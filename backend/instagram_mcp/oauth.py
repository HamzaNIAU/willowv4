"""Instagram OAuth handler for MCP integration"""

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


class InstagramOAuthHandler:
    """Handles Instagram OAuth 2.0 flow and token management"""
    
    OAUTH_URL = "https://api.instagram.com/oauth/authorize"
    TOKEN_URL = "https://api.instagram.com/oauth/access_token"
    LONG_LIVED_TOKEN_URL = "https://graph.instagram.com/access_token"
    REFRESH_TOKEN_URL = "https://graph.instagram.com/refresh_access_token"
    SCOPES = [
        "user_profile",
        "user_media"
    ]
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.client_id = os.getenv("INSTAGRAM_CLIENT_ID")
        self.client_secret = os.getenv("INSTAGRAM_CLIENT_SECRET")
        self.redirect_uri = os.getenv("INSTAGRAM_REDIRECT_URI", "http://localhost:8000/api/instagram/auth/callback")
        
        # Encryption key for tokens
        encryption_key = os.getenv("MCP_CREDENTIAL_ENCRYPTION_KEY")
        if encryption_key:
            self.fernet = Fernet(encryption_key.encode())
        else:
            # Generate a key if not provided (not recommended for production)
            logger.warning("No MCP_CREDENTIAL_ENCRYPTION_KEY found, generating temporary key")
            self.fernet = Fernet(Fernet.generate_key())
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Instagram OAuth credentials not configured")
    
    def get_auth_url(self, state: Optional[str] = None) -> tuple[str, str, str]:
        """Generate OAuth authorization URL"""
        if not state:
            state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": ",".join(self.SCOPES),
            "response_type": "code",
            "state": state,
        }
        
        auth_url = f"{self.OAUTH_URL}?{urlencode(params)}"
        return auth_url, "", state  # No code_verifier for Instagram Basic Display
    
    async def store_oauth_session(self, state: str, code_verifier: str, user_id: str):
        """Store OAuth session data temporarily"""
        client = await self.db.client
        
        session_data = {
            "state": state,
            "code_verifier": code_verifier,  # Not used for Instagram but kept for compatibility
            "user_id": user_id,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        }
        
        await client.table("instagram_oauth_sessions").upsert({
            "state": state,
            "session_data": self.encrypt_token(json.dumps(session_data)),
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
    
    async def get_oauth_session(self, state: str) -> Optional[Dict[str, Any]]:
        """Retrieve OAuth session data"""
        client = await self.db.client
        
        result = await client.table("instagram_oauth_sessions").select("*").eq(
            "state", state
        ).execute()
        
        if not result.data:
            return None
        
        try:
            session_raw = result.data[0]["session_data"]
            session_data = json.loads(self.decrypt_token(session_raw))
            
            # Check if session is expired
            expires_at = datetime.fromisoformat(session_data["expires_at"].replace('Z', '+00:00'))
            if datetime.now(timezone.utc) > expires_at:
                await self.cleanup_oauth_session(state)
                return None
            
            return session_data
        except Exception as e:
            logger.error(f"Failed to decrypt OAuth session: {e}")
            await self.cleanup_oauth_session(state)
            return None
    
    async def cleanup_oauth_session(self, state: str):
        """Clean up expired OAuth session"""
        client = await self.db.client
        await client.table("instagram_oauth_sessions").delete().eq("state", state).execute()
    
    async def exchange_code_for_tokens(self, code: str, code_verifier: str = None) -> Tuple[str, str, datetime]:
        """Exchange authorization code for access token and convert to long-lived token"""
        async with aiohttp.ClientSession() as session:
            # Step 1: Exchange code for short-lived token
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
                "code": code,
            }
            
            async with session.post(self.TOKEN_URL, data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Token exchange failed: {error_text}")
                    raise Exception(f"Token exchange failed: {error_text}")
                
                token_data = await response.json()
                short_lived_token = token_data["access_token"]
                
            # Step 2: Convert to long-lived token (60 days)
            long_lived_params = {
                "grant_type": "ig_exchange_token",
                "client_secret": self.client_secret,
                "access_token": short_lived_token
            }
            
            async with session.get(self.LONG_LIVED_TOKEN_URL, params=long_lived_params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Long-lived token exchange failed: {error_text}")
                    # Use short-lived token as fallback
                    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
                    return short_lived_token, None, expires_at
                
                long_lived_data = await response.json()
                access_token = long_lived_data["access_token"]
                expires_in = long_lived_data.get("expires_in", 5184000)  # 60 days default
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                
                return access_token, None, expires_at  # Instagram doesn't provide refresh tokens
    
    async def refresh_access_token(self, access_token: str) -> Tuple[str, datetime]:
        """Refresh a long-lived token (extends for another 60 days)"""
        async with aiohttp.ClientSession() as session:
            params = {
                "grant_type": "ig_refresh_token",
                "access_token": access_token
            }
            
            async with session.get(self.REFRESH_TOKEN_URL, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Token refresh failed: {error_text}")
                    raise Exception(f"Token refresh failed: {error_text}")
                
                token_data = await response.json()
                
                new_access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 5184000)  # 60 days
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                
                return new_access_token, expires_at
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Fetch Instagram user information for authenticated user"""
        async with aiohttp.ClientSession() as session:
            params = {
                "fields": "id,username,account_type,media_count",
                "access_token": access_token
            }
            
            async with session.get(
                "https://graph.instagram.com/me",
                params=params
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to fetch user info: {error_text}")
                    raise Exception(f"Failed to fetch user info: {error_text}")
                
                user_response = await response.json()
                
                if "error" in user_response:
                    raise Exception(f"Instagram API error: {user_response['error']}")
                
                # Get additional profile info if available
                profile_params = {
                    "fields": "biography,followers_count,follows_count,media_count,name,profile_picture_url,username,website",
                    "access_token": access_token
                }
                
                profile_info = {}
                try:
                    async with session.get(
                        f"https://graph.instagram.com/{user_response['id']}",
                        params=profile_params
                    ) as profile_response:
                        if profile_response.status == 200:
                            profile_info = await profile_response.json()
                except Exception as e:
                    logger.warning(f"Could not fetch detailed profile info: {e}")
                
                user_info = {
                    "id": user_response["id"],
                    "username": user_response["username"],
                    "account_type": user_response.get("account_type", "PERSONAL"),
                    "name": profile_info.get("name", user_response["username"]),
                    "biography": profile_info.get("biography", ""),
                    "profile_picture_url": profile_info.get("profile_picture_url", ""),
                    "website": profile_info.get("website", ""),
                    "followers_count": profile_info.get("followers_count", 0),
                    "following_count": profile_info.get("follows_count", 0),
                    "media_count": profile_info.get("media_count", user_response.get("media_count", 0)),
                }
                
                logger.info(f"Fetched Instagram user info for {user_info['name']} (@{user_info['username']})")
                
                return user_info
    
    def encrypt_token(self, token: str) -> str:
        """Encrypt a token for storage"""
        return self.fernet.encrypt(token.encode()).decode()
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt a stored token"""
        return self.fernet.decrypt(encrypted_token.encode()).decode()
    
    async def save_account(
        self,
        user_id: str,
        user_info: Dict[str, Any],
        access_token: str,
        refresh_token: Optional[str],
        expires_at: datetime
    ) -> str:
        """Save Instagram account to database"""
        client = await self.db.client
        
        # Encrypt token
        encrypted_access = self.encrypt_token(access_token)
        
        # Prepare account data
        account_data = {
            "id": user_info["id"],
            "user_id": user_id,
            "username": user_info["username"],
            "name": user_info["name"],
            "biography": user_info.get("biography"),
            "profile_picture_url": user_info.get("profile_picture_url"),
            "website": user_info.get("website"),
            "account_type": user_info.get("account_type", "PERSONAL"),
            "followers_count": user_info.get("followers_count", 0),
            "following_count": user_info.get("following_count", 0),
            "media_count": user_info.get("media_count", 0),
            "access_token": encrypted_access,
            "token_expires_at": expires_at.isoformat(),
            "token_scopes": self.SCOPES,
            "is_active": True,
        }
        
        # Upsert account (update if exists, insert if not)
        result = await client.table("instagram_accounts").upsert(
            account_data,
            on_conflict="id,user_id"
        ).execute()
        
        if result.data:
            logger.info(f"Saved Instagram account {user_info['id']} for user {user_id}: @{user_info['username']}")
            
            # Create MCP toggle entries for all user's agents
            await self._create_account_toggles(user_id, user_info["id"])
            
            return user_info["id"]
        else:
            raise Exception("Failed to save Instagram account")
    
    async def _create_account_toggles(self, user_id: str, account_id: str):
        """Create MCP toggle entries for all user's agents when an account is connected"""
        from services.mcp_toggles import MCPToggleService
        
        client = await self.db.client
        toggle_service = MCPToggleService(self.db)
        
        try:
            # Get all agents for this user
            agents_result = await client.table("agents").select("agent_id").eq(
                "account_id", user_id
            ).execute()
            
            if agents_result.data:
                mcp_id = f"social.instagram.{account_id}"
                created_count = 0
                
                for agent in agents_result.data:
                    agent_id = agent["agent_id"]
                    
                    # Create toggle entry (default to enabled for better UX)
                    success = await toggle_service.set_toggle(
                        agent_id=agent_id,
                        user_id=user_id,
                        mcp_id=mcp_id,
                        enabled=True  # Default to enabled
                    )
                    
                    if success:
                        created_count += 1
                        logger.info(f"Created MCP toggle for agent {agent_id}, Instagram account {account_id} (enabled by default)")
                
                if created_count > 0:
                    logger.info(f"Created {created_count} MCP toggle entries for Instagram account {account_id}")
            else:
                logger.info(f"No agents found for user {user_id}, no toggles created")
                
        except Exception as e:
            logger.error(f"Failed to create MCP toggles for Instagram account {account_id}: {e}")
            # Don't fail the account save if toggle creation fails
    
    async def get_valid_token(self, user_id: str, account_id: str) -> str:
        """Get a valid access token, refreshing if necessary"""
        client = await self.db.client
        
        # Get account from database
        result = await client.table("instagram_accounts").select("*").eq(
            "user_id", user_id
        ).eq("id", account_id).execute()
        
        if not result.data:
            raise Exception(f"Instagram account {account_id} not found")
        
        account = result.data[0]
        
        # Decrypt token
        access_token = self.decrypt_token(account["access_token"])
        
        # Parse token expiry time with robust timezone handling
        token_expires = account["token_expires_at"]
        if token_expires.endswith('Z'):
            token_expires = token_expires.replace('Z', '+00:00')
        elif '+' not in token_expires and '-' not in token_expires[-6:]:
            # No timezone info, assume UTC
            token_expires = token_expires + '+00:00'
        expires_at = datetime.fromisoformat(token_expires)
        
        # Proactive 7-day buffer for token refresh (Instagram tokens last 60 days)
        buffer_time = datetime.now(timezone.utc) + timedelta(days=7)
        time_until_expiry = expires_at - datetime.now(timezone.utc)
        
        logger.info(f"🔍 Token Check: Expires {expires_at}, Buffer {buffer_time}, Time left: {time_until_expiry}")
        
        # Token still has >7 days? Use it!
        if expires_at > buffer_time:
            logger.debug(f"✅ Token Valid: {time_until_expiry} remaining for @{account['username']}")
            return access_token
        
        # Auto-refresh Instagram long-lived token (extends by 60 days)
        logger.info(f"🤖 FULLY AUTOMATIC REFRESH: Silently refreshing token for @{account['username']} (expires in {time_until_expiry})")
        
        try:
            # Silent automatic refresh: No user interaction required
            new_access_token, new_expires_at = await self.refresh_access_token(access_token)
            
            # Update database with fresh token
            encrypted_access = self.encrypt_token(new_access_token)
            
            await client.table("instagram_accounts").update({
                "access_token": encrypted_access,
                "token_expires_at": new_expires_at.isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "last_refresh_success": datetime.now(timezone.utc).isoformat(),
                "needs_reauth": False,  # Clear re-auth flags
                "refresh_failure_count": 0  # Reset failure count
            }).eq("id", account_id).eq("user_id", user_id).execute()
            
            new_time_until_expiry = new_expires_at - datetime.now(timezone.utc)
            logger.info(f"🎉 SILENT REFRESH SUCCESS: @{account['username']} token automatically renewed! New expiry: {new_expires_at}")
            
            return new_access_token
            
        except Exception as refresh_error:
            logger.warning(f"⚠️ AUTOMATIC REFRESH ATTEMPT FAILED for @{account['username']}: {refresh_error}")
            
            # Graceful degradation: Don't throw errors, try to continue with existing token
            await client.table("instagram_accounts").update({
                "last_refresh_error": str(refresh_error),
                "last_refresh_attempt": datetime.now(timezone.utc).isoformat(),
                "refresh_failure_count": account.get("refresh_failure_count", 0) + 1,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", account_id).eq("user_id", user_id).execute()
            
            # Automatic fallback: Try existing token anyway
            logger.info(f"🤖 AUTOMATIC FALLBACK: Using existing token for @{account['username']} despite refresh failure")
            return access_token  # Let post attempt proceed - might work anyway
    
    async def get_user_accounts(self, user_id: str) -> list:
        """Get all Instagram accounts for a user"""
        client = await self.db.client
        
        result = await client.table("instagram_accounts").select("*").eq(
            "user_id", user_id
        ).eq("is_active", True).execute()
        
        accounts = []
        for account in result.data:
            accounts.append({
                "id": account["id"],
                "username": account["username"],
                "name": account["name"],
                "biography": account.get("biography"),
                "profile_picture_url": account.get("profile_picture_url"),
                "website": account.get("website"),
                "account_type": account.get("account_type", "PERSONAL"),
                "followers_count": account.get("followers_count", 0),
                "following_count": account.get("following_count", 0),
                "media_count": account.get("media_count", 0),
            })
        
        return accounts
    
    async def remove_account(self, user_id: str, account_id: str) -> bool:
        """Remove an Instagram account connection and clean up associated toggles"""
        client = await self.db.client
        
        # First, clean up MCP toggles for this account
        await self._cleanup_account_toggles(user_id, account_id)
        
        # Then remove the account
        result = await client.table("instagram_accounts").delete().eq(
            "user_id", user_id
        ).eq("id", account_id).execute()
        
        success = bool(result.data)
        
        if success:
            logger.info(f"Removed Instagram account {account_id} for user {user_id}")
        
        return success
    
    async def _cleanup_account_toggles(self, user_id: str, account_id: str):
        """Clean up MCP toggle entries when an account is disconnected"""
        client = await self.db.client
        
        try:
            mcp_id = f"social.instagram.{account_id}"
            
            # Delete all toggle entries for this account
            result = await client.table("agent_mcp_toggles").delete().eq(
                "user_id", user_id
            ).eq("mcp_id", mcp_id).execute()
            
            if result.data:
                logger.info(f"Cleaned up {len(result.data)} MCP toggle entries for Instagram account {account_id}")
            else:
                logger.info(f"No MCP toggle entries found for Instagram account {account_id}")
                
        except Exception as e:
            logger.error(f"Failed to clean up MCP toggles for Instagram account {account_id}: {e}")