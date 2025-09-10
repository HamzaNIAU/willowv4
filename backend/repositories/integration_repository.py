"""
Integration Repository - Postiz Style
=====================================
Universal repository for ALL social media integrations.
Based on Postiz IntegrationRepository pattern.
"""

import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from cryptography.fernet import Fernet
import os

from services.supabase import DBConnection
from utils.logger import logger


class IntegrationRepository:
    """
    Universal repository for social media integrations.
    Based on Postiz IntegrationRepository - handles ALL platforms uniformly.
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
    
    def _generate_internal_id(self, platform: str, account_id: str) -> str:
        """Generate internal ID following Postiz pattern"""
        timestamp = int(datetime.now().timestamp())
        return f"{platform}_{account_id[:20]}_{timestamp}"
    
    async def create_or_update_integration(
        self,
        user_id: str,
        name: str,
        picture: Optional[str],
        internal_id: str,
        provider: str,  # Platform identifier ('youtube', 'pinterest', etc.)
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
        username: Optional[str] = None,
        additional_settings: Optional[List[Dict[str, Any]]] = None,
        platform_data: Optional[Dict[str, Any]] = None,
        is_between_steps: bool = False
    ) -> str:
        """
        Universal integration save method - Postiz createOrUpdateIntegration pattern.
        ALL platforms use this same method.
        
        Args:
            user_id: User's UUID
            name: Display name for the account
            picture: Profile picture URL
            internal_id: Internal tracking ID
            provider: Platform identifier ('youtube', 'pinterest', etc.)
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            expires_in: Token expiration in seconds
            username: Platform username/handle
            additional_settings: Platform-specific settings
            platform_data: Platform-specific data (Kortix addition)
            is_between_steps: Multi-step OAuth flag
            
        Returns:
            Integration ID
        """
        try:
            client = await self.db.client
            
            # Calculate token expiration
            token_expires_at = None
            if expires_in:
                token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            # Prepare integration data (following Postiz pattern exactly)
            integration_data = {
                "internal_id": internal_id,
                "user_id": user_id,
                "name": name,
                "picture": picture,
                "platform_account_id": internal_id.split('_')[1] if '_' in internal_id else internal_id,
                "platform": provider,
                "access_token": self._encrypt_token(access_token),
                "refresh_token": self._encrypt_token(refresh_token) if refresh_token else None,
                "token_expires_at": token_expires_at.isoformat() if token_expires_at else None,
                "platform_data": json.dumps(platform_data) if platform_data else '{}',
                "additional_settings": json.dumps(additional_settings) if additional_settings else '[]',
                "disabled": False,
                "refresh_needed": False,
                "in_between_steps": is_between_steps,
                "posting_times": json.dumps([{"time": 120}, {"time": 400}, {"time": 700}]),  # Default posting times
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Upsert integration (Postiz pattern - update if exists, create if not)
            result = await client.table("integrations").upsert(
                integration_data,
                on_conflict="user_id,internal_id"
            ).execute()
            
            if not result.data:
                raise Exception("Failed to create or update integration")
            
            integration_id = result.data[0]["id"]
            logger.info(f"✅ Created/updated {provider} integration: {name} ({integration_id})")
            
            return integration_id
            
        except Exception as e:
            logger.error(f"❌ Failed to create/update {provider} integration: {e}")
            raise
    
    async def get_integration_by_id(self, user_id: str, integration_id: str) -> Optional[Dict[str, Any]]:
        """Get integration by ID with decrypted tokens"""
        try:
            client = await self.db.client
            
            result = await client.table("integrations").select("*").eq(
                "user_id", user_id
            ).eq("id", integration_id).eq("disabled", False).single().execute()
            
            if not result.data:
                return None
            
            integration = result.data
            
            # Decrypt tokens and parse JSON fields
            return {
                **integration,
                "access_token": self._decrypt_token(integration["access_token"]) if integration["access_token"] else None,
                "refresh_token": self._decrypt_token(integration["refresh_token"]) if integration["refresh_token"] else None,
                "platform_data": json.loads(integration["platform_data"]) if integration["platform_data"] else {},
                "additional_settings": json.loads(integration["additional_settings"]) if integration["additional_settings"] else []
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get integration: {e}")
            return None
    
    async def get_integrations_list(self, user_id: str, platform: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all integrations for user, optionally filtered by platform"""
        try:
            client = await self.db.client
            
            query = client.table("integrations").select("*").eq("user_id", user_id).eq("disabled", False)
            
            if platform:
                query = query.eq("platform", platform)
            
            result = await query.execute()
            
            # Decrypt tokens and parse JSON fields for all integrations
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
    
    async def disable_integration(self, user_id: str, integration_id: str) -> bool:
        """Disable integration (soft delete)"""
        try:
            client = await self.db.client
            
            result = await client.table("integrations").update({
                "disabled": True,
                "deleted_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", integration_id).eq("user_id", user_id).execute()
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"❌ Failed to disable integration: {e}")
            return False
    
    async def refresh_needed(self, user_id: str, integration_id: str) -> bool:
        """Mark integration as needing token refresh"""
        try:
            client = await self.db.client
            
            result = await client.table("integrations").update({
                "refresh_needed": True,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", integration_id).eq("user_id", user_id).execute()
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"❌ Failed to mark refresh needed: {e}")
            return False
    
    async def update_integration_tokens(
        self,
        user_id: str,
        integration_id: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None
    ) -> bool:
        """Update integration tokens after refresh"""
        try:
            client = await self.db.client
            
            update_data = {
                "access_token": self._encrypt_token(access_token),
                "refresh_needed": False,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            if refresh_token:
                update_data["refresh_token"] = self._encrypt_token(refresh_token)
            
            if expires_in:
                update_data["token_expires_at"] = (
                    datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                ).isoformat()
            
            result = await client.table("integrations").update(update_data).eq(
                "id", integration_id
            ).eq("user_id", user_id).execute()
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"❌ Failed to update integration tokens: {e}")
            return False
    
    async def get_integrations_needing_refresh(self) -> List[Dict[str, Any]]:
        """Get integrations that need token refresh (Postiz pattern)"""
        try:
            client = await self.db.client
            
            # Get integrations expiring within 1 day or marked as needing refresh
            tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
            
            result = await client.table("integrations").select("*").or_(
                f"token_expires_at.lte.{tomorrow.isoformat()},refresh_needed.eq.true"
            ).eq("disabled", False).eq("in_between_steps", False).execute()
            
            # Decrypt tokens for refresh operations
            integrations = []
            for integration in result.data:
                integration_data = {
                    **integration,
                    "access_token": self._decrypt_token(integration["access_token"]) if integration["access_token"] else None,
                    "refresh_token": self._decrypt_token(integration["refresh_token"]) if integration["refresh_token"] else None,
                    "platform_data": json.loads(integration["platform_data"]) if integration["platform_data"] else {},
                }
                integrations.append(integration_data)
            
            logger.info(f"🔄 Found {len(integrations)} integrations needing token refresh")
            
            return integrations
            
        except Exception as e:
            logger.error(f"❌ Failed to get integrations needing refresh: {e}")
            return []