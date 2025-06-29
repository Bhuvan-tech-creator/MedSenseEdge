"""Utility functions used throughout the application"""

import math
from datetime import datetime, timedelta


def detect_platform(user_id):
    """Detect if user is from Telegram or WhatsApp based on user_id format"""
    user_id_str = str(user_id)
    # Telegram user IDs are typically numeric and can be negative for groups
    # WhatsApp user IDs are phone numbers with country codes
    if user_id_str.startswith("-") or user_id_str.isdigit() or len(user_id_str) > 15:
        return "telegram"
    return "whatsapp"


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula"""
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of earth in kilometers
    r = 6371
    return c * r


def format_history_text(history):
    """Format user history for display"""
    if not history:
        return "📋 Your Recent Medical History:\n\nNo medical history found."
    
    history_text = "📋 Your Recent Medical History:\n\n"
    for i, (symptoms, diagnosis, timestamp, body_part, severity) in enumerate(history[:5], 1):
        date_str = datetime.fromisoformat(timestamp).strftime("%b %d, %Y")
        history_text += f"{i}. {date_str}: {symptoms[:50]}...\n"
    
    return history_text


def format_medical_history_for_analysis(history):
    """Format medical history for use in medical analysis prompts"""
    if not history:
        return "\n\nUSER'S MEDICAL HISTORY: No previous consultations found."
    
    history_text = "\n\nUSER'S MEDICAL HISTORY (Past 12 months):\n"
    for i, (past_symptoms, past_diagnosis, timestamp, body_part, severity) in enumerate(history[:10], 1):
        date_str = datetime.fromisoformat(timestamp).strftime("%b %d, %Y")
        history_text += f"{i}. {date_str}: Symptoms: {past_symptoms} | Diagnosis: {past_diagnosis}\n"
    
    return history_text


def format_profile_for_analysis(profile):
    """Format user profile for medical analysis prompts"""
    if not profile:
        return "\n\nUSER PROFILE: No profile information available"
    
    age_text = f"Age: {profile['age']}" if profile['age'] else "Age: Not provided"
    gender_text = f"Gender: {profile['gender']}" if profile['gender'] else "Gender: Not provided"
    return f"\n\nUSER PROFILE:\n{age_text}\n{gender_text}"


def is_country_mention(text, country_keywords):
    """Check if text contains country name"""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in country_keywords)


def contains_symptom_keywords(text, keywords):
    """Check if text contains any of the specified symptom keywords"""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in keywords)


def is_inactive_session(last_activity, hours_threshold=48):
    """Check if session is inactive based on last activity"""
    if not isinstance(last_activity, datetime):
        return True
    
    threshold = datetime.now() - timedelta(hours=hours_threshold)
    return last_activity < threshold


def truncate_text(text, max_length=4096):
    """Truncate text to specified maximum length"""
    if len(text) <= max_length:
        return text
    return text[:max_length]


def format_clinic_recommendations(clinics, address):
    """Format clinic recommendations for display"""
    if not clinics:
        return (f"📍 Location received: {address}\n\n"
                f"I couldn't find specific medical facilities within 5km, "
                f"but you should visit your nearest clinic or hospital for the symptoms discussed.\n\n"
                f"Feel free to ask about new symptoms or type 'history' to see past consultations.")
    
    clinic_text = f"📍 Based on your location ({address}), here are the nearest medical facilities:\n\n"
    
    for i, clinic in enumerate(clinics, 1):
        # Generate Google Maps link
        maps_link = f"https://www.google.com/maps/search/?api=1&query={clinic['lat']},{clinic['lon']}"
        clinic_text += (f"{i}. **{clinic['name']}** ({clinic['type'].title()})\n"
                       f"   📍 {clinic['distance']}km away\n"
                       f"   🗺️ [Open in Maps]({maps_link})\n\n")
    
    clinic_text += ("Visit the most appropriate facility based on your symptoms' urgency.\n\n"
                   "Feel free to ask about new symptoms or type 'history' to see past consultations.")
    
    return clinic_text 