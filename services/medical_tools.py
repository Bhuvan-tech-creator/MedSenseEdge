"""
Pure Data Tools for LangGraph Medical Agent System
Tools provide data only - LLM agent orchestrates and analyzes
"""
import json
from typing import Optional, Dict, Any, List
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from datetime import datetime
from models.user import get_user_profile, get_user_history, save_diagnosis_to_history, get_user_country, save_user_profile
from services.external_apis import get_endlessmedical_diagnosis, check_disease_outbreaks_for_user, find_nearby_clinics, reverse_geocode, pubmed_search, set_endlessmedical_features, analyze_endlessmedical_session
class LocationInput(BaseModel):
    """Input schema for location-based tools"""
    latitude: float = Field(description="User's latitude coordinate")
    longitude: float = Field(description="User's longitude coordinate") 
    radius_km: int = Field(default=5, description="Search radius in kilometers")
class UserProfileInput(BaseModel):
    """Input schema for user profile operations"""
    user_id: str = Field(description="User identifier")
    age: Optional[int] = Field(default=None, description="User's age")
    gender: Optional[str] = Field(default=None, description="User's gender")
    platform: Optional[str] = Field(default=None, description="Platform (whatsapp/telegram)")
class MedicalSearchInput(BaseModel):
    """Input schema for medical database search"""
    symptoms: str = Field(description="Symptoms to search for")
    age: Optional[int] = Field(default=None, description="Patient age")
    gender: Optional[str] = Field(default=None, description="Patient gender")
class WebSearchInput(BaseModel):
    """Input schema for web search"""
    query: str = Field(description="Search query")
    max_results: int = Field(default=5, description="Maximum number of results")
class DiagnosisInput(BaseModel):
    """Input schema for final diagnosis"""
    user_id: str = Field(description="User identifier")
    symptoms: str = Field(description="Patient symptoms")
    diagnosis: str = Field(description="Final diagnosis text")
    confidence: float = Field(description="Confidence level 0-1")
class MedicalFeatureInput(BaseModel):
    """Input schema for setting medical features"""
    features: Dict[str, str] = Field(description="Dictionary of medical features to set, e.g. {'Temp': '38.5', 'Headache': '1'}")
    age: Optional[int] = Field(default=None, description="Patient age")
    gender: Optional[str] = Field(default=None, description="Patient gender")
@tool("find_nearby_hospitals", args_schema=LocationInput)
def find_nearby_hospitals(latitude: float, longitude: float, radius_km: int = 5) -> str:
    """
    Find nearby hospitals and medical facilities using location coordinates.
    Returns JSON list of nearby medical facilities with names, distances, and coordinates.
    """
    print(f"🏥 TOOL CALLED: find_nearby_hospitals(lat={latitude}, lon={longitude}, radius={radius_km}km)")
    try:
        location_name = reverse_geocode(latitude, longitude)
        clinics = find_nearby_clinics(latitude, longitude, radius_km)
        result = {
            "location": location_name,
            "search_radius_km": radius_km,
            "facilities_found": len(clinics),
            "facilities": clinics
        }
        print(f"✅ TOOL RESULT: Found {len(clinics)} facilities near {location_name}")
        return json.dumps(result, indent=2)
    except Exception as e:
        print(f"❌ TOOL ERROR: find_nearby_hospitals failed - {str(e)}")
        return json.dumps({"error": str(e)})
