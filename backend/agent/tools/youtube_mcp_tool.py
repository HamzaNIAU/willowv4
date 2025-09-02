"""YouTube MCP-Style Tool - Simple and Efficient"""

import asyncio
import aiohttp
import os
from typing import Optional, Dict, Any
from agentpress.tool import Tool, ToolResult, openapi_schema
from utils.logger import logger


class YouTubeTool(Tool):
    """YouTube tool following MCP pattern - simple HTTP calls with agent visibility"""
    
    def __init__(self, user_id: str, agent_id: Optional[str] = None, jwt_token: Optional[str] = None, **kwargs):
        super().__init__()
        self.user_id = user_id
        self.agent_id = agent_id
        self.jwt_token = jwt_token
        self.backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        
        logger.info(f"[YouTube MCP] Initialized for user {user_id}, agent {agent_id}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_upload_video",
            "description": "Upload video to YouTube using MCP pattern - efficient with agent visibility",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Video title"
                    },
                    "description": {
                        "type": "string", 
                        "description": "Video description (optional)"
                    },
                    "privacy": {
                        "type": "string",
                        "enum": ["public", "private", "unlisted"],
                        "description": "Privacy setting (default: public)"
                    },
                    "context": {
                        "type": "string",
                        "description": "Context about the video for auto-metadata generation"
                    }
                },
                "required": ["title"]
            }
        }
    })
    async def youtube_upload_video(
        self,
        title: str,
        description: str = "",
        privacy: str = "public", 
        context: Optional[str] = None
    ) -> ToolResult:
        """Upload video to YouTube - follows MCP pattern for agent visibility"""
        try:
            logger.info(f"[YouTube MCP] Starting upload: {title}")
            
            # Enhance description if context provided
            if context and not description:
                description = f"🎬 {context}\\n\\nUploaded on {asyncio.get_event_loop().time()}"
            
            # STEP 1: Call existing working backend API (like MCPs call external servers)
            upload_result = await self._initiate_upload(title, description, privacy)
            
            if not upload_result.get('success'):
                return self.fail_response(f"❌ **Upload failed to start**: {upload_result.get('error', 'Unknown error')}")
            
            upload_id = upload_result.get('upload_id')
            if not upload_id:
                return self.fail_response("❌ **No upload ID received**")
            
            # STEP 2: Poll for completion (like MCPs handle async operations)  
            logger.info(f"[YouTube MCP] Polling for upload completion: {upload_id}")
            final_status = await self._poll_upload_completion(upload_id)
            
            # STEP 3: Return ToolResult based on final status (EXACT MCP pattern)
            if final_status.get('video_id'):
                video_url = f"https://www.youtube.com/watch?v={final_status['video_id']}"
                channel_name = final_status.get('channel', {}).get('name', 'YouTube')
                
                return self.success_response(
                    f"🎉 **YouTube Upload Successful!**\\n\\n"
                    f"🎬 **Title**: {title}\\n"
                    f"📺 **Channel**: {channel_name}\\n"
                    f"🔗 **YouTube URL**: {video_url}\\n"
                    f"🆔 **Video ID**: {final_status['video_id']}\\n\\n"
                    f"✨ **MCP Pattern**: Efficient execution"
                )
            elif final_status.get('error'):
                return self.fail_response(f"❌ **Upload failed**: {final_status['error']}")
            else:
                return self.success_response(
                    f"📤 **Upload Processing**\\n\\n"
                    f"🎬 **Title**: {title}\\n"
                    f"📤 **Upload ID**: {upload_id}\\n\\n"
                    f"Upload is processing in background. Video will be available shortly!"
                )
                
        except Exception as e:
            logger.error(f"[YouTube MCP] Upload exception: {e}", exc_info=True)
            return self.fail_response(f"❌ **Upload error**: {str(e)}")
    
    async def _initiate_upload(self, title: str, description: str, privacy: str) -> Dict[str, Any]:
        """Initiate upload via backend API (like MCP external call)"""
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.post(
                    f"{self.backend_url}/api/youtube/universal-upload",
                    headers={
                        "Authorization": f"Bearer {self.jwt_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "platform": "youtube",
                        "account_id": "auto",  # Auto-select enabled channel
                        "title": title,
                        "description": description,
                        "privacy_status": privacy,
                        "auto_discover": True  # Use reference system
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                )
                
                if response.status == 200:
                    data = await response.json()
                    return {"success": True, "upload_id": data.get('upload_id'), "data": data}
                else:
                    error_text = await response.text()
                    return {"success": False, "error": f"HTTP {response.status}: {error_text}"}
                    
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _poll_upload_completion(self, upload_id: str, max_attempts: int = 30) -> Dict[str, Any]:
        """Poll for upload completion (like MCP async operation polling)"""
        logger.info(f"[YouTube MCP] Polling upload status for {upload_id}")
        
        for attempt in range(max_attempts):
            try:
                async with aiohttp.ClientSession() as session:
                    response = await session.get(
                        f"{self.backend_url}/api/youtube/upload-status/{upload_id}",
                        headers={"Authorization": f"Bearer {self.jwt_token}"},
                        timeout=aiohttp.ClientTimeout(total=15)
                    )
                    
                    if response.status == 200:
                        status_data = await response.json()
                        
                        # Check if upload completed successfully  
                        if status_data.get('video', {}).get('video_id'):
                            logger.info(f"[YouTube MCP] Upload completed: {status_data['video']['video_id']}")
                            return status_data
                        elif status_data.get('status') == 'failed':
                            logger.error(f"[YouTube MCP] Upload failed: {status_data.get('message', 'Unknown error')}")
                            return {'error': status_data.get('message', 'Upload failed')}
                        elif status_data.get('status') in ['completed', 'uploaded']:
                            # Success but might not have video_id yet
                            logger.info(f"[YouTube MCP] Upload completed with status: {status_data.get('status')}")
                            return status_data
                        
                        # Still processing - continue polling
                        logger.debug(f"[YouTube MCP] Still processing, attempt {attempt + 1}/{max_attempts}")
                        
            except Exception as e:
                logger.warning(f"[YouTube MCP] Polling attempt {attempt + 1} failed: {e}")
                
            # Wait before next attempt (like MCP retry logic)
            await asyncio.sleep(10)
        
        # Polling timeout
        logger.warning(f"[YouTube MCP] Polling timed out after {max_attempts} attempts")
        return {'error': f'Upload status polling timed out after {max_attempts * 10} seconds'}
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_channels",
            "description": "Get YouTube channels via backend API",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    })
    async def youtube_channels(self) -> ToolResult:
        """Get YouTube channels - MCP pattern with backend API call"""
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.get(
                    f"{self.backend_url}/api/youtube/channels",
                    headers={"Authorization": f"Bearer {self.jwt_token}"},
                    timeout=aiohttp.ClientTimeout(total=15)
                )
                
                if response.status == 200:
                    data = await response.json()
                    channels = data.get('channels', [])
                    
                    if channels:
                        message = f"📺 **Found {len(channels)} YouTube Channel(s):**\\n\\n"
                        for channel in channels:
                            message += f"• **{channel['name']}** ({channel['id']})\\n"
                            message += f"  📊 {channel.get('subscriber_count', 0):,} subscribers\\n"
                            if channel.get('username'):
                                message += f"  🌐 @{channel['username']}\\n"
                            message += "\\n"
                        
                        return self.success_response(message)
                    else:
                        return self.success_response(
                            "No YouTube channels found.\\n"
                            "Use `youtube_authenticate` to connect channels."
                        )
                else:
                    error_text = await response.text()
                    return self.fail_response(f"Failed to get channels: HTTP {response.status}: {error_text}")
                    
        except Exception as e:
            logger.error(f"[YouTube MCP] Channels error: {e}")
            return self.fail_response(f"Error getting channels: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_authenticate", 
            "description": "Start YouTube OAuth authentication flow",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    })
    async def youtube_authenticate(self) -> ToolResult:
        """YouTube authentication - MCP pattern"""
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.post(
                    f"{self.backend_url}/api/youtube/auth/initiate",
                    headers={"Authorization": f"Bearer {self.jwt_token}"},
                    json={"thread_id": "agent_request"},
                    timeout=aiohttp.ClientTimeout(total=15)
                )
                
                if response.status == 200:
                    data = await response.json()
                    auth_url = data.get('auth_url')
                    
                    return self.success_response(
                        f"🔗 **Connect Your YouTube Account**\\n\\n"
                        f"Click here to authorize: {auth_url}\\n\\n"
                        f"After connecting, your channels will be available for uploads!"
                    )
                else:
                    error_text = await response.text() 
                    return self.fail_response(f"Authentication failed: {error_text}")
                    
        except Exception as e:
            return self.fail_response(f"Authentication error: {str(e)}")