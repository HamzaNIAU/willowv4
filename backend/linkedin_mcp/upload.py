"""LinkedIn Upload Service"""

import uuid
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import base64

from services.supabase import DBConnection
from services.youtube_file_service import YouTubeFileService
from utils.logger import logger
from utils.encryption import decrypt_data
from .service import LinkedInAPIService
from .oauth import LinkedInOAuthHandler
from .accounts import LinkedInAccountService


class LinkedInUploadService:
    """Service for handling LinkedIn post creation and uploads"""
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.file_service = YouTubeFileService(db)
        self.api_service = LinkedInAPIService()
        self.oauth_handler = LinkedInOAuthHandler(db)
        self.account_service = LinkedInAccountService(db)
    
    async def create_post(self, user_id: str, post_params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a LinkedIn post with automatic file discovery"""
        try:
            # Validate required parameters
            if not post_params.get("account_id"):
                raise ValueError("account_id is required")
            
            if not post_params.get("text"):
                raise ValueError("text content is required")
            
            account_id = post_params["account_id"]
            text = post_params["text"]
            visibility = post_params.get("visibility", "PUBLIC")  # PUBLIC, CONNECTIONS
            
            # Validate account access
            if not await self.account_service.validate_account_access(user_id, account_id):
                raise ValueError("Invalid account or expired token. Please re-authenticate.")
            
            # Auto-discover files if enabled
            video_reference_id = post_params.get("video_reference_id")
            image_reference_ids = post_params.get("image_reference_ids", [])
            
            if post_params.get("auto_discover", True) and not video_reference_id and not image_reference_ids:
                uploads = await self.file_service.get_latest_pending_uploads(user_id)
                
                if uploads.get("video"):
                    video_reference_id = uploads["video"]["reference_id"]
                    logger.info(f"Auto-discovered video: {video_reference_id}")
                
                if uploads.get("thumbnail"):
                    image_reference_ids = [uploads["thumbnail"]["reference_id"]]
                    logger.info(f"Auto-discovered image: {image_reference_ids}")
            
            # Create post record
            post_record_id = str(uuid.uuid4())
            
            await self.db.execute("""
                INSERT INTO linkedin_posts (
                    id, user_id, account_id, text, visibility,
                    video_reference_id, image_reference_ids,
                    post_status, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', NOW())
            """, post_record_id, user_id, account_id, text, visibility,
                video_reference_id, image_reference_ids
            )
            
            # Start background posting
            asyncio.create_task(self._create_post_background(post_record_id, user_id, post_params))
            
            # Get account info for response
            account_info = await self.account_service.get_account(user_id, account_id)
            
            return {
                "post_record_id": post_record_id,
                "status": "posting",
                "message": "LinkedIn post creation started",
                "account_name": account_info.get("name", "LinkedIn User") if account_info else "LinkedIn User",
                "text": text
            }
            
        except Exception as e:
            logger.error(f"Failed to create LinkedIn post: {e}")
            raise
    
    async def _create_post_background(self, post_record_id: str, user_id: str, post_params: Dict[str, Any]):
        """Background task to create LinkedIn post"""
        try:
            # Update status to posting
            await self.db.execute("""
                UPDATE linkedin_posts 
                SET post_status = 'posting', status_message = 'Creating LinkedIn post...'
                WHERE id = $1
            """, post_record_id)
            
            # Get post details
            post = await self.db.fetchrow("""
                SELECT * FROM linkedin_posts WHERE id = $1
            """, post_record_id)
            
            if not post:
                raise Exception("Post record not found")
            
            account_id = post['account_id']
            text = post['text']
            visibility = post['visibility']
            video_reference_id = post['video_reference_id']
            image_reference_ids = post['image_reference_ids'] or []
            
            # Get valid access token
            access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
            
            # Determine post type and create accordingly
            if video_reference_id:
                # Video post
                video_data = await self.file_service.get_file_data(video_reference_id)
                video_filename = await self.file_service.get_file_name(video_reference_id)
                
                # Get thumbnail if available
                thumbnail_data = None
                if image_reference_ids:
                    thumbnail_data = await self.file_service.get_file_data(image_reference_ids[0])
                
                result = await self.api_service.create_video_post(
                    access_token, account_id, text, video_data, video_filename,
                    thumbnail_data, visibility
                )
                
                # Mark video reference as used
                await self.file_service.mark_reference_as_used(video_reference_id)
                if image_reference_ids:
                    await self.file_service.mark_reference_as_used(image_reference_ids[0])
                
            elif image_reference_ids:
                # Image post (LinkedIn supports only one image per post in basic API)
                image_data = await self.file_service.get_file_data(image_reference_ids[0])
                image_filename = await self.file_service.get_file_name(image_reference_ids[0])
                
                result = await self.api_service.create_image_post(
                    access_token, account_id, text, image_data, image_filename, visibility
                )
                
                # Mark image reference as used
                await self.file_service.mark_reference_as_used(image_reference_ids[0])
                
            else:
                # Text-only post
                result = await self.api_service.create_text_post(
                    access_token, account_id, text, visibility
                )
            
            # Update post record with success
            await self.db.execute("""
                UPDATE linkedin_posts SET
                    post_id = $2,
                    post_url = $3,
                    post_status = 'completed',
                    status_message = 'Post created successfully',
                    completed_at = NOW()
                WHERE id = $1
            """, post_record_id, result['post_id'], result['post_url'])
            
            logger.info(f"Successfully created LinkedIn post {result['post_id']} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Background LinkedIn post creation failed: {e}")
            
            # Update post record with error
            await self.db.execute("""
                UPDATE linkedin_posts SET
                    post_status = 'failed',
                    status_message = $2,
                    error_details = $3
                WHERE id = $1
            """, post_record_id, str(e), {"error": str(e), "timestamp": datetime.utcnow().isoformat()})
    
    async def get_post_status(self, user_id: str, post_record_id: str) -> Dict[str, Any]:
        """Get the status of a LinkedIn post creation"""
        try:
            post = await self.db.fetchrow("""
                SELECT 
                    id, account_id, text, post_id, post_url,
                    post_status, status_message, error_details,
                    created_at, completed_at,
                    video_reference_id, image_reference_ids
                FROM linkedin_posts
                WHERE id = $1 AND user_id = $2
            """, post_record_id, user_id)
            
            if not post:
                raise Exception("Post not found")
            
            # Get account info
            account_info = await self.account_service.get_account(user_id, post['account_id'])
            
            response = {
                "post_record_id": post['id'],
                "status": post['post_status'],
                "message": post['status_message'],
                "text": post['text'],
                "created_at": post['created_at'].isoformat() if post['created_at'] else None,
                "completed_at": post['completed_at'].isoformat() if post['completed_at'] else None,
                "account": {
                    "id": post['account_id'],
                    "name": account_info.get("name", "LinkedIn User") if account_info else "LinkedIn User"
                }
            }
            
            # Add success details if completed
            if post['post_status'] == 'completed' and post['post_id']:
                response.update({
                    "post_id": post['post_id'],
                    "post_url": post['post_url'],
                    "platform": "linkedin"
                })
            
            # Add error details if failed
            if post['post_status'] == 'failed' and post['error_details']:
                response["error_details"] = post['error_details']
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to get LinkedIn post status: {e}")
            raise
    
    async def delete_post(self, user_id: str, account_id: str, post_id: str) -> Dict[str, Any]:
        """Delete a LinkedIn post"""
        try:
            # Validate account access
            if not await self.account_service.validate_account_access(user_id, account_id):
                raise ValueError("Invalid account or expired token")
            
            # Get valid access token
            access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
            
            # Delete via API
            success = await self.api_service.delete_post(access_token, post_id)
            
            if success:
                # Update database record
                await self.db.execute("""
                    UPDATE linkedin_posts SET
                        post_status = 'deleted',
                        deleted_at = NOW()
                    WHERE user_id = $1 AND account_id = $2 AND post_id = $3
                """, user_id, account_id, post_id)
                
                return {
                    "success": True,
                    "message": f"LinkedIn post {post_id} deleted successfully"
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to delete LinkedIn post {post_id}"
                }
                
        except Exception as e:
            logger.error(f"Failed to delete LinkedIn post: {e}")
            raise
    
    async def get_recent_posts(self, user_id: str, account_id: str, limit: int = 10) -> Dict[str, Any]:
        """Get recent posts from LinkedIn account"""
        try:
            # Get posts from database
            posts = await self.db.fetch("""
                SELECT 
                    id, post_id, text, post_url, post_status,
                    created_at, completed_at
                FROM linkedin_posts
                WHERE user_id = $1 AND account_id = $2
                AND post_status IN ('completed', 'posting')
                ORDER BY created_at DESC
                LIMIT $3
            """, user_id, account_id, limit)
            
            # Format posts
            formatted_posts = []
            for post in posts:
                formatted_post = {
                    "id": post['post_id'],
                    "text": post['text'],
                    "post_url": post['post_url'],
                    "status": post['post_status'],
                    "created_at": post['created_at'].isoformat() if post['created_at'] else None,
                    "platform": "linkedin"
                }
                formatted_posts.append(formatted_post)
            
            # Get account info
            account_info = await self.account_service.get_account(user_id, account_id)
            
            return {
                "success": True,
                "posts": formatted_posts,
                "count": len(formatted_posts),
                "account": {
                    "id": account_id,
                    "name": account_info.get("name", "LinkedIn User") if account_info else "LinkedIn User"
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get LinkedIn recent posts: {e}")
            raise
    
    async def get_post_analytics(self, user_id: str, account_id: str, post_id: str) -> Dict[str, Any]:
        """Get analytics for a specific LinkedIn post"""
        try:
            # Validate account access
            if not await self.account_service.validate_account_access(user_id, account_id):
                raise ValueError("Invalid account or expired token")
            
            # Get valid access token
            access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
            
            # Get analytics from API
            analytics = await self.api_service.get_post_analytics(access_token, post_id)
            
            return {
                "success": True,
                "post_id": post_id,
                "analytics": analytics
            }
            
        except Exception as e:
            logger.error(f"Failed to get LinkedIn post analytics: {e}")
            raise