@tool("set_medical_features", args_schema=MedicalFeatureInput)
def set_medical_features(features: Dict[str, str], age: Optional[int] = None, gender: Optional[str] = None) -> str:
    """
    Set specific medical features in EndlessMedical database for analysis.
    CORRECT EndlessMedical features you can set (from their API documentation):
    BASIC PATIENT INFO:
    - Age: '25' (patient age in years)
    - Gender: 'Male' or 'Female'
    - BMI: '24.5' (body mass index)
    FEVER & TEMPERATURE:
    - Temp: '38.5' (fever temperature in Celsius)
    - Chills: '1' (has chills)
    FATIGUE & GENERAL:
    - GeneralizedFatigue: '1' (has fatigue/tiredness)
    NAUSEA & VOMITING:
    - Nausea: '1' (has nausea)
    - Vomiting: '1' (has vomiting)
    HEADACHE:
    - HeadacheFrontal: '1' (frontal headache)
    - HeadacheTemporal: '1' (temporal headache)
    - HeadachePulsatile: '1' (pulsating headache)
    - HeadacheSqueezing: '1' (squeezing headache)
    - HeadacheIntensity: '1-10' (headache severity scale)
    - HeadacheAssociatedWithNausea: '1' (headache with nausea)
    CHEST PAIN:
    - ChestPainAnginaYesNo: '1' (has chest pain)
    - ChestPainSeverity: '1-10' (chest pain severity)
    - ChestPainQuality: 'sharp' or 'dull' or 'burning'
    - ChestPainAssociatedWithCough: '1' (chest pain with cough)
    STOMACH/ABDOMINAL PAIN:
    - StomachPainSeveritySx: '1-10' (stomach pain severity)
    - StomachPainEpigastricArea: '1' (upper stomach pain)
    - StomachPainPeriumbilicalArea: '1' (around navel pain)
    - RUQPain: '1' (right upper quadrant pain)
    - LUQPain: '1' (left upper quadrant pain)
    - RLQPain: '1' (right lower quadrant pain)
    - LLQPain: '1' (left lower quadrant pain)
    COUGH & BREATHING:
    - SeverityCough: '1-10' (cough severity)
    - AccessoryMuscles: '1' (using extra muscles to breathe)
    - DecreasedBreathSounds: '1' (reduced breath sounds)
    THROAT:
    - SoreThroatROS: '1' (has sore throat)
    - SwallowPain: '1' (pain when swallowing)
    PAIN (GENERAL):
    - JointsPain: '1' (joint pain)
    - BoneGenPain: '1' (general bone pain)
    - MuscleGenPain: '1' (general muscle pain)
    - BackPainRadPerineum: '1' (back pain radiating)
    - LowbackPain: '1' (lower back pain)
    - SpinePain: '1' (spine pain)
    DIZZINESS:
    - DizzinessWithExertion: '1' (dizzy with activity)
    - DizzinessWithPosition: '1' (dizzy when changing position)
    - OrthostaticLightheadedness: '1' (dizzy when standing)
    SKIN:
    - SkinErythemapapulesRashHx: '1' (has red bumpy rash)
    - SkinUrticariaRashHx: '1' (has hives/urticaria)
    - SkinHerpesRashHx: '1' (has herpes-type rash)
    Returns JSON with session results and features set.
    """
    print(f"🔬 TOOL CALLED: set_medical_features(features={list(features.keys())}, age={age}, gender={gender})")
    try:
        from services.external_apis import set_endlessmedical_features
        profile = {}
        if age:
            profile['age'] = age
            features['Age'] = str(age)
        if gender:
            profile['gender'] = gender
            features['Gender'] = gender.title()
        result = set_endlessmedical_features(features)
        if result and result.get('status') == 'success':
            print(f"✅ TOOL RESULT: Set {result.get('total_features', 0)} medical features successfully")
            return json.dumps({
                "status": "success",
                "features_set": result.get('features_set', []),
                "session_id": result.get('session_id'),
                "ready_for_analysis": True,
                "total_features": result.get('total_features', 0)
            }, indent=2)
        else:
            print(f"❌ TOOL ERROR: set_medical_features failed - {result.get('error') if result else 'Unknown error'}")
            return json.dumps({
                "status": "failed",
                "error": result.get('error') if result else "Unknown error",
                "features_attempted": list(features.keys())
            })
    except Exception as e:
        print(f"❌ TOOL ERROR: set_medical_features exception - {str(e)}")
        return json.dumps({"error": str(e)})
@tool("analyze_medical_features")  
def analyze_medical_features() -> str:
    """
    Analyze the medical features that were previously set using set_medical_features.
    This should be called AFTER set_medical_features to get the diagnosis.
    Returns JSON with possible conditions and probabilities from EndlessMedical database.
    """
    print(f"🧬 TOOL CALLED: analyze_medical_features()")
    try:
        result = analyze_endlessmedical_session()
        if result and result.get('status') == 'success':
            conditions_count = len(result.get('conditions', []))
            print(f"✅ TOOL RESULT: Found {conditions_count} potential conditions from EndlessMedical")
            return json.dumps({
                "status": "success", 
                "conditions": result.get('conditions', []),
                "database": "EndlessMedical (830+ medical conditions)",
                "analysis_date": result.get('date')
            }, indent=2)
        else:
            print(f"⚠️ TOOL RESULT: No conditions found in EndlessMedical database")
            return json.dumps({
                "status": "no_results",
                "message": "No specific conditions found in clinical database",
                "error": result.get('error') if result else None
            })
    except Exception as e:
        print(f"❌ TOOL ERROR: analyze_medical_features exception - {str(e)}")
        return json.dumps({"error": str(e)})
