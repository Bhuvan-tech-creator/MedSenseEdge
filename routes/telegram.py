"""Telegram webhook routes"""
from flask import Blueprint, request, current_app
from services.message_service import (
    send_telegram_message, get_telegram_file_path, download_telegram_image
)
from services.message_processor import get_message_processor
from services.session_service import get_session_service
from utils.constants import WELCOME_MSG, IMAGE_ERROR_MSG
telegram_bp = Blueprint('telegram', __name__)
@telegram_bp.route("/webhook/telegram", methods=["POST"])
def telegram_webhook():
    """Telegram webhook endpoint"""
    session_service = get_session_service()
    message_processor = get_message_processor()
    session_service.clear_inactive_sessions()
    try:
        data = request.get_json()
        if "message" not in data:
            return "OK", 200
        msg = data["message"]
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if not chat_id:
            return "No chat_id", 400
        session_service.update_session_activity(chat_id)
        if "text" in msg:
            text = msg["text"]
            if text.startswith("/start"):
                if session_service.should_start_profile_setup(chat_id):
                    session_service.start_profile_setup(chat_id, "telegram")
                else:
                    send_telegram_message(chat_id, WELCOME_MSG)
                return "OK", 200
            if text.startswith("/"):
                text = text[1:]
            response = message_processor.handle_text_message(chat_id, text, "telegram")
            if response:
                send_telegram_message(chat_id, response)
        elif "photo" in msg:
            photos = msg["photo"]
            file_id = photos[-1]["file_id"]
            file_path = get_telegram_file_path(file_id)
            if file_path:
                telegram_token = current_app.config.get('TELEGRAM_BOT_TOKEN')
                file_url = f"https://api.telegram.org/file/bot{telegram_token}/{file_path}"
                image_base64 = download_telegram_image(file_url)
                if image_base64:
                    response = message_processor.handle_image_message(chat_id, image_base64, "telegram")
                    if response:
                        send_telegram_message(chat_id, response)
                else:
                    send_telegram_message(chat_id, IMAGE_ERROR_MSG)
            else:
                send_telegram_message(chat_id, IMAGE_ERROR_MSG)
        elif "location" in msg:
            latitude = msg["location"]["latitude"]
            longitude = msg["location"]["longitude"]
            response = message_processor.handle_location_message(chat_id, latitude, longitude, "telegram")
            if response:
                send_telegram_message(chat_id, response)
        return "OK", 200
    except Exception as e:
        print(f"Telegram webhook error: {e}")
        return "Error", 500 
