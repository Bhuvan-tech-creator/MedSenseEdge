from flask import Flask, request, jsonify
import os
import requests
import base64
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Import all medical analysis functions from our medical services module
from medical_services import (
    init_database, save_user_profile, get_user_profile, is_new_user,
    get_user_recent_location, save_diagnosis_to_history, save_feedback, 
    get_user_history, get_history_id, save_user_location, reverse_geocode, 
    find_nearby_clinics, save_user_country, get_user_country, 
    check_disease_outbreaks_for_user, generate_language_aware_response,
    gemini_combined_diagnose_with_history, gemini_text_diagnose_with_profile,
    gemini_image_diagnose_with_profile, llm
)

load_dotenv()

# Environment Variables
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Flask App
app = Flask(__name__)

WELCOME_MSG = (
    "\U0001F44B Welcome to MedSense AI.\n"
    "Type your symptoms (e.g., 'I have fever and chills') or send an image from your camera or gallery.\n"
    "You can provide text, image, or both for the best analysis!\n"
    "📋 Type 'history' to see your past consultations\n"
    "📋 Type 'clear' to clear session data and start a new session\n"
    "\u26A0\ufe0f I'm an AI assistant, not a doctor. For emergencies, text EMERGENCY and visit a clinic."
)

# Store user sessions with last activity timestamp and profile setup state
user_sessions = {}



def clear_inactive_sessions():
    """Clear sessions for users inactive for more than 2 months"""
    two_months_ago = datetime.now() - timedelta(days=60)
    inactive_users = [user_id for user_id, session in user_sessions.items() 
                    if session.get('last_activity', datetime.now()) < two_months_ago]
    for user_id in inactive_users:
        user_sessions[user_id] = {"text": None, "image": None, "location": None, "last_activity": datetime.now(), "profile_step": None, "awaiting_location_for_clinics": False}
        print(f"Cleared session for inactive user {user_id}")

# Initialize database on startup
init_database()

def test_telegram_token():
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
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

def get_telegram_webhook_info():
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json().get('result', {})
        return None
    except Exception as e:
        print(f"Error getting webhook info: {e}")
        return None

