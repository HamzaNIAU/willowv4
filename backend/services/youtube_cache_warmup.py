"""YouTube Channel Cache Warmup Service.

Handles cache warming on application startup to ensure optimal performance
for the pre-computed context injection system.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from utils.logger import logger
from services.supabase import DBConnection
from services.youtube_channel_cache import YouTubeChannelCacheService


class YouTubeCacheWarmupService:
    """Service for warming YouTube channel cache on startup."""
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.cache_service = YouTubeChannelCacheService(db)
    
    async def warm_cache_on_startup(self, max_concurrent_users: int = 10):
        """Warm cache for active users on application startup."""
        try:
            logger.info("Starting YouTube channel cache warmup...")
            start_time = datetime.now()
            
            # Get recently active users (users who created threads in last 7 days)
            active_users = await self._get_recently_active_users()
            
            if not active_users:
                logger.info("No recently active users found, skipping cache warmup")
                return
            
            logger.info(f"Found {len(active_users)} recently active users for cache warmup")
            
            # Process users in batches to avoid overwhelming the database
            semaphore = asyncio.Semaphore(max_concurrent_users)
            tasks = []
            
            for user_data in active_users:
                task = self._warm_user_cache_with_semaphore(semaphore, user_data)
                tasks.append(task)
            
            # Execute all warmup tasks
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successes and failures
            successes = sum(1 for result in results if result is True)
            failures = sum(1 for result in results if isinstance(result, Exception))
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"YouTube cache warmup completed in {duration:.2f}s: "
                f"{successes} successful, {failures} failed out of {len(active_users)} users"
            )
            
        except Exception as e:
            logger.error(f"Error during YouTube cache warmup: {e}")
    
    async def _warm_user_cache_with_semaphore(self, semaphore: asyncio.Semaphore, user_data: Dict[str, Any]) -> bool:
        """Warm cache for a single user with concurrency control."""
        async with semaphore:
            return await self._warm_user_cache(user_data)
    
    async def _warm_user_cache(self, user_data: Dict[str, Any]) -> bool:
        """Warm cache for a single user and their agents."""
        user_id = user_data['user_id']
        
        try:
            # Get user's agents
            agent_ids = await self._get_user_agent_ids(user_id)
            
            # Warm cache for this user
            await self.cache_service.warm_cache_for_user(user_id, agent_ids)
            
            logger.debug(f"Warmed cache for user {user_id} with {len(agent_ids)} agents")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to warm cache for user {user_id}: {e}")
            return False
    
    async def _get_recently_active_users(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get users who have been active in the last N days."""
        try:
            client = await self.db.client
            
            # Get users who created threads in the last N days
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            result = await client.table('threads').select(
                'account_id'
            ).gte('created_at', cutoff_date.isoformat()).execute()
            
            if not result.data:
                return []
            
            # Get unique user IDs
            user_ids = list(set(thread['account_id'] for thread in result.data))
            
            # Return user data
            return [{'user_id': user_id} for user_id in user_ids]
            
        except Exception as e:
            logger.error(f"Error getting recently active users: {e}")
            return []
    
    async def _get_user_agent_ids(self, user_id: str) -> List[str]:
        """Get agent IDs for a user."""
        try:
            client = await self.db.client
            
            result = await client.table('agents').select(
                'agent_id'
            ).eq('account_id', user_id).execute()
            
            if not result.data:
                return []
            
            return [agent['agent_id'] for agent in result.data]
            
        except Exception as e:
            logger.error(f"Error getting agent IDs for user {user_id}: {e}")
            return []
    
    async def scheduled_cache_refresh(self):
        """Scheduled task to refresh cache periodically."""
        try:
            logger.info("Starting scheduled YouTube channel cache refresh...")
            
            # Get cache statistics
            stats = await self.cache_service.get_cache_stats()
            logger.info(f"Current cache stats: {stats}")
            
            # Warm cache for recently active users
            await self.warm_cache_on_startup(max_concurrent_users=5)
            
        except Exception as e:
            logger.error(f"Error during scheduled cache refresh: {e}")


# Global instance for easy access
_warmup_service = None

async def get_warmup_service() -> YouTubeCacheWarmupService:
    """Get the global warmup service instance."""
    global _warmup_service
    if _warmup_service is None:
        from services.supabase import DBConnection
        db = DBConnection()
        _warmup_service = YouTubeCacheWarmupService(db)
    return _warmup_service

async def warm_youtube_cache_on_startup():
    """Convenience function to warm cache on startup."""
    warmup_service = await get_warmup_service()
    await warmup_service.warm_cache_on_startup()