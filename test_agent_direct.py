#!/usr/bin/env python3
"""
Direct test of the PubMed-focused medical agent
Tests PubMed search integration and citation formatting
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

async def test_pubmed_search_directly():
    """Test the enhanced PubMed search function directly"""
    print("\n🔬 Direct PubMed Search Test")
    print("=" * 60)
    
    with app.app_context():
        from services.external_apis import pubmed_search
        
        test_queries = [
            "headache nausea treatment",
            "fever chills diagnosis",
            "stomach pain causes"
        ]
        
        for query in test_queries:
            print(f"\n📚 Testing PubMed search: '{query}'")
            try:
                results = pubmed_search(query, 2)  # Get 2 articles
                
                if results and not results[0].get('error'):
                    for i, article in enumerate(results, 1):
                        print(f"\n📄 Article {i}:")
                        print(f"   Title: {article.get('title', 'N/A')[:80]}...")
                        print(f"   Journal: {article.get('journal', 'N/A')} ({article.get('year', 'N/A')})")
                        print(f"   Authors: {article.get('authors', 'N/A')}")
                        print(f"   PMID: {article.get('pmid', 'N/A')}")
                        print(f"   Link: {article.get('href', 'N/A')}")
                        
                        # Check if full text extraction worked
                        full_text = article.get('full_text_excerpt', '')
                        if full_text and full_text != "Full text not accessible":
                            print(f"   ✅ Full text extracted: {full_text[:100]}...")
                        else:
                            print(f"   ⚠️ Full text not accessible")
                        
                        print(f"   Abstract preview: {article.get('abstract', '')[:150]}...")
                else:
                    print(f"   ❌ Search failed: {results[0].get('error', 'Unknown error') if results else 'No results'}")
                    
            except Exception as e:
                print(f"   ❌ Exception: {e}")

async def test_medical_agent_pubmed():
    """Test the medical agent with PubMed focus"""
    
    print("\n🧪 PubMed-Focused Medical Agent Test")
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
        test_user_id = "pubmed_test_user"
        save_user_profile(test_user_id, age=30, gender='male', platform='test')
        print(f"\n👤 Test user created: {test_user_id}")
        
        # Get agent system
        agent_system = get_medical_agent_system()
        
        # Test queries focused on PubMed citations
        test_queries = [
            "I have a headache and feel nauseous",
            "I'm experiencing fever and chills", 
            "My stomach hurts and I feel tired"
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
                    
                    # Check for PubMed integration
                    pubmed_indicators = {
                        "PubMed links": "pubmed.ncbi.nlm.nih.gov" in response,
                        "Research mentions": any(term in response.lower() for term in ['research', 'study', 'published', 'clinical trial']),
                        "Journal citations": any(term in response.lower() for term in ['journal', 'jama', 'nejm', 'bmj']),
                        "Evidence-based": any(term in response.lower() for term in ['evidence', 'literature', 'peer-reviewed']),
                        "PMID mentions": 'pmid' in response.lower() or 'PMID' in response,
                        "Research sections": "Research-Based Analysis" in response or "Evidence Summary" in response
                    }
                    
                    print("\n🔍 PubMed Integration Check:")
                    for check, found in pubmed_indicators.items():
                        status = "✅" if found else "❌"
                        print(f"   {status} {check}")
                        
                    # Count PubMed links
                    pubmed_link_count = response.count("pubmed.ncbi.nlm.nih.gov")
                    print(f"\n📎 PubMed links found: {pubmed_link_count}")
                    
                    # Check tools used
                    tools_used = result.get("tools_used", [])
                    print(f"\n🔧 Tools used: {tools_used}")
                    if "web_search_medical" in tools_used:
                        print("   ✅ PubMed search tool was used!")
                    else:
                        print("   ⚠️ PubMed search tool was NOT used")
                        
                else:
                    print(f"\n❌ Agent returned error: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"\n❌ Exception: {e}")
                import traceback
                traceback.print_exc()
            
            # Small delay between tests
            await asyncio.sleep(2)

async def test_web_search_tool():
    """Test the web_search_medical tool directly"""
    print("\n🌐 Direct Web Search Tool Test")
    print("=" * 60)
    
    with app.app_context():
        from services.medical_tools import web_search_medical
        
        print("\n🔍 Testing web_search_medical tool...")
        result = web_search_medical.invoke({
            'query': 'headache nausea migraine',
            'max_results': 3
        })
        
        print("📊 Tool Result:")
        print(result)
        
        # Try to parse JSON result
        try:
            import json
            if isinstance(result, str):
                result_data = json.loads(result)
                search_results = result_data.get('search_results', [])
                print(f"\n✅ Found {len(search_results)} PubMed articles")
                
                for i, article in enumerate(search_results[:2], 1):
                    print(f"\nArticle {i}:")
                    print(f"  Title: {article.get('title', '')[:70]}...")
                    print(f"  URL: {article.get('href', '')}")
                    print(f"  Journal: {article.get('journal', 'Unknown')}")
            else:
                print("⚠️ Result is not JSON string format")
                
        except Exception as e:
            print(f"❌ Could not parse tool result: {e}")

def main():
    """Run all tests"""
    print("🏥 MedSenseEdge PubMed-Focused Agent Test")
    print("=" * 60)
    
    # Test PubMed search directly
    asyncio.run(test_pubmed_search_directly())
    
    # Test web search tool
    asyncio.run(test_web_search_tool())
    
    # Test agent
    asyncio.run(test_medical_agent_pubmed())
    
    print("\n" + "=" * 60)
    print("🎉 PubMed-focused agent test completed!")
    print("✅ Check above for PubMed links, citations, and research references")

if __name__ == "__main__":
    # First check if dotenv is installed
    try:
        import dotenv
    except ImportError:
        print("❌ python-dotenv not installed!")
        print("💡 Install it with: pip3 install python-dotenv")
        sys.exit(1)
    
    main() 