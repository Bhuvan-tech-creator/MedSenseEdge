from flask import Flask, request
import os
import requests
from dotenv import load_dotenv
import base64
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# Load env vars
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Init Flask
app = Flask(__name__)

# Init Gemini 2.5 Flash
llm = ChatGoogleGenerativeAI(
    model="models/gemini-2.5-flash",
    google_api_key=GEMINI_API_KEY
)

# Welcome + disclaimer
WELCOME_MSG = (
    "👋 Welcome to MedSense AI.\n"
    "Text your symptoms (e.g., 'I have fever and chills') or send an image.\n"
    "⚠️ I’m an AI assistant, not a doctor. For emergencies, text EMERGENCY or visit a clinic."
)

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Token mismatch", 403

    if request.method == "POST":
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
                        send_whatsapp_message(sender, "🚨 This may be urgent. Please visit a clinic immediately.")
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
            print("Error:", e)
        return "OK", 200

# TEXT DIAGNOSIS using LangChain + Gemini 2.5 Flash
def gemini_text_diagnose(symptom_text):
    try:
        prompt = f"""You're a helpful AI health assistant. A user says: "{symptom_text}"
Provide a potential diagnosis, possible causes, and whether they should visit a clinic.
End your message with a disclaimer: "I am not a doctor. This is an AI-based suggestion."""
        result = llm.invoke(prompt)
        return result.content
    except Exception as e:
        print("Gemini text error:", e)
        return "Sorry, I'm unable to process your request right now."

# IMAGE DIAGNOSIS
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
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        print("Gemini image error:", e)
        return "Sorry, I couldn’t analyze the image."

def get_image_url(media_id):
    url = f"https://graph.facebook.com/v19.0/{media_id}"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    res = requests.get(url, headers=headers)
    return res.json()['url']

def download_and_encode_image(url):
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    res = requests.get(url, headers=headers)
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
        "text": {"body": message}
    }
    res = requests.post(url, json=payload, headers=headers)
    print("WhatsApp status:", res.status_code, res.text)

if __name__ == "__main__":
    app.run(port=5000)
