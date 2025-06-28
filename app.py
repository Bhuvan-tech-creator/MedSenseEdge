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
    "\u26A0\ufe0f I’m an AI assistant, not a doctor. For emergencies, text EMERGENCY or visit a clinic."
)

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

            if 'text' in msg:
                body = msg['text']['body']
                if body.lower() == "help":
                    send_whatsapp_message(sender, "Type your symptoms or send an image.")
                elif body.lower() == "emergency":
                    send_whatsapp_message(sender, "\ud83d\udea8 This may be urgent. Please visit a clinic immediately.")
                else:
                    reply = gemini_text_diagnose(body)
                    send_whatsapp_message(sender, reply)

            elif 'image' in msg:
                media_id = msg['image']['id']
                image_url = get_image_url(media_id)
                image_base64 = download_and_encode_image(image_url)
                reply = gemini_image_diagnose(image_base64)
                send_whatsapp_message(sender, reply)

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

        if "text" in msg:
            reply = gemini_text_diagnose(msg["text"])
            send_telegram_message(chat_id, reply)

        elif "photo" in msg:
            file_id = msg["photo"][-1]["file_id"]
            file_path = get_telegram_file_path(file_id)
            file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
            image_base64 = download_and_encode_image(file_url)
            reply = gemini_image_diagnose(image_base64)
            send_telegram_message(chat_id, reply)

    except Exception as e:
        print("Telegram Error:", e)
    return "OK", 200

# Gemini Text

def gemini_text_diagnose(symptom_text):
    try:
        prompt = f"""You're a helpful AI health assistant. A user says: \"{symptom_text}\"
Provide a potential diagnosis, possible causes, and whether they should visit a clinic.
First, start the message with a one sentence summary of the diagnosis.
Then, give a short summary of the symptoms that the user entered.
Then, list 2-3 reasonable diagnoses with explanations.
Then, list 2-3 causes for this condition / illness.
Then, answer whether the user should visit a clinic.
End your message with a disclaimer: \"I am not a doctor. This is an AI-based suggestion.
Make sure that the message in total is less than 2500 characters long."""
        result = llm.invoke(prompt)
        return result.content
    except Exception as e:
        print("Gemini text error:", e)
        return "Sorry, I'm unable to process your request right now."

# Gemini Image

def gemini_image_diagnose(base64_img):
    try:
        prompt = [
            {"role": "user", "parts": [
                {"text": "Please analyze this medical image and describe any visible issues."},
                {"inline_data": {
                    "mime_type": "image/jpeg",
                    "data": base64_img
                }}
            ]}
        ]
        result = llm.invoke(prompt)
        return result.content
    except Exception as e:
        print("Gemini image error:", e)
        return "Sorry, I couldn’t analyze the image."

# WhatsApp Helpers

def get_image_url(media_id):
    url = f"https://graph.facebook.com/v19.0/{media_id}"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    res = requests.get(url, headers=headers)
    return res.json()['url']

def download_and_encode_image(url):
    res = requests.get(url)
    return base64.b64encode(res.content).decode('utf-8')

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
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
    res = requests.get(url)
    return res.json()['result']['file_path']

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text[:4096]}
    res = requests.post(url, json=payload)
    print(f"Telegram message sent. Status: {res.status_code}, Response: {res.text}")

if __name__ == "__main__":
    app.run(port=5000)
