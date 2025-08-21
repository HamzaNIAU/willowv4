"""YouTube OAuth2 with PKCE Enhancement - Enterprise-grade authentication"""

import os
import json
import secrets
import hashlib
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlencode
import asyncio
from asyncio import Lock

import aiohttp
from utils.logger import logger
from services.supabase import DBConnection


class YouTubeOAuthEnhanced:
    """Enhanced OAuth2 handler with PKCE for bank-grade security"""
    
    OAUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    
    # Comprehensive YouTube OAuth scopes with explanations
    SCOPES = [
        # Core Functionality
        "https://www.googleapis.com/auth/youtube.upload",           # Upload videos
        "https://www.googleapis.com/auth/youtube",                  # Full YouTube access
        "https://www.googleapis.com/auth/youtube.readonly",         # Read channel data
        "https://www.googleapis.com/auth/youtube.force-ssl",        # SSL enforcement
        
        # Analytics & Insights
        "https://www.googleapis.com/auth/yt-analytics.readonly",    # View analytics
        "https://www.googleapis.com/auth/yt-analytics-monetary.readonly", # Revenue data
        
        # User Information
        "https://www.googleapis.com/auth/userinfo.email",          # Email address
        "https://www.googleapis.com/auth/userinfo.profile",         # Profile info
    ]
    
    # Optional scopes for partner features (add if user has YouTube Partner access)
    PARTNER_SCOPES = [
        "https://www.googleapis.com/auth/youtubepartner",           # Partner features
        "https://www.googleapis.com/auth/youtube.channel-memberships.creator", # Memberships
        "https://www.googleapis.com/auth/youtubepartner-channel-audit",        # Audit
        "https://www.googleapis.com/auth/youtubepartner-content-owner-readonly", # CMS
    ]
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.client_id = os.getenv("YOUTUBE_CLIENT_ID")
        self.client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("YOUTUBE_REDIRECT_URI", "http://localhost:8000/api/youtube/auth/callback")
        
        # PKCE settings
        self.pkce_enabled = os.getenv("YOUTUBE_PKCE_ENABLED", "true").lower() == "true"
        
        # Token refresh settings
        self.refresh_buffer_seconds = int(os.getenv("YOUTUBE_TOKEN_REFRESH_BUFFER_SECONDS", "300"))
        self.refresh_max_retries = int(os.getenv("YOUTUBE_TOKEN_REFRESH_MAX_RETRIES", "3"))
        
        # Refresh queue to prevent concurrent refreshes
        self._refresh_locks: Dict[str, Lock] = {}
        
        if not self.client_id or not self.client_secret:
            raise ValueError("YouTube OAuth credentials not configured")
        
        logger.info(f"YouTubeOAuthEnhanced initialized with PKCE: {self.pkce_enabled}")
    
    def generate_pkce_params(self) -> Tuple[str, str]:
        """
        Generate PKCE code verifier and challenge for enhanced security
        
        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        # Generate cryptographically secure random code verifier
        # Must be 43-128 characters, using unreserved characters
        code_verifier = base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode('utf-8').rstrip('=')
        
        # Generate code challenge using S256 method (SHA256)
        challenge_bytes = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode('utf-8').rstrip('=')
        
        return code_verifier, code_challenge
    
    def generate_state_token(self, user_id: str) -> str:
        """
        Generate secure state token for CSRF protection
        
        Args:
            user_id: User ID to embed in state
            
        Returns:
            Secure state token
        """
        # Generate random component
        random_component = secrets.token_urlsafe(32)
        
        # Create state with user ID and random component
        state_data = {
            "user_id": user_id,
            "random": random_component,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Encode as base64
        state_json = json.dumps(state_data)
        state_token = base64.urlsafe_b64encode(state_json.encode()).decode()
        
        return state_token
    
    def verify_state_token(self, state_token: str) -> Dict[str, Any]:
        """
        Verify and decode state token
        
        Args:
            state_token: State token to verify
            
        Returns:
            Decoded state data
            
        Raises:
            ValueError: If state token is invalid or expired
        """
        try:
            # Decode from base64
            state_json = base64.urlsafe_b64decode(state_token.encode()).decode()
            state_data = json.loads(state_json)
            
            # Verify timestamp (max 10 minutes old)
            timestamp = datetime.fromisoformat(state_data["timestamp"])
            now = datetime.now(timezone.utc)
            
            if (now - timestamp).total_seconds() > 600:
                raise ValueError("State token expired")
            
            return state_data
            
        except Exception as e:
            raise ValueError(f"Invalid state token: {e}")
    
    async def generate_auth_url(self, user_id: str, include_partner_scopes: bool = False) -> Dict[str, str]:
        """
        Generate OAuth authorization URL with PKCE parameters
        
        Args:
            user_id: User ID for state token
            include_partner_scopes: Whether to include YouTube Partner scopes
            
        Returns:
            Dict with auth_url, state, and code_verifier (if PKCE enabled)
        """
        # Generate state token for CSRF protection
        state = self.generate_state_token(user_id)
        
        # Determine scopes
        scopes = self.SCOPES.copy()
        if include_partner_scopes:
            scopes.extend(self.PARTNER_SCOPES)
        
        # Base OAuth parameters
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",     # Get refresh token
            "prompt": "consent",           # Force consent screen
            "include_granted_scopes": "true",  # Include previously granted scopes
            "state": state,
        }
        
        result = {
            "auth_url": f"{self.OAUTH_URL}?{urlencode(params)}",
            "state": state
        }
        
        # Add PKCE parameters if enabled
        if self.pkce_enabled:
            code_verifier, code_challenge = self.generate_pkce_params()
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
            result["auth_url"] = f"{self.OAUTH_URL}?{urlencode(params)}"
            result["code_verifier"] = code_verifier
            
            # Store code verifier temporarily (you might want to use Redis for this)
            await self._store_pkce_verifier(user_id, state, code_verifier)
        
        logger.info(f"Generated auth URL for user {user_id} with PKCE: {self.pkce_enabled}")
        
        return result
    
    async def exchange_code_for_tokens(
        self, 
        code: str, 
        state: str,
        code_verifier: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens with PKCE verification
        
        Args:
            code: Authorization code from OAuth callback
            state: State token from OAuth callback
            code_verifier: PKCE code verifier (required if PKCE enabled)
            
        Returns:
            Dict with tokens and metadata
        """
        # Verify state token
        state_data = self.verify_state_token(state)
        user_id = state_data["user_id"]
        
        # If PKCE is enabled and no verifier provided, retrieve it
        if self.pkce_enabled and not code_verifier:
            code_verifier = await self._retrieve_pkce_verifier(user_id, state)
            if not code_verifier:
                raise ValueError("PKCE code verifier not found")
        
        async with aiohttp.ClientSession() as session:
            data = {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            }
            
            # Add PKCE verifier if enabled
            if self.pkce_enabled and code_verifier:
                data["code_verifier"] = code_verifier
            
            async with session.post(self.TOKEN_URL, data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Token exchange failed: {error_text}")
                    raise Exception(f"Failed to exchange code for tokens: {error_text}")
                
                token_data = await response.json()
                
                # Calculate token expiry with buffer
                expires_in = token_data.get("expires_in", 3600)
                expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                
                # Parse granted scopes
                scopes = token_data.get("scope", "").split() if token_data.get("scope") else []
                
                # Determine capabilities from scopes
                capabilities = self.get_capabilities_from_scopes(scopes)
                
                result = {
                    "access_token": token_data["access_token"],
                    "refresh_token": token_data.get("refresh_token"),
                    "token_type": token_data.get("token_type", "Bearer"),
                    "expiry": expiry,
                    "scopes": scopes,
                    "capabilities": capabilities,
                    "user_id": user_id
                }
                
                logger.info(f"Successfully exchanged code for tokens for user {user_id}")
                
                return result
    
    async def refresh_access_token_with_retry(
        self, 
        refresh_token: str,
        user_id: str,
        channel_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Refresh access token with intelligent retry logic and queue management
        
        Args:
            refresh_token: Refresh token
            user_id: User ID
            channel_id: Optional channel ID for queue management
            
        Returns:
            Dict with new access token and expiry
        """
        # Create unique key for refresh queue
        queue_key = f"{user_id}:{channel_id}" if channel_id else user_id
        
        # Get or create lock for this refresh operation
        if queue_key not in self._refresh_locks:
            self._refresh_locks[queue_key] = Lock()
        
        lock = self._refresh_locks[queue_key]
        
        # Acquire lock to prevent concurrent refreshes
        async with lock:
            last_error = None
            
            for attempt in range(self.refresh_max_retries):
                try:
                    async with aiohttp.ClientSession() as session:
                        data = {
                            "refresh_token": refresh_token,
                            "client_id": self.client_id,
                            "client_secret": self.client_secret,
                            "grant_type": "refresh_token",
                        }
                        
                        async with session.post(self.TOKEN_URL, data=data) as response:
                            if response.status != 200:
                                error_text = await response.text()
                                raise Exception(f"Token refresh failed: {error_text}")
                            
                            token_data = await response.json()
                            
                            # Calculate expiry with buffer
                            expires_in = token_data.get("expires_in", 3600)
                            expiry = datetime.now(timezone.utc) + timedelta(
                                seconds=expires_in - self.refresh_buffer_seconds
                            )
                            
                            result = {
                                "access_token": token_data["access_token"],
                                "expiry": expiry,
                                "token_type": token_data.get("token_type", "Bearer")
                            }
                            
                            logger.info(f"Successfully refreshed token for {queue_key}")
                            
                            return result
                            
                except Exception as e:
                    last_error = e
                    logger.warning(f"Token refresh attempt {attempt + 1} failed: {e}")
                    
                    if attempt < self.refresh_max_retries - 1:
                        # Exponential backoff: 2^attempt seconds
                        await asyncio.sleep(2 ** attempt)
            
            # All retries failed
            logger.error(f"Token refresh failed after {self.refresh_max_retries} attempts: {last_error}")
            raise Exception(f"Failed to refresh token after {self.refresh_max_retries} attempts: {last_error}")
    
    def get_capabilities_from_scopes(self, scopes: list) -> Dict[str, bool]:
        """
        Map OAuth scopes to capabilities for UI feature flags
        
        Args:
            scopes: List of granted OAuth scopes
            
        Returns:
            Dict of capability flags
        """
        scope_set = set(scopes)
        
        return {
            "upload": "https://www.googleapis.com/auth/youtube.upload" in scope_set,
            "analytics": "https://www.googleapis.com/auth/yt-analytics.readonly" in scope_set,
            "monetization": "https://www.googleapis.com/auth/yt-analytics-monetary.readonly" in scope_set,
            "streaming": "https://www.googleapis.com/auth/youtube" in scope_set,
            "management": "https://www.googleapis.com/auth/youtubepartner" in scope_set,
            "memberships": "https://www.googleapis.com/auth/youtube.channel-memberships.creator" in scope_set,
            "audit": "https://www.googleapis.com/auth/youtubepartner-channel-audit" in scope_set,
        }
    
    async def _store_pkce_verifier(self, user_id: str, state: str, code_verifier: str) -> None:
        """
        Store PKCE code verifier temporarily
        
        In production, use Redis or similar for this
        """
        client = await self.db.client
        
        # Store in a temporary table or cache
        # For now, we'll use the session storage approach
        await client.table("youtube_oauth_sessions").insert({
            "user_id": user_id,
            "state": state,
            "code_verifier": code_verifier,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        }).execute()
    
    async def _retrieve_pkce_verifier(self, user_id: str, state: str) -> Optional[str]:
        """
        Retrieve PKCE code verifier
        
        In production, use Redis or similar for this
        """
        client = await self.db.client
        
        result = await client.table("youtube_oauth_sessions").select("code_verifier").eq(
            "user_id", user_id
        ).eq("state", state).execute()
        
        if result.data and len(result.data) > 0:
            # Delete after retrieval (one-time use)
            await client.table("youtube_oauth_sessions").delete().eq(
                "user_id", user_id
            ).eq("state", state).execute()
            
            return result.data[0]["code_verifier"]
        
        return None
    
    async def validate_and_refresh_token(
        self,
        access_token: str,
        refresh_token: str,
        expiry: datetime,
        user_id: str,
        channel_id: Optional[str] = None
    ) -> Tuple[str, datetime]:
        """
        Validate token and refresh if needed with intelligent buffer
        
        Args:
            access_token: Current access token
            refresh_token: Refresh token
            expiry: Token expiry time
            user_id: User ID
            channel_id: Optional channel ID
            
        Returns:
            Tuple of (valid_access_token, new_expiry)
        """
        now = datetime.now(timezone.utc)
        buffer_time = timedelta(seconds=self.refresh_buffer_seconds)
        
        # Check if token needs refresh
        if expiry - now > buffer_time:
            # Token is still valid
            return access_token, expiry
        
        # Token needs refresh
        logger.info(f"Token expiring soon for {user_id}, refreshing proactively")
        
        result = await self.refresh_access_token_with_retry(
            refresh_token, user_id, channel_id
        )
        
        return result["access_token"], result["expiry"]