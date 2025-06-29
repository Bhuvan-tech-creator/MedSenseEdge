#!/usr/bin/env python3
"""
Test the medical agent with location mentions to trigger WHO Disease Outbreak News
"""

import os
import sys
import asyncio
from pathlib import Path

# Load environment variables from .env file FIRST
from dotenv import load_dotenv
env_path = Path('.') / '.env'
if env_path.exists():
    print(f"📁 Loading environment from {env_path}")
    load_dotenv(env_path)
else:
    print("⚠️ No .env file found")

# Now set up Flask
os.environ['FLASK_APP'] = 'app.py'

from flask import Flask
from config import Config
from services.medical_agent import get_medical_agent_system
from models.database import init_database
from models.user import save_user_profile

# Create Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
init_database()

async def test_agent_with_location():
    """Test the medical agent with location mentions to trigger outbreak tools"""
    
    print("\n🌍 Medical Agent Test WITH Location Mentions")
    print("=" * 60)
    
    with app.app_context():
        # Check API keys
        gemini_key = app.config.get('GEMINI_API_KEY')
        
        print("\n📋 API Keys Status:")
        print(f"   GEMINI_API_KEY: {'✅ Loaded' if gemini_key else '❌ Missing'} ({len(gemini_key) if gemini_key else 0} chars)")
        
        if not gemini_key:
            print("\n❌ Missing GEMINI_API_KEY! Check your .env file")
            return
        
        # Set up test user
        test_user_id = "location_test_user"
        save_user_profile(test_user_id, age=28, gender='female', platform='test')
        print(f"\n👤 Test user created: {test_user_id}")
        
        # Get agent system
        agent_system = get_medical_agent_system()
        
        # Test queries WITH location mentions to trigger WHO outbreak tool
        test_queries = [
            "I'm in Zimbabwe and have fever and headache",
            "I live in India and feel nauseous and tired", 
            "Here in USA I'm experiencing chills and body aches",
            "I am in South Africa and have stomach pain"
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n{'='*60}")
            print(f"🌍 Test {i}: '{query}'")
            print(f"{'='*60}")
            
            try:
                # Call agent directly
                result = await agent_system.analyze_medical_query(
                    user_id=test_user_id,
                    message=query,
                    image_data=None,
                    location=None,
                    emergency=False
                )
                
                if result.get("success"):
                    response = result.get("analysis", "No analysis available")
                    
                    print("\n📤 Agent Response:")
                    print("-" * 60)
                    print(response)
                    print("-" * 60)
                    
                    # Check for WHO outbreak tool usage
                    outbreak_indicators = {
                        "Outbreak tool used": "Disease Outbreak Alert Check" in response,
                        "WHO mentioned": "WHO" in response or "World Health" in response,
                        "Outbreak data": any(term in response.lower() for term in ['outbreak', 'epidemic', 'pandemic', 'disease alert']),
                        "Country detection": any(country in response for country in ['Zimbabwe', 'India', 'USA', 'South Africa']),
                        "Location processed": "No location provided" not in response
                    }
                    
                    print("\n🔍 WHO Outbreak Tool Check:")
                    for check, found in outbreak_indicators.items():
                        status = "✅" if found else "❌"
                        print(f"   {status} {check}")
                        
                    # Check tools used
                    tools_used = result.get("tools_used", [])
                    print(f"\n🔧 Tools used: {tools_used}")
                    if "check_disease_outbreaks" in tools_used:
                        print("   ✅ WHO Disease Outbreak News tool was used!")
                    else:
                        print("   ⚠️ WHO Disease Outbreak News tool was NOT used")
                        
                    # Check if country was auto-detected and saved
                    from models.user import get_user_country
                    saved_country = get_user_country(test_user_id)
                    print(f"\n🌍 Auto-detected country: {saved_country or 'None'}")
                        
                else:
                    print(f"\n❌ Agent returned error: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"\n❌ Exception: {e}")
                import traceback
                traceback.print_exc()
            
            # Small delay between tests
            await asyncio.sleep(2)

def main():
    """Run the location-based test"""
    print("🌍 MedSenseEdge WHO Disease Outbreak News Test")
    print("=" * 60)
    
    # Test agent with location mentions
    asyncio.run(test_agent_with_location())
    
    print("\n" + "=" * 60)
    print("🎉 Location-based test completed!")
    print("✅ Check above for WHO Disease Outbreak News tool usage")

if __name__ == "__main__":
    main() 