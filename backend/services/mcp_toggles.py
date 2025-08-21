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
            client = await self.db.client
            
            # Upsert the toggle state
            result = await client.table("agent_mcp_toggles").upsert({
                "agent_id": agent_id,
                "user_id": user_id,
                "mcp_id": mcp_id,
                "enabled": enabled,
                "updated_at": datetime.utcnow().isoformat()
            }, on_conflict="agent_id,user_id,mcp_id").execute()
            
            return len(result.data) > 0
            
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
                return result.data["enabled"]
            
            # Default to disabled for social media MCPs (security first)
            if mcp_id.startswith("social."):
                logger.debug(f"No toggle found for social MCP {mcp_id}, defaulting to disabled")
                return False
            
            # Default to enabled for other MCPs
            return True
            
        except Exception as e:
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
        """
        try:
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
            
            return [item["mcp_id"] for item in result.data]
            
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