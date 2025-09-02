"""Universal Social Media Upload Service
Handles uploads to any social media platform with unified progress tracking
"""

import uuid
import asyncio
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone
from enum import Enum

from utils.logger import logger


class SocialMediaPlatform(Enum):
    """Supported social media platforms"""
    YOUTUBE = "youtube"
    TIKTOK = "tiktok" 
    INSTAGRAM = "instagram"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    FACEBOOK = "facebook"
    TWITCH = "twitch"
    PINTEREST = "pinterest"


class UploadStatus(Enum):
    """Universal upload status types"""
    PENDING = "pending"
    UPLOADING = "uploading" 
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SCHEDULED = "scheduled"


class UniversalSocialMediaService:
    """Universal service for social media uploads across all platforms"""
    
    def __init__(self, db):
        self.db = db
        
    async def create_upload_record(
        self, 
        user_id: str,
        platform: SocialMediaPlatform,
        account_id: str,
        upload_params: Dict[str, Any]
    ) -> str:
        """Create a universal upload record for any platform"""
        
        upload_id = str(uuid.uuid4())
        client = await self.db.client
        
        # Extract universal fields
        upload_data = {
            "id": upload_id,
            "user_id": user_id,
            "platform": platform.value,
            "platform_account_id": account_id,
            "platform_account_name": upload_params.get("account_name"),
            
            # Content metadata
            "title": upload_params["title"],
            "description": upload_params.get("description", ""),
            "tags": upload_params.get("tags", []),
            "category_id": upload_params.get("category_id"),
            "privacy_status": upload_params.get("privacy_status", "public"),
            
            # File information
            "video_reference_id": upload_params.get("video_reference_id"),
            "thumbnail_reference_id": upload_params.get("thumbnail_reference_id"),
            "file_name": upload_params["file_name"],
            "file_size": upload_params["file_size"],
            "mime_type": upload_params.get("mime_type"),
            
            # Progress tracking
            "upload_status": UploadStatus.PENDING.value,
            "upload_progress": 0,
            "bytes_uploaded": 0,
            "total_bytes": upload_params["file_size"],
            "status_message": "Upload queued",
            
            # Platform-specific data
            "platform_metadata": upload_params.get("platform_metadata", {}),
            "platform_settings": upload_params.get("platform_settings", {}),
            
            # Scheduling
            "scheduled_for": upload_params.get("scheduled_for"),
            "notify_followers": upload_params.get("notify_followers", True),
        }
        
        result = await client.table("social_media_uploads").insert(upload_data).execute()
        
        if not result.data:
            raise Exception("Failed to create upload record")
            
        logger.info(f"Created universal upload record {upload_id} for {platform.value}")
        return upload_id
    
    async def update_upload_progress(
        self,
        upload_id: str,
        progress: float = None,
        bytes_uploaded: int = None,
        status: UploadStatus = None,
        status_message: str = None,
        platform_data: Dict[str, Any] = None
    ) -> bool:
        """Update upload progress for any platform"""
        
        client = await self.db.client
        update_data = {}
        
        if progress is not None:
            update_data["upload_progress"] = min(100, max(0, progress))
            
        if bytes_uploaded is not None:
            update_data["bytes_uploaded"] = bytes_uploaded
            
        if status is not None:
            update_data["upload_status"] = status.value
            if status == UploadStatus.UPLOADING and "started_at" not in update_data:
                update_data["started_at"] = datetime.now(timezone.utc).isoformat()
            elif status == UploadStatus.COMPLETED:
                update_data["completed_at"] = datetime.now(timezone.utc).isoformat()
                update_data["upload_progress"] = 100
                
        if status_message:
            update_data["status_message"] = status_message
            
        if platform_data:
            # Merge platform data
            existing_result = await client.table("social_media_uploads").select("platform_metadata").eq("id", upload_id).execute()
            if existing_result.data:
                existing_metadata = existing_result.data[0].get("platform_metadata", {})
                existing_metadata.update(platform_data)
                update_data["platform_metadata"] = existing_metadata
            else:
                update_data["platform_metadata"] = platform_data
        
        if not update_data:
            return True
            
        result = await client.table("social_media_uploads").update(update_data).eq("id", upload_id).execute()
        return bool(result.data)
    
    async def mark_upload_completed(
        self,
        upload_id: str,
        platform_post_id: str,
        platform_url: str,
        embed_url: str = None,
        analytics_data: Dict[str, Any] = None
    ) -> bool:
        """Mark upload as completed with platform response data"""
        
        client = await self.db.client
        update_data = {
            "upload_status": UploadStatus.COMPLETED.value,
            "upload_progress": 100,
            "platform_post_id": platform_post_id,
            "platform_url": platform_url,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "status_message": "Upload completed successfully"
        }
        
        if embed_url:
            update_data["embed_url"] = embed_url
            
        if analytics_data:
            update_data.update({
                "view_count": analytics_data.get("view_count", 0),
                "like_count": analytics_data.get("like_count", 0),
                "share_count": analytics_data.get("share_count", 0),
                "comment_count": analytics_data.get("comment_count", 0)
            })
        
        result = await client.table("social_media_uploads").update(update_data).eq("id", upload_id).execute()
        return bool(result.data)
    
    async def get_upload_status(self, user_id: str, upload_id: str) -> Optional[Dict[str, Any]]:
        """Get upload status for any platform"""
        
        client = await self.db.client
        result = await client.table("social_media_uploads").select("*").eq(
            "user_id", user_id
        ).eq("id", upload_id).execute()
        
        if not result.data:
            return None
            
        upload = result.data[0]
        
        # Get account info
        account_result = await client.table("social_media_accounts").select("*").eq(
            "user_id", user_id
        ).eq("platform", upload["platform"]).eq(
            "platform_account_id", upload["platform_account_id"]
        ).execute()
        
        account_info = {}
        if account_result.data:
            account = account_result.data[0]
            account_info = {
                "id": account["platform_account_id"],
                "name": account["display_name"],
                "username": account.get("username"),
                "profile_picture": account.get("profile_picture"),
                "follower_count": account.get("follower_count", 0),
                "is_verified": account.get("is_verified", False)
            }
        
        return {
            "success": True,
            "upload_id": upload["id"],
            "platform": upload["platform"],
            "status": upload["upload_status"],
            "progress": upload.get("upload_progress", 0),
            "bytes_uploaded": upload.get("bytes_uploaded", 0),
            "total_bytes": upload.get("total_bytes", upload.get("file_size", 0)),
            "status_message": upload.get("status_message", ""),
            
            # Account info
            "account": account_info,
            
            # Content info
            "content": {
                "title": upload["title"],
                "description": upload.get("description"),
                "file_name": upload["file_name"],
                "file_size": upload["file_size"],
                "privacy_status": upload.get("privacy_status"),
                "tags": upload.get("tags", [])
            },
            
            # Platform response (when completed)
            "platform_data": {
                "post_id": upload.get("platform_post_id"),
                "url": upload.get("platform_url"),
                "embed_url": upload.get("embed_url"),
                "metadata": upload.get("platform_metadata", {})
            },
            
            # Analytics
            "analytics": {
                "view_count": upload.get("view_count", 0),
                "like_count": upload.get("like_count", 0),
                "share_count": upload.get("share_count", 0),
                "comment_count": upload.get("comment_count", 0)
            },
            
            # Timestamps
            "created_at": upload.get("created_at"),
            "started_at": upload.get("started_at"),
            "completed_at": upload.get("completed_at")
        }
    
    async def get_recent_uploads(
        self,
        user_id: str,
        platform: SocialMediaPlatform = None,
        limit: int = 10,
        status: UploadStatus = None
    ) -> List[Dict[str, Any]]:
        """Get recent uploads for user, optionally filtered by platform/status"""
        
        client = await self.db.client
        query = client.table("social_media_uploads").select("*").eq("user_id", user_id)
        
        if platform:
            query = query.eq("platform", platform.value)
            
        if status:
            query = query.eq("upload_status", status.value)
            
        result = await query.order("created_at", desc=True).limit(limit).execute()
        
        return result.data or []
    
    async def create_social_media_account(
        self,
        user_id: str,
        platform: SocialMediaPlatform,
        account_data: Dict[str, Any]
    ) -> str:
        """Create or update a social media account record"""
        
        client = await self.db.client
        account_id = str(uuid.uuid4())
        
        account_record = {
            "id": account_id,
            "user_id": user_id,
            "platform": platform.value,
            "platform_account_id": account_data["platform_account_id"],
            "username": account_data.get("username"),
            "display_name": account_data["display_name"],
            "profile_picture": account_data.get("profile_picture"),
            "profile_banner": account_data.get("profile_banner"),
            "description": account_data.get("description"),
            "website_url": account_data.get("website_url"),
            "follower_count": account_data.get("follower_count", 0),
            "following_count": account_data.get("following_count", 0),
            "post_count": account_data.get("post_count", 0),
            "total_views": account_data.get("total_views", 0),
            "access_token": account_data.get("access_token"),  # Should be encrypted
            "refresh_token": account_data.get("refresh_token"),  # Should be encrypted
            "token_expires_at": account_data.get("token_expires_at"),
            "token_scopes": account_data.get("token_scopes", []),
            "platform_metadata": account_data.get("platform_metadata", {}),
            "is_verified": account_data.get("is_verified", False)
        }
        
        # Use upsert to handle existing accounts
        result = await client.table("social_media_accounts").upsert(
            account_record,
            on_conflict="platform,platform_account_id,user_id"
        ).execute()
        
        logger.info(f"Created/updated {platform.value} account for user {user_id}")
        return account_id
    
    async def get_user_accounts(
        self,
        user_id: str,
        platform: SocialMediaPlatform = None,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Get all social media accounts for a user"""
        
        client = await self.db.client
        query = client.table("social_media_accounts").select("*").eq("user_id", user_id)
        
        if platform:
            query = query.eq("platform", platform.value)
            
        if active_only:
            query = query.eq("is_active", True)
            
        result = await query.order("created_at", desc=False).execute()
        return result.data or []


# Platform-specific upload handlers can inherit from this base
class BasePlatformUploader:
    """Base class for platform-specific upload handlers"""
    
    def __init__(self, universal_service: UniversalSocialMediaService):
        self.universal_service = universal_service
        self.platform = None  # Set in subclass
    
    async def upload(self, user_id: str, account_id: str, upload_params: Dict[str, Any]) -> str:
        """Override in subclass for platform-specific upload logic"""
        raise NotImplementedError("Subclasses must implement upload method")
    
    async def get_upload_url(self, post_id: str) -> str:
        """Override in subclass to generate platform-specific URLs"""
        raise NotImplementedError("Subclasses must implement get_upload_url method")
    
    async def get_embed_url(self, post_id: str) -> str:
        """Override in subclass to generate embeddable URLs"""
        return None  # Default: no embed URL