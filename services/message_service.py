"""Message service for WhatsApp and Telegram communication"""

import requests
import base64
from flask import current_app
from utils.helpers import truncate_text


def send_whatsapp_message(recipient, message):
    """Send WhatsApp message"""
    try:
        whatsapp_token = current_app.config.get('WHATSAPP_TOKEN')
        phone_number_id = current_app.config.get('PHONE_NUMBER_ID')
        max_length = current_app.config.get('MAX_MESSAGE_LENGTH', 4096)
        
        url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {whatsapp_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {"body": truncate_text(message, max_length)}
        }
        res = requests.post(url, json=payload, headers=headers)
        print(f"WhatsApp message sent. Status: {res.status_code}, Response: {res.text}")
        return res.status_code == 200
    except Exception as e:
        print(f"Error sending WhatsApp message: {e}")
        return False


def send_telegram_message(chat_id, text):
    """Send Telegram message"""
    try:
        telegram_token = current_app.config.get('TELEGRAM_BOT_TOKEN')
        max_length = current_app.config.get('MAX_MESSAGE_LENGTH', 4096)
        
        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        payload = {
            "chat_id": chat_id, 
            "text": truncate_text(text, max_length)
        }
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200 and res.json().get('ok'):
            return True
        return False
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return False


def get_whatsapp_image_url(media_id):
    """Get WhatsApp image URL from media ID"""
    try:
        whatsapp_token = current_app.config.get('WHATSAPP_TOKEN')
        url = f"https://graph.facebook.com/v19.0/{media_id}"
        headers = {"Authorization": f"Bearer {whatsapp_token}"}
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            print(f"Error getting image URL: {res.status_code}, {res.text}")
            return None
        return res.json().get('url')
    except Exception as e:
        print(f"Error in get_whatsapp_image_url: {e}")
        return None


def download_and_encode_whatsapp_image(image_url):
    """Download and base64 encode WhatsApp image"""
    try:
        whatsapp_token = current_app.config.get('WHATSAPP_TOKEN')
        headers = {"Authorization": f"Bearer {whatsapp_token}"}
        res = requests.get(image_url, headers=headers)
        if res.status_code != 200:
            print(f"Error downloading image: {res.status_code}, {res.text}")
            return None
        if len(res.content) == 0:
            print("Downloaded image is empty")
            return None
        return base64.b64encode(res.content).decode('utf-8')
    except Exception as e:
        print(f"Error in download_and_encode_whatsapp_image: {e}")
        return None


def get_telegram_file_path(file_id):
    """Get Telegram file path from file ID"""
    try:
        telegram_token = current_app.config.get('TELEGRAM_BOT_TOKEN')
        url = f"https://api.telegram.org/bot{telegram_token}/getFile"
        payload = {"file_id": file_id}
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code != 200:
            print(f"Error getting Telegram file path: {res.status_code}, {res.text}")
            return None
        result = res.json()
        if result.get('ok'):
            return result.get('result', {}).get('file_path')
        return None
    except Exception as e:
        print(f"Error in get_telegram_file_path: {e}")
        return None


def download_telegram_image(file_url):
    """Download and base64 encode Telegram image"""
    try:
        res = requests.get(file_url, timeout=30)
        if res.status_code != 200:
            print(f"Error downloading Telegram image: {res.status_code}, {res.text}")
            return None
        if len(res.content) == 0:
            print("Downloaded Telegram image is empty")
            return None
        return base64.b64encode(res.content).decode('utf-8')
    except Exception as e:
        print(f"Error in download_telegram_image: {e}")
        return None


def test_telegram_token():
    """Test if Telegram bot token is valid"""
    try:
        telegram_token = current_app.config.get('TELEGRAM_BOT_TOKEN')
        url = f"https://api.telegram.org/bot{telegram_token}/getMe"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                return True
            return False
        return False
    except Exception as e:
        print(f"Error testing Telegram token: {e}")
        return False


def get_telegram_bot_info():
    """Get Telegram bot information including username"""
    try:
        telegram_token = current_app.config.get('TELEGRAM_BOT_TOKEN')
        url = f"https://api.telegram.org/bot{telegram_token}/getMe"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                return data.get('result', {})
            return None
        return None
    except Exception as e:
        print(f"Error getting bot info: {e}")
        return None


def get_telegram_webhook_info():
    """Get current Telegram webhook information"""
    try:
        telegram_token = current_app.config.get('TELEGRAM_BOT_TOKEN')
        url = f"https://api.telegram.org/bot{telegram_token}/getWebhookInfo"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json().get('result', {})
        return None
    except Exception as e:
        print(f"Error getting webhook info: {e}")
        return None


def set_telegram_webhook(webhook_url):
    """Set Telegram webhook URL"""
    try:
        telegram_token = current_app.config.get('TELEGRAM_BOT_TOKEN')
        
        # Delete existing webhook first
        delete_url = f"https://api.telegram.org/bot{telegram_token}/deleteWebhook"
        requests.post(delete_url, timeout=10)
        
        # Set new webhook
        set_url = f"https://api.telegram.org/bot{telegram_token}/setWebhook"
        payload = {
            "url": f"{webhook_url}/webhook/telegram",
            "allowed_updates": ["message", "callback_query"]
        }
        res = requests.post(set_url, json=payload, timeout=10)
        if res.status_code == 200 and res.json().get('ok'):
            return True
        return False
    except Exception as e:
        print(f"Error setting webhook: {e}")
        return False 