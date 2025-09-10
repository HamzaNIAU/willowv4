"""YouTube Upload Service - Handles video uploads to YouTube"""

import os
import uuid
import asyncio
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
        """Upload a video to YouTube with intelligent auto-discovery"""
        
        logger.info(f"[YouTube Upload] Starting upload for user {user_id} with params: {params}")
        channel_id = params["channel_id"]
        
        # Import file service for automatic discovery
        from services.youtube_file_service import YouTubeFileService
        file_service = YouTubeFileService(self.db, user_id)
        
        # Check if auto-discovery is enabled
        auto_discover = params.get("auto_discover", True)  # Default to True for backward compatibility
        video_reference_id = params.get("video_reference_id")
        thumbnail_reference_id = params.get("thumbnail_reference_id")
        
        logger.info(f"[YouTube Upload] Auto-discover: {auto_discover}, Video ref: {video_reference_id}, Thumb ref: {thumbnail_reference_id}")
        
        # Only auto-discover if explicitly enabled and no reference provided
        if not video_reference_id and auto_discover:
            # Automatically find the latest pending uploads
            logger.info(f"[YouTube Upload] Auto-discovery enabled - looking for recent uploads for user {user_id}")
            uploads = await file_service.get_latest_pending_uploads(user_id)
            
            logger.info(f"[YouTube Upload] Found uploads: Video={bool(uploads.get('video'))}, Thumbnail={bool(uploads.get('thumbnail'))}")
            
            if uploads.get("video"):
                logger.info(f"[YouTube Upload] Video details: {uploads['video']}")
            
            if not uploads["video"]:
                logger.error(f"[YouTube Upload] No video found in reference system for user {user_id}")
                raise Exception(
                    "❌ No video file found in upload queue.\n\n"
                    "To upload a video to YouTube:\n"
                    "1. Attach a video file to your message (drag & drop or use the paperclip icon)\n"
                    "2. The file will automatically get a reference ID when attached\n"
                    "3. Then ask me to upload it to YouTube\n\n"
                    "Note: Video files are automatically prepared for upload when you attach them. "
                    "If you just attached a file, please wait a moment for it to be processed."
                )
            
            video_reference_id = uploads["video"]["reference_id"]
            logger.info(f"[YouTube Upload] Auto-discovered video: {uploads['video']['file_name']} (ref: {video_reference_id})")
            
            # Also check for thumbnail if not provided (OPTIONAL - not required)
            if not thumbnail_reference_id and uploads.get("thumbnail"):
                thumbnail_reference_id = uploads["thumbnail"]["reference_id"]
                logger.info(f"[YouTube Upload] Auto-discovered thumbnail: {uploads['thumbnail']['file_name']} (ref: {thumbnail_reference_id})")
            elif not thumbnail_reference_id:
                logger.info("[YouTube Upload] No thumbnail found - video will use YouTube auto-generated thumbnail")
        elif not video_reference_id and not auto_discover:
            logger.error(f"[YouTube Upload] Auto-discovery disabled and no video reference provided")
            raise Exception("No video specified. Please attach a video file to your message when asking to upload to YouTube. Files are stored in the reference system, not in /workspace.")
        
        # Get valid access token
        access_token = await self.oauth_handler.get_valid_token(user_id, channel_id)
        
        # Get channel info
        client = await self.db.client
        # FIXED: Use compatibility view that filters by platform='youtube' only
        channel_result = await client.table("youtube_channels_compat").select("name").eq(
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
        
        # Return immediately with upload ID - upload will be processed in background
        try:
            logger.info(f"[YouTube Upload] Starting background upload to YouTube API for video '{params['title']}'")
            
            # Update status to uploading
            await client.table("youtube_uploads").update({
                "upload_status": "uploading", 
                "status_message": "Upload queued and processing..."
            }).eq("id", upload_id).execute()
            
            # Start background task for actual upload
            asyncio.create_task(self._perform_upload_background(
                upload_id, user_id, channel_id, channel_name, params, 
                video_reference_id, thumbnail_reference_id, access_token
            ))
            
            # Return immediately to prevent connection timeout
            return {
                "upload_id": upload_id,
                "channel_name": channel_name,
                "status": "uploading",
                "message": f"Upload started for '{params['title']}' - processing in background",
                "video_reference": video_reference_id,
                "thumbnail_reference": thumbnail_reference_id,
                "automatic_discovery": not params.get("video_reference_id")
            }
            
        except Exception as upload_error:
            logger.error(f"[YouTube Upload] Failed to start upload: {upload_error}", exc_info=True)
            
            # Update upload record with failure
            await client.table("youtube_uploads").update({
                "upload_status": "failed",
                "status_message": f"Failed to start upload: {str(upload_error)}"
            }).eq("id", upload_id).execute()
            
            raise Exception(f"Failed to start video upload: {str(upload_error)}")
    
    async def _perform_upload_background(
        self, 
        upload_id: str, 
        user_id: str, 
        channel_id: str, 
        channel_name: str, 
        params: dict, 
        video_reference_id: str, 
        thumbnail_reference_id: str, 
        access_token: str
    ):
        """Perform the actual YouTube upload in background"""
        client = await self.db.client
        
        try:
            logger.info(f"[YouTube Upload Background] Starting actual upload to YouTube API for video '{params['title']}'")
            
            # Update status to actively uploading
            await client.table("youtube_uploads").update({
                "upload_status": "uploading",
                "status_message": "Uploading to YouTube..."
            }).eq("id", upload_id).execute()
            
            # Initialize file service
            from services.youtube_file_service import YouTubeFileService
            file_service = YouTubeFileService(self.db, user_id)
            
            # Get video file data
            video_data = await file_service.get_file_data(video_reference_id, user_id)
            
            if not video_data:
                raise Exception("Failed to retrieve video file data - reference ID may be invalid or expired")
            
            # Validate file data
            if len(video_data) < 1024:  # Less than 1KB
                raise Exception(f"Video file data is too small ({len(video_data)} bytes) - file may be corrupted")
            
            if len(video_data) > 137438953472:  # 128GB YouTube limit
                raise Exception(f"Video file is too large ({len(video_data)} bytes) - exceeds YouTube's 128GB limit")
            
            logger.info(f"[YouTube Upload Background] Retrieved and validated video data: {len(video_data)} bytes ({len(video_data)/1024/1024:.1f} MB)")
            
            # Create temporary file for upload
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                temp_file.write(video_data)
                temp_file.flush()  # Ensure data is written to disk
                temp_file_path = temp_file.name
                
                # Verify file was written correctly
                temp_file_size = os.path.getsize(temp_file_path)
                if temp_file_size != len(video_data):
                    raise Exception(f"Temporary file size mismatch: expected {len(video_data)}, got {temp_file_size}")
                
                logger.info(f"[YouTube Upload] Created temporary file: {temp_file_path} ({temp_file_size} bytes)")
            
            try:
                # Build YouTube service
                credentials = Credentials(token=access_token)
                youtube = build('youtube', 'v3', credentials=credentials)
                
                # Prepare video metadata
                body = {
                    'snippet': {
                        'title': params["title"],
                        'description': params.get("description", ""),
                        'tags': params.get("tags", []),
                        'categoryId': str(params.get("category_id", "22"))
                    },
                    'status': {
                        'privacyStatus': params.get("privacy_status", "public"),
                        'madeForKids': params.get("made_for_kids", False),
                        'notifySubscribers': params.get("notify_subscribers", True)
                    }
                }
                
                # Handle scheduled publishing
                if params.get("scheduled_for"):
                    body['status']['publishAt'] = params["scheduled_for"]
                    body['status']['privacyStatus'] = 'private'  # Must be private for scheduled
                
                logger.info(f"[YouTube Upload] Uploading with metadata: {body}")
                
                # Create media upload with chunked progress tracking
                # Use 1MB chunks for progress updates
                chunksize = 1024 * 1024  # 1MB chunks
                media = MediaFileUpload(
                    temp_file_path,
                    chunksize=chunksize,
                    resumable=True,
                    mimetype='video/*'
                )
                
                # Execute upload with progress tracking
                insert_request = youtube.videos().insert(
                    part=','.join(body.keys()),
                    body=body,
                    media_body=media
                )
                
                logger.info(f"[YouTube Upload] Starting chunked upload with progress tracking...")
                
                # Perform resumable upload with progress tracking
                response = None
                video_id = None
                
                while response is None:
                    try:
                        logger.info(f"[YouTube Upload] Executing next chunk...")
                        status, response = insert_request.next_chunk()
                        
                        if status:
                            # Calculate progress percentage
                            progress = int(status.progress() * 100)
                            bytes_uploaded = status.resumable_progress
                            total_bytes = status.total_size
                            
                            logger.info(f"[YouTube Upload] Progress: {progress}% ({bytes_uploaded}/{total_bytes} bytes)")
                            
                            # Update database with progress (using only existing columns for now)
                            await client.table("youtube_uploads").update({
                                "upload_progress": progress,
                                "status_message": f"Uploading to YouTube... {progress}% complete ({bytes_uploaded}/{total_bytes} bytes)"
                            }).eq("id", upload_id).execute()
                            
                    except Exception as chunk_error:
                        logger.error(f"[YouTube Upload] Chunk upload error: {chunk_error}")
                        raise chunk_error
                
                video_id = response['id']
                
                logger.info(f"[YouTube Upload] Successfully uploaded video: {video_id}")
                
                # Handle thumbnail upload if provided
                thumbnail_uploaded = False
                if thumbnail_reference_id:
                    try:
                        logger.info(f"[YouTube Upload] Uploading thumbnail for video {video_id}")
                        thumbnail_data = await file_service.get_file_data(thumbnail_reference_id, user_id)
                        
                        if thumbnail_data:
                            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as thumb_file:
                                thumb_file.write(thumbnail_data)
                                thumb_file_path = thumb_file.name
                            
                            try:
                                youtube.thumbnails().set(
                                    videoId=video_id,
                                    media_body=MediaFileUpload(thumb_file_path, mimetype='image/jpeg')
                                ).execute()
                                
                                thumbnail_uploaded = True
                                logger.info(f"[YouTube Upload] Successfully uploaded thumbnail")
                            finally:
                                os.unlink(thumb_file_path)
                        
                    except Exception as thumb_error:
                        logger.warning(f"[YouTube Upload] Thumbnail upload failed: {thumb_error}")
                        # Don't fail the entire upload if thumbnail fails
                
                # Wait for YouTube processing to complete
                logger.info(f"[YouTube Upload] Waiting for YouTube processing to complete...")
                await client.table("youtube_uploads").update({
                    "upload_status": "processing",
                    "upload_progress": 100,
                    "video_id": video_id,
                    "status_message": "Uploaded - waiting for YouTube processing...",
                }).eq("id", upload_id).execute()
                
                # Poll YouTube API for processing status
                processing_complete = await self._wait_for_processing(youtube, video_id, client, upload_id)
                
                if processing_complete:
                    # Update upload record with final success
                    await client.table("youtube_uploads").update({
                        "upload_status": "completed",
                        "status_message": "Upload and processing completed successfully",
                        "completed_at": datetime.now(timezone.utc).isoformat()
                    }).eq("id", upload_id).execute()
                    
                    logger.info(f"[YouTube Upload Background] Complete! Video ID: {video_id} - https://youtube.com/watch?v={video_id}")
                else:
                    # Processing timed out, but upload succeeded
                    await client.table("youtube_uploads").update({
                        "upload_status": "uploaded",
                        "status_message": "Upload successful - processing may still be in progress",
                        "completed_at": datetime.now(timezone.utc).isoformat()
                    }).eq("id", upload_id).execute()
                    
                    logger.warning(f"[YouTube Upload] Upload completed but processing status unknown: {video_id}")
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
        
        except Exception as upload_error:
            logger.error(f"[YouTube Upload] Upload failed: {upload_error}", exc_info=True)
            
            # Update upload record with failure
            await client.table("youtube_uploads").update({
                "upload_status": "failed",
                "status_message": f"Upload failed: {str(upload_error)}"
            }).eq("id", upload_id).execute()
            
            raise Exception(f"Failed to upload video to YouTube: {str(upload_error)}")
    
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
    
    async def _wait_for_processing(self, youtube, video_id: str, client, upload_id: str, timeout_minutes: int = 5) -> bool:
        """
        Wait for YouTube video processing to complete
        
        Returns:
            bool: True if processing completed, False if timed out
        """
        import asyncio
        from datetime import datetime, timezone, timedelta
        
        start_time = datetime.now(timezone.utc)
        timeout_time = start_time + timedelta(minutes=timeout_minutes)
        
        logger.info(f"[YouTube Processing] Starting processing check for video {video_id}, timeout in {timeout_minutes} minutes")
        
        while datetime.now(timezone.utc) < timeout_time:
            try:
                # Get video processing status from YouTube API
                response = youtube.videos().list(
                    part="processingDetails,status",
                    id=video_id
                ).execute()
                
                if not response.get("items"):
                    logger.warning(f"[YouTube Processing] Video {video_id} not found in API response")
                    await asyncio.sleep(10)
                    continue
                
                video_data = response["items"][0]
                processing_details = video_data.get("processingDetails", {})
                status = video_data.get("status", {})
                
                processing_status = processing_details.get("processingStatus")
                upload_status = status.get("uploadStatus")
                privacy_status = status.get("privacyStatus")
                
                logger.info(f"[YouTube Processing] Status - Upload: {upload_status}, Processing: {processing_status}, Privacy: {privacy_status}")
                
                # Update database with current status
                await client.table("youtube_uploads").update({
                    "status_message": f"YouTube processing: {processing_status or 'checking...'}"
                }).eq("id", upload_id).execute()
                
                # Check if processing is complete
                if processing_status == "succeeded" and upload_status == "uploaded":
                    logger.info(f"[YouTube Processing] Video {video_id} processing completed successfully")
                    return True
                elif processing_status == "failed":
                    logger.error(f"[YouTube Processing] Video {video_id} processing failed")
                    await client.table("youtube_uploads").update({
                        "status_message": "YouTube processing failed"
                    }).eq("id", upload_id).execute()
                    return False
                elif upload_status == "failed":
                    logger.error(f"[YouTube Processing] Video {video_id} upload failed")
                    await client.table("youtube_uploads").update({
                        "status_message": "YouTube upload failed"
                    }).eq("id", upload_id).execute()
                    return False
                
                # Still processing, wait before next check
                await asyncio.sleep(15)  # Check every 15 seconds
                
            except Exception as e:
                logger.warning(f"[YouTube Processing] Error checking status: {e}")
                await asyncio.sleep(10)
        
        logger.warning(f"[YouTube Processing] Processing check timed out after {timeout_minutes} minutes for video {video_id}")
        return False