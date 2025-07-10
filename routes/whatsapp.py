"""WhatsApp webhook routes"""
import threading
import time
from datetime import datetime, timedelta
from flask import Blueprint, request, current_app
from services.message_service import (
    send_whatsapp_message, get_whatsapp_image_url, download_and_encode_whatsapp_image
)
from services.message_processor import get_message_processor
from services.session_service import get_session_service
from utils.constants import (
    IMAGE_ERROR_MSG, PROCESSING_TEXT_MSG, 
    PROCESSING_IMAGE_MSG, PROCESSING_LOCATION_MSG
)

whatsapp_bp = Blueprint('whatsapp', __name__)

# Message deduplication for WhatsApp webhooks
processed_messages = {}

def clean_old_messages():
    """Clean messages older than 5 minutes"""
    cutoff = datetime.now() - timedelta(minutes=5)
    to_remove = [msg_id for msg_id, timestamp in processed_messages.items() if timestamp < cutoff]
    for msg_id in to_remove:
        del processed_messages[msg_id]

def is_duplicate_message(message_id):
    """Check if we've already processed this message"""
    clean_old_messages()
    if message_id in processed_messages:
        return True
    processed_messages[message_id] = datetime.now()
    return False

def _process_whatsapp_message_background(sender, message_type, content, app_context):
    """Process WhatsApp message in background thread"""
    try:
        # Push Flask app context for background thread
        with app_context.app_context():
            print(f"🔄 WHATSAPP BG: Background processing started for {sender}")
            
            message_processor = get_message_processor()
            response = None
            
            if message_type == "text":
                body, immediate_msg = content
                print(f"📝 WHATSAPP BG: Processing text message: '{body[:50]}...'")
                
                # Send immediate processing message
                print(f"⚡ WHATSAPP BG: Sending immediate processing message to {sender}")
                send_whatsapp_message(sender, immediate_msg)
                
                # Process the message
                response = message_processor.handle_text_message(sender, body, "whatsapp")
                
            elif message_type == "image":
                media_id, caption_text, immediate_msg = content
                print(f"🖼️ WHATSAPP BG: Processing image message for {sender}")
                
                # Send immediate processing message
                print(f"⚡ WHATSAPP BG: Sending immediate processing message to {sender}")
                send_whatsapp_message(sender, immediate_msg)
                
                # Download and process the image
                image_url = get_whatsapp_image_url(media_id)
                if image_url:
                    image_base64 = download_and_encode_whatsapp_image(image_url)
                    if image_base64:
                        response = message_processor.handle_image_message(sender, image_base64, "whatsapp", caption_text)
                    else:
                        response = IMAGE_ERROR_MSG
                else:
                    response = IMAGE_ERROR_MSG
                
            elif message_type == "location":
                latitude, longitude, immediate_msg = content
                print(f"📍 WHATSAPP BG: Processing location message for {sender}")
                
                # Send immediate processing message
                print(f"⚡ WHATSAPP BG: Sending immediate processing message to {sender}")
                send_whatsapp_message(sender, immediate_msg)
                
                # Process the location
                response = message_processor.handle_location_message(sender, latitude, longitude, "whatsapp")
            
            # Send final response if available
            if response:
                print(f"✅ WHATSAPP BG: Sending final response to {sender}")
                send_whatsapp_message(sender, response)
                print(f"🎉 WHATSAPP BG: Background processing completed for {sender}")
            else:
                print(f"⚠️ WHATSAPP BG: No response generated for {sender}")
                
    except Exception as e:
        print(f"❌ WHATSAPP BG: Error in background processing for {sender}: {str(e)}")
        try:
            # Send error message to user
            error_msg = "I apologize, but I encountered a technical issue. Please try again or consult a healthcare professional if urgent."
            send_whatsapp_message(sender, error_msg)
        except:
            print(f"❌ WHATSAPP BG: Failed to send error message to {sender}")

