"""
Pure Data Tools for LangGraph Medical Agent System
Tools provide data only - LLM agent orchestrates and analyzes
"""

import json
from typing import Optional, Dict, Any, List
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from models.user import get_user_profile, get_user_history, save_diagnosis_to_history, get_user_country, save_user_profile
from services.external_apis import get_endlessmedical_diagnosis, check_disease_outbreaks_for_user, find_nearby_clinics, reverse_geocode, duckduckgo_search


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


@tool("find_nearby_hospitals", args_schema=LocationInput)
def find_nearby_hospitals(latitude: float, longitude: float, radius_km: int = 5) -> str:
    """
    Find nearby hospitals and medical facilities using location coordinates.
    Returns JSON list of nearby medical facilities with names, distances, and coordinates.
    """
    try:
        # Get location name for context
        location_name = reverse_geocode(latitude, longitude)
        
        # Find nearby medical facilities
        clinics = find_nearby_clinics(latitude, longitude, radius_km)
        
        result = {
            "location": location_name,
            "search_radius_km": radius_km,
            "facilities_found": len(clinics),
            "facilities": clinics
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool("search_medical_database", args_schema=MedicalSearchInput)
def search_medical_database(symptoms: str, age: Optional[int] = None, gender: Optional[str] = None) -> str:
    """
    Search EndlessMedical clinical database for symptoms.
    Returns JSON with possible conditions, probabilities, and medical information.
    """
    try:
        # Prepare user profile for EndlessMedical
        profile = {}
        if age:
            profile['age'] = age
        if gender:
            profile['gender'] = gender
            
        # Get diagnosis from EndlessMedical
        result = get_endlessmedical_diagnosis(symptoms, profile)
        
        if result and result.get('status') == 'success':
            return json.dumps({
                "status": "success",
                "symptoms_analyzed": symptoms,
                "conditions": result.get('conditions', []),
                "database": "EndlessMedical (830+ medical conditions)",
                "analysis_date": result.get('date')
            }, indent=2)
        else:
            return json.dumps({
                "status": "no_results",
                "symptoms_analyzed": symptoms,
                "message": "No specific conditions found in clinical database"
            })
            
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool("web_search_medical", args_schema=WebSearchInput)
def web_search_medical(query: str, max_results: int = 5) -> str:
    """
    Search the web for medical information and research.
    Returns JSON with search results from medical sources.
    """
    try:
        # Enhanced medical query
        medical_query = f"medical research treatment {query} symptoms diagnosis"
        
        # Perform web search
        results = duckduckgo_search(medical_query, max_results)
        
        return json.dumps({
            "query": query,
            "results_count": len(results),
            "search_results": results
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool("get_user_profile", args_schema=UserProfileInput)
def get_user_profile_tool(user_id: str) -> str:
    """
    Retrieve user profile information from database.
    Returns JSON with user's age, gender, medical history, and platform.
    """
    try:
        # Get user profile
        profile = get_user_profile(user_id)
        
        # Get user history
        history = get_user_history(user_id, days_back=365)
        
        # Get user country
        country = get_user_country(user_id)
        
        result = {
            "user_id": user_id,
            "profile": profile,
            "medical_history": history,
            "country": country,
            "history_entries": len(history) if history else 0
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool("save_user_profile", args_schema=UserProfileInput)
def save_user_profile_tool(user_id: str, age: Optional[int] = None, gender: Optional[str] = None, platform: Optional[str] = None) -> str:
    """
    Save user profile information to database.
    Returns confirmation of saved profile data.
    """
    try:
        # Save profile to database
        save_user_profile(user_id, age, gender, platform)
        
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
        return json.dumps({"error": str(e)})


@tool("check_disease_outbreaks", args_schema=UserProfileInput)
def check_disease_outbreaks(user_id: str) -> str:
    """
    Check for disease outbreaks in user's location.
    Returns JSON with current outbreak information from WHO.
    """
    try:
        # Get outbreaks for user location
        outbreaks = check_disease_outbreaks_for_user(user_id)
        
        # Get user country for context
        country = get_user_country(user_id)
        
        result = {
            "user_country": country,
            "outbreaks_found": len(outbreaks) if outbreaks else 0,
            "outbreaks": outbreaks or [],
            "source": "WHO Disease Outbreak News"
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool("final_diagnosis", args_schema=DiagnosisInput)
def final_diagnosis(user_id: str, symptoms: str, diagnosis: str, confidence: float) -> str:
    """
    Save final diagnosis to user's medical history.
    Returns confirmation of saved diagnosis.
    """
    try:
        # Get user platform for saving
        profile = get_user_profile(user_id)
        platform = profile.get('platform', 'unknown') if profile else 'unknown'
        
        # Save diagnosis to history
        save_diagnosis_to_history(user_id, platform, symptoms, diagnosis)
        
        result = {
            "status": "diagnosis_saved",
            "user_id": user_id,
            "symptoms": symptoms,
            "diagnosis": diagnosis,
            "confidence": confidence,
            "saved_to_history": True
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})


# Export pure data tools for LangGraph agent
MEDICAL_TOOLS = [
    find_nearby_hospitals,
    search_medical_database,
    web_search_medical,
    get_user_profile_tool,
    save_user_profile_tool,
    check_disease_outbreaks,
    final_diagnosis
] 