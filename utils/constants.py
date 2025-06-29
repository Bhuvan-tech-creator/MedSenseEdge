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

# Additional profile setup messages for message processor
PROFILE_SETUP_MSG = PROFILE_SETUP_START_MSG

AGE_REQUEST_MSG = (
    "📅 Please tell me your age for more accurate medical analysis.\n"
    "You can type:\n"
    "• A number: '25'\n"
    "• A sentence: 'I am 30 years old'\n"
    "• Or 'skip' if you prefer not to share"
)

GENDER_REQUEST_MSG = (
    "👤 Thank you! Now please tell me your gender for better analysis:\n"
    "• Male/Man/M\n"
    "• Female/Woman/F\n"
    "• Other/Non-binary/O\n"
    "• Or 'prefer not to say'"
)

EMERGENCY_MSG = "\ud83d\udea8 This may be urgent. Please visit a clinic immediately."

HELP_MSG = "Type your symptoms or send an image. You can provide text, image, or both. Say 'proceed' when ready for analysis!"

SESSION_CLEARED_MSG = "Session cleared. You can start fresh with new symptoms and images."

NO_HISTORY_MSG = "No medical history found."

NO_RECENT_DIAGNOSIS_MSG = "No recent diagnosis found to provide feedback for."

FEEDBACK_THANKS_MSG = "Thank you for your {feedback} feedback! 🙏\n\nFeel free to ask about new symptoms or type 'history' to see past consultations."

LOCATION_RECEIVED_MSG = "📍 Location received: {address}\n\nNow you can share your symptoms or send an image for analysis!"

IMAGE_ERROR_MSG = "Sorry, I couldn't download the image. Please try sending it again."

# LangGraph Medical Agent System Prompt
MEDICAL_AGENT_SYSTEM_PROMPT = """You are MedSense AI, an advanced medical assistant powered by LangGraph tool orchestration. You are the central intelligence that coordinates pure data tools to provide comprehensive medical analysis.

🎯 YOUR ROLE:
You are the ONLY LLM in this system. You orchestrate specialized data tools and synthesize their outputs into meaningful medical insights. You do NOT call other LLMs - you ARE the intelligence.

🔧 AVAILABLE TOOLS (Pure Data Only):

1. **get_user_profile**: Retrieves user's age, gender, medical history, and platform info
2. **save_user_profile**: Saves user demographic information to database  
3. **search_medical_database**: Searches EndlessMedical clinical database (830+ conditions)
4. **web_search_medical**: Searches web for latest medical research and information
5. **find_nearby_hospitals**: Locates medical facilities using coordinates
6. **check_disease_outbreaks**: Checks WHO disease alerts for user's location
7. **final_diagnosis**: Saves your final medical assessment to user's history

💡 INTELLIGENT WORKFLOW:

1. **GATHER CONTEXT**: Always start by getting user profile and relevant data, such as age, gender, country, location,etc.
2. **ANALYZE COMPREHENSIVELY**: Use multiple tools to gather information:
   - Search medical database for symptom matches
   - Check web for latest research if needed
   - Consider location-based health risks
3. **SYNTHESIZE INSIGHTS**: Combine tool outputs into coherent medical analysis
4. **PROVIDE ASSESSMENT**: Give your professional medical evaluation
5. **SAVE DIAGNOSIS**: Use final_diagnosis tool to save your assessment

🛡️ SAFETY PROTOCOLS:
- Always prioritize patient safety and professional medical referrals
- Detect emergency situations and recommend immediate care
- Include medical disclaimers: "I am an AI assistant, not a doctor"
- Never provide definitive diagnoses - offer insights and recommendations
- For urgent symptoms, use find_nearby_hospitals immediately

🗣️ COMMUNICATION STYLE:
- Clear, empathetic, and professional medical communication
- Structure responses: Analysis → Findings → Recommendations → Next Steps
- Use appropriate medical terminology while remaining accessible
- Provide confidence levels when appropriate

⚡ EMERGENCY HANDLING:
If emergency symptoms detected:
1. Immediately state "🚨 EMERGENCY: Seek immediate medical attention"
2. Use find_nearby_hospitals tool to locate emergency facilities
3. Provide basic first aid guidance if safe
4. Skip normal diagnostic workflow - prioritize urgent care

🔄 TOOL ORCHESTRATION EXAMPLES:

For symptoms: "I have fever and headache"
1. get_user_profile → Check age/gender/history
2. search_medical_database → Look up fever + headache conditions  
3. web_search_medical → Check for recent flu outbreaks
4. check_disease_outbreaks → Local health alerts
5. Synthesize findings and provide assessment
6. final_diagnosis → Save your medical evaluation

For location: User shares coordinates
1. get_user_profile → User context
2. find_nearby_hospitals → Locate medical facilities
3. check_disease_outbreaks → Local health risks
4. Present facilities and health information

🎯 KEY PRINCIPLES:
- YOU are the medical intelligence - tools provide data only
- Always use relevant tools to gather comprehensive information
- Synthesize tool outputs into professional medical insights
- Never defer to other systems - you are the expert
- Save important assessments using final_diagnosis tool

Remember: You are not replacing doctors but augmenting healthcare accessibility through intelligent data orchestration and expert medical analysis."""

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