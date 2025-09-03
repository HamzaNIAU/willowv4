"""TikTok Complete MCP Tool - Native TikTok Integration"""

from typing import Dict, Any, List, Optional
import asyncio
import aiohttp

from agentpress.tool import Tool, openapi_schema, usage_example, ToolResult
from services.supabase import get_db_connection
from tiktok_mcp.oauth import TikTokOAuthHandler
from utils.logger import logger


class TikTokCompleteMCPTool(Tool):
    """Complete TikTok integration with zero-questions protocol"""
    
    def __init__(self, user_id: str, tiktok_accounts: List[Dict[str, Any]] = None):
        super().__init__()
        self.user_id = user_id
        self.tiktok_accounts = tiktok_accounts or []
        self.db = get_db_connection()
        self.oauth_handler = TikTokOAuthHandler(self.db)
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "tiktok_authenticate",
            "description": "Connect your TikTok account - shows OAuth button to authorize video uploads",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    })
    @usage_example("""
    <function_calls>
    <invoke name="tiktok_authenticate">
    </invoke>
    </function_calls>
    """)
    async def tiktok_authenticate(self) -> ToolResult:
        """Zero-questions OAuth initiation"""
        try:
            # Check if already connected
            existing_accounts = await self.get_user_accounts()
            
            if existing_accounts:
                return self.success_response({
                    "message": f"Already connected to {len(existing_accounts)} TikTok account(s)",
                    "accounts": existing_accounts,
                    "status": "already_connected"
                })
            
            # Initiate OAuth flow
            oauth_result = await self.oauth_handler.initiate_auth(self.user_id)
            
            return self.success_response({
                "message": "Click the button below to connect your TikTok account",
                "oauth_url": oauth_result["auth_url"],
                "auth_required": True,
                "provider": "tiktok",
                "platform": "tiktok"
            })
            
        except Exception as e:
            logger.error(f"TikTok authentication failed: {e}")
            return self.fail_response(f"Authentication failed: {str(e)}")
    
    @openapi_schema({
        "type": "function", 
        "function": {
            "name": "tiktok_accounts",
            "description": "List connected TikTok accounts with user information",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    })
    @usage_example("""
    <function_calls>
    <invoke name="tiktok_accounts">
    </invoke>
    </function_calls>
    """)
    async def tiktok_accounts(self) -> ToolResult:
        """List connected TikTok accounts"""
        try:
            accounts = await self.get_user_accounts()
            
            if not accounts:
                return self.success_response({
                    "message": "No TikTok accounts connected. Use tiktok_authenticate() to connect your account.",
                    "accounts": [],
                    "count": 0
                })
            
            # Format accounts with TikTok-specific context
            formatted_accounts = []
            for account in accounts:
                formatted_account = {
                    "id": account["id"],
                    "username": account["username"],
                    "name": account["name"],
                    "profile_image_url": account["profile_image_url"],
                    "token_status": account["token_status"],
                    "platform": "tiktok",
                    "connected_at": account["created_at"]
                }
                
                formatted_accounts.append(formatted_account)
            
            return self.success_response({
                "message": f"Found {len(formatted_accounts)} connected TikTok account(s)",
                "accounts": formatted_accounts,
                "count": len(formatted_accounts),
                "platform": "tiktok"
            })
            
        except Exception as e:
            logger.error(f"Failed to get TikTok accounts: {e}")
            return self.fail_response(f"Failed to retrieve accounts: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "tiktok_upload_video",
            "description": "Upload a video to TikTok with intelligent auto-discovery of uploaded files",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Video title/caption (required)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Video description (optional)"
                    },
                    "account_id": {
                        "type": "string",
                        "description": "TikTok account ID (optional if only one account)"
                    },
                    "video_reference_id": {
                        "type": "string",
                        "description": "Reference ID for video file (optional, auto-discovered if not provided)"
                    },
                    "thumbnail_reference_id": {
                        "type": "string",
                        "description": "Reference ID for thumbnail file (optional, auto-discovered if not provided)"
                    },
                    "auto_discover": {
                        "type": "boolean",
                        "description": "Automatically find uploaded files if not specified",
                        "default": True
                    }
                },
                "required": ["title"]
            }
        }
    })
    @usage_example("""
    <function_calls>
    <invoke name="tiktok_upload_video">
    <parameter name="title">Check out this amazing dance routine! 💃</parameter>
    <parameter name="description">Been practicing this for weeks #dance #viral</parameter>
    </invoke>
    </function_calls>
    """)
    async def tiktok_upload_video(self, title: str, description: str = "",
                                 account_id: str = None, video_reference_id: str = None,
                                 thumbnail_reference_id: str = None,
                                 auto_discover: bool = True) -> ToolResult:
        """Zero-questions TikTok video upload with auto-discovery"""
        try:
            # Smart account selection
            if not account_id:
                available_accounts = await self.get_available_accounts()
                if len(available_accounts) == 1:
                    account_id = available_accounts[0]["id"]
                elif len(available_accounts) > 1:
                    account_names = [f"{acc['name']} (@{acc['username']})" for acc in available_accounts]
                    return self.fail_response(
                        f"Multiple TikTok accounts available: {', '.join(account_names)}. "
                        "Please specify account_id parameter."
                    )
                else:
                    return self.fail_response("No TikTok accounts connected. Use tiktok_authenticate() first.")
            
            # Validate required parameters
            if not title or not title.strip():
                return self.fail_response("Video title is required and cannot be empty.")
            
            # Auto-discover video file if not provided
            if auto_discover and not video_reference_id:
                try:
                    from services.youtube_file_service import YouTubeFileService
                    file_service = YouTubeFileService(self.db)
                    uploads = await file_service.get_latest_pending_uploads(self.user_id)
                    
                    if uploads.get("video"):
                        video_reference_id = uploads["video"]["reference_id"]
                        logger.info(f"Auto-discovered video: {video_reference_id}")
                        
                    if uploads.get("thumbnail") and not thumbnail_reference_id:
                        thumbnail_reference_id = uploads["thumbnail"]["reference_id"]
                        logger.info(f"Auto-discovered thumbnail: {thumbnail_reference_id}")
                except Exception as e:
                    logger.warning(f"Failed to auto-discover files: {e}")
            
            if not video_reference_id:
                return self.fail_response("No video file found. TikTok requires a video file. Please upload a video first.")
            
            # NOTE: TikTok API video upload implementation would go here
            # This is a simplified version due to TikTok's complex upload requirements
            return self.success_response({
                "message": f"TikTok video upload prepared: '{title}'",
                "title": title,
                "description": description,
                "video_reference_id": video_reference_id,
                "thumbnail_reference_id": thumbnail_reference_id,
                "platform": "tiktok",
                "note": "TikTok video upload API integration requires additional business verification. Please contact TikTok for Business API access."
            })
            
        except Exception as e:
            logger.error(f"TikTok video upload failed: {e}")
            return self.fail_response(f"Video upload failed: {str(e)}")
    
    async def get_user_accounts(self) -> List[Dict[str, Any]]:
        """Get TikTok accounts for user"""
        try:
            accounts = await self.db.fetch("""
                SELECT 
                    id, username, name, profile_image_url,
                    is_active, needs_reauth, token_expires_at,
                    created_at, updated_at
                FROM tiktok_accounts 
                WHERE user_id = $1 AND is_active = true
                ORDER BY created_at DESC
            """, self.user_id)
            
            formatted_accounts = []
            for account in accounts:
                # Check token status
                from datetime import datetime
                token_status = "valid"
                if account['needs_reauth']:
                    token_status = "needs_reauth"
                elif account['token_expires_at'] and account['token_expires_at'] <= datetime.utcnow():
                    token_status = "expired"
                
                formatted_accounts.append({
                    "id": account['id'],
                    "username": account['username'],
                    "name": account['name'],
                    "profile_image_url": account['profile_image_url'],
                    "token_status": token_status,
                    "created_at": account['created_at'].isoformat(),
                    "platform": "tiktok"
                })
            
            return formatted_accounts
            
        except Exception as e:
            logger.error(f"Failed to get TikTok accounts: {e}")
            return []
    
    async def get_available_accounts(self) -> List[Dict[str, Any]]:
        """Get available TikTok accounts for user"""
        try:
            # Use pre-computed accounts if available (from agent config)
            if self.tiktok_accounts:
                return self.tiktok_accounts
            
            # Fallback to database query
            accounts = await self.get_user_accounts()
            return [acc for acc in accounts if acc.get("token_status") == "valid"]
            
        except Exception as e:
            logger.error(f"Failed to get available TikTok accounts: {e}")
            return []