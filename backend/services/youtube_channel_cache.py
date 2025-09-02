"""YouTube Channel Cache Service for pre-computed context injection.

This service manages cached YouTube channel metadata and toggle states to eliminate 
runtime database queries during agent execution, providing a seamless experience
while reducing API costs.
"""

import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from utils.logger import logger
from services import redis
from services.supabase import DBConnection
from youtube_mcp.channels import YouTubeChannelService
from services.mcp_toggles import MCPToggleService


class YouTubeChannelCacheService:
    """Service for caching YouTube channel metadata with toggle states."""
    
    # Cache configuration
    CACHE_TTL = 3600  # 1 hour TTL for channel cache
    CACHE_KEY_PREFIX = "youtube:channels"
    INVALIDATION_CHANNEL = "youtube:cache:invalidate"
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.channel_service = YouTubeChannelService(db)
        self.toggle_service = MCPToggleService(db)
    
    def _get_cache_key(self, user_id: str, agent_id: Optional[str] = None) -> str:
        """Generate cache key for user/agent combination."""
        if agent_id:
            return f"{self.CACHE_KEY_PREFIX}:{user_id}:{agent_id}"
        else:
            return f"{self.CACHE_KEY_PREFIX}:{user_id}:all"
    
    def _get_user_cache_pattern(self, user_id: str) -> str:
        """Generate cache key pattern for all user's cached channels."""
        return f"{self.CACHE_KEY_PREFIX}:{user_id}:*"
    
    async def get_enabled_channels(self, user_id: str, agent_id: str) -> List[Dict[str, Any]]:
        """Get enabled YouTube channels for a specific agent from cache or database."""
        cache_key = self._get_cache_key(user_id, agent_id)
        
        try:
            # Try to get from cache first
            cached_data = await redis.get(cache_key)
            if cached_data:
                channels_data = json.loads(cached_data)
                logger.info(f"Retrieved {len(channels_data)} YouTube channels from cache for agent {agent_id}")
                return channels_data
            
            logger.info(f"Cache miss for YouTube channels, fetching from database for agent {agent_id}")
            
            # Cache miss - compute and store
            enabled_channels = await self._compute_enabled_channels(user_id, agent_id)
            
            # Store in cache
            await self._set_cache(cache_key, enabled_channels)
            
            return enabled_channels
            
        except Exception as e:
            logger.error(f"Error getting channels from cache, falling back to database: {e}")
            # Fallback to direct database query
            return await self._compute_enabled_channels(user_id, agent_id)
    
    async def get_all_user_channels(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all YouTube channels for a user (without toggle filtering)."""
        cache_key = self._get_cache_key(user_id)
        
        try:
            # Try to get from cache first
            cached_data = await redis.get(cache_key)
            if cached_data:
                channels_data = json.loads(cached_data)
                logger.info(f"Retrieved {len(channels_data)} YouTube channels from cache for user {user_id}")
                return channels_data
            
            logger.info(f"Cache miss for user channels, fetching from database for user {user_id}")
            
            # Cache miss - fetch from database
            all_channels = await self.channel_service.get_user_channels(user_id)
            
            # Store in cache
            await self._set_cache(cache_key, all_channels)
            
            return all_channels
            
        except Exception as e:
            logger.error(f"Error getting user channels from cache, falling back to database: {e}")
            # Fallback to direct database query
            return await self.channel_service.get_user_channels(user_id)
    
    async def _compute_enabled_channels(self, user_id: str, agent_id: str) -> List[Dict[str, Any]]:
        """Compute enabled channels for a specific agent by checking toggles."""
        try:
            # Get all connected channels
            all_channels = await self.channel_service.get_user_channels(user_id)
            
            # Filter to only enabled channels via MCP toggles
            enabled_channels = []
            for channel in all_channels:
                mcp_id = f"social.youtube.{channel['id']}"
                is_enabled = await self.toggle_service.is_enabled(agent_id, user_id, mcp_id)
                if is_enabled:
                    enabled_channels.append(channel)
                    logger.info(f"✅ YouTube channel {channel['name']} ({channel['id']}) is ENABLED for agent {agent_id}")
                else:
                    logger.info(f"❌ YouTube channel {channel['name']} ({channel['id']}) is DISABLED for agent {agent_id}")
            
            logger.info(f"Computed {len(enabled_channels)} enabled YouTube channels for agent {agent_id}")
            return enabled_channels
            
        except Exception as e:
            logger.error(f"Error computing enabled channels: {e}")
            return []
    
    async def _set_cache(self, cache_key: str, channels: List[Dict[str, Any]]):
        """Store channels in cache with TTL."""
        try:
            channels_json = json.dumps(channels, default=str)
            await redis.set(cache_key, channels_json, ex=self.CACHE_TTL)
            logger.debug(f"Cached {len(channels)} YouTube channels with key {cache_key}")
        except Exception as e:
            logger.error(f"Error setting cache for key {cache_key}: {e}")
    
    async def invalidate_user_cache(self, user_id: str, reason: str = "manual"):
        """Invalidate all cached data for a user."""
        try:
            pattern = self._get_user_cache_pattern(user_id)
            keys = await redis.keys(pattern)
            
            if keys:
                await redis.delete(*keys)
                logger.info(f"Invalidated {len(keys)} YouTube channel cache entries for user {user_id} (reason: {reason})")
            else:
                logger.debug(f"No cache entries to invalidate for user {user_id}")
            
            # Publish invalidation event
            await self._publish_invalidation(user_id, reason)
            
        except Exception as e:
            logger.error(f"Error invalidating cache for user {user_id}: {e}")
    
    async def invalidate_agent_cache(self, user_id: str, agent_id: str, reason: str = "toggle_change"):
        """Invalidate cached data for a specific agent."""
        try:
            cache_key = self._get_cache_key(user_id, agent_id)
            await redis.delete(cache_key)
            logger.info(f"Invalidated YouTube channel cache for agent {agent_id} (reason: {reason})")
            
            # Publish invalidation event
            await self._publish_invalidation(user_id, reason, agent_id)
            
        except Exception as e:
            logger.error(f"Error invalidating cache for agent {agent_id}: {e}")
    
    async def _publish_invalidation(self, user_id: str, reason: str, agent_id: Optional[str] = None):
        """Publish cache invalidation event for real-time updates."""
        try:
            invalidation_data = {
                "user_id": user_id,
                "agent_id": agent_id,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await redis.publish(self.INVALIDATION_CHANNEL, json.dumps(invalidation_data))
            logger.debug(f"Published cache invalidation event: {invalidation_data}")
            
        except Exception as e:
            logger.error(f"Error publishing invalidation event: {e}")
    
    async def warm_cache_for_user(self, user_id: str, agent_ids: Optional[List[str]] = None):
        """Pre-warm cache for a user and their agents."""
        try:
            # Warm user's all channels cache
            await self.get_all_user_channels(user_id)
            
            if agent_ids:
                # Warm agent-specific caches
                for agent_id in agent_ids:
                    await self.get_enabled_channels(user_id, agent_id)
                
                logger.info(f"Warmed YouTube channel cache for user {user_id} and {len(agent_ids)} agents")
            else:
                logger.info(f"Warmed YouTube channel cache for user {user_id}")
                
        except Exception as e:
            logger.error(f"Error warming cache for user {user_id}: {e}")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        try:
            pattern = f"{self.CACHE_KEY_PREFIX}:*"
            keys = await redis.keys(pattern)
            
            stats = {
                "total_cached_entries": len(keys),
                "cache_key_prefix": self.CACHE_KEY_PREFIX,
                "cache_ttl_seconds": self.CACHE_TTL,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Get TTL info for a sample of keys
            if keys:
                sample_key = keys[0]
                ttl = await redis.ttl(sample_key)
                stats["sample_key_ttl"] = ttl
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def handle_channel_connected(self, user_id: str, channel_id: str):
        """Handle when a new channel is connected."""
        logger.info(f"Handling YouTube channel connection: {channel_id} for user {user_id}")
        await self.invalidate_user_cache(user_id, reason="channel_connected")
    
    async def handle_channel_disconnected(self, user_id: str, channel_id: str):
        """Handle when a channel is disconnected."""
        logger.info(f"Handling YouTube channel disconnection: {channel_id} for user {user_id}")
        await self.invalidate_user_cache(user_id, reason="channel_disconnected")
    
    async def handle_toggle_change(self, user_id: str, agent_id: str, mcp_id: str, enabled: bool):
        """Handle when a toggle state changes."""
        if mcp_id.startswith("social.youtube."):
            channel_id = mcp_id.replace("social.youtube.", "")
            logger.info(f"Handling YouTube channel toggle change: {channel_id} -> {enabled} for agent {agent_id}")
            await self.invalidate_agent_cache(user_id, agent_id, reason="toggle_change")