@whatsapp_bp.route("/webhook", methods=["GET", "POST"])
def whatsapp_webhook():
    """WhatsApp webhook endpoint with background processing"""
    session_service = get_session_service()
    
    # Clean up inactive sessions
    session_service.clear_inactive_sessions()
    
    if request.method == "GET":
        challenge = request.args.get("hub.challenge")
        verify_token = current_app.config.get('VERIFY_TOKEN')
        if (request.args.get("hub.mode") == "subscribe" and 
            request.args.get("hub.verify_token") == verify_token):
            return challenge if challenge else "Webhook verification successful", 200
        return "Webhook verification failed - invalid token", 403
    
    try:
        data = request.get_json()
        entry = data['entry'][0]['changes'][0]['value']
        messages = entry.get('messages', [])
        
        if not messages:
            return "No messages to process", 200
            
        msg = messages[0]
        sender = msg['from']
        
        # Track timing
        start_time = time.time()
        timestamp = datetime.now().strftime("%H:%M:%S.%f")
        
        print(f"📨 WHATSAPP: Received message from {sender} at {timestamp}")
        
        # Check for duplicate messages using WhatsApp message ID
        message_id = msg.get('id')
        if message_id and is_duplicate_message(message_id):
            print(f"⚠️ WHATSAPP: Skipping duplicate message {message_id} from {sender}")
            return "Duplicate message detected - already processed", 200
            
        # Update session activity
        session_service.update_session_activity(sender)
        elapsed = time.time() - start_time
        print(f"🔄 WHATSAPP: Session updated for {sender} at {elapsed:.3f}s")
        
        # Check if user is in profile setup (handle immediately)
        if session_service.is_in_profile_setup(sender):
            message_processor = get_message_processor()
            if 'text' in msg:
                body = msg['text']['body']
                response = message_processor.handle_text_message(sender, body, "whatsapp")
                if response:
                    send_whatsapp_message(sender, response)
            elapsed = time.time() - start_time
            print(f"🏁 WHATSAPP: Webhook completed for {sender} in {elapsed:.3f}s")
            return "Profile setup message processed successfully", 200
            
        # Check if user should start profile setup
        if session_service.should_start_profile_setup(sender):
            print(f"✅ WHATSAPP: User {sender} not in profile setup, allowing processing message")
        else:
            print(f"✅ WHATSAPP: User {sender} not in profile setup, allowing processing message")
        
        # Get app context for background processing
        app_context = current_app._get_current_object()
        
        # Start background processing for different message types
        if 'text' in msg:
            body = msg['text']['body']
            
            print(f"🚀 WHATSAPP: Starting background processing for {sender} at {elapsed:.3f}s")
            
            # Start background thread for text processing
            thread = threading.Thread(
                target=_process_whatsapp_message_background,
                args=(sender, "text", (body, PROCESSING_TEXT_MSG), app_context),
                daemon=True
            )
            thread.start()
            
        elif 'image' in msg:
            media_id = msg['image']['id']
            caption_text = msg['image'].get('caption', None)
            
            print(f"🚀 WHATSAPP: Starting background processing for {sender} at {elapsed:.3f}s")
            
            # Start background thread for image processing
            thread = threading.Thread(
                target=_process_whatsapp_message_background,
                args=(sender, "image", (media_id, caption_text, PROCESSING_IMAGE_MSG), app_context),
                daemon=True
            )
            thread.start()
            
        elif 'location' in msg:
            latitude = msg['location']['latitude']
            longitude = msg['location']['longitude']
            
            print(f"🚀 WHATSAPP: Starting background processing for {sender} at {elapsed:.3f}s")
            
            # Start background thread for location processing
            thread = threading.Thread(
                target=_process_whatsapp_message_background,
                args=(sender, "location", (latitude, longitude, PROCESSING_LOCATION_MSG), app_context),
                daemon=True
            )
            thread.start()
            
        # Return success immediately
        elapsed = time.time() - start_time
        print(f"🏁 WHATSAPP: Webhook completed for {sender} in {elapsed:.3f}s")
        return "Message received - please give me a few seconds to process your request", 200
        
    except Exception as e:
        print(f"❌ WHATSAPP: Webhook error: {str(e)}")
        return "Error processing your request - please try again", 200  # Return 200 to prevent retries 
