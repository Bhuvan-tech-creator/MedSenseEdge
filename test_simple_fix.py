#!/usr/bin/env python3
"""
Simple test to verify both fixes: Zimbabwe detection + user ID handling
"""

import os
import sys
import asyncio
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
from services.medical_agent import get_medical_agent_system
from models.database import init_database
from models.user import save_user_profile, get_user_country

# Create Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
init_database()

async def test_complete_fix():
    """Test both Zimbabwe detection and user ID handling"""
    
    print("\n🔧 Complete Fix Test: Zimbabwe + User ID")
    print("=" * 60)
    
    with app.app_context():
        # Check API keys
        gemini_key = app.config.get('GEMINI_API_KEY')
        
        print("\n📋 API Keys Status:")
        print(f"   GEMINI_API_KEY: {'✅ Loaded' if gemini_key else '❌ Missing'} ({len(gemini_key) if gemini_key else 0} chars)")
        
        if not gemini_key:
            print("\n❌ Missing GEMINI_API_KEY! Check your .env file")
            return
        
        # Set up test user with a UNIQUE ID
        test_user_id = "fix_test_zimbabwe_user_123"
        save_user_profile(test_user_id, age=25, gender='male', platform='test')
        print(f"\n👤 Test user created: {test_user_id}")
        
        # FIRST: Test country detection in message processor (simulate message processing)
        print(f"\n1️⃣ Testing country detection in message processor...")
        
        from services.external_apis import detect_and_save_country_from_text
        test_message = "I'm in Zimbabwe and have fever and headache"
        detected_country = detect_and_save_country_from_text(test_user_id, test_message, 'test')
        
        if detected_country:
            print(f"✅ Country detected and saved: {detected_country}")
            
            # Verify it was saved
            saved_country = get_user_country(test_user_id)
            print(f"💾 Country in database: {saved_country}")
            
            if saved_country == detected_country:
                print("✅ Country detection and saving working!")
            else:
                print(f"❌ Country detection mismatch: detected '{detected_country}' but saved '{saved_country}'")
        else:
            print("❌ Country detection failed")
            return
        
        # SECOND: Test the agent with the same user ID
        print(f"\n2️⃣ Testing medical agent with user ID: {test_user_id}")
        
        agent_system = get_medical_agent_system()
        
        try:
            # Call agent with the SAME user ID that has the country saved
            result = await agent_system.analyze_medical_query(
                user_id=test_user_id,  # This MUST match the user ID used above
                message=test_message,
                image_data=None,
                location=None,
                emergency=False
            )
            
            if result.get("success"):
                response = result.get("analysis", "No analysis available")
                
                print("\n📤 Agent Response:")
                print("-" * 40)
                print(response[:500] + "..." if len(response) > 500 else response)
                print("-" * 40)
                
                # Check specific issues
                checks = {
                    "Outbreak tool used": "check_disease_outbreaks" in result.get("tools_used", []),
                    "WHO section present": "Disease Outbreak Alert Check" in response,
                    "Zimbabwe mentioned": "Zimbabwe" in response,
                    "Found outbreaks OR no outbreaks message": any(phrase in response for phrase in ["outbreak", "alert", "No current disease outbreak", "No active disease outbreaks"])
                }
                
                print("\n🔍 Fix Verification:")
                for check, passed in checks.items():
                    status = "✅" if passed else "❌"
                    print(f"   {status} {check}")
                
                # Check tools used
                tools_used = result.get("tools_used", [])
                print(f"\n🔧 Tools used: {tools_used}")
                
                # Most important check: Did it avoid the "No country set for user user_id" error?
                if "No country set for user user_id" not in response:
                    print("\n🎉 SUCCESS: No 'user_id' error detected!")
                    print("✅ User ID handling appears to be fixed!")
                else:
                    print("\n❌ FAILED: Still seeing 'user_id' error")
                    
            else:
                print(f"\n❌ Agent returned error: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"\n❌ Exception: {e}")
            import traceback
            traceback.print_exc()

def main():
    """Run the complete fix test"""
    print("🧪 Complete Fix Test - Zimbabwe Detection + User ID Handling")
    print("=" * 70)
    
    asyncio.run(test_complete_fix())
    
    print("\n" + "=" * 70)
    print("🎉 Complete fix test completed!")

if __name__ == "__main__":
    main() 