"""Universal Social Media Tool
Handles uploads to any social media platform through a unified interface
"""

import asyncio
import aiohttp
from typing import Dict, Any, List, Optional
from datetime import datetime

from agent.tools.base_tool import AgentBuilderBaseTool
from utils.agent_builder_tools import openapi_schema
from agentpress.tool import ToolResult
from utils.logger import logger


class UniversalSocialMediaTool(AgentBuilderBaseTool):
    """Universal tool for social media uploads across all platforms"""
    
    def __init__(self, jwt_token: str, user_id: str, base_url: str):
        super().__init__(jwt_token, user_id, base_url)
        self.supported_platforms = {
            'youtube': {
                'name': 'YouTube',
                'supports_video': True,
                'supports_image': False,
                'max_file_size_mb': 128000,
                'formats': ['mp4', 'mov', 'avi', 'wmv', 'flv', 'webm']
            },
            'tiktok': {
                'name': 'TikTok', 
                'supports_video': True,
                'supports_image': True,
                'max_file_size_mb': 2000,
                'formats': ['mp4', 'mov', 'avi']
            },
            'instagram': {
                'name': 'Instagram',
                'supports_video': True,
                'supports_image': True,
                'max_file_size_mb': 4000,
                'formats': ['mp4', 'mov', 'jpg', 'png']
            },
            'twitter': {
                'name': 'Twitter/X',
                'supports_video': True,
                'supports_image': True,
                'max_file_size_mb': 512,
                'formats': ['mp4', 'mov', 'jpg', 'png', 'gif']
            },
            'linkedin': {
                'name': 'LinkedIn',
                'supports_video': True,
                'supports_image': True,
                'max_file_size_mb': 5000,
                'formats': ['mp4', 'mov', 'jpg', 'png']
            }
        }
        
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "upload_to_social_media",
            "description": "Upload content to any social media platform (YouTube, TikTok, Instagram, Twitter, LinkedIn). Automatically detects attached files and provides platform-specific optimization.",
            "parameters": {
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "enum": ["youtube", "tiktok", "instagram", "twitter", "linkedin"],
                        "description": "The social media platform to upload to"
                    },
                    "account_id": {
                        "type": "string",
                        "description": "The account/channel ID on the platform. If not provided, will use the first available account."
                    },
                    "title": {
                        "type": "string",
                        "description": "Title/caption for the content"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description or additional text content"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags/hashtags for the content"
                    },
                    "privacy": {
                        "type": "string",
                        "enum": ["public", "private", "unlisted"],
                        "default": "public",
                        "description": "Privacy setting for the upload"
                    },
                    "schedule_for": {
                        "type": "string",
                        "description": "ISO datetime string for scheduled posting (optional)"
                    },
                    "video_reference_id": {
                        "type": "string",
                        "description": "Reference ID of uploaded video file. If not provided, will auto-discover recent uploads."
                    },
                    "thumbnail_reference_id": {
                        "type": "string", 
                        "description": "Reference ID of thumbnail image file (optional)"
                    },
                    "auto_discover": {
                        "type": "boolean",
                        "default": True,
                        "description": "Automatically find and use recently uploaded files if not specified"
                    }
                },
                "required": ["platform", "title"]
            }
        }
    })
    async def upload_to_social_media(
        self,
        platform: str,
        title: str,
        account_id: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        privacy: str = "public",
        schedule_for: Optional[str] = None,
        video_reference_id: Optional[str] = None,
        thumbnail_reference_id: Optional[str] = None,
        auto_discover: bool = True
    ) -> ToolResult:
        """Upload content to any social media platform"""
        
        try:
            platform = platform.lower()
            
            # Validate platform
            if platform not in self.supported_platforms:
                return self.fail_response(
                    f"❌ Platform '{platform}' is not supported.\n\n"
                    f"**Supported platforms:**\n" + 
                    "\n".join([f"• {info['name']}" for info in self.supported_platforms.values()])
                )
            
            platform_info = self.supported_platforms[platform]
            logger.info(f"[Universal Social Media] Starting upload to {platform_info['name']}")
            
            # Get user's accounts for this platform
            accounts = await self._get_platform_accounts(platform)
            if not accounts:
                return self.fail_response(
                    f"❌ **No {platform_info['name']} accounts connected**\n\n"
                    f"Please connect your {platform_info['name']} account first to upload content.\n\n"
                    f"**To connect an account:**\n"
                    f"1. Go to Settings → Social Media\n"
                    f"2. Click 'Connect {platform_info['name']}'\n"
                    f"3. Complete the authentication process"
                )
            
            # Auto-select account if not specified
            if not account_id:
                account_id = accounts[0]['platform_account_id']
                account_name = accounts[0]['display_name']
                logger.info(f"[Universal Social Media] Auto-selected account: {account_name}")
            else:
                account = next((acc for acc in accounts if acc['platform_account_id'] == account_id), None)
                if not account:
                    return self.fail_response(f"Account {account_id} not found for {platform_info['name']}")
                account_name = account['display_name']
            
            # Prepare upload parameters
            upload_params = {
                "platform": platform,
                "account_id": account_id,
                "account_name": account_name,
                "title": title,
                "description": description or "",
                "tags": tags or [],
                "privacy_status": privacy,
                "scheduled_for": schedule_for,
                "video_reference_id": video_reference_id,
                "thumbnail_reference_id": thumbnail_reference_id,
                "auto_discover": auto_discover,
                "notify_followers": True,
                "file_name": "auto-detected",  # Will be updated by file service
                "file_size": 0,  # Will be updated by file service
                "platform_settings": self._get_platform_specific_settings(platform),
                "platform_metadata": {
                    "upload_source": "agent_tool",
                    "agent_version": "universal_v1"
                }
            }
            
            # Call universal upload API
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.jwt_token}",
                    "Content-Type": "application/json"
                }
                
                async with session.post(
                    f"{self.base_url}/social-media/upload",
                    headers=headers,
                    json=upload_params
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"[Universal Social Media] Upload failed: {error_text}")
                        return self.fail_response(f"Upload failed: {error_text}")
                    
                    result = await response.json()
                    
                    if not result.get("success"):
                        return self.fail_response(f"Upload failed: {result.get('message', 'Unknown error')}")
                    
                    # Format success response
                    emoji = self._get_platform_emoji(platform)
                    platform_name = platform_info['name']
                    
                    success_message = f"{emoji} **Uploading '{title}' to {platform_name}...**\n\n"
                    success_message += f"📤 Upload started - progress will be tracked automatically!\n\n"
                    success_message += f"**Account:** {account_name}\n"
                    success_message += f"**Privacy:** {privacy.upper()}\n"
                    
                    if tags:
                        success_message += f"**Tags:** {len(tags)} tags added\n"
                    
                    if schedule_for:
                        success_message += f"**Scheduled:** {schedule_for}\n"
                    else:
                        success_message += f"**Status:** Publishing now\n"
                    
                    success_message += f"\n🎬 Your content will be live on {platform_name} shortly!"
                    
                    return self.success_response({
                        "message": success_message,
                        "upload_id": result["upload_id"],
                        "platform": platform,
                        "status": "uploading",
                        "upload_started": True,  # Flag for frontend progress bar
                        "channel": {
                            "id": account_id,
                            "name": account_name,
                            "platform": platform_name
                        },
                        "content": {
                            "title": title,
                            "description": description,
                            "privacy": privacy,
                            "tags": tags
                        },
                        "automatic_discovery": auto_discover and not video_reference_id
                    })
                    
        except Exception as e:
            logger.error(f"[Universal Social Media] Upload error: {e}", exc_info=True)
            return self.fail_response(f"Upload failed: {str(e)}")
    
    @openapi_schema({
        "type": "function", 
        "function": {
            "name": "get_social_media_accounts",
            "description": "List all connected social media accounts across platforms",
            "parameters": {
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "enum": ["youtube", "tiktok", "instagram", "twitter", "linkedin"],
                        "description": "Filter by specific platform (optional)"
                    }
                }
            }
        }
    })
    async def get_social_media_accounts(self, platform: Optional[str] = None) -> ToolResult:
        """Get all connected social media accounts"""
        
        try:
            accounts = await self._get_platform_accounts(platform)
            
            if not accounts:
                platform_text = f" {platform.upper()}" if platform else ""
                return self.success_response({
                    "accounts": [],
                    "message": f"📱 **No{platform_text} social media accounts connected**\n\n"
                             "Connect your accounts to start uploading content:\n"
                             "• YouTube\n• TikTok\n• Instagram\n• Twitter/X\n• LinkedIn"
                })
            
            # Group by platform
            grouped = {}
            for account in accounts:
                platform_key = account['platform']
                if platform_key not in grouped:
                    grouped[platform_key] = []
                grouped[platform_key].append(account)
            
            # Format response
            message = "📱 **Connected Social Media Accounts:**\n\n"
            for platform_key, platform_accounts in grouped.items():
                platform_name = self.supported_platforms.get(platform_key, {}).get('name', platform_key.title())
                emoji = self._get_platform_emoji(platform_key)
                message += f"{emoji} **{platform_name}:**\n"
                
                for account in platform_accounts:
                    message += f"  • {account['display_name']}"
                    if account.get('username'):
                        message += f" (@{account['username']})"
                    if account.get('follower_count', 0) > 0:
                        message += f" • {account['follower_count']:,} followers"
                    message += "\n"
                message += "\n"
            
            return self.success_response({
                "accounts": accounts,
                "accounts_by_platform": grouped,
                "message": message,
                "total_accounts": len(accounts)
            })
            
        except Exception as e:
            logger.error(f"[Universal Social Media] Failed to get accounts: {e}", exc_info=True)
            return self.fail_response(f"Failed to get accounts: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "check_upload_status",
            "description": "Check the status of a social media upload",
            "parameters": {
                "type": "object",
                "properties": {
                    "upload_id": {
                        "type": "string",
                        "description": "The upload ID to check status for"
                    }
                },
                "required": ["upload_id"]
            }
        }
    })
    async def check_upload_status(self, upload_id: str) -> ToolResult:
        """Check status of a social media upload"""
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.jwt_token}",
                    "Content-Type": "application/json"
                }
                
                async with session.get(
                    f"{self.base_url}/social-media/upload-status/{upload_id}",
                    headers=headers
                ) as response:
                    
                    if response.status == 404:
                        return self.fail_response(f"Upload {upload_id} not found")
                    elif response.status != 200:
                        error_text = await response.text()
                        return self.fail_response(f"Failed to get upload status: {error_text}")
                    
                    data = await response.json()
                    
                    if not data.get("success"):
                        return self.fail_response(f"Failed to get upload status: {data.get('message', 'Unknown error')}")
                    
                    platform = data["platform"]
                    status = data["status"]
                    platform_name = self.supported_platforms.get(platform, {}).get('name', platform.title())
                    emoji = self._get_platform_emoji(platform)
                    
                    # Format status message
                    if status == 'completed':
                        message = f"✅ **Upload completed successfully!**\n\n"
                        message += f"{emoji} **{data['content']['title']}** is now live on {platform_name}!\n\n"
                        
                        if data['platform_data']['url']:
                            message += f"🔗 **Watch:** {data['platform_data']['url']}\n"
                        
                        if data['analytics']['view_count'] > 0:
                            message += f"👀 **Views:** {data['analytics']['view_count']:,}\n"
                        
                        message += f"📺 **Channel:** {data['account']['name']}\n"
                        
                    elif status == 'failed':
                        message = f"❌ **Upload failed**\n\n"
                        message += f"Error: {data['status_message']}\n"
                        message += f"Platform: {platform_name}\n"
                        
                    elif status in ['uploading', 'processing']:
                        progress = data['progress']
                        message = f"📤 **Upload in progress...**\n\n"
                        message += f"{emoji} {platform_name}: {progress:.1f}% complete\n"
                        message += f"📁 {data['content']['title']}\n"
                        message += f"📺 {data['account']['name']}\n\n"
                        message += f"Status: {data['status_message']}"
                        
                    else:
                        message = f"⏳ **Upload queued**\n\n"
                        message += f"{emoji} {platform_name}\n"
                        message += f"Status: {status}\n"
                    
                    return self.success_response({
                        "upload_status": data,
                        "message": message,
                        "status": status,
                        "platform": platform
                    })
                    
        except Exception as e:
            logger.error(f"[Universal Social Media] Status check failed: {e}", exc_info=True)
            return self.fail_response(f"Status check failed: {str(e)}")
    
    async def _get_platform_accounts(self, platform: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get user's accounts for specified platform(s)"""
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.jwt_token}",
                    "Content-Type": "application/json"
                }
                
                url = f"{self.base_url}/social-media/accounts"
                if platform:
                    url += f"?platform={platform}"
                
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success"):
                            # Flatten accounts from grouped format
                            accounts = []
                            for platform_accounts in data.get("accounts_by_platform", {}).values():
                                accounts.extend(platform_accounts)
                            return accounts
            return []
            
        except Exception as e:
            logger.error(f"[Universal Social Media] Failed to get accounts: {e}")
            return []
    
    def _get_platform_emoji(self, platform: str) -> str:
        """Get emoji for platform"""
        emojis = {
            'youtube': '📺',
            'tiktok': '🎵', 
            'instagram': '📷',
            'twitter': '🐦',
            'linkedin': '💼',
            'facebook': '👥'
        }
        return emojis.get(platform, '📤')
    
    def _get_platform_specific_settings(self, platform: str) -> Dict[str, Any]:
        """Get platform-specific default settings"""
        
        settings = {
            'youtube': {
                'made_for_kids': False,
                'category_id': '22',  # People & Blogs
                'notify_subscribers': True
            },
            'tiktok': {
                'duet_enabled': True,
                'comment_enabled': True,
                'stitch_enabled': True
            },
            'instagram': {
                'comment_enabled': True,
                'like_and_view_counts_disabled': False
            },
            'twitter': {
                'reply_settings': 'everyone'
            },
            'linkedin': {
                'notify_network': True
            }
        }
        
        return settings.get(platform, {})