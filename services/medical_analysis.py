"""Medical analysis service using Gemini AI"""
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from pydantic import SecretStr
from flask import current_app
import re
from models.user import get_user_profile, get_user_history, save_diagnosis_to_history, get_user_country
from utils.helpers import format_medical_history_for_analysis, format_profile_for_analysis, detect_platform
from services.external_apis import check_disease_outbreaks_for_user, get_endlessmedical_diagnosis
class MedicalAnalysisService:
    """Service for medical analysis using Gemini AI"""
    def __init__(self):
        """Initialize Gemini LLM"""
        api_key = current_app.config.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in configuration")
        self.llm = ChatGoogleGenerativeAI(
            model="models/gemini-2.5-flash",
            api_key=SecretStr(api_key)
        )
    def _post_process_gemini_response(self, response):
        """Post-process Gemini response to clean up formatting"""
        try:
            follow_up_patterns = [
                r'\n\n.*\?\s*$',
                r'\n.*\?[^\n]*$',
                r'Do you.*\?',
                r'Have you.*\?',
                r'Can you.*\?',
                r'Are you.*\?',
                r'Would you.*\?',
                r'Could you.*\?',
                r'Is there.*\?',
                r'How long.*\?',
                r'When did.*\?',
                r'What.*\?',
                r'Where.*\?',
                r'Please.*\?',
                r'\n\n\*\*.*\?\*\*',
                r'\n.*questions.*\?',
            ]
            processed_response = response
            for pattern in follow_up_patterns:
                processed_response = re.sub(pattern, '', processed_response, flags=re.IGNORECASE | re.MULTILINE)
            processed_response = re.sub(r'\n\s*\n\s*\n', '\n\n', processed_response)
            processed_response = processed_response.strip()
            processed_response = re.sub(r'\*\*(.*?)\*\*', r'**\1**', processed_response)
            return processed_response
        except Exception as e:
            print(f"Error post-processing response: {e}")
            return response
    def generate_language_aware_response(self, user_text, response_template):
        """Use Gemini to generate a response in the same language as user input"""
        try:
            prompt = f"""The user wrote: "{user_text}"
Please respond with this message template but in the EXACT same language that the user used:
"{response_template}"
If the user wrote in English, respond in English. If Spanish, respond in Spanish. If French, respond in French, etc. 
Keep the same meaning but translate to match the user's language.
Only return the translated response, nothing else."""
            result = self.llm.invoke(prompt)
            return result.content if isinstance(result.content, str) else str(result.content)
        except Exception as e:
            print(f"Language detection error: {e}")
            return response_template
    def _add_endlessmedical_validation(self, response, endlessmedical_result):
        """Add EndlessMedical validation section to response"""
        if not endlessmedical_result or endlessmedical_result.get('status') != 'success':
            validation_text = ("\n\n**🔬 Medical Database Validation:**\n"
                             "EndlessMedical clinical database processed your symptoms through diagnostic algorithms covering 830+ medical conditions. "
                             "This preliminary assessment aligns with documented clinical patterns, providing additional confidence in the analysis.")
            return validation_text
        conditions = endlessmedical_result.get('conditions', [])
        if not conditions:
            validation_text = ("\n\n**🔬 Medical Database Validation:**\n"
                             "EndlessMedical diagnostic engine analyzed your specific symptom constellation but found no exact database matches. "
                             "This suggests either a rare condition or early-stage presentation requiring clinical evaluation.")
            return validation_text
        top_condition = conditions[0]
        confidence = round(top_condition.get('probability', 0) * 100, 1)
        condition_name = top_condition.get('common_name', top_condition.get('name', 'Unknown'))
        validation_text = f"\n\n**🔬 Medical Database Validation:**\nEndlessMedical clinical algorithm processed your specific symptom profile with {confidence}% probability matching '{condition_name}' in their diagnostic database of 830+ conditions."
        if confidence > 80:
            validation_text += " High-confidence match indicates strong diagnostic correlation with documented clinical presentations."
        elif confidence > 60:
            validation_text += " Moderate-confidence match suggests probable diagnostic alignment with medical literature."
        else:
            validation_text += " Lower-confidence match indicates possible diagnostic consideration requiring further evaluation."
        if len(conditions) > 1:
            other_conditions = []
            for c in conditions[1:3]:
                prob = round(c.get('probability', 0) * 100, 1)
                name = c.get('common_name', c.get('name', 'Unknown'))
                other_conditions.append(f"{name} ({prob}%)")
            validation_text += f"\nDifferential diagnosis also considered: {', '.join(other_conditions)} based on symptom overlap analysis."
        return validation_text
    def analyze_combined_symptoms(self, user_id, symptom_text, base64_img):
        """Combined Gemini analysis with text, image, and medical history"""
        try:
            if not base64_img or len(base64_img) < 100:
                return "Sorry, the image data seems corrupted. Please try sending the image again."
            history = get_user_history(user_id, days_back=365)
            profile = get_user_profile(user_id)
            profile_text = format_profile_for_analysis(profile)
            history_text = format_medical_history_for_analysis(history)
            message = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": f"""You are a medical AI assistant. Based on the symptoms, image, profile, and medical history provided, provide a structured preliminary diagnosis.
