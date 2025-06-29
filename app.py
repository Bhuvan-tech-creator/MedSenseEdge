"""
MedSense AI - Medical Chatbot Application
Refactored but maintains exact same functionality and launch behavior as original
"""

from flask import Flask, request, jsonify
import os
from datetime import datetime

# Import configuration
from config import Config

# Import database initialization
from models.database import init_database

# Import services
from services.session_service import get_session_service
from services.message_service import (
    send_whatsapp_message, send_telegram_message, 
    get_whatsapp_image_url, download_and_encode_whatsapp_image,
    get_telegram_file_path, download_telegram_image,
    test_telegram_token, get_telegram_webhook_info, set_telegram_webhook
)
from services.message_processor import get_message_processor

# Import constants
from utils.constants import WELCOME_MSG, IMAGE_ERROR_MSG

# Create Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize database on startup
init_database()

# Get service instances
session_service = get_session_service()
message_processor = get_message_processor()


# Root route for health check
@app.route("/", methods=["GET"])
def health_check():
    session_service.clear_inactive_sessions()
    return "MedSense AI Bot is running!", 200


# Test route for Telegram
@app.route("/test-telegram", methods=["GET"])
def test_telegram_endpoint():
    token_works = test_telegram_token()
    webhook_info = get_telegram_webhook_info()
    return jsonify({
        "telegram_token_valid": token_works,
        "webhook_info": webhook_info
    })


# WhatsApp Webhook
@app.route("/webhook", methods=["GET", "POST"])
def whatsapp_webhook():
    # Clear inactive sessions
    session_service.clear_inactive_sessions()
    
    if request.method == "GET":
        # Webhook verification
        challenge = request.args.get("hub.challenge")
        verify_token = app.config.get('VERIFY_TOKEN')
        
        if (request.args.get("hub.mode") == "subscribe" and 
            request.args.get("hub.verify_token") == verify_token):
            return challenge if challenge else "", 200
        return "Verification failed", 403

    # Handle incoming messages
    try:
        data = request.get_json()
        entry = data['entry'][0]['changes'][0]['value']
        messages = entry.get('messages', [])
        
        if not messages:
            return "OK", 200
        
        msg = messages[0]
        sender = msg['from']

        # Update session activity
        session_service.update_session_activity(sender)

        if 'text' in msg:
            # Handle text message
            body = msg['text']['body']
            response = message_processor.handle_text_message(sender, body, "whatsapp")
            
            if response:
                send_whatsapp_message(sender, response)

        elif 'image' in msg:
            # Handle image message (with optional caption text)
            media_id = msg['image']['id']
            image_url = get_whatsapp_image_url(media_id)
            
            # Extract caption text if present
            caption_text = msg['image'].get('caption', None)
            
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
            # Handle location message
            latitude = msg['location']['latitude']
            longitude = msg['location']['longitude']
            
            response = message_processor.handle_location_message(sender, latitude, longitude, "whatsapp")
            if response:
                send_whatsapp_message(sender, response)

    except Exception as e:
        print("WhatsApp Error:", e)
    
    return "OK", 200


# Telegram Webhook
@app.route("/webhook/telegram", methods=["POST"])
def telegram_webhook():
    # Clear inactive sessions
    session_service.clear_inactive_sessions()
    
    try:
        data = request.get_json()
        
        if "message" not in data:
            return "OK", 200
        
        msg = data["message"]
        chat_id = str(msg.get("chat", {}).get("id", ""))
        
        if not chat_id:
            return "No chat_id", 400

        # Update session activity
        session_service.update_session_activity(chat_id)

        if "text" in msg:
            # Handle text message
            text = msg["text"]
            
            # Handle /start command specially
            if text.startswith("/start"):
                if session_service.should_start_profile_setup(chat_id):
                    session_service.start_profile_setup(chat_id, "telegram")
                else:
                    send_telegram_message(chat_id, WELCOME_MSG)
                return "OK", 200
            
            # Convert other Telegram commands to regular text
            if text.startswith("/"):
                text = text[1:]  # Remove the slash
            
            response = message_processor.handle_text_message(chat_id, text, "telegram")
            if response:
                send_telegram_message(chat_id, response)

        elif "photo" in msg:
            # Handle photo message (with optional caption text)
            photos = msg["photo"]
            file_id = photos[-1]["file_id"]  # Get the largest photo
            file_path = get_telegram_file_path(file_id)
            
            # Extract caption text if present
            caption_text = msg.get('caption', None)
            
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
            # Handle location message
            latitude = msg["location"]["latitude"]
            longitude = msg["location"]["longitude"]
            
            response = message_processor.handle_location_message(chat_id, latitude, longitude, "telegram")
            if response:
                send_telegram_message(chat_id, response)

        return "OK", 200
    
    except Exception as e:
        print(f"Telegram webhook error: {e}")
        return "Error", 500


# Webhook setup
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


if __name__ == "__main__":
    print("🚀 Starting MedSense AI Bot...")
    
    # Test integrations on startup
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
    
    # Test other configurations
    if app.config.get('WHATSAPP_TOKEN'):
        print("✅ WhatsApp token configured")
    else:
        print("⚠️ WhatsApp token not configured")
    
    if app.config.get('GEMINI_API_KEY'):
        print("✅ Gemini API key configured")
    else:
        print("❌ Gemini API key not configured")
    
    # Production configuration for Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)