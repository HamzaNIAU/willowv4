"""LinkedIn OAuth Handler"""

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


class LinkedInOAuthHandler:
    """Handle LinkedIn OAuth authentication flow"""
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.client_id = os.getenv("LINKEDIN_CLIENT_ID", "86ife4uk6w5mld")
        self.client_secret = os.getenv("LINKEDIN_CLIENT_SECRET")
        self.redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8000/api/linkedin/auth/callback")
        
        # LinkedIn OAuth endpoints
        self.auth_url = "https://www.linkedin.com/oauth/v2/authorization"
        self.token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        self.api_base_url = "https://api.linkedin.com/v2"
        
        # LinkedIn OAuth scopes for professional posting
        self.scopes = [
            "w_member_social",           # Post on behalf of user
            "w_organization_social",     # Post on behalf of company
            "r_liteprofile",            # Basic profile info
            "r_emailaddress"            # Email address
        ]
    
    def get_auth_url(self, state: str) -> Tuple[str, str, str]:
        """Generate LinkedIn OAuth authorization URL with PKCE"""
        
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
            
            await self.db.execute("""
                INSERT INTO linkedin_oauth_sessions (state, session_data, created_at, expires_at)
                VALUES ($1, $2, NOW(), NOW() + INTERVAL '10 minutes')
                ON CONFLICT (state) 
                DO UPDATE SET 
                    session_data = EXCLUDED.session_data,
                    expires_at = EXCLUDED.expires_at
            """, oauth_state, encrypted_data)
            
        except Exception as e:
            logger.error(f"Failed to store LinkedIn OAuth session: {e}")
            raise
    
    async def get_oauth_session(self, oauth_state: str) -> Optional[Dict[str, Any]]:
        """Retrieve OAuth session data"""
        try:
            row = await self.db.fetchrow("""
                SELECT session_data FROM linkedin_oauth_sessions 
                WHERE state = $1 AND expires_at > NOW()
            """, oauth_state)
            
            if not row:
                return None
            
            # Decrypt session data
            decrypted_data = decrypt_data(row['session_data'])
            return json.loads(decrypted_data)
            
        except Exception as e:
            logger.error(f"Failed to get LinkedIn OAuth session: {e}")
            return None
    
    async def cleanup_oauth_session(self, oauth_state: str):
        """Clean up OAuth session after use"""
        try:
            await self.db.execute("""
                DELETE FROM linkedin_oauth_sessions WHERE state = $1
            """, oauth_state)
        except Exception as e:
            logger.error(f"Failed to cleanup LinkedIn OAuth session: {e}")
    
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
            refresh_token = token_data.get('refresh_token')  # LinkedIn may not always provide refresh tokens
            expires_in = token_data.get('expires_in', 5183999)  # Default 60 days
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            logger.info(f"Successfully exchanged LinkedIn code for tokens. Expires in {expires_in} seconds")
            return access_token, refresh_token, expires_at
            
        except Exception as e:
            logger.error(f"Failed to exchange LinkedIn code for tokens: {e}")
            raise
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get LinkedIn user profile information"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                # Get basic profile
                async with session.get(
                    f"{self.api_base_url}/people/~:(id,firstName,lastName,profilePicture(displayImage~:playableStreams))",
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    profile_data = await response.json()
                
                # Get email address
                async with session.get(
                    f"{self.api_base_url}/emailAddress?q=members&projection=(elements*(handle~))",
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    email_data = await response.json()
            
            # Extract profile information
            user_info = {
                'id': profile_data['id'],
                'first_name': profile_data.get('firstName', {}).get('localized', {}).get('en_US', ''),
                'last_name': profile_data.get('lastName', {}).get('localized', {}).get('en_US', ''),
                'name': '',
                'email': '',
                'profile_image_url': ''
            }
            
            # Build full name
            user_info['name'] = f"{user_info['first_name']} {user_info['last_name']}".strip()
            
            # Extract email
            if email_data.get('elements'):
                user_info['email'] = email_data['elements'][0]['handle~']['emailAddress']
            
            # Extract profile picture
            if profile_data.get('profilePicture', {}).get('displayImage~', {}).get('elements'):
                images = profile_data['profilePicture']['displayImage~']['elements']
                if images:
                    # Use the largest available image
                    user_info['profile_image_url'] = images[-1]['identifiers'][0]['identifier']
            
            logger.info(f"Retrieved LinkedIn user info for: {user_info['name']} ({user_info['id']})")
            return user_info
            
        except Exception as e:
            logger.error(f"Failed to get LinkedIn user info: {e}")
            raise
    
    async def save_account(self, user_id: str, user_info: Dict[str, Any], 
                          access_token: str, refresh_token: Optional[str], 
                          expires_at: datetime) -> str:
        """Save LinkedIn account to database"""
        try:
            # Encrypt tokens
            encrypted_access_token = encrypt_data(access_token)
            encrypted_refresh_token = encrypt_data(refresh_token) if refresh_token else None
            
            account_id = user_info['id']
            
            await self.db.execute("""
                INSERT INTO linkedin_accounts (
                    id, user_id, name, first_name, last_name, email,
                    profile_image_url, access_token, refresh_token, token_expires_at,
                    token_scopes, is_active, created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, true, NOW(), NOW()
                )
                ON CONFLICT (id, user_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    email = EXCLUDED.email,
                    profile_image_url = EXCLUDED.profile_image_url,
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    token_expires_at = EXCLUDED.token_expires_at,
                    token_scopes = EXCLUDED.token_scopes,
                    is_active = true,
                    needs_reauth = false,
                    updated_at = NOW()
            """, 
                account_id, user_id, user_info['name'], user_info['first_name'],
                user_info['last_name'], user_info['email'], user_info['profile_image_url'],
                encrypted_access_token, encrypted_refresh_token, expires_at,
                self.scopes
            )
            
            logger.info(f"Saved LinkedIn account {account_id} for user {user_id}")
            return account_id
            
        except Exception as e:
            logger.error(f"Failed to save LinkedIn account: {e}")
            raise
    
    async def get_valid_token(self, user_id: str, account_id: str) -> str:
        """Get a valid access token, refreshing if necessary"""
        try:
            account = await self.db.fetchrow("""
                SELECT access_token, refresh_token, token_expires_at, needs_reauth
                FROM linkedin_accounts 
                WHERE user_id = $1 AND id = $2 AND is_active = true
            """, user_id, account_id)
            
            if not account:
                raise Exception("LinkedIn account not found")
            
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
                    logger.error(f"Token refresh failed: {e}")
                    # Mark as needing re-auth
                    await self.db.execute("""
                        UPDATE linkedin_accounts 
                        SET needs_reauth = true, last_refresh_error = $3
                        WHERE user_id = $1 AND id = $2
                    """, user_id, account_id, str(e))
                    raise Exception("Token expired and refresh failed. Please re-authenticate.")
            
            raise Exception("Token expired and no refresh token available. Please re-authenticate.")
            
        except Exception as e:
            logger.error(f"Failed to get valid LinkedIn token: {e}")
            raise
    
    async def _refresh_token(self, user_id: str, account_id: str, encrypted_refresh_token: str) -> str:
        """Refresh LinkedIn access token"""
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
            new_refresh_token = token_data.get('refresh_token', refresh_token)  # Some APIs don't return new refresh token
            expires_in = token_data.get('expires_in', 5183999)  # Default 60 days
            new_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            # Update tokens in database
            await self.db.execute("""
                UPDATE linkedin_accounts SET
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
            
            logger.info(f"Successfully refreshed LinkedIn token for account {account_id}")
            return new_access_token
            
        except Exception as e:
            logger.error(f"Failed to refresh LinkedIn token: {e}")
            
            # Update failure count
            await self.db.execute("""
                UPDATE linkedin_accounts SET
                    last_refresh_error = $3,
                    last_refresh_attempt = NOW(),
                    refresh_failure_count = refresh_failure_count + 1,
                    needs_reauth = (refresh_failure_count + 1 >= 3)
                WHERE user_id = $1 AND id = $2
            """, user_id, account_id, str(e))
            
            raise
    
    async def remove_account(self, user_id: str, account_id: str) -> bool:
        """Remove LinkedIn account"""
        try:
            result = await self.db.execute("""
                UPDATE linkedin_accounts 
                SET is_active = false, updated_at = NOW()
                WHERE user_id = $1 AND id = $2
            """, user_id, account_id)
            
            # Also remove from agent_social_accounts
            await self.db.execute("""
                DELETE FROM agent_social_accounts
                WHERE user_id = $1 AND platform = 'linkedin' AND account_id = $2
            """, user_id, account_id)
            
            logger.info(f"Removed LinkedIn account {account_id} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove LinkedIn account: {e}")
            return False