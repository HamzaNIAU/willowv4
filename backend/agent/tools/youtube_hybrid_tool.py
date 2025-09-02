"""YouTube Hybrid Tool - Follows Image Generation Tool Pattern"""

from typing import Optional, List, Dict, Any
from agentpress.tool import ToolResult, openapi_schema
from sandbox.tool_base import SandboxToolsBase
from agentpress.thread_manager import ThreadManager
import uuid
import tempfile
import os
from datetime import datetime, timezone
from utils.logger import logger

# Import YouTube API dependencies (same as backend)
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    build = None
    MediaFileUpload = None
    Credentials = None


class YouTubeTool(SandboxToolsBase):
    """YouTube hybrid tool - follows exact same pattern as image generation tool"""
    
    def __init__(self, project_id: str, thread_manager: ThreadManager, user_id: str, agent_id: Optional[str] = None, channel_metadata: Optional[List[Dict]] = None, access_tokens: Optional[Dict] = None, video_data: Optional[bytes] = None, jwt_token: Optional[str] = None, **kwargs):
        super().__init__(project_id, thread_manager)
        self.user_id = user_id
        self.agent_id = agent_id
        self.jwt_token = jwt_token
        
        # Stateless design - all data pre-fetched (like image tool)
        self.channel_metadata = channel_metadata or []
        self.access_tokens = access_tokens or {}  # Pre-fetched OAuth tokens
        self.video_data = video_data  # Pre-fetched video file data
        
        # No database connections needed (like image tool)
        logger.info(f"[YouTube Hybrid] Initialized stateless tool for user {user_id}")
        logger.info(f"[YouTube Hybrid] Pre-fetched data: {len(self.channel_metadata)} channels, {len(self.access_tokens)} tokens, video: {bool(self.video_data)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_upload_video",
            "description": "Upload video to YouTube using hybrid sandbox pattern with direct API calls",
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
                    "channel_id": {
                        "type": "string",
                        "description": "YouTube channel ID (optional - auto-selects if one enabled)"
                    },
                    "video_reference_id": {
                        "type": "string",
                        "description": "Video reference ID (optional - auto-discovers)"
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
        channel_id: Optional[str] = None,
        video_reference_id: Optional[str] = None
    ) -> ToolResult:
        """Upload video to YouTube - follows exact same pattern as image generation tool"""
        try:
            # STEP 1: Ensure sandbox (same as image tool)
            await self._ensure_sandbox()
            
            if not GOOGLE_API_AVAILABLE:
                return self.fail_response("Google API libraries not available")
            
            logger.info(f"[YouTube Hybrid] Starting upload: {title}")
            
            # STEP 2: Use pre-fetched channels (stateless like image tool)
            if not self.channel_metadata:
                return self.fail_response(
                    "❌ **No YouTube channels available**\\n\\n"
                    "Please connect YouTube channels first using `youtube_authenticate`."
                )
            
            # Auto-select channel if not specified
            if not channel_id:
                if len(self.channel_metadata) == 1:
                    channel_id = self.channel_metadata[0]["id"]
                    logger.info(f"[YouTube Hybrid] Auto-selected channel: {self.channel_metadata[0]['name']}")
                else:
                    # Multiple channels - return selection UI
                    channel_list = "\\n".join([f"• {ch['name']} ({ch['id']})" for ch in self.channel_metadata])
                    return self.success_response(
                        f"🎯 **Multiple channels available:**\\n\\n{channel_list}\\n\\n"
                        f"Please specify channel_id in your next upload call."
                    )
            
            # STEP 3: Use pre-fetched video data (stateless like image tool)
            if not self.video_data:
                return self.fail_response(
                    "❌ **No video file found**\\n\\n"
                    "Please attach a video file to your message before uploading."
                )
            
            # STEP 4: Save pre-fetched video to sandbox (like image tool)
            video_path = await self._save_video_to_sandbox(self.video_data)
            
            # STEP 5: Use pre-fetched OAuth token (stateless)
            access_token = self.access_tokens.get(channel_id)
            if not access_token:
                return self.fail_response(f"❌ **No OAuth token available for channel {channel_id}**")
            
            # STEP 6: Direct YouTube API call (like image tool calls OpenAI)
            video_id = await self._upload_to_youtube_api(video_path, title, description, privacy, access_token)
            
            # STEP 7: Clean up sandbox file
            await self.sandbox.fs.delete_file(video_path)
            
            # STEP 8: Agent sees immediate success (same as image tool)
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            return self.success_response(
                f"🎉 **YouTube Upload Successful!**\\n\\n"
                f"🎬 **Title**: {title}\\n"
                f"🔗 **YouTube URL**: {video_url}\\n"
                f"🆔 **Video ID**: {video_id}\\n\\n"
                f"✨ **Hybrid Execution**: Complete"
            )
            
        except Exception as e:
            # Agent sees immediate failure (same as image tool)
            logger.error(f"[YouTube Hybrid] Upload failed: {e}", exc_info=True)
            return self.fail_response(f"Upload failed: {str(e)}")
    
    # No database access methods needed - everything is pre-fetched!
    
    async def _save_video_to_sandbox(self, video_data: bytes) -> str:
        """Save video to sandbox workspace (same pattern as image tool)"""
        try:
            # Generate unique filename
            video_filename = f"upload_video_{uuid.uuid4().hex[:8]}.mp4"
            video_path = f"/workspace/{video_filename}"
            
            # Save to sandbox (exact same as image tool)
            await self.sandbox.fs.upload_file(video_data, video_path)
            
            logger.info(f"[YouTube Hybrid] Saved video to sandbox: {video_filename}")
            return video_path
            
        except Exception as e:
            logger.error(f"[YouTube Hybrid] Failed to save video to sandbox: {e}")
            raise Exception(f"Failed to prepare video file: {str(e)}")
    
    async def _upload_to_youtube_api(self, video_path: str, title: str, description: str, privacy: str, access_token: str) -> str:
        """Upload to YouTube API directly (like image tool calls OpenAI)"""
        try:
            # Create credentials
            credentials = Credentials(token=access_token)
            youtube = build('youtube', 'v3', credentials=credentials)
            
            # Prepare upload metadata
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'categoryId': '22'
                },
                'status': {
                    'privacyStatus': privacy,
                    'madeForKids': False
                }
            }
            
            # Create media upload
            media = MediaFileUpload(video_path, resumable=True, chunksize=1024*1024)
            
            # Execute upload with progress tracking
            insert_request = youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            response = None
            while response is None:
                status, response = insert_request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logger.info(f"[YouTube Hybrid] Upload progress: {progress}%")
            
            video_id = response['id']
            logger.info(f"[YouTube Hybrid] Upload successful: {video_id}")
            
            return video_id
            
        except Exception as e:
            logger.error(f"[YouTube Hybrid] YouTube API upload failed: {e}")
            raise Exception(f"YouTube upload failed: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_channels",
            "description": "Get YouTube channels via direct database access",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    })
    async def youtube_channels(self) -> ToolResult:
        """Get YouTube channels - stateless using pre-fetched data"""
        try:
            await self._ensure_sandbox()
            
            # Use pre-fetched channel data (stateless like image tool)
            if self.channel_metadata:
                message = f"📺 **Found {len(self.channel_metadata)} YouTube Channel(s):**\\n\\n"
                for channel in self.channel_metadata:
                    message += f"• **{channel['name']}** ({channel['id']})\\n"
                    message += f"  📊 {channel.get('subscriber_count', 0):,} subscribers\\n"
                    if channel.get('username'):
                        message += f"  🌐 @{channel['username']}\\n"
                    
                    # Show token availability
                    token_status = "✅ Token Ready" if channel['id'] in self.access_tokens else "❌ No Token"
                    message += f"  🔑 {token_status}\\n\\n"
                
                return self.success_response(message)
            else:
                return self.success_response(
                    "No YouTube channels available for this agent.\\n"
                    "Please enable channels in the MCP connections dropdown."
                )
                
        except Exception as e:
            logger.error(f"[YouTube Hybrid] Failed to get channels: {e}")
            return self.fail_response(f"Failed to get channels: {str(e)}")
    
    @openapi_schema({
        "type": "function", 
        "function": {
            "name": "youtube_check_recent_uploads",
            "description": "Check recent YouTube uploads via direct database access",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    })
    async def youtube_check_recent_uploads(self) -> ToolResult:
        """Check recent uploads - simplified for stateless pattern"""
        try:
            await self._ensure_sandbox()
            
            # For now, return simple message since we're focusing on upload functionality
            # This avoids database access complexity in sandbox
            return self.success_response(
                "📋 **Recent Uploads Check**\\n\\n"
                "This feature will show recent uploads. Currently focused on upload functionality.\\n"
                "Use the main upload feature to upload your videos!"
            )
                
        except Exception as e:
            logger.error(f"[YouTube Hybrid] Failed to check recent uploads: {e}")
            return self.fail_response(f"Error: {str(e)}")