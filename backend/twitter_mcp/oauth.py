"""Twitter OAuth handler for MCP integration"""

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


class TwitterOAuthHandler:
    """Handles Twitter OAuth 2.0 flow and token management"""
    
    OAUTH_URL = "https://twitter.com/i/oauth2/authorize"
    TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
    REVOKE_URL = "https://api.twitter.com/2/oauth2/revoke"
    SCOPES = [
        "tweet.read",
        "tweet.write",
        "users.read",
        "offline.access"
    ]
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.client_id = os.getenv("TWITTER_CLIENT_ID")
        self.client_secret = os.getenv("TWITTER_CLIENT_SECRET")
        self.redirect_uri = os.getenv("TWITTER_REDIRECT_URI", "http://localhost:8000/api/twitter/auth/callback")
        
        # Encryption key for tokens
        encryption_key = os.getenv("MCP_CREDENTIAL_ENCRYPTION_KEY")
        if encryption_key:
            self.fernet = Fernet(encryption_key.encode())
        else:
            # Generate a key if not provided (not recommended for production)
            logger.warning("No MCP_CREDENTIAL_ENCRYPTION_KEY found, generating temporary key")
            self.fernet = Fernet(Fernet.generate_key())
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Twitter OAuth credentials not configured")
    
    def get_auth_url(self, state: Optional[str] = None) -> tuple[str, str, str]:
        """Generate OAuth authorization URL with PKCE"""
        if not state:
            state = secrets.token_urlsafe(32)
        
        # Generate PKCE parameters
        code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.SCOPES),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        
        auth_url = f"{self.OAUTH_URL}?{urlencode(params)}"
        return auth_url, code_verifier, state
    
    async def store_oauth_session(self, state: str, code_verifier: str, user_id: str):
        """Store OAuth session data temporarily"""
        client = await self.db.client
        
        session_data = {
            "state": state,
            "code_verifier": code_verifier,
            "user_id": user_id,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        }
        
        await client.table("twitter_oauth_sessions").upsert({
            "state": state,
            "session_data": self.encrypt_token(json.dumps(session_data)),
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
    
    async def get_oauth_session(self, state: str) -> Optional[Dict[str, Any]]:
        """Retrieve OAuth session data"""
        client = await self.db.client
        
        result = await client.table("twitter_oauth_sessions").select("*").eq(
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
        await client.table("twitter_oauth_sessions").delete().eq("state", state).execute()
    
    async def exchange_code_for_tokens(self, code: str, code_verifier: str) -> Tuple[str, str, datetime]:
        """Exchange authorization code for access and refresh tokens"""
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(self.client_id, self.client_secret)
            data = {
                "code": code,
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "code_verifier": code_verifier,
            }
            
            async with session.post(self.TOKEN_URL, data=data, auth=auth) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Token exchange failed: {error_text}")
                    raise Exception(f"Token exchange failed: {error_text}")
                
                token_data = await response.json()
                
                access_token = token_data["access_token"]
                refresh_token = token_data.get("refresh_token")
                expires_in = token_data.get("expires_in", 7200)  # Twitter default is 2 hours
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                
                return access_token, refresh_token, expires_at
    
    async def refresh_access_token(self, refresh_token: str) -> Tuple[str, datetime]:
        """Refresh an expired access token"""
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(self.client_id, self.client_secret)
            data = {
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
            
            async with session.post(self.TOKEN_URL, data=data, auth=auth) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Token refresh failed: {error_text}")
                    raise Exception(f"Token refresh failed: {error_text}")
                
                token_data = await response.json()
                
                access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 7200)
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                
                return access_token, expires_at
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Fetch Twitter user information for authenticated user"""
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Get user info using Twitter API v2
            async with session.get(
                "https://api.twitter.com/2/users/me?user.fields=id,name,username,description,profile_image_url,public_metrics,verified,created_at",
                headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to fetch user info: {error_text}")
                    raise Exception(f"Failed to fetch user info: {error_text}")
                
                user_response = await response.json()
                
                if "errors" in user_response:
                    raise Exception(f"Twitter API error: {user_response['errors']}")
                
                user_data = user_response["data"]
                public_metrics = user_data.get("public_metrics", {})
                
                user_info = {
                    "id": user_data["id"],
                    "name": user_data["name"],
                    "username": user_data["username"],
                    "description": user_data.get("description", ""),
                    "profile_image_url": user_data.get("profile_image_url", ""),
                    "followers_count": public_metrics.get("followers_count", 0),
                    "following_count": public_metrics.get("following_count", 0),
                    "tweet_count": public_metrics.get("tweet_count", 0),
                    "listed_count": public_metrics.get("listed_count", 0),
                    "verified": user_data.get("verified", False),
                    "created_at": user_data.get("created_at"),
                }
                
                logger.info(f"Fetched Twitter user info for {user_info['name']} (@{user_info['username']})")
                
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
        """Save Twitter account to database"""
        client = await self.db.client
        
        # Encrypt tokens
        encrypted_access = self.encrypt_token(access_token)
        encrypted_refresh = self.encrypt_token(refresh_token) if refresh_token else None
        
        # Prepare account data
        account_data = {
            "id": user_info["id"],
            "user_id": user_id,
            "name": user_info["name"],
            "username": user_info["username"],
            "description": user_info.get("description"),
            "profile_image_url": user_info.get("profile_image_url"),
            "followers_count": user_info.get("followers_count", 0),
            "following_count": user_info.get("following_count", 0),
            "tweet_count": user_info.get("tweet_count", 0),
            "listed_count": user_info.get("listed_count", 0),
            "verified": user_info.get("verified", False),
            "twitter_created_at": user_info.get("created_at"),
            "access_token": encrypted_access,
            "refresh_token": encrypted_refresh,
            "token_expires_at": expires_at.isoformat(),
            "token_scopes": self.SCOPES,
            "is_active": True,
        }
        
        # Upsert account (update if exists, insert if not)
        result = await client.table("twitter_accounts").upsert(
            account_data,
            on_conflict="id,user_id"
        ).execute()
        
        if result.data:
            logger.info(f"Saved Twitter account {user_info['id']} for user {user_id}: @{user_info['username']}")
            
            # Create MCP toggle entries for all user's agents
            await self._create_account_toggles(user_id, user_info["id"])
            
            return user_info["id"]
        else:
            raise Exception("Failed to save Twitter account")
    
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
                mcp_id = f"social.twitter.{account_id}"
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
                        logger.info(f"Created MCP toggle for agent {agent_id}, Twitter account {account_id} (enabled by default)")
                
                if created_count > 0:
                    logger.info(f"Created {created_count} MCP toggle entries for Twitter account {account_id}")
            else:
                logger.info(f"No agents found for user {user_id}, no toggles created")
                
        except Exception as e:
            logger.error(f"Failed to create MCP toggles for Twitter account {account_id}: {e}")
            # Don't fail the account save if toggle creation fails
    
    async def get_valid_token(self, user_id: str, account_id: str) -> str:
        """Get a valid access token, refreshing if necessary"""
        client = await self.db.client
        
        # Get account from database
        result = await client.table("twitter_accounts").select("*").eq(
            "user_id", user_id
        ).eq("id", account_id).execute()
        
        if not result.data:
            raise Exception(f"Twitter account {account_id} not found")
        
        account = result.data[0]
        
        # Decrypt tokens
        access_token = self.decrypt_token(account["access_token"])
        refresh_token = self.decrypt_token(account["refresh_token"]) if account.get("refresh_token") else None
        
        # Parse token expiry time with robust timezone handling
        token_expires = account["token_expires_at"]
        if token_expires.endswith('Z'):
            token_expires = token_expires.replace('Z', '+00:00')
        elif '+' not in token_expires and '-' not in token_expires[-6:]:
            # No timezone info, assume UTC
            token_expires = token_expires + '+00:00'
        expires_at = datetime.fromisoformat(token_expires)
        
        # Proactive 5-minute buffer for seamless experience
        buffer_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        time_until_expiry = expires_at - datetime.now(timezone.utc)
        
        logger.info(f"🔍 Token Check: Expires {expires_at}, Buffer {buffer_time}, Time left: {time_until_expiry}")
        
        # Token still has >5 minutes? Use it!
        if expires_at > buffer_time:
            logger.debug(f"✅ Token Valid: {time_until_expiry} remaining for @{account['username']}")
            return access_token
        
        # Fully automatic refresh: Zero manual intervention required
        if not refresh_token:
            logger.warning(f"⚠️ No refresh token available for @{account['username']} - using fallback token strategy")
            logger.info(f"🤖 AUTOMATIC FALLBACK: Attempting tweet with existing token for @{account['username']}")
            return access_token  # Let tweet attempt proceed, might still work
        
        logger.info(f"🤖 FULLY AUTOMATIC REFRESH: Silently refreshing token for @{account['username']} (expires in {time_until_expiry})")
        
        try:
            # Silent automatic refresh: No user interaction required
            new_access_token, new_expires_at = await self.refresh_access_token(refresh_token)
            
            # Update database with fresh token
            encrypted_access = self.encrypt_token(new_access_token)
            
            await client.table("twitter_accounts").update({
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
            await client.table("twitter_accounts").update({
                "last_refresh_error": str(refresh_error),
                "last_refresh_attempt": datetime.now(timezone.utc).isoformat(),
                "refresh_failure_count": account.get("refresh_failure_count", 0) + 1,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", account_id).eq("user_id", user_id).execute()
            
            # Automatic fallback: Try existing token anyway
            logger.info(f"🤖 AUTOMATIC FALLBACK: Using existing token for @{account['username']} despite refresh failure")
            return access_token  # Let tweet proceed - might work anyway
    
    async def get_user_accounts(self, user_id: str) -> list:
        """Get all Twitter accounts for a user"""
        client = await self.db.client
        
        result = await client.table("twitter_accounts").select("*").eq(
            "user_id", user_id
        ).eq("is_active", True).execute()
        
        accounts = []
        for account in result.data:
            accounts.append({
                "id": account["id"],
                "name": account["name"],
                "username": account["username"],
                "description": account.get("description"),
                "profile_image_url": account.get("profile_image_url"),
                "followers_count": account.get("followers_count", 0),
                "following_count": account.get("following_count", 0),
                "tweet_count": account.get("tweet_count", 0),
                "verified": account.get("verified", False),
            })
        
        return accounts
    
    async def remove_account(self, user_id: str, account_id: str) -> bool:
        """Remove a Twitter account connection and clean up associated toggles"""
        client = await self.db.client
        
        # First, clean up MCP toggles for this account
        await self._cleanup_account_toggles(user_id, account_id)
        
        # Then remove the account
        result = await client.table("twitter_accounts").delete().eq(
            "user_id", user_id
        ).eq("id", account_id).execute()
        
        success = bool(result.data)
        
        if success:
            logger.info(f"Removed Twitter account {account_id} for user {user_id}")
        
        return success
    
    async def _cleanup_account_toggles(self, user_id: str, account_id: str):
        """Clean up MCP toggle entries when an account is disconnected"""
        client = await self.db.client
        
        try:
            mcp_id = f"social.twitter.{account_id}"
            
            # Delete all toggle entries for this account
            result = await client.table("agent_mcp_toggles").delete().eq(
                "user_id", user_id
            ).eq("mcp_id", mcp_id).execute()
            
            if result.data:
                logger.info(f"Cleaned up {len(result.data)} MCP toggle entries for Twitter account {account_id}")
            else:
                logger.info(f"No MCP toggle entries found for Twitter account {account_id}")
                
        except Exception as e:
            logger.error(f"Failed to clean up MCP toggles for Twitter account {account_id}: {e}")