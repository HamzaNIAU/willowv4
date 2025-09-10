"""
Unified Social Media Service
Handles all social media platform accounts in a single, consistent way
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from services.supabase import DBConnection
from utils.logger import logger
from cryptography.fernet import Fernet
import os

class UnifiedSocialMediaService:
    """Unified service for all social media platform accounts"""
    
    SUPPORTED_PLATFORMS = [
        'youtube', 'twitter', 'instagram', 'pinterest', 'linkedin',
        'tiktok', 'facebook', 'threads', 'snapchat', 'reddit', 'discord'
    ]
    
    def __init__(self, db: DBConnection):
        self.db = db
        # Get encryption key from environment
        encryption_key = os.getenv("MCP_CREDENTIAL_ENCRYPTION_KEY")
        if encryption_key:
            self.cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        else:
            logger.warning("No encryption key found - tokens will be stored unencrypted")
            self.cipher = None
    
    def _encrypt_token(self, token: str) -> str:
        """Encrypt a token for storage"""
        if self.cipher and token:
            return self.cipher.encrypt(token.encode()).decode()
        return token
    
    def _decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt a token from storage"""
        if self.cipher and encrypted_token:
            try:
                return self.cipher.decrypt(encrypted_token.encode()).decode()
            except Exception as e:
                logger.error(f"Failed to decrypt token: {e}")
                return encrypted_token
        return encrypted_token
    
    async def get_accounts(self, user_id: str, platform: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get social media accounts for a user, optionally filtered by platform"""
        client = await self.db.client
        
        query = client.table("social_media_accounts").select("*").eq(
            "user_id", user_id
        ).eq("is_active", True)
        
        if platform:
            if platform not in self.SUPPORTED_PLATFORMS:
                raise ValueError(f"Unsupported platform: {platform}")
            query = query.eq("platform", platform)
        
        result = await query.order("created_at", desc=True).execute()
        
        # Decrypt tokens before returning
        accounts = result.data or []
        for account in accounts:
            if account.get("access_token"):
                account["access_token"] = self._decrypt_token(account["access_token"])
            if account.get("refresh_token"):
                account["refresh_token"] = self._decrypt_token(account["refresh_token"])
        
        return accounts
    
    async def get_account(self, user_id: str, platform: str, account_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific social media account"""
        client = await self.db.client
        
        result = await client.table("social_media_accounts").select("*").eq(
            "user_id", user_id
        ).eq("platform", platform).eq(
            "platform_account_id", account_id
        ).single().execute()
        
        if result.data:
            account = result.data
            if account.get("access_token"):
                account["access_token"] = self._decrypt_token(account["access_token"])
            if account.get("refresh_token"):
                account["refresh_token"] = self._decrypt_token(account["refresh_token"])
            return account
        
        return None
    
    async def save_account(self, user_id: str, platform: str, account_data: Dict[str, Any]) -> str:
        """Save or update a social media account"""
        if platform not in self.SUPPORTED_PLATFORMS:
            raise ValueError(f"Unsupported platform: {platform}")
        
        client = await self.db.client
        
        # Encrypt tokens
        access_token = account_data.get("access_token")
        refresh_token = account_data.get("refresh_token")
        
        if access_token:
            access_token = self._encrypt_token(access_token)
        if refresh_token:
            refresh_token = self._encrypt_token(refresh_token)
        
        # Prepare the data for insertion
        db_data = {
            "user_id": user_id,
            "platform": platform,
            "platform_account_id": account_data["id"],
            "account_name": account_data.get("name", ""),
            "username": account_data.get("username"),
            "email": account_data.get("email"),
            "profile_image_url": account_data.get("profile_image_url") or account_data.get("profile_picture"),
            "bio": account_data.get("bio") or account_data.get("description"),
            "website_url": account_data.get("website_url"),
            "follower_count": account_data.get("follower_count", 0) or account_data.get("followers_count", 0),
            "following_count": account_data.get("following_count", 0),
            "post_count": account_data.get("post_count", 0) or account_data.get("video_count", 0) or account_data.get("pin_count", 0),
            "view_count": account_data.get("view_count", 0),
            "subscriber_count": account_data.get("subscriber_count", 0),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expires_at": account_data.get("token_expires_at"),
            "token_scopes": account_data.get("token_scopes", []),
            "is_active": True,
            "platform_data": account_data.get("platform_data", {}),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Upsert the account
        result = await client.table("social_media_accounts").upsert(
            db_data,
            on_conflict="user_id,platform,platform_account_id"
        ).execute()
        
        if result.data:
            logger.info(f"✅ Saved {platform} account {account_data['id']} for user {user_id}")
            return result.data[0]["id"]
        else:
            raise Exception(f"Failed to save {platform} account")
    
    async def update_tokens(self, user_id: str, platform: str, account_id: str, 
                          access_token: str, refresh_token: Optional[str] = None,
                          expires_at: Optional[datetime] = None) -> bool:
        """Update OAuth tokens for an account"""
        client = await self.db.client
        
        update_data = {
            "access_token": self._encrypt_token(access_token),
            "last_refresh_success": datetime.now(timezone.utc).isoformat(),
            "refresh_failure_count": 0,
            "needs_reauth": False,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        if refresh_token:
            update_data["refresh_token"] = self._encrypt_token(refresh_token)
        
        if expires_at:
            update_data["token_expires_at"] = expires_at.isoformat()
        
        result = await client.table("social_media_accounts").update(update_data).eq(
            "user_id", user_id
        ).eq("platform", platform).eq(
            "platform_account_id", account_id
        ).execute()
        
        return bool(result.data)
    
    async def mark_needs_reauth(self, user_id: str, platform: str, account_id: str, error: str) -> bool:
        """Mark an account as needing re-authentication"""
        client = await self.db.client
        
        result = await client.table("social_media_accounts").update({
            "needs_reauth": True,
            "last_refresh_error": error,
            "last_refresh_attempt": datetime.now(timezone.utc).isoformat(),
            "refresh_failure_count": client.sql(
                "refresh_failure_count + 1"
            ),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq(
            "user_id", user_id
        ).eq("platform", platform).eq(
            "platform_account_id", account_id
        ).execute()
        
        return bool(result.data)
    
    async def remove_account(self, user_id: str, platform: str, account_id: str) -> bool:
        """Remove a social media account"""
        client = await self.db.client
        
        result = await client.table("social_media_accounts").delete().eq(
            "user_id", user_id
        ).eq("platform", platform).eq(
            "platform_account_id", account_id
        ).execute()
        
        if result.data:
            logger.info(f"✅ Removed {platform} account {account_id} for user {user_id}")
            return True
        
        return False
    
    async def get_all_user_accounts(self, user_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """Get all social media accounts for a user, grouped by platform"""
        accounts = await self.get_accounts(user_id)
        
        # Group by platform
        grouped = {}
        for account in accounts:
            platform = account["platform"]
            if platform not in grouped:
                grouped[platform] = []
            grouped[platform].append(account)
        
        return grouped
    
    async def check_token_expiry(self, user_id: str, platform: str, account_id: str) -> bool:
        """Check if an account's token is expired or about to expire"""
        account = await self.get_account(user_id, platform, account_id)
        
        if not account:
            return True  # Account doesn't exist
        
        if account.get("needs_reauth"):
            return True
        
        if not account.get("token_expires_at"):
            return False  # No expiry set, assume valid
        
        # Check if token expires in next 5 minutes
        expires_at = datetime.fromisoformat(account["token_expires_at"].replace('Z', '+00:00'))
        time_until_expiry = expires_at - datetime.now(timezone.utc)
        
        return time_until_expiry < timedelta(minutes=5)
    
    async def format_for_platform(self, platform: str, accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format accounts for platform-specific API compatibility"""
        formatted = []
        
        for account in accounts:
            if platform == "youtube":
                formatted.append({
                    "id": account["platform_account_id"],
                    "name": account["account_name"],
                    "username": account.get("username"),
                    "profile_picture": account.get("profile_image_url"),
                    "profile_picture_medium": account.get("platform_data", {}).get("profile_picture_medium"),
                    "profile_picture_small": account.get("platform_data", {}).get("profile_picture_small"),
                    "subscriber_count": account.get("subscriber_count", 0),
                    "view_count": account.get("view_count", 0),
                    "video_count": account.get("post_count", 0),
                    "created_at": account.get("created_at"),
                    "updated_at": account.get("updated_at"),
                })
            elif platform == "pinterest":
                formatted.append({
                    "id": account["platform_account_id"],
                    "name": account["account_name"],
                    "username": account.get("username"),
                    "profile_picture": account.get("profile_image_url"),
                    "profile_picture_medium": account.get("profile_image_url"),
                    "profile_picture_small": account.get("profile_image_url"),
                    "subscriber_count": account.get("follower_count", 0),
                    "view_count": account.get("view_count", 0) or account.get("platform_data", {}).get("monthly_views", 0),
                    "video_count": account.get("post_count", 0) or account.get("platform_data", {}).get("pin_count", 0),
                    "created_at": account.get("created_at"),
                    "updated_at": account.get("updated_at"),
                })
            else:
                # Generic format for other platforms
                formatted.append({
                    "id": account["platform_account_id"],
                    "name": account["account_name"],
                    "username": account.get("username"),
                    "profile_picture": account.get("profile_image_url"),
                    "follower_count": account.get("follower_count", 0),
                    "following_count": account.get("following_count", 0),
                    "post_count": account.get("post_count", 0),
                    "created_at": account.get("created_at"),
                    "updated_at": account.get("updated_at"),
                })
        
        return formatted