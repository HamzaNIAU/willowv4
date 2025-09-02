"""
Authentication and authorization for Veo3 MCP service.

This module handles JWT token generation/validation, Google Cloud
authentication, and MCP permission management.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from functools import wraps

import jwt
from cryptography.fernet import Fernet
from fastapi import HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from google.auth import default
from google.auth.transport.requests import Request
from google.oauth2 import service_account
import google.auth.exceptions

from .config import Config, get_config
from .models import JWTPayload, AgentPermission


# Security scheme for FastAPI
security = HTTPBearer()


class TokenManager:
    """Manages JWT tokens and encryption."""
    
    def __init__(self, config: Config):
        """
        Initialize token manager.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.fernet = self._get_or_create_fernet_key()
    
    def _get_or_create_fernet_key(self) -> Fernet:
        """Get or create Fernet encryption key."""
        key_file = ".veo3_mcp_key"
        
        if os.path.exists(key_file):
            with open(key_file, "rb") as f:
                key = f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, "wb") as f:
                f.write(key)
            os.chmod(key_file, 0o600)  # Restrict permissions
        
        return Fernet(key)
    
    def encrypt_token(self, token: str) -> str:
        """
        Encrypt a token for storage.
        
        Args:
            token: Plain text token
        
        Returns:
            Encrypted token string
        """
        return self.fernet.encrypt(token.encode()).decode()
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """
        Decrypt a stored token.
        
        Args:
            encrypted_token: Encrypted token string
        
        Returns:
            Decrypted token
        
        Raises:
            Exception: If decryption fails
        """
        return self.fernet.decrypt(encrypted_token.encode()).decode()
    
    def generate_jwt(
        self,
        user_id: str,
        project_id: str,
        agent_id: Optional[str] = None,
        permissions: Optional[List[str]] = None
    ) -> str:
        """
        Generate a JWT token.
        
        Args:
            user_id: User identifier
            project_id: Google Cloud project ID
            agent_id: Optional agent identifier
            permissions: Optional list of permissions
        
        Returns:
            JWT token string
        """
        now = datetime.utcnow()
        expiration = now + timedelta(hours=self.config.JWT_EXPIRATION_HOURS)
        
        payload = JWTPayload(
            user_id=user_id,
            project_id=project_id,
            agent_id=agent_id,
            permissions=permissions or [],
            exp=expiration,
            iat=now
        )
        
        return jwt.encode(
            payload.dict(),
            self.config.JWT_SECRET_KEY,
            algorithm=self.config.JWT_ALGORITHM
        )
    
    def decode_jwt(self, token: str) -> JWTPayload:
        """
        Decode and validate a JWT token.
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded JWT payload
        
        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                self.config.JWT_SECRET_KEY,
                algorithms=[self.config.JWT_ALGORITHM]
            )
            return JWTPayload(**payload)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}"
            )


class GoogleCloudAuth:
    """Handles Google Cloud authentication."""
    
    def __init__(self):
        """Initialize Google Cloud authentication."""
        self.credentials = None
        self.project_id = None
        self._initialize_credentials()
    
    def _initialize_credentials(self):
        """Initialize Google Cloud credentials."""
        try:
            # Try to get default credentials
            self.credentials, self.project_id = default()
            
            # Refresh if needed
            if hasattr(self.credentials, 'refresh'):
                request = Request()
                self.credentials.refresh(request)
        except google.auth.exceptions.DefaultCredentialsError:
            # Try service account from environment
            service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if service_account_path and os.path.exists(service_account_path):
                self.credentials = service_account.Credentials.from_service_account_file(
                    service_account_path
                )
                with open(service_account_path, 'r') as f:
                    sa_info = json.load(f)
                    self.project_id = sa_info.get("project_id")
            else:
                raise Exception(
                    "No Google Cloud credentials found. Please set up "
                    "Application Default Credentials or provide a service account key."
                )
    
    def get_credentials(self):
        """Get Google Cloud credentials."""
        return self.credentials
    
    def get_project_id(self) -> str:
        """Get Google Cloud project ID."""
        return self.project_id or get_config().PROJECT_ID


class MCPPermissionManager:
    """Manages MCP toggle permissions."""
    
    def __init__(self):
        """Initialize permission manager."""
        # In production, this would connect to a database
        # For now, using in-memory storage
        self.permissions: Dict[str, Dict[str, bool]] = {}
    
    async def check_permission(
        self,
        agent_id: str,
        mcp_id: str
    ) -> bool:
        """
        Check if an agent has permission for a specific MCP ID.
        
        Args:
            agent_id: Agent identifier
            mcp_id: MCP permission ID
        
        Returns:
            True if permission granted, False otherwise
        """
        agent_permissions = self.permissions.get(agent_id, {})
        return agent_permissions.get(mcp_id, False)
    
    async def grant_permission(
        self,
        agent_id: str,
        mcp_id: str
    ) -> None:
        """
        Grant permission to an agent.
        
        Args:
            agent_id: Agent identifier
            mcp_id: MCP permission ID
        """
        if agent_id not in self.permissions:
            self.permissions[agent_id] = {}
        self.permissions[agent_id][mcp_id] = True
    
    async def revoke_permission(
        self,
        agent_id: str,
        mcp_id: str
    ) -> None:
        """
        Revoke permission from an agent.
        
        Args:
            agent_id: Agent identifier
            mcp_id: MCP permission ID
        """
        if agent_id in self.permissions:
            self.permissions[agent_id][mcp_id] = False
    
    async def get_agent_permissions(
        self,
        agent_id: str
    ) -> List[str]:
        """
        Get all permissions for an agent.
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            List of MCP IDs the agent has permission for
        """
        agent_permissions = self.permissions.get(agent_id, {})
        return [
            mcp_id for mcp_id, enabled in agent_permissions.items()
            if enabled
        ]


# Global instances
token_manager = TokenManager(get_config())
gcp_auth = GoogleCloudAuth()
permission_manager = MCPPermissionManager()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> JWTPayload:
    """
    Verify JWT token from request.
    
    Args:
        credentials: HTTP authorization credentials
    
    Returns:
        Decoded JWT payload
    
    Raises:
        HTTPException: If token is invalid
    """
    token = credentials.credentials
    return token_manager.decode_jwt(token)


async def verify_agent_permission(
    mcp_id: str,
    payload: JWTPayload = Depends(verify_token)
) -> JWTPayload:
    """
    Verify agent has permission for specific MCP ID.
    
    Args:
        mcp_id: MCP permission ID to check
        payload: JWT payload from token
    
    Returns:
        JWT payload if permission granted
    
    Raises:
        HTTPException: If permission denied
    """
    if not payload.agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No agent ID in token"
        )
    
    has_permission = await permission_manager.check_permission(
        payload.agent_id,
        mcp_id
    )
    
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Agent {payload.agent_id} does not have permission for {mcp_id}"
        )
    
    return payload


def require_auth(func):
    """
    Decorator to require authentication for a function.
    
    Usage:
        @require_auth
        async def protected_function(payload: JWTPayload, ...):
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract token from kwargs or first arg
        token = kwargs.get('token') or (args[0] if args else None)
        
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        payload = token_manager.decode_jwt(token)
        
        # Inject payload into function
        return await func(payload=payload, *args[1:], **kwargs)
    
    return wrapper


def require_permission(mcp_id: str):
    """
    Decorator to require specific MCP permission.
    
    Args:
        mcp_id: MCP permission ID required
    
    Usage:
        @require_permission("veo3.model.veo-3.0-generate-preview")
        async def protected_function(payload: JWTPayload, ...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get payload from kwargs or decode from token
            payload = kwargs.get('payload')
            
            if not payload:
                token = kwargs.get('token') or (args[0] if args else None)
                if not token:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required"
                    )
                payload = token_manager.decode_jwt(token)
            
            # Check permission
            if payload.agent_id:
                has_permission = await permission_manager.check_permission(
                    payload.agent_id,
                    mcp_id
                )
                if not has_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied for {mcp_id}"
                    )
            
            return await func(payload=payload, *args[1:], **kwargs)
        
        return wrapper
    return decorator