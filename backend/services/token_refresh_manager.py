"""Token Refresh Manager with queue management and intelligent retry logic"""

import asyncio
import time
from typing import Dict, Any, Optional, Tuple, Set
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from enum import Enum
import aiohttp

from services.encryption_service import get_token_encryption
from services.channel_cache import get_channel_cache
from services.supabase import DBConnection
from utils.logger import logger


class RefreshStatus(Enum):
    """Token refresh status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"


class RefreshRequest:
    """Token refresh request"""
    
    def __init__(
        self,
        user_id: str,
        channel_id: str,
        refresh_token: str,
        priority: int = 0
    ):
        self.user_id = user_id
        self.channel_id = channel_id
        self.refresh_token = refresh_token
        self.priority = priority
        self.status = RefreshStatus.PENDING
        self.created_at = time.time()
        self.attempts = 0
        self.last_attempt = None
        self.error = None
        self.future = asyncio.Future()
    
    @property
    def key(self) -> str:
        """Unique key for this request"""
        return f"{self.user_id}:{self.channel_id}"
    
    def __lt__(self, other):
        """For priority queue comparison"""
        # Higher priority first, then older requests
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.created_at < other.created_at


class TokenRefreshManager:
    """Manages token refresh operations with queue and rate limiting"""
    
    def __init__(
        self,
        max_concurrent: int = 5,
        max_retries: int = 3,
        rate_limit_per_minute: int = 60
    ):
        """
        Initialize token refresh manager
        
        Args:
            max_concurrent: Maximum concurrent refresh operations
            max_retries: Maximum retry attempts per request
            rate_limit_per_minute: Maximum refreshes per minute
        """
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
        self.rate_limit_per_minute = rate_limit_per_minute
        
        # Queue and tracking
        self.pending_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.active_refreshes: Dict[str, RefreshRequest] = {}
        self.completed_refreshes: Dict[str, RefreshRequest] = {}
        self.refresh_locks: Dict[str, asyncio.Lock] = {}
        
        # Rate limiting
        self.refresh_timestamps: list = []
        self.rate_limit_lock = asyncio.Lock()
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "successful": 0,
            "failed": 0,
            "rate_limited": 0,
            "avg_duration_ms": 0
        }
        
        # Services
        self.db = DBConnection()
        self.encryption = get_token_encryption()
        self.cache = get_channel_cache()
        
        # Worker tasks
        self.workers: list = []
        self.running = False
        
        # OAuth settings
        self.client_id = None
        self.client_secret = None
        self.token_url = "https://oauth2.googleapis.com/token"
        
        logger.info(f"TokenRefreshManager initialized: max_concurrent={max_concurrent}")
    
    def configure_oauth(self, client_id: str, client_secret: str):
        """Configure OAuth credentials"""
        self.client_id = client_id
        self.client_secret = client_secret
    
    async def start(self):
        """Start the refresh manager workers"""
        if self.running:
            return
        
        self.running = True
        
        # Start worker tasks
        for i in range(self.max_concurrent):
            worker = asyncio.create_task(self._worker(i))
            self.workers.append(worker)
        
        logger.info(f"Started {self.max_concurrent} refresh workers")
    
    async def stop(self):
        """Stop the refresh manager"""
        self.running = False
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        
        logger.info("Stopped refresh manager")
    
    async def refresh_token(
        self,
        user_id: str,
        channel_id: str,
        refresh_token: str,
        priority: int = 0
    ) -> Tuple[str, datetime]:
        """
        Queue a token refresh request
        
        Args:
            user_id: User ID
            channel_id: YouTube channel ID
            refresh_token: Refresh token
            priority: Priority level (higher = more urgent)
            
        Returns:
            Tuple of (new_access_token, expiry)
        """
        key = f"{user_id}:{channel_id}"
        
        # Check if already being refreshed
        if key in self.active_refreshes:
            logger.debug(f"Refresh already in progress for {key}, waiting...")
            request = self.active_refreshes[key]
            return await request.future
        
        # Check if recently completed
        if key in self.completed_refreshes:
            recent = self.completed_refreshes[key]
            if time.time() - recent.last_attempt < 60:  # Within 1 minute
                if recent.status == RefreshStatus.COMPLETED:
                    logger.debug(f"Using recently refreshed token for {key}")
                    return await recent.future
        
        # Create new request
        request = RefreshRequest(user_id, channel_id, refresh_token, priority)
        self.stats["total_requests"] += 1
        
        # Add to queue
        await self.pending_queue.put((request.priority, request))
        self.active_refreshes[key] = request
        
        logger.info(f"Queued refresh request for {key} with priority {priority}")
        
        # Wait for completion
        try:
            return await request.future
        finally:
            # Cleanup
            if key in self.active_refreshes:
                del self.active_refreshes[key]
    
    async def _worker(self, worker_id: int):
        """Worker task to process refresh requests"""
        logger.info(f"Worker {worker_id} started")
        
        while self.running:
            try:
                # Get next request from queue
                try:
                    _, request = await asyncio.wait_for(
                        self.pending_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Check rate limit
                if await self._is_rate_limited():
                    logger.warning(f"Rate limited, delaying request {request.key}")
                    request.status = RefreshStatus.RATE_LIMITED
                    self.stats["rate_limited"] += 1
                    await asyncio.sleep(1)
                    await self.pending_queue.put((request.priority, request))
                    continue
                
                # Process request
                logger.info(f"Worker {worker_id} processing {request.key}")
                request.status = RefreshStatus.IN_PROGRESS
                
                start_time = time.time()
                success = await self._process_refresh(request)
                duration_ms = (time.time() - start_time) * 1000
                
                # Update statistics
                if success:
                    self.stats["successful"] += 1
                else:
                    self.stats["failed"] += 1
                
                # Update average duration
                current_avg = self.stats["avg_duration_ms"]
                total_processed = self.stats["successful"] + self.stats["failed"]
                self.stats["avg_duration_ms"] = (
                    (current_avg * (total_processed - 1) + duration_ms) / total_processed
                )
                
                # Move to completed
                self.completed_refreshes[request.key] = request
                
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
        
        logger.info(f"Worker {worker_id} stopped")
    
    async def _process_refresh(self, request: RefreshRequest) -> bool:
        """
        Process a single refresh request
        
        Args:
            request: Refresh request to process
            
        Returns:
            True if successful, False otherwise
        """
        request.attempts += 1
        request.last_attempt = time.time()
        
        try:
            # Perform the actual refresh
            async with aiohttp.ClientSession() as session:
                data = {
                    "refresh_token": request.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token"
                }
                
                async with session.post(self.token_url, data=data) as response:
                    if response.status == 429:  # Rate limited
                        request.status = RefreshStatus.RATE_LIMITED
                        request.error = "Rate limited by YouTube"
                        
                        # Retry with exponential backoff
                        if request.attempts < self.max_retries:
                            delay = 2 ** request.attempts
                            logger.warning(f"Rate limited, retrying in {delay}s")
                            await asyncio.sleep(delay)
                            await self.pending_queue.put((request.priority, request))
                            return False
                        else:
                            request.future.set_exception(
                                Exception("Rate limited after max retries")
                            )
                            return False
                    
                    if response.status != 200:
                        error_text = await response.text()
                        request.error = f"HTTP {response.status}: {error_text}"
                        
                        # Check if token is invalid (needs re-auth)
                        if response.status == 400 and "invalid_grant" in error_text:
                            logger.error(f"Refresh token invalid for {request.key}")
                            await self._mark_channel_needs_reauth(
                                request.user_id, 
                                request.channel_id
                            )
                            request.future.set_exception(
                                Exception("Refresh token invalid, re-authentication required")
                            )
                            return False
                        
                        # Retry if temporary error
                        if request.attempts < self.max_retries and response.status >= 500:
                            logger.warning(f"Server error, retrying {request.key}")
                            await asyncio.sleep(2 ** request.attempts)
                            await self.pending_queue.put((request.priority, request))
                            return False
                        
                        request.future.set_exception(Exception(request.error))
                        return False
                    
                    # Parse response
                    token_data = await response.json()
                    
                    access_token = token_data["access_token"]
                    expires_in = token_data.get("expires_in", 3600)
                    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                    
                    # Update database
                    await self._update_token_in_db(
                        request.user_id,
                        request.channel_id,
                        access_token,
                        expiry
                    )
                    
                    # Update cache
                    await self.cache.set_channel_tokens(
                        request.user_id,
                        request.channel_id,
                        access_token,
                        request.refresh_token,
                        expiry
                    )
                    
                    # Record refresh timestamp for rate limiting
                    async with self.rate_limit_lock:
                        self.refresh_timestamps.append(time.time())
                    
                    # Complete request
                    request.status = RefreshStatus.COMPLETED
                    request.future.set_result((access_token, expiry))
                    
                    logger.info(f"Successfully refreshed token for {request.key}")
                    return True
                    
        except Exception as e:
            logger.error(f"Error refreshing token for {request.key}: {e}")
            request.error = str(e)
            
            # Retry if not at max attempts
            if request.attempts < self.max_retries:
                logger.info(f"Retrying refresh for {request.key} (attempt {request.attempts})")
                await asyncio.sleep(2 ** request.attempts)
                await self.pending_queue.put((request.priority, request))
                return False
            
            request.status = RefreshStatus.FAILED
            request.future.set_exception(e)
            return False
    
    async def _is_rate_limited(self) -> bool:
        """Check if we're rate limited"""
        async with self.rate_limit_lock:
            now = time.time()
            
            # Remove timestamps older than 1 minute
            self.refresh_timestamps = [
                ts for ts in self.refresh_timestamps
                if now - ts < 60
            ]
            
            # Check if at limit
            return len(self.refresh_timestamps) >= self.rate_limit_per_minute
    
    async def _update_token_in_db(
        self,
        user_id: str,
        channel_id: str,
        access_token: str,
        expiry: datetime
    ):
        """Update token in database"""
        client = await self.db.client
        
        # Encrypt token
        encrypted_token = self.encryption.encrypt_token(access_token)
        
        # Update database
        await client.table("youtube_channels").update({
            "access_token": encrypted_token,
            "token_expires_at": expiry.isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("user_id", user_id).eq("id", channel_id).execute()
    
    async def _mark_channel_needs_reauth(self, user_id: str, channel_id: str):
        """Mark channel as needing re-authentication"""
        client = await self.db.client
        
        await client.table("youtube_channels").update({
            "is_active": False,
            "needs_reauth": True,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("user_id", user_id).eq("id", channel_id).execute()
        
        # Invalidate cache
        await self.cache.invalidate_channel(user_id, channel_id)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get refresh manager statistics"""
        return {
            **self.stats,
            "active_refreshes": len(self.active_refreshes),
            "queue_size": self.pending_queue.qsize(),
            "completed_cache_size": len(self.completed_refreshes),
            "workers": len(self.workers),
            "running": self.running
        }
    
    async def clear_completed_cache(self):
        """Clear completed refresh cache"""
        self.completed_refreshes.clear()
        logger.info("Cleared completed refresh cache")


# Singleton instance
_refresh_manager = None

def get_refresh_manager() -> TokenRefreshManager:
    """Get singleton refresh manager instance"""
    global _refresh_manager
    if _refresh_manager is None:
        import os
        max_concurrent = int(os.getenv("YOUTUBE_REFRESH_MAX_CONCURRENT", "5"))
        max_retries = int(os.getenv("YOUTUBE_REFRESH_MAX_RETRIES", "3"))
        rate_limit = int(os.getenv("YOUTUBE_REFRESH_RATE_LIMIT_PER_MIN", "60"))
        
        _refresh_manager = TokenRefreshManager(
            max_concurrent=max_concurrent,
            max_retries=max_retries,
            rate_limit_per_minute=rate_limit
        )
        
        # Configure OAuth
        client_id = os.getenv("YOUTUBE_CLIENT_ID")
        client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
        if client_id and client_secret:
            _refresh_manager.configure_oauth(client_id, client_secret)
    
    return _refresh_manager


# Export for convenience
__all__ = ["TokenRefreshManager", "RefreshStatus", "get_refresh_manager"]