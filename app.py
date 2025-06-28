from flask import Flask, request, jsonify
import os
import requests
import base64
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr

load_dotenv()

# Environment Variables
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Flask App
app = Flask(__name__)

# Gemini 2.5 Flash LLM Init - Fixed SecretStr type
llm = ChatGoogleGenerativeAI(
    model="models/gemini-2.5-flash",
    api_key=SecretStr(GEMINI_API_KEY) if GEMINI_API_KEY else None
)

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

# Initialize Database
def init_database():
    conn = sqlite3.connect('medsense_history.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS symptom_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            symptoms TEXT NOT NULL,
            diagnosis TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            body_part TEXT,
            severity TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS diagnosis_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            history_id INTEGER NOT NULL,
            feedback TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            FOREIGN KEY (history_id) REFERENCES symptom_history(id)
        )
    ''')
    
    # Add user profiles table for age and gender
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            age INTEGER,
            gender TEXT,
            timestamp DATETIME NOT NULL,
            platform TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

def save_user_profile(user_id, age, gender, platform):
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO user_profiles (user_id, age, gender, timestamp, platform)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, age, gender, datetime.now(), platform))
        conn.commit()
        conn.close()
        print(f"Saved profile for user {user_id}: age {age}, gender {gender}")
        return True
    except Exception as e:
        print(f"Error saving user profile: {e}")
        return False

def get_user_profile(user_id):
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT age, gender FROM user_profiles WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        conn.close()
        if result:
            return {"age": result[0], "gender": result[1]}
        return None
    except Exception as e:
        print(f"Error retrieving user profile: {e}")
        return None

def is_new_user(user_id):
    """Check if user is new (no profile and no history)"""
    profile = get_user_profile(user_id)
    history = get_user_history(user_id)
    return profile is None and len(history) == 0

def save_diagnosis_to_history(user_id, platform, symptoms, diagnosis, body_part=None, severity=None):
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO symptom_history (user_id, platform, symptoms, diagnosis, timestamp, body_part, severity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, platform, symptoms, diagnosis, datetime.now(), body_part, severity))
        history_id = cursor.lastrowid
        conn.commit()
        conn.close()
        print(f"Saved diagnosis to history for user {user_id}")
        return history_id
    except Exception as e:
        print(f"Error saving to database: {e}")
        return None

def save_feedback(user_id, history_id, feedback):
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO diagnosis_feedback (user_id, history_id, feedback, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (user_id, history_id, feedback, datetime.now()))
        conn.commit()
        conn.close()
        print(f"Saved feedback for user {user_id}, history_id {history_id}")
    except Exception as e:
        print(f"Error saving feedback: {e}")

def get_user_history(user_id, days_back=365):
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        cutoff_date = datetime.now() - timedelta(days=days_back)
        cursor.execute('''
            SELECT symptoms, diagnosis, timestamp, body_part, severity 
            FROM symptom_history 
            WHERE user_id = ? AND timestamp >= ?
            ORDER BY timestamp DESC
        ''', (user_id, cutoff_date))
        history = cursor.fetchall()
        conn.close()
        return history
    except Exception as e:
        print(f"Error retrieving history: {e}")
        return []

def get_history_id(user_id, timestamp):
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM symptom_history 
            WHERE user_id = ? AND timestamp = ?
        ''', (user_id, timestamp))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        print(f"Error retrieving history_id: {e}")
        return None

def clear_inactive_sessions():
    """Clear sessions for users inactive for more than 2 months"""
    two_months_ago = datetime.now() - timedelta(days=60)
    inactive_users = [user_id for user_id, session in user_sessions.items() 
                    if session.get('last_activity', datetime.now()) < two_months_ago]
    for user_id in inactive_users:
        user_sessions[user_id] = {"text": None, "image": None, "last_activity": datetime.now(), "profile_step": None}
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
                user_sessions[sender] = {"text": None, "image": None, "last_activity": datetime.now(), "profile_step": None}
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
                    user_sessions[sender] = {"text": None, "image": None, "last_activity": datetime.now(), "profile_step": None}
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
                user_sessions[chat_id] = {"text": None, "image": None, "last_activity": datetime.now(), "profile_step": None}
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
                    user_sessions[chat_id] = {"text": None, "image": None, "last_activity": datetime.now(), "profile_step": None}
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
    
    if text and not image:
        return f"✅ I've recorded your symptoms: '{text}'\n\n📸 Please send an image of the affected area for a complete analysis, or type 'proceed' if you only want text-based analysis.\n\nType 'clear' to start over or 'history' to see past consultations."
    elif image and not text:
        return f"✅ I've received your image.\n\n📝 Please describe your symptoms in text (e.g., 'I have pain and swelling'), or type 'proceed' if you only want image-based analysis.\n\nType 'clear' to start over or 'history' to see past consultations."
    else:
        # Both available - proceed with analysis
        return process_user_input(user_id, session_data)

