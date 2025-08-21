"""YouTube Tool for Agent Integration"""

from typing import Dict, Any, Optional, List
from agentpress.tool import Tool, ToolResult, openapi_schema
import aiohttp
import asyncio
import json
import os
import jwt
import re
from datetime import datetime, timedelta
import time
from utils.logger import logger
from services.supabase import DBConnection
from services.mcp_toggles import MCPToggleService


class YouTubeTool(Tool):
    """Native YouTube integration tool for the agent"""
    
    def __init__(self, user_id: str, channel_ids: Optional[List[str]] = None, thread_manager=None, jwt_token: Optional[str] = None, agent_id: Optional[str] = None, db: Optional[DBConnection] = None, thread_id: Optional[str] = None, project_id: Optional[str] = None):
        self.user_id = user_id
        self.channel_ids = channel_ids or []
        self.thread_manager = thread_manager
        self.agent_id = agent_id
        self.db = db or DBConnection()
        self.thread_id = thread_id
        self.project_id = project_id
        self.base_url = os.getenv("BACKEND_URL", "http://localhost:8000") + "/api"
        
        # Log initialization details
        logger.info(f"[YouTube Tool Init] user_id: {user_id}, agent_id: {agent_id}, channel_ids: {channel_ids}")
        
        # Use provided JWT token or create one
        self.jwt_token = jwt_token or self._create_jwt_token()
        
        # Initialize toggle service
        self.toggle_service = MCPToggleService(self.db) if self.db else None
        logger.info(f"[YouTube Tool Init] Toggle service initialized: {bool(self.toggle_service)}")
        
        # Store channel metadata for quick reference
        self.channel_metadata = {}
        self._has_channels = len(self.channel_ids) > 0
        
        # Smart caching system
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes default TTL
        self._cache_timestamps = {}
        
        super().__init__()
    
    def _create_jwt_token(self) -> str:
        """Create a JWT token for API authentication"""
        jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
        if not jwt_secret:
            logger.warning("SUPABASE_JWT_SECRET not set, authentication may fail")
            return ""
        
        # Create a simple JWT with the user_id
        payload = {
            "sub": self.user_id,
            "user_id": self.user_id,
            "role": "authenticated"
        }
        
        return jwt.encode(payload, jwt_secret, algorithm="HS256")
    
    def _get_cache(self, key: str, ignore_expiry: bool = False) -> Optional[Any]:
        """Get cached value if still valid
        
        Args:
            key: Cache key
            ignore_expiry: If True, return cached value even if expired
        """
        if key not in self._cache:
            return None
        
        # Check if cache expired (unless we're ignoring expiry)
        if not ignore_expiry:
            timestamp = self._cache_timestamps.get(key, 0)
            if time.time() - timestamp > self._cache_ttl:
                # Cache expired, remove it
                del self._cache[key]
                del self._cache_timestamps[key]
                logger.debug(f"Cache expired for key: {key}")
                return None
        
        logger.debug(f"Cache hit for key: {key} (ignore_expiry={ignore_expiry})")
        return self._cache[key]
    
    def _set_cache(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set cache value with optional custom TTL"""
        self._cache[key] = value
        self._cache_timestamps[key] = time.time()
        if ttl:
            # Store custom TTL for this key (not implemented in basic version)
            pass
        logger.debug(f"Cache set for key: {key}")
    
    def _clear_cache(self, pattern: Optional[str] = None) -> None:
        """Clear cache entries matching pattern or all if no pattern"""
        if pattern:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
                del self._cache_timestamps[key]
            logger.debug(f"Cleared {len(keys_to_delete)} cache entries matching '{pattern}'")
        else:
            self._cache.clear()
            self._cache_timestamps.clear()
            logger.debug("Cleared all cache entries")
    
    async def _check_enabled(self, channel_id: Optional[str] = None) -> tuple[bool, str]:
        """
        Check if YouTube tool is enabled for the current agent and channel
        Returns (is_enabled, message)
        """
        if not self.agent_id or not self.toggle_service:
            # If no agent ID or toggle service, assume enabled
            return True, ""
        
        try:
            # Check if specific channel is enabled
            if channel_id:
                mcp_id = f"social.youtube.{channel_id}"
                is_enabled = await self.toggle_service.is_enabled(
                    self.agent_id, 
                    self.user_id, 
                    mcp_id
                )
                if not is_enabled:
                    return False, f"YouTube channel {channel_id} is disabled. Please enable it in the MCP connections dropdown."
            
            # Check if any YouTube channel is enabled
            enabled_mcps = await self.toggle_service.get_enabled_mcps(
                self.agent_id,
                self.user_id,
                "social.youtube"
            )
            
            if not enabled_mcps and self.channel_ids:
                return False, "No YouTube channels are enabled. Please enable at least one channel in the MCP connections dropdown."
            
            return True, ""
            
        except Exception as e:
            logger.error(f"Error checking YouTube tool enabled state: {e}")
            # Default to enabled on error
            return True, ""
    
    async def _get_enabled_channels(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get only the YouTube channels that are enabled in MCP toggles
        Returns list of enabled channel data with smart caching
        """
        cache_key = f"enabled_channels_{self.agent_id}_{self.user_id}"
        
        # Check cache first unless force refresh
        if not force_refresh:
            cached_channels = self._get_cache(cache_key)
            if cached_channels is not None:
                # Update internal state from cache
                self.channel_metadata = {ch['id']: ch for ch in cached_channels}
                self.channel_ids = [ch['id'] for ch in cached_channels]
                return cached_channels
        
        # No agent ID or toggle service means use initialization channels
        if not self.agent_id or not self.toggle_service:
            logger.info(f"[YouTube Tool] No agent_id or toggle service, using initialization channels")
            if self.channel_ids:
                channels = await self._fetch_channel_metadata_for_ids(self.channel_ids)
                self._set_cache(cache_key, channels)
                return channels
            return []
        
        try:
            # Check if we have all_channels cached
            all_channels_cache_key = f"all_channels_{self.user_id}"
            all_channels = self._get_cache(all_channels_cache_key)
            
            if all_channels is None:
                # Fetch ALL user channels from the API with retry logic
                logger.info(f"[YouTube Tool] Fetching all channels from API")
                
                # Try up to 3 times with exponential backoff
                for attempt in range(3):
                    try:
                        async with aiohttp.ClientSession() as session:
                            headers = {
                                "Authorization": f"Bearer {self.jwt_token}",
                                "Content-Type": "application/json"
                            }
                            async with session.get(f"{self.base_url}/youtube/channels", headers=headers) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    all_channels = data.get("channels", [])
                                    # Cache all channels for 5 minutes
                                    self._set_cache(all_channels_cache_key, all_channels)
                                    break  # Success, exit retry loop
                                else:
                                    logger.error(f"Failed to get channels (attempt {attempt + 1}/3): {response.status}")
                                    if attempt < 2:  # Don't sleep on last attempt
                                        await asyncio.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s
                    except Exception as e:
                        logger.error(f"Error fetching channels (attempt {attempt + 1}/3): {e}")
                        if attempt < 2:
                            await asyncio.sleep(2 ** attempt)
                
                # If all attempts failed, try to use any previously cached data
                if all_channels is None:
                    # Check for stale cache (ignore expiry)
                    stale_cache = self._get_cache(all_channels_cache_key, ignore_expiry=True)
                    if stale_cache:
                        logger.warning("Using stale cached channels due to API failure")
                        all_channels = stale_cache
                    else:
                        # Last resort: if we have initialization channels, use them
                        if self.channel_ids:
                            logger.warning("API failed, falling back to initialization channels")
                            channels = await self._fetch_channel_metadata_for_ids(self.channel_ids)
                            self._set_cache(cache_key, channels)
                            return channels
                        return []
            
            # Filter channels based on CURRENT toggle states
            logger.info(f"[YouTube Tool] Checking toggle states for {len(all_channels)} channels")
            enabled_channels = []
            channels_needing_init = []
            
            for channel in all_channels:
                mcp_id = f"social.youtube.{channel['id']}"
                
                # First check if toggle exists
                toggles = await self.toggle_service.get_toggles(self.agent_id, self.user_id)
                
                if mcp_id not in toggles:
                    # No toggle exists - this is a newly connected channel
                    # Auto-enable it for better user experience
                    logger.info(f"[YouTube Tool] Auto-enabling newly connected channel {channel['name']} ({channel['id']})")
                    channels_needing_init.append((mcp_id, channel))
                    enabled_channels.append(channel)
                else:
                    # Toggle exists, respect its state
                    is_enabled = toggles[mcp_id]
                    if is_enabled:
                        enabled_channels.append(channel)
                        logger.debug(f"[YouTube Tool] Channel {channel['name']} ({channel['id']}) is enabled")
                    else:
                        logger.debug(f"[YouTube Tool] Channel {channel['name']} ({channel['id']}) is disabled")
            
            # Initialize toggles for new channels (set them as enabled)
            for mcp_id, channel in channels_needing_init:
                success = await self.toggle_service.set_toggle(
                    self.agent_id,
                    self.user_id,
                    mcp_id,
                    True  # Enable by default
                )
                if success:
                    logger.info(f"[YouTube Tool] Initialized toggle for channel {channel['name']} as enabled")
            
            # Update our internal state with current enabled channels
            self.channel_metadata = {ch['id']: ch for ch in enabled_channels}
            self.channel_ids = [ch['id'] for ch in enabled_channels]
            
            # Cache the enabled channels
            self._set_cache(cache_key, enabled_channels)
            
            logger.info(f"[YouTube Tool] Found {len(enabled_channels)} enabled channels")
            return enabled_channels
                    
        except Exception as e:
            logger.error(f"Error checking channel toggles: {e}")
            # Fallback to initialization channels on error
            if self.channel_ids:
                channels = await self._fetch_channel_metadata_for_ids(self.channel_ids)
                self._set_cache(cache_key, channels)
                return channels
            return []
    
    async def _fetch_channel_metadata_for_ids(self, channel_ids: List[str]) -> List[Dict[str, Any]]:
        """Helper method to fetch channel metadata for specific channel IDs"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.jwt_token}",
                    "Content-Type": "application/json"
                }
                async with session.get(f"{self.base_url}/youtube/channels", headers=headers) as response:
                    if response.status != 200:
                        return []
                    
                    data = await response.json()
                    all_channels = data.get("channels", [])
                    return [ch for ch in all_channels if ch["id"] in channel_ids]
        except Exception as e:
            logger.error(f"Error fetching channel metadata: {e}")
            return []
    
    def _generate_video_metadata(self, context: str) -> Dict[str, Any]:
        """
        Generate intelligent title, description, and tags based on context
        """
        context_lower = context.lower()
        current_year = datetime.now().year
        current_month = datetime.now().strftime("%B")
        
        # Detect video type from context
        video_type = "general"
        if any(word in context_lower for word in ["teaser", "preview", "coming soon", "announcement"]):
            video_type = "teaser"
        elif any(word in context_lower for word in ["demo", "demonstration", "showcase", "walkthrough"]):
            video_type = "demo"
        elif any(word in context_lower for word in ["tutorial", "how to", "guide", "learn"]):
            video_type = "tutorial"
        elif any(word in context_lower for word in ["update", "release", "launch", "new version"]):
            video_type = "update"
        elif any(word in context_lower for word in ["review", "unboxing", "first look"]):
            video_type = "review"
        
        # Extract app/product name if mentioned
        app_name = "App"
        name_patterns = [
            r"for (?:the )?([A-Z][a-zA-Z]+)(?:\s+app)?",  # "for Willow app"
            r"(?:the )?([A-Z][a-zA-Z]+)\s+app",           # "Willow app"
            r"about\s+([A-Z][a-zA-Z]+)",                  # "about Willow"
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                app_name = match.group(1).title()
                break
        
        # Generate title based on video type
        title_templates = {
            "teaser": [
                f"{app_name} - Coming Soon | Official Teaser {current_year}",
                f"Introducing {app_name} | Something Amazing is Coming",
                f"{app_name} App Reveal | Teaser Trailer {current_year}"
            ],
            "demo": [
                f"{app_name} Demo | See It In Action",
                f"{app_name} App Showcase | Full Walkthrough",
                f"First Look at {app_name} | Live Demo"
            ],
            "tutorial": [
                f"How to Use {app_name} | Complete Guide {current_year}",
                f"{app_name} Tutorial | Getting Started",
                f"Master {app_name} | Step-by-Step Tutorial"
            ],
            "update": [
                f"{app_name} Update | What's New in {current_month} {current_year}",
                f"Big Updates Coming to {app_name}",
                f"{app_name} - New Features Announced"
            ],
            "review": [
                f"{app_name} Review | Honest First Impressions",
                f"Is {app_name} Worth It? | Full Review",
                f"{app_name} - Everything You Need to Know"
            ],
            "general": [
                f"{app_name} | {current_year}",
                f"Check Out {app_name}",
                f"{app_name} - Watch This!"
            ]
        }
        
        # Select appropriate title
        title = title_templates.get(video_type, title_templates["general"])[0]
        
        # Generate description based on video type
        description_templates = {
            "teaser": f"""🚀 Something revolutionary is coming...

Introducing {app_name} - The future is almost here.

Get ready for an experience that will transform the way you work, play, and connect.

⏰ Coming Soon
🔔 Turn on notifications to be the first to know when we launch!

📱 Stay Connected:
→ Website: [Coming Soon]
→ Twitter: @{app_name}App
→ Instagram: @{app_name}App

Join the waitlist and get exclusive early access!

#{app_name} #ComingSoon #AppLaunch #Innovation #TechTeaser #{current_year} #NewApp #Startup #Technology""",
            
            "demo": f"""🎯 See {app_name} in action!

In this demo, we showcase the powerful features and intuitive design that make {app_name} stand out.

📋 What's Covered:
• Main features walkthrough
• User interface tour
• Key functionalities
• Real-world use cases

🚀 Ready to try it yourself?
→ Download: [Link]
→ Free Trial: Available

💬 Questions? Drop them in the comments!

#{app_name} #AppDemo #TechDemo #Software #Productivity #{current_year} #AppShowcase""",
            
            "tutorial": f"""📚 Learn how to master {app_name}!

This comprehensive guide will walk you through everything you need to know to get started with {app_name}.

⏱️ Timestamps:
0:00 Introduction
0:30 Getting Started
2:00 Main Features
5:00 Pro Tips
7:00 Conclusion

📌 Helpful Resources:
• Documentation: [Link]
• Support: [Link]
• Community: [Link]

🎯 By the end of this video, you'll be a {app_name} pro!

#{app_name} #Tutorial #HowTo #TechTutorial #Learning #{current_year} #Guide""",
            
            "update": f"""🎉 Exciting updates for {app_name}!

We've been working hard to bring you amazing new features and improvements.

✨ What's New:
• Feature updates
• Performance improvements
• Bug fixes
• UI enhancements

📅 Available now for all users!

📲 Update your app to experience these improvements.

#{app_name} #AppUpdate #NewFeatures #TechNews #{current_year} #ProductUpdate""",
            
            "general": f"""Welcome to {app_name}!

{context}

🔗 Links:
• Website: [Link]
• Download: [Link]
• Support: [Link]

📱 Follow us for more updates!

#{app_name} #{current_year} #Technology #App #Software"""
        }
        
        description = description_templates.get(video_type, description_templates["general"])
        
        # Generate tags based on video type and context
        base_tags = [app_name, str(current_year), "Technology", "Software", "App"]
        
        type_specific_tags = {
            "teaser": ["Coming Soon", "Teaser", "Preview", "Launch", "Announcement", "Startup"],
            "demo": ["Demo", "Showcase", "Walkthrough", "Features", "Tutorial"],
            "tutorial": ["Tutorial", "How To", "Guide", "Learning", "Education", "Tips"],
            "update": ["Update", "New Features", "Release", "Changelog", "Improvements"],
            "review": ["Review", "First Look", "Impressions", "Analysis", "Opinion"],
            "general": ["Video", "Content", "Tech"]
        }
        
        tags = base_tags + type_specific_tags.get(video_type, type_specific_tags["general"])
        
        # Add any specific tags from context
        if "ai" in context_lower or "artificial intelligence" in context_lower:
            tags.extend(["AI", "Artificial Intelligence", "Machine Learning"])
        if "mobile" in context_lower or "ios" in context_lower or "android" in context_lower:
            tags.extend(["Mobile App", "iOS", "Android"])
        if "web" in context_lower:
            tags.extend(["Web App", "Browser", "Online"])
        
        return {
            "title": title,
            "description": description,
            "tags": list(set(tags))[:15],  # YouTube allows max 15 tags
            "video_type": video_type,
            "app_name": app_name
        }
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_authenticate",
            "description": "USE IMMEDIATELY when user mentions YouTube/connect/channel - NO QUESTIONS! Just shows an OAuth button the user clicks to connect. The OAuth handles EVERYTHING (account selection, permissions, etc). NEVER ask user preferences first - just use this tool instantly!",
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
        """Start YouTube OAuth authentication flow - works from both agent chat and Social Media page"""
        try:
            # First check if there are already connected channels if requested
            if check_existing:
                channels_result = await self.youtube_channels()
                if channels_result.success:
                    # Parse the output - it might be a JSON string or dictionary
                    if isinstance(channels_result.output, str):
                        try:
                            output_data = json.loads(channels_result.output)
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse channels result: {channels_result.output}")
                            output_data = {}
                    else:
                        output_data = channels_result.output
                    
                    channels = output_data.get("channels", []) if isinstance(output_data, dict) else []
                    if channels:
                        # Already have channels connected
                        message = f"🎉 You already have {len(channels)} YouTube channel(s) connected:\n\n"
                        for ch in channels:
                            message += f"• **{ch['name']}**"
                            if ch.get('username'):
                                message += f" (@{ch['username']})"
                            message += f" - {ch.get('subscriber_count', 0):,} subscribers\n"
                        
                        message += "\n💡 **Tips:**\n"
                        message += "• To add more channels, click the button below or visit the Social Media page\n"
                        message += "• You can manage channel permissions in the MCP connections dropdown\n"
                        message += "• Each channel can be toggled on/off independently for this agent"
                        
                        # Still provide auth URL to add more channels
                        # Include thread context if available
                        request_data = {}
                        if self.thread_id:
                            request_data['thread_id'] = self.thread_id
                        if self.project_id:
                            request_data['project_id'] = self.project_id
                        
                        async with aiohttp.ClientSession() as session:
                            headers = {
                                "Authorization": f"Bearer {self.jwt_token}",
                                "Content-Type": "application/json"
                            }
                            async with session.post(f"{self.base_url}/youtube/auth/initiate", headers=headers, json=request_data) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    auth_url = data.get("auth_url")
                                    
                                    return self.success_response({
                                        "message": message,
                                        "auth_url": auth_url,
                                        "button_text": "Add Another Channel",
                                        "existing_channels": channels
                                    })
                        
                        # If we couldn't get auth URL, still show existing channels
                        return self.success_response({
                            "message": message,
                            "existing_channels": channels
                        })
            
            # Get auth URL from backend (same endpoint used by Social Media page)
            # Include thread context if available
            request_data = {}
            if self.thread_id:
                request_data['thread_id'] = self.thread_id
            if self.project_id:
                request_data['project_id'] = self.project_id
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.jwt_token}",
                    "Content-Type": "application/json"
                }
                async with session.post(f"{self.base_url}/youtube/auth/initiate", headers=headers, json=request_data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return self.fail_response(f"Failed to initiate authentication: {error_text}")
                    
                    data = await response.json()
                    auth_url = data.get("auth_url")
                    
                    if not auth_url:
                        return self.fail_response("No authentication URL received")
                    
                    # Return OAuth button for user to click
                    message = "🔗 **Connect Your YouTube Channel**\n\n"
                    message += "Click the button below to connect your YouTube account. "
                    message += "You can also manage your social media connections from the Social Media page in the dashboard.\n\n"
                    message += "**After connecting:**\n"
                    message += "• Your channel will appear in the MCP connections dropdown\n"
                    message += "• You can toggle it on/off for this agent\n"
                    message += "• Upload videos, manage content, and view analytics"
                    
                    return self.success_response({
                        "message": message,
                        "auth_url": auth_url,
                        "button_text": "Connect YouTube Channel"
                    })
        except Exception as e:
            logger.error(f"YouTube authentication error: {e}")
            return ToolResult(success=False, output=str(e))
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_channels",
            "description": "USE IMMEDIATELY when user asks about channels/stats - NO QUESTIONS! Shows connected YouTube channels or prompts to connect if none exist. If no channels connected, automatically provides OAuth button. Use this instantly without asking what they want to see.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Optional: Get detailed analytics for a specific channel. If not provided, returns all enabled channels."
                    },
                    "include_analytics": {
                        "type": "boolean",
                        "description": "Include detailed analytics like average views per video, country, creation date (default: false for list, true for single channel)"
                    }
                },
                "required": []
            }
        }
    })
    async def youtube_channels(self, channel_id: Optional[str] = None, include_analytics: Optional[bool] = None) -> ToolResult:
        """Get user's connected YouTube channels with comprehensive statistics - filtered by MCP toggle status"""
        # Check if tool is enabled (and specific channel if provided)
        is_enabled, message = await self._check_enabled(channel_id)
        if not is_enabled:
            return self.fail_response(message)
        
        try:
            # If specific channel requested, get detailed stats
            if channel_id:
                # Default to include analytics for single channel view
                if include_analytics is None:
                    include_analytics = True
                
                # Check cache for detailed channel info
                cache_key = f"channel_detail_{channel_id}"
                channel = self._get_cache(cache_key)
                
                if channel is None:
                    # Fetch from API if not cached
                    async with aiohttp.ClientSession() as session:
                        headers = {
                            "Authorization": f"Bearer {self.jwt_token}",
                            "Content-Type": "application/json"
                        }
                        async with session.get(f"{self.base_url}/youtube/channels/{channel_id}", headers=headers) as response:
                            if response.status == 404:
                                return self.fail_response(
                                    f"Channel {channel_id} not found. Use youtube_channels() without parameters to see available channels."
                                )
                            elif response.status != 200:
                                error_text = await response.text()
                                return self.fail_response(f"Failed to get channel details: {error_text}")
                            
                            data = await response.json()
                            channel = data.get("channel")
                            
                            # Cache the detailed channel info
                            self._set_cache(cache_key, channel)
                        
                        # Update metadata
                        self.channel_metadata[channel_id] = channel
                        
                        # Build detailed response
                        stats_message = f"📊 **Channel Analytics: {channel['name']}**\n\n"
                        
                        if channel.get('username'):
                            stats_message += f"**Username:** @{channel['username']}\n"
                        
                        stats_message += f"**Channel ID:** {channel['id']}\n\n"
                        stats_message += "**📈 Core Metrics:**\n"
                        stats_message += f"• **Subscribers:** {channel.get('subscriber_count', 0):,}\n"
                        stats_message += f"• **Total Views:** {channel.get('view_count', 0):,}\n"
                        stats_message += f"• **Videos Published:** {channel.get('video_count', 0):,}\n"
                        
                        # Include analytics if requested
                        if include_analytics:
                            if channel.get('view_count', 0) > 0 and channel.get('video_count', 0) > 0:
                                avg_views = channel['view_count'] / channel['video_count']
                                stats_message += f"• **Average Views per Video:** {avg_views:,.0f}\n"
                            
                            if channel.get('description'):
                                stats_message += f"\n**📝 Channel Description:**\n{channel['description'][:200]}...\n"
                            
                            if channel.get('country'):
                                stats_message += f"\n**🌍 Country:** {channel['country']}\n"
                            
                            if channel.get('published_at'):
                                stats_message += f"**📅 Channel Created:** {channel['published_at'][:10]}\n"
                        
                        response_data = {
                            "channel": channel,
                            "message": stats_message,
                            "analytics_summary": {
                                "name": channel['name'],
                                "subscribers": channel.get('subscriber_count', 0),
                                "total_views": channel.get('view_count', 0),
                                "videos": channel.get('video_count', 0)
                            }
                        }
                        
                        if include_analytics:
                            response_data["analytics_summary"]["average_views_per_video"] = (
                                channel['view_count'] / channel['video_count'] 
                                if channel.get('video_count', 0) > 0 else 0
                            )
                            response_data["analytics_summary"]["country"] = channel.get('country')
                            response_data["analytics_summary"]["created_at"] = channel.get('published_at')
                        
                        return self.success_response(response_data)
            
            # Otherwise, get list of all enabled channels
            channels = await self._get_enabled_channels()
            
            # Update our internal metadata with only enabled channels
            self.channel_metadata = {ch['id']: ch for ch in channels}
            self.channel_ids = [ch['id'] for ch in channels]
            self._has_channels = len(channels) > 0
            
            if not channels:
                # Check if user has any channels at all
                all_channels_check = self._get_cache(f"all_channels_{self.user_id}")
                if all_channels_check and len(all_channels_check) > 0:
                    # User has channels but none are enabled
                    return self.success_response({
                        "message": "⚠️ **YouTube channels need to be enabled**\n\nYou have YouTube channels connected, but they need to be enabled for this agent.\n\n**To enable channels:**\n1. Click the MCP connections button in the chat input\n2. Toggle on the YouTube channels you want to use\n3. Try this command again\n\n**Note:** Channels are now auto-enabled by default for new connections.",
                        "channels": [],
                        "has_channels": False,
                        "action_needed": "enable_channels"
                    })
                else:
                    # User has no channels connected at all
                    return self.success_response({
                        "message": "📺 **No YouTube channels connected**\n\nYou haven't connected any YouTube channels yet.\n\n**To connect a channel:**\n1. Use the `youtube_authenticate` command, or\n2. Go to Settings → Social Media in the dashboard\n\nOnce connected, your channels will be automatically enabled for use.",
                        "channels": [],
                        "has_channels": False,
                        "action_needed": "connect_channels"
                    })
            
            # Format channel information with enhanced details
            formatted_channels = []
            
            # Build appropriate message based on number of enabled channels
            if len(channels) == 1:
                summary_text = f"**Selected YouTube channel:**\n\n"
            else:
                summary_text = f"**{len(channels)} enabled YouTube channels:**\n\n"
            
            for channel in channels:
                formatted_channel = {
                    "id": channel["id"],
                    "name": channel["name"],
                    "username": channel.get("username"),
                    "profile_picture": channel.get("profile_picture"),
                    "subscriber_count": channel.get("subscriber_count", 0),
                    "view_count": channel.get("view_count", 0),
                    "video_count": channel.get("video_count", 0)
                }
                
                # Add analytics if requested
                if include_analytics:
                    if channel.get('view_count', 0) > 0 and channel.get('video_count', 0) > 0:
                        formatted_channel["average_views_per_video"] = channel['view_count'] / channel['video_count']
                    formatted_channel["country"] = channel.get("country")
                    formatted_channel["created_at"] = channel.get("published_at")
                    formatted_channel["description"] = channel.get("description")
                
                formatted_channels.append(formatted_channel)
                
                # Build readable summary
                summary_text += f"📺 **{channel['name']}**\n"
                if channel.get("username"):
                    summary_text += f"   @{channel['username']}\n"
                summary_text += f"   • {channel.get('subscriber_count', 0):,} subscribers\n"
                summary_text += f"   • {channel.get('view_count', 0):,} total views\n"
                summary_text += f"   • {channel.get('video_count', 0):,} videos\n"
                
                if include_analytics:
                    if channel.get('view_count', 0) > 0 and channel.get('video_count', 0) > 0:
                        avg_views = channel['view_count'] / channel['video_count']
                        summary_text += f"   • {avg_views:,.0f} avg views/video\n"
                
                summary_text += "\n"
            
            # Add single channel note
            if len(channels) == 1:
                summary_text += "✅ This channel will be used automatically for uploads.\n"
            
            return self.success_response({
                "channels": formatted_channels,
                "count": len(formatted_channels),
                "message": summary_text,
                "has_channels": True,
                "single_channel": len(channels) == 1,
                "selected_channel_id": channels[0]["id"] if len(channels) == 1 else None
            })
        except Exception as e:
            logger.error(f"Error fetching YouTube channels: {e}")
            return ToolResult(success=False, output=str(e))
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_upload_video",
            "description": "USE IMMEDIATELY when user mentions upload/video - NO QUESTIONS! Auto-discovers recent video files, auto-selects channel, auto-generates metadata. Just use it! The tool handles EVERYTHING. Never ask about file location, channel preference, or metadata - just use the tool instantly!",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "The YouTube channel ID to upload to. DO NOT specify unless user explicitly requests a specific channel. Leave empty to auto-select from enabled channels. Specifying a disabled channel will cause upload to fail."
                    },
                    "context": {
                        "type": "string",
                        "description": "Context or summary about the video (e.g., 'teaser for Willow app'). Used to auto-generate title and description if not provided."
                    },
                    "title": {
                        "type": "string",
                        "description": "Title for the YouTube video (optional - auto-generated from context if not provided)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description for the YouTube video (optional - auto-generated from context if not provided)"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags for the video (optional - auto-generated from context if not provided)"
                    },
                    "privacy": {
                        "type": "string",
                        "enum": ["private", "unlisted", "public"],
                        "description": "Privacy setting for the video (default: public)"
                    },
                    "video_reference_id": {
                        "type": "string",
                        "description": "Reference ID of uploaded video file (optional - auto-discovered from recent uploads)"
                    },
                    "thumbnail_reference_id": {
                        "type": "string",
                        "description": "Reference ID of thumbnail image (optional)"
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
        video_reference_id: Optional[str] = None,
        thumbnail_reference_id: Optional[str] = None
    ) -> ToolResult:
        """Upload a video to YouTube with intelligent metadata generation"""
        try:
            logger.info(f"[YouTube Upload] Starting upload - channel_id: {channel_id}, has context: {bool(context)}")
            
            # If no channel specified, check enabled channels
            if not channel_id:
                logger.info(f"[YouTube Upload] No channel_id provided, checking enabled channels...")
                
                # Get enabled channels
                enabled_channels = await self._get_enabled_channels()
                
                logger.info(f"[YouTube Upload] Found {len(enabled_channels)} enabled channels")
                
                if not enabled_channels:
                    return self.fail_response(
                        "No YouTube channels are enabled. Please enable at least one channel in the MCP connections dropdown."
                    )
                
                # If only one channel is enabled, auto-select it
                if len(enabled_channels) == 1:
                    channel_id = enabled_channels[0]["id"]
                    channel_name = enabled_channels[0]["name"]
                    logger.info(f"[YouTube Upload] Auto-selected the only enabled channel: {channel_name} ({channel_id})")
                else:
                    # Multiple channels enabled, user needs to specify
                    channel_list = "\n".join([
                        f"• {ch['name']} (@{ch.get('username', 'N/A')}) - ID: {ch['id']}"
                        for ch in enabled_channels
                    ])
                    return self.fail_response(
                        f"Multiple YouTube channels are enabled. Please specify which channel to upload to:\n\n{channel_list}\n\n"
                        f"Use: youtube_upload_video(channel_id='CHANNEL_ID', ...)"
                    )
            else:
                # Verify the specified channel is enabled
                enabled_channels = await self._get_enabled_channels()
                enabled_ids = [ch["id"] for ch in enabled_channels]
                
                if channel_id not in enabled_ids:
                    # Check if there are any enabled channels to suggest
                    if enabled_channels:
                        channel_names = ", ".join([ch["name"] for ch in enabled_channels])
                        return self.fail_response(
                            f"Channel {channel_id} is not enabled. Try uploading without specifying channel_id to auto-select from enabled channels: {channel_names}. Or enable the channel in the MCP connections dropdown."
                        )
                    else:
                        return self.fail_response(
                            f"Channel {channel_id} is not enabled. Please enable it in the MCP connections dropdown first."
                        )
            
            # Generate metadata if not provided
            if context and (not title or not description or not tags):
                logger.info(f"Generating metadata from context: {context}")
                generated = self._generate_video_metadata(context)
                
                # Use generated values if originals not provided
                if not title:
                    title = generated["title"]
                    logger.info(f"Generated title: {title}")
                
                if not description:
                    description = generated["description"]
                    logger.info(f"Generated description preview: {description[:100]}...")
                
                if not tags:
                    tags = generated["tags"]
                    logger.info(f"Generated tags: {tags}")
            
            # Fallback if still no title
            if not title:
                title = f"Video Upload - {datetime.now().strftime('%B %d, %Y')}"
            
            if not description:
                description = "Uploaded via YouTube API"
            
            if not tags:
                tags = ["Video", str(datetime.now().year)]
            
            # Prepare upload parameters
            upload_params = {
                "channel_id": channel_id,
                "title": title,
                "description": description,
                "tags": tags,
                "category_id": "22",  # People & Blogs default
                "privacy_status": privacy,
                "made_for_kids": False,
                "notify_subscribers": True
            }
            
            # Add reference IDs if provided
            if video_reference_id:
                upload_params["video_reference_id"] = video_reference_id
            if thumbnail_reference_id:
                upload_params["thumbnail_reference_id"] = thumbnail_reference_id
            
            # Make API call to backend upload service
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.jwt_token}",
                    "Content-Type": "application/json"
                }
                
                # Call the upload endpoint (this will auto-discover files if not specified)
                async with session.post(
                    f"{self.base_url}/youtube/upload",
                    headers=headers,
                    json=upload_params
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return self.fail_response(f"Upload failed: {error_text}")
                    
                    data = await response.json()
                    
                    # Get channel name for better response
                    # First update metadata if needed
                    if channel_id not in self.channel_metadata:
                        enabled_channels = await self._get_enabled_channels()
                        self.channel_metadata = {ch['id']: ch for ch in enabled_channels}
                    
                    channel_name = self.channel_metadata.get(channel_id, {}).get("name", channel_id)
                    
                    # Check if this was auto-selected (only one enabled channel)
                    enabled_channels = await self._get_enabled_channels()
                    was_auto_selected = len(enabled_channels) == 1
                    
                    # Build success message
                    if was_auto_selected:
                        success_message = f"""✅ Video upload initiated to your selected channel!

📺 **Channel:** {channel_name}
🎬 **Title:** {title}
🏷️ **Tags:** {', '.join(tags[:5])}{'...' if len(tags) > 5 else ''}
🔒 **Privacy:** {privacy}

📝 **Description Preview:**
{description[:200]}{'...' if len(description) > 200 else ''}

🚀 Your video is being uploaded to YouTube. You'll be notified when it's ready!"""
                    else:
                        success_message = f"""✅ Video upload initiated!

📺 **Channel:** {channel_name}
🎬 **Title:** {title}
🏷️ **Tags:** {', '.join(tags[:5])}{'...' if len(tags) > 5 else ''}
🔒 **Privacy:** {privacy}

📝 **Description Preview:**
{description[:200]}{'...' if len(description) > 200 else ''}

🚀 Your video is being uploaded to YouTube. You'll be notified when it's ready!"""
                    
                    return self.success_response({
                        "message": success_message,
                        "upload_details": {
                            "upload_id": data.get("upload_id"),
                            "channel": channel_name,
                            "title": title,
                            "description": description,
                            "tags": tags,
                            "privacy": privacy,
                            "status": data.get("status", "processing"),
                            "auto_generated": bool(context and not all([title, description, tags])),
                            "video_reference": data.get("video_reference"),
                            "thumbnail_reference": data.get("thumbnail_reference")
                        }
                    })
                    
        except Exception as e:
            logger.error(f"Error uploading video: {e}")
            return ToolResult(success=False, output=str(e))
    
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_list_captions",
            "description": "List all available captions/subtitles for a video. Returns language options and caption IDs for downloading.",
            "parameters": {
                "type": "object",
                "properties": {
                    "video_id": {
                        "type": "string",
                        "description": "The YouTube video ID to list captions for"
                    }
                },
                "required": ["video_id"]
            }
        }
    })
    async def youtube_list_captions(self, video_id: str) -> ToolResult:
        """List all available captions/subtitles for a video"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.jwt_token}",
                    "Content-Type": "application/json"
                }
                async with session.get(f"{self.base_url}/youtube/videos/{video_id}/captions", headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return self.fail_response(f"Failed to list captions: {error_text}")
                    
                    data = await response.json()
                    captions = data.get("captions", [])
                    
                    if not captions:
                        return self.success_response({
                            "captions": [],
                            "message": "No captions available for this video"
                        })
                    
                    message = f"📝 **Available Captions for Video {video_id}:**\n\n"
                    for caption in captions:
                        message += f"• **{caption.get('name', 'Unknown')}** ({caption.get('language', 'Unknown')})\n"
                        message += f"  - ID: {caption.get('id')}\n"
                        message += f"  - Kind: {caption.get('kind', 'Unknown')}\n"
                        if caption.get('is_auto_synced'):
                            message += f"  - Auto-generated\n"
                        message += "\n"
                    
                    return self.success_response({
                        "captions": captions,
                        "message": message,
                        "count": len(captions)
                    })
        except Exception as e:
            logger.error(f"Error listing captions: {e}")
            return ToolResult(success=False, output=str(e))
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_download_caption",
            "description": "Download caption/subtitle content for a video in various formats (srt, vtt, ttml, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "video_id": {
                        "type": "string",
                        "description": "The YouTube video ID"
                    },
                    "caption_id": {
                        "type": "string",
                        "description": "The caption ID obtained from youtube_list_captions"
                    },
                    "format": {
                        "type": "string",
                        "description": "Caption format: srt, vtt, ttml, srv1, srv2, srv3 (default: srt)",
                        "enum": ["srt", "vtt", "ttml", "srv1", "srv2", "srv3"]
                    }
                },
                "required": ["video_id", "caption_id"]
            }
        }
    })
    async def youtube_download_caption(self, video_id: str, caption_id: str, format: str = "srt") -> ToolResult:
        """Download caption/subtitle content for a video"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.jwt_token}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "caption_id": caption_id,
                    "format": format
                }
                
                async with session.post(
                    f"{self.base_url}/youtube/videos/{video_id}/caption/download",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return self.fail_response(f"Failed to download caption: {error_text}")
                    
                    data = await response.json()
                    content = data.get("content", "")
                    
                    return self.success_response({
                        "content": content,
                        "format": format,
                        "caption_id": caption_id,
                        "video_id": video_id,
                        "message": f"Successfully downloaded caption in {format} format"
                    })
        except Exception as e:
            logger.error(f"Error downloading caption: {e}")
            return ToolResult(success=False, output=str(e))
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_list_channel_videos",
            "description": "List videos from a YouTube channel with sorting options. Returns video metadata including views, likes, and publish dates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "The YouTube channel ID"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of videos to return (default: 10, max: 50)",
                        "minimum": 1,
                        "maximum": 50
                    },
                    "order": {
                        "type": "string",
                        "description": "Sort order for videos",
                        "enum": ["date", "rating", "relevance", "title", "viewCount"]
                    }
                },
                "required": ["channel_id"]
            }
        }
    })
    async def youtube_list_channel_videos(
        self, 
        channel_id: str, 
        max_results: int = 10,
        order: str = "date"
    ) -> ToolResult:
        """List videos from a YouTube channel"""
        # Check if tool is enabled for this specific channel
        is_enabled, message = await self._check_enabled(channel_id)
        if not is_enabled:
            return self.fail_response(message)
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.jwt_token}",
                    "Content-Type": "application/json"
                }
                
                params = {
                    "max_results": max_results,
                    "order": order
                }
                
                async with session.get(
                    f"{self.base_url}/youtube/channels/{channel_id}/videos",
                    headers=headers,
                    params=params
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return self.fail_response(f"Failed to list channel videos: {error_text}")
                    
                    data = await response.json()
                    videos = data.get("videos", [])
                    
                    if not videos:
                        return self.success_response({
                            "videos": [],
                            "message": "No videos found in this channel"
                        })
                    
                    message = f"📹 **Latest Videos from Channel:**\n\n"
                    for idx, video in enumerate(videos, 1):
                        message += f"{idx}. **{video.get('title', 'Untitled')}**\n"
                        message += f"   • Video ID: {video.get('id')}\n"
                        message += f"   • Views: {video.get('viewCount', 0):,}\n"
                        message += f"   • Likes: {video.get('likeCount', 0):,}\n"
                        message += f"   • Published: {video.get('publishedAt', 'Unknown')[:10]}\n"
                        message += f"   • Duration: {video.get('duration', 'Unknown')}\n\n"
                    
                    return self.success_response({
                        "videos": videos,
                        "message": message,
                        "count": len(videos),
                        "channel_id": channel_id
                    })
        except Exception as e:
            logger.error(f"Error listing channel videos: {e}")
            return ToolResult(success=False, output=str(e))
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_list_playlists",
            "description": "List all playlists from a YouTube channel. Returns playlist names, IDs, and video counts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "The YouTube channel ID"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of playlists to return (default: 10, max: 50)",
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": ["channel_id"]
            }
        }
    })
    async def youtube_list_playlists(self, channel_id: str, max_results: int = 10) -> ToolResult:
        """List playlists from a YouTube channel"""
        # Check if tool is enabled for this specific channel
        is_enabled, message = await self._check_enabled(channel_id)
        if not is_enabled:
            return self.fail_response(message)
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.jwt_token}",
                    "Content-Type": "application/json"
                }
                
                params = {"max_results": max_results}
                
                async with session.get(
                    f"{self.base_url}/youtube/channels/{channel_id}/playlists",
                    headers=headers,
                    params=params
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return self.fail_response(f"Failed to list playlists: {error_text}")
                    
                    data = await response.json()
                    playlists = data.get("playlists", [])
                    
                    if not playlists:
                        return self.success_response({
                            "playlists": [],
                            "message": "No playlists found in this channel"
                        })
                    
                    message = f"📋 **Channel Playlists:**\n\n"
                    for idx, playlist in enumerate(playlists, 1):
                        message += f"{idx}. **{playlist.get('title', 'Untitled')}**\n"
                        message += f"   • Playlist ID: {playlist.get('id')}\n"
                        message += f"   • Videos: {playlist.get('itemCount', 0)}\n"
                        message += f"   • Privacy: {playlist.get('privacyStatus', 'Unknown')}\n"
                        if playlist.get('description'):
                            desc = playlist['description'][:100]
                            message += f"   • Description: {desc}...\n"
                        message += "\n"
                    
                    return self.success_response({
                        "playlists": playlists,
                        "message": message,
                        "count": len(playlists),
                        "channel_id": channel_id
                    })
        except Exception as e:
            logger.error(f"Error listing playlists: {e}")
            return ToolResult(success=False, output=str(e))
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_list_subscriptions",
            "description": "List public subscriptions of a YouTube channel. Shows channels that this channel is subscribed to.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "The YouTube channel ID"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of subscriptions to return (default: 10, max: 50)",
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": ["channel_id"]
            }
        }
    })
    async def youtube_list_subscriptions(self, channel_id: str, max_results: int = 10) -> ToolResult:
        """List subscriptions of a YouTube channel"""
        # Check if tool is enabled for this specific channel
        is_enabled, message = await self._check_enabled(channel_id)
        if not is_enabled:
            return self.fail_response(message)
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.jwt_token}",
                    "Content-Type": "application/json"
                }
                
                params = {"max_results": max_results}
                
                async with session.get(
                    f"{self.base_url}/youtube/channels/{channel_id}/subscriptions",
                    headers=headers,
                    params=params
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return self.fail_response(f"Failed to list subscriptions: {error_text}")
                    
                    data = await response.json()
                    subscriptions = data.get("subscriptions", [])
                    
                    if not subscriptions:
                        return self.success_response({
                            "subscriptions": [],
                            "message": "No public subscriptions found for this channel"
                        })
                    
                    message = f"👥 **Channel Subscriptions:**\n\n"
                    for idx, sub in enumerate(subscriptions, 1):
                        message += f"{idx}. **{sub.get('title', 'Unknown Channel')}**\n"
                        message += f"   • Channel ID: {sub.get('channelId')}\n"
                        if sub.get('description'):
                            desc = sub['description'][:100]
                            message += f"   • Description: {desc}...\n"
                        message += "\n"
                    
                    return self.success_response({
                        "subscriptions": subscriptions,
                        "message": message,
                        "count": len(subscriptions),
                        "channel_id": channel_id
                    })
        except Exception as e:
            logger.error(f"Error listing subscriptions: {e}")
            return ToolResult(success=False, output=str(e))
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_subscribe_channel",
            "description": "Subscribe to another YouTube channel from your connected channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Your YouTube channel ID (the channel doing the subscribing)"
                    },
                    "target_channel_id": {
                        "type": "string",
                        "description": "The channel ID to subscribe to"
                    }
                },
                "required": ["channel_id", "target_channel_id"]
            }
        }
    })
    async def youtube_subscribe_channel(self, channel_id: str, target_channel_id: str) -> ToolResult:
        """Subscribe to another YouTube channel"""
        # Check if tool is enabled for this specific channel
        is_enabled, message = await self._check_enabled(channel_id)
        if not is_enabled:
            return self.fail_response(message)
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.jwt_token}",
                    "Content-Type": "application/json"
                }
                
                payload = {"target_channel_id": target_channel_id}
                
                async with session.post(
                    f"{self.base_url}/youtube/channels/{channel_id}/subscribe",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return self.fail_response(f"Failed to subscribe: {error_text}")
                    
                    data = await response.json()
                    
                    return self.success_response({
                        "subscription_id": data.get("subscription_id"),
                        "message": f"✅ Successfully subscribed to channel {target_channel_id}",
                        "channel_id": channel_id,
                        "target_channel_id": target_channel_id
                    })
        except Exception as e:
            logger.error(f"Error subscribing to channel: {e}")
            return ToolResult(success=False, output=str(e))
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_manage_video",
            "description": "Comprehensive video management tool: Get details, update metadata, change thumbnail - all in one smart interface. Can perform multiple operations in a single call.",
            "parameters": {
                "type": "object",
                "properties": {
                    "video_id": {
                        "type": "string",
                        "description": "The YouTube video ID to manage"
                    },
                    "operation": {
                        "type": "string",
                        "description": "Operation to perform: 'view' (get details), 'update' (modify metadata), 'thumbnail' (update thumbnail), 'optimize' (AI suggestions), or 'all' (view then update)",
                        "enum": ["view", "update", "thumbnail", "optimize", "all"]
                    },
                    "updates": {
                        "type": "object",
                        "description": "Updates to apply (for 'update' or 'all' operations)",
                        "properties": {
                            "title": {"type": "string", "description": "New video title"},
                            "description": {"type": "string", "description": "New video description"},
                            "tags": {"type": "array", "items": {"type": "string"}, "description": "New tags"},
                            "category_id": {"type": "string", "description": "New category ID"},
                            "privacy_status": {"type": "string", "enum": ["private", "unlisted", "public"]},
                            "thumbnail_path": {"type": "string", "description": "Path to new thumbnail image"}
                        }
                    },
                    "include_analytics": {
                        "type": "boolean",
                        "description": "Include performance analytics and optimization suggestions (default: true)"
                    }
                },
                "required": ["video_id", "operation"]
            }
        }
    })
    async def youtube_manage_video(
        self,
        video_id: str,
        operation: str = "view",
        updates: Optional[Dict[str, Any]] = None,
        include_analytics: bool = True
    ) -> ToolResult:
        """Unified video management - view, update, optimize all in one"""
        try:
            results = {}
            
            # Get current video details if needed
            if operation in ["view", "all", "optimize"]:
                # Direct API call to get video details
                async with aiohttp.ClientSession() as session:
                    headers = {
                        "Authorization": f"Bearer {self.jwt_token}",
                        "Content-Type": "application/json"
                    }
                    
                    async with session.get(
                        f"{self.base_url}/youtube/videos/{video_id}/details",
                        headers=headers
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            return self.fail_response(f"Failed to get video details: {error_text}")
                        
                        data = await response.json()
                        results["current_details"] = data
            
            # Apply updates if requested
            if operation in ["update", "all"] and updates:
                # Handle thumbnail separately if provided
                thumbnail_path = updates.pop("thumbnail_path", None)
                
                # Update video metadata if any non-thumbnail updates
                if updates:
                    # Direct API call to update video
                    async with aiohttp.ClientSession() as session:
                        headers = {
                            "Authorization": f"Bearer {self.jwt_token}",
                            "Content-Type": "application/json"
                        }
                        
                        async with session.put(
                            f"{self.base_url}/youtube/videos/{video_id}",
                            headers=headers,
                            json=updates
                        ) as response:
                            if response.status != 200:
                                error_text = await response.text()
                                return self.fail_response(f"Failed to update video: {error_text}")
                            
                            data = await response.json()
                            results["metadata_update"] = data
                
                # Update thumbnail if provided
                if thumbnail_path:
                    # Direct API call to update thumbnail
                    if not os.path.exists(thumbnail_path):
                        return self.fail_response(f"Thumbnail file not found: {thumbnail_path}")
                    
                    async with aiohttp.ClientSession() as session:
                        headers = {"Authorization": f"Bearer {self.jwt_token}"}
                        
                        with open(thumbnail_path, 'rb') as f:
                            data = aiohttp.FormData()
                            data.add_field('thumbnail', f, filename=os.path.basename(thumbnail_path))
                            
                            async with session.post(
                                f"{self.base_url}/youtube/videos/{video_id}/thumbnail",
                                headers=headers,
                                data=data
                            ) as response:
                                if response.status != 200:
                                    error_text = await response.text()
                                    return self.fail_response(f"Failed to update thumbnail: {error_text}")
                                
                                thumb_data = await response.json()
                                results["thumbnail_update"] = thumb_data
            
            # Handle thumbnail-only operation
            elif operation == "thumbnail" and updates and updates.get("thumbnail_path"):
                thumbnail_path = updates["thumbnail_path"]
                
                if not os.path.exists(thumbnail_path):
                    return self.fail_response(f"Thumbnail file not found: {thumbnail_path}")
                
                async with aiohttp.ClientSession() as session:
                    headers = {"Authorization": f"Bearer {self.jwt_token}"}
                    
                    with open(thumbnail_path, 'rb') as f:
                        data = aiohttp.FormData()
                        data.add_field('thumbnail', f, filename=os.path.basename(thumbnail_path))
                        
                        async with session.post(
                            f"{self.base_url}/youtube/videos/{video_id}/thumbnail",
                            headers=headers,
                            data=data
                        ) as response:
                            if response.status != 200:
                                error_text = await response.text()
                                return self.fail_response(f"Failed to update thumbnail: {error_text}")
                            
                            thumb_data = await response.json()
                            results["thumbnail_update"] = thumb_data
            
            # Provide optimization suggestions
            if operation == "optimize" and include_analytics:
                video_data = results.get("current_details", {}).get("video", {})
                suggestions = self._generate_optimization_suggestions(video_data)
                results["optimization_suggestions"] = suggestions
            
            # Build comprehensive response message
            message = self._build_manage_video_message(operation, results, video_id)
            
            return self.success_response({
                "video_id": video_id,
                "operation": operation,
                "results": results,
                "message": message
            })
            
        except Exception as e:
            logger.error(f"Error in youtube_manage_video: {e}")
            return ToolResult(success=False, output=str(e))
    
    def _generate_optimization_suggestions(self, video_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI-powered optimization suggestions based on video performance"""
        suggestions = {
            "title_optimization": [],
            "description_optimization": [],
            "tag_suggestions": [],
            "timing_suggestions": [],
            "engagement_tips": []
        }
        
        # Analyze title
        title = video_data.get("title", "")
        if len(title) < 30:
            suggestions["title_optimization"].append("Consider a longer, more descriptive title (30-60 characters)")
        if not any(char in title for char in ["!", "?", "-", ":"]):
            suggestions["title_optimization"].append("Add punctuation for better engagement")
        
        # Analyze description
        description = video_data.get("description", "")
        if len(description) < 200:
            suggestions["description_optimization"].append("Expand description to at least 200 characters for better SEO")
        if "http" not in description.lower():
            suggestions["description_optimization"].append("Add relevant links to boost engagement")
        
        # Analyze performance metrics
        stats = video_data.get("statistics", {})
        views = stats.get("viewCount", 0)
        likes = stats.get("likeCount", 0)
        
        if views > 0 and likes / views < 0.04:
            suggestions["engagement_tips"].append("Like ratio below 4% - consider more engaging content or clearer CTAs")
        
        # Tag suggestions
        current_tags = video_data.get("tags", [])
        if len(current_tags) < 5:
            suggestions["tag_suggestions"].append("Add more tags (aim for 5-15 relevant tags)")
        
        return suggestions
    
    def _build_manage_video_message(self, operation: str, results: Dict[str, Any], video_id: str) -> str:
        """Build a comprehensive message for video management results"""
        message = f"📹 **Video Management Report** (ID: {video_id})\n\n"
        
        if "current_details" in results:
            video = results["current_details"].get("video", {})
            message += f"**Current Status:**\n"
            message += f"• Title: {video.get('title', 'Unknown')}\n"
            message += f"• Views: {video.get('statistics', {}).get('viewCount', 0):,}\n"
            message += f"• Privacy: {video.get('privacyStatus', 'Unknown')}\n\n"
        
        if "metadata_update" in results:
            message += "✅ **Metadata Updated Successfully**\n\n"
        
        if "thumbnail_update" in results:
            message += "✅ **Thumbnail Updated Successfully**\n\n"
        
        if "optimization_suggestions" in results:
            suggestions = results["optimization_suggestions"]
            message += "💡 **Optimization Suggestions:**\n"
            
            for category, items in suggestions.items():
                if items:
                    category_name = category.replace("_", " ").title()
                    message += f"\n**{category_name}:**\n"
                    for item in items:
                        message += f"• {item}\n"
        
        return message
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_smart_search",
            "description": "Intelligent unified search that understands context. Automatically detects if you're searching for videos, channels, playlists, or specific @handles. Provides enhanced results with analytics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query - can be keywords, @handle, channel name, or video title"
                    },
                    "search_type": {
                        "type": "string",
                        "description": "Force specific search type (optional - auto-detected if not specified)",
                        "enum": ["auto", "video", "channel", "playlist", "handle"]
                    },
                    "filters": {
                        "type": "object",
                        "description": "Advanced search filters",
                        "properties": {
                            "max_results": {"type": "integer", "minimum": 1, "maximum": 50},
                            "order": {"type": "string", "enum": ["relevance", "date", "rating", "title", "viewCount"]},
                            "published_after": {"type": "string", "description": "ISO date string"},
                            "published_before": {"type": "string", "description": "ISO date string"},
                            "min_views": {"type": "integer", "description": "Minimum view count"},
                            "channel_id": {"type": "string", "description": "Limit to specific channel"}
                        }
                    },
                    "include_analytics": {
                        "type": "boolean",
                        "description": "Include performance metrics and insights (default: true)"
                    }
                },
                "required": ["query"]
            }
        }
    })
    async def youtube_smart_search(
        self,
        query: str,
        search_type: str = "auto",
        filters: Optional[Dict[str, Any]] = None,
        include_analytics: bool = True
    ) -> ToolResult:
        """Smart unified search with context understanding"""
        try:
            # Auto-detect search type from query
            if search_type == "auto":
                search_type = self._detect_search_type(query)
                logger.info(f"Auto-detected search type: {search_type}")
            
            # Handle @handle searches
            if search_type == "handle" or query.startswith("@"):
                handle_result = await self.youtube_get_channel_by_handle(query)
                if handle_result.success:
                    # Enhance with analytics if requested
                    if include_analytics:
                        channel = handle_result.output.get("channel", {})
                        channel_id = channel.get("id")
                        if channel_id:
                            # Get detailed analytics
                            analytics_result = await self.youtube_channels(channel_id=channel_id, include_analytics=True)
                            if analytics_result.success:
                                handle_result.output["analytics"] = analytics_result.output.get("analytics_summary")
                return handle_result
            
            # Regular search with filters
            filters = filters or {}
            search_result = await self.youtube_search(
                query=query,
                search_type=search_type if search_type != "auto" else "video",
                max_results=filters.get("max_results", 10),
                order=filters.get("order", "relevance")
            )
            
            if not search_result.success:
                return search_result
            
            # Enhance results with additional insights
            if include_analytics:
                results = search_result.output.get("results", [])
                enhanced_results = self._enhance_search_results(results, search_type)
                search_result.output["enhanced_results"] = enhanced_results
                
                # Add search insights
                insights = self._generate_search_insights(results, query)
                search_result.output["insights"] = insights
            
            # Build enhanced message
            message = self._build_smart_search_message(
                query, search_type, search_result.output, include_analytics
            )
            search_result.output["message"] = message
            
            return search_result
            
        except Exception as e:
            logger.error(f"Error in youtube_smart_search: {e}")
            return ToolResult(success=False, output=str(e))
    
    def _detect_search_type(self, query: str) -> str:
        """Intelligently detect the type of search from the query"""
        query_lower = query.lower()
        
        # Check for @handle
        if query.startswith("@"):
            return "handle"
        
        # Check for channel indicators
        channel_keywords = ["channel", "creator", "youtuber", "subscribe"]
        if any(keyword in query_lower for keyword in channel_keywords):
            return "channel"
        
        # Check for playlist indicators
        playlist_keywords = ["playlist", "collection", "series", "compilation"]
        if any(keyword in query_lower for keyword in playlist_keywords):
            return "playlist"
        
        # Default to video search
        return "video"
    
    def _enhance_search_results(self, results: List[Dict], search_type: str) -> List[Dict]:
        """Add performance insights to search results"""
        enhanced = []
        for result in results[:5]:  # Enhance top 5 results
            enhanced_result = result.copy()
            
            if search_type == "video":
                # Add engagement metrics
                views = result.get("viewCount", 0)
                if views > 1000000:
                    enhanced_result["performance_badge"] = "🔥 Viral"
                elif views > 100000:
                    enhanced_result["performance_badge"] = "📈 Popular"
                elif views > 10000:
                    enhanced_result["performance_badge"] = "👍 Growing"
            
            enhanced.append(enhanced_result)
        
        return enhanced
    
    def _generate_search_insights(self, results: List[Dict], query: str) -> Dict[str, Any]:
        """Generate insights from search results"""
        insights = {
            "total_results": len(results),
            "query_analysis": f"Searched for: '{query}'",
            "top_performer": None,
            "avg_views": 0
        }
        
        if results:
            # Find top performer
            top = max(results, key=lambda x: x.get("viewCount", 0), default=None)
            if top:
                insights["top_performer"] = {
                    "title": top.get("title"),
                    "views": top.get("viewCount", 0)
                }
            
            # Calculate average views
            total_views = sum(r.get("viewCount", 0) for r in results)
            insights["avg_views"] = total_views // len(results) if results else 0
        
        return insights
    
    def _build_smart_search_message(
        self, query: str, search_type: str, output: Dict, include_analytics: bool
    ) -> str:
        """Build enhanced search results message"""
        message = f"🔍 **Smart Search Results for: '{query}'**\n"
        message += f"Type: {search_type.title()} Search\n\n"
        
        results = output.get("results", [])
        if not results:
            return message + "No results found. Try different keywords or broaden your search."
        
        # Add insights if available
        if include_analytics and "insights" in output:
            insights = output["insights"]
            message += "📊 **Search Insights:**\n"
            message += f"• Found {insights['total_results']} results\n"
            if insights.get("top_performer"):
                top = insights["top_performer"]
                message += f"• Top result: {top['title']} ({top['views']:,} views)\n"
            message += f"• Average views: {insights['avg_views']:,}\n\n"
        
        # Add top results
        message += "**Top Results:**\n"
        for i, result in enumerate(results[:5], 1):
            if search_type == "video":
                message += f"{i}. **{result.get('title', 'Unknown')}**\n"
                message += f"   • Channel: {result.get('channelTitle', 'Unknown')}\n"
                if "performance_badge" in result:
                    message += f"   • {result['performance_badge']}\n"
            elif search_type == "channel":
                message += f"{i}. **{result.get('title', 'Unknown')}**\n"
                if result.get('description'):
                    message += f"   • {result['description'][:100]}...\n"
            message += "\n"
        
        return message