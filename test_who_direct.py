#!/usr/bin/env python3
"""
Direct test of WHO Disease Outbreak News API to see what outbreaks are available
"""

import os
import sys
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
env_path = Path('.') / '.env'
if env_path.exists():
    print(f"📁 Loading environment from {env_path}")
    load_dotenv(env_path)
else:
    print("⚠️ No .env file found")

# Set up Flask
os.environ['FLASK_APP'] = 'app.py'

from flask import Flask
from config import Config
from models.database import init_database
from models.user import save_user_country

# Create Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
init_database()

def test_who_api_direct():
    """Test WHO Disease Outbreak News API directly"""
    print("\n🌐 Direct WHO Disease Outbreak News API Test")
    print("=" * 60)
    
    with app.app_context():
        from services.external_apis import fetch_who_disease_outbreaks, check_disease_outbreaks_for_user
        
        # Test 1: Fetch raw WHO data
        print("\n1️⃣ Fetching raw WHO Disease Outbreak News data...")
        outbreak_data = fetch_who_disease_outbreaks()
        
        if outbreak_data:
            print(f"✅ WHO API returned data")
            
            # Handle different response structures
            if isinstance(outbreak_data, list):
                entries = outbreak_data
            else:
                entries = outbreak_data.get('value', outbreak_data.get('data', outbreak_data.get('outbreaks', [])))
            
            print(f"📊 Found {len(entries)} outbreak entries")
            
            # Show first few outbreak titles
            print("\n📋 Sample outbreak titles:")
            for i, entry in enumerate(entries[:5], 1):
                title = entry.get('Title', entry.get('title', 'Unknown'))
                print(f"   {i}. {title}")
            
        else:
            print("❌ No data returned from WHO API")
            return
        
        # Test 2: Check specific countries
        test_countries = ['Zimbabwe', 'India', 'USA', 'United States']
        
        for country in test_countries:
            print(f"\n2️⃣ Testing outbreak detection for: {country}")
            
            # Create test user with this country
            test_user_id = f"test_user_{country.lower().replace(' ', '_')}"
            save_user_country(test_user_id, country, 'test')
            
            # Check outbreaks for this user
            outbreaks = check_disease_outbreaks_for_user(test_user_id)
            
            if outbreaks:
                print(f"✅ Found {len(outbreaks)} relevant outbreak(s) for {country}:")
                for outbreak in outbreaks:
                    print(f"   🚨 {outbreak.get('disease', 'Unknown')}: {outbreak.get('title', 'No title')}")
            else:
                print(f"❌ No outbreaks found for {country}")
        
        # Test 3: Check what countries ARE mentioned in outbreaks
        print(f"\n3️⃣ Analyzing which countries/regions are mentioned in current outbreaks...")
        
        mentioned_countries = set()
        for entry in entries:
            title = entry.get('Title', entry.get('title', ''))
            summary = entry.get('Summary', entry.get('summary', ''))
            overview = entry.get('Overview', entry.get('overview', ''))
            
            content = f"{title} {summary} {overview}".lower()
            
            # Check for common country names
            common_countries = [
                'china', 'india', 'usa', 'united states', 'brazil', 'russia',
                'nigeria', 'south africa', 'zimbabwe', 'kenya', 'uganda',
                'congo', 'sudan', 'yemen', 'syria', 'afghanistan', 'pakistan'
            ]
            
            for country in common_countries:
                if country in content:
                    mentioned_countries.add(country)
        
        print(f"📍 Countries/regions mentioned in current outbreaks:")
        for country in sorted(mentioned_countries):
            print(f"   • {country.title()}")

def main():
    """Run the direct WHO API test"""
    print("🦠 WHO Disease Outbreak News API Direct Test")
    print("=" * 60)
    
    test_who_api_direct()
    
    print("\n" + "=" * 60)
    print("🎉 WHO API direct test completed!")

if __name__ == "__main__":
    main() 