# Root route for health check
@app.route("/", methods=["GET"])
def health_check():
    clear_inactive_sessions()
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
    clear_inactive_sessions()
    if request.method == "GET":
        challenge = request.args.get("hub.challenge")
        if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return challenge if challenge else "", 200
        return "Verification failed", 403

    data = request.get_json()
    try:
        entry = data['entry'][0]['changes'][0]['value']
        messages = entry.get('messages', [])
        if messages:
            msg = messages[0]
            sender = msg['from']

            # Initialize session if needed
            if sender not in user_sessions:
                user_sessions[sender] = {"text": None, "image": None, "location": None, "last_activity": datetime.now(), "profile_step": None, "awaiting_location_for_clinics": False}
            user_sessions[sender]["last_activity"] = datetime.now()

            if 'text' in msg:
                body = msg['text']['body']
                
                # Check if user is setting up profile
                if user_sessions[sender].get("profile_step"):
                    handle_profile_setup(sender, body, "whatsapp")
                    return "OK", 200
                
                # Check if new user needs profile setup
                if is_new_user(sender) and body.lower() not in ["skip", "help", "emergency"]:
                    start_profile_setup(sender, "whatsapp")
                    return "OK", 200
                
                if body.lower() == "help":
                    send_whatsapp_message(sender, "Type your symptoms or send an image. You can provide text, image, or both. Say 'proceed' when ready for analysis!")
                elif body.lower() == "emergency":
                    send_whatsapp_message(sender, "\ud83d\udea8 This may be urgent. Please visit a clinic immediately.")
                elif body.lower() == "history":
                    history = get_user_history(sender)
                    if history:
                        history_text = "📋 Your Recent Medical History:\n\n"
                        for i, (symptoms, diagnosis, timestamp, body_part, severity) in enumerate(history[:5], 1):
                            date_str = datetime.fromisoformat(timestamp).strftime("%b %d, %Y")
                            history_text += f"{i}. {date_str}: {symptoms[:50]}...\n"
                        send_whatsapp_message(sender, history_text)
                    else:
                        send_whatsapp_message(sender, "No medical history found.")
                elif body.lower() == "clear":
                    user_sessions[sender] = {"text": None, "image": None, "location": None, "last_activity": datetime.now(), "profile_step": None, "awaiting_location_for_clinics": False}
                    send_whatsapp_message(sender, "Session cleared. You can start fresh with new symptoms and images.")
                elif body.lower() == "proceed":
                    reply = process_user_input(sender, user_sessions[sender])
                    send_whatsapp_message(sender, reply)
                elif body.lower() in ["good", "bad"]:
                    # Handle feedback
                    history = get_user_history(sender, days_back=1)
                    if history:
                        history_id = get_history_id(sender, history[0][2])
                        if history_id:
                            save_feedback(sender, history_id, body.lower())
                            send_whatsapp_message(sender, f"Thank you for your {body} feedback! 🙏\n\nFeel free to ask about new symptoms or type 'history' to see past consultations.")
                        else:
                            send_whatsapp_message(sender, "No recent diagnosis found to provide feedback for.")
                    else:
                        send_whatsapp_message(sender, "No recent diagnosis found to provide feedback for.")
                else:
                    # Check if this might be a country name (if no country is saved yet)
                    if not get_user_country(sender) and any(keyword in body.lower() for keyword in ['united states', 'usa', 'america', 'india', 'brazil', 'china', 'mexico', 'canada', 'australia', 'uk', 'england', 'france', 'germany', 'spain', 'italy', 'japan', 'korea', 'nigeria', 'south africa', 'egypt', 'pakistan', 'bangladesh', 'indonesia', 'philippines', 'vietnam', 'thailand', 'malaysia', 'singapore', 'turkey', 'iran', 'israel', 'saudi arabia', 'uae', 'qatar', 'kuwait', 'russia', 'ukraine', 'poland', 'netherlands', 'belgium', 'switzerland', 'sweden', 'norway', 'denmark', 'finland', 'argentina', 'chile', 'peru', 'colombia', 'venezuela']):
                        # This looks like a country name, save it
                        save_user_country(sender, body.title(), "whatsapp")
                        
                        # Check for disease outbreaks
                        outbreaks = check_disease_outbreaks_for_user(sender)
                        if outbreaks:
                            outbreak_msg = f"🌍 Thank you! I've saved {body.title()} as your country.\n\n⚠️ Disease Alert: There are {len(outbreaks)} disease outbreak(s) currently reported in {body.title()}. Stay informed and follow local health guidelines.\n\nFeel free to ask about symptoms or type 'history' to see past consultations."
                        else:
                            outbreak_msg = f"🌍 Thank you! I've saved {body.title()} as your country. I'll notify you of any disease outbreaks in your area.\n\nFeel free to ask about symptoms or type 'history' to see past consultations."
                        
                        send_whatsapp_message(sender, outbreak_msg)
                else:
                    user_sessions[sender]["text"] = body
                        reply = handle_partial_input(sender, user_sessions[sender])
                    send_whatsapp_message(sender, reply)

            elif 'image' in msg:
                # Check if new user needs profile setup
                if is_new_user(sender):
                    start_profile_setup(sender, "whatsapp")
                    return "OK", 200
                    
                media_id = msg['image']['id']
                image_url = get_image_url(media_id)
                if image_url:
                    image_base64 = download_and_encode_image(image_url)
                    if image_base64:
                        user_sessions[sender]["image"] = image_base64
                        reply = handle_partial_input(sender, user_sessions[sender])
                        send_whatsapp_message(sender, reply)
                    else:
                        send_whatsapp_message(sender, "Sorry, I couldn't download the image. Please try sending it again.")
                else:
                    send_whatsapp_message(sender, "Sorry, I couldn't access the image. Please try sending it again.")

            elif 'location' in msg:
                # Handle location sharing
                latitude = msg['location']['latitude']
                longitude = msg['location']['longitude']
                
                # Get address from coordinates
                address = reverse_geocode(latitude, longitude)
                
                # Check if we're waiting for location after diagnosis
                if user_sessions[sender].get("awaiting_location_for_clinics"):
                    # Provide clinic recommendations only
                    clinics = find_nearby_clinics(latitude, longitude)
                    save_user_location(sender, latitude, longitude, address, "whatsapp")
                    
                    if clinics:
                        clinic_text = f"📍 Based on your location ({address}), here are the nearest medical facilities:\n\n"
                        for i, clinic in enumerate(clinics, 1):
                            # Generate Google Maps link
                            maps_link = f"https://www.google.com/maps/search/?api=1&query={clinic['lat']},{clinic['lon']}"
                            clinic_text += f"{i}. **{clinic['name']}** ({clinic['type'].title()})\n   📍 {clinic['distance']}km away\n   🗺️ [Open in Maps]({maps_link})\n\n"
                        clinic_text += "Visit the most appropriate facility based on your symptoms' urgency.\n\n"
                        clinic_text += "Feel free to ask about new symptoms or type 'history' to see past consultations."
                    else:
                        clinic_text = f"📍 Location received: {address}\n\nI couldn't find specific medical facilities within 5km, but you should visit your nearest clinic or hospital for the symptoms discussed.\n\nFeel free to ask about new symptoms or type 'history' to see past consultations."
                    
                    user_sessions[sender]["awaiting_location_for_clinics"] = False
                    send_whatsapp_message(sender, clinic_text)
                else:
                    # Regular location sharing during symptom input
                    location_data = {"lat": latitude, "lon": longitude, "address": address}
                    user_sessions[sender]["location"] = location_data
                    save_user_location(sender, latitude, longitude, address, "whatsapp")
                    send_whatsapp_message(sender, f"📍 Location received: {address}\n\nNow you can share your symptoms or send an image for analysis!")

    except Exception as e:
        print("WhatsApp Error:", e)
    return "OK", 200

