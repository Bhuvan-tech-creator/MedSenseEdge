"""Utility functions used throughout the application"""
import math
from datetime import datetime, timedelta
def detect_platform(user_id):
    """Detect if user is from Telegram or WhatsApp based on user_id format"""
    user_id_str = str(user_id)
    if user_id_str.startswith("-") or user_id_str.isdigit() or len(user_id_str) > 15:
        return "telegram"
    return "whatsapp"
def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula"""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
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
        # Direct navigation/directions link only
        directions_link = f"https://www.google.com/maps/dir/?api=1&destination={clinic['lat']},{clinic['lon']}&destination_place_id={clinic['name'].replace(' ', '+').replace('&', 'and')}"
        
        clinic_text += (f"{i}. **{clinic['name']}** ({clinic['type'].title()})\n"
                       f"   📍 {clinic['distance']}km away\n"
                       f"   🗺️ [Get Directions]({directions_link})\n\n")
    
    clinic_text += ("💡 **Tips:**\n"
                   "• Tap 'Get Directions' for turn-by-turn navigation\n"
                   "• Call ahead to confirm hours and availability\n\n"
                   "Visit the most appropriate facility based on your symptoms' urgency.\n\n"
                   "Feel free to ask about new symptoms or type 'history' to see past consultations.")
    
    return clinic_text


def format_clinic_data_with_maps(clinic_data):
    """Format clinic data from JSON with Google Maps links for medical agent responses"""
    try:
        if isinstance(clinic_data, str):
            import json
            clinic_data = json.loads(clinic_data)
        
        facilities = clinic_data.get('facilities', [])
        location = clinic_data.get('location', 'your location')
        
        if not facilities:
            return f"📍 No medical facilities found within the search radius near {location}. I recommend visiting your nearest clinic or hospital for medical care."
        
        response = f"📍 **Medical Facilities Near You** ({location}):\n\n"
        
        for i, facility in enumerate(facilities, 1):
            # Direct navigation/directions link only
            directions_link = f"https://www.google.com/maps/dir/?api=1&destination={facility['lat']},{facility['lon']}"
            
            response += (f"{i}. **{facility['name']}** ({facility['type'].title()})\n"
                        f"   📍 {facility['distance']}km away\n"
                        f"   🗺️ [Get Directions]({directions_link})\n\n")
        
        response += ("💡 **Navigation Tips:**\n"
                    "• Tap 'Get Directions' for turn-by-turn navigation\n"
                    "• Consider calling ahead to confirm hours and availability\n\n")
        
        return response
        
    except Exception as e:
        return f"📍 I found medical facilities near you, but couldn't format the information properly. Please try sharing your location again." 
