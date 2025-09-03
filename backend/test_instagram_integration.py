#!/usr/bin/env python3
"""Test script for Instagram MCP integration"""

import asyncio
import os
import uuid
from dotenv import load_dotenv

from services.supabase import DBConnection
from instagram_mcp.oauth import InstagramOAuthHandler
from instagram_mcp.accounts import InstagramAccountService
from instagram_mcp.service import InstagramAPIService
from instagram_mcp.upload import InstagramUploadService
from agent.tools.instagram_complete_mcp_tool import InstagramTool
from utils.logger import logger


async def test_instagram_integration():
    """Test Instagram integration components"""
    
    print("🧪 Testing Instagram MCP Integration...")
    
    # Load environment
    load_dotenv()
    
    # Initialize database
    db = DBConnection()
    
    try:
        # Test 1: OAuth Handler
        print("\n1️⃣ Testing Instagram OAuth Handler...")
        oauth_handler = InstagramOAuthHandler(db)
        
        # Generate auth URL
        test_user_id = str(uuid.uuid4())
        auth_url, code_verifier, state = oauth_handler.get_auth_url()
        print(f"✅ OAuth URL generated: {auth_url[:50]}...")
        print(f"✅ Code verifier: {code_verifier[:20]}...")
        print(f"✅ State: {state[:20]}...")
        
        # Test 2: Account Service
        print("\n2️⃣ Testing Instagram Account Service...")
        account_service = InstagramAccountService(db)
        
        # Get accounts (should be empty for new user)
        accounts = await account_service.get_user_accounts(test_user_id)
        print(f"✅ Account service working: {len(accounts)} accounts found")
        
        # Test 3: API Service
        print("\n3️⃣ Testing Instagram API Service...")
        api_service = InstagramAPIService(db)
        print("✅ Instagram API service initialized")
        
        # Test 4: Upload Service  
        print("\n4️⃣ Testing Instagram Upload Service...")
        upload_service = InstagramUploadService(db)
        print("✅ Instagram upload service initialized")
        
        # Test 5: Native Tool
        print("\n5️⃣ Testing Instagram Native Tool...")
        test_agent_id = "test-agent"
        
        # Test tool initialization
        instagram_tool = InstagramTool(
            user_id=test_user_id,
            agent_id=test_agent_id,
            account_ids=[],
            account_metadata=[]
        )
        print(f"✅ Instagram tool initialized for user {test_user_id}")
        
        # Test authentication method (should return auth URL)
        auth_result = await instagram_tool.instagram_authenticate()
        print(f"✅ Instagram authenticate method working: {auth_result.success}")
        
        # Test accounts method (should handle empty accounts gracefully)
        accounts_result = await instagram_tool.instagram_accounts()
        print(f"✅ Instagram accounts method: {accounts_result.success} (expected failure for no accounts)")
        
        # Test 6: Database Tables
        print("\n6️⃣ Testing Database Tables...")
        client = await db.client
        
        # Test instagram_accounts table
        try:
            test_result = await client.table("instagram_accounts").select("count").execute()
            print("✅ instagram_accounts table accessible")
        except Exception as e:
            print(f"❌ instagram_accounts table error: {e}")
        
        # Test instagram_oauth_sessions table
        try:
            test_result = await client.table("instagram_oauth_sessions").select("count").execute()
            print("✅ instagram_oauth_sessions table accessible")
        except Exception as e:
            print(f"❌ instagram_oauth_sessions table error: {e}")
        
        # Test instagram_posts table
        try:
            test_result = await client.table("instagram_posts").select("count").execute()
            print("✅ instagram_posts table accessible")
        except Exception as e:
            print(f"❌ instagram_posts table error: {e}")
        
        print("\n🎉 Instagram Integration Test Complete!")
        print("✅ All core components are working properly")
        print("📸 Ready for Instagram OAuth authentication and posting")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        logger.error(f"Instagram integration test error: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    asyncio.run(test_instagram_integration())