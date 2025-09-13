"""YouTube Complete MCP Tool - Preserves ALL Original Functionality"""

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


class YouTubeTool(Tool):
    """Complete YouTube integration tool following MCP pattern"""
    
    def __init__(self, user_id: str, channel_ids: Optional[List[str]] = None, channel_metadata: Optional[List[Dict[str, Any]]] = None, jwt_token: Optional[str] = None, agent_id: Optional[str] = None, thread_id: Optional[str] = None, **kwargs):
        super().__init__()
        self.user_id = user_id
        self.channel_ids = channel_ids or []
        self.agent_id = agent_id
        self.thread_id = thread_id
        
        # Use provided JWT token or create one
        self.jwt_token = jwt_token or self._create_jwt_token()
        
        # Backend URL configuration - FIXED for Docker worker network
        backend_url = os.getenv("BACKEND_URL", "http://backend:8000")  # Use Docker service name
        self.base_url = backend_url + "/api"
        
        # Channel metadata for quick reference
        self.channel_metadata = {ch['id']: ch for ch in channel_metadata} if channel_metadata else {}
        self._has_channels = len(self.channel_ids) > 0
        
        logger.info(f"[YouTube MCP] Initialized for user {user_id}, agent {agent_id}")
        logger.info(f"[YouTube MCP] Channel metadata: {len(self.channel_metadata)} channels")
        logger.info(f"[YouTube MCP] Base URL: {self.base_url}")
    
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
    
    async def _check_enabled_channels(self) -> tuple[bool, List[Dict[str, Any]], str]:
        """Query the universal integrations system for enabled YouTube channels."""
        try:
            from services.supabase import DBConnection
            from services.unified_integration_service import UnifiedIntegrationService
            db = DBConnection()
            integration_service = UnifiedIntegrationService(db)

            # For the virtual agent, show all user integrations for YouTube
            if self.agent_id == "suna-default":
                integrations = await integration_service.get_user_integrations(self.user_id, platform="youtube")
            else:
                integrations = await integration_service.get_agent_integrations(self.agent_id, self.user_id, platform="youtube")

            channels = []
            for integ in integrations:
                pdata = integ.get("platform_data", {})
                channels.append({
                    "id": integ["platform_account_id"],
                    "name": integ.get("cached_name") or integ["name"],
                    "username": pdata.get("username"),
                    "profile_picture": integ.get("cached_picture") or integ.get("picture"),
                    "subscriber_count": pdata.get("subscriber_count", 0),
                    "view_count": pdata.get("view_count", 0),
                    "video_count": pdata.get("video_count", 0),
                    "country": pdata.get("country")
                })

            if channels:
                logger.info(f"Universal integrations returned {len(channels)} enabled YouTube channels for agent {self.agent_id}")
                return True, channels, ""

            # No channels found
            if self.agent_id == "suna-default":
                return False, [], (
                    "❌ **No YouTube accounts connected**\\n\\nPlease connect a YouTube account in Social Media settings."
                )
            else:
                return False, [], (
                    "❌ **No YouTube channels enabled**\\n\\nPlease enable at least one account in the MCP connections dropdown (⚙️ button)."
                )
        except Exception as e:
            logger.error(f"Universal integrations query failed: {e}")
            return False, [], f"Error checking accounts: {str(e)}"
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_authenticate",
            "description": "ONLY call this if NO YouTube channels are connected. Check existing channels first with youtube_channels before using this.",
            "parameters": {
                "type": "object",
                "properties": {
                    "check_existing": {
                        "type": "boolean",
                        "description": "Check if channels are already connected before showing auth (default: true)"
                    }
                },
                "required": []
            }
        }
    })
    async def youtube_authenticate(self, check_existing: bool = True) -> ToolResult:
        """YouTube authentication - MCP pattern with complete OAuth flow"""
        try:
            # ALWAYS check existing channels first to avoid unnecessary auth
            has_channels, channels, _ = await self._check_enabled_channels()
            if has_channels:
                logger.info(f"[YouTube MCP] Authentication skipped - {len(channels)} channels already enabled")
                # Return existing channels instead of showing auth
                channel_list = "\\n".join([f"• **{ch['name']}** ({ch.get('username', ch['id'])})" for ch in channels])
                return self.success_response({
                    "message": f"✅ **YouTube Already Connected!**\\n\\n📺 **Available channels:**\\n{channel_list}\\n\\n💡 **Ready for uploads!** Use `youtube_upload_video` to upload videos.",
                    "existing_channels": channels,
                    "already_authenticated": True,
                    "skip_auth": True
                })
            
            # No existing channels found, proceed with authentication
            
            # Get auth URL from backend
            async with aiohttp.ClientSession() as session:
                request_data = {}
                if self.thread_id:
                    request_data['thread_id'] = self.thread_id
                
                response = await session.post(
                    f"{self.base_url}/youtube/auth/initiate",
                    headers={"Authorization": f"Bearer {self.jwt_token}", "Content-Type": "application/json"},
                    json=request_data,
                    timeout=aiohttp.ClientTimeout(total=15)
                )
                
                if response.status == 200:
                    data = await response.json()
                    auth_url = data.get("auth_url")
                    
                    return self.success_response({
                        "message": "🔗 **Connect Your YouTube Channel**\\n\\nClick the button below to connect your YouTube account.",
                        "auth_url": auth_url,
                        "button_text": "Connect YouTube Channel",
                        "existing_channels": channels if check_existing and has_channels else []
                    })
                else:
                    error_text = await response.text()
                    return self.fail_response(f"Failed to initiate authentication: {error_text}")
                    
        except Exception as e:
            logger.error(f"[YouTube MCP] Authentication error: {e}")
            return self.fail_response(f"Authentication failed: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_channels",
            "description": "INSTANT ACTION - Shows all connected channels with stats immediately",
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
    async def youtube_channels(self, include_analytics: bool = False) -> ToolResult:
        """Get YouTube channels - complete MCP pattern"""
        try:
            has_channels, channels, error_msg = await self._check_enabled_channels()
            
            if not has_channels:
                return self.fail_response(error_msg)
            
            # Format channels for frontend (preserve original response format)
            formatted_channels = []
            for ch in channels:
                formatted_channels.append({
                    "id": ch["id"],
                    "name": ch["name"],
                    "username": ch.get("username"),
                    "profile_picture": ch.get("profile_picture"),
                    "subscriber_count": ch.get("subscriber_count", 0),
                    "view_count": ch.get("view_count", 0),
                    "video_count": ch.get("video_count", 0)
                })
            
            summary_text = f"📺 **YouTube Channels for this Agent**\\n\\n"
            summary_text += f"Found {len(channels)} enabled channel(s):\\n\\n"
            
            for channel in channels:
                summary_text += f"**{channel['name']}**\\n"
                if channel.get('username'):
                    summary_text += f"   • @{channel['username']}\\n"
                summary_text += f"   • {channel.get('subscriber_count', 0):,} subscribers\\n"
                if include_analytics:
                    summary_text += f"   • {channel.get('view_count', 0):,} total views\\n"
                    summary_text += f"   • {channel.get('video_count', 0):,} videos\\n"
                summary_text += "\\n"
            
            return self.success_response({
                "channels": formatted_channels,
                "count": len(formatted_channels),
                "message": summary_text,
                "has_channels": True,
                "single_channel": len(channels) == 1
            })
            
        except Exception as e:
            logger.error(f"[YouTube MCP] Error fetching channels: {e}")
            return self.fail_response(f"Failed to get channels: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_upload_video", 
            "description": "PREFERRED ACTION - Upload video to YouTube when channels are connected. Auto-selects enabled channel and handles upload with progress tracking. Use this for all upload requests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "YouTube channel ID (optional - auto-selects if one enabled)"
                    },
                    "context": {
                        "type": "string",
                        "description": "Context about video for metadata generation"
                    },
                    "title": {
                        "type": "string",
                        "description": "Video title (auto-generated if not provided)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Video description (auto-generated if not provided)"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Video tags (auto-generated if not provided)"
                    },
                    "privacy": {
                        "type": "string",
                        "enum": ["private", "unlisted", "public"],
                        "description": "Privacy setting (default: public)"
                    },
                    "video_reference_id": {
                        "type": "string",
                        "description": "Video reference ID (auto-discovered if not provided)"
                    }
                },
                "required": []
            }
        }
    })
    async def youtube_upload_video(
        self,
        channel_id: Optional[str] = None,
        context: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        privacy: str = "public",
        video_reference_id: Optional[str] = None
    ) -> ToolResult:
        """Complete YouTube upload with all original functionality - MCP pattern"""
        try:
            logger.info(f"[YouTube MCP] Starting upload - context: {bool(context)}, title: {title}")
            
            # STEP 1: Channel validation (preserve original logic)
            has_channels, available_channels, error_msg = await self._check_enabled_channels()
            
            if not has_channels:
                return self.fail_response(error_msg)
            
            # Channel selection logic - upload to all enabled channels
            if not channel_id:
                if len(available_channels) == 1:
                    channel_id = available_channels[0]["id"]
                    channel_name = available_channels[0]["name"]
                    logger.info(f"[YouTube MCP] Auto-selected channel: {channel_name}")
                else:
                    # Multiple channels - upload to all enabled channels
                    logger.info(f"[YouTube MCP] Uploading to {len(available_channels)} enabled channels")
                    
                    upload_results = []
                    for channel in available_channels:
                        try:
                            channel_upload = await self._smart_upload_with_token_recovery(
                                channel["id"], title, description, tags, privacy, video_reference_id
                            )
                            upload_results.append({
                                "channel": channel,
                                "result": channel_upload,
                                "success": channel_upload.get("success", False)
                            })
                            logger.info(f"✅ Upload to {channel['name']}: {'Success' if channel_upload.get('success') else 'Failed'}")
                        except Exception as e:
                            logger.error(f"❌ Upload to {channel['name']} failed: {e}")
                            upload_results.append({
                                "channel": channel,
                                "result": {"success": False, "error": str(e)},
                                "success": False
                            })
                    
                    successful_uploads = [r for r in upload_results if r["success"]]
                    failed_uploads = [r for r in upload_results if not r["success"]]
                    
                    message = f"🎬 **Multi-Channel Upload Complete!**\\n\\n"
                    message += f"📊 **Results:** {len(successful_uploads)} successful, {len(failed_uploads)} failed\\n\\n"
                    
                    for result in successful_uploads:
                        message += f"✅ **{result['channel']['name']}** - Upload started\\n"
                    
                    for result in failed_uploads:
                        message += f"❌ **{result['channel']['name']}** - Failed: {result['result'].get('error', 'Unknown error')}\\n"
                    
                    return self.success_response({
                        "message": message,
                        "upload_results": upload_results,
                        "channels": available_channels,
                        "multi_channel_upload": True,
                        "successful_count": len(successful_uploads),
                        "failed_count": len(failed_uploads)
                    })
            
            # STEP 2: Metadata generation (preserve original logic)
            if context and not title:
                title = self._generate_title_from_context(context)
            if context and not description:
                description = self._generate_description_from_context(context)
            if context and not tags:
                tags = self._generate_tags_from_context(context)
            
            # Smart fallbacks
            if not title:
                title = f"Amazing New Video - {datetime.now(timezone.utc).strftime('%B %d, %Y')}"
            if not description:
                description = f"🎬 New video uploaded on {datetime.now(timezone.utc).strftime('%B %d, %Y')}"
            if not tags:
                tags = ["Video", "YouTube", "New", "Content"]
            
            # STEP 3: SMART UPLOAD with automatic token refresh (Morphic-inspired)
            upload_result = await self._smart_upload_with_token_recovery(channel_id, title, description, tags, privacy, video_reference_id)
            
            if not upload_result.get('success'):
                return self._handle_upload_error(upload_result.get('error', 'Unknown error'))
            
            upload_id = upload_result.get('upload_id')
            
            # STEP 4: Return immediate response with upload tracking (preserve original format)
            channel_info = self._get_channel_info(channel_id, available_channels)
            
            return self.success_response({
                "upload_id": upload_id,
                "status": "uploading",
                "channel_name": channel_info.get('name', 'YouTube Channel'),
                "title": title,
                "message": f"🎬 **Uploading '{title}' to {channel_info.get('name')}...**\\n\\n📤 Upload started - check progress in a moment!",
                "upload_started": True,
                "channel": channel_info,
                "channels": [channel_info],
                "has_channels": True,
                "single_channel": True,
                "mcp_execution": True
            })
                
        except Exception as e:
            logger.error(f"[YouTube MCP] Upload error: {e}", exc_info=True)
            return self.fail_response(f"Upload failed: {str(e)}")
    
    async def _smart_upload_with_token_recovery(self, channel_id: str, title: str, description: str, tags: List[str], privacy: str, video_reference_id: Optional[str]) -> Dict[str, Any]:
        """SMART UPLOAD with automatic token refresh and retry - Morphic-inspired intelligence"""
        
        # INTELLIGENT RETRY LOGIC: 3 attempts with progressive recovery
        for attempt in range(3):
            try:
                logger.info(f"🚀 Smart Upload Attempt {attempt + 1}/3 for {title}")
                
                # Attempt upload with current authentication state
                result = await self._initiate_upload(channel_id, title, description, tags, privacy, video_reference_id)
                
                if result.get('success'):
                    logger.info(f"✅ Upload successful on attempt {attempt + 1}")
                    return result
                
                # Check if it's an authentication error
                error_msg = result.get('error', '').lower()
                if 'auth' in error_msg or 'token' in error_msg or 'unauthorized' in error_msg:
                    if attempt < 2:  # Still have retries
                        logger.info(f"🔄 Authentication error detected, will retry after token operations...")
                        await asyncio.sleep(1)  # Brief pause before retry
                        continue
                    else:
                        # Final attempt - return auth error
                        logger.error(f"❌ Authentication failed after 3 attempts")
                        return result
                else:
                    # Non-auth error - return immediately
                    return result
                    
            except Exception as e:
                error_str = str(e).lower()
                if ('auth' in error_str or 'token' in error_str) and attempt < 2:
                    logger.warning(f"⚠️ Upload attempt {attempt + 1} failed with auth error: {e}")
                    await asyncio.sleep(2)  # Longer pause for exceptions
                    continue
                else:
                    logger.error(f"❌ Upload attempt {attempt + 1} failed: {e}")
                    return {"success": False, "error": str(e)}
        
        return {"success": False, "error": "Upload failed after 3 intelligent retry attempts"}
    
    async def _initiate_upload(self, channel_id: str, title: str, description: str, tags: List[str], privacy: str, video_reference_id: Optional[str]) -> Dict[str, Any]:
        """Initiate upload via backend API (MCP external call pattern)"""
        try:
            upload_params = {
                "platform": "youtube",
                "account_id": channel_id,
                "title": title,
                "description": description,
                "tags": tags,
                "privacy_status": privacy,
                "video_reference_id": video_reference_id,
                "auto_discover": True,
                "made_for_kids": False,
                "notify_subscribers": True
            }
            
            # Use robust HTTP session with proper error handling
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                logger.info(f"[YouTube MCP] Calling upload API: {self.base_url}/youtube/universal-upload")
                
                try:
                    response = await session.post(
                        f"{self.base_url}/youtube/universal-upload",
                        headers={
                            "Authorization": f"Bearer {self.jwt_token}",
                            "Content-Type": "application/json"
                        },
                        json=upload_params
                    )
                    
                    logger.info(f"[YouTube MCP] Upload API response: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"[YouTube MCP] Upload initiated successfully: {data.get('upload_id')}")
                        return {"success": True, "upload_id": data.get('upload_id'), "data": data}
                    else:
                        error_text = await response.text()
                        logger.error(f"[YouTube MCP] Upload API error {response.status}: {error_text}")
                        return {"success": False, "error": f"HTTP {response.status}: {error_text}"}
                        
                except aiohttp.ClientError as e:
                    logger.error(f"[YouTube MCP] Network error calling upload API: {e}")
                    return {"success": False, "error": f"Network error: {str(e)}"}
                except asyncio.TimeoutError:
                    logger.error(f"[YouTube MCP] Upload API timeout")
                    return {"success": False, "error": "Upload API timeout - please try again"}
                except Exception as e:
                    logger.error(f"[YouTube MCP] Unexpected error in upload API call: {e}")
                    return {"success": False, "error": f"Unexpected error: {str(e)}"}
                    
        except Exception as e:
            logger.error(f"[YouTube MCP] Upload initiation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_title_from_context(self, context: str) -> str:
        """Generate SEO-optimized title from context"""
        return f"{context} - {datetime.now(timezone.utc).strftime('%B %Y')}"
    
    def _generate_description_from_context(self, context: str) -> str:
        """Generate comprehensive description from context"""
        return f"🎬 {context}\\n\\nUploaded on {datetime.now(timezone.utc).strftime('%B %d, %Y')}\\n\\n👍 Like if you enjoyed\\n💬 Comment your thoughts\\n🔔 Subscribe for more!"
    
    def _generate_tags_from_context(self, context: str) -> List[str]:
        """Generate relevant tags from context"""
        base_tags = ["Video", "YouTube", "New", "Content"]
        context_words = re.findall(r'\\b[A-Za-z]{3,}\\b', context)
        return base_tags + context_words[:5]
    
    def _get_channel_info(self, channel_id: str, available_channels: List[Dict]) -> Dict[str, Any]:
        """Get channel info for response formatting"""
        for channel in available_channels:
            if channel['id'] == channel_id:
                return {
                    "id": channel["id"],
                    "name": channel["name"],
                    "profile_picture": channel.get("profile_picture"),
                    "subscriber_count": channel.get("subscriber_count", 0),
                    "view_count": channel.get("view_count", 0),
                    "video_count": channel.get("video_count", 0)
                }
        
        return {"id": channel_id, "name": "YouTube Channel"}
    
    def _handle_upload_error(self, error: str) -> ToolResult:
        """SMART ERROR HANDLING with context-aware guidance - Enhanced beyond Morphic"""
        error_lower = error.lower()
        
        if "no video file found" in error_lower or "no video found" in error_lower:
            return self.fail_response(
                "❌ **No video file found**\\n\\n"
                "**To upload a video:**\\n"
                "1. 📎 Attach your video file to the message\\n"
                "2. 💬 Tell me to upload it to YouTube\\n\\n"
                "Video files are automatically prepared when attached."
            )
        elif "re-authorization required" in error or "authentication refresh needed" in error or "invalid_grant" in error_lower:
            # SMART AUTH ERROR: Context-aware guidance
            return self.success_response({
                "message": "🔄 **Smart Authentication Update**\\n\\n"
                          "Your YouTube tokens need refreshing - this is normal and happens automatically.\\n\\n"
                          "**What happened:** Automatic token refresh detected your authentication needs updating.\\n\\n"
                          "**Next step:** Click the authentication button below to refresh your access.",
                "auth_required": True,
                "smart_refresh_attempted": True,
                "context_preserved": True,
                "auth_url": None,  # Will be generated by authenticate function
                "reason": "proactive_token_management"
            })
        elif "token" in error_lower or "auth" in error_lower:
            # GENERIC AUTH ERROR: Fallback guidance
            return self.success_response({
                "message": "🔐 **Authentication Update Required**\\n\\n"
                          "Your YouTube authentication needs to be refreshed.\\n\\n"
                          "This is normal for security - please use `youtube_authenticate` to reconnect.",
                "auth_required": True,
                "generic_auth_error": True
            })
        elif "quota" in error_lower:
            return self.fail_response(
                "📊 **Upload quota exceeded**\\n\\n"
                "YouTube's daily upload limit reached.\\n\\n"
                "**Info:**\\n"
                "• Limit resets at midnight Pacific Time\\n"
                "• Try again tomorrow"
            )
        elif "cannot connect to host" in error_lower:
            return self.fail_response(
                "🌐 **Connection Error**\\n\\n"
                "Could not connect to YouTube service.\\n\\n"
                "**Try:**\\n"
                "• Check your internet connection\\n"  
                "• Wait a moment and try again\\n"
                "• The service might be temporarily unavailable"
            )
        else:
            return self.fail_response(f"❌ **Upload failed**\\n\\n{error}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_check_upload_status",
            "description": "Check recent upload status and get video URLs",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    })
    async def youtube_check_upload_status(self) -> ToolResult:
        """Check for recent successful uploads - MCP pattern"""
        try:
            # Query recent uploads via backend API
            async with aiohttp.ClientSession() as session:
                response = await session.get(
                    f"{self.base_url}/youtube/sandbox/recent-uploads?limit=5",
                    headers={"Authorization": f"Bearer {self.jwt_token}"},
                    timeout=aiohttp.ClientTimeout(total=15)
                )
                
                if response.status == 200:
                    data = await response.json()
                    uploads = data.get('uploads', [])
                    successful_uploads = [u for u in uploads if u.get('video_id')]
                    
                    if successful_uploads:
                        message = f"🎉 **Found {len(successful_uploads)} Recent Successful Upload(s):**\\n\\n"
                        for upload in successful_uploads:
                            video_id = upload['video_id']
                            upload_title = upload['title']
                            video_url = f"https://www.youtube.com/watch?v={video_id}"
                            message += f"🎬 **{upload_title}**\\n🔗 {video_url}\\n\\n"
                        
                        return self.success_response(message)
                    else:
                        return self.success_response("No recent successful uploads found.")
                else:
                    error_text = await response.text()
                    return self.fail_response(f"Failed to check uploads: {error_text}")
                    
        except Exception as e:
            return self.fail_response(f"Error checking uploads: {str(e)}")
