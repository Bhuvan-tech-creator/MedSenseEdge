"""External API integrations for medical services"""

import requests
import time
from flask import current_app
from utils.helpers import calculate_distance
from models.user import get_user_country
from duckduckgo_search import DDGS

# Simple session cache for EndlessMedical
_endlessmedical_session = {"session_id": None, "initialized": False}


def duckduckgo_search(query, max_results=5):
    """Search DuckDuckGo for medical information"""
    try:
        with DDGS() as ddgs:
            results = []
            search_results = ddgs.text(query, max_results=max_results)
            
            for result in search_results:
                results.append({
                    'title': result.get('title', ''),
                    'body': result.get('body', ''),
                    'href': result.get('href', ''),
                    'source': 'DuckDuckGo'
                })
            
            return results
            
    except Exception as e:
        print(f"Error in DuckDuckGo search: {e}")
        return [{"error": f"Search failed: {str(e)}"}]


def reverse_geocode(latitude, longitude):
    """Convert coordinates to human-readable address using Nominatim"""
    try:
        nominatim_url = current_app.config.get('NOMINATIM_API_URL')
        user_agent = current_app.config.get('NOMINATIM_USER_AGENT')
        
        url = f"{nominatim_url}/reverse"
        params = {
            'lat': latitude,
            'lon': longitude,
            'format': 'json',
            'addressdetails': 1
        }
        headers = {'User-Agent': user_agent}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        time.sleep(1)  # Rate limiting for Nominatim
        
        if response.status_code == 200:
            data = response.json()
            if 'display_name' in data:
                return data['display_name']
        return f"Location: {latitude:.4f}, {longitude:.4f}"
    except Exception as e:
        print(f"Error in reverse geocoding: {e}")
        return f"Location: {latitude:.4f}, {longitude:.4f}"


