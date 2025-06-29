"""
MedSense AI - Medical Chatbot Application
Refactored but maintains exact same functionality and launch behavior as original
"""
from flask import Flask, request, jsonify
import os
from datetime import datetime, timedelta
from config import Config
from models.database import init_database
from services.session_service import get_session_service
from services.message_service import (
    send_whatsapp_message, send_telegram_message, 
    get_whatsapp_image_url, download_and_encode_whatsapp_image,
    get_telegram_file_path, download_telegram_image,
    test_telegram_token, get_telegram_webhook_info, set_telegram_webhook, get_telegram_bot_info
)
from services.message_processor import get_message_processor
from services.followup_service import get_followup_service
from utils.constants import WELCOME_MSG, IMAGE_ERROR_MSG, PROCESSING_TEXT_MSG, PROCESSING_IMAGE_MSG, PROCESSING_LOCATION_MSG

app = Flask(__name__)
app.config.from_object(Config)
init_database()

session_service = get_session_service()
message_processor = get_message_processor()

# Message deduplication for WhatsApp webhooks
processed_messages = {}

# Message deduplication for Telegram webhooks (NEW)
processed_telegram_messages = {}

def clean_old_messages():
    """Clean messages older than 5 minutes"""
    cutoff = datetime.now() - timedelta(minutes=5)
    # Clean WhatsApp messages
    to_remove = [msg_id for msg_id, timestamp in processed_messages.items() if timestamp < cutoff]
    for msg_id in to_remove:
        del processed_messages[msg_id]
    
    # Clean Telegram messages (NEW)
    to_remove_telegram = [msg_id for msg_id, timestamp in processed_telegram_messages.items() if timestamp < cutoff]
    for msg_id in to_remove_telegram:
        del processed_telegram_messages[msg_id]

def is_duplicate_message(message_id):
    """Check if we've already processed this message"""
    clean_old_messages()
    if message_id in processed_messages:
        return True
    processed_messages[message_id] = datetime.now()
    return False

def is_duplicate_telegram_message(message_id):
    """Check if we've already processed this Telegram message"""
    clean_old_messages()
    if message_id in processed_telegram_messages:
        return True
    processed_telegram_messages[message_id] = datetime.now()
    return False

@app.route("/", methods=["GET"])
def health_check():
    session_service.clear_inactive_sessions()
    return "MedSense AI Bot is running!", 200

@app.route("/test-telegram", methods=["GET"])
def test_telegram_endpoint():
    token_works = test_telegram_token()
    webhook_info = get_telegram_webhook_info()
    return jsonify({
        "telegram_token_valid": token_works,
        "webhook_info": webhook_info
    })

@app.route("/bot-info", methods=["GET"])
def get_bot_info():
    """Get Telegram bot information"""
    bot_info = get_telegram_bot_info()
    return jsonify({
        "bot_info": bot_info
    })

@app.route("/test-followup", methods=["GET"])
def test_followup_system():
    """Test follow-up system status"""
    from models.user import get_pending_followups
    from services.followup_service import get_followup_service
    followup_service = get_followup_service()
    pending_followups = get_pending_followups()
    return jsonify({
        "followup_scheduler_running": followup_service.running,
        "pending_followups_count": len(pending_followups),
        "pending_followups": pending_followups[:5],
        "check_interval_seconds": followup_service.check_interval
    })

@app.route("/trigger-followup/<user_id>", methods=["GET"])
def trigger_followup_test(user_id):
    """Manually trigger a follow-up for testing purposes"""
    from services.followup_service import get_followup_service
    try:
        followup_service = get_followup_service()
        followup_service._process_pending_followups()
        return jsonify({
            "status": "follow-up check triggered",
            "user_id": user_id,
            "message": "Check the logs to see if any follow-ups were sent"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        })

