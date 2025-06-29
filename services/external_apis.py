"""External API integrations for medical services"""

import requests
import time
import xml.etree.ElementTree as ET
from flask import current_app
from utils.helpers import calculate_distance
from models.user import get_user_country

# Simple session cache for EndlessMedical
_endlessmedical_session = {"session_id": None, "initialized": False}


def pubmed_search(query, max_results=5):
    """
    Enhanced PubMed search with full article content extraction
    Returns structured data with medical research articles including full text when available
    """
    try:
        # Clean and enhance the medical query
        medical_query = f"({query}) AND (medicine[Title/Abstract] OR clinical[Title/Abstract] OR treatment[Title/Abstract] OR diagnosis[Title/Abstract])"
        
        # Step 1: Search for PubMed IDs
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        search_params = {
            'db': 'pubmed',
            'term': medical_query,
            'retmode': 'json',
            'retmax': max_results,
            'sort': 'relevance',
            'usehistory': 'y'
        }
        
        search_response = requests.get(search_url, params=search_params, timeout=10)
        search_response.raise_for_status()
        search_data = search_response.json()
        
        pubmed_ids = search_data.get('esearchresult', {}).get('idlist', [])
        
        if not pubmed_ids:
            return [{"title": "No PubMed articles found", "body": "Try different medical terms", "href": "", "source": "PubMed"}]
        
        # Step 2: Fetch detailed information for each article
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fetch_params = {
            'db': 'pubmed',
            'id': ','.join(pubmed_ids),
            'retmode': 'xml'
        }
        
        fetch_response = requests.get(fetch_url, params=fetch_params, timeout=15)
        fetch_response.raise_for_status()
        
        # Parse XML response
        root = ET.fromstring(fetch_response.content)
        articles = []
        
        for article in root.findall('.//PubmedArticle')[:max_results]:
            try:
                # Extract article information
                medline_citation = article.find('.//MedlineCitation')
                pmid = medline_citation.find('.//PMID').text if medline_citation.find('.//PMID') is not None else "Unknown"
                
                # Title
                title_elem = article.find('.//ArticleTitle')
                title = title_elem.text if title_elem is not None else "No Title Available"
                
                # Abstract - try to get full abstract
                abstract_parts = []
                abstract_texts = article.findall('.//AbstractText')
                if abstract_texts:
                    for abstract_text in abstract_texts:
                        label = abstract_text.get('Label', '')
                        text = abstract_text.text or ''
                        if label:
                            abstract_parts.append(f"{label}: {text}")
                        else:
                            abstract_parts.append(text)
                    abstract = " ".join(abstract_parts)
                else:
                    abstract = "No abstract available"
                
                # Journal
                journal_elem = article.find('.//Journal/Title')
                if not journal_elem:
                    journal_elem = article.find('.//Journal/ISOAbbreviation')
                journal = journal_elem.text if journal_elem is not None else "Unknown Journal"
                
                # Publication year
                year_elem = article.find('.//PubDate/Year')
                year = year_elem.text if year_elem is not None else "Unknown"
                
                # Authors
                authors = []
                for author in article.findall('.//Author')[:3]:  # First 3 authors
                    lastname = author.find('LastName')
                    firstname = author.find('ForeName')
                    if lastname is not None and firstname is not None:
                        authors.append(f"{firstname.text} {lastname.text}")
                
                author_text = ", ".join(authors) if authors else "Unknown Authors"
                if len(authors) >= 3:
                    author_text += " et al."
                
                # Create article URL
                article_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                
                # Try to get full text content
                full_text_content = _attempt_full_text_extraction(pmid, article_url)
                
                # Format the body with medical context and full text if available
                body = f"{abstract}\n\n"
                if full_text_content:
                    body += f"**Key Findings from Full Text:**\n{full_text_content}\n\n"
                
                body += f"**Journal:** {journal} ({year})\n**Authors:** {author_text}\n**PMID:** {pmid}"
                
                articles.append({
                    'title': title,
                    'body': body,
                    'href': article_url,
                    'source': 'PubMed',
                    'pmid': pmid,
                    'journal': journal,
                    'year': year,
                    'authors': author_text,
                    'abstract': abstract,
                    'full_text_excerpt': full_text_content or "Full text not accessible"
                })
                
            except Exception as e:
                print(f"Error parsing individual article: {e}")
                continue
        
        if not articles:
            return [{"title": "No detailed articles found", "body": "PubMed search completed but no article details available", "href": "", "source": "PubMed"}]
        
        return articles
        
    except requests.exceptions.RequestException as e:
        print(f"Error in PubMed search (network): {e}")
        return [{"error": f"PubMed search failed: Network error - {str(e)}"}]
    except ET.ParseError as e:
        print(f"Error parsing PubMed XML: {e}")
        return [{"error": f"PubMed search failed: XML parsing error - {str(e)}"}]
    except Exception as e:
        print(f"Error in PubMed search: {e}")
        return [{"error": f"PubMed search failed: {str(e)}"}]