# Telegram Webhook
@app.route("/webhook/telegram", methods=["POST"])
def telegram_webhook():
    clear_inactive_sessions()
    try:
        data = request.get_json()
        if "message" in data:
            msg = data["message"]
            chat_id = str(msg.get("chat", {}).get("id", ""))
            
            if not chat_id:
                return "No chat_id", 400

            # Initialize session if needed
            if chat_id not in user_sessions:
                user_sessions[chat_id] = {"text": None, "image": None, "location": None, "last_activity": datetime.now(), "profile_step": None, "awaiting_location_for_clinics": False}
            user_sessions[chat_id]["last_activity"] = datetime.now()

            if "text" in msg:
                text = msg["text"]
                
                # Check if user is setting up profile
                if user_sessions[chat_id].get("profile_step"):
                    handle_profile_setup(chat_id, text, "telegram")
                    return "OK", 200
                
                if text.startswith("/start"):
                    if is_new_user(chat_id):
                        start_profile_setup(chat_id, "telegram")
                    else:
                    send_telegram_message(chat_id, WELCOME_MSG)
                elif text.lower() in ["help", "/help"]:
                    send_telegram_message(chat_id, "Type your symptoms or send an image. You can provide text, image, or both. Say 'proceed' when ready for analysis!")
                elif text.lower() in ["emergency", "/emergency"]:
                    send_telegram_message(chat_id, "🚨 This may be urgent. Please visit a clinic immediately.")
                elif text.lower() in ["history", "/history"]:
                    history = get_user_history(chat_id)
                    if history:
                        history_text = "📋 Your Recent Medical History:\n\n"
                        for i, (symptoms, diagnosis, timestamp, body_part, severity) in enumerate(history[:5], 1):
                            date_str = datetime.fromisoformat(timestamp).strftime("%b %d, %Y")
                            history_text += f"{i}. {date_str}: {symptoms[:50]}...\n"
                        send_telegram_message(chat_id, history_text)
                    else:
                        send_telegram_message(chat_id, "No medical history found.")
                elif text.lower() in ["clear", "/clear"]:
                    user_sessions[chat_id] = {"text": None, "image": None, "location": None, "last_activity": datetime.now(), "profile_step": None, "awaiting_location_for_clinics": False}
                    send_telegram_message(chat_id, "Session cleared. You can start fresh with new symptoms and images.")
                elif text.lower() == "proceed":
                    reply = process_user_input(chat_id, user_sessions[chat_id])
                    send_telegram_message(chat_id, reply)
                elif text.lower() in ["good", "bad"]:
                    # Handle feedback
                    history = get_user_history(chat_id, days_back=1)
                    if history:
                        history_id = get_history_id(chat_id, history[0][2])
                        if history_id:
                            save_feedback(chat_id, history_id, text.lower())
                            send_telegram_message(chat_id, f"Thank you for your {text} feedback! 🙏\n\nFeel free to ask about new symptoms or type 'history' to see past consultations.")
                        else:
                            send_telegram_message(chat_id, "No recent diagnosis found to provide feedback for.")
                    else:
                        send_telegram_message(chat_id, "No recent diagnosis found to provide feedback for.")
                else:
                    # Check if new user needs profile setup
                    if is_new_user(chat_id) and text.lower() != "skip":
                        start_profile_setup(chat_id, "telegram")
                        return "OK", 200
                    
                    # Check if this might be a country name (if no country is saved yet)
                    if not get_user_country(chat_id) and any(keyword in text.lower() for keyword in ['united states', 'usa', 'america', 'india', 'brazil', 'china', 'mexico', 'canada', 'australia', 'uk', 'england', 'france', 'germany', 'spain', 'italy', 'japan', 'korea', 'nigeria', 'south africa', 'egypt', 'pakistan', 'bangladesh', 'indonesia', 'philippines', 'vietnam', 'thailand', 'malaysia', 'singapore', 'turkey', 'iran', 'israel', 'saudi arabia', 'uae', 'qatar', 'kuwait', 'russia', 'ukraine', 'poland', 'netherlands', 'belgium', 'switzerland', 'sweden', 'norway', 'denmark', 'finland', 'argentina', 'chile', 'peru', 'colombia', 'venezuela']):
                        # This looks like a country name, save it
                        save_user_country(chat_id, text.title(), "telegram")
                        
                        # Check for disease outbreaks
                        outbreaks = check_disease_outbreaks_for_user(chat_id)
                        if outbreaks:
                            outbreak_msg = f"🌍 Thank you! I've saved {text.title()} as your country.\n\n⚠️ Disease Alert: There are {len(outbreaks)} disease outbreak(s) currently reported in {text.title()}. Stay informed and follow local health guidelines.\n\nFeel free to ask about symptoms or type 'history' to see past consultations."
                        else:
                            outbreak_msg = f"🌍 Thank you! I've saved {text.title()} as your country. I'll notify you of any disease outbreaks in your area.\n\nFeel free to ask about symptoms or type 'history' to see past consultations."
                        
                        send_telegram_message(chat_id, outbreak_msg)
                else:
                    user_sessions[chat_id]["text"] = text
                        reply = handle_partial_input(chat_id, user_sessions[chat_id])
                    send_telegram_message(chat_id, reply)

            elif "photo" in msg:
                # Check if new user needs profile setup
                if is_new_user(chat_id):
                    start_profile_setup(chat_id, "telegram")
                    return "OK", 200
                    
                photos = msg["photo"]
                file_id = photos[-1]["file_id"]
                file_path = get_telegram_file_path(file_id)
                if file_path:
                    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
                    image_base64 = download_telegram_image(file_url)
                    if image_base64:
                        user_sessions[chat_id]["image"] = image_base64
                        reply = handle_partial_input(chat_id, user_sessions[chat_id])
                        send_telegram_message(chat_id, reply)
                    else:
                        send_telegram_message(chat_id, "Sorry, I couldn't download the image. Please try sending it again.")
                else:
                    send_telegram_message(chat_id, "Sorry, I couldn't access the image. Please try sending it again.")

            elif "location" in msg:
                # Handle location sharing
                latitude = msg["location"]["latitude"]
                longitude = msg["location"]["longitude"]
                
                # Get address from coordinates
                address = reverse_geocode(latitude, longitude)
                
                # Check if we're waiting for location after diagnosis
                if user_sessions[chat_id].get("awaiting_location_for_clinics"):
                    # Provide clinic recommendations only
                    clinics = find_nearby_clinics(latitude, longitude)
                    save_user_location(chat_id, latitude, longitude, address, "telegram")
                    
                    if clinics:
                        clinic_text = f"📍 Based on your location ({address}), here are the nearest medical facilities:\n\n"
                        for i, clinic in enumerate(clinics, 1):
                            # Generate Google Maps link
                            maps_link = f"https://www.google.com/maps/search/?api=1&query={clinic['lat']},{clinic['lon']}"
                            clinic_text += f"{i}. **{clinic['name']}** ({clinic['type'].title()})\n   📍 {clinic['distance']}km away\n   🗺️ [Open in Maps]({maps_link})\n\n"
                        clinic_text += "Visit the most appropriate facility based on your symptoms' urgency.\n\n"
                        clinic_text += "Feel free to ask about new symptoms or type 'history' to see past consultations."
                    else:
                        clinic_text = f"📍 Location received: {address}\n\nI couldn't find specific medical facilities within 5km, but you should visit your nearest clinic or hospital for the symptoms discussed.\n\nFeel free to ask about new symptoms or type 'history' to see past consultations."
                    
                    user_sessions[chat_id]["awaiting_location_for_clinics"] = False
                    send_telegram_message(chat_id, clinic_text)
                else:
                    # Regular location sharing during symptom input
                    location_data = {"lat": latitude, "lon": longitude, "address": address}
                    user_sessions[chat_id]["location"] = location_data
                    save_user_location(chat_id, latitude, longitude, address, "telegram")
                    send_telegram_message(chat_id, f"📍 Location received: {address}\n\nNow you can share your symptoms or send an image for analysis!")

        return "OK", 200
    except Exception as e:
        print(f"Telegram webhook error: {e}")
        return "Error", 500

