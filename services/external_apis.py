"""External API integrations for medical services"""
import requests
import time
import xml.etree.ElementTree as ET
from flask import current_app
from utils.helpers import calculate_distance
from models.user import get_user_country, save_user_country
import re
from datetime import datetime
_endlessmedical_session = {"session_id": None, "initialized": False}
def pubmed_search(query, max_results=5):
    """
    Enhanced PubMed search with full article content extraction
    Returns structured data with medical research articles including full text when available
    """
    try:
        medical_query = f"({query}) AND (medicine[Title/Abstract] OR clinical[Title/Abstract] OR treatment[Title/Abstract] OR diagnosis[Title/Abstract])"
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
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fetch_params = {
            'db': 'pubmed',
            'id': ','.join(pubmed_ids),
            'retmode': 'xml'
        }
        fetch_response = requests.get(fetch_url, params=fetch_params, timeout=15)
        fetch_response.raise_for_status()
        root = ET.fromstring(fetch_response.content)
        articles = []
        for article in root.findall('.//PubmedArticle')[:max_results]:
            try:
                medline_citation = article.find('.//MedlineCitation')
                pmid = medline_citation.find('.//PMID').text if medline_citation.find('.//PMID') is not None else "Unknown"
                title_elem = article.find('.//ArticleTitle')
                title = title_elem.text if title_elem is not None else "No Title Available"
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
                journal_elem = article.find('.//Journal/Title')
                if not journal_elem:
                    journal_elem = article.find('.//Journal/ISOAbbreviation')
                journal = journal_elem.text if journal_elem is not None else "Unknown Journal"
                year_elem = article.find('.//PubDate/Year')
                year = year_elem.text if year_elem is not None else "Unknown"
                authors = []
                for author in article.findall('.//Author')[:3]:
                    lastname = author.find('LastName')
                    firstname = author.find('ForeName')
                    if lastname is not None and firstname is not None:
                        authors.append(f"{firstname.text} {lastname.text}")
                author_text = ", ".join(authors) if authors else "Unknown Authors"
                if len(authors) >= 3:
                    author_text += " et al."
                article_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                full_text_content = _attempt_full_text_extraction(pmid, article_url)
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
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(pubmed_url, headers=headers, timeout=10)
        if response.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            key_sections = []
            abstract_sections = soup.find_all(['div', 'p'], class_=lambda x: x and 'abstract' in x.lower())
            for section in abstract_sections:
                text = section.get_text(strip=True)
                if any(keyword in text.lower() for keyword in ['conclusion', 'results', 'findings', 'significance']):
                    key_sections.append(text[:200])
            if key_sections:
                return " ".join(key_sections)
            conclusion_keywords = ['conclusion', 'results', 'findings', 'clinical significance']
            all_text = soup.get_text()
            for keyword in conclusion_keywords:
                keyword_index = all_text.lower().find(keyword)
                if keyword_index != -1:
                    start = max(0, keyword_index - 50)
                    end = min(len(all_text), keyword_index + 300)
                    excerpt = all_text[start:end].strip()
                    if len(excerpt) > 50:
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
        time.sleep(1)
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
            for element in data.get('elements', [])[:5]:
                if 'tags' in element:
                    name = element['tags'].get('name', 'Medical Facility')
                    amenity = element['tags'].get('amenity', 'clinic')
                    if element['type'] == 'node':
                        lat, lon = element['lat'], element['lon']
                    elif 'center' in element:
                        lat, lon = element['center']['lat'], element['center']['lon']
                    else:
                        continue
                    distance = calculate_distance(latitude, longitude, lat, lon)
                    clinics.append({
                        'name': name,
                        'type': amenity,
                        'distance': round(distance, 2),
                        'lat': lat,
                        'lon': lon
                    })
            clinics.sort(key=lambda x: x['distance'])
            return clinics[:3]
        return []
    except Exception as e:
        print(f"Error finding nearby clinics: {e}")
        return []