def find_nearby_clinics(latitude, longitude, radius_km=5):
    """Find nearby medical facilities using Overpass API"""
    try:
        overpass_url = current_app.config.get('OVERPASS_API_URL')
        
        # Overpass QL query to find hospitals, clinics, and pharmacies
        overpass_query = f"""
        [out:json][timeout:25];
        (
          node["amenity"~"^(hospital|clinic|doctors|pharmacy)$"](around:{radius_km*1000},{latitude},{longitude});
          way["amenity"~"^(hospital|clinic|doctors|pharmacy)$"](around:{radius_km*1000},{latitude},{longitude});
          relation["amenity"~"^(hospital|clinic|doctors|pharmacy)$"](around:{radius_km*1000},{latitude},{longitude});
        );
        out center meta;
        """
        
        response = requests.post(overpass_url, data=overpass_query, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            clinics = []
            
            for element in data.get('elements', [])[:5]:  # Limit to 5 closest
                if 'tags' in element:
                    name = element['tags'].get('name', 'Medical Facility')
                    amenity = element['tags'].get('amenity', 'clinic')
                    
                    # Get coordinates
                    if element['type'] == 'node':
                        lat, lon = element['lat'], element['lon']
                    elif 'center' in element:
                        lat, lon = element['center']['lat'], element['center']['lon']
                    else:
                        continue
                    
                    # Calculate approximate distance
                    distance = calculate_distance(latitude, longitude, lat, lon)
                    
                    clinics.append({
                        'name': name,
                        'type': amenity,
                        'distance': round(distance, 2),
                        'lat': lat,
                        'lon': lon
                    })
            
            # Sort by distance
            clinics.sort(key=lambda x: x['distance'])
            return clinics[:3]  # Return top 3 closest
        
        return []
    except Exception as e:
        print(f"Error finding nearby clinics: {e}")
        return []


def fetch_who_disease_outbreaks():
    """Fetch current disease outbreaks from WHO"""
    try:
        who_url = current_app.config.get('WHO_DON_API_URL')
        response = requests.get(who_url, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"WHO API returned status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching WHO disease outbreaks: {e}")
        return None


def check_disease_outbreaks_for_user(user_id):
    """Check for disease outbreaks in user's country"""
    user_country = get_user_country(user_id)
    if not user_country:
        return []
    
    outbreaks = fetch_who_disease_outbreaks()
    if not outbreaks:
        return []
    
    relevant_outbreaks = []
    for event in outbreaks.get('events', []):
        if user_country.lower() in event.get('location', '').lower():
            relevant_outbreaks.append({
                'disease': event.get('disease', 'Unknown'),
                'location': event.get('location', ''),
                'date': event.get('date_published', ''),
                'summary': event.get('summary', '')[:200] + '...' if len(event.get('summary', '')) > 200 else event.get('summary', '')
            })
    
    return relevant_outbreaks


def initialize_endlessmedical():
    """DEPRECATED - Use set_endlessmedical_features instead"""
    print("⚠️ WARNING: initialize_endlessmedical is deprecated. Use RapidAPI functions instead.")
    return False


def get_endlessmedical_diagnosis(symptoms_text, user_profile):
    """DEPRECATED - Use set_endlessmedical_features + analyze_endlessmedical_session instead"""
    print("⚠️ WARNING: get_endlessmedical_diagnosis is deprecated. Using RapidAPI functions instead.")
    
    # Redirect to new implementation
    try:
        # Map common symptoms to features
        features = {}
        symptoms_lower = symptoms_text.lower()
        
        # Age from profile
        if user_profile and user_profile.get('age'):
            features['Age'] = str(user_profile.get('age'))
        else:
            features['Age'] = '30'  # Default age
            
        # Map symptoms to features
        if 'headache' in symptoms_lower:
            features['HeadacheFrontal'] = '1'
        if 'fever' in symptoms_lower:
            features['Temp'] = '38.5'
        if 'tired' in symptoms_lower or 'fatigue' in symptoms_lower:
            features['GeneralizedFatigue'] = '1'
        if 'nausea' in symptoms_lower:
            features['Nausea'] = '1'
        if 'hand' in symptoms_lower and ('hurt' in symptoms_lower or 'pain' in symptoms_lower):
            features['JointsPain'] = '1'
            features['MuscleGenPain'] = '1'
            
        # Use new RapidAPI functions
        set_result = set_endlessmedical_features(features)
        if set_result.get('status') == 'success':
            return analyze_endlessmedical_session()
        else:
            return None
            
    except Exception as e:
        print(f"Error in deprecated function redirect: {e}")
        return None


def set_endlessmedical_features(features_dict):
    """
    Set medical features in EndlessMedical session via RapidAPI (secure)
    This allows the LLM to specify exactly which features to set
    """
    global _endlessmedical_session
    
    try:
        # RapidAPI configuration
        rapidapi_key = current_app.config.get('RAPIDAPI_KEY')
        if not rapidapi_key:
            return {"status": "error", "error": "RAPIDAPI_KEY not found in configuration"}
        
        rapidapi_host = "endlessmedicalapi1.p.rapidapi.com"
        base_url = f"https://{rapidapi_host}/v1/dx"
        
        headers = {
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": rapidapi_host,
            "Content-Type": "application/json"
        }
        
        # Initialize session if needed
        if not _endlessmedical_session["initialized"]:
            session_response = requests.get(f"{base_url}/InitSession", headers=headers, timeout=10)
            if session_response.status_code != 200:
                return {"status": "error", "error": f"Failed to initialize session: {session_response.status_code}"}
                
            session_data = session_response.json()
            if session_data.get('status') != 'ok':
                return {"status": "error", "error": "Session initialization failed"}
                
            session_id = session_data.get('SessionID')
            if not session_id:
                return {"status": "error", "error": "No session ID received"}
            
            # Accept terms of use
            terms_passphrase = "I have read, understood and I accept and agree to comply with the Terms of Use of EndlessMedicalAPI and Endless Medical services. The Terms of Use are available on endlessmedical.com"
            
            terms_response = requests.post(
                f"{base_url}/AcceptTermsOfUse",
                params={'SessionID': session_id, 'passphrase': terms_passphrase},
                headers=headers,
                timeout=10
            )
            
            if terms_response.status_code != 200 or terms_response.json().get('status') != 'ok':
                return {"status": "error", "error": "Failed to accept terms of use"}
            
            _endlessmedical_session["session_id"] = session_id
            _endlessmedical_session["initialized"] = True
            print(f"✅ EndlessMedical session initialized via RapidAPI: {session_id}")
        
        session_id = _endlessmedical_session["session_id"]
        features_set = []
        
        # Set each feature
        for feature_name, feature_value in features_dict.items():
            try:
                response = requests.post(
                    f"{base_url}/UpdateFeature",
                    params={'SessionID': session_id, 'name': feature_name, 'value': str(feature_value)},
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    features_set.append(f"{feature_name}={feature_value}")
                    print(f"✅ Set {feature_name} = {feature_value}")
                else:
                    print(f"❌ Failed to set {feature_name}: HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error setting {feature_name}: {e}")
        
        return {
            "status": "success",
            "session_id": session_id,
            "features_set": features_set,
            "total_features": len(features_set)
        }
        
    except Exception as e:
        print(f"Error setting EndlessMedical features via RapidAPI: {e}")
        return {"status": "error", "error": str(e)}


def analyze_endlessmedical_session():
    """
    Analyze the current EndlessMedical session via RapidAPI (secure)
    Should be called after set_endlessmedical_features
    """
    global _endlessmedical_session
    
    try:
        if not _endlessmedical_session["initialized"] or not _endlessmedical_session["session_id"]:
            return {"status": "error", "error": "No active session. Call set_medical_features first."}
        
        # RapidAPI configuration
        rapidapi_key = current_app.config.get('RAPIDAPI_KEY')
        if not rapidapi_key:
            return {"status": "error", "error": "RAPIDAPI_KEY not found in configuration"}
        
        rapidapi_host = "endlessmedicalapi1.p.rapidapi.com"
        base_url = f"https://{rapidapi_host}/v1/dx"
        
        headers = {
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": rapidapi_host,
            "Content-Type": "application/json"
        }
        
        session_id = _endlessmedical_session["session_id"]
        
        # Analyze
        analyze_response = requests.get(
            f"{base_url}/Analyze",
            params={'SessionID': session_id},
            headers=headers,
            timeout=15
        )
        
        if analyze_response.status_code == 200:
            analyze_data = analyze_response.json()
            if analyze_data.get('status') == 'ok':
                diseases = analyze_data.get('Diseases', [])
                
                if diseases:
                    # Convert to standard format
                    conditions = []
                    for disease_dict in diseases[:5]:  # Top 5
                        for disease_name, probability in disease_dict.items():
                            conditions.append({
                                'name': disease_name,
                                'probability': float(probability),
                                'common_name': disease_name
                            })
                    
                    print(f"✅ EndlessMedical analysis via RapidAPI: {len(conditions)} conditions found")
                    
                    # Clear session for next use
                    _endlessmedical_session["initialized"] = False
                    _endlessmedical_session["session_id"] = None
                    
                    return {
                        'conditions': conditions,
                        'status': 'success',
                        'date': time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                else:
                    print("ℹ️ EndlessMedical analysis completed but no diseases found")
                    return {
                        'conditions': [],
                        'status': 'no_conditions'
                    }
            else:
                print(f"❌ EndlessMedical analysis failed: {analyze_data}")
                return {"status": "error", "error": f"Analysis failed: {analyze_data}"}
        else:
            print(f"❌ EndlessMedical analysis HTTP error: {analyze_response.status_code}")
            return {"status": "error", "error": f"HTTP error: {analyze_response.status_code}"}
        
    except Exception as e:
        print(f"Error analyzing EndlessMedical session via RapidAPI: {e}")
        return {"status": "error", "error": str(e)} 