def start_profile_setup(user_id, platform):
    """Start the profile setup process for new users"""
    user_sessions[user_id]["profile_step"] = "age"
    message = (
        "👋 Welcome to MedSense AI!\n\n"
        "To provide you with more accurate medical analysis, I'd like to know a bit about you.\n\n"
        "📅 Please tell me your age (or type 'skip' if you prefer not to share):"
    )
    if platform == "whatsapp":
        send_whatsapp_message(user_id, message)
    else:
        send_telegram_message(user_id, message)

def handle_profile_setup(user_id, text, platform):
    """Handle user responses during profile setup"""
    step = user_sessions[user_id].get("profile_step")
    
    if step == "age":
        if text.lower() == "skip":
            user_sessions[user_id]["profile_step"] = None
            message = "No problem! You can start using MedSense AI right away.\n\n" + WELCOME_MSG
        else:
            try:
                age = int(text)
                if 1 <= age <= 120:
                    user_sessions[user_id]["temp_age"] = age
                    user_sessions[user_id]["profile_step"] = "gender"
                    message = "👤 Thank you! Now please tell me your gender (Male/Female/Other) or type 'skip':"
                else:
                    message = "Please enter a valid age between 1 and 120, or type 'skip':"
            except ValueError:
                message = "Please enter a valid number for your age, or type 'skip':"
                
    elif step == "gender":
        if text.lower() == "skip":
            age = user_sessions[user_id].get("temp_age")
            if age:
                save_user_profile(user_id, age, None, platform)
            user_sessions[user_id]["profile_step"] = None
            user_sessions[user_id].pop("temp_age", None)
            message = "✅ Profile saved! You can now start using MedSense AI.\n\n" + WELCOME_MSG
        else:
            gender = text.lower()
            if gender in ["male", "female", "other", "m", "f"]:
                # Normalize gender values
                if gender in ["m", "male"]:
                    gender = "Male"
                elif gender in ["f", "female"]:
                    gender = "Female"
                else:
                    gender = "Other"
                    
                age = user_sessions[user_id].get("temp_age")
                save_user_profile(user_id, age, gender, platform)
                user_sessions[user_id]["profile_step"] = None
                user_sessions[user_id].pop("temp_age", None)
                message = f"✅ Thank you! Profile saved (Age: {age}, Gender: {gender}).\n\n" + WELCOME_MSG
            else:
                message = "Please enter Male, Female, Other, or type 'skip':"
    else:
        message = "Something went wrong. Please start over."
        user_sessions[user_id]["profile_step"] = None
    
    if platform == "whatsapp":
        send_whatsapp_message(user_id, message)
    else:
        send_telegram_message(user_id, message)

