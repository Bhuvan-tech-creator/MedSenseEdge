"""
Message processor using LangGraph Medical Agent System
Replaces simple LLM calls with sophisticated tool orchestration
"""
import asyncio
import threading
import hashlib
import re
from datetime import datetime, timedelta
from flask import current_app  # Added import
from services.medical_agent import get_medical_agent_system
from services.session_service import get_session_service
from services.external_apis import reverse_geocode
from utils.constants import WELCOME_MSG, PROFILE_SETUP_MSG, AGE_REQUEST_MSG, GENDER_REQUEST_MSG
from models.user import is_followup_response_expected
from services.followup_service import get_followup_service

class MessageProcessor:
    def __init__(self):
        self.session_service = get_session_service()
        # Request deduplication to prevent duplicate analyses
        self.processing_requests = {}
        self.completed_requests = {}
        self._lock = threading.Lock()
        
    def _generate_request_hash(self, user_id, message_type, content):
        """Generate unique hash for request deduplication"""
        content_str = str(content)[:200]  # Limit content length for hash
        request_string = f"{user_id}_{message_type}_{content_str}"
        return hashlib.md5(request_string.encode()).hexdigest()
    
    def _clean_old_requests(self):
        """Clean request tracking older than 10 minutes"""
        cutoff = datetime.now() - timedelta(minutes=10)
        with self._lock:
            # Clean processing requests
            to_remove = [req_hash for req_hash, timestamp in self.processing_requests.items() 
                        if timestamp < cutoff]
            for req_hash in to_remove:
                del self.processing_requests[req_hash]
            
            # Clean completed requests  
            to_remove = [req_hash for req_hash, (timestamp, _) in self.completed_requests.items()
                        if timestamp < cutoff]
            for req_hash in to_remove:
                del self.completed_requests[req_hash]
    
    def _is_duplicate_request(self, user_id, message_type, content):
        """Check if this request is already being processed or was recently completed"""
        request_hash = self._generate_request_hash(user_id, message_type, content)
        
        with self._lock:
            self._clean_old_requests()
            
            # Check if currently processing
            if request_hash in self.processing_requests:
                print(f"🔄 DUPLICATE: Request {request_hash[:8]} already processing for user {user_id}")
                return True, None
                
            # Check if recently completed
            if request_hash in self.completed_requests:
                _, cached_response = self.completed_requests[request_hash]
                print(f"💾 CACHED: Returning cached response {request_hash[:8]} for user {user_id}")
                return True, cached_response
                
            # Mark as processing
            self.processing_requests[request_hash] = datetime.now()
            return False, request_hash
    
    def _mark_request_completed(self, request_hash, response):
        """Mark request as completed and cache the response"""
        with self._lock:
            # Remove from processing
            if request_hash in self.processing_requests:
                del self.processing_requests[request_hash]
            
            # Add to completed with response
            self.completed_requests[request_hash] = (datetime.now(), response)
    
    def _get_agent_system(self):
        return get_medical_agent_system()
    
    def _run_async_analysis(self, agent_system, user_id, message, image_data, location, emergency):
        """Run async analysis in a new event loop with Flask app context"""
        # FLASK CONTEXT FIX: Capture the current app context
        app_context = current_app._get_current_object() if current_app else None
        
        loop = None
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # FLASK CONTEXT FIX: Push app context in the new thread
            if app_context:
                with app_context.app_context():
                    result = loop.run_until_complete(
                        agent_system.analyze_medical_query(
                            user_id=user_id,
                            message=message,
                            image_data=image_data,
                            location=location,
                            emergency=emergency
                        )
                    )
            else:
                # Fallback if no app context available
                print("⚠️ WARNING: No Flask app context available - some features may not work")
                result = loop.run_until_complete(
                    agent_system.analyze_medical_query(
                        user_id=user_id,
                        message=message,
                        image_data=image_data,
                        location=location,
                        emergency=emergency
                    )
                )
            
            return result
        except Exception as e:
            print(f"❌ Error in async analysis: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "fallback_message": "I encountered a technical issue analyzing your request."
            }
        finally:
            # Clean up the event loop safely
            if loop is not None:
                try:
                    loop.close()
                except:
                    pass

    def handle_text_message(self, sender, text, platform):
        try:
            # Check for followup responses first (no deduplication needed)
            if is_followup_response_expected(sender):
                followup_service = get_followup_service()
                return followup_service.handle_followup_response(sender, text)
            
            # Check for profile setup
            if self.session_service.should_start_profile_setup(sender):
                print(f"🔄 Starting profile setup for new user {sender} on {platform}")
                self.session_service.start_profile_setup(sender, platform)
                return None
            
            if self.session_service.is_in_profile_setup(sender):
                print(f"👤 Handling profile setup step for {sender} on {platform}")
                return self._handle_profile_setup(sender, text, platform)
            
            # Check for duplicate request
            is_duplicate, cache_result = self._is_duplicate_request(sender, "text", text)
            if is_duplicate:
                return cache_result  # Return cached response or None if still processing
            
            request_hash = cache_result  # cache_result is actually request_hash when not duplicate
            
            print(f"🔄 PROCESSING: New text analysis {request_hash[:8]} for user {sender}")
            
            # Process with medical agent - simplified approach
            try:
                agent_system = self._get_agent_system()
                result = self._run_async_analysis(agent_system, sender, text, None, None, False)
                
                if result.get("success"):
                    response = result.get("analysis", "I couldn't analyze your query. Please try again.")
                else:
                    response = result.get("fallback_message", "I encountered an issue. Please try again.")
                
                # Cache the response
                self._mark_request_completed(request_hash, response)
                print(f"✅ COMPLETED: Text analysis {request_hash[:8]} for user {sender}")
                return response
                
            except Exception as e:
                print(f"❌ ERROR: Text analysis {request_hash[:8]} failed: {str(e)}")
                error_response = "I apologize, but I'm experiencing technical difficulties. Please try again or consult a healthcare professional if your concern is urgent."
                self._mark_request_completed(request_hash, error_response)
                return error_response
                
        except Exception as e:
            print(f"Error processing text message: {e}")
            return "I apologize, but I'm experiencing technical difficulties. Please try again or consult a healthcare professional if your concern is urgent."

    def handle_image_message(self, sender, image_base64, platform, caption_text=None):
        try:
            if self.session_service.should_start_profile_setup(sender):
                self.session_service.start_profile_setup(sender, platform)
                return None
            
            if self.session_service.is_in_profile_setup(sender):
                return "Please complete your profile setup first before sending images."
            
            # Create content hash for image (use first 100 chars of base64 + caption)
            image_content = f"{image_base64[:100]}_{caption_text or ''}"
            
            # Check for duplicate request
            is_duplicate, cache_result = self._is_duplicate_request(sender, "image", image_content)
            if is_duplicate:
                return cache_result
            
            request_hash = cache_result
            print(f"🔄 PROCESSING: New image analysis {request_hash[:8]} for user {sender}")
            
            if caption_text and caption_text.strip():
                image_message = caption_text.strip()
            else:
                image_message = "Please analyze this medical image for any health concerns."
            
            try:
                agent_system = self._get_agent_system()
                result = self._run_async_analysis(agent_system, sender, image_message, image_base64, None, False)
                
                if result.get("success"):
                    response = result.get("analysis", "I couldn't analyze the image. Please try again.")
                else:
                    response = result.get("fallback_message", "I couldn't analyze the image. Please try again.")
                
                self._mark_request_completed(request_hash, response)
                print(f"✅ COMPLETED: Image analysis {request_hash[:8]} for user {sender}")
                return response
                
            except Exception as e:
                print(f"❌ ERROR: Image analysis {request_hash[:8]} failed: {str(e)}")
                error_response = "I couldn't analyze the image. Please try sending it again or describe your symptoms in text."
                self._mark_request_completed(request_hash, error_response)
                return error_response
                
        except Exception as e:
            print(f"Error processing image message: {e}")
            return "I couldn't analyze the image. Please try sending it again or describe your symptoms in text."

    def handle_location_message(self, sender, latitude, longitude, platform):
        try:
            if self.session_service.should_start_profile_setup(sender):
                self.session_service.start_profile_setup(sender, platform)
                return None
            
            if self.session_service.is_in_profile_setup(sender):
                return "Please complete your profile setup first before sharing location."
            
            location_content = f"{latitude}_{longitude}"
            
            # Check for duplicate request
            is_duplicate, cache_result = self._is_duplicate_request(sender, "location", location_content)
            if is_duplicate:
                return cache_result
            
            request_hash = cache_result
            print(f"🔄 PROCESSING: New location analysis {request_hash[:8]} for user {sender}")
            
            location_name = reverse_geocode(latitude, longitude)
            location_message = f"Please find medical facilities and health information for my current location: {location_name}. Also check for any disease outbreaks in this area."
            
            try:
                agent_system = self._get_agent_system()
                result = self._run_async_analysis(agent_system, sender, location_message, None, location_name, False)
                
                if result.get("success"):
                    response = result.get("analysis", "I couldn't process your location. Please try again.")
                else:
                    response = result.get("fallback_message", "I couldn't process your location. Please try again.")
                
                self._mark_request_completed(request_hash, response)
                print(f"✅ COMPLETED: Location analysis {request_hash[:8]} for user {sender}")
                return response
                
            except Exception as e:
                print(f"❌ ERROR: Location analysis {request_hash[:8]} failed: {str(e)}")
                error_response = "I couldn't process your location. Please try again or describe where you're looking for medical facilities."
                self._mark_request_completed(request_hash, error_response)
                return error_response
                
        except Exception as e:
            print(f"Error processing location message: {e}")
            return "I couldn't process your location. Please try again or describe where you're looking for medical facilities."

    def _handle_profile_setup(self, sender, text, platform):
        try:
            setup_step = self.session_service.get_profile_setup_step(sender)
            if setup_step == "age":
                age = self._extract_age_from_text(text)
                if age:
                    self.session_service.save_age(sender, age)
                    self.session_service.set_profile_setup_step(sender, "gender")
                    return GENDER_REQUEST_MSG
                else:
                    return "Please provide a valid age (e.g., '25' or 'I am 25 years old')."
            elif setup_step == "gender":
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
        try:
            numbers = re.findall(r'\b\d+\b', text)
            for num_str in numbers:
                age = int(num_str)
                if 1 <= age <= 120:
                    return age
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
        try:
            text_lower = text.lower().strip()
            if any(word in text_lower for word in ['male', 'man', 'boy', 'masculine']):
                return 'male'
            elif any(word in text_lower for word in ['female', 'woman', 'girl', 'feminine']):
                return 'female'
            elif any(word in text_lower for word in ['other', 'non-binary', 'nonbinary', 'nb']):
                return 'other'
            elif any(word in text_lower for word in ['prefer not', 'not say', 'private', 'none']):
                return 'prefer_not_to_say'
            if text_lower in ['m', 'f', 'o', 'n']:
                mapping = {'m': 'male', 'f': 'female', 'o': 'other', 'n': 'prefer_not_to_say'}
                return mapping[text_lower]
            return None
        except Exception as e:
            print(f"Error extracting gender: {e}")
            return None

message_processor = None
def get_message_processor():
    global message_processor
    if message_processor is None:
        message_processor = MessageProcessor()
    return message_processor 
