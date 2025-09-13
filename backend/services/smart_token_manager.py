"""Smart Token Management Service - Beyond Morphic Intelligence"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from services.supabase import DBConnection
from youtube_mcp.oauth import YouTubeOAuthHandler
from utils.logger import logger


class SmartTokenManager:
    """Intelligent token management with proactive refresh and health monitoring"""
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.oauth_handler = YouTubeOAuthHandler(db)
        self._monitoring_active = False
    
    async def start_background_monitoring(self):
        """Start intelligent background token health monitoring - OPTIMIZED for Redis efficiency"""
        if self._monitoring_active:
            logger.debug("Smart Token Monitor already active, skipping duplicate initialization")
            return
        
        self._monitoring_active = True
        logger.info("🔄 Starting OPTIMIZED Smart Token Health Monitor...")
        
        # REDIS-EFFICIENT: Only start monitoring on worker 1 to avoid Redis overload
        import os
        worker_id = os.getenv("WORKER_ID", "1")
        if worker_id == "1":
            # Background task for proactive token refresh
            asyncio.create_task(self._token_health_monitor())
            logger.info("🚀 Token monitoring active on primary worker")
        else:
            logger.info(f"⏸️ Token monitoring skipped on worker {worker_id} (primary worker handles this)")
    
    async def _token_health_monitor(self):
        """REDIS-OPTIMIZED background monitor with reduced frequency"""
        logger.info("🔄 Redis-optimized token monitor starting...")
        
        while self._monitoring_active:
            try:
                # REDIS-EFFICIENT: Check every 10 minutes instead of 2 (reduces load)
                await asyncio.sleep(600)  # 10 minutes
                
                logger.debug("🔍 Starting periodic token health check...")
                await self._check_and_refresh_expiring_tokens()
                logger.debug("✅ Token health check completed")
                
            except Exception as e:
                logger.error(f"❌ Token health monitor error: {e}")
                await asyncio.sleep(900)  # Wait 15 minutes on error (longer recovery time)
    
    async def _check_and_refresh_expiring_tokens(self):
        """Proactively refresh tokens that expire within 10 minutes"""
        try:
            client = await self.db.client
            
            # Find channels with tokens expiring within 10 minutes
            ten_minutes_from_now = datetime.now(timezone.utc) + timedelta(minutes=10)
            
            result = await client.table("integrations").select("*").eq(
                "platform", "youtube"
            ).eq("disabled", False).eq(
                "refresh_needed", False
            ).lt("token_expires_at", ten_minutes_from_now.isoformat()).execute()
            
            if result.data:
                logger.info(f"🔍 Found {len(result.data)} integrations needing proactive refresh")
                
                for integration in result.data:
                    try:
                        await self._proactive_refresh_channel(integration)
                    except Exception as e:
                        logger.error(f"Failed to refresh integration {integration['name']}: {e}")
            else:
                logger.debug("✅ All tokens healthy - no proactive refresh needed")
                
        except Exception as e:
            logger.error(f"Error checking token health: {e}")
    
    async def _proactive_refresh_channel(self, integration: Dict[str, Any]):
        """Proactively refresh a single integration's token (Morphic pattern)"""
        channel_id = integration['platform_account_id']
        user_id = integration['user_id']
        channel_name = integration['name']
        
        logger.info(f"🔄 Proactive Refresh: {channel_name} ({channel_id})")
        
        try:
            # Use the smart OAuth handler to refresh
            new_token = await self.oauth_handler.get_valid_token(user_id, channel_id)
            
            # Update success tracking
            await self._update_refresh_success(channel_id, user_id)
            
            logger.info(f"✅ Proactive Refresh Success: {channel_name}")
            
        except Exception as e:
            # Update failure tracking  
            await self._update_refresh_failure(channel_id, user_id, str(e))
            
            logger.warning(f"⚠️ Proactive Refresh Failed: {channel_name} - {e}")
    
    async def _update_refresh_success(self, channel_id: str, user_id: str):
        """Update database with successful refresh tracking"""
        client = await self.db.client
        
        await client.table("youtube_channels").update({
            "last_refresh_success": datetime.now(timezone.utc).isoformat(),
            "refresh_failure_count": 0,  # Reset failure count
            "needs_reauth": False,
            "last_refresh_error": None,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", channel_id).eq("user_id", user_id).execute()
    
    async def _update_refresh_failure(self, channel_id: str, user_id: str, error: str):
        """Update database with refresh failure tracking"""
        client = await self.db.client
        
        # Increment failure count
        result = await client.table("youtube_channels").select("refresh_failure_count").eq(
            "id", channel_id
        ).eq("user_id", user_id).execute()
        
        current_failures = result.data[0].get("refresh_failure_count", 0) if result.data else 0
        new_failure_count = current_failures + 1
        
        # Mark for re-auth if too many failures
        needs_reauth = new_failure_count >= 3
        
        await client.table("youtube_channels").update({
            "last_refresh_attempt": datetime.now(timezone.utc).isoformat(),
            "last_refresh_error": error,
            "refresh_failure_count": new_failure_count,
            "needs_reauth": needs_reauth,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", channel_id).eq("user_id", user_id).execute()
        
        if needs_reauth:
            logger.warning(f"🚨 Channel {channel_id} marked for re-auth after {new_failure_count} failures")
    
    async def get_user_token_health(self, user_id: str) -> List[Dict[str, Any]]:
        """Get comprehensive token health status for user (diagnostic tool)"""
        try:
            client = await self.db.client
            
            result = await client.table("youtube_channels").select("*").eq(
                "user_id", user_id
            ).eq("is_active", True).execute()
            
            health_status = []
            for channel in result.data:
                expires_at = datetime.fromisoformat(channel["token_expires_at"].replace('Z', '+00:00'))
                time_until_expiry = expires_at - datetime.now(timezone.utc)
                minutes_until_expiry = time_until_expiry.total_seconds() / 60
                
                # Determine health status
                if channel.get("needs_reauth"):
                    status = "needs_reauth"
                elif minutes_until_expiry <= 0:
                    status = "expired"
                elif minutes_until_expiry <= 5:
                    status = "expiring_soon"
                elif minutes_until_expiry <= 60:
                    status = "refresh_window"
                else:
                    status = "healthy"
                
                health_status.append({
                    "channel_id": channel["id"],
                    "channel_name": channel["name"],
                    "token_status": status,
                    "minutes_until_expiry": round(minutes_until_expiry, 1),
                    "needs_attention": channel.get("needs_reauth", False) or minutes_until_expiry <= 5,
                    "last_refresh_success": channel.get("last_refresh_success"),
                    "failure_count": channel.get("refresh_failure_count", 0),
                    "auto_refresh_enabled": channel.get("auto_refresh_enabled", True)
                })
            
            return health_status
            
        except Exception as e:
            logger.error(f"Error getting token health: {e}")
            return []
    
    async def force_refresh_user_tokens(self, user_id: str) -> Dict[str, Any]:
        """Manually force refresh all user's tokens (admin tool)"""
        try:
            client = await self.db.client
            
            result = await client.table("youtube_channels").select("*").eq(
                "user_id", user_id
            ).eq("is_active", True).execute()
            
            refresh_results = {"success": 0, "failed": 0, "details": []}
            
            for channel in result.data:
                try:
                    await self.oauth_handler.get_valid_token(user_id, channel["id"])
                    refresh_results["success"] += 1
                    refresh_results["details"].append({
                        "channel": channel["name"],
                        "result": "success"
                    })
                    logger.info(f"✅ Force refresh success: {channel['name']}")
                except Exception as e:
                    refresh_results["failed"] += 1
                    refresh_results["details"].append({
                        "channel": channel["name"], 
                        "result": "failed",
                        "error": str(e)
                    })
                    logger.error(f"❌ Force refresh failed: {channel['name']} - {e}")
            
            return refresh_results
            
        except Exception as e:
            logger.error(f"Error in force refresh: {e}")
            return {"success": 0, "failed": 0, "error": str(e)}


# Global instance for background monitoring
_smart_token_manager: Optional[SmartTokenManager] = None

async def get_smart_token_manager(db: DBConnection) -> SmartTokenManager:
    """Get or create global smart token manager instance"""
    global _smart_token_manager
    
    if _smart_token_manager is None:
        _smart_token_manager = SmartTokenManager(db)
        await _smart_token_manager.start_background_monitoring()
        logger.info("🧠 Smart Token Manager initialized with background monitoring")
    
    return _smart_token_manager

async def initialize_smart_token_system(db: DBConnection):
    """Initialize the smart token management system on startup"""
    try:
        manager = await get_smart_token_manager(db)
        logger.info("🚀 Smart Token Management System initialized successfully")
        return manager
    except Exception as e:
        logger.error(f"❌ Failed to initialize smart token system: {e}")
        return None