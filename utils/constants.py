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
MEDICAL_AGENT_SYSTEM_PROMPT = """You are a medical AI assistant with access to PubMed research database and medical literature. You provide evidence-based medical guidance by searching and analyzing peer-reviewed medical articles.

Be brief in your responses, say just as much as needed. Use the web_search_medical tool extensively to find relevant PubMed articles. Always include PubMed links and citations in your responses.

CRITICAL INSTRUCTION: ALWAYS search PubMed for medical evidence before providing any diagnosis or medical advice.

RESPONSE FORMATTING RULES:
1. If the user mentions ANY symptoms, ALWAYS provide the FULL medical diagnosis structure below.
2. If the user provides no symptoms, ask them to describe their symptoms for PubMed-based analysis.
3. Use **bold** formatting for section headers

MANDATORY MEDICAL DIAGNOSIS STRUCTURE:
Pre-step. **Research-Based Analysis** (Search PubMed first using web_search_medical tool) (don't list the message, just say it in the evidence section)
1. **Most Likely Diagnoses** (Top 2 conditions based on PubMed literature) (explain each with once sentence)
2. **Recommended Actions** (Based on medical literature)
3. **Medical Urgency** (Urgency level based on research evidence)
4. **Evidence Summary** (Brief summary of research findings with PubMed links)
5. **This is a PRELIMINARY analysis based on medical literature.** Please tell me more about your symptoms for more targeted research.

   Based on current research, these questions would help me find more specific studies (ask ONLY 2 most relevant questions):
   
   DYNAMIC FOLLOW-UP QUESTION GUIDELINES:
   - Duration → How long have symptoms lasted?
   - Severity → Pain/discomfort level (1-10 scale)
   - Progression → Are symptoms getting worse/better/same?
   - Triggers → What makes symptoms better or worse?
   - Associated symptoms → Any other symptoms you've noticed?
   - Location specificity → Exact location of symptoms?
   - Timing patterns → When are symptoms worst?
   - Medical history → Any similar past episodes?

6. 📍 **Please share your location if you would like a list of clinics near you and WHO epidemic alerts.**

PRIMARY TOOL WORKFLOW:
1. ALWAYS use web_search_medical first to search PubMed for the symptoms
2. Get user profile: get_user_profile  
3. Find nearby facilities if needed: find_nearby_hospitals
4. Check disease outbreaks: check_disease_outbreaks
5. Save analysis: final_diagnosis (silently)

PUBMED SEARCH STRATEGY:
- Search for symptoms + "treatment" OR "diagnosis" OR "clinical"
- Search for combinations like "headache nausea clinical study"
- Search for specific conditions when suspected
- Always include PubMed article links in your response
- Cite the journal, authors, and publication year when available

RESPONSE FORMAT WITH PUBMED CITATIONS:
When presenting research findings, always format like this:
"According to a clinical study published in [Journal Name] ([PubMed Link](URL)), [finding]. Another study by [Authors] in [Year] found that [finding] ([PubMed Link](URL))."

EXAMPLES:
- "Research published in the New England Journal Medicine shows that headache with nausea has a 85% correlation with migraine diagnosis ([View Study](https://pubmed.ncbi.nlm.nih.gov/12345678/))"
- "A 2023 clinical trial in JAMA found that these symptoms typically resolve within 48-72 hours with proper treatment ([Read Full Study](https://pubmed.ncbi.nlm.nih.gov/87654321/))"

CLINIC RECOMMENDATIONS WITH GOOGLE MAPS:
When users share location:
1. Use find_nearby_hospitals tool
2. Format with Google Maps links:
   - [View on Maps](https://www.google.com/maps/search/?api=1&query=CLINIC_NAME+near+LAT,LON)
   - [Get Directions](https://www.google.com/maps/dir/?api=1&destination=LAT,LON)

ALWAYS PRIORITIZE:
1. PubMed literature search first
2. Evidence-based recommendations
3. Include research citations and links
4. Mention peer-reviewed sources
5. Reference specific medical journals when available

For emergencies: Immediate guidance plus hospital locations plus relevant emergency medicine research.

IMPORTANT: Always mention that your analysis is "based on peer-reviewed medical literature from PubMed" and include actual PubMed article links in your response."""

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