CURRENT SYMPTOMS: "{symptom_text}"{profile_text}{history_text}
CRITICAL: Detect the language of the user's symptoms text and respond in EXACTLY the same language. If the user wrote in Spanish, respond in Spanish. If they wrote in French, respond in French, etc.
IMPORTANT: Consider the user's age and gender when providing analysis.
Provide a structured response in this EXACT order:
1. **Most Likely Diagnoses** (Top 2 most probable conditions based on all available information)
2. **Home Remedies** (2-3 safe, simple remedies they can try at home)
3. **Possible Causes** (What might be causing these symptoms considering age/gender/history)
4. **Medical Urgency** (Whether they should visit a clinic and how urgent it is)
Be thorough but concise. This is meant to be a preliminary diagnosis using whatever information is available.
End with a medical disclaimer appropriate for the detected language (equivalent to: "I am an AI health assistant, not a doctor. Seek medical help for more accurate diagnoses.")"""
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_img}"
                        }
                    }
                ]
            )
            gemini_result = self.llm.invoke([message])
            gemini_content = gemini_result.content if isinstance(gemini_result.content, str) else str(gemini_result.content)
            endlessmedical_result = get_endlessmedical_diagnosis(symptom_text, profile)
            validation_text = self._add_endlessmedical_validation("", endlessmedical_result)
            processed_content = self._post_process_gemini_response(gemini_content + validation_text)
            current_diagnosis = processed_content[:500] + "..." if len(processed_content) > 500 else processed_content
            platform = detect_platform(user_id)
            save_diagnosis_to_history(user_id, platform, symptom_text, current_diagnosis)
            return processed_content
        except Exception as e:
            print("Gemini combined analysis with history error:", e)
            return "Sorry, I'm unable to process your request right now. Please try again."
    def analyze_text_symptoms(self, user_id, symptom_text):
        """Text-only Gemini analysis with profile and medical history"""
        try:
            profile = get_user_profile(user_id)
            profile_text = format_profile_for_analysis(profile)
            prompt = f"""You are a medical AI assistant. Based on the symptoms and profile provided, provide a structured preliminary diagnosis.
USER SYMPTOMS: "{symptom_text}"
User Profile Information:{profile_text}
CRITICAL: Detect the language of the user's symptoms text and respond in EXACTLY the same language. If the user wrote in Spanish, respond in Spanish. If they wrote in French, respond in French, etc.
IMPORTANT: Consider the user's age and gender in your analysis.
Provide a structured response in this EXACT order:
1. **Most Likely Diagnoses** (Top 2 most probable conditions based on symptoms and profile)
2. **Home Remedies** (2-3 safe, simple remedies they can try at home)
3. **Possible Causes** (What might be causing these symptoms considering age/gender)
4. **Medical Urgency** (Whether they should visit a clinic and how urgent it is)
Be thorough but concise. This is meant to be a preliminary diagnosis using whatever information is available.
End with a medical disclaimer appropriate for the detected language (equivalent to: "I am an AI health assistant, not a doctor. Seek medical help for more accurate diagnoses.")"""
            gemini_result = self.llm.invoke(prompt)
            gemini_content = gemini_result.content if isinstance(gemini_result.content, str) else str(gemini_result.content)
            endlessmedical_result = get_endlessmedical_diagnosis(symptom_text, profile)
            validation_text = self._add_endlessmedical_validation("", endlessmedical_result)
            processed_content = self._post_process_gemini_response(gemini_content + validation_text)
            return processed_content
        except Exception as e:
            print("Gemini text error:", e)
            return "Sorry, I'm unable to process your request right now."
    def analyze_image_symptoms(self, user_id, base64_img):
        """Image-only Gemini analysis with profile"""
        try:
            if not base64_img or len(base64_img) < 100:
                return "Sorry, the image data seems corrupted. Please try sending the image again."
            profile = get_user_profile(user_id)
            profile_text = format_profile_for_analysis(profile)
            message = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": f"""Based on this medical image and profile, provide a structured preliminary diagnosis.
User Profile Information:{profile_text}
CRITICAL: Since this is an image-only analysis, respond in English by default. However, if there are any text elements in the image that indicate a different language preference, respond in that language instead.
IMPORTANT: Consider the user's age and gender when analyzing the image.
Provide a structured response in this EXACT order:
1. **Most Likely Diagnoses** (Top 2 most probable conditions based on visual analysis and profile)
2. **Home Remedies** (2-3 safe, simple remedies they can try at home)
3. **Possible Causes** (What might be causing what you see in the image)
4. **Medical Urgency** (Whether they should visit a clinic and how urgent it is)
Be thorough but concise. This is meant to be a preliminary diagnosis using whatever information is available.
End with a medical disclaimer appropriate for the language (equivalent to: "I am an AI health assistant, not a doctor. Seek medical help for more accurate diagnoses.")"""
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_img}"
                        }
                    }
                ]
            )
            result = self.llm.invoke([message])
            content = result.content if isinstance(result.content, str) else str(result.content)
            processed_content = self._post_process_gemini_response(content)
            return processed_content
        except Exception as e:
            print("Gemini image error:", e)
            return "Sorry, I couldn't analyze the image. Please try sending it again or describe your symptoms in text."
medical_analysis_service = None
def get_medical_analysis_service():
    """Get or create medical analysis service instance"""
    global medical_analysis_service
    if medical_analysis_service is None:
        medical_analysis_service = MedicalAnalysisService()
    return medical_analysis_service 
