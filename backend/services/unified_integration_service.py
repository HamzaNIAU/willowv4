"""
Unified Integration Service - Postiz Style
===========================================
This service handles all social media integrations using a single unified table
based on the proven Postiz architecture.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from cryptography.fernet import Fernet
import os

from services.supabase import DBConnection
from utils.logger import logger


class UnifiedIntegrationService:
    """
    Unified service for managing all social media platform integrations.
    Based on Postiz's Integration model - single table, JSON storage.
    """
    
    def __init__(self, db: DBConnection):
        self.db = db
        # Use same encryption key as other services
        encryption_key = os.getenv("MCP_CREDENTIAL_ENCRYPTION_KEY")
        if not encryption_key:
            raise ValueError("MCP_CREDENTIAL_ENCRYPTION_KEY environment variable not set")
        self.fernet = Fernet(encryption_key.encode())
    
    def _encrypt_token(self, token: str) -> str:
        """Encrypt a token for secure storage"""
        return self.fernet.encrypt(token.encode()).decode()
    
    def _decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt a stored token"""
        return self.fernet.decrypt(encrypted_token.encode()).decode()
    
    async def save_integration(
        self,
        user_id: str,
        platform: str,
        platform_account_id: str,
        account_data: Dict[str, Any],
        access_token: str,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
        token_scopes: Optional[List[str]] = None
    ) -> str:
        """
        Save a social media integration using Postiz model.
        
        Args:
            user_id: User's UUID
            platform: Platform type ('youtube', 'pinterest', etc.)
            platform_account_id: Platform's internal account ID
            account_data: Platform-specific data to store in platform_data JSONB
            access_token: OAuth access token
            refresh_token: OAuth refresh token (optional)
            token_expires_at: Token expiration timestamp
            token_scopes: OAuth scopes granted
            
        Returns:
            Integration ID (UUID)
        """
        try:
            client = await self.db.client
            
            # Generate internal ID (Postiz pattern)
            internal_id = f"{platform}_{platform_account_id[:20]}_{int(datetime.now().timestamp())}"
            
            # Prepare integration data
            integration_data = {
                "id": str(uuid.uuid4()),
                "internal_id": internal_id,
                "user_id": user_id,
                "name": account_data.get("name", f"{platform.title()} Account"),
                "picture": account_data.get("picture"),
                "platform_account_id": platform_account_id,
                "platform": platform,
                "access_token": self._encrypt_token(access_token),
                "refresh_token": self._encrypt_token(refresh_token) if refresh_token else None,
                "token_expires_at": token_expires_at.isoformat() if token_expires_at else None,
                "token_scopes": ",".join(token_scopes) if token_scopes else None,
                "platform_data": json.dumps(account_data.get("platform_data", {})),
                "additional_settings": json.dumps(account_data.get("additional_settings", [])),
                "disabled": False,
                "refresh_needed": False,
                "in_between_steps": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Upsert integration (handle existing accounts)
            result = await client.table("integrations").upsert(
                integration_data,
                on_conflict="user_id,platform,platform_account_id"
            ).execute()
            
            if not result.data:
                raise Exception("Failed to save integration")
            
            integration_id = result.data[0]["id"]
            logger.info(f"✅ Saved {platform} integration: {account_data.get('name')} ({integration_id})")
            
            return integration_id
            
        except Exception as e:
            logger.error(f"❌ Failed to save {platform} integration: {e}")
            raise
    
    async def get_user_integrations(
        self, 
        user_id: str, 
        platform: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get user's integrations, optionally filtered by platform.
        
        Args:
            user_id: User's UUID
            platform: Optional platform filter
            
        Returns:
            List of integration records with decrypted tokens
        """
        try:
            client = await self.db.client
            
            query = client.table("integrations").select("*").eq("user_id", user_id).eq("disabled", False)
            
            if platform:
                query = query.eq("platform", platform)
            
            result = await query.execute()
            
            # Decrypt tokens and parse JSON fields
            integrations = []
            for integration in result.data:
                integration_data = {
                    **integration,
                    "access_token": self._decrypt_token(integration["access_token"]) if integration["access_token"] else None,
                    "refresh_token": self._decrypt_token(integration["refresh_token"]) if integration["refresh_token"] else None,
                    "platform_data": json.loads(integration["platform_data"]) if integration["platform_data"] else {},
                    "additional_settings": json.loads(integration["additional_settings"]) if integration["additional_settings"] else []
                }
                integrations.append(integration_data)
            
            logger.info(f"📊 Found {len(integrations)} integrations for user {user_id}" + (f" ({platform})" if platform else ""))
            
            return integrations
            
        except Exception as e:
            logger.error(f"❌ Failed to get integrations: {e}")
            return []
    
    async def get_agent_integrations(
        self, 
        agent_id: str, 
        user_id: str, 
        platform: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get integrations enabled for a specific agent.
        
        Args:
            agent_id: Agent's UUID
            user_id: User's UUID  
            platform: Optional platform filter
            
        Returns:
            List of enabled integration records
        """
        try:
            client = await self.db.client
            
            # Query agent_integrations with JOIN to integrations
            query_sql = """
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
            """
            
            params = [agent_id, user_id]
            if platform:
                query_sql += " AND i.platform = %s"
                params.append(platform)
                
            result = await client.rpc("execute_sql", {"query": query_sql, "params": params}).execute()
            
            # Decrypt tokens and parse JSON fields
            integrations = []
            for integration in result.data:
                integration_data = {
                    **integration,
                    "access_token": self._decrypt_token(integration["access_token"]) if integration["access_token"] else None,
                    "refresh_token": self._decrypt_token(integration["refresh_token"]) if integration["refresh_token"] else None,
                    "platform_data": json.loads(integration["platform_data"]) if integration["platform_data"] else {},
                    "additional_settings": json.loads(integration["additional_settings"]) if integration["additional_settings"] else [],
                    "cached_stats": json.loads(integration["cached_stats"]) if integration["cached_stats"] else {}
                }
                integrations.append(integration_data)
            
            logger.info(f"🤖 Agent {agent_id} has {len(integrations)} enabled integrations" + (f" ({platform})" if platform else ""))
            
            return integrations
            
        except Exception as e:
            logger.error(f"❌ Failed to get agent integrations: {e}")
            return []
    
    async def create_agent_integration(
        self,
        agent_id: str,
        user_id: str, 
        integration_id: str,
        enabled: bool = True
    ) -> bool:
        """
        Create agent-integration relationship (replaces MCP toggles for social media).
        
        Args:
            agent_id: Agent's UUID
            user_id: User's UUID
            integration_id: Integration's UUID
            enabled: Whether this agent can use this integration
            
        Returns:
            Success status
        """
        try:
            client = await self.db.client
            
            # Get integration details for caching
            integration_result = await client.table("integrations").select("*").eq("id", integration_id).single().execute()
            
            if not integration_result.data:
                raise Exception(f"Integration {integration_id} not found")
            
            integration = integration_result.data
            platform_data = json.loads(integration["platform_data"]) if integration["platform_data"] else {}
            
            # Create agent_integration record
            agent_integration_data = {
                "agent_id": agent_id,
                "user_id": user_id,
                "integration_id": integration_id,
                "enabled": enabled,
                "cached_name": integration["name"],
                "cached_picture": integration["picture"],
                "cached_stats": json.dumps(self._extract_stats_for_platform(integration["platform"], platform_data))
            }
            
            result = await client.table("agent_integrations").upsert(
                agent_integration_data,
                on_conflict="agent_id,user_id,integration_id"
            ).execute()
            
            logger.info(f"🔗 Created agent integration: Agent {agent_id} → {integration['platform']} {integration['name']}")
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"❌ Failed to create agent integration: {e}")
            return False
    
    def _extract_stats_for_platform(self, platform: str, platform_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant stats based on platform type."""
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
    
    async def update_integration_stats(
        self,
        integration_id: str,
        new_stats: Dict[str, Any]
    ) -> bool:
        """Update platform-specific stats in platform_data."""
        try:
            client = await self.db.client
            
            # Get current platform_data
            result = await client.table("integrations").select("platform_data").eq("id", integration_id).single().execute()
            
            if not result.data:
                return False
            
            current_data = json.loads(result.data["platform_data"]) if result.data["platform_data"] else {}
            
            # Merge new stats with existing data
            updated_data = {**current_data, **new_stats}
            
            # Update platform_data
            update_result = await client.table("integrations").update({
                "platform_data": json.dumps(updated_data),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", integration_id).execute()
            
            logger.info(f"📊 Updated integration stats for {integration_id}")
            
            return bool(update_result.data)
            
        except Exception as e:
            logger.error(f"❌ Failed to update integration stats: {e}")
            return False
    
    async def remove_integration(self, user_id: str, integration_id: str) -> bool:
        """Soft delete an integration."""
        try:
            client = await self.db.client
            
            # Soft delete the integration
            result = await client.table("integrations").update({
                "disabled": True,
                "deleted_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", integration_id).eq("user_id", user_id).execute()
            
            if result.data:
                logger.info(f"🗑️ Removed integration {integration_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to remove integration: {e}")
            return False

    async def set_agent_integration_enabled(
        self,
        agent_id: str,
        user_id: str,
        platform: str,
        platform_account_id: str,
        enabled: bool
    ) -> bool:
        """Enable/disable a specific integration for a given agent.

        Also mirrors the state to agent_social_accounts for real-time UI updates.
        """
        try:
            client = await self.db.client
            # Find the integration row
            integ_result = await client.table('integrations').select('*').eq(
                'user_id', user_id
            ).eq('platform', platform).eq('platform_account_id', platform_account_id).single().execute()
            if not integ_result.data:
                raise Exception('Integration not found')

            integration = integ_result.data
            platform_data = json.loads(integration['platform_data']) if integration.get('platform_data') else {}

            # Upsert into agent_integrations
            agent_integration_data = {
                'agent_id': agent_id,
                'user_id': user_id,
                'integration_id': integration['id'],
                'enabled': enabled,
                'cached_name': integration.get('name'),
                'cached_picture': integration.get('picture'),
                'cached_stats': json.dumps(self._extract_stats_for_platform(platform, platform_data))
            }
            await client.table('agent_integrations').upsert(
                agent_integration_data,
                on_conflict='agent_id,user_id,integration_id'
            ).execute()

            # Mirror to agent_social_accounts for real-time menus
            try:
                mirror = {
                    'agent_id': agent_id,
                    'user_id': user_id,
                    'platform': platform,
                    'account_id': platform_account_id,
                    'account_name': integration.get('name'),
                    'username': platform_data.get('username'),
                    'profile_picture': integration.get('picture'),
                    'enabled': enabled,
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }
                await client.table('agent_social_accounts').upsert(
                    mirror,
                    on_conflict='agent_id,user_id,platform,account_id'
                ).execute()
            except Exception as mirror_err:
                logger.warning(f"Mirror to agent_social_accounts failed: {mirror_err}")

            logger.info(f"🔁 Set agent integration enabled: agent={agent_id}, platform={platform}, account={platform_account_id} → {enabled}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to set agent integration enabled: {e}")
            return False
