"""Test Twitter Integration End-to-End"""

import asyncio
import os
import json
from datetime import datetime
from services.supabase import DBConnection
from twitter_mcp.oauth import TwitterOAuthHandler
from twitter_mcp.accounts import TwitterAccountService
from twitter_mcp.twitter_service import TwitterAPIService
from twitter_mcp.upload import TwitterUploadService
from agent.tools.twitter_complete_mcp_tool import TwitterTool
from utils.logger import logger


async def test_twitter_oauth_flow():
    """Test Twitter OAuth configuration and URL generation"""
    print("🔧 Testing Twitter OAuth Configuration...")
    
    try:
        db = DBConnection()
        await db.initialize()
        
        oauth_handler = TwitterOAuthHandler(db)
        
        # Test auth URL generation
        auth_url, code_verifier, state = oauth_handler.get_auth_url("test_state")
        
        assert auth_url.startswith("https://twitter.com/i/oauth2/authorize"), "Invalid OAuth URL"
        assert "code_challenge" in auth_url, "Missing PKCE code challenge"
        assert "client_id" in auth_url, "Missing client ID"
        assert len(code_verifier) > 0, "Empty code verifier"
        assert len(state) > 0, "Empty state"
        
        print(f"✅ OAuth URL generated successfully")
        print(f"   URL: {auth_url[:100]}...")
        print(f"   State: {state}")
        print(f"   Code Verifier: {code_verifier[:20]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ OAuth test failed: {e}")
        return False


async def test_twitter_service_initialization():
    """Test Twitter API service initialization"""
    print("🔧 Testing Twitter API Service...")
    
    try:
        db = DBConnection()
        await db.initialize()
        
        # Test service initialization
        twitter_service = TwitterAPIService(db)
        assert twitter_service.BASE_URL == "https://api.twitter.com/2", "Wrong API base URL"
        assert twitter_service.UPLOAD_URL == "https://upload.twitter.com/1.1/media/upload.json", "Wrong upload URL"
        
        print("✅ Twitter API Service initialized successfully")
        return True
        
    except Exception as e:
        print(f"❌ Twitter service test failed: {e}")
        return False


async def test_twitter_account_service():
    """Test Twitter account management service"""
    print("🔧 Testing Twitter Account Service...")
    
    try:
        db = DBConnection()
        await db.initialize()
        
        account_service = TwitterAccountService(db)
        
        # Test getting accounts for non-existent user (should return empty)
        test_user_id = "00000000-0000-0000-0000-000000000000"
        accounts = await account_service.get_user_accounts(test_user_id)
        
        assert isinstance(accounts, list), "Accounts should be a list"
        assert len(accounts) == 0, "Should have no accounts for test user"
        
        print("✅ Twitter Account Service working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Account service test failed: {e}")
        return False


async def test_twitter_upload_service():
    """Test Twitter upload service initialization"""
    print("🔧 Testing Twitter Upload Service...")
    
    try:
        db = DBConnection()
        await db.initialize()
        
        upload_service = TwitterUploadService(db)
        
        # Test that service components are initialized
        assert upload_service.oauth_handler is not None, "OAuth handler not initialized"
        assert upload_service.twitter_service is not None, "Twitter service not initialized"
        
        print("✅ Twitter Upload Service initialized successfully")
        return True
        
    except Exception as e:
        print(f"❌ Upload service test failed: {e}")
        return False


async def test_twitter_tool_initialization():
    """Test Twitter MCP tool initialization"""
    print("🔧 Testing Twitter MCP Tool...")
    
    try:
        test_user_id = "00000000-0000-0000-0000-000000000000"
        test_agent_id = "test-agent"
        
        # Test tool initialization
        twitter_tool = TwitterTool(
            user_id=test_user_id,
            agent_id=test_agent_id,
            account_ids=[],
            account_metadata=[]
        )
        
        assert twitter_tool.user_id == test_user_id, "Wrong user ID"
        assert twitter_tool.agent_id == test_agent_id, "Wrong agent ID"
        assert twitter_tool.base_url.endswith("/api"), "Wrong base URL"
        
        print("✅ Twitter MCP Tool initialized successfully")
        print(f"   User ID: {twitter_tool.user_id}")
        print(f"   Agent ID: {twitter_tool.agent_id}")
        print(f"   Base URL: {twitter_tool.base_url}")
        
        return True
        
    except Exception as e:
        print(f"❌ Twitter tool test failed: {e}")
        return False


async def test_environment_variables():
    """Test that required environment variables are configured"""
    print("🔧 Testing Environment Variables...")
    
    required_vars = [
        "TWITTER_CLIENT_ID",
        "TWITTER_CLIENT_SECRET", 
        "TWITTER_REDIRECT_URI",
        "MCP_CREDENTIAL_ENCRYPTION_KEY"
    ]
    
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            print(f"✅ {var}: {'*' * min(len(value), 20)}")
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("   Please configure these in your .env file:")
        for var in missing_vars:
            print(f"   {var}=your_value_here")
        return False
    
    print("✅ All required environment variables are configured")
    return True


async def test_database_schema():
    """Test that Twitter database tables exist"""
    print("🔧 Testing Database Schema...")
    
    try:
        db = DBConnection()
        await db.initialize()
        client = await db.client
        
        # Test that Twitter tables exist
        tables_to_check = [
            "twitter_accounts",
            "twitter_oauth_sessions", 
            "twitter_tweets"
        ]
        
        for table_name in tables_to_check:
            try:
                # Try to query the table (should not error even if empty)
                result = await client.table(table_name).select("*").limit(0).execute()
                print(f"✅ Table '{table_name}' exists and is accessible")
            except Exception as e:
                print(f"❌ Table '{table_name}' error: {e}")
                return False
        
        print("✅ All Twitter database tables are accessible")
        return True
        
    except Exception as e:
        print(f"❌ Database schema test failed: {e}")
        return False


async def run_all_tests():
    """Run all Twitter integration tests"""
    print("🐦 **TWITTER INTEGRATION TEST SUITE**")
    print("=" * 50)
    
    tests = [
        ("Environment Variables", test_environment_variables),
        ("Database Schema", test_database_schema),
        ("OAuth Configuration", test_twitter_oauth_flow),
        ("Twitter API Service", test_twitter_service_initialization),
        ("Account Service", test_twitter_account_service),
        ("Upload Service", test_twitter_upload_service),
        ("MCP Tool", test_twitter_tool_initialization),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        print("-" * 30)
        
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("🎯 **TEST RESULTS SUMMARY**")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("-" * 50)
    print(f"Total Tests: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed/len(results)*100):.1f}%")
    
    if failed == 0:
        print("\n🎉 **ALL TESTS PASSED!** Twitter integration is ready.")
    else:
        print(f"\n⚠️  **{failed} TESTS FAILED.** Please fix the issues above.")
    
    return failed == 0


if __name__ == "__main__":
    import asyncio
    
    # Suppress some logs for cleaner output
    import logging
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    try:
        result = asyncio.run(run_all_tests())
        exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n❌ Tests interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n💥 Test suite crashed: {e}")
        exit(1)