# Handle partial input (text only or image only)
def handle_partial_input(user_id, session_data):
    text = session_data.get("text")
    image = session_data.get("image")
    location = session_data.get("location")
    
    location_prompt = ""
    if location:
        location_prompt = f"\n📍 Location: {location['address']}"
    
    if text and not image:
        # Generate language-aware response for text-only case
        template = f"✅ I've recorded your symptoms: '{text}'{location_prompt}\n\n📸 Please send an image of the affected area for a complete analysis, or type 'proceed' if you only want text-based analysis.\n\nType 'clear' to start over or 'history' to see past consultations."
        return generate_language_aware_response(text, template)
    elif image and not text:
        # For image-only, ask for text in English (no user text to detect from)
        return f"✅ I've received your image.{location_prompt}\n\n📝 Please describe your symptoms in text (e.g., 'I have pain and swelling'), or type 'proceed' if you only want image-based analysis.\n\nType 'clear' to start over or 'history' to see past consultations."
    else:
        # Both available - proceed with analysis
        return process_user_input(user_id, session_data)

# Process user input for analysis
def process_user_input(user_id, session_data):
    text = session_data.get("text")
    image = session_data.get("image")
    
    # Check if user has country info for disease outbreak notifications
    user_country = get_user_country(user_id)
    platform = "telegram" if str(user_id).startswith("-") or str(user_id).isdigit() or len(str(user_id)) > 15 else "whatsapp"
    
    if text and image:
        # Both text and image available - comprehensive analysis
        reply = gemini_combined_diagnose_with_history(str(user_id), text, image)
        user_sessions[user_id] = {"text": None, "image": None, "location": None, "last_activity": datetime.now(), "profile_step": None, "awaiting_location_for_clinics": True}
        
        # Ask for country if not available
        if not user_country:
            country_prompt = generate_language_aware_response(text, "\n\n🌍 To provide disease outbreak notifications, please tell me your country (e.g., 'United States', 'India', 'Brazil'):")
            reply += country_prompt
        else:
            # Check for disease outbreaks
            outbreaks = check_disease_outbreaks_for_user(user_id)
            if outbreaks:
                outbreak_text = generate_language_aware_response(text, f"\n\n⚠️ Disease Alert: There are {len(outbreaks)} disease outbreak(s) reported in {user_country}.")
                reply += outbreak_text
        
        return reply + "\n\n💬 Please provide feedback on this diagnosis by replying 'good' or 'bad' to help improve our service.\n\n📍 Would you like to share your location to get nearby clinic recommendations?"
    elif text and not image:
        # Text only analysis
        reply = gemini_text_diagnose_with_profile(str(user_id), text)
        save_diagnosis_to_history(user_id, platform, text, reply[:500] + "..." if len(reply) > 500 else reply)
        user_sessions[user_id] = {"text": None, "image": None, "location": None, "last_activity": datetime.now(), "profile_step": None, "awaiting_location_for_clinics": True}
        
        # Ask for country if not available
        if not user_country:
            country_prompt = generate_language_aware_response(text, "\n\n🌍 To provide disease outbreak notifications, please tell me your country (e.g., 'United States', 'India', 'Brazil'):")
            reply += country_prompt
        else:
            # Check for disease outbreaks
            outbreaks = check_disease_outbreaks_for_user(user_id)
            if outbreaks:
                outbreak_text = generate_language_aware_response(text, f"\n\n⚠️ Disease Alert: There are {len(outbreaks)} disease outbreak(s) reported in {user_country}.")
                reply += outbreak_text
        
        return reply + "\n\n💬 Please provide feedback on this diagnosis by replying 'good' or 'bad' to help improve our service.\n\n📍 Would you like to share your location to get nearby clinic recommendations?"
    elif image and not text:
        # Image only analysis
        reply = gemini_image_diagnose_with_profile(str(user_id), image)
        save_diagnosis_to_history(user_id, platform, "Image analysis only", reply[:500] + "..." if len(reply) > 500 else reply)
        user_sessions[user_id] = {"text": None, "image": None, "location": None, "last_activity": datetime.now(), "profile_step": None, "awaiting_location_for_clinics": True}
        
        # For image-only, ask for country in English
        if not user_country:
            reply += "\n\n🌍 To provide disease outbreak notifications, please tell me your country (e.g., 'United States', 'India', 'Brazil'):"
        else:
            # Check for disease outbreaks
            outbreaks = check_disease_outbreaks_for_user(user_id)
            if outbreaks:
                reply += f"\n\n⚠️ Disease Alert: There are {len(outbreaks)} disease outbreak(s) reported in {user_country}."
        
        return reply + "\n\n💬 Please provide feedback on this diagnosis by replying 'good' or 'bad' to help improve our service.\n\n📍 Would you like to share your location to get nearby clinic recommendations?"
    else:
        return "Please describe your symptoms or send an image. You can provide text, image, or both! Type 'history' to see past consultations."

