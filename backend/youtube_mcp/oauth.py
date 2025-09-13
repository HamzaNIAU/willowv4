"""YouTube OAuth handler for MCP integration"""

import os
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlencode

import aiohttp
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False
    Request = None
    Credentials = None
    build = None
from cryptography.fernet import Fernet

from services.supabase import DBConnection
from utils.logger import logger


class YouTubeOAuthHandler:
    """Handles YouTube OAuth flow and token management"""
    
    OAUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/yt-analytics.readonly",
        "https://www.googleapis.com/auth/youtube.force-ssl",
    ]
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.client_id = os.getenv("YOUTUBE_CLIENT_ID")
        self.client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("YOUTUBE_REDIRECT_URI", "http://localhost:8000/api/youtube/auth/callback")
        
        # Encryption key for tokens
        encryption_key = os.getenv("MCP_CREDENTIAL_ENCRYPTION_KEY")
        if encryption_key:
            self.fernet = Fernet(encryption_key.encode())
        else:
            # Generate a key if not provided (not recommended for production)
            logger.warning("No MCP_CREDENTIAL_ENCRYPTION_KEY found, generating temporary key")
            self.fernet = Fernet(Fernet.generate_key())
        
        if not self.client_id or not self.client_secret:
            raise ValueError("YouTube OAuth credentials not configured")
    
    def get_auth_url(self, state: Optional[str] = None) -> str:
        """Generate OAuth authorization URL"""
        if not state:
            state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        
        return f"{self.OAUTH_URL}?{urlencode(params)}"
    
    async def exchange_code_for_tokens(self, code: str) -> Tuple[str, str, datetime]:
        """Exchange authorization code for access and refresh tokens"""
        async with aiohttp.ClientSession() as session:
            data = {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            }
            
            async with session.post(self.TOKEN_URL, data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Token exchange failed: {error_text}")
                
                token_data = await response.json()
                
                access_token = token_data["access_token"]
                refresh_token = token_data.get("refresh_token")
                expires_in = token_data.get("expires_in", 3600)
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                
                return access_token, refresh_token, expires_at
    
    async def refresh_access_token(self, refresh_token: str) -> Tuple[str, datetime]:
        """Refresh an expired access token"""
        async with aiohttp.ClientSession() as session:
            data = {
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
            }
            
            async with session.post(self.TOKEN_URL, data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Token refresh failed: {error_text}")
                
                token_data = await response.json()
                
                access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                
                return access_token, expires_at
    
    async def get_channel_info(self, access_token: str) -> Dict[str, Any]:
        """Fetch YouTube channel information for authenticated user"""
        credentials = Credentials(token=access_token)
        youtube = build("youtube", "v3", credentials=credentials)
        
        try:
            # Get user's channel
            channels_response = youtube.channels().list(
                part="snippet,statistics,contentDetails",
                mine=True
            ).execute()
            
            if not channels_response.get("items"):
                raise Exception("No YouTube channel found for this account")
            
            channel = channels_response["items"][0]
            snippet = channel.get("snippet", {})
            statistics = channel.get("statistics", {})
            
            # Extract channel information
            thumbnails = snippet.get("thumbnails", {})
            
            # Try to get the best available thumbnail
            profile_picture = (
                thumbnails.get("high", {}).get("url") or
                thumbnails.get("medium", {}).get("url") or
                thumbnails.get("default", {}).get("url")
            )
            
            channel_info = {
                "id": channel["id"],
                "name": snippet.get("title", ""),
                "username": snippet.get("customUrl", "").replace("@", "") if snippet.get("customUrl") else None,
                "custom_url": snippet.get("customUrl"),
                "description": snippet.get("description", ""),
                "profile_picture": profile_picture,
                "profile_picture_medium": thumbnails.get("medium", {}).get("url") or profile_picture,
                "profile_picture_small": thumbnails.get("default", {}).get("url") or profile_picture,
                "subscriber_count": int(statistics.get("subscriberCount", 0)),
                "view_count": int(statistics.get("viewCount", 0)),
                "video_count": int(statistics.get("videoCount", 0)),
                "country": snippet.get("country"),
                "published_at": snippet.get("publishedAt"),
            }
            
            logger.info(f"Fetched channel info for {channel_info['name']}: profile_picture={profile_picture}")
            
            return channel_info
            
        except Exception as e:
            logger.error(f"Failed to fetch channel info: {e}")
            raise
    
    def encrypt_token(self, token: str) -> str:
        """Encrypt a token for storage"""
        return self.fernet.encrypt(token.encode()).decode()
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt a stored token"""
        return self.fernet.decrypt(encrypted_token.encode()).decode()
    
    async def save_channel(
        self,
        user_id: str,
        channel_info: Dict[str, Any],
        access_token: str,
        refresh_token: Optional[str],
        expires_at: datetime
    ) -> str:
        """Save YouTube channel to database"""
        client = await self.db.client
        
        # Encrypt tokens
        encrypted_access = self.encrypt_token(access_token)
        encrypted_refresh = self.encrypt_token(refresh_token) if refresh_token else None
        
        # Prepare channel data
        channel_data = {
            "id": channel_info["id"],
            "user_id": user_id,
            "name": channel_info["name"],
            "username": channel_info.get("username"),
            "custom_url": channel_info.get("custom_url"),
            "profile_picture": channel_info.get("profile_picture"),
            "profile_picture_medium": channel_info.get("profile_picture_medium"),
            "profile_picture_small": channel_info.get("profile_picture_small"),
            "description": channel_info.get("description"),
            "subscriber_count": channel_info.get("subscriber_count", 0),
            "view_count": channel_info.get("view_count", 0),
            "video_count": channel_info.get("video_count", 0),
            "country": channel_info.get("country"),
            "published_at": channel_info.get("published_at"),
            "access_token": encrypted_access,
            "refresh_token": encrypted_refresh,
            "token_expires_at": expires_at.isoformat(),
            "token_scopes": self.SCOPES,
            "is_active": True,
        }
        
        # Use universal integrations service (Postiz-style)
        from services.unified_integration_service import UnifiedIntegrationService
        integration_service = UnifiedIntegrationService(self.db)
        
        # Calculate expires_in for Postiz pattern
        expires_in = int((expires_at - datetime.now(timezone.utc)).total_seconds()) if expires_at else None
        
        # Prepare YouTube-specific platform data (preserve ALL YouTube concepts!)
        platform_data = {
            "channel_id": channel_info["id"],
            "username": channel_info.get("username"),
            "custom_url": channel_info.get("custom_url"),
            "description": channel_info.get("description"),
            "subscriber_count": channel_info.get("subscriber_count", 0),
            "view_count": channel_info.get("view_count", 0),
            "video_count": channel_info.get("video_count", 0),
            "country": channel_info.get("country"),
            "published_at": channel_info.get("published_at"),
            "profile_pictures": {
                "default": channel_info.get("profile_picture"),
                "medium": channel_info.get("profile_picture_medium"),
                "small": channel_info.get("profile_picture_small")
            }
        }
        
        # Save using universal integrations table
        integration_id = await integration_service.save_integration(
            user_id=user_id,
            platform="youtube",
            platform_account_id=channel_info["id"],
            account_data={
                "name": channel_info["name"],
                "picture": channel_info.get("profile_picture"),
                "platform_data": platform_data
            },
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=expires_at,
            token_scopes=self.SCOPES
        )
        
        logger.info(f"✅ Saved YouTube integration {integration_id} for user {user_id}")
        
        # Invalidate cache to reflect the newly connected channel
        try:
            from services.youtube_channel_cache import YouTubeChannelCacheService
            cache_service = YouTubeChannelCacheService(self.db)
            await cache_service.handle_channel_connected(user_id, channel_info["id"])
        except Exception as e:
            logger.warning(f"Failed to invalidate cache after channel connection: {e}")
        
        # Create agent_integrations for all user's agents (including suna-default)
        try:
            client = await self.db.client
            agents_result = await client.table("agents").select("agent_id").eq("account_id", user_id).execute()
            agent_ids = [a["agent_id"] for a in (agents_result.data or [])]
            if "suna-default" not in agent_ids:
                agent_ids.append("suna-default")
            for agent_id in agent_ids:
                await integration_service.create_agent_integration(
                    agent_id=agent_id,
                    user_id=user_id,
                    integration_id=integration_id,
                    enabled=True
                )
        except Exception as e:
            logger.warning(f"Failed to create agent_integrations for YouTube: {e}")

        return channel_info["id"]
    
    async def _create_channel_toggles(self, user_id: str, channel_id: str):
        """Create MCP toggle entries for all user's agents when a channel is connected"""
        from services.mcp_toggles import MCPToggleService
        
        client = await self.db.client
        toggle_service = MCPToggleService(self.db)
        
        try:
            # Get all agents for this user
            agents_result = await client.table("agents").select("agent_id").eq(
                "account_id", user_id
            ).execute()
            
            if agents_result.data:
                mcp_id = f"social.youtube.{channel_id}"
                created_count = 0
                
                for agent in agents_result.data:
                    agent_id = agent["agent_id"]
                    
                    # Create toggle entry (default to enabled for better UX)
                    success = await toggle_service.set_toggle(
                        agent_id=agent_id,
                        user_id=user_id,
                        mcp_id=mcp_id,
                        enabled=True  # Default to enabled - user can disable if needed
                    )
                    
                    if success:
                        created_count += 1
                        logger.info(f"Created MCP toggle for agent {agent_id}, channel {channel_id} (enabled by default)")
                
                if created_count > 0:
                    logger.info(f"Created {created_count} MCP toggle entries for YouTube channel {channel_id}")
            else:
                logger.info(f"No agents found for user {user_id}, no toggles created")
                
        except Exception as e:
            logger.error(f"Failed to create MCP toggles for channel {channel_id}: {e}")
            # Don't fail the channel save if toggle creation fails
    
    async def get_valid_token(self, user_id: str, channel_id: str) -> str:
        """Get a valid access token, refreshing if necessary"""
        client = await self.db.client
        # Read from integrations table
        integ_result = await client.table("integrations").select("*").eq(
            "user_id", user_id
        ).eq("platform", "youtube").eq("platform_account_id", channel_id).single().execute()

        if not integ_result.data:
            raise Exception(f"YouTube integration for {channel_id} not found")

        integration = integ_result.data
        # Decrypt tokens
        access_token = self.decrypt_token(integration.get("access_token")) if integration.get("access_token") else None
        refresh_token = self.decrypt_token(integration.get("refresh_token")) if integration.get("refresh_token") else None
        
        # SMART MORPHIC-INSPIRED TOKEN MANAGEMENT
        # Parse token expiry time with robust timezone handling
        token_expires = integration.get("token_expires_at")
        if token_expires.endswith('Z'):
            token_expires = token_expires.replace('Z', '+00:00')
        elif '+' not in token_expires and '-' not in token_expires[-6:]:
            # No timezone info, assume UTC
            token_expires = token_expires + '+00:00'
        expires_at = datetime.fromisoformat(token_expires)
        
        # MORPHIC PATTERN: Proactive 5-minute buffer for seamless experience
        buffer_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        time_until_expiry = expires_at - datetime.now(timezone.utc)
        
        logger.info(f"🔍 Token Check: Expires {expires_at}, Buffer {buffer_time}, Time left: {time_until_expiry}")
        
        # SMART DECISION: Token still has >5 minutes? Use it!
        if expires_at > buffer_time:
            logger.debug(f"✅ Token Valid: {time_until_expiry} remaining for integration {channel_id}")
            return access_token
        
        # FULLY AUTOMATIC REFRESH: Zero manual intervention required
        if not refresh_token:
            logger.warning(f"⚠️ No refresh token available for integration {channel_id} - using fallback token strategy")
            
            # AUTOMATIC FALLBACK: Try to use existing token anyway (might still work)
            logger.info(f"🤖 AUTOMATIC FALLBACK: Attempting upload with existing token for integration {channel_id}")
            return access_token  # Let upload attempt proceed, might still work
        
        logger.info(f"🤖 FULLY AUTOMATIC REFRESH: Silently refreshing token for integration {channel_id} (expires in {time_until_expiry})")
        
        try:
            # SILENT AUTOMATIC REFRESH: No user interaction required
            new_access_token, new_expires_at = await self.refresh_access_token(refresh_token)
            
            # Update database with fresh token
            encrypted_access = self.encrypt_token(new_access_token)
            await client.table("integrations").update({
                "access_token": encrypted_access,
                "token_expires_at": new_expires_at.isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "refresh_needed": False
            }).eq("user_id", user_id).eq("platform", "youtube").eq("platform_account_id", channel_id).execute()
            
            new_time_until_expiry = new_expires_at - datetime.now(timezone.utc)
            logger.info(f"🎉 SILENT REFRESH SUCCESS: integration {channel_id} token automatically renewed! New expiry: {new_expires_at}")
            
            return new_access_token
            
        except Exception as refresh_error:
            logger.warning(f"⚠️ AUTOMATIC REFRESH ATTEMPT FAILED for {channel['name']}: {refresh_error}")
            
            # GRACEFUL DEGRADATION: Don't throw errors, try to continue with existing token
            await client.table("integrations").update({
                "last_refresh_error": str(refresh_error),
                "last_refresh_attempt": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("user_id", user_id).eq("platform", "youtube").eq("platform_account_id", channel_id).execute()
            
            # AUTOMATIC FALLBACK: Try existing token anyway (might still work for a bit)
            logger.info(f"🤖 AUTOMATIC FALLBACK: Using existing token for integration {channel_id} despite refresh failure")
            return access_token  # Let upload proceed - might work anyway
    
    async def get_user_channels(self, user_id: str) -> list:
        """Get all YouTube channels for a user from integrations."""
        client = await self.db.client
        result = await client.table("integrations").select("*").eq(
            "user_id", user_id
        ).eq("platform", "youtube").eq("disabled", False).execute()
        channels = []
        for integ in result.data or []:
            pdata = json.loads(integ.get("platform_data") or '{}') if isinstance(integ.get("platform_data"), str) else (integ.get("platform_data") or {})
            channels.append({
                "id": integ["platform_account_id"],
                "name": integ["name"],
                "username": pdata.get("username"),
                "profile_picture": integ.get("picture"),
                "subscriber_count": pdata.get("subscriber_count", 0),
                "video_count": pdata.get("video_count", 0),
                "view_count": pdata.get("view_count", 0),
            })
        return channels
    
    async def remove_channel(self, user_id: str, channel_id: str) -> bool:
        """Remove a YouTube channel connection and clean up associated toggles"""
        client = await self.db.client
        
        # First, clean up MCP toggles for this channel
        await self._cleanup_channel_toggles(user_id, channel_id)
        
        # Then disable the integration
        from services.unified_integration_service import UnifiedIntegrationService
        integration_service = UnifiedIntegrationService(self.db)
        integrations = await integration_service.get_user_integrations(user_id, platform="youtube")
        target = next((i for i in integrations if i.get("platform_account_id") == channel_id), None)
        success = False
        if target:
            success = await integration_service.remove_integration(user_id, target["id"])
        
        if success:
            logger.info(f"Removed YouTube integration {channel_id} for user {user_id}")
            
            # Invalidate cache to reflect the removed channel
            try:
                from services.youtube_channel_cache import YouTubeChannelCacheService
                cache_service = YouTubeChannelCacheService(self.db)
                await cache_service.handle_channel_disconnected(user_id, channel_id)
            except Exception as e:
                logger.warning(f"Failed to invalidate cache after channel removal: {e}")
        
        return success
    
    async def _cleanup_channel_toggles(self, user_id: str, channel_id: str):
        """Clean up MCP toggle entries when a channel is disconnected"""
        client = await self.db.client
        
        try:
            mcp_id = f"social.youtube.{channel_id}"
            
            # Delete all toggle entries for this channel
            result = await client.table("agent_mcp_toggles").delete().eq(
                "user_id", user_id
            ).eq("mcp_id", mcp_id).execute()
            
            if result.data:
                logger.info(f"Cleaned up {len(result.data)} MCP toggle entries for channel {channel_id}")
            else:
                logger.info(f"No MCP toggle entries found for channel {channel_id}")
                
        except Exception as e:
            logger.error(f"Failed to clean up MCP toggles for channel {channel_id}: {e}")
            # Don't fail the channel removal if toggle cleanup fails