# Process user input for analysis
def process_user_input(user_id, session_data):
    text = session_data.get("text")
    image = session_data.get("image")
    
    if text and image:
        # Both text and image available - comprehensive analysis
        reply = gemini_combined_diagnose_with_history(str(user_id), text, image)
        user_sessions[user_id] = {"text": None, "image": None, "last_activity": datetime.now(), "profile_step": None}
        return reply + "\n\n💬 Please provide feedback on this diagnosis by replying 'good' or 'bad' to help improve our service."
    elif text and not image:
        # Text only analysis
        reply = gemini_text_diagnose_with_profile(str(user_id), text)
        # Save text-only diagnosis to history
        platform = "telegram" if str(user_id).startswith("-") or str(user_id).isdigit() or len(str(user_id)) > 15 else "whatsapp"
        save_diagnosis_to_history(user_id, platform, text, reply[:500] + "..." if len(reply) > 500 else reply)
        user_sessions[user_id] = {"text": None, "image": None, "last_activity": datetime.now(), "profile_step": None}
        return reply + "\n\n💬 Please provide feedback on this diagnosis by replying 'good' or 'bad' to help improve our service."
    elif image and not text:
        # Image only analysis
        reply = gemini_image_diagnose_with_profile(str(user_id), image)
        # Save image-only diagnosis to history
        platform = "telegram" if str(user_id).startswith("-") or str(user_id).isdigit() or len(str(user_id)) > 15 else "whatsapp"
        save_diagnosis_to_history(user_id, platform, "Image analysis only", reply[:500] + "..." if len(reply) > 500 else reply)
        user_sessions[user_id] = {"text": None, "image": None, "last_activity": datetime.now(), "profile_step": None}
        return reply + "\n\n💬 Please provide feedback on this diagnosis by replying 'good' or 'bad' to help improve our service."
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

IMPORTANT: Consider the user's age and gender when providing analysis, as medical conditions can vary significantly by demographic factors.

Provide TWO separate diagnoses:

**DIAGNOSIS 1 - WITHOUT HISTORY:**
Analyze ONLY the current image, symptoms, and user profile (age/gender), ignoring medical history. Make sure to provide a reasonable diagnosis taking in factors like what's happening in the world right now and how common the diagnosis might be. Keep this diagnosis less than 500 characters long. 

**DIAGNOSIS 2 - WITH HISTORY CONSIDERATION:**
Analyze the current image, symptoms, and user profile while considering how the medical history might be relevant. Make sure to provide a reasonable diagnosis taking in factors liek what's happening in the world right now and how common the diagnosis might be. Keep this diagnosis less than 500 characters long. 

For each diagnosis provide:
1. **Assessment**: Brief summary considering age and gender factors
2. **Visual Observations**: What you see in the image
3. **Most Likely Condition**: Primary diagnosis with age/gender considerations
4. **Confidence Level**: A percentage score of how confident you are on the diagnosis from 1 - 100%
5. **Possible Causes**: A potential cause relevant to user's demographics
6. **Recommendation**: Whether to visit clinic and urgency level

For Diagnosis 2, specifically mention if medical history influences your assessment.

End with: "I am an AI health assistant, not a doctor. Seek medical help for more accurate diagnoses."

Keep under 1250 characters total."""
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
        prompt = f"""You're a helpful AI health assistant. A user says: \"{symptom_text}\"

User Profile Information:{profile_text}

Provide a potential diagnosis, possible causes, and whether they should visit a clinic.
IMPORTANT: Consider the user's age and gender in your analysis, as medical conditions can vary significantly by demographic factors.

First, start with a one sentence summary of the diagnosis.
Then, give a short summary of the symptoms.
Then, list 1-2 reasonable diagnoses with explanations and confidence levels (percentage score from 1-100%), considering age and gender factors.
Then, list a potential cause for this condition, relevant to the user's demographic.
Then, answer whether the user should visit a clinic.
End with: \"I am an AI health assistant, not a doctor. Seek medical help for more accurate diagnoses.\"
Keep under 750 characters."""
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

IMPORTANT: Consider the user's age and gender when analyzing the image, as medical conditions can vary significantly by demographic factors.

Provide:
1. What you observe in the image that is related to medicine and health of the user
2. Possible conditions based on visual appearance with confidence levels (a percentage score from 1-100%), considering age and gender
3. Recommended next steps appropriate for the user's demographic
4. Disclaimer that this is AI analysis, not medical diagnosis

End with: "I am an AI health assistant, not a doctor. Seek medical help for more accurate diagnoses."
Keep response under 750 characters."""
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
    app.run(port=5000, debug=True)