def get_profile_text(user_id):
    """Get formatted user profile information for Gemini prompts"""
    profile = get_user_profile(user_id)
    if profile:
        age_text = f"Age: {profile['age']}" if profile['age'] else "Age: Not provided"
        gender_text = f"Gender: {profile['gender']}" if profile['gender'] else "Gender: Not provided"
        return f"\n\nUSER PROFILE:\n{age_text}\n{gender_text}"
    return "\n\nUSER PROFILE: No profile information available"

def get_location_and_clinics_text(location_data):
    """Get formatted location and nearby clinics information"""
    if not location_data:
        return "\n\nLOCATION: Not provided"
    
    location_text = f"\n\nUSER LOCATION:\n{location_data['address']}"
    
    # Find nearby clinics
    clinics = find_nearby_clinics(location_data['lat'], location_data['lon'])
    
    if clinics:
        location_text += "\n\nNEARBY MEDICAL FACILITIES:"
        for i, clinic in enumerate(clinics, 1):
            location_text += f"\n{i}. {clinic['name']} ({clinic['type']}) - {clinic['distance']}km away"
    else:
        location_text += "\n\nNo nearby medical facilities found within 5km radius."

    return location_text

# Combined Gemini Analysis with History and Profile
def gemini_combined_diagnose_with_history(user_id, symptom_text, base64_img):
    try:
        from langchain_core.messages import HumanMessage
        
        if not base64_img or len(base64_img) < 100:
            return "Sorry, the image data seems corrupted. Please try sending the image again."
        
        history = get_user_history(user_id, days_back=365)
        profile_text = get_profile_text(user_id)
        history_text = ""
        
        if history:
            history_text = "\n\nUSER'S MEDICAL HISTORY (Past 12 months):\n"
            for i, (past_symptoms, past_diagnosis, timestamp, body_part, severity) in enumerate(history[:10], 1):
                date_str = datetime.fromisoformat(timestamp).strftime("%b %d, %Y")
                history_text += f"{i}. {date_str}: Symptoms: {past_symptoms} | Diagnosis: {past_diagnosis}\n"
        else:
            history_text = "\n\nUSER'S MEDICAL HISTORY: No previous consultations found."
        
        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": f"""You are a helpful AI health assistant. I am providing you with an image, text describing current symptoms, user profile information, and medical history.

