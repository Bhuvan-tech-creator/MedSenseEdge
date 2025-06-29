"""Follow-up service for 24-hour symptom check-ins"""
import time
import threading
from datetime import datetime, timedelta
from models.user import get_pending_followups, mark_followup_sent, save_followup_response
from services.message_service import send_whatsapp_message, send_telegram_message
class FollowUpService:
    """Service to manage 24-hour follow-up check-ins"""
    def __init__(self):
        self.running = False
        self.check_interval = 300
    def start_scheduler(self):
        """Start the follow-up scheduler in a background thread"""
        if not self.running:
            self.running = True
            scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            scheduler_thread.start()
            print("✅ Follow-up scheduler started")
    def stop_scheduler(self):
        """Stop the follow-up scheduler"""
        self.running = False
        print("⏹️ Follow-up scheduler stopped")
    def _scheduler_loop(self):
        """Main scheduler loop that runs in background"""
        while self.running:
            try:
                self._process_pending_followups()
                time.sleep(self.check_interval)
            except Exception as e:
                print(f"Error in follow-up scheduler: {e}")
                time.sleep(60)
    def _process_pending_followups(self):
        """Process all pending follow-up reminders"""
        try:
            pending_followups = get_pending_followups()
            for followup in pending_followups:
                followup_id, user_id, platform, symptoms, diagnosis_id, scheduled_time = followup
                followup_message = self._create_followup_message(symptoms)
                success = False
                if platform == "whatsapp":
                    success = send_whatsapp_message(user_id, followup_message)
                elif platform == "telegram":
                    success = send_telegram_message(user_id, followup_message)
                if success:
                    mark_followup_sent(followup_id)
                    print(f"✅ Follow-up sent to {user_id} on {platform}")
                else:
                    print(f"❌ Failed to send follow-up to {user_id} on {platform}")
        except Exception as e:
            print(f"Error processing follow-ups: {e}")
    def _create_followup_message(self, original_symptoms):
        """Create a follow-up check-in message"""
        message = (
            f"🩺 **24-Hour Health Check-in**\n\n"
            f"Hi! Yesterday you consulted me about: *{original_symptoms[:50]}{'...' if len(original_symptoms) > 50 else ''}*\n\n"
            f"I wanted to check in on your health:\n"
            f"**Have your symptoms improved, stayed the same, or gotten worse?**\n\n"
            f"Please let me know how you're feeling now. If your symptoms have worsened or you have new concerns, I'm here to help! 💙"
        )
        return message
    def handle_followup_response(self, user_id, response_text):
        """Handle user's response to a follow-up check-in"""
        try:
            save_followup_response(user_id, response_text)
            response_lower = response_text.lower()
            if any(word in response_lower for word in ['better', 'improved', 'good', 'fine', 'well']):
                return (
                    "😊 **Great to hear you're feeling better!**\n\n"
                    "That's wonderful news. Continue taking care of yourself and don't hesitate to reach out if you have any new health concerns.\n\n"
                    "📍 **Please share your location if you would like a list of clinics near you and an alert if your location has been flagged by WHO for an epidemic alert.**"
                )
            elif any(word in response_lower for word in ['worse', 'worst', 'bad', 'terrible', 'pain']):
                return (
                    "😟 **I'm sorry to hear your symptoms have worsened.**\n\n"
                    "Since your condition hasn't improved in 24 hours, I recommend consulting with a healthcare professional for a proper evaluation.\n\n"
                    "Please describe your current symptoms so I can provide updated guidance:\n\n"
                    "📍 **Please share your location if you would like a list of clinics near you and an alert if your location has been flagged by WHO for an epidemic alert.**"
                )
            elif any(word in response_lower for word in ['same', 'similar', 'unchanged', 'no change']):
                return (
                    "📋 **I see your symptoms are about the same.**\n\n"
                    "If symptoms persist without improvement for more than a few days, it may be worth getting a professional evaluation.\n\n"
                    "Feel free to describe any changes or new symptoms you've noticed:\n\n"
                    "📍 **Please share your location if you would like a list of clinics near you and an alert if your location has been flagged by WHO for an epidemic alert.**"
                )
            else:
                return (
                    "🩺 **Thank you for the update on your health.**\n\n"
                    "I'm here to help if you'd like to describe your current symptoms in more detail or if you have any new health concerns.\n\n"
                    "📍 **Please share your location if you would like a list of clinics near you and an alert if your location has been flagged by WHO for an epidemic alert.**"
                )
        except Exception as e:
            print(f"Error handling follow-up response: {e}")
            return (
                "Thank you for your response. I'm here to help if you have any health concerns.\n\n"
                "📍 **Please share your location if you would like a list of clinics near you and an alert if your location has been flagged by WHO for an epidemic alert.**"
            )
followup_service = None
def get_followup_service():
    """Get or create follow-up service instance"""
    global followup_service
    if followup_service is None:
        followup_service = FollowUpService()
    return followup_service 
