#!/usr/bin/env python3
"""
Test RapidAPI key directly
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

# Test EndlessMedical API directly
url = "https://endlessmedicalapi1.p.rapidapi.com/v1/dx/InitSession"
headers = {
    "X-RapidAPI-Key": rapidapi_key,
    "X-RapidAPI-Host": "endlessmedicalapi1.p.rapidapi.com"
}

print(f"\n📡 Testing: {url}")
print(f"🔐 Headers: X-RapidAPI-Host = {headers['X-RapidAPI-Host']}")

try:
    response = requests.get(url, headers=headers, timeout=10)
    
    print(f"\n📊 Response Status: {response.status_code}")
    print(f"📄 Response Headers:")
    for key, value in response.headers.items():
        if key.lower() in ['x-ratelimit-requests-limit', 'x-ratelimit-requests-remaining', 'x-rapidapi-subscription']:
            print(f"   {key}: {value}")
    
    if response.status_code == 200:
        print(f"\n✅ SUCCESS! Your RapidAPI key works!")
        print(f"📦 Response: {response.text[:200]}")
    elif response.status_code == 403:
        print(f"\n❌ FORBIDDEN (403)")
        print(f"📦 Response: {response.text}")
        print("\n💡 Possible reasons:")
        print("   1. You haven't subscribed to EndlessMedical API on RapidAPI")
        print("   2. Your subscription expired")
        print("   3. You've exceeded your quota")
        print("\n🔗 Subscribe here: https://rapidapi.com/lukaszkiljanek/api/endlessmedicalapi1")
    elif response.status_code == 401:
        print(f"\n❌ UNAUTHORIZED (401)")
        print("💡 Your API key is invalid or expired")
    else:
        print(f"\n⚠️ Unexpected status: {response.status_code}")
        print(f"📦 Response: {response.text}")
        
except Exception as e:
    print(f"\n❌ Error: {e}")

print("\n" + "="*60)
print("📝 Next steps:")
print("1. If 403: Subscribe to the API at the link above")
print("2. If 401: Get a new API key from RapidAPI")
print("3. If success: Your bot should work now!") 