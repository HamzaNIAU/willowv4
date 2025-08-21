"""YouTube Upload Service - Handles video uploads to YouTube"""

import os
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    build = None
    MediaFileUpload = None
    Credentials = None

from services.supabase import DBConnection
from utils.logger import logger
from .oauth import YouTubeOAuthHandler


class YouTubeUploadService:
    """Service for uploading videos to YouTube"""
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.oauth_handler = YouTubeOAuthHandler(db)
    
    async def upload_video(self, user_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Upload a video to YouTube with automatic file discovery"""
        
        channel_id = params["channel_id"]
        
        # Import file service for automatic discovery
        from services.youtube_file_service import YouTubeFileService
        file_service = YouTubeFileService(self.db)
        
        # If no video_reference_id provided, try automatic discovery
        video_reference_id = params.get("video_reference_id")
        thumbnail_reference_id = params.get("thumbnail_reference_id")
        
        if not video_reference_id:
            # Automatically find the latest pending uploads
            logger.info(f"No video reference provided, attempting automatic discovery for user {user_id}")
            uploads = await file_service.get_latest_pending_uploads(user_id)
            
            if not uploads["video"]:
                raise Exception("No video file found. Please upload a video file first.")
            
            video_reference_id = uploads["video"]["reference_id"]
            logger.info(f"Automatically found video: {uploads['video']['file_name']} ({video_reference_id})")
            
            # Also check for thumbnail if not provided (OPTIONAL - not required)
            if not thumbnail_reference_id and uploads["thumbnail"]:
                thumbnail_reference_id = uploads["thumbnail"]["reference_id"]
                logger.info(f"Automatically found thumbnail: {uploads['thumbnail']['file_name']} ({thumbnail_reference_id})")
            elif not thumbnail_reference_id:
                logger.info("No thumbnail found - uploading video without custom thumbnail")
        
        # Get valid access token
        access_token = await self.oauth_handler.get_valid_token(user_id, channel_id)
        
        # Get channel info
        client = await self.db.client
        channel_result = await client.table("youtube_channels").select("name").eq(
            "user_id", user_id
        ).eq("id", channel_id).execute()
        
        if not channel_result.data:
            raise Exception(f"Channel {channel_id} not found")
        
        channel_name = channel_result.data[0]["name"]
        
        # Get video file info from reference
        video_ref_result = await client.table("video_file_references").select("*").eq(
            "id", video_reference_id
        ).eq("user_id", user_id).execute()
        
        if not video_ref_result.data:
            raise Exception(f"Video reference {video_reference_id} not found")
        
        video_info = video_ref_result.data[0]
        
        # Create upload record
        upload_id = str(uuid.uuid4())
        upload_data = {
            "id": upload_id,
            "user_id": user_id,
            "channel_id": channel_id,
            "title": params["title"],
            "description": params.get("description", ""),
            "tags": params.get("tags", []),
            "category_id": params.get("category_id", "22"),
            "privacy_status": params.get("privacy_status", "public"),
            "made_for_kids": params.get("made_for_kids", False),
            "file_name": video_info["file_name"],
            "file_size": video_info["file_size"],
            "upload_status": "pending",
            "video_reference_id": video_reference_id,
            "thumbnail_reference_id": thumbnail_reference_id,
            "scheduled_for": params.get("scheduled_for"),
            "notify_subscribers": params.get("notify_subscribers", True),
        }
        
        result = await client.table("youtube_uploads").insert(upload_data).execute()
        
        if not result.data:
            raise Exception("Failed to create upload record")
        
        # Mark references as used
        references_to_mark = [video_reference_id]
        if thumbnail_reference_id:
            references_to_mark.append(thumbnail_reference_id)
        
        await file_service.mark_references_as_used(references_to_mark)
        
        # Note: Actual video upload implementation would go here
        # This would involve:
        # 1. Getting the file data using file_service.get_file_data()
        # 2. Using YouTube API to upload the video
        # 3. Uploading thumbnail if provided
        # 4. Updating the upload record with progress
        # 5. Handling resumable uploads for large files
        
        # Log the upload details
        logger.info(f"Upload initiated for video '{params['title']}' to channel {channel_id}")
        if thumbnail_reference_id:
            logger.info(f"Video and thumbnail automatically paired for upload")
        else:
            logger.info(f"Video will be uploaded without custom thumbnail (YouTube will auto-generate)")
        
        return {
            "upload_id": upload_id,
            "channel_name": channel_name,
            "status": "pending",
            "message": f"Upload queued for '{params['title']}'",
            "video_reference": video_reference_id,
            "thumbnail_reference": thumbnail_reference_id,
            "automatic_discovery": not params.get("video_reference_id")
        }
    
    async def get_upload_status(self, user_id: str, upload_id: str) -> Dict[str, Any]:
        """Get the status of an upload"""
        client = await self.db.client
        
        result = await client.table("youtube_uploads").select("*").eq(
            "user_id", user_id
        ).eq("id", upload_id).execute()
        
        if not result.data:
            raise Exception(f"Upload {upload_id} not found")
        
        upload = result.data[0]
        
        return {
            "upload_id": upload["id"],
            "title": upload["title"],
            "status": upload["upload_status"],
            "progress": upload.get("upload_progress", 0),
            "video_id": upload.get("video_id"),
            "message": upload.get("status_message", ""),
            "created_at": upload.get("created_at"),
            "completed_at": upload.get("completed_at"),
        }