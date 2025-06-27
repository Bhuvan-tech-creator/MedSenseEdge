from flask import Flask, request, jsonify, abort
import os
import requests
from dotenv import load_dotenv
import base64

load_dotenv()

# Load secrets from .env
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")  # Should be 'medsenseedge'
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")  # Your WhatsApp Bearer token
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")  # Your WhatsApp phone number ID
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Your Google Gemini API key

app = Flask(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"

WELCOME_MSG = (
    "👋 Welcome to MedSense AI.\n"
    "Text your symptoms (e.g., 'I have fever and chills') or send an image.\n"
    "⚠️ I’m an AI assistant, not a doctor. For emergencies, text EMERGENCY or visit a clinic."
)

@app.route("/webhook", methods=["GET", "POST"])
def whatsapp_webhook():
    if request.method == "GET":
        # Verification handshake with Meta
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        else:
            return "Verification token mismatch", 403

    if request.method == "POST":
        # Handle incoming WhatsApp messages
        data = request.get_json()
        try:
            entry = data['entry'][0]['changes'][0]['value']
            messages = entry.get('messages', [])
            if messages:
                message = messages[0]
                sender = message['from']

                # Send welcome message if it's the first message (optional)
                # You can check a DB or session here for first-time users

                # Text message handling
                if 'text' in message:
                    user_msg = message['text']['body'].strip()
                    if user_msg.lower() == "help":
                        send_whatsapp_message(sender, "Type your symptoms or send a photo.")
                    elif user_msg.lower() == "emergency":
                        send_whatsapp_message(sender, "🚨 This may be urgent. Visit a clinic nearby.")
                    else:
                        ai_response = gemini_text_diagnose(user_msg)
                        send_whatsapp_message(sender, ai_response)

                # Image message handling
                elif 'image' in message:
                    media_id = message['image']['id']
                    image_url = get_image_url(media_id)
                    image_base64 = download_and_encode_image(image_url)
                    ai_response = gemini_image_diagnose(image_base64)
                    send_whatsapp_message(sender, ai_response)

                # Both text and image (rare in WhatsApp, but if supported)
                elif 'text' in message and 'image' in message:
                    # Combine logic as needed
                    pass

        except Exception as e:
            print("Error processing message:", e)

        return "EVENT_RECEIVED", 200


def gemini_text_diagnose(text):
    headers = {"Content-Type": "application/json"}
    payload = {
        "prompt": {
            "text": f"Diagnose these symptoms and provide a detailed, professional medical response:\n{text}"
        },
        "temperature": 0.2,
        "maxOutputTokens": 512
    }
    response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", json=payload, headers=headers)
    if response.status_code != 200:
        return "Sorry, I'm unable to process your request right now."
    data = response.json()
    try:
        return data['candidates'][0]['output']
    except Exception:
        return "Sorry, I couldn't understand the symptoms."


def gemini_image_diagnose(image_base64):
    headers = {"Content-Type": "application/json"}
    payload = {
        "prompt": {
            "text": "Analyze this medical image and provide a detailed diagnosis or observation.",
            "image": {
                "mimeType": "image/jpeg",
                "data": image_base64
            }
        },
        "temperature": 0.2,
        "maxOutputTokens": 512
    }
    response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", json=payload, headers=headers)
    if response.status_code != 200:
        return "Sorry, I couldn’t analyze the image."
    data = response.json()
    try:
        return data['candidates'][0]['output']
    except Exception:
        return "Sorry, I couldn’t analyze the image."


def get_image_url(media_id):
    url = f"https://graph.facebook.com/v19.0/{media_id}"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to get image URL: {response.text}")
    return response.json()['url']


def download_and_encode_image(url):
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    image_response = requests.get(url, headers=headers)
    if image_response.status_code != 200:
        raise Exception(f"Failed to download image: {image_response.text}")
    return base64.b64encode(image_response.content).decode('utf-8')


def send_whatsapp_message(recipient_id, message):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_id,
        "type": "text",
        "text": {"body": message}
    }
    resp = requests.post(url, json=payload, headers=headers)
    if resp.status_code not in [200, 201]:
        print(f"Failed to send message: {resp.status_code}, {resp.text}")


if __name__ == "__main__":
    app.run(port=5000)