def _attempt_full_text_extraction(pmid, pubmed_url):
    """
    Attempt to extract key content from PubMed article page
    """
    try:
        # Try to get content from the PubMed page itself
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(pubmed_url, headers=headers, timeout=10)
        if response.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try to extract key findings or conclusion
            # Look for conclusion, results, or significance sections
            key_sections = []
            
            # Check for structured abstract sections
            abstract_sections = soup.find_all(['div', 'p'], class_=lambda x: x and 'abstract' in x.lower())
            for section in abstract_sections:
                text = section.get_text(strip=True)
                if any(keyword in text.lower() for keyword in ['conclusion', 'results', 'findings', 'significance']):
                    key_sections.append(text[:200])
            
            # If we found key sections, return them
            if key_sections:
                return " ".join(key_sections)
            
            # Fallback: try to get any conclusion or results text
            conclusion_keywords = ['conclusion', 'results', 'findings', 'clinical significance']
            all_text = soup.get_text()
            
            for keyword in conclusion_keywords:
                keyword_index = all_text.lower().find(keyword)
                if keyword_index != -1:
                    # Extract text around the keyword
                    start = max(0, keyword_index - 50)
                    end = min(len(all_text), keyword_index + 300)
                    excerpt = all_text[start:end].strip()
                    if len(excerpt) > 50:  # Only return if substantial content
                        return excerpt
            
        return None
        
    except Exception as e:
        print(f"Could not extract full text for PMID {pmid}: {e}")
        return None


def duckduckgo_search(query, max_results=5):
    """
    DEPRECATED: DuckDuckGo search replaced with PubMed search for medical accuracy
    Redirects to pubmed_search for better medical content
    """
    print("⚠️ DuckDuckGo search deprecated. Using PubMed search for medical accuracy.")
    return pubmed_search(query, max_results)


