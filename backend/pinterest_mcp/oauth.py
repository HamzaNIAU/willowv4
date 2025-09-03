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
        """Save Pinterest account to database - Following YouTube channel save pattern exactly"""
        client = await self.db.client
        
        # Encrypt tokens
        encrypted_access = self.encrypt_token(access_token)
        encrypted_refresh = self.encrypt_token(refresh_token) if refresh_token else None
        
        # Prepare account data - following YouTube pattern exactly
        account_data = {
            "id": account_info["id"],
            "user_id": user_id,
            "username": account_info["username"],
            "name": account_info["name"],
            "profile_image_url": account_info.get("profile_image_url"),
            "website_url": account_info.get("website_url"),
            "about": account_info.get("about"),
            "account_type": account_info.get("account_type", "PERSONAL"),
            "pin_count": account_info.get("pin_count", 0),
            "board_count": account_info.get("board_count", 0),
            "follower_count": account_info.get("follower_count", 0),
            "following_count": account_info.get("following_count", 0),
            "access_token": encrypted_access,
            "refresh_token": encrypted_refresh,
            "token_expires_at": expires_at.isoformat(),
            "token_scopes": self.SCOPES,
            "is_active": True,
        }
        
        # Upsert account (update if exists, insert if not) - following YouTube pattern
        result = await client.table("pinterest_accounts").upsert(
            account_data,
            on_conflict="id,user_id"
        ).execute()
        
        if result.data:
            logger.info(f"Saved Pinterest account {account_info['id']} for user {user_id}")
            
            # Create unified social accounts entry - following YouTube pattern
            await self._create_unified_social_account(user_id, account_info)
            
            return account_info["id"]
        else:
            raise Exception("Failed to save Pinterest account")
    
    async def _create_unified_social_account(self, user_id: str, account_info: Dict[str, Any]):
        """Create unified social account entry - Following YouTube pattern"""
        client = await self.db.client
        
        # Get all user's agents (including suna-default)
        agents_result = await client.rpc("get_user_agent_ids", {"input_user_id": user_id}).execute()
        agent_ids = [agent["agent_id"] for agent in agents_result.data] if agents_result.data else []
        
        # Add suna-default if not present
        if "suna-default" not in agent_ids:
            agent_ids.append("suna-default")
        
        # Create unified social account entries for all agents
        for agent_id in agent_ids:
            unified_account_data = {
                "agent_id": agent_id,
                "user_id": user_id,
                "platform": "pinterest",
                "account_id": account_info["id"],
                "account_name": account_info["name"],
                "username": account_info.get("username"),
                "profile_picture": account_info.get("profile_image_url"),
                "subscriber_count": account_info.get("follower_count", 0),
                "view_count": 0,  # Pinterest doesn't have view count
                "video_count": account_info.get("pin_count", 0),  # Use pin_count as video_count equivalent
                "enabled": True,  # Default to enabled
            }
            
            await client.table("agent_social_accounts").upsert(
                unified_account_data,
                on_conflict="agent_id,user_id,platform,account_id"
            ).execute()
            
            logger.info(f"Created unified social account entry for Pinterest {account_info['id']} and agent {agent_id}")