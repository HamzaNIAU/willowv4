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
        """Query the universal integrations system for enabled Pinterest accounts."""
        try:
            from services.supabase import DBConnection
            from services.unified_integration_service import UnifiedIntegrationService
            db = DBConnection()
            integration_service = UnifiedIntegrationService(db)

            if self.agent_id == "suna-default":
                integrations = await integration_service.get_user_integrations(self.user_id, platform="pinterest")
            else:
                integrations = await integration_service.get_agent_integrations(self.agent_id, self.user_id, platform="pinterest")

            accounts = []
            for integ in integrations:
                pdata = integ.get("platform_data", {})
                accounts.append({
                    "id": integ["platform_account_id"],
                    "name": integ.get("cached_name") or integ["name"],
                    "username": pdata.get("username"),
                    "profile_picture": integ.get("cached_picture") or integ.get("picture"),
                    "subscriber_count": pdata.get("follower_count", 0),
                    "view_count": pdata.get("monthly_views", 0),
                    "video_count": pdata.get("pin_count", 0),
                    "country": pdata.get("country")
                })

            if accounts:
                return True, accounts, ""

            if self.agent_id == "suna-default":
                return False, [], "❌ **No Pinterest accounts connected**\n\nPlease connect a Pinterest account in Social Media settings."
            else:
                return False, [], "❌ **No Pinterest accounts enabled**\n\nPlease enable at least one account in the MCP connections dropdown (⚙️ button)."
        except Exception as e:
            logger.error(f"Universal integrations query failed (Pinterest): {e}")
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
            
            # Format accounts for UI parity with YouTube
            formatted_accounts = []
            for acc in accounts:
                formatted_accounts.append({
                    "id": acc["id"],
                    "name": acc["name"],
                    "username": acc.get("username"),
                    "profile_picture": acc.get("profile_picture"),
                    "subscriber_count": acc.get("subscriber_count", 0),
                    "view_count": acc.get("view_count", 0),
                    "video_count": acc.get("video_count", 0)
                })

            # Human-readable summary (also used by the left chat)
            summary = "📌 **Pinterest Accounts:**\\n\\n"
            for acc in accounts:
                handle = acc.get('username', acc['id'])
                summary += f"• **{acc['name']}** ({handle})\\n"

            return self.success_response({
                "accounts": formatted_accounts,
                "count": len(formatted_accounts),
                "message": summary,
                "has_accounts": True,
                "single_account": len(formatted_accounts) == 1
            })
            
        except Exception as e:
            return self.fail_response(f"Error: {str(e)}")

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "pinterest_account_boards",
            "description": "List boards for a Pinterest account",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "Pinterest account ID"}
                },
                "required": ["account_id"]
            }
        }
    })
    async def pinterest_account_boards(self, account_id: str) -> ToolResult:
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/pinterest/boards/{account_id}"
                headers = {"Authorization": f"Bearer {self.jwt_token}"}
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status != 200:
                        return self.fail_response(f"Failed to get boards: HTTP {resp.status} {await resp.text()}")
                    data = await resp.json()
                    return self.success_response({
                        "account_id": account_id,
                        "boards": data.get("boards", []),
                        "count": data.get("count", 0)
                    })
        except Exception as e:
            logger.error(f"[Pinterest MCP] Boards error: {e}")
            return self.fail_response(str(e))

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "pinterest_create_pin",
            "description": "Create a Pinterest pin on a board",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string"},
                    "board_id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "link": {"type": "string"}
                },
                "required": ["account_id", "title"]
            }
        }
    })
    async def pinterest_create_pin(self, account_id: str, title: str, description: str = "", link: str = "", board_id: str = "") -> ToolResult:
        try:
            payload = {
                "account_id": account_id,
                "board_id": board_id or "board_123",
                "title": title,
                "description": description,
                "link": link or None,
            }
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/pinterest/pin/create"
                headers = {"Authorization": f"Bearer {self.jwt_token}", "Content-Type": "application/json"}
                async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        return self.fail_response(f"Failed to create pin: HTTP {resp.status} {await resp.text()}")
                    result = await resp.json()
                    return self.success_response({
                        "pin_id": result.get("pin_id"),
                        "pin_url": result.get("pin_url"),
                        "title": title,
                        "description": description,
                        "account_id": account_id,
                        "board_id": payload["board_id"],
                        "status": "completed",
                        "message": result.get("message", "Pinterest pin created successfully")
                    })
        except Exception as e:
            logger.error(f"[Pinterest MCP] Create pin error: {e}")
            return self.fail_response(str(e))

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "pinterest_pin_status",
            "description": "Check the status of a Pinterest pin (lightweight placeholder)",
            "parameters": {
                "type": "object",
                "properties": {
                    "pin_id": {"type": "string"},
                    "pin_url": {"type": "string"}
                },
                "required": ["pin_id"]
            }
        }
    })
    async def pinterest_pin_status(self, pin_id: str, pin_url: str = "") -> ToolResult:
        try:
            # Placeholder status (API not implemented yet)
            return self.success_response({
                "pin_id": pin_id,
                "pin_url": pin_url or f"https://www.pinterest.com/pin/{pin_id}/",
                "status": "available",
                "message": "Pin is available"
            })
        except Exception as e:
            return self.fail_response(str(e))

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "pinterest_recent_pins",
            "description": "Get recent pins for an account (mock/demo)",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": ["account_id"]
            }
        }
    })
    async def pinterest_recent_pins(self, account_id: str, limit: int = 10) -> ToolResult:
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/pinterest/pins/{account_id}/recent?limit={limit}"
                headers = {"Authorization": f"Bearer {self.jwt_token}"}
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status != 200:
                        return self.fail_response(f"Failed to fetch recent pins: HTTP {resp.status} {await resp.text()}")
                    data = await resp.json()
                    return self.success_response({
                        "account_id": account_id,
                        "pins": data.get("pins", []),
                        "count": data.get("count", 0)
                    })
        except Exception as e:
            logger.error(f"[Pinterest MCP] Recent pins error: {e}")
            return self.fail_response(str(e))
