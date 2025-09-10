"""YouTube Channel Service for managing connected channels"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from services.supabase import DBConnection
from utils.logger import logger


class YouTubeChannelService:
    """Service for managing YouTube channels"""
    
    def __init__(self, db: DBConnection):
        self.db = db
    
    async def get_user_channels(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active YouTube channels for a user"""
        client = await self.db.client
        
        # FIXED: Use compatibility view that filters by platform='youtube' only
        result = await client.table("youtube_channels_compat").select("*").eq(
            "user_id", user_id
        ).eq("is_active", True).order("created_at", desc=True).execute()
        
        channels = []
        for channel in result.data:
            channels.append({
                "id": channel["id"],
                "name": channel["name"],
                "username": channel.get("username"),
                "custom_url": channel.get("custom_url"),
                "profile_picture": channel.get("profile_picture"),
                "profile_picture_medium": channel.get("profile_picture_medium"),
                "profile_picture_small": channel.get("profile_picture_small"),
                "description": channel.get("description"),
                "subscriber_count": channel.get("subscriber_count", 0),
                "view_count": channel.get("view_count", 0),
                "video_count": channel.get("video_count", 0),
                "country": channel.get("country"),
                "published_at": channel.get("published_at"),
                "created_at": channel.get("created_at"),
                "updated_at": channel.get("updated_at"),
            })
        
        return channels
    
    async def get_channel(self, user_id: str, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific YouTube channel"""
        client = await self.db.client
        
        # FIXED: Use compatibility view that filters by platform='youtube' only
        result = await client.table("youtube_channels_compat").select("*").eq(
            "user_id", user_id
        ).eq("id", channel_id).eq("is_active", True).execute()
        
        if not result.data:
            return None
        
        channel = result.data[0]
        return {
            "id": channel["id"],
            "name": channel["name"],
            "username": channel.get("username"),
            "custom_url": channel.get("custom_url"),
            "profile_picture": channel.get("profile_picture"),
            "profile_picture_medium": channel.get("profile_picture_medium"),
            "profile_picture_small": channel.get("profile_picture_small"),
            "description": channel.get("description"),
            "subscriber_count": channel.get("subscriber_count", 0),
            "view_count": channel.get("view_count", 0),
            "video_count": channel.get("video_count", 0),
            "country": channel.get("country"),
            "published_at": channel.get("published_at"),
            "created_at": channel.get("created_at"),
            "updated_at": channel.get("updated_at"),
        }
    
    async def update_channel_stats(self, user_id: str, channel_id: str, stats: Dict[str, Any]) -> bool:
        """Update channel statistics"""
        client = await self.db.client
        
        update_data = {
            "subscriber_count": stats.get("subscriber_count"),
            "view_count": stats.get("view_count"),
            "video_count": stats.get("video_count"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Remove None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        # FIXED: Update via social_media_accounts table for unified system
        result = await client.table("social_media_accounts").update(update_data).eq(
            "user_id", user_id
        ).eq("platform", "youtube").eq("platform_account_id", channel_id).execute()
        
        if result.data:
            logger.info(f"Updated stats for channel {channel_id}")
            return True
        
        return False
    
    async def deactivate_channel(self, user_id: str, channel_id: str) -> bool:
        """SMART DEACTIVATION: Mark for re-auth instead of disconnecting (preserves user connections)"""
        client = await self.db.client
        
        logger.warning(f"🔄 SMART DEACTIVATION: Marking channel {channel_id} for re-auth instead of disconnecting")
        
        # FIXED: Update via social_media_accounts table for unified system
        result = await client.table("social_media_accounts").update({
            "needs_reauth": True,  # Mark for re-auth instead of disconnecting
            "last_refresh_error": "Channel marked for re-authentication due to system issues",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            # is_active stays TRUE - preserve connection!
        }).eq("user_id", user_id).eq("platform", "youtube").eq("platform_account_id", channel_id).execute()
        
        if result.data:
            logger.info(f"✅ Smart deactivation: Channel {channel_id} marked for re-auth (connection preserved)")
            return True
        
        return False
    
    async def channel_exists(self, user_id: str, channel_id: str) -> bool:
        """Check if a channel exists for a user"""
        client = await self.db.client
        
        # FIXED: Check via social_media_accounts table for unified system
        result = await client.table("social_media_accounts").select("platform_account_id").eq(
            "user_id", user_id
        ).eq("platform", "youtube").eq("platform_account_id", channel_id).eq("is_active", True).execute()
        
        return len(result.data) > 0