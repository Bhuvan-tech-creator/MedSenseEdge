"""Health check and test routes"""

from flask import Blueprint, jsonify
from services.session_service import get_session_service
from services.message_service import test_telegram_token, get_telegram_webhook_info, set_telegram_webhook, get_telegram_bot_info

health_bp = Blueprint('health', __name__)


@health_bp.route("/", methods=["GET"])
def health_check():
    """Main health check endpoint"""
    # Clear inactive sessions on health check
    session_service = get_session_service()
    session_service.clear_inactive_sessions()
    return "MedSense AI Bot is running!", 200


@health_bp.route("/test-telegram", methods=["GET"])
def test_telegram_endpoint():
    """Test Telegram bot configuration"""
    token_works = test_telegram_token()
    webhook_info = get_telegram_webhook_info()
    return jsonify({
        "telegram_token_valid": token_works,
        "webhook_info": webhook_info
    })


@health_bp.route("/bot-info", methods=["GET"])
def get_bot_info():
    """Get Telegram bot information"""
    bot_info = get_telegram_bot_info()
    return jsonify({
        "bot_info": bot_info
    })


@health_bp.route("/set-webhook/<path:webhook_url>", methods=["GET"])
def manual_set_webhook(webhook_url):
    """Manually set Telegram webhook"""
    if not webhook_url.startswith(('http://', 'https://')):
        webhook_url = f"https://{webhook_url}"
    
    success = set_telegram_webhook(webhook_url)
    webhook_info = get_telegram_webhook_info()
    
    return jsonify({
        "webhook_set": success,
        "webhook_url": f"{webhook_url}/webhook/telegram",
        "current_webhook_info": webhook_info
    }) 