CURRENT SYMPTOMS: "{symptom_text}"{profile_text}{history_text}

CRITICAL: Detect the language of the user's symptoms text and respond in EXACTLY the same language. If the user wrote in Spanish, respond in Spanish. If they wrote in French, respond in French, etc.

IMPORTANT: Consider the user's age and gender when providing analysis.

Provide a comprehensive but concise analysis:

1. **Assessment**: Brief summary with confidence level (60-100%)
2. **Visual Observations**: What you see in the image
3. **Most Likely Condition**: Primary diagnosis considering age/gender
4. **Possible Causes**: Relevant to user's demographics
5. **Home Remedies**: 2-3 simple, safe remedies they can try
6. **Medical Advice**: Whether to visit clinic and urgency level

KEEP CONCISE: Maximum 600 characters total to avoid overwhelming the user.

End with a medical disclaimer appropriate for the detected language (equivalent to: "I am an AI health assistant, not a doctor. Seek medical help for more accurate diagnoses.")"""
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_img}"
                    }
                }
            ]
        )
        
        result = llm.invoke([message])
        result_content = result.content if isinstance(result.content, str) else str(result.content)
        current_diagnosis = result_content[:500] + "..." if len(result_content) > 500 else result_content
        platform = "telegram" if user_id.startswith("-") or user_id.isdigit() or len(user_id) > 15 else "whatsapp"
        save_diagnosis_to_history(user_id, platform, symptom_text, current_diagnosis)
        
        return result_content
    except Exception as e:
        print("Gemini combined analysis with history error:", e)
        fallback_result = gemini_text_diagnose_with_profile(user_id, symptom_text)
        return fallback_result + "\n\n(Note: Could not analyze the image, diagnosis based on symptoms only)"

# Gemini Text Only with Profile
def gemini_text_diagnose_with_profile(user_id, symptom_text):
    try:
        profile_text = get_profile_text(user_id)
        
        prompt = f"""You're a helpful AI health assistant. A user says: "{symptom_text}"

User Profile Information:{profile_text}

