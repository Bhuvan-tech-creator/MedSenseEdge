"""WhatsApp webhook routes"""
from flask import Blueprint, request
from services.message_service import (
    send_whatsapp_message, get_whatsapp_image_url, download_and_encode_whatsapp_image
)
from services.message_processor import get_message_processor
from services.session_service import get_session_service
from utils.constants import IMAGE_ERROR_MSG
whatsapp_bp = Blueprint('whatsapp', __name__)
@whatsapp_bp.route("/webhook", methods=["GET", "POST"])
def whatsapp_webhook():
    """WhatsApp webhook endpoint"""
    session_service = get_session_service()
    message_processor = get_message_processor()
    session_service.clear_inactive_sessions()
    if request.method == "GET":
        challenge = request.args.get("hub.challenge")
        verify_token = request.app.config.get('VERIFY_TOKEN')
        if (request.args.get("hub.mode") == "subscribe" and 
            request.args.get("hub.verify_token") == verify_token):
            return challenge if challenge else "", 200
        return "Verification failed", 403
    try:
        data = request.get_json()
        entry = data['entry'][0]['changes'][0]['value']
        messages = entry.get('messages', [])
        if not messages:
            return "OK", 200
        msg = messages[0]
        sender = msg['from']
        session_service.update_session_activity(sender)
        if 'text' in msg:
            body = msg['text']['body']
            response = message_processor.handle_text_message(sender, body, "whatsapp")
            if response:
                send_whatsapp_message(sender, response)
        elif 'image' in msg:
            media_id = msg['image']['id']
            image_url = get_whatsapp_image_url(media_id)
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
            latitude = msg['location']['latitude']
            longitude = msg['location']['longitude']
            response = message_processor.handle_location_message(sender, latitude, longitude, "whatsapp")
            if response:
                send_whatsapp_message(sender, response)
    except Exception as e:
        print("WhatsApp Error:", e)
    return "OK", 200 
