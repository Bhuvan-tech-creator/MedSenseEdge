from flask import Flask, request, jsonify
import os
import requests
import base64
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# Environment Variables
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Flask App
app = Flask(__name__)

# Gemini 2.5 Flash LLM Init
llm = ChatGoogleGenerativeAI(
    model="models/gemini-2.5-flash",
    google_api_key=GEMINI_API_KEY
)

WELCOME_MSG = (
    "\U0001F44B Welcome to MedSense AI.\n"
    "Type your symptoms (e.g., 'I have fever and chills') or send an image from your camera or gallery.\n"
    "For best results, send both an image and describe your symptoms!\n"
    "📋 Type 'history' to see your past consultations\n"
    "\u26A0\ufe0f I'm an AI assistant, not a doctor. For emergencies, text EMERGENCY or visit a clinic."
)

# Store user sessions to combine text and image
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
    conn.commit()
    conn.close()

def save_diagnosis_to_history(user_id, platform, symptoms, diagnosis, body_part=None, severity=None):
    try:
        conn = sqlite3.connect('medsense_history.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO symptom_history (user_id, platform, symptoms, diagnosis, timestamp, body_part, severity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, platform, symptoms, diagnosis, datetime.now(), body_part, severity))
        conn.commit()
        conn.close()
        print(f"Saved diagnosis to history for user {user_id}")
    except Exception as e:
        print(f"Error saving to database: {e}")

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

# Initialize database on startup
init_database()

# Function to test Telegram bot token
def test_telegram_token():
    """Test if the Telegram bot token is valid"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
        response = requests.get(url, timeout=10)
        
        print(f"Telegram token test - Status: {response.status_code}")
        print(f"Telegram token test - Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                bot_info = data.get('result', {})
                print(f"✅ Telegram bot is working! Bot name: {bot_info.get('first_name')}, Username: @{bot_info.get('username')}")
                return True
            else:
                print(f"❌ Telegram API returned error: {data}")
                return False
        else:
            print(f"❌ HTTP error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing Telegram token: {e}")
        return False

# Function to get webhook info
def get_telegram_webhook_info():
    """Get current webhook information"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                webhook_info = data.get('result', {})
                print(f"Current webhook URL: {webhook_info.get('url', 'Not set')}")
                print(f"Pending update count: {webhook_info.get('pending_update_count', 0)}")
                print(f"Last error date: {webhook_info.get('last_error_date', 'None')}")
                print(f"Last error message: {webhook_info.get('last_error_message', 'None')}")
                return webhook_info
        return None
    except Exception as e:
        print(f"Error getting webhook info: {e}")
        return None

# Root route for health check
@app.route("/", methods=["GET"])
def health_check():
    return "MedSense AI Bot is running!", 200

# Test route for Telegram
@app.route("/test-telegram", methods=["GET"])
def test_telegram_endpoint():
    """Test endpoint to check Telegram bot status"""
    token_works = test_telegram_token()
    webhook_info = get_telegram_webhook_info()
    
    return jsonify({
        "telegram_token_valid": token_works,
        "webhook_info": webhook_info
    })

# WhatsApp Webhook
@app.route("/webhook", methods=["GET", "POST"])
def whatsapp_webhook():
    if request.method == "GET":
        if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Verification failed", 403

    data = request.get_json()
    try:
        entry = data['entry'][0]['changes'][0]['value']
        messages = entry.get('messages', [])
        if messages:
            msg = messages[0]
            sender = msg['from']

            # Initialize user session if not exists
            if sender not in user_sessions:
                user_sessions[sender] = {"text": None, "image": None}

            if 'text' in msg:
                body = msg['text']['body']
                if body.lower() == "help":
                    send_whatsapp_message(sender, "Type your symptoms or send an image. For best diagnosis, send both!")
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
                    user_sessions[sender] = {"text": None, "image": None}
                    send_whatsapp_message(sender, "Session cleared. You can start fresh with new symptoms and images.")
                else:
                    user_sessions[sender]["text"] = body
                    reply = process_user_input(sender, user_sessions[sender])
                    send_whatsapp_message(sender, reply)

            elif 'image' in msg:
                media_id = msg['image']['id']
                image_url = get_image_url(media_id)
                if image_url:
                    image_base64 = download_and_encode_image(image_url)
                    if image_base64:
                        user_sessions[sender]["image"] = image_base64
                        reply = process_user_input(sender, user_sessions[sender])
                        send_whatsapp_message(sender, reply)
                    else:
                        send_whatsapp_message(sender, "Sorry, I couldn't download the image. Please try sending it again.")
                else:
                    send_whatsapp_message(sender, "Sorry, I couldn't access the image. Please try sending it again.")

    except Exception as e:
        print("WhatsApp Error:", e)
    return "OK", 200

# Telegram Webhook - Fixed and improved
@app.route("/webhook/telegram", methods=["POST"])
def telegram_webhook():
    print("=== Telegram webhook called ===")
    
    try:
        # Get raw data for debugging
        raw_data = request.get_data(as_text=True)
        print(f"Raw data received: {raw_data}")
        
        data = request.get_json()
        print(f"Parsed JSON data: {data}")
        
        if not data:
            print("❌ No data received from Telegram")
            return "No data", 400
        
        # Handle different types of updates
        if "message" in data:
            msg = data["message"]
            print(f"Message object: {msg}")
            
            # Get chat info
            chat = msg.get("chat", {})
            chat_id = str(chat.get("id", ""))
            chat_type = chat.get("type", "")
            
            # Get user info
            user = msg.get("from", {})
            user_id = user.get("id")
            username = user.get("username", "")
            first_name = user.get("first_name", "")
            
            print(f"Chat ID: {chat_id}, Chat Type: {chat_type}")
            print(f"User ID: {user_id}, Username: {username}, Name: {first_name}")
            
            if not chat_id:
                print("❌ No chat_id found in message")
                return "No chat_id", 400
            
            # Initialize user session if not exists
            if chat_id not in user_sessions:
                user_sessions[chat_id] = {"text": None, "image": None}
                print(f"✅ Initialized session for chat_id: {chat_id}")

            # Handle /start command
            if "text" in msg:
                text = msg["text"]
                print(f"📝 Text message received: '{text}'")
                
                if text.startswith("/start"):
                    print("🚀 Handling /start command")
                    success = send_telegram_message(chat_id, WELCOME_MSG)
                    print(f"Welcome message sent: {success}")
                    return "OK", 200
                elif text.lower() in ["help", "/help"]:
                    send_telegram_message(chat_id, "Type your symptoms or send an image. For best diagnosis, send both!")
                elif text.lower() in ["emergency", "/emergency"]:
                    send_telegram_message(chat_id, "🚨 This may be urgent. Please visit a clinic immediately.")
                elif text.lower() in ["history", "/history"]:
                    history = get_user_history(chat_id)
                    if history:
                        history_text = "📋 Your Recent Medical History:\n\n"
                        for i, (symptoms, diagnosis, timestamp, body_part, severity) in enumerate(history[:5], 1):
                            try:
                                date_str = datetime.fromisoformat(timestamp).strftime("%b %d, %Y")
                            except:
                                date_str = "Unknown date"
                            history_text += f"{i}. {date_str}: {symptoms[:50]}...\n"
                        send_telegram_message(chat_id, history_text)
                    else:
                        send_telegram_message(chat_id, "No medical history found.")
                elif text.lower() in ["clear", "/clear"]:
                    user_sessions[chat_id] = {"text": None, "image": None}
                    send_telegram_message(chat_id, "Session cleared. You can start fresh with new symptoms and images.")
                else:
                    print(f"💬 Processing regular text message")
                    user_sessions[chat_id]["text"] = text
                    reply = process_user_input(chat_id, user_sessions[chat_id])
                    send_telegram_message(chat_id, reply)

            # Handle photo messages
            elif "photo" in msg:
                print("📸 Photo message received")
                try:
                    photos = msg["photo"]
                    if not photos:
                        print("❌ No photos in photo message")
                        send_telegram_message(chat_id, "Sorry, I couldn't access the photo. Please try sending it again.")
                        return "OK", 200
                    
                    # Get highest resolution photo
                    file_id = photos[-1]["file_id"]
                    print(f"📷 Photo file_id: {file_id}")
                    
                    file_path = get_telegram_file_path(file_id)
                    if file_path:
                        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
                        print(f"🔗 Photo URL: {file_url}")
                        
                        image_base64 = download_telegram_image(file_url)
                        if image_base64:
                            user_sessions[chat_id]["image"] = image_base64
                            reply = process_user_input(chat_id, user_sessions[chat_id])
                            send_telegram_message(chat_id, reply)
                        else:
                            send_telegram_message(chat_id, "Sorry, I couldn't download the image. Please try sending it again.")
                    else:
                        send_telegram_message(chat_id, "Sorry, I couldn't access the image. Please try sending it again.")
                except Exception as e:
                    print(f"❌ Error processing photo: {e}")
                    import traceback
                    traceback.print_exc()
                    send_telegram_message(chat_id, "Sorry, there was an error processing your image. Please try again.")
            else:
                print(f"ℹ️ Unhandled message type: {list(msg.keys())}")
                send_telegram_message(chat_id, "I can handle text messages and photos. Please send your symptoms or an image.")

        else:
            print(f"ℹ️ Unhandled update type: {list(data.keys())}")

        return "OK", 200
        
    except Exception as e:
        print(f"❌ Telegram webhook error: {e}")
        import traceback
        traceback.print_exc()
        return "Error", 500

# Process user input (combines text and image analysis)
def process_user_input(user_id, session_data):
    text = session_data.get("text")
    image = session_data.get("image")
    
    if text and image:
        # Both text and image available - provide comprehensive analysis with history
        reply = gemini_combined_diagnose_with_history(str(user_id), text, image)
        # Clear session after providing diagnosis
        user_sessions[user_id] = {"text": None, "image": None}
        return reply
    elif text and not image:
        # Only text available - store it and ask for image
        return f"✅ I've recorded your symptoms: '{text}'\n\n📸 Now please send an image of the affected area for a complete analysis. I'll analyze both together once I receive the image.\n\nType 'clear' to start over or 'history' to see past consultations."
    elif image and not text:
        # Only image available - store it and ask for symptoms description
        return f"✅ I've received your image.\n\n📝 Now please describe your symptoms in text (e.g., 'I have pain and swelling'). I'll analyze both the image and your symptoms together.\n\nType 'clear' to start over or 'history' to see past consultations."
    else:
        # Neither available
        return "Please describe your symptoms or send an image. For best results, provide both! Type 'history' to see past consultations."

# Combined Gemini Analysis with History (Text + Image + Past Diagnoses)
def gemini_combined_diagnose_with_history(user_id, symptom_text, base64_img):
    try:
        from langchain_core.messages import HumanMessage
        
        # Validate base64 image
        if not base64_img or len(base64_img) < 100:
            return "Sorry, the image data seems corrupted. Please try sending the image again."
        
        # Get user's medical history
        history = get_user_history(user_id, days_back=365)
        history_text = ""
        
        if history:
            history_text = "\n\nUSER'S MEDICAL HISTORY (Past 12 months):\n"
            for i, (past_symptoms, past_diagnosis, timestamp, body_part, severity) in enumerate(history[:10], 1):
                try:
                    date_str = datetime.fromisoformat(timestamp).strftime("%b %d, %Y")
                except:
                    date_str = "Unknown date"
                history_text += f"{i}. {date_str}: Symptoms: {past_symptoms} | Diagnosis: {past_diagnosis}\n"
        else:
            history_text = "\n\nUSER'S MEDICAL HISTORY: No previous consultations found."
        
        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": f"""You are a helpful AI health assistant. I am providing you with BOTH an image and text describing current symptoms, plus the user's medical history. You MUST provide TWO separate diagnoses.

CURRENT SYMPTOMS: "{symptom_text}"{history_text}

IMPORTANT: You must provide EXACTLY TWO diagnoses:

**DIAGNOSIS 1 - WITHOUT HISTORY:**
Analyze ONLY the current image and symptoms, ignoring medical history completely.

**DIAGNOSIS 2 - WITH HISTORY CONSIDERATION:**
Analyze the current image and symptoms while considering how the medical history might be relevant (e.g., recurring conditions, complications from past injuries, chronic conditions, related body parts).

For each diagnosis provide:
1. **Assessment**: Brief summary of findings
2. **Visual Observations**: What you see in the image
3. **Most Likely Condition**: Primary diagnosis
4. **Possible Causes**: 2 potential causes
5. **Recommendation**: Whether to visit clinic and urgency

For Diagnosis 2, specifically mention if and how the medical history influences your assessment.

End with: "I am not a doctor. This analysis considers your medical history for context."

Keep under 3000 characters total."""
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
        
        # Save this consultation to history
        current_diagnosis = result.content[:500] + "..." if len(result.content) > 500 else result.content
        platform = "telegram" if user_id.startswith("-") or user_id.isdigit() or len(user_id) > 15 else "whatsapp"
        save_diagnosis_to_history(user_id, platform, symptom_text, current_diagnosis)
        
        return result.content
    except Exception as e:
        print("Gemini combined analysis with history error:", e)
        # Fallback to text-only analysis
        return gemini_text_diagnose(symptom_text) + "\n\n(Note: Could not analyze the image, diagnosis based on symptoms only)"

# Gemini Text Only
def gemini_text_diagnose(symptom_text):
    try:
        prompt = f"""You're a helpful AI health assistant. A user says: \"{symptom_text}\"
Provide a potential diagnosis, possible causes, and whether they should visit a clinic.
First, start the message with a one sentence summary of the diagnosis.
Then, give a short summary of the symptoms that the user entered.
Then, list 2-3 reasonable diagnoses with explanations.
Then, list 2-3 causes for this condition / illness.
Then, answer whether the user should visit a clinic.
End your message with a disclaimer: \"I am not a doctor. This is an AI-based suggestion.\"
Make sure that the message in total is less than 2500 characters long."""
        result = llm.invoke(prompt)
        return result.content
    except Exception as e:
        print("Gemini text error:", e)
        return "Sorry, I'm unable to process your request right now."

# Gemini Image Only
def gemini_image_diagnose(base64_img):
    try:
        from langchain_core.messages import HumanMessage
        
        # Validate base64 image
        if not base64_img or len(base64_img) < 100:
            return "Sorry, the image data seems corrupted. Please try sending the image again."
        
        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": """Please analyze this medical image and describe any visible issues, potential conditions, and recommendations.

Provide:
1. What you observe in the image
2. Possible conditions based on visual appearance
3. Recommended next steps
4. Disclaimer that this is AI analysis, not medical diagnosis

Keep response under 2500 characters."""
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
        return result.content
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
        
        # Verify we have image content
        if len(res.content) == 0:
            print("Downloaded image is empty")
            return None
            
        print(f"Downloaded image size: {len(res.content)} bytes")
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

# Telegram Helpers - Improved with better error handling
def get_telegram_file_path(file_id):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile"
        payload = {"file_id": file_id}
        res = requests.post(url, json=payload, timeout=10)
        
        print(f"getFile API call - Status: {res.status_code}, Response: {res.text}")
        
        if res.status_code != 200:
            print(f"❌ Error getting Telegram file path: {res.status_code}, {res.text}")
            return None
            
        result = res.json()
        if result.get('ok'):
            file_path = result.get('result', {}).get('file_path')
            print(f"✅ Got file path: {file_path}")
            return file_path
        else:
            print(f"❌ Telegram API error: {result}")
            return None
    except Exception as e:
        print(f"❌ Error in get_telegram_file_path: {e}")
        return None

def download_telegram_image(file_url):
    try:
        print(f"🔽 Downloading image from: {file_url}")
        res = requests.get(file_url, timeout=30)
        
        if res.status_code != 200:
            print(f"❌ Error downloading Telegram image: {res.status_code}, {res.text}")
            return None
        
        # Verify we have image content
        if len(res.content) == 0:
            print("❌ Downloaded Telegram image is empty")
            return None
            
        print(f"✅ Downloaded Telegram image size: {len(res.content)} bytes")
        encoded = base64.b64encode(res.content).decode('utf-8')
        print(f"✅ Encoded image size: {len(encoded)} characters")
        return encoded
    except Exception as e:
        print(f"❌ Error in download_telegram_image: {e}")
        return None

def send_telegram_message(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id, 
            "text": text[:4096]
        }
        
        print(f"📤 Sending message to chat_id {chat_id}: {text[:100]}...")
        res = requests.post(url, json=payload, timeout=10)
        print(f"📤 Telegram message response - Status: {res.status_code}, Response: {res.text}")
        
        if res.status_code == 200:
            result = res.json()
            if result.get('ok'):
                print(f"✅ Message sent successfully")
                return True
            else:
                print(f"❌ Telegram API error: {result}")
                return False
        else:
            print(f"❌ HTTP error: {res.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending Telegram message: {e}")
        return False

# Improved webhook setup function
def set_telegram_webhook(webhook_url):
    """Call this function to set up the Telegram webhook"""
    try:
        # First, delete any existing webhook
        delete_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook"
        delete_res = requests.post(delete_url, timeout=10)
        print(f"Delete webhook response: {delete_res.status_code}, {delete_res.text}")
        
        # Set new webhook
        set_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
        payload = {
            "url": f"{webhook_url}/webhook/telegram",
            "allowed_updates": ["message", "callback_query"]
        }
        set_res = requests.post(set_url, json=payload, timeout=10)
        print(f"Set webhook response: {set_res.status_code}, {set_res.text}")
        
        if set_res.status_code == 200:
            result = set_res.json()
            if result.get('ok'):
                print(f"✅ Webhook set successfully to: {webhook_url}/webhook/telegram")
                return True
            else:
                print(f"❌ Failed to set webhook: {result}")
                return False
        else:
            print(f"❌ HTTP error setting webhook: {set_res.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error setting webhook: {e}")
        return False

# Route to manually set webhook
@app.route("/set-webhook/<path:webhook_url>", methods=["GET"])
def manual_set_webhook(webhook_url):
    """Manual route to set webhook - useful for testing"""
    # Ensure the URL has proper protocol
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
    
    # Test Telegram token on startup
    print("\n=== Testing Telegram Token ===")
    if TELEGRAM_BOT_TOKEN:
        token_works = test_telegram_token()
        if token_works:
            print("✅ Telegram token is valid")
            get_telegram_webhook_info()
        else:
            print("❌ Telegram token is invalid or bot is not working")
    else:
        print("❌ TELEGRAM_BOT_TOKEN not found in environment variables")
    
    print("\n=== Starting Flask App ===")
    app.run(port=5000, debug=True)