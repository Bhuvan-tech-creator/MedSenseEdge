import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration"""
    
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    
    # WhatsApp API
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
    PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
    VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
    
    # Telegram API
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    # Google Gemini API
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    # Location services
    NOMINATIM_USER_AGENT = os.getenv("NOMINATIM_USER_AGENT", "MedSenseAI/1.0")
    OVERPASS_API_URL = os.getenv("OVERPASS_API_URL", "https://overpass-api.de/api/interpreter")
    NOMINATIM_API_URL = os.getenv("NOMINATIM_API_URL", "https://nominatim.openstreetmap.org")
    
    # External APIs
    RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')  # Secure EndlessMedical API via RapidAPI
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    
    # Database
    DATABASE_PATH = 'medsense_history.db'
    
    # Session settings
    SESSION_CLEANUP_HOURS = 48  # 2 months = 48 * 30 hours
    SESSION_TIMEOUT = 1800  # 30 minutes
    
    # Message limits