from flask import Flask, request
import os
import requests
import base64
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
    "\u26A0\ufe0f I'm an AI assistant, not a doctor. For emergencies, text EMERGENCY or visit a clinic."
)

# Store user sessions to combine text and image
user_sessions = {}

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

# Telegram Webhook
@app.route("/webhook/telegram", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    try:
        msg = data.get("message", {})
        chat_id = msg.get("chat", {}).get("id")

        # Initialize user session if not exists
        if chat_id not in user_sessions:
            user_sessions[chat_id] = {"text": None, "image": None}

        if "text" in msg:
            text = msg["text"]
            if text.lower() == "clear":
                user_sessions[chat_id] = {"text": None, "image": None}
                send_telegram_message(chat_id, "Session cleared. You can start fresh with new symptoms and images.")
            else:
                user_sessions[chat_id]["text"] = text
                reply = process_user_input(chat_id, user_sessions[chat_id])
                send_telegram_message(chat_id, reply)

        elif "photo" in msg:
            file_id = msg["photo"][-1]["file_id"]
            file_path = get_telegram_file_path(file_id)
            if file_path:
                file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
                image_base64 = download_and_encode_image(file_url)
                if image_base64:
                    user_sessions[chat_id]["image"] = image_base64
                    reply = process_user_input(chat_id, user_sessions[chat_id])
                    send_telegram_message(chat_id, reply)
                else:
                    send_telegram_message(chat_id, "Sorry, I couldn't download the image. Please try sending it again.")
            else:
                send_telegram_message(chat_id, "Sorry, I couldn't access the image. Please try sending it again.")

    except Exception as e:
        print("Telegram Error:", e)
    return "OK", 200

# Process user input (combines text and image analysis)
def process_user_input(user_id, session_data):
    text = session_data.get("text")
    image = session_data.get("image")
    
    if text and image:
        # Both text and image available - provide comprehensive analysis
        reply = gemini_combined_diagnose(text, image)
        # Clear session after providing diagnosis
        user_sessions[user_id] = {"text": None, "image": None}
        return reply
    elif text and not image:
        # Only text available - store it and ask for image
        return f"✅ I've recorded your symptoms: '{text}'\n\n📸 Now please send an image of the affected area for a complete analysis. I'll analyze both together once I receive the image.\n\nType 'clear' to start over."
    elif image and not text:
        # Only image available - store it and ask for symptoms description
        return f"✅ I've received your image.\n\n📝 Now please describe your symptoms in text (e.g., 'I have pain and swelling'). I'll analyze both the image and your symptoms together.\n\nType 'clear' to start over."
    else:
        # Neither available
        return "Please describe your symptoms or send an image. For best results, provide both!"

# Combined Gemini Analysis (Text + Image)
def gemini_combined_diagnose(symptom_text, base64_img):
    try:
        from langchain_core.messages import HumanMessage
        
        # Validate base64 image
        if not base64_img or len(base64_img) < 100:
            return "Sorry, the image data seems corrupted. Please try sending the image again."
        
        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": f"""You are a helpful AI health assistant. I am providing you with BOTH an image and text describing symptoms. You MUST analyze BOTH the image AND the described symptoms together to provide a comprehensive diagnosis.

USER'S DESCRIBED SYMPTOMS: "{symptom_text}"

IMPORTANT: You must reference BOTH the visual findings from the image AND the symptoms described in the text above. Do not ignore either piece of information.

Please provide:

1. **Overall Assessment**: One sentence summary combining both visual and symptom findings
2. **Image Analysis**: What you observe in the image (visual findings)
3. **Symptom Summary**: Summary of the symptoms the user described: "{symptom_text}"
4. **Combined Diagnosis**: 2-3 most likely diagnoses based on BOTH the image AND the described symptoms
5. **Possible Causes**: 2-3 potential causes considering both visual and symptomatic evidence
6. **Recommendation**: Whether to visit a clinic and urgency level
7. **Additional Advice**: Any precautions or next steps

You MUST mention both the visual findings AND the described symptoms in your analysis.

End with: "I am not a doctor. This is an AI-based suggestion combining image and symptom analysis."

Keep under 2500 characters."""
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
        print("Gemini combined analysis error:", e)
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

# Telegram Helpers
def get_telegram_file_path(file_id):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
        res = requests.get(url)
        if res.status_code != 200:
            print(f"Error getting Telegram file path: {res.status_code}, {res.text}")
            return None
        return res.json().get('result', {}).get('file_path')
    except Exception as e:
        print(f"Error in get_telegram_file_path: {e}")
        return None

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text[:4096]}
    res = requests.post(url, json=payload)
    print(f"Telegram message sent. Status: {res.status_code}, Response: {res.text}")

if __name__ == "__main__":
    app.run(port=5000)