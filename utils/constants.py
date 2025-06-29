"""Constants and messages used throughout the application"""

WELCOME_MSG = (
    "\U0001F44B Welcome to MedSense AI.\n"
    "Type your symptoms (e.g., 'I have fever and chills') or send an image from your camera or gallery.\n"
    "You can provide text, image, or both for the best analysis!\n"
    "📋 Type 'history' to see your past consultations\n"
    "📋 Type 'clear' to clear session data and start a new session\n"
    "\u26A0\ufe0f I'm an AI assistant, not a doctor. For emergencies, text EMERGENCY and visit a clinic."
)

PROFILE_SETUP_START_MSG = (
    "👋 Welcome to MedSense AI!\n\n"
    "To provide you with more accurate medical analysis, I'd like to know a bit about you.\n\n"
    "📅 Please tell me your age (or type 'skip' if you prefer not to share):"
)

EMERGENCY_MSG = "\ud83d\udea8 This may be urgent. Please visit a clinic immediately."

HELP_MSG = "Type your symptoms or send an image. You can provide text, image, or both. Say 'proceed' when ready for analysis!"

SESSION_CLEARED_MSG = "Session cleared. You can start fresh with new symptoms and images."

NO_HISTORY_MSG = "No medical history found."

NO_RECENT_DIAGNOSIS_MSG = "No recent diagnosis found to provide feedback for."

FEEDBACK_THANKS_MSG = "Thank you for your {feedback} feedback! 🙏\n\nFeel free to ask about new symptoms or type 'history' to see past consultations."

LOCATION_RECEIVED_MSG = "📍 Location received: {address}\n\nNow you can share your symptoms or send an image for analysis!"

IMAGE_ERROR_MSG = "Sorry, I couldn't download the image. Please try sending it again."

# Country detection keywords
COUNTRY_KEYWORDS = [
    'united states', 'usa', 'america', 'india', 'brazil', 'china', 'mexico', 
    'canada', 'australia', 'uk', 'england', 'france', 'germany', 'spain', 
    'italy', 'japan', 'korea', 'nigeria', 'south africa', 'egypt', 'pakistan', 
    'bangladesh', 'indonesia', 'philippines', 'vietnam', 'thailand', 'malaysia', 
    'singapore', 'turkey', 'iran', 'israel', 'saudi arabia', 'uae', 'qatar', 
    'kuwait', 'russia', 'ukraine', 'poland', 'netherlands', 'belgium', 
    'switzerland', 'sweden', 'norway', 'denmark', 'finland', 'argentina', 
    'chile', 'peru', 'colombia', 'venezuela'
]

# Fever detection keywords
FEVER_KEYWORDS = ['fever', 'hot', 'temperature', 'high temp']
COLD_KEYWORDS = ['chills', 'cold', 'shivering']
FATIGUE_KEYWORDS = ['tired', 'fatigue', 'weakness', 'weak']

# Symptom pattern keywords for validation messages
PAIN_KEYWORDS = ['pain', 'hurt', 'ache', 'sore']
SKIN_KEYWORDS = ['rash', 'skin', 'red', 'itch']
RESPIRATORY_KEYWORDS = ['cough', 'throat', 'respiratory']
DIGESTIVE_KEYWORDS = ['stomach', 'nausea', 'digestive', 'abdomen']


# Profile setup messages
PROFILE_AGE_PROMPT = "Please enter a valid age between 1 and 120, or type 'skip':"
PROFILE_GENDER_PROMPT = "👤 Thank you! Now please tell me your gender (Male/Female/Other) or type 'skip':"
PROFILE_GENDER_INVALID = "Please enter Male, Female, Other, or type 'skip':"

PROFILE_COMPLETE_WITH_GENDER = "✅ Thank you! Profile saved (Age: {age}, Gender: {gender}).\n\n💡 Tip: Mention your country anytime (e.g., 'United States', 'India') to receive disease outbreak alerts in your area.\n\n"

PROFILE_COMPLETE_NO_GENDER = "✅ Profile saved! You can now start using MedSense AI.\n\n💡 Tip: Mention your country anytime (e.g., 'United States', 'India') to receive disease outbreak alerts in your area.\n\n"

# Analysis response templates
TEXT_ONLY_TEMPLATE = "✅ I've recorded your symptoms: '{text}'{location}\n\n📸 Please send an image of the affected area for a complete analysis, or type 'proceed' if you only want text-based analysis.\n\nType 'clear' to start over or 'history' to see past consultations."

IMAGE_ONLY_TEMPLATE = "✅ I've received your image.{location}\n\n📝 Please describe your symptoms in text (e.g., 'I have pain and swelling'), or type 'proceed' if you only want image-based analysis.\n\nType 'clear' to start over or 'history' to see past consultations."

FEEDBACK_PROMPT = "\n\n💬 Please provide feedback on this diagnosis by replying 'good' or 'bad' to help improve our service.\n\n📍 Would you like to share your location to get nearby clinic recommendations?"

DEFAULT_SYMPTOMS_PROMPT = "Please describe your symptoms or send an image. You can provide text, image, or both! Type 'history' to see past consultations." 