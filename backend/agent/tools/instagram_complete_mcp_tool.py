"""Instagram Complete MCP Tool - Native Instagram Integration"""

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


class InstagramTool(Tool):
    """Complete Instagram integration tool following MCP pattern"""
    
    def __init__(self, user_id: str, account_ids: Optional[List[str]] = None, account_metadata: Optional[List[Dict[str, Any]]] = None, jwt_token: Optional[str] = None, agent_id: Optional[str] = None, thread_id: Optional[str] = None, **kwargs):
        super().__init__()
        self.user_id = user_id
        self.account_ids = account_ids or []
        self.agent_id = agent_id
        self.thread_id = thread_id
        
        # Use provided JWT token or create one
        self.jwt_token = jwt_token or self._create_jwt_token()
        
        # Backend URL configuration - Use Docker service name for worker network
        backend_url = os.getenv("BACKEND_URL", "http://backend:8000")
        self.base_url = backend_url + "/api"
        
        # Account metadata for quick reference
        self.account_metadata = {acc['id']: acc for acc in account_metadata} if account_metadata else {}
        self._has_accounts = len(self.account_ids) > 0
        
        logger.info(f"[Instagram MCP] Initialized for user {user_id}, agent {agent_id}")
        logger.info(f"[Instagram MCP] Account metadata: {len(self.account_metadata)} accounts")
        logger.info(f"[Instagram MCP] Base URL: {self.base_url}")
    
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
        """Real-time: Direct database query - NO CACHE DEPENDENCIES"""
        try:
            logger.info(f"🟠 REAL-TIME: Querying database directly for Instagram accounts, agent {self.agent_id}")
            
            # Real-time: Direct database access instead of HTTP/cache  
            from services.supabase import DBConnection
            db = DBConnection()
            client = await db.client
            
            # Special handling for suna-default virtual agent
            if self.agent_id == "suna-default":
                logger.info(f"[Instagram MCP] Using agent_social_accounts for suna-default agent (respects MCP toggles)")
                # Query agent_social_accounts to respect MCP toggle state for suna-default
                result = await client.table("agent_social_accounts").select("""
                    account_id, account_name, enabled,
                    instagram_accounts!inner(id, username, name, biography, profile_picture_url, account_type, followers_count, following_count, media_count)
                """).eq("agent_id", "suna-default").eq(
                    "user_id", self.user_id
                ).eq("platform", "instagram").eq("enabled", True).execute()
                
                if result.data:
                    accounts = []
                    for account in result.data:
                        ig_data = account["instagram_accounts"]
                        accounts.append({
                            "id": ig_data["id"],
                            "username": ig_data.get("username", ""),
                            "name": ig_data.get("name", ""),
                            "biography": ig_data.get("biography", ""),
                            "profile_picture_url": ig_data.get("profile_picture_url"),
                            "account_type": ig_data.get("account_type", "PERSONAL"),
                            "followers_count": ig_data.get("followers_count", 0),
                            "following_count": ig_data.get("following_count", 0),
                            "media_count": ig_data.get("media_count", 0)
                        })
                    logger.info(f"✅ Found {len(accounts)} ENABLED Instagram accounts for suna-default (respecting MCP toggles)")
                    for acc in accounts:
                        logger.info(f"  ✅ MCP Enabled: {acc['name']} (@{acc['username']})")
                    return True, accounts, ""
                else:
                    logger.info(f"❌ No enabled Instagram accounts found for suna-default (check MCP toggles)")
                    error_msg = (
                        "❌ **No Instagram accounts enabled**\\n\\n"
                        "Please enable Instagram accounts in the Social Media dropdown"
                    )
                    return False, [], error_msg
            
            # For other agents, check direct social accounts
            else:
                result = await client.table("agent_social_accounts").select("*").eq(
                    "agent_id", self.agent_id
                ).eq("user_id", self.user_id).eq("platform", "instagram").eq("enabled", True).execute()
                
                if result.data:
                    accounts = [
                        {
                            "id": row["account_id"],
                            "username": row["username"],
                            "name": row["account_name"],
                            "biography": row["biography"],
                            "profile_picture_url": row["profile_picture_url"],
                            "account_type": row["account_type"],
                            "followers_count": row["followers_count"],
                            "following_count": row["following_count"],
                            "media_count": row["media_count"]
                        } for row in result.data
                    ]
                    return True, accounts, ""
                else:
                    error_msg = f"❌ No Instagram accounts enabled for agent {self.agent_id}"
                    return False, [], error_msg
            
        except Exception as e:
            logger.error(f"[Instagram MCP] Database query error: {e}")
            error_msg = f"Failed to check Instagram accounts: {str(e)}"
            return False, [], error_msg
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "instagram_authenticate",
            "description": "FIRST ACTION - Connect Instagram account via OAuth when no accounts are connected",
            "parameters": {
                "type": "object",
                "properties": {
                    "check_existing": {
                        "type": "boolean", 
                        "description": "Check for existing accounts before showing OAuth (default: true)"
                    }
                },
                "required": []
            }
        }
    })
    async def instagram_authenticate(self, check_existing: bool = True) -> ToolResult:
        """Authenticate Instagram account - complete MCP pattern"""
        try:
            logger.info(f"[Instagram MCP] Authentication requested, check_existing: {check_existing}")
            
            # Check existing accounts if requested
            has_accounts, accounts, error_msg = await self._check_enabled_accounts()
            
            if check_existing and has_accounts:
                logger.info(f"[Instagram MCP] Found {len(accounts)} existing accounts, returning account list")
                return self.success_response({
                    "message": f"🟠 **Instagram accounts already connected**\\n\\nYou have {len(accounts)} Instagram account(s) connected. Use instagram_accounts() to view them.",
                    "accounts": accounts,
                    "has_existing_accounts": True,
                    "skip_auth": True
                })
            
            # No existing accounts found, proceed with authentication
            
            # Get auth URL from backend
            async with aiohttp.ClientSession() as session:
                request_data = {}
                if self.thread_id:
                    request_data['thread_id'] = self.thread_id
                
                response = await session.post(
                    f"{self.base_url}/instagram/auth/initiate",
                    headers={"Authorization": f"Bearer {self.jwt_token}", "Content-Type": "application/json"},
                    json=request_data,
                    timeout=aiohttp.ClientTimeout(total=15)
                )
                
                if response.status == 200:
                    data = await response.json()
                    auth_url = data.get("auth_url")
                    
                    return self.success_response({
                        "message": "🔗 **Connect Your Instagram Account**\\n\\nClick the button below to connect your Instagram account.",
                        "auth_url": auth_url,
                        "button_text": "Connect Instagram Account",
                        "existing_accounts": accounts if check_existing and has_accounts else []
                    })
                else:
                    error_text = await response.text()
                    return self.fail_response(f"Failed to initiate authentication: {error_text}")
                    
        except Exception as e:
            logger.error(f"[Instagram MCP] Authentication error: {e}")
            return self.fail_response(f"Authentication failed: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "instagram_accounts",
            "description": "INSTANT ACTION - Shows all connected Instagram accounts with stats immediately",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_analytics": {
                        "type": "boolean",
                        "description": "Include detailed analytics (default: false)"
                    }
                },
                "required": []
            }
        }
    })
    async def instagram_accounts(self, include_analytics: bool = False) -> ToolResult:
        """Get Instagram accounts - complete MCP pattern"""
        try:
            has_accounts, accounts, error_msg = await self._check_enabled_accounts()
            
            if not has_accounts:
                return self.fail_response(error_msg)
            
            # Format accounts for frontend (preserve original response format)
            formatted_accounts = []
            for acc in accounts:
                formatted_accounts.append({
                    "id": acc["id"],
                    "username": acc.get("username"),
                    "name": acc["name"],
                    "biography": acc.get("biography"),
                    "profile_picture_url": acc.get("profile_picture_url"),
                    "account_type": acc.get("account_type", "PERSONAL"),
                    "followers_count": acc.get("followers_count", 0),
                    "following_count": acc.get("following_count", 0),
                    "media_count": acc.get("media_count", 0)
                })
            
            summary_text = f"📸 **Instagram Accounts for this Agent**\\n\\n"
            summary_text += f"Found {len(accounts)} enabled account(s):\\n\\n"
            
            for account in accounts:
                summary_text += f"**{account['name']}**\\n"
                if account.get('username'):
                    summary_text += f"   • @{account['username']}\\n"
                summary_text += f"   • {account.get('followers_count', 0):,} followers\\n"
                summary_text += f"   • {account.get('media_count', 0):,} posts\\n"
                if include_analytics:
                    summary_text += f"   • {account.get('following_count', 0):,} following\\n"
                    summary_text += f"   • Account type: {account.get('account_type', 'PERSONAL')}\\n"
                    if account.get('biography'):
                        summary_text += f"   • Bio: {account['biography'][:50]}...\\n"
                summary_text += "\\n"
            
            return self.success_response({
                "accounts": formatted_accounts,
                "count": len(formatted_accounts),
                "message": summary_text,
                "has_accounts": True,
                "single_account": len(accounts) == 1
            })
            
        except Exception as e:
            logger.error(f"[Instagram MCP] Error fetching accounts: {e}")
            return self.fail_response(f"Failed to get accounts: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "instagram_create_post", 
            "description": "PREFERRED ACTION - Create an Instagram post when accounts are connected. Auto-selects enabled account and handles media upload with progress tracking. Use this for all Instagram post requests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Instagram account ID (optional - auto-selects if one enabled)"
                    },
                    "caption": {
                        "type": "string",
                        "description": "Post caption text (optional, max 2200 characters)"
                    },
                    "media_type": {
                        "type": "string",
                        "enum": ["IMAGE", "VIDEO", "CAROUSEL"],
                        "description": "Media type (auto-detected if not provided)"
                    },
                    "video_reference_id": {
                        "type": "string",
                        "description": "Video reference ID (auto-discovered if not provided)"
                    },
                    "image_reference_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Image reference IDs (auto-discovered if not provided)"
                    },
                    "auto_discover": {
                        "type": "boolean",
                        "description": "Auto-discover uploaded media files (default: true)"
                    }
                },
                "required": []
            }
        }
    })
    async def instagram_create_post(
        self,
        caption: str = "",
        account_id: Optional[str] = None,
        media_type: Optional[str] = None,
        video_reference_id: Optional[str] = None,
        image_reference_ids: Optional[List[str]] = None,
        auto_discover: bool = True
    ) -> ToolResult:
        """Create Instagram post - complete MCP pattern"""
        try:
            logger.info(f"[Instagram MCP] Creating post with caption: '{caption[:50]}...'")
            
            # Check enabled accounts
            has_accounts, accounts, error_msg = await self._check_enabled_accounts()
            
            if not has_accounts:
                return self.fail_response(error_msg)
            
            # Auto-select account if not specified
            if not account_id:
                if len(accounts) == 1:
                    account_id = accounts[0]["id"]
                    account_name = accounts[0]["name"]
                    logger.info(f"[Instagram MCP] Auto-selected single account: {account_name}")
                else:
                    account_list = "\\n".join([f"• {acc['name']} (@{acc['username']}) - ID: {acc['id']}" for acc in accounts])
                    return self.fail_response(
                        f"Multiple Instagram accounts available. Please specify account_id:\\n\\n{account_list}"
                    )
            else:
                # Validate specified account
                selected_account = next((acc for acc in accounts if acc["id"] == account_id), None)
                if not selected_account:
                    return self.fail_response(f"Instagram account {account_id} not found or not enabled")
                account_name = selected_account["name"]
            
            # Prepare post data
            post_data = {
                "account_id": account_id,
                "caption": caption,
                "auto_discover": auto_discover
            }
            
            if media_type:
                post_data["media_type"] = media_type
            if video_reference_id:
                post_data["video_reference_id"] = video_reference_id
            if image_reference_ids:
                post_data["image_reference_ids"] = image_reference_ids
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                response = await session.post(
                    f"{self.base_url}/instagram/post",
                    headers={"Authorization": f"Bearer {self.jwt_token}", "Content-Type": "application/json"},
                    json=post_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                )
                
                if response.status == 200:
                    data = await response.json()
                    
                    post_record_id = data.get("post_record_id")
                    discovered_files = data.get("discovered_files", [])
                    
                    response_message = f"📸 **Instagram Post Started!**\\n\\n"
                    response_message += f"**Account:** {account_name}\\n"
                    response_message += f"**Caption:** {caption[:100]}{'...' if len(caption) > 100 else ''}\\n\\n"
                    
                    if discovered_files:
                        response_message += f"**Auto-discovered files:**\\n"
                        for file in discovered_files:
                            response_message += f"• {file['name']} ({file['type']})\\n"
                        response_message += "\\n"
                    
                    response_message += f"**Status:** {data.get('status', 'posting')}\\n"
                    response_message += f"Post is being created in the background...\\n\\n"
                    response_message += f"*Track ID: {post_record_id}*"
                    
                    return self.success_response({
                        "post_record_id": post_record_id,
                        "account_name": account_name,
                        "account_username": selected_account.get("username", ""),
                        "status": data.get("status", "posting"),
                        "message": response_message,
                        "media_count": data.get("media_count", 0),
                        "discovered_files": discovered_files,
                        "automatic_discovery": data.get("automatic_discovery", False)
                    })
                else:
                    error_text = await response.text()
                    return self.fail_response(f"Failed to create Instagram post: {error_text}")
                    
        except Exception as e:
            logger.error(f"[Instagram MCP] Post creation error: {e}")
            return self.fail_response(f"Failed to create Instagram post: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "instagram_create_story",
            "description": "Create an Instagram Story with auto-discovery",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Instagram account ID (optional - auto-selects if one enabled)"
                    },
                    "auto_discover": {
                        "type": "boolean",
                        "description": "Auto-discover uploaded media files (default: true)"
                    }
                },
                "required": []
            }
        }
    })
    async def instagram_create_story(
        self,
        account_id: Optional[str] = None,
        auto_discover: bool = True
    ) -> ToolResult:
        """Create Instagram story - complete MCP pattern"""
        try:
            logger.info(f"[Instagram MCP] Creating story")
            
            # Check enabled accounts
            has_accounts, accounts, error_msg = await self._check_enabled_accounts()
            
            if not has_accounts:
                return self.fail_response(error_msg)
            
            # Auto-select account if not specified
            if not account_id:
                if len(accounts) == 1:
                    account_id = accounts[0]["id"]
                    account_name = accounts[0]["name"]
                    logger.info(f"[Instagram MCP] Auto-selected single account: {account_name}")
                else:
                    account_list = "\\n".join([f"• {acc['name']} (@{acc['username']}) - ID: {acc['id']}" for acc in accounts])
                    return self.fail_response(
                        f"Multiple Instagram accounts available. Please specify account_id:\\n\\n{account_list}"
                    )
            else:
                # Validate specified account
                selected_account = next((acc for acc in accounts if acc["id"] == account_id), None)
                if not selected_account:
                    return self.fail_response(f"Instagram account {account_id} not found or not enabled")
                account_name = selected_account["name"]
            
            # Prepare story data
            story_data = {
                "account_id": account_id,
                "auto_discover": auto_discover
            }
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                response = await session.post(
                    f"{self.base_url}/instagram/story",
                    headers={"Authorization": f"Bearer {self.jwt_token}", "Content-Type": "application/json"},
                    json=story_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                )
                
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("success"):
                        story_id = data.get("story_id")
                        discovered_files = data.get("discovered_files", [])
                        
                        response_message = f"📱 **Instagram Story Posted!**\\n\\n"
                        response_message += f"**Account:** {account_name}\\n"
                        
                        if discovered_files:
                            response_message += f"**Media:** {discovered_files[0]['name']} ({discovered_files[0]['type']})\\n"
                        
                        response_message += f"**Story ID:** {story_id}\\n"
                        response_message += f"Story will be visible for 24 hours"
                        
                        return self.success_response({
                            "story_id": story_id,
                            "account_name": account_name,
                            "message": response_message,
                            "discovered_files": discovered_files
                        })
                    else:
                        return self.fail_response(data.get("error", "Story creation failed"))
                else:
                    error_text = await response.text()
                    return self.fail_response(f"Failed to create Instagram story: {error_text}")
                    
        except Exception as e:
            logger.error(f"[Instagram MCP] Story creation error: {e}")
            return self.fail_response(f"Failed to create Instagram story: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "instagram_get_posts",
            "description": "Get recent Instagram posts from connected accounts",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Instagram account ID (optional - shows all if not specified)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of posts to retrieve (default: 10, max: 25)"
                    }
                },
                "required": []
            }
        }
    })
    async def instagram_get_posts(
        self,
        account_id: Optional[str] = None,
        limit: int = 10
    ) -> ToolResult:
        """Get Instagram posts - complete MCP pattern"""
        try:
            # Check enabled accounts
            has_accounts, accounts, error_msg = await self._check_enabled_accounts()
            
            if not has_accounts:
                return self.fail_response(error_msg)
            
            # Use first account if not specified
            if not account_id:
                account_id = accounts[0]["id"]
                account_name = accounts[0]["name"]
            else:
                # Validate specified account
                selected_account = next((acc for acc in accounts if acc["id"] == account_id), None)
                if not selected_account:
                    return self.fail_response(f"Instagram account {account_id} not found or not enabled")
                account_name = selected_account["name"]
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                response = await session.get(
                    f"{self.base_url}/instagram/accounts/{account_id}/posts",
                    headers={"Authorization": f"Bearer {self.jwt_token}"},
                    params={"limit": min(limit, 25)},
                    timeout=aiohttp.ClientTimeout(total=15)
                )
                
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("success"):
                        posts = data.get("posts", [])
                        
                        response_message = f"📸 **Instagram Posts - {account_name}**\\n\\n"
                        response_message += f"Found {len(posts)} recent post(s):\\n\\n"
                        
                        for post in posts[:5]:  # Show first 5 posts
                            response_message += f"**{post.get('caption', 'No caption')[:50]}**\\n"
                            response_message += f"• Media type: {post.get('media_type', 'IMAGE')}\\n"
                            response_message += f"• Created: {post.get('created_at', 'Unknown')}\\n"
                            if post.get('media_url'):
                                response_message += f"• [View Post]({post['media_url']})\\n"
                            response_message += "\\n"
                        
                        if len(posts) > 5:
                            response_message += f"... and {len(posts) - 5} more posts"
                        
                        return self.success_response({
                            "posts": posts,
                            "count": len(posts),
                            "account_name": account_name,
                            "message": response_message
                        })
                    else:
                        return self.fail_response(data.get("error", "Failed to get posts"))
                else:
                    error_text = await response.text()
                    return self.fail_response(f"Failed to get Instagram posts: {error_text}")
                    
        except Exception as e:
            logger.error(f"[Instagram MCP] Get posts error: {e}")
            return self.fail_response(f"Failed to get Instagram posts: {str(e)}")