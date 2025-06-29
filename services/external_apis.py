"""External API integrations for medical services"""

import requests
import time
from flask import current_app
from utils.helpers import calculate_distance
from models.user import get_user_country


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
    """Initialize EndlessMedical API connection"""
    try:
        endlessmedical_url = current_app.config.get('ENDLESSMEDICAL_API_URL')
        # Test connection with InitSession endpoint (with SSL verification disabled for troubleshooting)
        response = requests.get(f"{endlessmedical_url}/InitSession", timeout=10, verify=False)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'ok':
                print("✅ EndlessMedical API connection successful")
                return True
            else:
                print(f"❌ EndlessMedical API test failed: {result}")
                return None
        else:
            print(f"❌ EndlessMedical API test failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ EndlessMedical API initialization error: {e}")
        print("🔬 Note: EndlessMedical validation will be disabled, falling back to Gemini-only analysis.")
        return None


def get_endlessmedical_diagnosis(symptoms_text, user_profile):
    """Get diagnosis from EndlessMedical API as a second layer of confirmation"""
    try:
        endlessmedical_url = current_app.config.get('ENDLESSMEDICAL_API_URL')
        
        # Initialize session
        session_response = requests.get(f"{endlessmedical_url}/InitSession", timeout=10, verify=False)
        if session_response.status_code != 200:
            return None
            
        session_data = session_response.json()
        if session_data.get('status') != 'ok':
            return None
            
        session_id = session_data.get('SessionID')
        if not session_id:
            return None
        
        # Accept terms of use
        terms_passphrase = "I have read, understood and I accept and agree to comply with the Terms of Use of EndlessMedicalAPI and Endless Medical services. The Terms of Use are available on endlessmedical.com"
        
        terms_response = requests.post(
            f"{endlessmedical_url}/AcceptTermsOfUse",
            params={'SessionID': session_id, 'passphrase': terms_passphrase},
            timeout=10,
            verify=False
        )
        
        if terms_response.status_code != 200 or terms_response.json().get('status') != 'ok':
            return None
        
        successful_updates = 0
        
        # Set Age (confirmed working)
        if user_profile and user_profile.get('age'):
            age = user_profile.get('age')
            if str(age).isdigit():
                age_response = requests.post(
                    f"{endlessmedical_url}/UpdateFeature",
                    params={'SessionID': session_id, 'name': 'Age', 'value': str(age)},
                    timeout=10,
                    verify=False
                )
                if age_response.status_code == 200:
                    successful_updates += 1
                    print(f"✅ Age set successfully")
        
        # Set temperature based on symptoms (confirmed working)
        symptoms_lower = symptoms_text.lower()
        if any(fever_word in symptoms_lower for fever_word in ['fever', 'hot', 'temperature', 'high temp']):
            temp_response = requests.post(
                f"{endlessmedical_url}/UpdateFeature",
                params={'SessionID': session_id, 'name': 'Temp', 'value': '38.5'},  # 38.5°C = fever
                timeout=10,
                verify=False
            )
            if temp_response.status_code == 200:
                successful_updates += 1
                print(f"✅ Fever temperature set successfully")
        elif any(cold_word in symptoms_lower for cold_word in ['chills', 'cold', 'shivering']):
            # Try setting chills
            chills_response = requests.post(
                f"{endlessmedical_url}/UpdateFeature",
                params={'SessionID': session_id, 'name': 'Chills', 'value': '1'},  # Try numeric format
                timeout=10,
                verify=False
            )
            if chills_response.status_code == 200:
                successful_updates += 1
                print(f"✅ Chills set successfully")
        
        # Set fatigue if mentioned
        if any(fatigue_word in symptoms_lower for fatigue_word in ['tired', 'fatigue', 'weakness', 'weak']):
            fatigue_response = requests.post(
                f"{endlessmedical_url}/UpdateFeature",
                params={'SessionID': session_id, 'name': 'GeneralizedFatigue', 'value': '1'},
                timeout=10,
                verify=False
            )
            if fatigue_response.status_code == 200:
                successful_updates += 1
                print(f"✅ Fatigue set successfully")
        
        # Only proceed with analysis if we have at least one successful feature update
        if successful_updates == 0:
            print("⚠️ No features were successfully updated, skipping analysis")
            return None
        
        print(f"📊 Proceeding with analysis using {successful_updates} features")
        
        # Analyze
        analyze_response = requests.get(
            f"{endlessmedical_url}/Analyze",
            params={'SessionID': session_id},
            timeout=15,
            verify=False
        )
        
        if analyze_response.status_code == 200:
            analyze_data = analyze_response.json()
            if analyze_data.get('status') == 'ok':
                diseases = analyze_data.get('Diseases', [])
                
                if diseases:
                    # Convert to standard format
                    conditions = []
                    for disease_dict in diseases[:3]:  # Top 3
                        for disease_name, probability in disease_dict.items():
                            conditions.append({
                                'name': disease_name,
                                'probability': float(probability),
                                'common_name': disease_name
                            })
                    
                    print(f"✅ EndlessMedical returned {len(conditions)} conditions")
                    return {
                        'conditions': conditions,
                        'status': 'success'
                    }
                else:
                    print("ℹ️ EndlessMedical analysis completed but no diseases found")
                    return {
                        'conditions': [],
                        'status': 'no_conditions'
                    }
            else:
                print(f"❌ EndlessMedical analysis failed: {analyze_data}")
        else:
            print(f"❌ EndlessMedical analysis HTTP error: {analyze_response.status_code}")
        
        return None
        
    except Exception as e:
        print(f"Error getting EndlessMedical diagnosis: {e}")
        return None 