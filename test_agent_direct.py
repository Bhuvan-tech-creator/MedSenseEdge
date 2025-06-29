#!/usr/bin/env python3
"""
Direct test of the medical agent - bypasses Telegram/WhatsApp
Loads API keys from .env file properly
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

async def test_medical_agent_directly():
    """Test the medical agent directly with a medical query"""
    
    print("\n🧪 Direct Medical Agent Test")
    print("=" * 60)
    
    with app.app_context():
        # Check API keys
        rapidapi_key = app.config.get('RAPIDAPI_KEY')
        gemini_key = app.config.get('GEMINI_API_KEY')
        
        print("\n📋 API Keys Status:")
        print(f"   RAPIDAPI_KEY: {'✅ Loaded' if rapidapi_key else '❌ Missing'} ({len(rapidapi_key) if rapidapi_key else 0} chars)")
        print(f"   GEMINI_API_KEY: {'✅ Loaded' if gemini_key else '❌ Missing'} ({len(gemini_key) if gemini_key else 0} chars)")
        
        if not rapidapi_key or not gemini_key:
            print("\n❌ Missing API keys! Check your .env file")
            return
        
        # Set up test user
        test_user_id = "direct_test_user"
        save_user_profile(test_user_id, age=30, gender='male', platform='test')
        print(f"\n👤 Test user created: {test_user_id}")
        
        # Get agent system
        agent_system = get_medical_agent_system()
        
        # Test queries
        test_queries = [
            "I have a headache and my hand hurts",
            "I'm feeling tired and have a fever",
            "My stomach hurts and I feel nauseous"
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n{'='*60}")
            print(f"📨 Test {i}: '{query}'")
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
                    
                    # Check for medical database usage
                    if "Medical Database Validation" in response:
                        print("\n✅ Medical Database Validation FOUND!")
                        if "EndlessMedical" in response:
                            print("✅ Using EndlessMedical via RapidAPI")
                            
                            # Extract confidence if mentioned
                            import re
                            confidence_match = re.search(r'(\d+(?:\.\d+)?)\s*%', response)
                            if confidence_match:
                                print(f"✅ Confidence level: {confidence_match.group(0)}")
                    else:
                        print("\n⚠️ No Medical Database Validation in response")
                        
                else:
                    print(f"\n❌ Agent returned error: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"\n❌ Exception: {e}")
                import traceback
                traceback.print_exc()
            
            # Small delay between tests
            await asyncio.sleep(1)

async def test_medical_tools_directly():
    """Test the medical tools directly"""
    print("\n🔧 Direct Medical Tools Test")
    print("=" * 60)
    
    with app.app_context():
        from services.medical_tools import set_medical_features, analyze_medical_features
        
        print("\n1️⃣ Testing set_medical_features...")
        features_result = set_medical_features.invoke({
            'features': {
                'Age': '30',
                'HeadacheFrontal': '1',
                'JointsPain': '1',
                'MuscleGenPain': '1'
            },
            'age': 30,
            'gender': 'male'
        })
        print(f"Result: {features_result}")
        
        print("\n2️⃣ Testing analyze_medical_features...")
        analysis_result = analyze_medical_features.invoke({})
        print(f"Result: {analysis_result}")

def main():
    """Run all tests"""
    print("🏥 MedSenseEdge Direct Agent Test")
    print("=" * 60)
    
    # Test tools directly
    asyncio.run(test_medical_tools_directly())
    
    # Test agent
    asyncio.run(test_medical_agent_directly())
    
    print("\n" + "=" * 60)
    print("🎉 Test completed!")

if __name__ == "__main__":
    # First check if dotenv is installed
    try:
        import dotenv
    except ImportError:
        print("❌ python-dotenv not installed!")
        print("💡 Install it with: pip3 install python-dotenv")
        sys.exit(1)
    
    main() 