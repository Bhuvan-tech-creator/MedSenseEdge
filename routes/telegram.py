"""Telegram webhook routes"""
import threading
import time
from datetime import datetime
from flask import Blueprint, request, current_app
from services.message_service import (
    send_telegram_message, get_telegram_file_path, download_telegram_image
)
from services.message_processor import get_message_processor
from services.session_service import get_session_service
from utils.constants import (
    WELCOME_MSG, IMAGE_ERROR_MSG, PROCESSING_TEXT_MSG, 
    PROCESSING_IMAGE_MSG, PROCESSING_LOCATION_MSG
)

telegram_bp = Blueprint('telegram', __name__)

def _process_telegram_message_background(chat_id, message_type, content, app_context):
    """Process telegram message in background thread"""
    try:
        # Push Flask app context for background thread
        with app_context.app_context():
            print(f"🔄 TELEGRAM BG: Background processing started for {chat_id}")
            
            message_processor = get_message_processor()
            response = None
            
            if message_type == "text":
                text, immediate_msg = content
                print(f"📝 TELEGRAM BG: Processing text message: '{text[:50]}...'")
                
                # Send immediate processing message
                print(f"⚡ TELEGRAM BG: Sending immediate processing message to {chat_id}")
                send_telegram_message(chat_id, immediate_msg)
                
                # Process the message
                response = message_processor.handle_text_message(chat_id, text, "telegram")
                
            elif message_type == "image":
                image_base64, immediate_msg = content
                print(f"🖼️ TELEGRAM BG: Processing image message for {chat_id}")
                
                # Send immediate processing message
                print(f"⚡ TELEGRAM BG: Sending immediate processing message to {chat_id}")
                send_telegram_message(chat_id, immediate_msg)
                
                # Process the image
                response = message_processor.handle_image_message(chat_id, image_base64, "telegram")
                
            elif message_type == "location":
                latitude, longitude, immediate_msg = content
                print(f"📍 TELEGRAM BG: Processing location message for {chat_id}")
                
                # Send immediate processing message
                print(f"⚡ TELEGRAM BG: Sending immediate processing message to {chat_id}")
                send_telegram_message(chat_id, immediate_msg)
                
                # Process the location
                response = message_processor.handle_location_message(chat_id, latitude, longitude, "telegram")
            
            # Send final response if available
            if response:
                print(f"✅ TELEGRAM BG: Sending final response to {chat_id}")
                send_telegram_message(chat_id, response)
                print(f"🎉 TELEGRAM BG: Background processing completed for {chat_id}")
            else:
                print(f"⚠️ TELEGRAM BG: No response generated for {chat_id}")
                
    except Exception as e:
        print(f"❌ TELEGRAM BG: Error in background processing for {chat_id}: {str(e)}")
        try:
            # Send error message to user
            error_msg = "I apologize, but I encountered a technical issue. Please try again or consult a healthcare professional if urgent."
            send_telegram_message(chat_id, error_msg)
        except:
            print(f"❌ TELEGRAM BG: Failed to send error message to {chat_id}")

