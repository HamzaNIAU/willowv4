"""Pinterest Complete MCP Tool - Following YouTube Pattern Exactly"""

import asyncio
import aiohttp
import json
import os
import re
import jwt
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
from agentpress.tool import Tool, ToolResult, openapi_schema
from utils.logger import logger


class PinterestTool(Tool):
    """Complete Pinterest integration tool following YouTube MCP pattern exactly"""
    
    def __init__(self, user_id: str, account_ids: Optional[List[str]] = None, account_metadata: Optional[List[Dict[str, Any]]] = None, jwt_token: Optional[str] = None, agent_id: Optional[str] = None, thread_id: Optional[str] = None, **kwargs):
        super().__init__()
        self.user_id = user_id
        self.account_ids = account_ids or []
        self.agent_id = agent_id
        self.thread_id = thread_id
        
        # Use provided JWT token or create one
        self.jwt_token = jwt_token or self._create_jwt_token()
        
        # Backend URL configuration - FIXED for Docker worker network
        backend_url = os.getenv("BACKEND_URL", "http://backend:8000")  # Use Docker service name
        self.base_url = backend_url + "/api"
        
        # Account metadata for quick reference
        self.account_metadata = {acc['id']: acc for acc in account_metadata} if account_metadata else {}
        self._has_accounts = len(self.account_ids) > 0
        
        logger.info(f"[Pinterest MCP] Initialized for user {user_id}, agent {agent_id}")
        logger.info(f"[Pinterest MCP] Account metadata: {len(self.account_metadata)} accounts")
        logger.info(f"[Pinterest MCP] Base URL: {self.base_url}")
    
    def _create_jwt_token(self) -> str:
        """Create a JWT token for API authentication"""
        jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
        if not jwt_secret:
            logger.warning("SUPABASE_JWT_SECRET not set, authentication may fail")
            return ""
        
        payload = {
            "sub": self.user_id,
            "user_id": self.user_id,
            "role": "authenticated"
        }
        
        return jwt.encode(payload, jwt_secret, algorithm="HS256")
    
    async def _check_enabled_accounts(self) -> tuple[bool, List[Dict[str, Any]], str]:
        """REAL-TIME: Direct database query - NO CACHE DEPENDENCIES (Following YouTube pattern)"""
        try:
            logger.info(f"🔴 REAL-TIME: Querying database directly for Pinterest agent {self.agent_id}")
            
            # REAL-TIME: Direct database access instead of HTTP/cache  
            from services.supabase import DBConnection
            db = DBConnection()
            client = await db.client
            
            # Special handling for suna-default virtual agent
            if self.agent_id == "suna-default":
                logger.info(f"[Pinterest MCP] Using agent_social_accounts for suna-default agent")
                result = await client.table("agent_social_accounts").select("*").eq(
                    "agent_id", "suna-default"
                ).eq("user_id", self.user_id).eq("platform", "pinterest").eq("enabled", True).execute()
                
                if result.data:
                    accounts = []
                    for account in result.data:
                        accounts.append({
                            "id": account["account_id"],
                            "name": account["account_name"],
                            "username": account.get("username", ""),
                            "profile_picture": account.get("profile_picture"),
                            "subscriber_count": account.get("subscriber_count", 0),
                            "view_count": account.get("view_count", 0),
                            "video_count": account.get("video_count", 0)
                        })
                    logger.info(f"✅ Found {len(accounts)} ENABLED Pinterest accounts for suna-default")
                    return True, accounts, ""
                else:
                    error_msg = (
                        "❌ **No Pinterest accounts enabled**\\n\\n"
                        "Please enable Pinterest accounts in the Social Media dropdown"
                    )
                    return False, [], error_msg
            
            # Regular agent - query agent_social_accounts
            result = await client.table("agent_social_accounts").select("*").eq(
                "agent_id", self.agent_id
            ).eq("user_id", self.user_id).eq("platform", "pinterest").eq("enabled", True).execute()
            
            accounts = []
            for account in result.data:
                accounts.append({
                    "id": account["account_id"],
                    "name": account["account_name"],
                    "username": account["username"],
                    "profile_picture": account["profile_picture"],
                    "subscriber_count": account["subscriber_count"],
                    "view_count": account["view_count"],
                    "video_count": account["video_count"],
                    "country": account["country"]
                })
            
            if accounts:
                return True, accounts, ""
            else:
                all_accounts_result = await client.table("agent_social_accounts").select("*").eq(
                    "agent_id", self.agent_id
                ).eq("user_id", self.user_id).eq("platform", "pinterest").execute()
                
                if all_accounts_result.data:
                    disabled_count = len(all_accounts_result.data)
                    return False, [], f"❌ **{disabled_count} Pinterest accounts connected but disabled**\\n\\nPlease enable at least one account in the MCP connections dropdown (⚙️ button)."
                else:
                    return False, [], "❌ **No Pinterest accounts connected**\\n\\nPlease connect a Pinterest account first using `pinterest_authenticate`."
                    
        except Exception as e:
            logger.error(f"🔴 REAL-TIME ERROR: Failed to query Pinterest accounts: {e}")
            return False, [], f"Error checking Pinterest accounts: {str(e)}"
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "pinterest_authenticate",
            "description": "ONLY call this if NO Pinterest accounts are connected. Check existing accounts first with pinterest_accounts before using this.",
            "parameters": {
                "type": "object",
                "properties": {
                    "check_existing": {
                        "type": "boolean",
                        "description": "Check if accounts are already connected before showing auth (default: true)"
                    }
                },
                "required": []
            }
        }
    })
    async def pinterest_authenticate(self, check_existing: bool = True) -> ToolResult:
        """Pinterest authentication - MCP pattern with complete OAuth flow"""
        try:
            # ALWAYS check existing accounts first to avoid unnecessary auth
            has_accounts, accounts, _ = await self._check_enabled_accounts()
            if has_accounts:
                logger.info(f"[Pinterest MCP] Authentication skipped - {len(accounts)} accounts already enabled")
                account_list = "\\n".join([f"• **{acc['name']}** (@{acc.get('username', acc['id'])})" for acc in accounts])
                return self.success_response({
                    "message": f"✅ **Pinterest Already Connected!**\\n\\n📌 **Available accounts:**\\n{account_list}\\n\\n💡 **Ready for pinning!** Use `pinterest_create_pin` to create pins.",
                    "existing_accounts": accounts,
                    "already_authenticated": True,
                    "skip_auth": True
                })
            
            # Get auth URL from backend
            async with aiohttp.ClientSession() as session:
                request_data = {}
                if self.thread_id:
                    request_data['thread_id'] = self.thread_id
                
                response = await session.post(
                    f"{self.base_url}/pinterest/auth/initiate",
                    headers={"Authorization": f"Bearer {self.jwt_token}", "Content-Type": "application/json"},
                    json=request_data,
                    timeout=aiohttp.ClientTimeout(total=15)
                )
                
                if response.status == 200:
                    data = await response.json()
                    auth_url = data.get("auth_url")
                    
                    return self.success_response({
                        "message": "🔗 **Connect Your Pinterest Account**\\n\\nClick the button below to connect your Pinterest account.",
                        "auth_url": auth_url,
                        "button_text": "Connect Pinterest Account"
                    })
                else:
                    error_text = await response.text()
                    return self.fail_response(f"Failed to initiate Pinterest authentication: {error_text}")
                    
        except Exception as e:
            logger.error(f"[Pinterest MCP] Authentication error: {e}")
            return self.fail_response(f"Pinterest authentication failed: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "pinterest_accounts",
            "description": "Show connected Pinterest accounts",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    })
    async def pinterest_accounts(self) -> ToolResult:
        """Get Pinterest accounts"""
        try:
            has_accounts, accounts, error_msg = await self._check_enabled_accounts()
            
            if not has_accounts:
                return self.fail_response(error_msg)
            
            message = f"📌 **Pinterest Accounts:**\\n\\n"
            for account in accounts:
                message += f"• **{account['name']}** ({account['id']})\\n"
            
            return self.success_response(message)
            
        except Exception as e:
            return self.fail_response(f"Error: {str(e)}")