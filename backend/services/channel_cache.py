"""In-memory channel caching with LRU eviction for performance optimization"""

import asyncio
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from collections import OrderedDict
import hashlib
import json

from utils.logger import logger


class LRUCache:
    """Thread-safe LRU cache implementation"""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        """
        Initialize LRU cache
        
        Args:
            max_size: Maximum number of items in cache
            ttl_seconds: Time-to-live for cache entries in seconds
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self.lock = asyncio.Lock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get item from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        async with self.lock:
            if key not in self.cache:
                self.misses += 1
                return None
            
            value, timestamp = self.cache[key]
            
            # Check if expired
            if time.time() - timestamp > self.ttl_seconds:
                del self.cache[key]
                self.misses += 1
                return None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            self.hits += 1
            return value
    
    async def set(self, key: str, value: Any) -> None:
        """
        Set item in cache
        
        Args:
            key: Cache key
            value: Value to cache
        """
        async with self.lock:
            # If key exists, update and move to end
            if key in self.cache:
                self.cache[key] = (value, time.time())
                self.cache.move_to_end(key)
            else:
                # Add new entry
                self.cache[key] = (value, time.time())
                
                # Evict oldest if over capacity
                if len(self.cache) > self.max_size:
                    self.cache.popitem(last=False)
                    self.evictions += 1
    
    async def delete(self, key: str) -> bool:
        """
        Delete item from cache
        
        Args:
            key: Cache key
            
        Returns:
            True if item was deleted, False if not found
        """
        async with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries"""
        async with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        async with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "hit_rate": f"{hit_rate:.2f}%",
                "ttl_seconds": self.ttl_seconds
            }


