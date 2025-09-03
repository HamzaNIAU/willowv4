"""TikTok Upload Service - Handles video uploads with progress tracking"""

import uuid
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from services.supabase import DBConnection
from services.youtube_file_service import YouTubeFileService
from utils.logger import logger
from .service import TikTokAPIService


class TikTokUploadService:
    """Service for handling TikTok video uploads with progress tracking"""
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.file_service = YouTubeFileService(db)
        self.api_service = TikTokAPIService(db)
    
    async def upload_video(
        self,
        user_id: str,
        account_id: str,
        reference_id: str,
        title: str,
        description: str = "",
        privacy_level: str = "SELF_ONLY",
        disable_duet: bool = False,
        disable_comment: bool = False,
        disable_stitch: bool = False,
        brand_content_toggle: bool = False,
        brand_organic_toggle: bool = False
    ) -> Dict[str, Any]:
        """Upload video to TikTok with progress tracking"""
        
        try:
            # Generate upload ID
            upload_id = str(uuid.uuid4())
            
            # Get video file data
            file_data = await self.file_service.get_file_data(reference_id)
            if not file_data:
                raise Exception("Video file not found or expired")
            
            # Create upload record
            await self._create_upload_record(
                upload_id=upload_id,
                user_id=user_id,
                account_id=account_id,
                reference_id=reference_id,
                title=title,
                description=description,
                privacy_level=privacy_level,
                disable_duet=disable_duet,
                disable_comment=disable_comment,
                disable_stitch=disable_stitch,
                brand_content_toggle=brand_content_toggle,
                brand_organic_toggle=brand_organic_toggle
            )
            
            # Start background upload process
            asyncio.create_task(
                self._perform_upload_background(
                    upload_id=upload_id,
                    user_id=user_id,
                    account_id=account_id,
                    video_data=file_data,
                    title=title,
                    description=description,
                    privacy_level=privacy_level,
                    disable_duet=disable_duet,
                    disable_comment=disable_comment,
                    disable_stitch=disable_stitch,
                    brand_content_toggle=brand_content_toggle,
                    brand_organic_toggle=brand_organic_toggle
                )
            )
            
            return {
                "upload_id": upload_id,
                "status": "uploading",
                "message": f"TikTok video upload started: {title}",
                "progress": 0
            }
            
        except Exception as e:
            logger.error(f"TikTok upload initiation failed: {e}")
            raise
    
    async def _create_upload_record(
        self,
        upload_id: str,
        user_id: str,
        account_id: str,
        reference_id: str,
        title: str,
        description: str,
        privacy_level: str,
        disable_duet: bool,
        disable_comment: bool,
        disable_stitch: bool,
        brand_content_toggle: bool,
        brand_organic_toggle: bool
    ):
        """Create upload tracking record in database"""
        
        # Get file info for the reference
        file_info = await self.file_service.get_file_info(reference_id)
        if not file_info:
            raise Exception("Referenced file not found")
        
        # Build TikTok-specific settings
        platform_settings = {
            "privacy_level": privacy_level,
            "disable_duet": disable_duet,
            "disable_comment": disable_comment,
            "disable_stitch": disable_stitch,
            "brand_content_toggle": brand_content_toggle,
            "brand_organic_toggle": brand_organic_toggle
        }
        
        await self.db.execute("""
            INSERT INTO tiktok_videos (
                id, user_id, account_id, title, description,
                video_status, video_reference_id, created_at
            ) VALUES (
                $1, $2, $3, $4, $5, 'pending', $6, NOW()
            )
        """, 
            upload_id, user_id, account_id, title, description, reference_id
        )
    
    async def _perform_upload_background(
        self,
        upload_id: str,
        user_id: str,
        account_id: str,
        video_data: bytes,
        title: str,
        description: str,
        privacy_level: str,
        disable_duet: bool,
        disable_comment: bool,
        disable_stitch: bool,
        brand_content_toggle: bool,
        brand_organic_toggle: bool
    ):
        """Perform the actual upload in the background with progress updates"""
        
        try:
            # Update status to uploading
            await self._update_upload_status(upload_id, "uploading", 10)
            
            # Upload video using TikTok API
            upload_result = await self.api_service.create_video_upload(
                user_id=user_id,
                account_id=account_id,
                video_data=video_data,
                title=title,
                description=description,
                privacy_level=privacy_level,
                disable_duet=disable_duet,
                disable_comment=disable_comment,
                disable_stitch=disable_stitch,
                brand_content_toggle=brand_content_toggle,
                brand_organic_toggle=brand_organic_toggle
            )
            
            # Update progress - upload completed, waiting for processing
            await self._update_upload_status(upload_id, "processing", 80)
            
            # Monitor processing status
            publish_id = upload_result.get("publish_id")
            if publish_id:
                await self._monitor_processing_status(upload_id, user_id, account_id, publish_id)
            else:
                # Complete immediately if no processing needed
                await self._complete_upload(
                    upload_id=upload_id,
                    video_id=upload_result.get("video_id"),
                    publish_id=publish_id,
                    video_url=None
                )
            
        except Exception as e:
            logger.error(f"TikTok background upload failed for {upload_id}: {e}")
            await self._fail_upload(upload_id, str(e))
    
    async def _monitor_processing_status(
        self,
        upload_id: str,
        user_id: str,
        account_id: str,
        publish_id: str,
        max_attempts: int = 60  # 5 minutes with 5-second intervals
    ):
        """Monitor video processing status"""
        
        attempt = 0
        while attempt < max_attempts:
            try:
                # Check processing status
                status_result = await self.api_service.get_video_status(user_id, account_id, publish_id)
                
                status = status_result.get("status", "").lower()
                
                if status == "processing_download":
                    progress = 85
                elif status == "processing_upload":
                    progress = 90
                elif status == "processing":
                    progress = 95
                elif status in ["published", "success"]:
                    # Video published successfully
                    await self._complete_upload(
                        upload_id=upload_id,
                        video_id=status_result.get("video_id"),
                        publish_id=publish_id,
                        video_url=status_result.get("share_url")
                    )
                    return
                elif status in ["failed", "error"]:
                    # Processing failed
                    error_message = status_result.get("fail_reason", "Processing failed")
                    await self._fail_upload(upload_id, error_message)
                    return
                else:
                    # Unknown status, assume still processing
                    progress = 90
                
                # Update progress
                await self._update_upload_status(upload_id, "processing", progress)
                
                # Wait before next check
                await asyncio.sleep(5)
                attempt += 1
                
            except Exception as e:
                logger.error(f"Error checking TikTok processing status: {e}")
                attempt += 1
                await asyncio.sleep(5)
        
        # Timeout reached
        logger.warning(f"TikTok processing monitoring timeout for upload {upload_id}")
        await self._fail_upload(upload_id, "Processing timeout - video may still be processing")
    
    async def _update_upload_status(self, upload_id: str, status: str, progress: int = None):
        """Update upload status and progress"""
        
        status_message = f"Upload {status}"
        if progress is not None:
            status_message = f"Upload {status} ({progress}%)"
        
        await self.db.execute("""
            UPDATE tiktok_videos SET
                video_status = $2,
                status_message = $3
            WHERE id = $1
        """, upload_id, status, status_message)
    
    async def _complete_upload(
        self,
        upload_id: str,
        video_id: Optional[str],
        publish_id: str,
        video_url: Optional[str]
    ):
        """Mark upload as completed with final details"""
        
        await self.db.execute("""
            UPDATE tiktok_videos SET
                video_status = 'completed',
                status_message = 'Upload completed successfully',
                video_id = $2,
                video_url = $3,
                completed_at = NOW()
            WHERE id = $1
        """, upload_id, video_id, video_url)
        
        # Mark file reference as used
        reference_id = await self.db.fetchval(
            "SELECT video_reference_id FROM tiktok_videos WHERE id = $1", upload_id
        )
        if reference_id:
            await self.file_service.mark_reference_used(reference_id)
    
    async def _fail_upload(self, upload_id: str, error_message: str):
        """Mark upload as failed with error details"""
        
        await self.db.execute("""
            UPDATE tiktok_videos SET
                video_status = 'failed',
                status_message = $2,
                error_details = jsonb_build_object('error', $2, 'timestamp', NOW())
            WHERE id = $1
        """, upload_id, error_message)
    
    async def get_upload_status(self, user_id: str, upload_id: str) -> Optional[Dict[str, Any]]:
        """Get upload progress status"""
        
        try:
            row = await self.db.fetchrow("""
                SELECT 
                    tv.*, ta.name as account_name, ta.username as account_username
                FROM tiktok_videos tv
                LEFT JOIN tiktok_accounts ta ON tv.account_id = ta.id
                WHERE tv.id = $1 AND tv.user_id = $2
            """, upload_id, user_id)
            
            if not row:
                return None
            
            # Calculate progress based on status
            progress = 0
            if row["video_status"] == "uploading":
                progress = 50
            elif row["video_status"] == "processing":
                progress = 80
            elif row["video_status"] == "completed":
                progress = 100
            
            status_data = {
                "upload_id": row["id"],
                "account_id": row["account_id"],
                "account_name": row["account_name"],
                "account_username": row["account_username"],
                "title": row["title"],
                "description": row["description"],
                "upload_status": row["video_status"],
                "upload_progress": progress,
                "video_id": row["video_id"],
                "video_url": row["video_url"],
                "status_message": row["status_message"],
                "error_details": row["error_details"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
                "platform": "tiktok"
            }
            
            return status_data
            
        except Exception as e:
            logger.error(f"Failed to get TikTok upload status: {e}")
            raise
    
    async def get_user_uploads(
        self,
        user_id: str,
        account_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get user's TikTok upload history"""
        
        try:
            query = """
                SELECT 
                    tv.*, ta.name as account_name, ta.username as account_username
                FROM tiktok_videos tv
                LEFT JOIN tiktok_accounts ta ON tv.account_id = ta.id
                WHERE tv.user_id = $1
            """
            params = [user_id]
            
            if account_id:
                query += " AND tv.account_id = $2"
                params.append(account_id)
                query += " ORDER BY tv.created_at DESC LIMIT $3 OFFSET $4"
                params.extend([limit, offset])
            else:
                query += " ORDER BY tv.created_at DESC LIMIT $2 OFFSET $3"
                params.extend([limit, offset])
            
            rows = await self.db.fetch(query, *params)
            
            uploads = []
            for row in rows:
                # Calculate progress based on status
                progress = 0
                if row["video_status"] == "uploading":
                    progress = 50
                elif row["video_status"] == "processing":
                    progress = 80
                elif row["video_status"] == "completed":
                    progress = 100
                
                upload_data = {
                    "upload_id": row["id"],
                    "account_id": row["account_id"],
                    "account_name": row["account_name"],
                    "account_username": row["account_username"],
                    "title": row["title"],
                    "description": row["description"],
                    "upload_status": row["video_status"],
                    "upload_progress": progress,
                    "video_id": row["video_id"],
                    "video_url": row["video_url"],
                    "status_message": row["status_message"],
                    "error_details": row["error_details"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
                    "platform": "tiktok"
                }
                uploads.append(upload_data)
            
            return uploads
            
        except Exception as e:
            logger.error(f"Failed to get TikTok user uploads: {e}")
            raise
    
    async def update_video_stats(
        self,
        upload_id: str,
        view_count: Optional[int] = None,
        like_count: Optional[int] = None,
        comment_count: Optional[int] = None,
        share_count: Optional[int] = None
    ) -> bool:
        """Update video statistics (placeholder - TikTok videos table doesn't have stats columns)"""
        
        try:
            # Note: The tiktok_videos table doesn't have view/like/comment/share columns
            # This is a placeholder for future enhancement or integration with analytics
            logger.info(f"TikTok video stats update requested for {upload_id}: views={view_count}, likes={like_count}, comments={comment_count}, shares={share_count}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update TikTok video stats: {e}")
            return False