CRITICAL: Detect the language of the user's symptoms text and respond in EXACTLY the same language. If the user wrote in Spanish, respond in Spanish. If they wrote in French, respond in French, etc.

IMPORTANT: Consider the user's age and gender in your analysis.

Provide:
1. **Assessment**: Brief summary with confidence level (60-100%)
2. **Most Likely Condition**: Primary diagnosis considering age/gender
3. **Possible Causes**: Relevant to user's demographics  
4. **Home Remedies**: 2-3 simple, safe remedies they can try
5. **Medical Advice**: Whether to visit clinic and urgency level

KEEP CONCISE: Maximum 450 characters total to avoid overwhelming the user.

End with a medical disclaimer appropriate for the detected language (equivalent to: "I am an AI health assistant, not a doctor. Seek medical help for more accurate diagnoses.")"""
        result = llm.invoke(prompt)
        return result.content if isinstance(result.content, str) else str(result.content)
    except Exception as e:
        print("Gemini text error:", e)
        return "Sorry, I'm unable to process your request right now."

# Gemini Image Only with Profile
def gemini_image_diagnose_with_profile(user_id, base64_img):
    try:
        from langchain_core.messages import HumanMessage
        
        if not base64_img or len(base64_img) < 100:
            return "Sorry, the image data seems corrupted. Please try sending the image again."
        
        profile_text = get_profile_text(user_id)
        
        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": f"""Please analyze this medical image and describe any visible issues, potential conditions, and recommendations.

User Profile Information:{profile_text}

CRITICAL: Since this is an image-only analysis, respond in English by default. However, if the user has previously communicated in another language or if there are any text elements in the image that indicate a different language preference, respond in that language instead.

IMPORTANT: Consider the user's age and gender when analyzing the image.

Provide:
1. **Visual Observations**: What you see in the image
2. **Assessment**: Brief summary with confidence level (60-100%)
3. **Most Likely Condition**: Primary diagnosis considering age/gender
4. **Home Remedies**: 2-3 simple, safe remedies they can try
5. **Medical Advice**: Whether to visit clinic and urgency level

KEEP CONCISE: Maximum 450 characters total to avoid overwhelming the user.

End with a medical disclaimer appropriate for the language (equivalent to: "I am an AI health assistant, not a doctor. Seek medical help for more accurate diagnoses.")"""
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_img}"
                    }
                }
            ]
        )
        
        result = llm.invoke([message])
        return result.content if isinstance(result.content, str) else str(result.content)
    except Exception as e:
        print("Gemini image error:", e)
        return "Sorry, I couldn't analyze the image. Please try sending it again or describe your symptoms in text."

# WhatsApp Helpers
def get_image_url(media_id):
    url = f"https://graph.facebook.com/v19.0/{media_id}"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        print(f"Error getting image URL: {res.status_code}, {res.text}")
        return None
    return res.json().get('url')

def download_and_encode_image(image_url):
    try:
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
        res = requests.get(image_url, headers=headers)
        if res.status_code != 200:
            print(f"Error downloading image: {res.status_code}, {res.text}")
            return None
        if len(res.content) == 0:
            print("Downloaded image is empty")
            return None
        return base64.b64encode(res.content).decode('utf-8')
    except Exception as e:
        print(f"Error in download_and_encode_image: {e}")
        return None

def send_whatsapp_message(recipient, message):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "text",
        "text": {"body": message[:4096]}
    }
    res = requests.post(url, json=payload, headers=headers)
    print(f"WhatsApp message sent. Status: {res.status_code}, Response: {res.text}")

# Telegram Helpers
def get_telegram_file_path(file_id):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile"
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

def send_telegram_message(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id, 
            "text": text[:4096]
        }
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200 and res.json().get('ok'):
            return True
        return False
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return False

# Webhook setup
def set_telegram_webhook(webhook_url):
    try:
        delete_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook"
        requests.post(delete_url, timeout=10)
        set_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
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
    if TELEGRAM_BOT_TOKEN:
        token_works = test_telegram_token()
        if token_works:
            print("✅ Telegram token is valid")
            get_telegram_webhook_info()
        else:
            print("❌ Telegram token is invalid or bot is not working")
    else:
        print("❌ TELEGRAM_BOT_TOKEN not found in environment variables")
    
    # Production configuration for Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)