def fetch_who_disease_outbreaks():
    """Fetch current disease outbreaks from WHO Disease Outbreak News API"""
    try:
        who_api_url = "https://www.who.int/api/news/diseaseoutbreaknews"
        headers = {
            'User-Agent': 'MedSenseAI/1.0 Medical Bot',
            'Accept': 'application/json'
        }
        print(f"🌐 Fetching WHO disease outbreaks from: {who_api_url}")
        response = requests.get(who_api_url, headers=headers, timeout=15)
        print(f"📡 WHO API Response Status: {response.status_code}")
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"📊 WHO API returned {len(data) if isinstance(data, list) else 'data'} outbreak entries")
                return data
            except ValueError as json_error:
                print(f"❌ JSON parsing error: {json_error}")
                print(f"Raw response: {response.text[:200]}...")
                return None
        else:
            print(f"❌ WHO API returned status code: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            return None
    except requests.exceptions.Timeout:
        print("⏱️ WHO API request timed out")
        return None
    except requests.exceptions.ConnectionError:
        print("🌐 Connection error to WHO API")
        return None
    except Exception as e:
        print(f"💥 Error fetching WHO disease outbreaks: {e}")
        return None
def check_disease_outbreaks_for_user(user_id):
    """Check for disease outbreaks in user's country using WHO Disease Outbreak News API"""
    user_country = get_user_country(user_id)
    if not user_country:
        print(f"⚠️ No country set for user {user_id}")
        return []
    print(f"🔍 Checking disease outbreaks for user {user_id} in country: {user_country}")
    outbreaks_data = fetch_who_disease_outbreaks()
    if not outbreaks_data:
        print("❌ No outbreak data received from WHO API")
        return []
    relevant_outbreaks = []
    current_year = datetime.now().year
    cutoff_year = current_year - 2  # Only show outbreaks from last 2 years
    
    try:
        if isinstance(outbreaks_data, list):
            outbreak_entries = outbreaks_data
        else:
            outbreak_entries = outbreaks_data.get('value', outbreaks_data.get('data', outbreaks_data.get('outbreaks', [])))
        print(f"📋 Processing {len(outbreak_entries)} outbreak entries")
        
        for entry in outbreak_entries:
            try:
                title = entry.get('Title', entry.get('title', 'Unknown outbreak'))
                summary = entry.get('Summary', entry.get('summary', ''))
                overview = entry.get('Overview', entry.get('overview', ''))
                publication_date = entry.get('PublicationDate', entry.get('PublicationDateAndTime', entry.get('DateCreated', '')))
                
                # IMPROVED DATE FILTERING - Skip old outbreaks
                is_recent = False
                outbreak_year = None
                if publication_date:
                    try:
                        if 'T' in publication_date:
                            parsed_date = datetime.fromisoformat(publication_date.replace('Z', '+00:00'))
                            outbreak_year = parsed_date.year
                        elif '-' in publication_date:
                            # Handle YYYY-MM-DD format
                            year_part = publication_date.split('-')[0]
                            if year_part.isdigit() and len(year_part) == 4:
                                outbreak_year = int(year_part)
                        elif publication_date.isdigit() and len(publication_date) == 4:
                            # Handle YYYY format
                            outbreak_year = int(publication_date)
                        
                        if outbreak_year and outbreak_year >= cutoff_year:
                            is_recent = True
                        else:
                            print(f"⏰ Skipping old outbreak from {outbreak_year}: {title[:50]}...")
                            continue
                    except Exception as date_error:
                        print(f"⚠️ Date parsing error for '{publication_date}': {date_error}")
                        # If we can't parse the date, skip it to be safe
                        continue
                else:
                    # No date available, skip it
                    print(f"📅 Skipping outbreak with no date: {title[:50]}...")
                    continue
                
                if not is_recent:
                    continue
                
                # IMPROVED COUNTRY MATCHING - More precise matching
                user_country_clean = user_country.lower().strip()
                
                # Expand country variations more carefully
                country_variations = [user_country_clean]
                
                # Add specific country mappings
                country_mapping = {
                    'united states': ['usa', 'america', 'us', 'united states of america'],
                    'usa': ['united states', 'america', 'us', 'united states of america'],
                    'america': ['usa', 'united states', 'us', 'united states of america'],
                    'united kingdom': ['uk', 'britain', 'england', 'great britain'],
                    'uk': ['united kingdom', 'britain', 'england', 'great britain'],
                    'britain': ['uk', 'united kingdom', 'england', 'great britain'],
                    'south africa': ['rsa', 'republic of south africa'],
                    'democratic republic of congo': ['drc', 'congo drc', 'dr congo'],
                    'drc': ['democratic republic of congo', 'congo drc', 'dr congo'],
                    'china': ['peoples republic of china', 'prc'],
                    'russia': ['russian federation', 'ussr'],
                    'south korea': ['republic of korea', 'korea south'],
                    'north korea': ['democratic peoples republic of korea', 'korea north']
                }
                
                if user_country_clean in country_mapping:
                    country_variations.extend(country_mapping[user_country_clean])
                
                # Check title and content for country mentions
                content_text = f"{title} {summary} {overview}".lower()
                
                # STRICTER COUNTRY MATCHING - Must appear in title or be prominent in content
                is_relevant = False
                country_found_in = []
                
                # Check if country appears in title (high relevance)
                title_lower = title.lower()
                for country_var in country_variations:
                    pattern = r'\b' + re.escape(country_var) + r'\b'
                    if re.search(pattern, title_lower, re.IGNORECASE):
                        is_relevant = True
                        country_found_in.append(f"title: {country_var}")
                        break
                
                # If not in title, check for prominent mentions in content
                if not is_relevant:
                    for country_var in country_variations:
                        pattern = r'\b' + re.escape(country_var) + r'\b'
                        matches = re.findall(pattern, content_text, re.IGNORECASE)
                        # Require multiple mentions or specific outbreak keywords
                        if len(matches) >= 2 or (len(matches) >= 1 and any(keyword in content_text for keyword in ['outbreak in', 'epidemic in', 'cases in', 'reported in'])):
                            is_relevant = True
                            country_found_in.append(f"content: {country_var} ({len(matches)} mentions)")
                            break
                
                # Also check regions/countries field if available
                if not is_relevant:
                    regions_content = entry.get('regionscountries', entry.get('RegionsCountries', ''))
                    if regions_content and isinstance(regions_content, str):
                        regions_lower = regions_content.lower()
                        for country_var in country_variations:
                            pattern = r'\b' + re.escape(country_var) + r'\b'
                            if re.search(pattern, regions_lower, re.IGNORECASE):
                                is_relevant = True
                                country_found_in.append(f"regions: {country_var}")
                                break
                
                # ADDITIONAL VALIDATION - Ensure it's actually about the country, not just mentioning it
                if is_relevant:
                    # Skip if it's clearly about a different primary country
                    other_countries = ['afghanistan', 'albania', 'algeria', 'argentina', 'australia', 'austria', 'bangladesh', 'belgium', 'brazil', 'canada', 'chile', 'colombia', 'denmark', 'egypt', 'ethiopia', 'finland', 'france', 'germany', 'ghana', 'greece', 'india', 'indonesia', 'iran', 'iraq', 'ireland', 'israel', 'italy', 'japan', 'kenya', 'malaysia', 'mexico', 'morocco', 'netherlands', 'nigeria', 'norway', 'pakistan', 'peru', 'philippines', 'poland', 'portugal', 'romania', 'saudi arabia', 'singapore', 'spain', 'sweden', 'switzerland', 'thailand', 'turkey', 'ukraine', 'venezuela', 'vietnam']
                    
                    # Remove user's country from the check list
                    other_countries = [c for c in other_countries if c != user_country_clean and c not in country_variations]
                    
                    # Count mentions of other countries in title
                    other_country_mentions_in_title = 0
                    for other_country in other_countries:
                        if re.search(r'\b' + re.escape(other_country) + r'\b', title_lower):
                            other_country_mentions_in_title += 1
                    
                    # If title prominently features other countries, it's probably not about user's country
                    if other_country_mentions_in_title >= 2:
                        print(f"🚫 Skipping outbreak primarily about other countries: {title[:50]}...")
                        continue
                
                if is_relevant:
                    disease_name = title
                    if ' – ' in title:  # WHO often uses this format: "Disease – Country"
                        disease_name = title.split(' – ')[0].strip()
                    elif '-' in title:
                        disease_name = title.split('-')[0].strip()
                    elif 'outbreak' in title.lower():
                        disease_name = title.replace('outbreak', '').replace('Outbreak', '').strip()
                    
                    formatted_date = publication_date
                    if publication_date:
                        try:
                            if 'T' in publication_date:
                                parsed_date = datetime.fromisoformat(publication_date.replace('Z', '+00:00'))
                                formatted_date = parsed_date.strftime('%Y-%m-%d')
                        except:
                            pass
                    
                    outbreak_info = {
                        'disease': disease_name,
                        'title': title,
                        'location': user_country,
                        'date': formatted_date,
                        'year': outbreak_year,
                        'summary': (summary or overview)[:300] + '...' if len(summary or overview) > 300 else (summary or overview),
                        'source': 'WHO Disease Outbreak News',
                        'relevance_details': ', '.join(country_found_in)
                    }
                    relevant_outbreaks.append(outbreak_info)
                    print(f"✅ Found relevant outbreak: {disease_name} for {user_country} ({outbreak_year}) - Found in: {', '.join(country_found_in)}")
            except Exception as e:
                print(f"⚠️ Error processing outbreak entry: {e}")
                continue
        
        # Sort by year (most recent first)
        relevant_outbreaks.sort(key=lambda x: x.get('year', 0), reverse=True)
        
        # Limit to most recent 5 outbreaks to avoid overwhelming users
        relevant_outbreaks = relevant_outbreaks[:5]
        
        print(f"🎯 Found {len(relevant_outbreaks)} recent and relevant outbreaks for {user_country}")
        return relevant_outbreaks
    except Exception as e:
        print(f"💥 Error processing WHO outbreak data: {e}")
        return []
def initialize_endlessmedical():
    """DEPRECATED - Use set_endlessmedical_features instead"""
    print("⚠️ WARNING: initialize_endlessmedical is deprecated. Use RapidAPI functions instead.")
    return False
def get_endlessmedical_diagnosis(symptoms_text, user_profile):
    """DEPRECATED - Use set_endlessmedical_features + analyze_endlessmedical_session instead"""
    print("⚠️ WARNING: get_endlessmedical_diagnosis is deprecated. Using RapidAPI functions instead.")
    try:
        features = {}
        symptoms_lower = symptoms_text.lower()
        if user_profile and user_profile.get('age'):
            features['Age'] = str(user_profile.get('age'))
        else:
            features['Age'] = '30'
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
        rapidapi_key = current_app.config.get('RAPIDAPI_KEY')
        if not rapidapi_key:
            print("❌ RAPIDAPI_KEY not found in configuration")
            return {
                "status": "error", 
                "error": "RAPIDAPI_KEY not found in configuration",
                "details": "Please set RAPIDAPI_KEY environment variable"
            }
        rapidapi_host = "endlessmedicalapi1.p.rapidapi.com"
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
        if not _endlessmedical_session["initialized"]:
            print("🔄 Initializing EndlessMedical session...")
            session_id = None
            working_base_url = None
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
                        continue
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
        session_id = _endlessmedical_session["session_id"]
        base_url = _endlessmedical_session.get("base_url", possible_base_urls[0])
        features_set = []
        failed_features = []
        print(f"🔧 Setting {len(features_dict)} features using session {session_id}")
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
                            conditions = []
                            for disease_dict in diseases[:5]:
                                for disease_name, probability in disease_dict.items():
                                    conditions.append({
                                        'name': disease_name,
                                        'probability': float(probability),
                                        'common_name': disease_name
                                    })
                            print(f"✅ EndlessMedical analysis complete: {len(conditions)} conditions found")
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