@telegram_bp.route("/webhook/telegram", methods=["POST"])
def telegram_webhook():
    """Telegram webhook endpoint with background processing"""
    session_service = get_session_service()
    
    # Clean up inactive sessions
    session_service.clear_inactive_sessions()
    
    try:
        data = request.get_json()
        if "message" not in data:
            return "No message data received", 200
            
        msg = data["message"]
        chat_id = str(msg.get("chat", {}).get("id", ""))
        
        if not chat_id:
            return "No chat_id", 400
            
        # Track timing
        start_time = time.time()
        timestamp = datetime.now().strftime("%H:%M:%S.%f")
        
        print(f"📨 TELEGRAM: Received message from {chat_id} at {timestamp}")
        
        # Update session activity
        session_service.update_session_activity(chat_id)
        elapsed = time.time() - start_time
        print(f"🔄 TELEGRAM: Session updated for {chat_id} at {elapsed:.3f}s")
        
        # Handle /start command immediately (no background processing needed)
        if "text" in msg and msg["text"].startswith("/start"):
            if session_service.should_start_profile_setup(chat_id):
                session_service.start_profile_setup(chat_id, "telegram")
            else:
                send_telegram_message(chat_id, WELCOME_MSG)
            elapsed = time.time() - start_time
            print(f"🏁 TELEGRAM: Webhook completed for {chat_id} in {elapsed:.3f}s")
            return "Start command processed successfully", 200
        
        # Check if user is in profile setup (handle immediately)
        if session_service.is_in_profile_setup(chat_id):
            message_processor = get_message_processor()
            if "text" in msg:
                text = msg["text"]
                if text.startswith("/"):
                    text = text[1:]
                response = message_processor.handle_text_message(chat_id, text, "telegram")
                if response:
                    send_telegram_message(chat_id, response)
            elapsed = time.time() - start_time
            print(f"🏁 TELEGRAM: Webhook completed for {chat_id} in {elapsed:.3f}s")
            return "Profile setup message processed successfully", 200
            
        # Check if user should start profile setup
        if session_service.should_start_profile_setup(chat_id):
            print(f"✅ TELEGRAM: User {chat_id} not in profile setup, allowing processing message")
        else:
            print(f"✅ TELEGRAM: User {chat_id} not in profile setup, allowing processing message")
        
        # Get app context for background processing
        app_context = current_app._get_current_object()
        
        # Start background processing for different message types
        if "text" in msg:
            text = msg["text"]
            if text.startswith("/"):
                text = text[1:]
                
            print(f"🚀 TELEGRAM: Starting background processing for {chat_id} at {elapsed:.3f}s")
            
            # Start background thread for text processing
            thread = threading.Thread(
                target=_process_telegram_message_background,
                args=(chat_id, "text", (text, PROCESSING_TEXT_MSG), app_context),
                daemon=True
            )
            thread.start()
            
        elif "photo" in msg:
            photos = msg["photo"]
            file_id = photos[-1]["file_id"]
            
            print(f"🚀 TELEGRAM: Starting background processing for {chat_id} at {elapsed:.3f}s")
            
            # Get file path and download image in background
            def process_photo():
                try:
                    with app_context.app_context():
                        file_path = get_telegram_file_path(file_id)
                        if file_path:
                            telegram_token = current_app.config.get('TELEGRAM_BOT_TOKEN')
                            file_url = f"https://api.telegram.org/file/bot{telegram_token}/{file_path}"
                            image_base64 = download_telegram_image(file_url)
                            if image_base64:
                                _process_telegram_message_background(
                                    chat_id, "image", (image_base64, PROCESSING_IMAGE_MSG), app_context
                                )
                            else:
                                send_telegram_message(chat_id, IMAGE_ERROR_MSG)
                        else:
                            send_telegram_message(chat_id, IMAGE_ERROR_MSG)
                except Exception as e:
                    print(f"❌ TELEGRAM: Error processing photo: {str(e)}")
                    send_telegram_message(chat_id, IMAGE_ERROR_MSG)
            
            thread = threading.Thread(target=process_photo, daemon=True)
            thread.start()
            
        elif "location" in msg:
            latitude = msg["location"]["latitude"]
            longitude = msg["location"]["longitude"]
            
            print(f"🚀 TELEGRAM: Starting background processing for {chat_id} at {elapsed:.3f}s")
            
            # Start background thread for location processing
            thread = threading.Thread(
                target=_process_telegram_message_background,
                args=(chat_id, "location", (latitude, longitude, PROCESSING_LOCATION_MSG), app_context),
                daemon=True
            )
            thread.start()
            
        # Return success immediately
        elapsed = time.time() - start_time
        print(f"🏁 TELEGRAM: Webhook completed for {chat_id} in {elapsed:.3f}s")
        return "Message received - please give me a few seconds to process your request", 200
        
    except Exception as e:
        print(f"❌ TELEGRAM: Webhook error: {str(e)}")
        return "Error processing your request - please try again", 500 
