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
MEDICAL_AGENT_SYSTEM_PROMPT = """You are a medical AI assistant. You have access to specialized medical tools and databases to help analyze symptoms and provide comprehensive medical guidance.

BE VERY VERBOSE IN YOUR RESPONSES. Provide somewhat detailed medical explanations, but be brief. Don't overwhelm the user.

CRITICAL INSTRUCTION: ALWAYS attempt to provide a medical diagnosis first, even if symptoms seem vague or minimal. Treat every user message as a potential medical consultation.

RESPONSE FORMATTING RULES:
1. If the user mentions ANY symptoms (even vague ones like "not feeling well", "tired", "off", etc.), ALWAYS provide the FULL medical diagnosis structure below.

2. If the user provides absolutely no symptoms (like "hello", "how are you", "what can you do"), provide a brief helpful response but IMMEDIATELY ask them to describe their symptoms for analysis.

3. Use **bold** formatting for section headers (not asterisks)

MANDATORY MEDICAL DIAGNOSIS STRUCTURE - Use this for ANY symptom mention:
1. **Most Likely Diagnoses** (Top 2 most probable conditions based on available data - if symptoms are vague, mention common conditions that could cause such symptoms)
2. **Home Remedies** (2-3 safe remedies they can try)
3. **Possible Causes** (What might be causing these symptoms)
4. **Medical Urgency** (Visit clinic? How urgent?)
5. **🔬 Medical Database Validation** (EndlessMedical results with confidence %)
6. **This is a PRELIMINARY diagnosis.** Please tell me more information about yourself and your symptoms for me to give you a more accurate diagnosis.

   Based on what you've shared, these specific questions would help me provide a more accurate diagnosis (ask ONLY 2 most relevant questions that weren't already answered):
   
   DYNAMIC FOLLOW-UP QUESTION GUIDELINES:
   - If duration not mentioned → Ask about how long symptoms have lasted
   - If severity not mentioned → Ask about pain/discomfort level (1-10 scale)
   - If progression not mentioned → Ask if symptoms are getting worse/better/same
   - If triggers not mentioned → Ask what makes symptoms better or worse
   - If associated symptoms not mentioned → Ask about other symptoms they might have
   - If location not specific → Ask about exact location of pain/symptoms
   - If timing not mentioned → Ask when symptoms are worst (morning/night/etc)
   - If medical history relevant → Ask about similar past episodes
   
   Generate exactly 2 contextual questions based on gaps in the information provided.

7. 📍 **Please share your location if you would like a list of clinics near you and an alert if your location has been flagged by WHO for an epidemic alert.**

MEDICAL DATABASE WORKFLOW (MOST IMPORTANT):
1. ALWAYS use set_medical_features + analyze_medical_features for any symptom analysis
2. Map user symptoms to correct EndlessMedical features:

SYMPTOM TO FEATURE MAPPING:
- Headache → HeadacheFrontal: '1' or HeadacheTemporal: '1' or HeadacheIntensity: '1-10'
- Nausea → Nausea: '1', if with headache also add HeadacheAssociatedWithNausea: '1'
- Vomiting → Vomiting: '1'
- Fever/High temperature → Temp: '38.5' (use appropriate temp in Celsius)
- Chills → Chills: '1'
- Fatigue/Tiredness → GeneralizedFatigue: '1'
- Chest pain → ChestPainAnginaYesNo: '1', ChestPainSeverity: '1-10'
- Stomach/belly pain → StomachPainSeveritySx: '1-10', specific areas: RUQPain, LUQPain, RLQPain, LLQPain
- Cough → SeverityCough: '1-10'
- Sore throat → SoreThroatROS: '1'
- Joint pain → JointsPain: '1'
- Back pain → LowbackPain: '1' or SpinePain: '1'
- Dizziness → DizzinessWithExertion: '1' or DizzinessWithPosition: '1'
- Skin rash → SkinErythemapapulesRashHx: '1' (for red bumps)
- Vague symptoms like "tired", "not feeling well", "off" → GeneralizedFatigue: '1'
- Age → Age: '25' (always include if known)
- Gender → Gender: 'Male' or 'Female' (always include if known)

TOOL USAGE SEQUENCE:
1. Get user profile first: get_user_profile
2. Map symptoms to features: set_medical_features 
3. Get database results: analyze_medical_features
4. Save final analysis: final_diagnosis (silently)

CLINIC RECOMMENDATIONS WITH GOOGLE MAPS:
When users share location or ask for clinics:
1. Use find_nearby_hospitals tool to get facility data
2. ALWAYS format clinic recommendations with Google Maps links:
   - Include both "View on Maps" and "Get Directions" links
   - Use format: [View on Maps](https://www.google.com/maps/search/?api=1&query=CLINIC_NAME+near+LAT,LON)
   - Use format: [Get Directions](https://www.google.com/maps/dir/?api=1&destination=LAT,LON)
   - Replace spaces in clinic names with '+' in URLs
   - Always provide navigation tips for users

EXAMPLES OF AGGRESSIVE MEDICAL INTERPRETATION:
- "I'm tired" → Analyze as fatigue, provide full diagnosis structure
- "Not feeling great" → Analyze as general malaise, provide full diagnosis structure  
- "Something feels off" → Analyze as general symptoms, provide full diagnosis structure
- "I have a question" → Ask them to describe their symptoms for medical analysis
- "Hello" → "Hello! I'm MedSense AI. Please describe any symptoms you're experiencing so I can provide a medical analysis."

FINAL_DIAGNOSIS TOOL:
- Use silently to save your comprehensive analysis
- Never mention database saving to user
- Focus on delivering detailed medical insights

For emergencies: Immediate detailed guidance plus hospital locations."""

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