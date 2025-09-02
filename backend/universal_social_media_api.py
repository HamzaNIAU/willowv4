"""Universal Social Media API
Handles uploads and account management for all social media platforms
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any, Optional, List
from datetime import datetime

from services.supabase import DBConnection
from services.universal_social_media_service import (
    UniversalSocialMediaService, 
    SocialMediaPlatform, 
    UploadStatus
)
from utils.auth_utils import get_current_user_id_from_jwt
from utils.logger import logger

router = APIRouter(prefix="/social-media", tags=["Universal Social Media"])

# Database connection
db: Optional[DBConnection] = None

def initialize(database: DBConnection):
    """Initialize Universal Social Media API with database connection"""
    global db
    db = database


@router.get("/platforms")
async def get_supported_platforms() -> Dict[str, Any]:
    """Get list of supported social media platforms"""
    return {
        "success": True,
        "platforms": [
            {
                "id": "youtube",
                "name": "YouTube",
                "description": "Video sharing platform by Google",
                "supports_video": True,
                "supports_image": False,
                "supports_text": True,
                "max_file_size_mb": 128000,  # 128GB
                "supported_formats": ["mp4", "mov", "avi", "wmv", "flv", "webm"]
            },
            {
                "id": "tiktok", 
                "name": "TikTok",
                "description": "Short-form video platform",
                "supports_video": True,
                "supports_image": True,
                "supports_text": True,
                "max_file_size_mb": 2000,  # 2GB
                "supported_formats": ["mp4", "mov", "avi"]
            },
            {
                "id": "instagram",
                "name": "Instagram", 
                "description": "Photo and video sharing",
                "supports_video": True,
                "supports_image": True,
                "supports_text": True,
                "max_file_size_mb": 4000,  # 4GB for video
                "supported_formats": ["mp4", "mov", "jpg", "png"]
            },
            {
                "id": "twitter",
                "name": "Twitter/X",
                "description": "Microblogging platform",
                "supports_video": True,
                "supports_image": True,
                "supports_text": True,
                "max_file_size_mb": 512,  # 512MB
                "supported_formats": ["mp4", "mov", "jpg", "png", "gif"]
            },
            {
                "id": "linkedin",
                "name": "LinkedIn",
                "description": "Professional networking platform",
                "supports_video": True,
                "supports_image": True,
                "supports_text": True,
                "max_file_size_mb": 5000,  # 5GB
                "supported_formats": ["mp4", "mov", "jpg", "png"]
            }
        ]
    }


@router.post("/upload")
async def initiate_upload(
    upload_data: Dict[str, Any],
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Universal upload endpoint for any social media platform"""
    try:
        service = UniversalSocialMediaService(db)
        
        # Validate required fields
        required_fields = ["platform", "account_id", "title", "file_name", "file_size"]
        for field in required_fields:
            if field not in upload_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Validate platform
        try:
            platform = SocialMediaPlatform(upload_data["platform"].lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unsupported platform: {upload_data['platform']}")
        
        # Create upload record
        upload_id = await service.create_upload_record(
            user_id=user_id,
            platform=platform,
            account_id=upload_data["account_id"],
            upload_params=upload_data
        )
        
        # Start upload processing based on platform
        if platform == SocialMediaPlatform.YOUTUBE:
            # Import YouTube-specific handler
            from youtube_mcp.upload import YouTubeUploadService
            youtube_service = YouTubeUploadService(db)
            # Convert to YouTube format and delegate
            youtube_params = _convert_to_youtube_params(upload_data)
            result = await youtube_service.upload_video(user_id, youtube_params)
            
            # Update universal record with YouTube result
            await service.update_upload_progress(
                upload_id=upload_id,
                status=UploadStatus.UPLOADING,
                status_message="Upload started via YouTube API",
                platform_data={"youtube_upload_id": result.get("upload_id")}
            )
            
        # TODO: Add other platform handlers
        elif platform == SocialMediaPlatform.TIKTOK:
            # await _handle_tiktok_upload(service, upload_id, user_id, upload_data)
            raise HTTPException(status_code=501, detail="TikTok upload coming soon!")
        elif platform == SocialMediaPlatform.INSTAGRAM:
            # await _handle_instagram_upload(service, upload_id, user_id, upload_data)
            raise HTTPException(status_code=501, detail="Instagram upload coming soon!")
        else:
            raise HTTPException(status_code=501, detail=f"{platform.value} upload not yet implemented")
        
        return {
            "success": True,
            "upload_id": upload_id,
            "platform": platform.value,
            "status": "uploading",
            "message": f"Upload started for {platform.value}",
            "upload_started": True,
            "account": {
                "id": upload_data["account_id"],
                "name": upload_data.get("account_name", "Unknown Account")
            }
        }
        
    except Exception as e:
        logger.error(f"Universal upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upload-status/{upload_id}")
async def get_upload_status(
    upload_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get upload status for any platform"""
    try:
        service = UniversalSocialMediaService(db)
        status = await service.get_upload_status(user_id, upload_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Upload not found")
            
        return status
        
    except Exception as e:
        logger.error(f"Failed to get upload status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/uploads")
async def get_user_uploads(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get user's uploads across all platforms"""
    try:
        service = UniversalSocialMediaService(db)
        
        platform_enum = None
        if platform:
            try:
                platform_enum = SocialMediaPlatform(platform.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid platform: {platform}")
        
        status_enum = None
        if status:
            try:
                status_enum = UploadStatus(status.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        
        uploads = await service.get_recent_uploads(
            user_id=user_id,
            platform=platform_enum,
            limit=min(limit, 100),  # Cap at 100
            status=status_enum
        )
        
        return {
            "success": True,
            "uploads": uploads,
            "count": len(uploads)
        }
        
    except Exception as e:
        logger.error(f"Failed to get uploads: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts")
async def get_user_accounts(
    platform: Optional[str] = None,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get user's connected social media accounts"""
    try:
        service = UniversalSocialMediaService(db)
        
        platform_enum = None
        if platform:
            try:
                platform_enum = SocialMediaPlatform(platform.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid platform: {platform}")
        
        accounts = await service.get_user_accounts(
            user_id=user_id,
            platform=platform_enum,
            active_only=True
        )
        
        # Group by platform
        grouped_accounts = {}
        for account in accounts:
            platform_key = account["platform"]
            if platform_key not in grouped_accounts:
                grouped_accounts[platform_key] = []
            grouped_accounts[platform_key].append(account)
        
        return {
            "success": True,
            "accounts_by_platform": grouped_accounts,
            "total_accounts": len(accounts)
        }
        
    except Exception as e:
        logger.error(f"Failed to get accounts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _convert_to_youtube_params(universal_params: Dict[str, Any]) -> Dict[str, Any]:
    """Convert universal upload params to YouTube-specific format"""
    return {
        "channel_id": universal_params["account_id"],
        "title": universal_params["title"],
        "description": universal_params.get("description", ""),
        "tags": universal_params.get("tags", []),
        "category_id": universal_params.get("category_id", "22"),
        "privacy_status": universal_params.get("privacy_status", "public"),
        "made_for_kids": universal_params.get("platform_settings", {}).get("made_for_kids", False),
        "video_reference_id": universal_params.get("video_reference_id"),
        "thumbnail_reference_id": universal_params.get("thumbnail_reference_id"),
        "scheduled_for": universal_params.get("scheduled_for"),
        "notify_subscribers": universal_params.get("notify_followers", True),
        "auto_discover": universal_params.get("auto_discover", True)
    }


# TODO: Add platform-specific upload handlers
async def _handle_tiktok_upload(service, upload_id, user_id, upload_data):
    """Handle TikTok-specific upload logic"""
    # Implementation for TikTok API integration
    pass

async def _handle_instagram_upload(service, upload_id, user_id, upload_data):
    """Handle Instagram-specific upload logic"""
    # Implementation for Instagram Graph API integration
    pass