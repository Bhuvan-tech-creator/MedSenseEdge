import os
from dotenv import load_dotenv
load_dotenv()
class Config:
    """Application configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
    PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
    VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    NOMINATIM_USER_AGENT = os.getenv("NOMINATIM_USER_AGENT", "MedSenseAI/1.0")
    OVERPASS_API_URL = os.getenv("OVERPASS_API_URL", "https://overpass-api.de/api/interpreter")
    NOMINATIM_API_URL = os.getenv("NOMINATIM_API_URL", "https://nominatim.openstreetmap.org")
    RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    DATABASE_PATH = 'medsense_history.db'
    SESSION_CLEANUP_HOURS = 48
    SESSION_TIMEOUT = 1800
