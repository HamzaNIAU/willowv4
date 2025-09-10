"""Pinterest OAuth handler following YouTube's exact working pattern"""

import os
import json
import secrets
import hashlib
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlencode

import aiohttp
from cryptography.fernet import Fernet

from services.supabase import DBConnection
from utils.logger import logger


class PinterestOAuthHandler:
    """Handles Pinterest OAuth flow and token management - Following YouTube pattern exactly"""
    
    OAUTH_URL = "https://www.pinterest.com/oauth/"
    TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"
    SCOPES = [
        "pins:read",
        "pins:write", 
        "boards:read",
        "boards:write",
        "user_accounts:read"
    ]
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.client_id = os.getenv("PINTEREST_CLIENT_ID")
        self.client_secret = os.getenv("PINTEREST_CLIENT_SECRET")
        self.redirect_uri = os.getenv("PINTEREST_REDIRECT_URI", "http://localhost:8000/api/pinterest/auth/callback")
        
        # Encryption key for tokens
        encryption_key = os.getenv("MCP_CREDENTIAL_ENCRYPTION_KEY")
        if encryption_key:
            self.fernet = Fernet(encryption_key.encode())
        else:
            # Generate a key if not provided (not recommended for production)
            logger.warning("No MCP_CREDENTIAL_ENCRYPTION_KEY found, generating temporary key")
            self.fernet = Fernet(Fernet.generate_key())
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Pinterest OAuth credentials not configured")
    
    def get_auth_url(self, state: Optional[str] = None) -> str:
        """Generate OAuth authorization URL - Following YouTube pattern exactly"""
        if not state:
            state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": ",".join(self.SCOPES),  # Pinterest uses comma-separated scopes
            "state": state,
        }
        
        return f"{self.OAUTH_URL}?{urlencode(params)}"
    
    async def exchange_code_for_tokens(self, code: str) -> Tuple[str, str, datetime]:
        """Exchange authorization code for access and refresh tokens - Following YouTube pattern"""
        async with aiohttp.ClientSession() as session:
            data = {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            }
            
            async with session.post(self.TOKEN_URL, data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Pinterest token exchange failed: {error_text}")
                
                token_data = await response.json()
                
                access_token = token_data["access_token"]
                refresh_token = token_data.get("refresh_token")
                expires_in = token_data.get("expires_in", 2592000)  # Default 30 days for Pinterest
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                
                return access_token, refresh_token, expires_at
    
    async def refresh_access_token(self, refresh_token: str) -> Tuple[str, datetime]:
        """Refresh an expired access token - Following YouTube pattern"""
        async with aiohttp.ClientSession() as session:
            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
            
            async with session.post(self.TOKEN_URL, data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Pinterest token refresh failed: {error_text}")
                
                token_data = await response.json()
                
                access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 2592000)
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                
                return access_token, expires_at
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get Pinterest user info - Following YouTube channel pattern"""
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            async with session.get(
                "https://api.pinterest.com/v5/user_account",
                headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Failed to fetch Pinterest user info: {error_text}")
                
                user_data = await response.json()
                
                # Format Pinterest user info similar to YouTube channel format
                account_info = {
                    "id": user_data["username"],  # Pinterest uses username as ID
                    "name": user_data.get("business_name") or user_data.get("username", ""),
                    "username": user_data.get("username", ""),
                    "profile_image_url": user_data.get("profile_image", ""),
                    "website_url": user_data.get("website_url"),
                    "about": user_data.get("about"),
                    "account_type": user_data.get("account_type", "PERSONAL"),
                    "pin_count": user_data.get("pin_count", 0),
                    "board_count": user_data.get("board_count", 0),
                    "follower_count": user_data.get("follower_count", 0),
                    "following_count": user_data.get("following_count", 0),
                }
                
                return account_info
    
    def encrypt_token(self, token: str) -> str:
        """Encrypt a token for storage - Following YouTube pattern exactly"""
        return self.fernet.encrypt(token.encode()).decode()
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt a stored token - Following YouTube pattern exactly"""
        return self.fernet.decrypt(encrypted_token.encode()).decode()
    
    async def save_account(
        self,
        user_id: str,
        account_info: Dict[str, Any],
        access_token: str,
        refresh_token: Optional[str],
        expires_at: datetime
    ) -> str:
        """Save Pinterest account using unified integrations table (Postiz style)"""
        try:
            from services.unified_integration_service import UnifiedIntegrationService
            
            integration_service = UnifiedIntegrationService(self.db)
            
            # Prepare Pinterest-specific platform data (no forced mapping!)
            platform_data = {
                "account_id": account_info["id"],
                "username": account_info["username"],
                "bio": account_info.get("about"),
                "website_url": account_info.get("website_url"),
                "account_type": account_info.get("account_type", "PERSONAL"),
                "pin_count": account_info.get("pin_count", 0),
                "board_count": account_info.get("board_count", 0), 
                "follower_count": account_info.get("follower_count", 0),
                "following_count": account_info.get("following_count", 0),
                "profile_image_url": account_info.get("profile_image_url")
            }
            
            # Save to unified integrations table
            integration_id = await integration_service.save_integration(
                user_id=user_id,
                platform="pinterest",
                platform_account_id=account_info["id"],
                account_data={
                    "name": account_info["name"],
                    "picture": account_info.get("profile_image_url"),
                    "platform_data": platform_data
                },
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=expires_at,
                token_scopes=self.SCOPES
            )
            
            # Create agent integrations for all user's agents
            await self._create_agent_integrations(user_id, integration_id)
            
            logger.info(f"✅ Saved Pinterest integration {integration_id} for user {user_id}")
            return account_info["id"]
            
        except Exception as e:
            logger.error(f"❌ Failed to save Pinterest account: {e}")
            raise
    
    async def _create_agent_integrations(self, user_id: str, integration_id: str):
        """Create agent integrations using unified system (Postiz style)"""
        try:
            from services.unified_integration_service import UnifiedIntegrationService
            
            integration_service = UnifiedIntegrationService(self.db)
            client = await self.db.client
            
            # Get all user's agents (including suna-default)
            agents_result = await client.table("agents").select("agent_id").eq("account_id", user_id).execute()
            agent_ids = [agent["agent_id"] for agent in agents_result.data] if agents_result.data else []
            
            # Also add suna-default if user doesn't have custom agents
            if not agent_ids:
                agent_ids = ["suna-default"]
            elif "suna-default" not in agent_ids:
                agent_ids.append("suna-default")
            
            logger.info(f"Creating agent integrations for Pinterest - Found {len(agent_ids)} agents")
            
            # Create agent integration for each agent
            for agent_id in agent_ids:
                await integration_service.create_agent_integration(
                    agent_id=agent_id,
                    user_id=user_id,
                    integration_id=integration_id,
                    enabled=True
                )
                logger.info(f"✅ Created agent integration: {agent_id} → Pinterest")
                
        except Exception as e:
            logger.error(f"❌ Failed to create agent integrations: {e}")
            raise
    
    async def get_valid_token(self, user_id: str, account_id: str) -> str:
        """Get a valid access token, refreshing if necessary - SMART MORPHIC-INSPIRED TOKEN MANAGEMENT"""
        client = await self.db.client
        
        # Get account from database
        result = await client.table("pinterest_accounts").select("*").eq(
            "user_id", user_id
        ).eq("id", account_id).execute()
        
        if not result.data:
            raise Exception(f"Pinterest account {account_id} not found")
        
        account = result.data[0]
        
        # Decrypt tokens
        access_token = self.decrypt_token(account["access_token"])
        refresh_token = self.decrypt_token(account["refresh_token"]) if account.get("refresh_token") else None
        
        # SMART MORPHIC-INSPIRED TOKEN MANAGEMENT (same as YouTube)
        token_expires = account["token_expires_at"]
        if token_expires.endswith('Z'):
            token_expires = token_expires.replace('Z', '+00:00')
        elif '+' not in token_expires and '-' not in token_expires[-6:]:
            token_expires = token_expires + '+00:00'
        expires_at = datetime.fromisoformat(token_expires)
        
        # MORPHIC PATTERN: Proactive 5-minute buffer for seamless experience
        buffer_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        time_until_expiry = expires_at - datetime.now(timezone.utc)
        
        logger.info(f"🔍 Pinterest Token Check: Expires {expires_at}, Buffer {buffer_time}, Time left: {time_until_expiry}")
        
        # SMART DECISION: Token still has >5 minutes? Use it!
        if expires_at > buffer_time:
            logger.debug(f"✅ Pinterest Token Valid: {time_until_expiry} remaining for account {account['username']}")
            return access_token
        
        # FULLY AUTOMATIC REFRESH: Zero manual intervention required
        if not refresh_token:
            logger.warning(f"⚠️ No refresh token available for Pinterest {account['username']} - using fallback token strategy")
            
            # AUTOMATIC FALLBACK: Try to use existing token anyway (might still work)
            logger.info(f"🤖 AUTOMATIC FALLBACK: Attempting Pinterest operations with existing token for {account['username']}")
            return access_token
        
        logger.info(f"🤖 FULLY AUTOMATIC REFRESH: Silently refreshing Pinterest token for {account['username']} (expires in {time_until_expiry})")
        
        try:
            # SILENT AUTOMATIC REFRESH: No user interaction required
            new_access_token, new_expires_at = await self.refresh_access_token(refresh_token)
            
            # Update database with fresh token
            encrypted_access = self.encrypt_token(new_access_token)
            
            await client.table("pinterest_accounts").update({
                "access_token": encrypted_access,
                "token_expires_at": new_expires_at.isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "last_refresh_success": datetime.now(timezone.utc).isoformat(),
                "needs_reauth": False,
                "refresh_failure_count": 0
            }).eq("id", account_id).eq("user_id", user_id).execute()
            
            logger.info(f"🎉 SILENT REFRESH SUCCESS: Pinterest {account['username']} token automatically renewed! New expiry: {new_expires_at}")
            
            return new_access_token
            
        except Exception as refresh_error:
            logger.warning(f"⚠️ AUTOMATIC REFRESH ATTEMPT FAILED for Pinterest {account['username']}: {refresh_error}")
            
            # GRACEFUL DEGRADATION: Don't throw errors, try to continue with existing token
            await client.table("pinterest_accounts").update({
                "last_refresh_error": str(refresh_error),
                "last_refresh_attempt": datetime.now(timezone.utc).isoformat(),
                "refresh_failure_count": account.get("refresh_failure_count", 0) + 1,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", account_id).eq("user_id", user_id).execute()
            
            # AUTOMATIC FALLBACK: Try existing token anyway
            logger.info(f"🤖 AUTOMATIC FALLBACK: Using existing Pinterest token for {account['username']} despite refresh failure")
            return access_token
    
    async def get_user_accounts(self, user_id: str) -> list:
        """Get all Pinterest accounts for a user - Following YouTube pattern"""
        client = await self.db.client
        
        result = await client.table("pinterest_accounts").select("*").eq(
            "user_id", user_id
        ).eq("is_active", True).execute()
        
        accounts = []
        for account in result.data:
            accounts.append({
                "id": account["id"],
                "name": account["name"],
                "username": account.get("username"),
                "profile_picture": account.get("profile_image_url"),
                "account_type": account.get("account_type", "PERSONAL"),
                "follower_count": account.get("follower_count", 0),
                "board_count": account.get("board_count", 0),
                "pin_count": account.get("pin_count", 0),
            })
        
        return accounts
    
    async def remove_account(self, user_id: str, account_id: str) -> bool:
        """Remove Pinterest account and clean up associated toggles - Following YouTube pattern"""
        client = await self.db.client
        
        # First, clean up MCP toggles for this account
        await self._cleanup_account_toggles(user_id, account_id)
        
        # Clean up unified social accounts
        await self._cleanup_unified_accounts(user_id, account_id)
        
        # Then remove the account
        result = await client.table("pinterest_accounts").delete().eq(
            "user_id", user_id
        ).eq("id", account_id).execute()
        
        success = bool(result.data)
        
        if success:
            logger.info(f"Removed Pinterest account {account_id} for user {user_id}")
        
        return success
    
    async def _cleanup_account_toggles(self, user_id: str, account_id: str):
        """Clean up MCP toggle entries when account is disconnected - Following YouTube pattern"""
        client = await self.db.client
        
        try:
            mcp_id = f"social.pinterest.{account_id}"
            
            # Delete all toggle entries for this account
            result = await client.table("agent_mcp_toggles").delete().eq(
                "user_id", user_id
            ).eq("mcp_id", mcp_id).execute()
            
            if result.data:
                logger.info(f"Cleaned up {len(result.data)} Pinterest MCP toggle entries for account {account_id}")
            else:
                logger.info(f"No Pinterest MCP toggle entries found for account {account_id}")
                
        except Exception as e:
            logger.error(f"Failed to clean up Pinterest MCP toggles for account {account_id}: {e}")
    
    async def _cleanup_unified_accounts(self, user_id: str, account_id: str):
        """Clean up unified social accounts when account is disconnected"""
        client = await self.db.client
        
        try:
            # Remove from unified accounts for all agents
            result = await client.table("agent_social_accounts").delete().eq(
                "user_id", user_id
            ).eq("platform", "pinterest").eq("account_id", account_id).execute()
            
            if result.data:
                logger.info(f"Cleaned up {len(result.data)} unified Pinterest account entries for {account_id}")
                
        except Exception as e:
            logger.error(f"Failed to clean up unified Pinterest accounts: {e}")