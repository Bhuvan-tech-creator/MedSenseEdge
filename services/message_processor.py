"""Message processor service for handling user inputs and orchestrating medical analysis"""

from models.user import (
    get_user_history, get_history_id, save_feedback, save_user_location, 
    save_user_country, get_user_country
)
from services.medical_analysis import get_medical_analysis_service
from services.external_apis import reverse_geocode, find_nearby_clinics, check_disease_outbreaks_for_user
from services.session_service import get_session_service
from utils.constants import *
from utils.helpers import (
    format_history_text, is_country_mention, contains_symptom_keywords,
    format_clinic_recommendations
)


class MessageProcessor:
    """Service for processing user messages and coordinating responses"""
    
    def __init__(self):
        self.session_service = get_session_service()
        self.medical_service = None
    
    def get_medical_service(self):
        """Lazy load medical analysis service"""
        if self.medical_service is None:
            self.medical_service = get_medical_analysis_service()
        return self.medical_service
    
    def handle_text_message(self, user_id, text, platform):
        """Handle text message from user"""
        session = self.session_service.get_session(user_id)
        
        # Check if user is setting up profile
        if self.session_service.is_setting_up_profile(user_id):
            self.session_service.handle_profile_setup(user_id, text, platform)
            return
        
        # Check if new user needs profile setup
        if self.session_service.should_start_profile_setup(user_id, text):
            self.session_service.start_profile_setup(user_id, platform)
            return
        
        # Handle special commands
        response = self._handle_special_commands(user_id, text, session)
        if response:
            return response
        
        # Handle country detection
        country_response = self._handle_country_detection(user_id, text, platform)
        if country_response:
            return country_response
        
        # Handle regular symptom text
        session["text"] = text
        return self._handle_partial_input(user_id, session)
    
    def handle_image_message(self, user_id, image_base64, platform):
        """Handle image message from user"""
        # Check if new user needs profile setup
        if self.session_service.should_start_profile_setup(user_id):
            self.session_service.start_profile_setup(user_id, platform)
            return
        
        session = self.session_service.get_session(user_id)
        session["image"] = image_base64
        return self._handle_partial_input(user_id, session)
    
    def handle_location_message(self, user_id, latitude, longitude, platform):
        """Handle location sharing from user"""
        # Get address from coordinates
        address = reverse_geocode(latitude, longitude)
        
        session = self.session_service.get_session(user_id)
        
        # Check if we're waiting for location after diagnosis
        if self.session_service.is_awaiting_location(user_id):
            # Provide clinic recommendations only
            clinics = find_nearby_clinics(latitude, longitude)
            save_user_location(user_id, latitude, longitude, address, platform)
            
            clinic_response = format_clinic_recommendations(clinics, address)
            self.session_service.set_awaiting_location(user_id, False)
            
            return clinic_response
        else:
            # Regular location sharing during symptom input
            location_data = {"lat": latitude, "lon": longitude, "address": address}
            session["location"] = location_data
            save_user_location(user_id, latitude, longitude, address, platform)
            
            return LOCATION_RECEIVED_MSG.format(address=address)
    
    def _handle_special_commands(self, user_id, text, session):
        """Handle special commands like help, emergency, history, etc."""
        text_lower = text.lower()
        
        if text_lower == "help":
            return HELP_MSG
        elif text_lower == "emergency":
            return EMERGENCY_MSG
        elif text_lower == "history":
            history = get_user_history(user_id)
            return format_history_text(history)
        elif text_lower == "clear":
            self.session_service.clear_session(user_id)
            return SESSION_CLEARED_MSG
        elif text_lower == "proceed":
            return self._process_user_input(user_id, session)
        elif text_lower in ["good", "bad"]:
            return self._handle_feedback(user_id, text_lower)
        
        return None
    
    def _handle_country_detection(self, user_id, text, platform):
        """Handle country name detection and save"""
        if not get_user_country(user_id) and is_country_mention(text, COUNTRY_KEYWORDS):
            country_name = text.title()
            save_user_country(user_id, country_name, platform)
            
            # Check for disease outbreaks
            outbreaks = check_disease_outbreaks_for_user(user_id)
            if outbreaks:
                return f"🌍 Thank you! I've saved {country_name} as your country.\n\n⚠️ Disease Alert: There are {len(outbreaks)} disease outbreak(s) currently reported in {country_name}. Stay informed and follow local health guidelines.\n\nFeel free to ask about symptoms or type 'history' to see past consultations."
            else:
                return f"🌍 Thank you! I've saved {country_name} as your country. I'll notify you of any disease outbreaks in your area.\n\nFeel free to ask about symptoms or type 'history' to see past consultations."
        
        return None
    
    def _handle_feedback(self, user_id, feedback):
        """Handle user feedback on diagnosis"""
        history = get_user_history(user_id, days_back=1)
        if history:
            history_id = get_history_id(user_id, history[0][2])
            if history_id:
                save_feedback(user_id, history_id, feedback)
                return FEEDBACK_THANKS_MSG.format(feedback=feedback)
            else:
                return NO_RECENT_DIAGNOSIS_MSG
        else:
            return NO_RECENT_DIAGNOSIS_MSG
    
    def _handle_partial_input(self, user_id, session):
        """Handle partial input (text only or image only)"""
        text = session.get("text")
        image = session.get("image")
        location = session.get("location")
        
        location_prompt = ""
        if location:
            location_prompt = f"\n📍 Location: {location['address']}"
        
        if text and not image:
            # Generate language-aware response for text-only case
            medical_service = self.get_medical_service()
            template = TEXT_ONLY_TEMPLATE.format(text=text, location=location_prompt)
            return medical_service.generate_language_aware_response(text, template)
        elif image and not text:
            # For image-only, ask for text in English (no user text to detect from)
            return IMAGE_ONLY_TEMPLATE.format(location=location_prompt)
        else:
            # Both available - proceed with analysis
            return self._process_user_input(user_id, session)
    
    def _process_user_input(self, user_id, session):
        """Process user input for medical analysis"""
        text = session.get("text")
        image = session.get("image")
        
        if not text and not image:
            return DEFAULT_SYMPTOMS_PROMPT
        
        medical_service = self.get_medical_service()
        user_country = get_user_country(user_id)
        
        # Perform medical analysis based on available input
        if text and image:
            reply = medical_service.analyze_combined_symptoms(user_id, text, image)
        elif text and not image:
            reply = medical_service.analyze_text_symptoms(user_id, text)
        elif image and not text:
            reply = medical_service.analyze_image_symptoms(user_id, image)
        else:
            return DEFAULT_SYMPTOMS_PROMPT
        
        # Clear session after analysis
        self.session_service.clear_session(user_id)
        self.session_service.set_awaiting_location(user_id, True)
        
        # Add disease outbreak alerts if applicable
        if user_country:
            outbreaks = check_disease_outbreaks_for_user(user_id)
            if outbreaks:
                medical_service = self.get_medical_service()
                outbreak_text = medical_service.generate_language_aware_response(
                    text or "symptoms", 
                    f"⚠️ Disease Alert: There are {len(outbreaks)} disease outbreak(s) reported in {user_country}."
                )
                reply += f"\n\n{outbreak_text}"
        
        return reply + FEEDBACK_PROMPT


# Global message processor instance
message_processor = MessageProcessor()

def get_message_processor():
    """Get message processor instance"""
    return message_processor 