def web_search_medical(query, max_results=5):
    """
    Enhanced medical web search using PubMed E-utilities
    Optimized for medical and clinical content
    """
    return pubmed_search(query, max_results)


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
            print("❌ RAPIDAPI_KEY not found in configuration")
            return {
                "status": "error", 
                "error": "RAPIDAPI_KEY not found in configuration",
                "details": "Please set RAPIDAPI_KEY environment variable"
            }
        
        rapidapi_host = "endlessmedicalapi1.p.rapidapi.com"
        
        # Try multiple possible API endpoint structures
        possible_base_urls = [
            f"https://{rapidapi_host}",
            f"https://{rapidapi_host}/v1/dx", 
            f"https://api.endlessmedical.com/v1/dx"
        ]
        
        headers = {
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": rapidapi_host,
            "Content-Type": "application/json"
        }
        
        print(f"🔑 Using RapidAPI Key: {rapidapi_key[:10]}...{rapidapi_key[-4:]}")
        print(f"🔧 Setting {len(features_dict)} medical features...")
        
        # Initialize session if needed
        if not _endlessmedical_session["initialized"]:
            print("🔄 Initializing EndlessMedical session...")
            
            session_id = None
            working_base_url = None
            
            # Try each possible endpoint structure
            for base_url in possible_base_urls:
                print(f"🌐 Trying: {base_url}/InitSession")
                
                try:
                    session_response = requests.get(f"{base_url}/InitSession", headers=headers, timeout=10)
                    print(f"📡 Response: {session_response.status_code}")
                    
                    if session_response.status_code == 403:
                        print(f"❌ 403 Forbidden - Subscription required or quota exceeded")
                        return {
                            "status": "error", 
                            "error": "RapidAPI subscription required. Please subscribe to EndlessMedical API on RapidAPI platform.",
                            "details": "Visit https://rapidapi.com/lukaszkiljanek/api/endlessmedicalapi1 to subscribe",
                            "subscription_url": "https://rapidapi.com/lukaszkiljanek/api/endlessmedicalapi1"
                        }
                    elif session_response.status_code == 401:
                        print(f"❌ 401 Unauthorized - Invalid API key")
                        return {
                            "status": "error", 
                            "error": "Invalid RapidAPI key. Please check your RAPIDAPI_KEY in environment variables.",
                            "details": "Get a valid key from https://rapidapi.com/",
                            "rapidapi_url": "https://rapidapi.com/"
                        }
                    elif session_response.status_code == 404:
                        print(f"❌ 404 Not Found - Endpoint structure incorrect")
                        continue  # Try next URL
                    elif session_response.status_code == 200:
                        print(f"✅ Found working endpoint: {base_url}")
                        working_base_url = base_url
                        
                        try:
                            session_data = session_response.json()
                            print(f"📊 Session data: {session_data}")
                            
                            if session_data.get('status') == 'ok':
                                session_id = session_data.get('SessionID')
                                if session_id:
                                    print(f"✅ Session ID received: {session_id}")
                                    break
                                else:
                                    print(f"❌ No session ID in response: {session_data}")
                            else:
                                print(f"❌ Session init failed: {session_data}")
                                
                        except ValueError as e:
                            print(f"❌ JSON parsing error: {e}")
                            print(f"Raw response: {session_response.text[:200]}")
                            continue
                    else:
                        print(f"⚠️ Unexpected status {session_response.status_code}: {session_response.text[:100]}")
                        continue
                        
                except requests.exceptions.Timeout:
                    print(f"⏱️ Timeout for {base_url}")
                    continue
                except requests.exceptions.ConnectionError:
                    print(f"🌐 Connection error for {base_url}")
                    continue
                except Exception as e:
                    print(f"💥 Error with {base_url}: {e}")
                    continue
            
            # If no working endpoint found
            if not working_base_url or not session_id:
                print("❌ All EndlessMedical API endpoints failed")
                return {
                    "status": "error",
                    "error": "EndlessMedical API is currently unavailable",
                    "details": "All API endpoints returned errors. This may be due to:",
                    "possible_causes": [
                        "API structure has changed",
                        "RapidAPI subscription is not active",
                        "Service is temporarily down",
                        "API key is invalid or expired"
                    ],
                    "troubleshooting": {
                        "check_subscription": "https://rapidapi.com/lukaszkiljanek/api/endlessmedicalapi1",
                        "verify_api_key": "Check RAPIDAPI_KEY environment variable",
                        "contact_support": "Contact RapidAPI or EndlessMedical support"
                    }
                }
            
            # Accept terms of use
            terms_passphrase = "I have read, understood and I accept and agree to comply with the Terms of Use of EndlessMedicalAPI and Endless Medical services. The Terms of Use are available on endlessmedical.com"
            
            print("📝 Accepting terms of use...")
            try:
                terms_response = requests.post(
                    f"{working_base_url}/AcceptTermsOfUse",
                    params={'SessionID': session_id, 'passphrase': terms_passphrase},
                    headers=headers,
                    timeout=10
                )
                
                print(f"📡 Terms response: {terms_response.status_code}")
                
                if terms_response.status_code == 200:
                    terms_data = terms_response.json()
                    if terms_data.get('status') == 'ok':
                        _endlessmedical_session["session_id"] = session_id
                        _endlessmedical_session["initialized"] = True
                        _endlessmedical_session["base_url"] = working_base_url
                        print(f"✅ EndlessMedical session initialized: {session_id}")
                    else:
                        print(f"❌ Terms acceptance failed: {terms_data}")
                        return {
                            "status": "error", 
                            "error": "Failed to accept terms of use",
                            "details": str(terms_data)
                        }
                else:
                    print(f"❌ Terms acceptance HTTP error: {terms_response.status_code}")
                    return {
                        "status": "error", 
                        "error": f"Failed to accept terms: HTTP {terms_response.status_code}",
                        "details": terms_response.text[:200]
                    }
                    
            except Exception as e:
                print(f"💥 Terms acceptance error: {e}")
                return {
                    "status": "error", 
                    "error": f"Error accepting terms: {str(e)}",
                    "details": "Network or API error during terms acceptance"
                }
        
        # Set features using working session
        session_id = _endlessmedical_session["session_id"]
        base_url = _endlessmedical_session.get("base_url", possible_base_urls[0])
        features_set = []
        failed_features = []
        
        print(f"🔧 Setting {len(features_dict)} features using session {session_id}")
        
        # Set each feature
        for feature_name, feature_value in features_dict.items():
            try:
                print(f"🔧 Setting {feature_name} = {feature_value}")
                response = requests.post(
                    f"{base_url}/UpdateFeature",
                    params={'SessionID': session_id, 'name': feature_name, 'value': str(feature_value)},
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        if response_data.get('status') == 'ok':
                            features_set.append(f"{feature_name}={feature_value}")
                            print(f"✅ Set {feature_name} = {feature_value}")
                        else:
                            failed_features.append(f"{feature_name}: {response_data}")
                            print(f"❌ Failed to set {feature_name}: {response_data}")
                    except ValueError:
                        # Non-JSON response
                        if "ok" in response.text.lower():
                            features_set.append(f"{feature_name}={feature_value}")
                            print(f"✅ Set {feature_name} = {feature_value}")
                        else:
                            failed_features.append(f"{feature_name}: Invalid response")
                            print(f"❌ Failed to set {feature_name}: Invalid response")
                else:
                    failed_features.append(f"{feature_name}: HTTP {response.status_code}")
                    print(f"❌ Failed to set {feature_name}: HTTP {response.status_code}")
                    
            except Exception as e:
                failed_features.append(f"{feature_name}: {str(e)}")
                print(f"❌ Error setting {feature_name}: {e}")
        
        # Return results
        if features_set:
            result = {
                "status": "success",
                "session_id": session_id,
                "features_set": features_set,
                "failed_features": failed_features,
                "total_features": len(features_set),
                "success_rate": f"{len(features_set)}/{len(features_dict)} features set successfully"
            }
            print(f"✅ Features set successfully: {len(features_set)}/{len(features_dict)}")
            return result
        else:
            return {
                "status": "error",
                "error": "No features were successfully set",
                "failed_features": failed_features,
                "session_id": session_id,
                "troubleshooting": "Check feature names and values against EndlessMedical API documentation"
            }
        
    except Exception as e:
        print(f"💥 Unexpected error in set_endlessmedical_features: {e}")
        return {
            "status": "error", 
            "error": f"Unexpected error: {str(e)}",
            "details": "An unexpected error occurred while setting medical features"
        }


def analyze_endlessmedical_session():
    """
    Analyze the current EndlessMedical session via RapidAPI (secure)
    Should be called after set_endlessmedical_features
    """
    global _endlessmedical_session
    
    try:
        if not _endlessmedical_session["initialized"] or not _endlessmedical_session["session_id"]:
            print("❌ No active EndlessMedical session")
            return {
                "status": "error", 
                "error": "No active session. Call set_medical_features first.",
                "details": "You must initialize a session and set features before analysis"
            }
        
        # RapidAPI configuration
        rapidapi_key = current_app.config.get('RAPIDAPI_KEY')
        if not rapidapi_key:
            return {
                "status": "error", 
                "error": "RAPIDAPI_KEY not found in configuration",
                "details": "Please set RAPIDAPI_KEY environment variable"
            }
        
        rapidapi_host = "endlessmedicalapi1.p.rapidapi.com"
        base_url = _endlessmedical_session.get("base_url", f"https://{rapidapi_host}")
        
        headers = {
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": rapidapi_host,
            "Content-Type": "application/json"
        }
        
        session_id = _endlessmedical_session["session_id"]
        
        print(f"🔍 Analyzing EndlessMedical session: {session_id}")
        
        # Analyze
        try:
            analyze_response = requests.get(
                f"{base_url}/Analyze",
                params={'SessionID': session_id},
                headers=headers,
                timeout=15
            )
            
            print(f"📡 Analysis response: {analyze_response.status_code}")
            
            if analyze_response.status_code == 403:
                return {
                    "status": "error",
                    "error": "RapidAPI subscription required for analysis",
                    "details": "Your subscription may have expired or reached quota limits",
                    "subscription_url": "https://rapidapi.com/lukaszkiljanek/api/endlessmedicalapi1"
                }
            elif analyze_response.status_code == 401:
                return {
                    "status": "error",
                    "error": "Invalid RapidAPI key for analysis",
                    "details": "Check your RAPIDAPI_KEY environment variable"
                }
            elif analyze_response.status_code == 404:
                return {
                    "status": "error",
                    "error": "Analysis endpoint not found",
                    "details": "EndlessMedical API structure may have changed"
                }
            elif analyze_response.status_code == 200:
                try:
                    analyze_data = analyze_response.json()
                    print(f"📊 Analysis data: {analyze_data}")
                    
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
                            
                            print(f"✅ EndlessMedical analysis complete: {len(conditions)} conditions found")
                            
                            # Clear session for next use
                            _endlessmedical_session["initialized"] = False
                            _endlessmedical_session["session_id"] = None
                            
                            return {
                                'conditions': conditions,
                                'status': 'success',
                                'date': time.strftime('%Y-%m-%d %H:%M:%S'),
                                'total_conditions': len(conditions),
                                'database': 'EndlessMedical (830+ medical conditions)'
                            }
                        else:
                            print("ℹ️ EndlessMedical analysis completed but no diseases found")
                            return {
                                'status': 'no_results',
                                'message': 'No specific conditions found in clinical database',
                                'date': time.strftime('%Y-%m-%d %H:%M:%S'),
                                'suggestion': 'Try setting more specific medical features'
                            }
                    else:
                        print(f"❌ Analysis failed: {analyze_data}")
                        return {
                            'status': 'error',
                            'error': 'Analysis failed',
                            'details': str(analyze_data),
                            'suggestion': 'Check if all required features were set correctly'
                        }
                        
                except ValueError as e:
                    print(f"❌ JSON parsing error in analysis: {e}")
                    return {
                        'status': 'error',
                        'error': 'Invalid response format from analysis',
                        'details': f'JSON parsing failed: {str(e)}'
                    }
            else:
                print(f"⚠️ Unexpected analysis status: {analyze_response.status_code}")
                return {
                    'status': 'error',
                    'error': f'Analysis request failed: HTTP {analyze_response.status_code}',
                    'details': analyze_response.text[:200],
                    'suggestion': 'Check API status and try again'
                }
                
        except requests.exceptions.Timeout:
            print("⏱️ Analysis request timed out")
            return {
                'status': 'error',
                'error': 'Analysis request timed out',
                'details': 'The analysis took too long to complete'
            }
        except requests.exceptions.ConnectionError:
            print("🌐 Connection error during analysis")
            return {
                'status': 'error',
                'error': 'Network connection error during analysis',
                'details': 'Check internet connection and API status'
            }
        except Exception as e:
            print(f"💥 Analysis error: {e}")
            return {
                'status': 'error',
                'error': f'Analysis failed: {str(e)}',
                'details': 'An unexpected error occurred during analysis'
            }
        
    except Exception as e:
        print(f"💥 Unexpected error in analyze_endlessmedical_session: {e}")
        return {
            'status': 'error',
            'error': f'Unexpected error: {str(e)}',
            'details': 'An unexpected error occurred while analyzing the session'
        } 