@app.route("/webhook", methods=["GET", "POST"])
def whatsapp_webhook():
    session_service.clear_inactive_sessions()
    if request.method == "GET":
        challenge = request.args.get("hub.challenge")
        verify_token = app.config.get('VERIFY_TOKEN')
        if (request.args.get("hub.mode") == "subscribe" and 
            request.args.get("hub.verify_token") == verify_token):
            return challenge if challenge else "", 200
        return "Verification failed", 403
    
    # IMMEDIATE response to prevent webhook timeouts and retries
    response_data = {"status": "received"}
    
    try:
        data = request.get_json()
        entry = data['entry'][0]['changes'][0]['value']
        messages = entry.get('messages', [])
        if not messages:
            return "OK", 200
        msg = messages[0]
        sender = msg['from']
        
        # Check for duplicate messages using WhatsApp message ID
        message_id = msg.get('id')
        if message_id and is_duplicate_message(message_id):
            print(f"⚠️ Skipping duplicate WhatsApp message {message_id} from {sender}")
            return "OK", 200
            
        session_service.update_session_activity(sender)
        
        # Send immediate processing message for non-profile setup interactions
        should_send_processing_msg = not session_service.is_in_profile_setup(sender) and not session_service.should_start_profile_setup(sender)
        
        # Process message in background to prevent webhook timeout
        import threading
        def process_message():
            try:
                if 'text' in msg:
                    body = msg['text']['body']
                    # Send immediate processing message
                    if should_send_processing_msg and not body.lower().startswith(('/start', 'start', 'history', 'clear', 'help')):
                        send_whatsapp_message(sender, PROCESSING_TEXT_MSG)
                    
                    response = message_processor.handle_text_message(sender, body, "whatsapp")
                    if response:
                        send_whatsapp_message(sender, response)
                elif 'image' in msg:
                    media_id = msg['image']['id']
                    image_url = get_whatsapp_image_url(media_id)
                    caption_text = msg['image'].get('caption', None)
                    
                    # Send immediate processing message
                    if should_send_processing_msg:
                        send_whatsapp_message(sender, PROCESSING_IMAGE_MSG)
                    
                    if image_url:
                        image_base64 = download_and_encode_whatsapp_image(image_url)
                        if image_base64:
                            response = message_processor.handle_image_message(sender, image_base64, "whatsapp", caption_text)
                            if response:
                                send_whatsapp_message(sender, response)
                        else:
                            send_whatsapp_message(sender, IMAGE_ERROR_MSG)
                    else:
                        send_whatsapp_message(sender, IMAGE_ERROR_MSG)
                elif 'location' in msg:
                    latitude = msg['location']['latitude']
                    longitude = msg['location']['longitude']
                    
                    # Send immediate processing message
                    if should_send_processing_msg:
                        send_whatsapp_message(sender, PROCESSING_LOCATION_MSG)
                    
                    response = message_processor.handle_location_message(sender, latitude, longitude, "whatsapp")
                    if response:
                        send_whatsapp_message(sender, response)
            except Exception as e:
                print(f"Background WhatsApp processing error: {e}")
                # Send error message to user
                try:
                    send_whatsapp_message(sender, "I encountered a technical issue. Please try again or consult a healthcare professional if urgent.")
                except:
                    pass
        
        # Start background processing
        threading.Thread(target=process_message, daemon=True).start()
        
    except Exception as e:
        print("WhatsApp Error:", e)
    
    # Always return OK immediately to prevent retries
    return "OK", 200

@app.route("/webhook/telegram", methods=["POST"])
def telegram_webhook():
    session_service.clear_inactive_sessions()
    
    # IMMEDIATE response to prevent webhook timeouts and retries
    try:
        data = request.get_json()
        if "message" not in data:
            return "OK", 200
        msg = data["message"]
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if not chat_id:
            return "No chat_id", 400
        
        # Check for duplicate messages using Telegram message ID
        message_id = msg.get('message_id')
        if message_id and is_duplicate_telegram_message(f"{chat_id}_{message_id}"):
            print(f"⚠️ Skipping duplicate Telegram message {message_id} from {chat_id}")
            return "OK", 200
            
        session_service.update_session_activity(chat_id)
        
        # Send immediate processing message for non-profile setup interactions
        should_send_processing_msg = not session_service.is_in_profile_setup(chat_id) and not session_service.should_start_profile_setup(chat_id)
        
        # Process message in background to prevent webhook timeout
        import threading
        def process_message():
            try:
                if "text" in msg:
                    text = msg["text"]
                    if text.startswith("/start"):
                        text = "start"
                    elif text.startswith("/"):
                        text = text[1:]
                    
                    # Send immediate processing message
                    if should_send_processing_msg and not text.lower().startswith(('start', 'history', 'clear', 'help')):
                        send_telegram_message(chat_id, PROCESSING_TEXT_MSG)
                    
                    response = message_processor.handle_text_message(chat_id, text, "telegram")
                    if response:
                        send_telegram_message(chat_id, response)
                elif "photo" in msg:
                    photos = msg["photo"]
                    file_id = photos[-1]["file_id"]
                    file_path = get_telegram_file_path(file_id)
                    caption_text = msg.get('caption', None)
                    
                    # Send immediate processing message
                    if should_send_processing_msg:
                        send_telegram_message(chat_id, PROCESSING_IMAGE_MSG)
                    
                    if file_path:
                        telegram_token = app.config.get('TELEGRAM_BOT_TOKEN')
                        file_url = f"https://api.telegram.org/file/bot{telegram_token}/{file_path}"
                        image_base64 = download_telegram_image(file_url)
                        if image_base64:
                            response = message_processor.handle_image_message(chat_id, image_base64, "telegram", caption_text)
                            if response:
                                send_telegram_message(chat_id, response)
                        else:
                            send_telegram_message(chat_id, IMAGE_ERROR_MSG)
                    else:
                        send_telegram_message(chat_id, IMAGE_ERROR_MSG)
                elif "location" in msg:
                    latitude = msg["location"]["latitude"]
                    longitude = msg["location"]["longitude"]
                    
                    # Send immediate processing message
                    if should_send_processing_msg:
                        send_telegram_message(chat_id, PROCESSING_LOCATION_MSG)
                    
                    response = message_processor.handle_location_message(chat_id, latitude, longitude, "telegram")
                    if response:
                        send_telegram_message(chat_id, response)
            except Exception as e:
                print(f"Background Telegram processing error: {e}")
                # Send error message to user
                try:
                    send_telegram_message(chat_id, "I encountered a technical issue. Please try again or consult a healthcare professional if urgent.")
                except:
                    pass
        
        # Start background processing
        threading.Thread(target=process_message, daemon=True).start()
        
        return "OK", 200
    except Exception as e:
        print(f"Telegram webhook error: {e}")
        return "OK", 200  # Still return OK to prevent retries

