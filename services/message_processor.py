"""
Message processor using LangGraph Medical Agent System
Replaces simple LLM calls with sophisticated tool orchestration
"""

import asyncio
from services.medical_agent import get_medical_agent_system
from services.session_service import get_session_service
from services.external_apis import reverse_geocode, detect_and_save_country_from_text
from utils.constants import WELCOME_MSG, PROFILE_SETUP_MSG, AGE_REQUEST_MSG, GENDER_REQUEST_MSG
from models.user import is_followup_response_expected
from services.followup_service import get_followup_service


class MessageProcessor:
    """
    Advanced message processor using LangGraph medical agent system
    
    Features:
    - Tool-based medical analysis instead of simple LLM chains
    - Adaptive routing between multiple specialized tools
    - Context-aware conversation management
    - Multi-modal support (text + images)
    - Location-aware clinic finding
    - Disease outbreak monitoring
    - Web search integration for latest medical information
    - 24-hour follow-up tracking
    """
    
    def __init__(self):
        """Initialize the message processor with agent system"""
        self.session_service = get_session_service()
        
    def _get_agent_system(self):
        """Get the medical agent system instance"""
        return get_medical_agent_system()
    
    def handle_text_message(self, sender, text, platform):
        """
        Handle text messages using the LangGraph medical agent
        
        Replaces simple LLM calls with sophisticated tool orchestration:
        - Intent analysis and classification
        - Intelligent tool selection and execution
        - Safety checking and emergency detection
        - Response synthesis from multiple sources
        - Follow-up response handling
        """
        try:
            # Check if this is a response to a 24-hour follow-up
            if is_followup_response_expected(sender):
                followup_service = get_followup_service()
                return followup_service.handle_followup_response(sender, text)
            
            # Check if user needs profile setup
            if self.session_service.should_start_profile_setup(sender):
                self.session_service.start_profile_setup(sender, platform)
                return PROFILE_SETUP_MSG
            
            # Handle profile setup flow
            if self.session_service.is_in_profile_setup(sender):
                return self._handle_profile_setup(sender, text, platform)
            
            # Auto-detect and save country mentions for outbreak monitoring BEFORE agent processing
            detected_country = None
            try:
                detected_country = detect_and_save_country_from_text(sender, text, platform)
                if detected_country:
                    # Country was detected and saved - outbreak monitoring is now enabled
                    print(f"🌍 Country detection: {detected_country} saved for user {sender}")
                    print(f"✅ Country saved BEFORE agent processing - outbreak tool will now work!")
            except Exception as e:
                print(f"⚠️ Country detection error: {e}")
            
            # Process through LangGraph medical agent system
            agent_system = self._get_agent_system()
            
            # Run async agent processing in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    agent_system.analyze_medical_query(
                        user_id=sender,
                        message=text,
                        image_data=None,
                        location=None,
                        emergency=False
                    )
                )
                
                # Extract response from result
                if result.get("success"):
                    return result.get("analysis", "I couldn't analyze your query. Please try again.")
                else:
                    return result.get("fallback_message", "I encountered an issue. Please try again.")
                    
            finally:
                loop.close()
            
        except Exception as e:
            print(f"Error processing text message: {e}")
            return "I apologize, but I'm experiencing technical difficulties. Please try again or consult a healthcare professional if your concern is urgent."
    
    def handle_image_message(self, sender, image_base64, platform, caption_text=None):
        """
        Handle image messages using the LangGraph medical agent
        
        Features advanced multi-modal analysis:
        - Computer vision medical image analysis
        - Integration with user profile and history
        - Clinical database validation
        - Safety checking for emergency conditions
        - Support for image + text combinations
        """
        try:
            # Check if user needs profile setup
            if self.session_service.should_start_profile_setup(sender):
                self.session_service.start_profile_setup(sender, platform)
                return PROFILE_SETUP_MSG
            
            # Handle profile setup flow
            if self.session_service.is_in_profile_setup(sender):
                return "Please complete your profile setup first before sending images."
            
            # Auto-detect and save country mentions for outbreak monitoring (from image caption)
            if caption_text and caption_text.strip():
                try:
                    detected_country = detect_and_save_country_from_text(sender, caption_text.strip(), platform)
                    if detected_country:
                        print(f"🌍 Country detection from image caption: {detected_country} saved for user {sender}")
                except Exception as e:
                    print(f"⚠️ Country detection error from image caption: {e}")
            
            # Process image through LangGraph medical agent system
            agent_system = self._get_agent_system()
            
            # Use provided text or create default message
            if caption_text and caption_text.strip():
                image_message = caption_text.strip()
            else:
                image_message = "Please analyze this medical image for any health concerns."
            
            # Run async agent processing in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    agent_system.analyze_medical_query(
                        user_id=sender,
                        message=image_message,
                        image_data=image_base64,
                        location=None,
                        emergency=False
                    )
                )
                
                # Extract response from result
                if result.get("success"):
                    return result.get("analysis", "I couldn't analyze the image. Please try again.")
                else:
                    return result.get("fallback_message", "I couldn't analyze the image. Please try again.")
                    
            finally:
                loop.close()
            
        except Exception as e:
            print(f"Error processing image message: {e}")
            return "I couldn't analyze the image. Please try sending it again or describe your symptoms in text."
    
    def handle_location_message(self, sender, latitude, longitude, platform):
        """
        Handle location messages using the LangGraph medical agent
        
        Features location-aware medical services:
        - Nearby clinic and hospital finder
        - Location-specific disease outbreak alerts
        - Emergency services information
        - Travel health advisories
        """
        try:
            # Check if user needs profile setup
            if self.session_service.should_start_profile_setup(sender):
                self.session_service.start_profile_setup(sender, platform)
                return PROFILE_SETUP_MSG
            
            # Handle profile setup flow
            if self.session_service.is_in_profile_setup(sender):
                return "Please complete your profile setup first before sharing location."
            
            # Get location name for context
            location_name = reverse_geocode(latitude, longitude)
            
            # Extract and save country from location for outbreak monitoring
            try:
                if location_name:
                    # Try to extract country from reverse geocoded address
                    # Addresses usually end with country name (e.g., "123 Main St, City, State, Country")
                    address_parts = location_name.split(', ')
                    if len(address_parts) >= 2:
                        potential_country = address_parts[-1].strip()
                        # Save the country for outbreak monitoring
                        from models.user import save_user_country
                        success = save_user_country(sender, potential_country, platform)
                        if success:
                            print(f"🌍 Country extracted from location: {potential_country} saved for user {sender}")
            except Exception as e:
                print(f"⚠️ Error extracting country from location: {e}")
            
            # Create message requesting clinic information
            location_message = f"Please find medical facilities and health information for my current location: {location_name}. Also check for any disease outbreaks in this area."
            
            # Process through LangGraph medical agent system
            agent_system = self._get_agent_system()
            
            # Run async agent processing in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    agent_system.analyze_medical_query(
                        user_id=sender,
                        message=location_message,
                        image_data=None,
                        location=location_name,
                        emergency=False
                    )
                )
                
                # Extract response from result
                if result.get("success"):
                    return result.get("analysis", "I couldn't process your location. Please try again.")
                else:
                    return result.get("fallback_message", "I couldn't process your location. Please try again.")
                    
            finally:
                loop.close()
            
        except Exception as e:
            print(f"Error processing location message: {e}")
            return "I couldn't process your location. Please try again or describe where you're looking for medical facilities."
    
    def _handle_profile_setup(self, sender, text, platform):
        """
        Handle profile setup flow with enhanced user experience
        
        Features:
        - Natural language processing for age/gender extraction
        - Validation and error handling
        - Multi-language support
        - Platform-specific formatting
        """
        try:
            setup_step = self.session_service.get_profile_setup_step(sender)
            
            if setup_step == "age":
                # Enhanced age processing with natural language understanding
                age = self._extract_age_from_text(text)
                if age:
                    self.session_service.save_age(sender, age)
                    self.session_service.set_profile_setup_step(sender, "gender")
                    return GENDER_REQUEST_MSG
                else:
                    return "Please provide a valid age (e.g., '25' or 'I am 25 years old')."
            
            elif setup_step == "gender":
                # Enhanced gender processing with flexible input recognition
                gender = self._extract_gender_from_text(text)
                if gender:
                    self.session_service.save_gender(sender, gender)
                    self.session_service.complete_profile_setup(sender)
                    
                    welcome_message = f"✅ Profile setup complete!\n\n🤖 I'm MedSense AI, your personal medical assistant powered by advanced tool orchestration. I can help you with:\n\n🔍 Intelligent symptom analysis\n📸 Medical image analysis\n🌐 Latest medical research\n🏥 Nearby clinics & hospitals\n⚠️ Disease outbreak alerts\n🩺 Clinical validation\n\nHow can I help you today?"
                    
                    return welcome_message
                else:
                    return "Please specify your gender (e.g., 'male', 'female', 'other', or 'prefer not to say')."
            
            return "Please complete your profile setup."
            
        except Exception as e:
            print(f"Error in profile setup: {e}")
            return "There was an error setting up your profile. Please try again."
    
    def _extract_age_from_text(self, text):
        """Extract age from user text with natural language processing"""
        try:
            # Simple extraction logic - can be enhanced with NLP
            import re
            
            # Look for numbers in the text
            numbers = re.findall(r'\b\d+\b', text)
            
            for num_str in numbers:
                age = int(num_str)
                # Reasonable age range validation
                if 1 <= age <= 120:
                    return age
            
            # Look for spelled out numbers
            age_words = {
                'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
                'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
                'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
                'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
                'eighty': 80, 'ninety': 90
            }
            
            text_lower = text.lower()
            for word, value in age_words.items():
                if word in text_lower:
                    return value
            
            return None
            
        except Exception as e:
            print(f"Error extracting age: {e}")
            return None
    
    def _extract_gender_from_text(self, text):
        """Extract gender from user text with flexible recognition"""
        try:
            text_lower = text.lower().strip()
            
            # Direct matches
            if any(word in text_lower for word in ['male', 'man', 'boy', 'masculine']):
                return 'male'
            elif any(word in text_lower for word in ['female', 'woman', 'girl', 'feminine']):
                return 'female'
            elif any(word in text_lower for word in ['other', 'non-binary', 'nonbinary', 'nb']):
                return 'other'
            elif any(word in text_lower for word in ['prefer not', 'not say', 'private', 'none']):
                return 'prefer_not_to_say'
            
            # Single letter recognition
            if text_lower in ['m', 'f', 'o', 'n']:
                mapping = {'m': 'male', 'f': 'female', 'o': 'other', 'n': 'prefer_not_to_say'}
                return mapping[text_lower]
            
            return None
            
        except Exception as e:
            print(f"Error extracting gender: {e}")
            return None


# Global instance
message_processor = None

def get_message_processor():
    """Get or create message processor instance"""
    global message_processor
    if message_processor is None:
        message_processor = MessageProcessor()
    return message_processor 