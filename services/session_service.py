"""Session service for managing user sessions and profile setup"""

from datetime import datetime, timedelta
from models.user import save_user_profile, is_new_user
from services.message_service import send_whatsapp_message, send_telegram_message
from utils.constants import *
from utils.helpers import is_inactive_session, detect_platform


class SessionService:
    """
    Enhanced session service for LangGraph medical agent system
    
    Features:
    - Session state management for agent conversations
    - Profile setup flow coordination
    - Multi-platform support (WhatsApp/Telegram)
    - Activity tracking and cleanup
    - Agent state persistence
    """
    
    def __init__(self):
        """Initialize session storage"""
        self.user_sessions = {}
        self.profile_setup_sessions = {}
    
    def get_session(self, user_id):
        """Get or create user session"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                "text": None,
                "image": None,
                "location": None,
                "last_activity": datetime.now(),
                "profile_step": None,
                "awaiting_location_for_clinics": False,
                "agent_state": {},  # For LangGraph agent state persistence
                "conversation_context": []  # For maintaining context
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
            "awaiting_location_for_clinics": False,
            "agent_state": {},
            "conversation_context": []
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
    
    # New methods for LangGraph agent system
    def should_start_profile_setup(self, user_id):
        """Check if profile setup should be started for new user"""
        return is_new_user(user_id) and not self.is_in_profile_setup(user_id)
    
    def start_profile_setup(self, user_id, platform):
        """Start the profile setup process for new users"""
        self.profile_setup_sessions[user_id] = {
            "step": "age",
            "platform": platform,
            "started_at": datetime.now(),
            "temp_data": {}
        }
        
        # Send initial age request
        if platform == "whatsapp":
            send_whatsapp_message(user_id, AGE_REQUEST_MSG)
        else:
            send_telegram_message(user_id, AGE_REQUEST_MSG)
    
    def is_in_profile_setup(self, user_id):
        """Check if user is currently in profile setup flow"""
        return user_id in self.profile_setup_sessions
    
    def get_profile_setup_step(self, user_id):
        """Get current profile setup step"""
        if user_id in self.profile_setup_sessions:
            return self.profile_setup_sessions[user_id]["step"]
        return None
    
    def set_profile_setup_step(self, user_id, step):
        """Set profile setup step"""
        if user_id in self.profile_setup_sessions:
            self.profile_setup_sessions[user_id]["step"] = step
    
    def save_age(self, user_id, age):
        """Save user age during profile setup"""
        if user_id in self.profile_setup_sessions:
            self.profile_setup_sessions[user_id]["temp_data"]["age"] = age
    
    def save_gender(self, user_id, gender):
        """Save user gender during profile setup"""
        if user_id in self.profile_setup_sessions:
            self.profile_setup_sessions[user_id]["temp_data"]["gender"] = gender
    
    def complete_profile_setup(self, user_id):
        """Complete profile setup and save to database"""
        if user_id not in self.profile_setup_sessions:
            return False
        
        setup_data = self.profile_setup_sessions[user_id]
        temp_data = setup_data["temp_data"]
        platform = setup_data["platform"]
        
        age = temp_data.get("age")
        gender = temp_data.get("gender")
        
        # Save to database
        save_user_profile(user_id, age, gender, platform)
        
        # Clean up profile setup session
        del self.profile_setup_sessions[user_id]
        
        return True
    
    # Legacy methods for backward compatibility
    def start_profile_setup_legacy(self, user_id, platform):
        """Start the profile setup process for new users (legacy)"""
        session = self.get_session(user_id)
        session["profile_step"] = "age"
        
        if platform == "whatsapp":
            send_whatsapp_message(user_id, PROFILE_SETUP_START_MSG)
        else:
            send_telegram_message(user_id, PROFILE_SETUP_START_MSG)
    
    def handle_profile_setup(self, user_id, text, platform):
        """Handle user responses during profile setup (legacy)"""
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
        """Handle age setup step (legacy)"""
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
        """Handle gender setup step (legacy)"""
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
        """Check if user is currently setting up profile (legacy)"""
        session = self.get_session(user_id)
        return session.get("profile_step") is not None
    
    def should_start_profile_setup_legacy(self, user_id, text=None):
        """Check if profile setup should be started for new user (legacy)"""
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
    
    # Agent state management methods
    def save_agent_state(self, user_id, state_data):
        """Save LangGraph agent state for persistence"""
        session = self.get_session(user_id)
        session["agent_state"] = state_data
    
    def get_agent_state(self, user_id):
        """Get saved LangGraph agent state"""
        session = self.get_session(user_id)
        return session.get("agent_state", {})
    
    def add_conversation_context(self, user_id, message_type, content):
        """Add message to conversation context"""
        session = self.get_session(user_id)
        session["conversation_context"].append({
            "type": message_type,
            "content": content,
            "timestamp": datetime.now()
        })
        
        # Keep only last 10 messages to prevent memory bloat
        if len(session["conversation_context"]) > 10:
            session["conversation_context"] = session["conversation_context"][-10:]
    
    def get_conversation_context(self, user_id):
        """Get conversation context for agent"""
        session = self.get_session(user_id)
        return session.get("conversation_context", [])


# Global session service instance
session_service = SessionService()

def get_session_service():
    """Get session service instance"""
    return session_service 