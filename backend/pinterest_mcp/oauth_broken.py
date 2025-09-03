"""Pinterest OAuth Handler"""

import hashlib
import secrets
import base64
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple
import aiohttp
import json

from services.supabase import DBConnection
from utils.encryption import encrypt_data, decrypt_data
from utils.logger import logger
import os


class PinterestOAuthHandler:
    """Handle Pinterest OAuth authentication flow"""
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.client_id = os.getenv("PINTEREST_CLIENT_ID", "1509701")
        self.client_secret = os.getenv("PINTEREST_CLIENT_SECRET")
        self.redirect_uri = os.getenv("PINTEREST_REDIRECT_URI", "http://localhost:8000/api/pinterest/auth/callback")
        
        # Pinterest OAuth endpoints
        self.auth_url = "https://www.pinterest.com/oauth"
        self.token_url = "https://api.pinterest.com/v5/oauth/token"
        self.api_base_url = "https://api.pinterest.com/v5"
        
        # Pinterest OAuth scopes
        self.scopes = [
            "pins:read",
            "pins:write",
            "boards:read",
            "boards:write",
            "user_accounts:read"
        ]
    
    def get_auth_url(self, state: str) -> Tuple[str, str, str]:
        """Generate Pinterest OAuth authorization URL with PKCE"""
        
        # Generate PKCE parameters
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        
        # Generate OAuth state
        oauth_state = secrets.token_urlsafe(32)
        
        # Build authorization URL
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'state': f"{oauth_state}:{state}",  # Combine OAuth state with user state
            'scope': ' '.join(self.scopes),
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256'
        }
        
        auth_url = self.auth_url + '?' + '&'.join([f"{k}={v}" for k, v in params.items()])
        
        return auth_url, code_verifier, oauth_state
    
    async def store_oauth_session(self, oauth_state: str, code_verifier: str, user_id: str):
        """Store OAuth session data securely"""
        try:
            session_data = {
                'code_verifier': code_verifier,
                'user_id': user_id,
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Encrypt session data
            encrypted_data = encrypt_data(json.dumps(session_data))
            
            client = await self.db.client
            await client.table("pinterest_oauth_sessions").upsert({
                "state": oauth_state,
                "session_data": encrypted_data,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat()
            }).execute()
            
        except Exception as e:
            logger.error(f"Failed to store Pinterest OAuth session: {e}")
            raise
    
    async def get_oauth_session(self, oauth_state: str) -> Optional[Dict[str, Any]]:
        """Retrieve OAuth session data"""
        try:
            client = await self.db.client
            result = await client.table("pinterest_oauth_sessions").select("session_data").eq(
                "state", oauth_state
            ).gt("expires_at", datetime.utcnow().isoformat()).execute()
            
            if not result.data:
                return None
            
            row = result.data[0]
            
            if not row:
                return None
            
            # Decrypt session data
            decrypted_data = decrypt_data(row['session_data'])
            return json.loads(decrypted_data)
            
        except Exception as e:
            logger.error(f"Failed to get Pinterest OAuth session: {e}")
            return None
    
    async def cleanup_oauth_session(self, oauth_state: str):
        """Clean up OAuth session after use"""
        try:
            client = await self.db.client
            await client.table("pinterest_oauth_sessions").delete().eq(
                "state", oauth_state
            ).execute()
        except Exception as e:
            logger.error(f"Failed to cleanup Pinterest OAuth session: {e}")
    
    async def exchange_code_for_tokens(self, code: str, code_verifier: str) -> Tuple[str, Optional[str], datetime]:
        """Exchange authorization code for access tokens"""
        try:
            data = {
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': self.redirect_uri,
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code_verifier': code_verifier
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.token_url, data=data) as response:
                    response.raise_for_status()
                    token_data = await response.json()
            
            access_token = token_data['access_token']
            refresh_token = token_data.get('refresh_token')
            expires_in = token_data.get('expires_in', 2592000)  # Default 30 days
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            logger.info(f"Successfully exchanged Pinterest code for tokens. Expires in {expires_in} seconds")
            return access_token, refresh_token, expires_at
            
        except Exception as e:
            logger.error(f"Failed to exchange Pinterest code for tokens: {e}")
            raise
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get Pinterest user profile information"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}/user_account",
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    user_data = await response.json()
            
            # Extract user information
            user_info = {
                'id': user_data['id'],
                'username': user_data['username'],
                'name': user_data.get('business_name') or user_data.get('username'),
                'profile_image_url': user_data.get('profile_image'),
                'website_url': user_data.get('website_url'),
                'about': user_data.get('about'),
                'pin_count': user_data.get('pin_count', 0),
                'board_count': user_data.get('board_count', 0),
                'follower_count': user_data.get('follower_count', 0),
                'following_count': user_data.get('following_count', 0),
                'account_type': user_data.get('account_type', 'PERSONAL')  # PERSONAL or BUSINESS
            }
            
            logger.info(f"Retrieved Pinterest user info for: {user_info['name']} (@{user_info['username']})")
            return user_info
            
        except Exception as e:
            logger.error(f"Failed to get Pinterest user info: {e}")
            raise
    
    async def save_account(self, user_id: str, user_info: Dict[str, Any], 
                          access_token: str, refresh_token: Optional[str], 
                          expires_at: datetime) -> str:
        """Save Pinterest account to database"""
        try:
            # Encrypt tokens
            encrypted_access_token = encrypt_data(access_token)
            encrypted_refresh_token = encrypt_data(refresh_token) if refresh_token else None
            
            account_id = user_info['id']
            
            await self.db.execute("""
                INSERT INTO pinterest_accounts (
                    id, user_id, username, name, profile_image_url, website_url,
                    about, pin_count, board_count, follower_count, following_count,
                    account_type, access_token, refresh_token, token_expires_at,
                    token_scopes, is_active, created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, true, NOW(), NOW()
                )
                ON CONFLICT (id, user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    name = EXCLUDED.name,
                    profile_image_url = EXCLUDED.profile_image_url,
                    website_url = EXCLUDED.website_url,
                    about = EXCLUDED.about,
                    pin_count = EXCLUDED.pin_count,
                    board_count = EXCLUDED.board_count,
                    follower_count = EXCLUDED.follower_count,
                    following_count = EXCLUDED.following_count,
                    account_type = EXCLUDED.account_type,
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    token_expires_at = EXCLUDED.token_expires_at,
                    token_scopes = EXCLUDED.token_scopes,
                    is_active = true,
                    needs_reauth = false,
                    updated_at = NOW()
            """, 
                account_id, user_id, user_info['username'], user_info['name'],
                user_info['profile_image_url'], user_info['website_url'], user_info['about'],
                user_info['pin_count'], user_info['board_count'], user_info['follower_count'],
                user_info['following_count'], user_info['account_type'],
                encrypted_access_token, encrypted_refresh_token, expires_at, self.scopes
            )
            
            logger.info(f"Saved Pinterest account {account_id} for user {user_id}")
            return account_id
            
        except Exception as e:
            logger.error(f"Failed to save Pinterest account: {e}")
            raise
    
    async def get_valid_token(self, user_id: str, account_id: str) -> str:
        """Get a valid access token, refreshing if necessary"""
        try:
            account = await self.db.fetchrow("""
                SELECT access_token, refresh_token, token_expires_at, needs_reauth
                FROM pinterest_accounts 
                WHERE user_id = $1 AND id = $2 AND is_active = true
            """, user_id, account_id)
            
            if not account:
                raise Exception("Pinterest account not found")
            
            if account['needs_reauth']:
                raise Exception("Account requires re-authentication")
            
            # Check if token is still valid (with 5 minute buffer)
            expires_at = account['token_expires_at']
            if expires_at > datetime.utcnow() + timedelta(minutes=5):
                return decrypt_data(account['access_token'])
            
            # Try to refresh token if available
            if account['refresh_token']:
                try:
                    return await self._refresh_token(user_id, account_id, account['refresh_token'])
                except Exception as e:
                    logger.error(f"Pinterest token refresh failed: {e}")
                    # Mark as needing re-auth
                    await self.db.execute("""
                        UPDATE pinterest_accounts 
                        SET needs_reauth = true, last_refresh_error = $3
                        WHERE user_id = $1 AND id = $2
                    """, user_id, account_id, str(e))
                    raise Exception("Token expired and refresh failed. Please re-authenticate.")
            
            raise Exception("Token expired and no refresh token available. Please re-authenticate.")
            
        except Exception as e:
            logger.error(f"Failed to get valid Pinterest token: {e}")
            raise
    
    async def _refresh_token(self, user_id: str, account_id: str, encrypted_refresh_token: str) -> str:
        """Refresh Pinterest access token"""
        try:
            refresh_token = decrypt_data(encrypted_refresh_token)
            
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.token_url, data=data) as response:
                    response.raise_for_status()
                    token_data = await response.json()
            
            new_access_token = token_data['access_token']
            new_refresh_token = token_data.get('refresh_token', refresh_token)
            expires_in = token_data.get('expires_in', 2592000)  # Default 30 days
            new_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            # Update tokens in database
            await self.db.execute("""
                UPDATE pinterest_accounts SET
                    access_token = $3,
                    refresh_token = $4,
                    token_expires_at = $5,
                    needs_reauth = false,
                    last_refresh_success = NOW(),
                    last_refresh_error = NULL,
                    refresh_failure_count = 0,
                    updated_at = NOW()
                WHERE user_id = $1 AND id = $2
            """, user_id, account_id, 
                encrypt_data(new_access_token),
                encrypt_data(new_refresh_token),
                new_expires_at
            )
            
            logger.info(f"Successfully refreshed Pinterest token for account {account_id}")
            return new_access_token
            
        except Exception as e:
            logger.error(f"Failed to refresh Pinterest token: {e}")
            
            # Update failure count
            await self.db.execute("""
                UPDATE pinterest_accounts SET
                    last_refresh_error = $3,
                    last_refresh_attempt = NOW(),
                    refresh_failure_count = refresh_failure_count + 1,
                    needs_reauth = (refresh_failure_count + 1 >= 3)
                WHERE user_id = $1 AND id = $2
            """, user_id, account_id, str(e))
            
            raise
    
    async def remove_account(self, user_id: str, account_id: str) -> bool:
        """Remove Pinterest account"""
        try:
            result = await self.db.execute("""
                UPDATE pinterest_accounts 
                SET is_active = false, updated_at = NOW()
                WHERE user_id = $1 AND id = $2
            """, user_id, account_id)
            
            # Also remove from agent_social_accounts
            await self.db.execute("""
                DELETE FROM agent_social_accounts
                WHERE user_id = $1 AND platform = 'pinterest' AND account_id = $2
            """, user_id, account_id)
            
            logger.info(f"Removed Pinterest account {account_id} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove Pinterest account: {e}")
            return False