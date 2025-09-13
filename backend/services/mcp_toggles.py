"""MCP Toggle Management Service"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from services.supabase import DBConnection
from utils.logger import logger
import json


class MCPToggleService:
    """Service for managing MCP toggle states"""
    
    def __init__(self, db: DBConnection):
        self.db = db
    
    async def get_toggles(self, agent_id: str, user_id: str) -> Dict[str, bool]:
        """
        Get all MCP toggle states for an agent and user
        Returns a dict mapping mcp_id to enabled state
        """
        try:
            # Special handling for suna-default virtual agent
            if agent_id == "suna-default":
                # Return empty toggles for virtual agent (all MCPs use defaults)
                return {}
            
            client = await self.db.client
            
            result = await client.table("agent_mcp_toggles").select("*").eq(
                "agent_id", agent_id
            ).eq(
                "user_id", user_id
            ).execute()
            
            # Convert to dict for easy lookup
            toggles = {}
            for toggle in result.data:
                toggles[toggle["mcp_id"]] = toggle["enabled"]
            
            return toggles
            
        except Exception as e:
            logger.error(f"Failed to get MCP toggles: {e}")
            return {}
    
    async def set_toggle(
        self, 
        agent_id: str, 
        user_id: str, 
        mcp_id: str, 
        enabled: bool
    ) -> bool:
        """
        Set the toggle state for a specific MCP
        Uses upsert to create or update
        """
        try:
            # Special handling for suna-default virtual agent
            if agent_id == "suna-default":
                # Cannot set toggles for virtual agent
                logger.warning(f"Attempted to set toggle for virtual agent suna-default")
                return False
            
            client = await self.db.client
            
            # Upsert the toggle state
            result = await client.table("agent_mcp_toggles").upsert({
                "agent_id": agent_id,
                "user_id": user_id,
                "mcp_id": mcp_id,
                "enabled": enabled,
                "updated_at": datetime.utcnow().isoformat()
            }, on_conflict="agent_id,user_id,mcp_id").execute()
            
            success = len(result.data) > 0
            
            # Invalidate YouTube channel cache if this is a YouTube toggle
            if success and mcp_id.startswith("social.youtube."):
                try:
                    from services.youtube_channel_cache import YouTubeChannelCacheService
                    cache_service = YouTubeChannelCacheService(self.db)
                    await cache_service.handle_toggle_change(user_id, agent_id, mcp_id, enabled)
                    logger.debug(f"Invalidated YouTube channel cache for toggle change: {mcp_id} -> {enabled}")
                except Exception as cache_error:
                    logger.warning(f"Failed to invalidate YouTube channel cache: {cache_error}")
                    # Don't fail the toggle operation if cache invalidation fails
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to set MCP toggle: {e}")
            return False
    
    async def is_enabled(
        self, 
        agent_id: str, 
        user_id: str, 
        mcp_id: str
    ) -> bool:
        """
        Check if a specific MCP is enabled for an agent and user
        Returns False by default for social media MCPs, True for others
        """
        try:
            client = await self.db.client
            
            result = await client.table("agent_mcp_toggles").select("enabled").eq(
                "agent_id", agent_id
            ).eq(
                "user_id", user_id
            ).eq(
                "mcp_id", mcp_id
            ).single().execute()
            
            if result.data:
                is_enabled = result.data["enabled"]
                logger.debug(f"Toggle found for {mcp_id}: {is_enabled} (agent: {agent_id})")
                return is_enabled
            
            # Special handling for YouTube channels - auto-enable if channel is connected
            if mcp_id.startswith("social.youtube."):
                channel_id = mcp_id.replace("social.youtube.", "")
                # Check if this YouTube channel is actually connected for the user
                channel_result = await client.table("youtube_channels").select("id").eq(
                    "user_id", user_id
                ).eq("id", channel_id).eq("is_active", True).execute()
                
                if channel_result.data:
                    # Channel exists and is active - auto-enable it
                    logger.debug(f"Auto-enabling connected YouTube channel {channel_id} for agent {agent_id}")
                    # Create the toggle record as enabled for future lookups
                    await self.set_toggle(agent_id, user_id, mcp_id, True)
                    return True
                else:
                    # Channel doesn't exist - keep disabled
                    logger.debug(f"YouTube channel {channel_id} not connected, keeping disabled")
                    return False
            
            # Default to disabled for other social media MCPs (security first)  
            if mcp_id.startswith("social."):
                logger.debug(f"No toggle found for social MCP {mcp_id}, defaulting to disabled")
                return False
            
            # Default to enabled for other MCPs
            return True
            
        except Exception as e:
            # If no record exists or error, check if it's a YouTube channel
            if mcp_id.startswith("social.youtube."):
                try:
                    client = await self.db.client
                    channel_id = mcp_id.replace("social.youtube.", "")
                    # Check if this YouTube channel is actually connected for the user
                    channel_result = await client.table("youtube_channels").select("id").eq(
                        "user_id", user_id
                    ).eq("id", channel_id).eq("is_active", True).execute()
                    
                    if channel_result.data:
                        # Channel exists and is active - auto-enable it
                        logger.debug(f"Auto-enabling connected YouTube channel {channel_id} for agent {agent_id} (exception path)")
                        # Create the toggle record as enabled for future lookups
                        await self.set_toggle(agent_id, user_id, mcp_id, True)
                        return True
                    else:
                        # Channel doesn't exist - keep disabled
                        logger.debug(f"YouTube channel {channel_id} not connected, keeping disabled (exception path)")
                        return False
                except Exception as inner_e:
                    logger.error(f"Error checking YouTube channel connection: {inner_e}")
                    return False
            
            # If no record exists or error, check if it's a social MCP
            if mcp_id.startswith("social."):
                logger.debug(f"No toggle found for social MCP {mcp_id}, defaulting to disabled")
                return False
            
            # Default to enabled for non-social MCPs
            logger.debug(f"No toggle found for {mcp_id}, defaulting to enabled")
            return True
    
    async def get_enabled_mcps(
        self, 
        agent_id: str, 
        user_id: str,
        mcp_type: Optional[str] = None
    ) -> List[str]:
        """
        Get list of enabled MCP IDs for an agent and user
        Optionally filter by MCP type (e.g., 'social.youtube')
        For YouTube channels, auto-enables connected channels that don't have explicit toggles
        """
        try:
            # Special handling for suna-default virtual agent: derive enabled social integrations
            if agent_id == "suna-default":
                try:
                    from services.unified_integration_service import UnifiedIntegrationService
                    integration_service = UnifiedIntegrationService(self.db)
                    # Get all integrations for the agent filtered by platform if requested
                    platform_filter = None
                    if mcp_type and mcp_type.startswith("social."):
                        # mcp_type like 'social.youtube' -> platform 'youtube'
                        platform_filter = mcp_type.split(".", 1)[1]
                    integrations = await integration_service.get_agent_integrations(agent_id, user_id, platform=platform_filter)
                    enabled_mcp_ids: List[str] = []
                    for integ in integrations:
                        platform = integ.get("platform")
                        account_id = integ.get("platform_account_id")
                        if platform and account_id:
                            enabled_mcp_ids.append(f"social.{platform}.{account_id}")
                    logger.info(f"[MCPToggleService] (suna-default) Enabled MCPs via unified integrations: {enabled_mcp_ids}")
                    return enabled_mcp_ids
                except Exception as e:
                    logger.warning(f"[MCPToggleService] (suna-default) Failed to resolve unified integrations: {e}")
                    # Fall through to generic handling below
            logger.info(f"[MCPToggleService] get_enabled_mcps called with agent_id={agent_id}, user_id={user_id}, mcp_type={mcp_type}")
            client = await self.db.client
            
            query = client.table("agent_mcp_toggles").select("mcp_id").eq(
                "agent_id", agent_id
            ).eq(
                "user_id", user_id
            ).eq(
                "enabled", True
            )
            
            # Filter by type if specified
            if mcp_type:
                query = query.like("mcp_id", f"{mcp_type}%")
            
            result = await query.execute()
            enabled_mcp_ids = [item["mcp_id"] for item in result.data]
            logger.info(f"[MCPToggleService] Found {len(enabled_mcp_ids)} enabled MCPs from database: {enabled_mcp_ids}")
            
            # Special handling for YouTube channels - auto-enable connected channels
            if mcp_type == "social.youtube":
                # Get all connected YouTube channels for this user
                channels_result = await client.table("youtube_channels").select("id").eq(
                    "user_id", user_id
                ).eq("is_active", True).execute()
                
                if channels_result.data:
                    # Check each connected channel and auto-enable if no toggle exists
                    for channel in channels_result.data:
                        channel_id = channel["id"]
                        mcp_id = f"social.youtube.{channel_id}"
                        
                        # If this channel isn't already in our enabled list, check if we should auto-enable
                        if mcp_id not in enabled_mcp_ids:
                            # Check if a toggle record exists
                            toggle_result = await client.table("agent_mcp_toggles").select("enabled").eq(
                                "agent_id", agent_id
                            ).eq("user_id", user_id).eq("mcp_id", mcp_id).execute()
                            
                            if not toggle_result.data:
                                # No toggle exists for this connected channel - auto-enable it
                                logger.info(f"Auto-enabling connected YouTube channel {channel_id} for agent {agent_id}")
                                success = await self.set_toggle(agent_id, user_id, mcp_id, True)
                                if success:
                                    enabled_mcp_ids.append(mcp_id)
                
                logger.info(f"[MCPToggleService] Final enabled YouTube channels for agent {agent_id}: {enabled_mcp_ids}")
            
            return enabled_mcp_ids
            
        except Exception as e:
            logger.error(f"Failed to get enabled MCPs: {e}")
            return []
    
    async def bulk_set_toggles(
        self,
        agent_id: str,
        user_id: str,
        toggles: Dict[str, bool]
    ) -> bool:
        """
        Set multiple toggle states at once
        """
        try:
            client = await self.db.client
            
            # Prepare bulk upsert data
            upsert_data = []
            for mcp_id, enabled in toggles.items():
                upsert_data.append({
                    "agent_id": agent_id,
                    "user_id": user_id,
                    "mcp_id": mcp_id,
                    "enabled": enabled,
                    "updated_at": datetime.utcnow().isoformat()
                })
            
            if upsert_data:
                result = await client.table("agent_mcp_toggles").upsert(
                    upsert_data,
                    on_conflict="agent_id,user_id,mcp_id"
                ).execute()
                
                return len(result.data) > 0
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to bulk set MCP toggles: {e}")
            return False
    
    async def delete_agent_toggles(self, agent_id: str, user_id: str) -> bool:
        """
        Delete all toggle states for an agent and user
        """
        try:
            client = await self.db.client
            
            await client.table("agent_mcp_toggles").delete().eq(
                "agent_id", agent_id
            ).eq(
                "user_id", user_id
            ).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete agent toggles: {e}")
            return False
    
    async def enable_channel_for_all_agents(self, user_id: str, channel_id: str) -> int:
        """
        Enable a social media channel for all user's agents
        
        Returns:
            Number of agents updated
        """
        try:
            client = await self.db.client
            mcp_id = f"social.youtube.{channel_id}"
            
            # Get all user's agents
            agents_result = await client.table("agents").select("agent_id").eq(
                "account_id", user_id
            ).execute()
            
            if not agents_result.data:
                return 0
            
            updated_count = 0
            for agent in agents_result.data:
                success = await self.set_toggle(
                    agent_id=agent["agent_id"],
                    user_id=user_id,
                    mcp_id=mcp_id,
                    enabled=True
                )
                if success:
                    updated_count += 1
            
            logger.info(f"Enabled channel {channel_id} for {updated_count} agents")
            return updated_count
            
        except Exception as e:
            logger.error(f"Failed to enable channel for all agents: {e}")
            return 0
    
    async def disable_channel_for_all_agents(self, user_id: str, channel_id: str) -> int:
        """
        Disable a social media channel for all user's agents
        
        Returns:
            Number of agents updated
        """
        try:
            client = await self.db.client
            mcp_id = f"social.youtube.{channel_id}"
            
            # Get all user's agents
            agents_result = await client.table("agents").select("agent_id").eq(
                "account_id", user_id
            ).execute()
            
            if not agents_result.data:
                return 0
            
            updated_count = 0
            for agent in agents_result.data:
                success = await self.set_toggle(
                    agent_id=agent["agent_id"],
                    user_id=user_id,
                    mcp_id=mcp_id,
                    enabled=False
                )
                if success:
                    updated_count += 1
            
            logger.info(f"Disabled channel {channel_id} for {updated_count} agents")
            return updated_count
            
        except Exception as e:
            logger.error(f"Failed to disable channel for all agents: {e}")
            return 0
    
    async def get_channel_toggle_status(self, user_id: str, channel_id: str) -> Dict[str, bool]:
        """
        Get toggle status for a channel across all user's agents
        
        Returns:
            Dict mapping agent_id to enabled status
        """
        try:
            client = await self.db.client
            mcp_id = f"social.youtube.{channel_id}"
            
            # Get all toggles for this channel
            result = await client.table("agent_mcp_toggles").select("*").eq(
                "user_id", user_id
            ).eq("mcp_id", mcp_id).execute()
            
            status_map = {}
            for toggle in result.data:
                status_map[toggle["agent_id"]] = toggle["enabled"]
            
            return status_map
            
        except Exception as e:
            logger.error(f"Failed to get channel toggle status: {e}")
            return {}
    
    async def auto_enable_connected_channels(self, user_id: str) -> int:
        """
        Auto-enable all connected YouTube channels for all user's agents.
        This is a utility method to help users who have the old disabled defaults.
        
        Returns:
            Number of channel-agent pairs that were enabled
        """
        try:
            client = await self.db.client
            
            # Get all connected YouTube channels for this user
            channels_result = await client.table("youtube_channels").select("id").eq(
                "user_id", user_id
            ).eq("is_active", True).execute()
            
            if not channels_result.data:
                return 0
            
            # Get all user's agents
            agents_result = await client.table("agents").select("agent_id").eq(
                "account_id", user_id
            ).execute()
            
            if not agents_result.data:
                return 0
            
            enabled_count = 0
            for channel in channels_result.data:
                channel_id = channel["id"]
                mcp_id = f"social.youtube.{channel_id}"
                
                for agent in agents_result.data:
                    agent_id = agent["agent_id"]
                    
                    # Enable the channel for this agent
                    success = await self.set_toggle(
                        agent_id=agent_id,
                        user_id=user_id,
                        mcp_id=mcp_id,
                        enabled=True
                    )
                    
                    if success:
                        enabled_count += 1
            
            logger.info(f"Auto-enabled {enabled_count} YouTube channel-agent pairs for user {user_id}")
            return enabled_count
            
        except Exception as e:
            logger.error(f"Failed to auto-enable connected channels: {e}")
            return 0
