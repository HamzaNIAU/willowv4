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
        """Get all active YouTube channels for a user.

        Fallback order for maximum compatibility:
        1) youtube_channels_compat view (preferred, unified model)
        2) social_media_accounts where platform='youtube'
        3) legacy youtube_channels table
        """
        client = await self.db.client

        def _row_to_channel(row: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "id": row.get("id") or row.get("platform_account_id"),
                "name": row.get("name") or row.get("account_name"),
                "username": row.get("username"),
                "custom_url": row.get("custom_url") or (row.get("platform_data", {}) or {}).get("custom_url"),
                "profile_picture": row.get("profile_picture") or row.get("profile_image_url"),
                "profile_picture_medium": row.get("profile_picture_medium") or (row.get("platform_data", {}) or {}).get("profile_picture_medium"),
                "profile_picture_small": row.get("profile_picture_small") or (row.get("platform_data", {}) or {}).get("profile_picture_small"),
                "description": row.get("description") or row.get("bio"),
                "subscriber_count": row.get("subscriber_count", 0),
                "view_count": row.get("view_count", 0),
                "video_count": row.get("video_count") if "video_count" in row else row.get("post_count", 0),
                "country": row.get("country") or (row.get("platform_data", {}) or {}).get("country"),
                "published_at": row.get("published_at") or (row.get("platform_data", {}) or {}).get("published_at"),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
            }

        # Attempt 1: unified compatibility view
        try:
            result = await client.table("youtube_channels_compat").select("*").eq(
                "user_id", user_id
            ).eq("is_active", True).order("created_at", desc=True).execute()
            return [_row_to_channel(ch) for ch in result.data]
        except Exception as e:
            logger.warning(f"youtube_channels_compat not available, falling back (error: {e})")

        # Attempt 2: unified social_media_accounts
        try:
            result = await client.table("social_media_accounts").select("*").eq(
                "user_id", user_id
            ).eq("platform", "youtube").eq("is_active", True).order("created_at", desc=True).execute()
            return [_row_to_channel(ch) for ch in result.data]
        except Exception as e:
            logger.warning(f"social_media_accounts fallback failed, trying legacy table (error: {e})")

        # Attempt 3: legacy table
        try:
            result = await client.table("youtube_channels").select("*").eq(
                "user_id", user_id
            ).eq("is_active", True).order("created_at", desc=True).execute()
            return [_row_to_channel(ch) for ch in result.data]
        except Exception as e:
            logger.error(f"All fallbacks failed for get_user_channels: {e}")
            return []
    
    async def get_channel(self, user_id: str, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific YouTube channel with robust fallbacks (compat view → unified table → legacy)."""
        client = await self.db.client

        def _row_to_channel(row: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "id": row.get("id") or row.get("platform_account_id"),
                "name": row.get("name") or row.get("account_name"),
                "username": row.get("username"),
                "custom_url": row.get("custom_url") or (row.get("platform_data", {}) or {}).get("custom_url"),
                "profile_picture": row.get("profile_picture") or row.get("profile_image_url"),
                "profile_picture_medium": row.get("profile_picture_medium") or (row.get("platform_data", {}) or {}).get("profile_picture_medium"),
                "profile_picture_small": row.get("profile_picture_small") or (row.get("platform_data", {}) or {}).get("profile_picture_small"),
                "description": row.get("description") or row.get("bio"),
                "subscriber_count": row.get("subscriber_count", 0),
                "view_count": row.get("view_count", 0),
                "video_count": row.get("video_count") if "video_count" in row else row.get("post_count", 0),
                "country": row.get("country") or (row.get("platform_data", {}) or {}).get("country"),
                "published_at": row.get("published_at") or (row.get("platform_data", {}) or {}).get("published_at"),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
            }

        # Attempt 1: compat view
        try:
            result = await client.table("youtube_channels_compat").select("*").eq(
                "user_id", user_id
            ).eq("id", channel_id).eq("is_active", True).execute()
            if result.data:
                return _row_to_channel(result.data[0])
        except Exception as e:
            logger.warning(f"youtube_channels_compat not available for single fetch, fallback (error: {e})")

        # Attempt 2: unified table
        try:
            result = await client.table("social_media_accounts").select("*").eq(
                "user_id", user_id
            ).eq("platform", "youtube").eq("platform_account_id", channel_id).eq("is_active", True).execute()
            if result.data:
                return _row_to_channel(result.data[0])
        except Exception as e:
            logger.warning(f"social_media_accounts fallback failed for single fetch, trying legacy (error: {e})")

        # Attempt 3: legacy table
        try:
            result = await client.table("youtube_channels").select("*").eq(
                "user_id", user_id
            ).eq("id", channel_id).eq("is_active", True).execute()
            if result.data:
                return _row_to_channel(result.data[0])
        except Exception as e:
            logger.error(f"All fallbacks failed for get_channel: {e}")

        return None
    
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