class ChannelCache:
    """YouTube channel data caching service"""
    
    def __init__(self, max_channels: int = 100, ttl_seconds: int = 300):
        """
        Initialize channel cache
        
        Args:
            max_channels: Maximum number of channels to cache
            ttl_seconds: Time-to-live for cache entries
        """
        # Separate caches for different data types
        self.metadata_cache = LRUCache(max_channels, ttl_seconds)
        self.token_cache = LRUCache(max_channels, ttl_seconds // 2)  # Shorter TTL for tokens
        self.stats_cache = LRUCache(max_channels, ttl_seconds * 2)  # Longer TTL for stats
        
        # Cache for upload quotas (very short TTL)
        self.quota_cache = LRUCache(max_channels, 60)  # 1 minute TTL
        
        logger.info(f"ChannelCache initialized: max_channels={max_channels}, ttl={ttl_seconds}s")
    
    def _get_cache_key(self, user_id: str, channel_id: str, suffix: str = "") -> str:
        """Generate cache key"""
        key = f"{user_id}:{channel_id}"
        if suffix:
            key += f":{suffix}"
        return key
    
    async def get_channel_metadata(self, user_id: str, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached channel metadata
        
        Args:
            user_id: User ID
            channel_id: YouTube channel ID
            
        Returns:
            Channel metadata or None if not cached
        """
        key = self._get_cache_key(user_id, channel_id, "metadata")
        data = await self.metadata_cache.get(key)
        
        if data:
            logger.debug(f"Cache hit for channel metadata: {channel_id}")
        else:
            logger.debug(f"Cache miss for channel metadata: {channel_id}")
        
        return data
    
    async def set_channel_metadata(
        self, 
        user_id: str, 
        channel_id: str, 
        metadata: Dict[str, Any]
    ) -> None:
        """
        Cache channel metadata
        
        Args:
            user_id: User ID
            channel_id: YouTube channel ID
            metadata: Channel metadata to cache
        """
        key = self._get_cache_key(user_id, channel_id, "metadata")
        await self.metadata_cache.set(key, metadata)
        logger.debug(f"Cached metadata for channel: {channel_id}")
    
    async def get_channel_tokens(
        self, 
        user_id: str, 
        channel_id: str
    ) -> Optional[Tuple[str, str, datetime]]:
        """
        Get cached channel tokens
        
        Args:
            user_id: User ID
            channel_id: YouTube channel ID
            
        Returns:
            Tuple of (access_token, refresh_token, expiry) or None
        """
        key = self._get_cache_key(user_id, channel_id, "tokens")
        return await self.token_cache.get(key)
    
    async def set_channel_tokens(
        self,
        user_id: str,
        channel_id: str,
        access_token: str,
        refresh_token: str,
        expiry: datetime
    ) -> None:
        """
        Cache channel tokens
        
        Args:
            user_id: User ID
            channel_id: YouTube channel ID
            access_token: Access token
            refresh_token: Refresh token
            expiry: Token expiry time
        """
        key = self._get_cache_key(user_id, channel_id, "tokens")
        await self.token_cache.set(key, (access_token, refresh_token, expiry))
        logger.debug(f"Cached tokens for channel: {channel_id}")
    
    async def invalidate_channel_tokens(self, user_id: str, channel_id: str) -> None:
        """
        Invalidate cached tokens for a channel
        
        Args:
            user_id: User ID
            channel_id: YouTube channel ID
        """
        key = self._get_cache_key(user_id, channel_id, "tokens")
        await self.token_cache.delete(key)
        logger.debug(f"Invalidated token cache for channel: {channel_id}")
    
    async def get_channel_stats(self, user_id: str, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached channel statistics
        
        Args:
            user_id: User ID
            channel_id: YouTube channel ID
            
        Returns:
            Channel statistics or None
        """
        key = self._get_cache_key(user_id, channel_id, "stats")
        return await self.stats_cache.get(key)
    
    async def set_channel_stats(
        self,
        user_id: str,
        channel_id: str,
        stats: Dict[str, Any]
    ) -> None:
        """
        Cache channel statistics
        
        Args:
            user_id: User ID
            channel_id: YouTube channel ID
            stats: Channel statistics
        """
        key = self._get_cache_key(user_id, channel_id, "stats")
        await self.stats_cache.set(key, stats)
        logger.debug(f"Cached stats for channel: {channel_id}")
    
    async def get_upload_quota(self, user_id: str, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached upload quota information
        
        Args:
            user_id: User ID
            channel_id: YouTube channel ID
            
        Returns:
            Upload quota info or None
        """
        key = self._get_cache_key(user_id, channel_id, "quota")
        return await self.quota_cache.get(key)
    
    async def set_upload_quota(
        self,
        user_id: str,
        channel_id: str,
        quota: Dict[str, Any]
    ) -> None:
        """
        Cache upload quota information
        
        Args:
            user_id: User ID
            channel_id: YouTube channel ID
            quota: Upload quota information
        """
        key = self._get_cache_key(user_id, channel_id, "quota")
        await self.quota_cache.set(key, quota)
        logger.debug(f"Cached quota for channel: {channel_id}")
    
    async def invalidate_channel(self, user_id: str, channel_id: str) -> None:
        """
        Invalidate all cached data for a channel
        
        Args:
            user_id: User ID
            channel_id: YouTube channel ID
        """
        # Invalidate all cache types
        await self.metadata_cache.delete(self._get_cache_key(user_id, channel_id, "metadata"))
        await self.token_cache.delete(self._get_cache_key(user_id, channel_id, "tokens"))
        await self.stats_cache.delete(self._get_cache_key(user_id, channel_id, "stats"))
        await self.quota_cache.delete(self._get_cache_key(user_id, channel_id, "quota"))
        
        logger.info(f"Invalidated all cache for channel: {channel_id}")
    
    async def clear_user_cache(self, user_id: str) -> None:
        """
        Clear all cached data for a user
        
        Args:
            user_id: User ID
        """
        # This would require tracking keys by user
        # For now, we'll clear all caches (simpler but less efficient)
        await self.clear_all()
        logger.info(f"Cleared cache for user: {user_id}")
    
    async def clear_all(self) -> None:
        """Clear all caches"""
        await self.metadata_cache.clear()
        await self.token_cache.clear()
        await self.stats_cache.clear()
        await self.quota_cache.clear()
        logger.info("Cleared all channel caches")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics for all caches"""
        return {
            "metadata": await self.metadata_cache.get_stats(),
            "tokens": await self.token_cache.get_stats(),
            "stats": await self.stats_cache.get_stats(),
            "quota": await self.quota_cache.get_stats()
        }
    
    async def warm_cache(self, channels: List[Dict[str, Any]]) -> None:
        """
        Pre-populate cache with channel data
        
        Args:
            channels: List of channel data to cache
        """
        for channel in channels:
            user_id = channel.get("user_id")
            channel_id = channel.get("id")
            
            if user_id and channel_id:
                # Cache metadata
                metadata = {
                    "id": channel_id,
                    "name": channel.get("name"),
                    "username": channel.get("username"),
                    "profile_picture": channel.get("profile_picture"),
                    "subscriber_count": channel.get("subscriber_count"),
                    "video_count": channel.get("video_count")
                }
                await self.set_channel_metadata(user_id, channel_id, metadata)
                
                # Cache stats if available
                if "view_count" in channel:
                    stats = {
                        "subscriber_count": channel.get("subscriber_count"),
                        "view_count": channel.get("view_count"),
                        "video_count": channel.get("video_count")
                    }
                    await self.set_channel_stats(user_id, channel_id, stats)
        
        logger.info(f"Warmed cache with {len(channels)} channels")


# Singleton instance
_channel_cache = None

def get_channel_cache() -> ChannelCache:
    """Get singleton channel cache instance"""
    global _channel_cache
    if _channel_cache is None:
        # Get settings from environment
        max_channels = int(os.getenv("YOUTUBE_CACHE_MAX_CHANNELS", "100"))
        ttl_seconds = int(os.getenv("YOUTUBE_CACHE_TTL_SECONDS", "300"))
        _channel_cache = ChannelCache(max_channels, ttl_seconds)
    return _channel_cache


# Export for convenience
import os
__all__ = ["ChannelCache", "LRUCache", "get_channel_cache"]