@tool("search_medical_database", args_schema=MedicalSearchInput)
def search_medical_database(symptoms: str, age: Optional[int] = None, gender: Optional[str] = None) -> str:
    """
    Search EndlessMedical clinical database for symptoms.
    IMPORTANT: This tool now works in coordination with set_medical_features and analyze_medical_features.
    For best results:
    1. First call set_medical_features with specific symptoms mapped to EndlessMedical features
    2. Then call analyze_medical_features to get the diagnosis
    3. This tool provides a simpler interface but may be less accurate
    Returns JSON with possible conditions, probabilities, and medical information.
    """
    print(f"🔍 TOOL CALLED: search_medical_database(symptoms='{symptoms[:50]}...', age={age}, gender={gender})")
    try:
        result = get_endlessmedical_diagnosis(symptoms, {'age': age, 'gender': gender} if age or gender else {})
        if result and result.get('status') == 'success':
            conditions_count = len(result.get('conditions', []))
            print(f"✅ TOOL RESULT: Found {conditions_count} conditions for symptoms: {symptoms[:30]}...")
            return json.dumps({
                "status": "success",
                "symptoms_analyzed": symptoms,
                "conditions": result.get('conditions', []),
                "database": "EndlessMedical (830+ medical conditions)",
                "analysis_date": result.get('date'),
                "note": "For more accurate results, use set_medical_features + analyze_medical_features"
            }, indent=2)
        else:
            print(f"⚠️ TOOL RESULT: No conditions found for symptoms: {symptoms[:30]}...")
            return json.dumps({
                "status": "no_results",
                "symptoms_analyzed": symptoms,
                "message": "No specific conditions found in clinical database. Try using set_medical_features for more precise symptom mapping."
            })
    except Exception as e:
        print(f"❌ TOOL ERROR: search_medical_database exception - {str(e)}")
        return json.dumps({"error": str(e)})
@tool("web_search_medical", args_schema=WebSearchInput)
def web_search_medical(query: str, max_results: int = 5) -> str:
    """
    Search PubMed for medical research articles and clinical information.
    Returns JSON with peer-reviewed medical literature from PubMed database.
    """
    print(f"📚 TOOL CALLED: web_search_medical(query='{query}', max_results={max_results})")
    try:
        results = pubmed_search(query, max_results)
        articles_found = len(results) if results else 0
        print(f"✅ TOOL RESULT: Found {articles_found} PubMed articles for query: {query}")
        return json.dumps({
            "query": query,
            "results_count": len(results),
            "search_results": results,
            "source": "PubMed E-utilities API",
            "description": "Peer-reviewed medical literature and research articles"
        }, indent=2)
    except Exception as e:
        print(f"❌ TOOL ERROR: web_search_medical exception - {str(e)}")
        return json.dumps({"error": str(e)})
