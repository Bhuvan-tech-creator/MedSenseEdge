"""Main application entry point"""
import os
from app import create_app
from app.services.message_service import test_telegram_token, get_telegram_webhook_info
def main():
    """Main application startup"""
    print("🚀 Starting MedSense AI Bot...")
    app = create_app()
    with app.app_context():
        telegram_token = app.config.get('TELEGRAM_BOT_TOKEN')
        if telegram_token:
            token_works = test_telegram_token()
            if token_works:
                print("✅ Telegram token is valid")
                webhook_info = get_telegram_webhook_info()
                if webhook_info.get('url'):
                    print(f"✅ Telegram webhook configured: {webhook_info.get('url')}")
                else:
                    print("⚠️ Telegram webhook not configured")
            else:
                print("❌ Telegram token is invalid or bot is not working")
        else:
            print("❌ TELEGRAM_BOT_TOKEN not found in environment variables")
        whatsapp_token = app.config.get('WHATSAPP_TOKEN')
        gemini_key = app.config.get('GEMINI_API_KEY')
        if whatsapp_token:
            print("✅ WhatsApp token configured")
        else:
            print("⚠️ WhatsApp token not configured")
        if gemini_key:
            print("✅ Gemini API key configured")
        else:
            print("❌ Gemini API key not configured")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
if __name__ == "__main__":
    main() 
