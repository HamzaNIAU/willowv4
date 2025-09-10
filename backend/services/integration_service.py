"""
Integration Service - Postiz Style  
==================================
Universal service for managing ALL social media integrations.
Based on Postiz IntegrationService - handles YouTube, Pinterest, etc. uniformly.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from repositories.integration_repository import IntegrationRepository
from services.supabase import DBConnection
from utils.logger import logger


class IntegrationService:
    """
    Universal integration service based on Postiz architecture.
    ALL platforms use this same service for database operations.
    """
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.repository = IntegrationRepository(db)
    
    async def create_or_update_integration(
        self,
        user_id: str,
        name: str,
        picture: Optional[str],
        provider: str,  # 'youtube', 'pinterest', 'twitter', etc.
        platform_account_id: str,  # Platform's internal ID
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
        username: Optional[str] = None,
        additional_settings: Optional[List[Dict[str, Any]]] = None,
        platform_data: Optional[Dict[str, Any]] = None,
        is_between_steps: bool = False
    ) -> str:
        """
        Universal integration creation/update - Postiz pattern.
        ALL platforms (YouTube, Pinterest, Twitter, etc.) use this method.
        """
        try:
            # Generate internal ID (Postiz pattern)
            internal_id = self.repository._generate_internal_id(provider, platform_account_id)
            
            # Create/update integration using repository
            integration_id = await self.repository.create_or_update_integration(
                user_id=user_id,
                name=name,
                picture=picture,
                internal_id=internal_id,
                provider=provider,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expires_in,
                username=username,
                additional_settings=additional_settings,
                platform_data=platform_data,
                is_between_steps=is_between_steps
            )
            
            # Create agent integrations for all user's agents (Kortix-specific)
            await self._create_agent_integrations(user_id, integration_id, provider, name, picture, platform_data)
            
            logger.info(f"✅ {provider.title()} integration saved successfully: {name}")
            
            return integration_id
            
        except Exception as e:
            logger.error(f"❌ Failed to create {provider} integration: {e}")
            raise
    
    async def _create_agent_integrations(
        self, 
        user_id: str, 
        integration_id: str,
        platform: str,
        name: str,
        picture: Optional[str],
        platform_data: Optional[Dict[str, Any]]
    ):
        """Create agent integration permissions (Kortix-specific addition)"""
        try:
            client = await self.db.client
            
            # Get all user's agents 
            agents_result = await client.table("agents").select("agent_id").eq("account_id", user_id).execute()
            agent_ids = [agent["agent_id"] for agent in agents_result.data] if agents_result.data else []
            
            # Add suna-default if no custom agents
            if not agent_ids or "suna-default" not in [a for a in agent_ids if isinstance(a, str) and a == "suna-default"]:
                agent_ids.append("suna-default")
            
            logger.info(f"Creating agent integrations for {platform} - {len(agent_ids)} agents")
            
            # Create agent integration for each agent
            for agent_id in agent_ids:
                agent_integration_data = {
                    "agent_id": agent_id,
                    "user_id": user_id,
                    "integration_id": integration_id,
                    "enabled": True,
                    "cached_name": name,
                    "cached_picture": picture,
                    "cached_stats": json.dumps(self._extract_stats_for_platform(platform, platform_data or {}))
                }
                
                await client.table("agent_integrations").upsert(
                    agent_integration_data,
                    on_conflict="agent_id,user_id,integration_id"
                ).execute()
                
                logger.info(f"✅ Created agent integration: {agent_id} → {platform} {name}")
                
        except Exception as e:
            logger.error(f"❌ Failed to create agent integrations: {e}")
            raise
    
    def _extract_stats_for_platform(self, platform: str, platform_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant stats for caching based on platform type"""
        if platform == 'youtube':
            return {
                "subscriber_count": platform_data.get("subscriber_count", 0),
                "video_count": platform_data.get("video_count", 0),
                "view_count": platform_data.get("view_count", 0),
                "country": platform_data.get("country")
            }
        elif platform == 'pinterest':
            return {
                "follower_count": platform_data.get("follower_count", 0),
                "pin_count": platform_data.get("pin_count", 0),
                "board_count": platform_data.get("board_count", 0)
            }
        elif platform == 'twitter':
            return {
                "follower_count": platform_data.get("follower_count", 0),
                "following_count": platform_data.get("following_count", 0),
                "tweet_count": platform_data.get("tweet_count", 0),
                "verified": platform_data.get("verified", False)
            }
        elif platform == 'instagram':
            return {
                "follower_count": platform_data.get("follower_count", 0),
                "following_count": platform_data.get("following_count", 0),
                "media_count": platform_data.get("media_count", 0)
            }
        elif platform == 'linkedin':
            return {
                "connection_count": platform_data.get("connection_count", 0),
                "follower_count": platform_data.get("follower_count", 0)
            }
        else:
            return {}
    
    async def get_user_integrations(self, user_id: str, platform: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get user's integrations, optionally filtered by platform"""
        return await self.repository.get_integrations_list(user_id, platform)
    
    async def get_integration_by_id(self, user_id: str, integration_id: str) -> Optional[Dict[str, Any]]:
        """Get specific integration by ID"""
        return await self.repository.get_integration_by_id(user_id, integration_id)
    
    async def disable_integration(self, user_id: str, integration_id: str) -> bool:
        """Disable integration (disconnect)"""
        return await self.repository.disable_integration(user_id, integration_id)
    
    async def refresh_integration_token(
        self,
        user_id: str,
        integration_id: str,
        new_access_token: str,
        new_refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None
    ) -> bool:
        """Update integration tokens after refresh"""
        return await self.repository.update_integration_tokens(
            user_id, integration_id, new_access_token, new_refresh_token, expires_in
        )
    
    async def mark_refresh_needed(self, user_id: str, integration_id: str) -> bool:
        """Mark integration as needing token refresh"""
        return await self.repository.refresh_needed(user_id, integration_id)
    
    async def get_agent_integrations(
        self, 
        agent_id: str, 
        user_id: str,
        platform: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get integrations enabled for a specific agent"""
        try:
            client = await self.db.client
            
            # Query agent_integrations with JOIN to integrations
            base_query = """
                SELECT 
                    i.*,
                    ai.enabled,
                    ai.cached_name,
                    ai.cached_picture,
                    ai.cached_stats
                FROM integrations i
                JOIN agent_integrations ai ON i.id = ai.integration_id
                WHERE ai.agent_id = %s 
                    AND ai.user_id = %s 
                    AND ai.enabled = true
                    AND i.disabled = false
                    AND i.deleted_at IS NULL
            """
            
            if platform:
                base_query += " AND i.platform = %s"
                params = [agent_id, user_id, platform]
            else:
                params = [agent_id, user_id]
            
            # Note: This is simplified - in real implementation you'd use proper query builder
            # For now, fall back to basic query
            query = client.table("agent_integrations").select("""
                *,
                integrations!inner(*)
            """).eq("agent_id", agent_id).eq("user_id", user_id).eq("enabled", True)
            
            if platform:
                # This would need to be implemented with proper JOIN support
                # For now, we'll get all and filter
                pass
            
            result = await query.execute()
            
            integrations = []
            for record in result.data or []:
                if record.get("integrations"):
                    integration = record["integrations"]
                    if platform and integration.get("platform") != platform:
                        continue
                        
                    if integration.get("disabled") or integration.get("deleted_at"):
                        continue
                        
                    # Decrypt tokens and parse JSON
                    integration_data = {
                        **integration,
                        **record,  # Include agent_integration fields
                        "access_token": self.repository._decrypt_token(integration["access_token"]) if integration.get("access_token") else None,
                        "refresh_token": self.repository._decrypt_token(integration["refresh_token"]) if integration.get("refresh_token") else None,
                        "platform_data": json.loads(integration["platform_data"]) if integration.get("platform_data") else {},
                        "cached_stats": json.loads(record["cached_stats"]) if record.get("cached_stats") else {}
                    }
                    integrations.append(integration_data)
            
            logger.info(f"🤖 Agent {agent_id} has {len(integrations)} enabled integrations" + (f" ({platform})" if platform else ""))
            
            return integrations
            
        except Exception as e:
            logger.error(f"❌ Failed to get agent integrations: {e}")
            return []