@app.route("/set-webhook/<path:webhook_url>", methods=["GET"])
def manual_set_webhook(webhook_url):
    if not webhook_url.startswith(('http://', 'https://')):
        webhook_url = f"https://{webhook_url}"
    success = set_telegram_webhook(webhook_url)
    webhook_info = get_telegram_webhook_info()
    return jsonify({
        "webhook_set": success,
        "webhook_url": f"{webhook_url}/webhook/telegram",
        "current_webhook_info": webhook_info
    })

@app.route("/test-duplicate-prevention", methods=["GET"])
def test_duplicate_prevention():
    """Test endpoint to verify duplicate prevention systems"""
    from services.message_processor import get_message_processor
    from services.message_service import send_whatsapp_message, send_telegram_message
    import time
    
    test_user = "test_user_123"
    test_message = "I have a headache and fever"
    
    results = {
        "webhook_deduplication": {
            "whatsapp": {},
            "telegram": {}
        },
        "message_processor_deduplication": {},
        "message_sending_deduplication": {}
    }
    
    # Test webhook deduplication
    msg_id = "test_msg_001"
    first_check = is_duplicate_message(msg_id)
    second_check = is_duplicate_message(msg_id)
    results["webhook_deduplication"]["whatsapp"] = {
        "first_check": first_check,
        "second_check": second_check,
        "working": not first_check and second_check
    }
    
    telegram_msg_id = f"{test_user}_test_msg_001"
    first_tg_check = is_duplicate_telegram_message(telegram_msg_id)
    second_tg_check = is_duplicate_telegram_message(telegram_msg_id)
    results["webhook_deduplication"]["telegram"] = {
        "first_check": first_tg_check,
        "second_check": second_tg_check,
        "working": not first_tg_check and second_tg_check
    }
    
    # Test message processor deduplication
    processor = get_message_processor()
    first_dup_check = processor._is_duplicate_request(test_user, "text", test_message)
    second_dup_check = processor._is_duplicate_request(test_user, "text", test_message)
    results["message_processor_deduplication"] = {
        "first_check": first_dup_check[0],  # is_duplicate
        "second_check": second_dup_check[0],  # is_duplicate  
        "working": not first_dup_check[0] and second_dup_check[0]
    }
    
    # Test message sending deduplication (would need actual tokens to test fully)
    results["message_sending_deduplication"] = {
        "info": "Message sending deduplication active - prevents identical messages within 2 minutes",
        "hash_system": "Uses MD5 hash of recipient + message content for deduplication"
    }
    
    return jsonify({
        "status": "Duplicate Prevention Test Results",
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "summary": {
            "webhook_protection": results["webhook_deduplication"]["whatsapp"]["working"] and results["webhook_deduplication"]["telegram"]["working"],
            "processor_protection": results["message_processor_deduplication"]["working"],
            "all_systems_working": all([
                results["webhook_deduplication"]["whatsapp"]["working"],
                results["webhook_deduplication"]["telegram"]["working"], 
                results["message_processor_deduplication"]["working"]
            ])
        }
    })

if __name__ == "__main__":
    print("🚀 Starting MedSense AI Bot...")
    followup_service = get_followup_service()
    followup_service.start_scheduler()
    print("✅ 24-hour follow-up scheduler initialized")
    if app.config.get('TELEGRAM_BOT_TOKEN'):
        token_works = test_telegram_token()
        if token_works:
            print("✅ Telegram token is valid")
            webhook_info = get_telegram_webhook_info()
            if webhook_info and webhook_info.get('url'):
                print(f"✅ Telegram webhook configured: {webhook_info.get('url')}")
            else:
                print("⚠️ Telegram webhook not configured")
        else:
            print("❌ Telegram token is invalid or bot is not working")
    else:
        print("❌ TELEGRAM_BOT_TOKEN not found in environment variables")
    if app.config.get('WHATSAPP_TOKEN'):
        print("✅ WhatsApp token configured")
    else:
        print("⚠️ WhatsApp token not configured")
    if app.config.get('GEMINI_API_KEY'):
        print("✅ Gemini API key configured")
    else:
        print("❌ Gemini API key not configured")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
