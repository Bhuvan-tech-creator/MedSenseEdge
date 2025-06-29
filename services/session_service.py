"""Session service for managing user sessions and profile setup"""

from datetime import datetime, timedelta
from models.user import save_user_profile, is_new_user
from services.message_service import send_whatsapp_message, send_telegram_message
from utils.constants import *
from utils.helpers import is_inactive_session, detect_platform


class SessionService:
    """Service for managing user sessions"""
    
    def __init__(self):
        """Initialize session storage"""
        self.user_sessions = {}
    
    def get_session(self, user_id):
        """Get or create user session"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                "text": None,
                "image": None,
                "location": None,
                "last_activity": datetime.now(),
                "profile_step": None,
                "awaiting_location_for_clinics": False
            }
        return self.user_sessions[user_id]
    
    def update_session_activity(self, user_id):
        """Update last activity timestamp for user"""
        session = self.get_session(user_id)
        session["last_activity"] = datetime.now()
    
    def clear_session(self, user_id):
        """Clear user session data"""
        self.user_sessions[user_id] = {
            "text": None,
            "image": None,
            "location": None,
            "last_activity": datetime.now(),
            "profile_step": None,
            "awaiting_location_for_clinics": False
        }
    
    def clear_inactive_sessions(self, hours_threshold=48):
        """Clear sessions for users inactive for more than specified hours"""
        inactive_users = []
        for user_id, session in self.user_sessions.items():
            last_activity = session.get('last_activity', datetime.now())
            if is_inactive_session(last_activity, hours_threshold):
                inactive_users.append(user_id)
        
        for user_id in inactive_users:
            self.clear_session(user_id)
            print(f"Cleared session for inactive user {user_id}")
    
    def start_profile_setup(self, user_id, platform):
        """Start the profile setup process for new users"""
        session = self.get_session(user_id)
        session["profile_step"] = "age"
        
        if platform == "whatsapp":
            send_whatsapp_message(user_id, PROFILE_SETUP_START_MSG)
        else:
            send_telegram_message(user_id, PROFILE_SETUP_START_MSG)
    
    def handle_profile_setup(self, user_id, text, platform):
        """Handle user responses during profile setup"""
        session = self.get_session(user_id)
        step = session.get("profile_step")
        
        if step == "age":
            message = self._handle_age_setup(user_id, text, session)
        elif step == "gender":
            message = self._handle_gender_setup(user_id, text, session, platform)
        else:
            message = "Something went wrong. Please start over."
            session["profile_step"] = None
        
        if platform == "whatsapp":
            send_whatsapp_message(user_id, message)
        else:
            send_telegram_message(user_id, message)
    
    def _handle_age_setup(self, user_id, text, session):
        """Handle age setup step"""
        if text.lower() == "skip":
            session["profile_step"] = None
            return "No problem! You can start using MedSense AI right away.\n\n" + WELCOME_MSG
        else:
            try:
                age = int(text)
                if 1 <= age <= 120:
                    session["temp_age"] = age
                    session["profile_step"] = "gender"
                    return PROFILE_GENDER_PROMPT
                else:
                    return PROFILE_AGE_PROMPT
            except ValueError:
                return PROFILE_AGE_PROMPT
    
    def _handle_gender_setup(self, user_id, text, session, platform):
        """Handle gender setup step"""
        if text.lower() == "skip":
            age = session.get("temp_age")
            if age:
                save_user_profile(user_id, age, None, platform)
            session["profile_step"] = None
            session.pop("temp_age", None)
            return PROFILE_COMPLETE_NO_GENDER + WELCOME_MSG
        else:
            gender = text.lower()
            if gender in ["male", "female", "other", "m", "f"]:
                if gender in ["m", "male"]:
                    gender = "Male"
                elif gender in ["f", "female"]:
                    gender = "Female"
                else:
                    gender = "Other"
                    
                age = session.get("temp_age")
                save_user_profile(user_id, age, gender, platform)
                session["profile_step"] = None
                session.pop("temp_age", None)
                return PROFILE_COMPLETE_WITH_GENDER.format(age=age, gender=gender) + WELCOME_MSG
            else:
                return PROFILE_GENDER_INVALID
    
    def is_setting_up_profile(self, user_id):
        """Check if user is currently setting up profile"""
        session = self.get_session(user_id)
        return session.get("profile_step") is not None
    
    def should_start_profile_setup(self, user_id, text=None):
        """Check if profile setup should be started for new user"""
        if text and text.lower() in ["skip", "help", "emergency"]:
            return False
        return is_new_user(user_id)
    
    def set_awaiting_location(self, user_id, awaiting=True):
        """Set whether user is awaiting location for clinic recommendations"""
        session = self.get_session(user_id)
        session["awaiting_location_for_clinics"] = awaiting
    
    def is_awaiting_location(self, user_id):
        """Check if user is awaiting location for clinic recommendations"""
        session = self.get_session(user_id)
        return session.get("awaiting_location_for_clinics", False)


# Global session service instance
session_service = SessionService()

def get_session_service():
    """Get session service instance"""
    return session_service 