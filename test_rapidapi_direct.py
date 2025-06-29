#!/usr/bin/env python3
"""
Test different endpoint structures for RapidAPI
"""

import os
import requests
from dotenv import load_dotenv

# Load .env file
load_dotenv()

rapidapi_key = os.getenv('RAPIDAPI_KEY')
if not rapidapi_key:
    print("❌ No RAPIDAPI_KEY in .env file")
    exit(1)

print(f"🔑 Testing RapidAPI key: {rapidapi_key[:10]}...{rapidapi_key[-4:]}")

# Test different URL patterns
test_urls = [
    "https://endlessmedicalapi1.p.rapidapi.com/InitSession",
    "https://endlessmedicalapi1.p.rapidapi.com/v1/InitSession",
    "https://endlessmedicalapi1.p.rapidapi.com/v1/dx/InitSession",
    "https://endlessmedicalapi1.p.rapidapi.com/GetFeatures",
    "https://endlessmedicalapi1.p.rapidapi.com/v1/dx/GetFeatures",
]

headers = {
    "X-RapidAPI-Key": rapidapi_key,
    "X-RapidAPI-Host": "endlessmedicalapi1.p.rapidapi.com"
}

for url in test_urls:
    print(f"\n📡 Testing: {url}")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ SUCCESS! This URL works!")
            print(f"   Response preview: {response.text[:100]}...")
            break
        elif response.status_code == 403:
            print(f"   ❌ 403 - Not subscribed or quota exceeded")
            print(f"   Response: {response.text}")
        elif response.status_code == 404:
            print(f"   ❌ 404 - Endpoint not found")
        else:
            print(f"   ⚠️ {response.status_code} - {response.text[:100]}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n" + "="*60)
print("💡 If all URLs return 403, you need to subscribe to the API")
print("💡 If all URLs return 404, the API structure might be different")
print("🔗 Subscribe here: https://rapidapi.com/lukaszkiljanek/api/endlessmedicalapi1") 