@tool("get_user_profile", args_schema=UserProfileInput)
def get_user_profile_tool(user_id: str) -> str:
    """
    Retrieve user profile information from database.
    Returns JSON with user's age, gender, medical history, and platform.
    """
    print(f"👤 TOOL CALLED: get_user_profile(user_id={user_id})")
    try:
        profile = get_user_profile(user_id)
        history = get_user_history(user_id, days_back=365)
        country = get_user_country(user_id)
        history_count = len(history) if history else 0
        print(f"✅ TOOL RESULT: Retrieved profile for {user_id} - {history_count} history entries, country: {country or 'None'}")
        result = {
            "user_id": user_id,
            "profile": profile,
            "medical_history": history,
            "country": country,
            "history_entries": len(history) if history else 0
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        print(f"❌ TOOL ERROR: get_user_profile exception - {str(e)}")
        return json.dumps({"error": str(e)})
@tool("save_user_profile", args_schema=UserProfileInput)
def save_user_profile_tool(user_id: str, age: Optional[int] = None, gender: Optional[str] = None, platform: Optional[str] = None) -> str:
    """
    Save user profile information to database.
    Returns confirmation of saved profile data.
    """
    print(f"💾 TOOL CALLED: save_user_profile(user_id={user_id}, age={age}, gender={gender}, platform={platform})")
    try:
        save_user_profile(user_id, age, gender, platform)
        print(f"✅ TOOL RESULT: Saved profile for {user_id} - age: {age}, gender: {gender}")
        result = {
            "status": "success",
            "user_id": user_id,
            "saved_data": {
                "age": age,
                "gender": gender,
                "platform": platform
            }
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        print(f"❌ TOOL ERROR: save_user_profile exception - {str(e)}")
        return json.dumps({"error": str(e)})
class OutbreakCheckInput(BaseModel):
    """Input schema for disease outbreak checking"""
    user_id: str = Field(description="User identifier")
    country: Optional[str] = Field(default=None, description="User's country (if mentioned in conversation)")
    platform: Optional[str] = Field(default="unknown", description="Platform (whatsapp/telegram)")
@tool("check_disease_outbreaks", args_schema=OutbreakCheckInput)
def check_disease_outbreaks(user_id: str, country: Optional[str] = None, platform: Optional[str] = "unknown") -> str:
    """
    Check for disease outbreaks in user's location using WHO Disease Outbreak News API.
    If country is provided, saves it to database for future reference.
    Returns JSON with current outbreak information from WHO Disease Outbreak News.
    """
    print(f"🌍 TOOL CALLED: check_disease_outbreaks(user_id={user_id}, country={country}, platform={platform})")
    try:
        if country and country.strip():
            from models.user import save_user_country
            save_success = save_user_country(user_id, country.strip(), platform)
            if save_success:
                print(f"✅ COUNTRY SAVED: '{country}' saved for user {user_id}")
            else:
                print(f"⚠️ COUNTRY SAVE FAILED: Failed to save '{country}' for user {user_id}")
        outbreaks = check_disease_outbreaks_for_user(user_id)
        saved_country = get_user_country(user_id)
        outbreak_count = len(outbreaks) if outbreaks else 0
        print(f"✅ TOOL RESULT: Found {outbreak_count} outbreaks for {saved_country or 'unknown location'}")
        
        if not saved_country:
            return json.dumps({
                "status": "no_country",
                "message": "User location not set. Please mention your country to receive outbreak alerts.",
                "user_country": None,
                "outbreaks_found": 0,
                "outbreaks": [],
                "source": "WHO Disease Outbreak News"
            }, indent=2)
        result = {
            "status": "success",
            "user_country": saved_country,
            "outbreaks_found": len(outbreaks) if outbreaks else 0,
            "outbreaks": outbreaks or [],
            "source": "WHO Disease Outbreak News API",
            "last_checked": datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
        if outbreaks:
            result["alert_level"] = "active_outbreaks"
            result["message"] = f"Found {len(outbreaks)} active disease outbreak(s) relevant to {saved_country}. Please review the details below."
        else:
            result["alert_level"] = "no_outbreaks"
            result["message"] = f"No active disease outbreaks currently reported for {saved_country} in WHO Disease Outbreak News."
        return json.dumps(result, indent=2)
    except Exception as e:
        print(f"❌ TOOL ERROR: check_disease_outbreaks exception - {str(e)}")
        error_result = {
            "status": "error",
            "error": str(e),
            "user_country": get_user_country(user_id),
            "outbreaks_found": 0,
            "outbreaks": [],
            "source": "WHO Disease Outbreak News API",
            "message": "Error accessing WHO Disease Outbreak News. Please try again later."
        }
        return json.dumps(error_result, indent=2)
@tool("final_diagnosis", args_schema=DiagnosisInput)
def final_diagnosis(user_id: str, symptoms: str, diagnosis: str, confidence: float) -> str:
    """
    Save final diagnosis to user's medical history.
    Returns confirmation of saved diagnosis.
    """
    print(f"📋 TOOL CALLED: final_diagnosis(user_id={user_id}, symptoms='{symptoms[:50]}...', confidence={confidence})")
    try:
        profile = get_user_profile(user_id)
        platform = profile.get('platform', 'unknown') if profile else 'unknown'
        history_id = save_diagnosis_to_history(user_id, platform, symptoms, diagnosis)
        print(f"✅ TOOL RESULT: Saved diagnosis to history (ID: {history_id}) - symptoms: {symptoms[:30]}...")
        result = {
            "status": "diagnosis_saved",
            "user_id": user_id,
            "symptoms": symptoms,
            "diagnosis": diagnosis,
            "confidence": confidence,
            "saved_to_history": True,
            "history_id": history_id
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        print(f"❌ TOOL ERROR: final_diagnosis exception - {str(e)}")
        return json.dumps({"error": str(e)})
MEDICAL_TOOLS = [
    web_search_medical,
    find_nearby_hospitals,
    get_user_profile_tool,
    save_user_profile_tool,
    check_disease_outbreaks,
    final_diagnosis,
    search_medical_database,
] 
