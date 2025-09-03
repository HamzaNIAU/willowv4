"""Instagram Upload Service - Handles Instagram posts, stories, and media uploads"""

import os
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from services.supabase import DBConnection
from utils.logger import logger
from .oauth import InstagramOAuthHandler
from .service import InstagramAPIService


class InstagramUploadService:
    """Service for uploading posts, stories, and media to Instagram"""
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.oauth_handler = InstagramOAuthHandler(db)
        self.instagram_service = InstagramAPIService(db)
    
    async def create_post(self, user_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create an Instagram post with intelligent auto-discovery"""
        
        logger.info(f"[Instagram Upload] Starting post creation for user {user_id} with params: {params}")
        account_id = params["account_id"]
        
        # Import file service for automatic discovery
        from services.youtube_file_service import YouTubeFileService  # Reuse the file service
        file_service = YouTubeFileService(self.db, user_id)
        
        # Check if auto-discovery is enabled
        auto_discover = params.get("auto_discover", True)
        video_reference_id = params.get("video_reference_id")
        image_reference_ids = params.get("image_reference_ids", [])
        
        logger.info(f"[Instagram Upload] Auto-discover: {auto_discover}, Video ref: {video_reference_id}, Image refs: {image_reference_ids}")
        
        # Auto-discover media files if enabled
        discovered_files = []
        media_urls = []
        
        if auto_discover:
            logger.info(f"[Instagram Upload] Auto-discovery enabled - looking for recent uploads for user {user_id}")
            uploads = await file_service.get_latest_pending_uploads(user_id)
            
            logger.info(f"[Instagram Upload] Found uploads: Video={bool(uploads.get('video'))}, Thumbnail={bool(uploads.get('thumbnail'))}")
            
            # Process video if found
            if uploads.get("video"):
                video_data = await file_service.get_file_data(uploads["video"]["reference_id"], user_id)
                if video_data:
                    # For Instagram, we need to upload to a publicly accessible URL
                    # For now, we'll use the reference system as a placeholder
                    media_urls.append({
                        "type": "video",
                        "reference_id": uploads["video"]["reference_id"],
                        "filename": uploads["video"]["file_name"]
                    })
                    discovered_files.append({"type": "video", "name": uploads["video"]["file_name"]})
                    logger.info(f"[Instagram Upload] Auto-discovered video: {uploads['video']['file_name']}")
            
            # Process image if found
            if uploads.get("thumbnail"):
                image_data = await file_service.get_file_data(uploads["thumbnail"]["reference_id"], user_id)
                if image_data:
                    media_urls.append({
                        "type": "image",
                        "reference_id": uploads["thumbnail"]["reference_id"],
                        "filename": uploads["thumbnail"]["file_name"]
                    })
                    discovered_files.append({"type": "image", "name": uploads["thumbnail"]["file_name"]})
                    logger.info(f"[Instagram Upload] Auto-discovered image: {uploads['thumbnail']['file_name']}")
        
        # Process specific reference files if provided
        if video_reference_id:
            video_data = await file_service.get_file_data(video_reference_id, user_id)
            if video_data:
                media_urls.append({
                    "type": "video", 
                    "reference_id": video_reference_id,
                    "filename": f"video_{video_reference_id}"
                })
        
        for img_ref_id in image_reference_ids:
            image_data = await file_service.get_file_data(img_ref_id, user_id)
            if image_data:
                media_urls.append({
                    "type": "image",
                    "reference_id": img_ref_id,
                    "filename": f"image_{img_ref_id}"
                })
        
        # Get valid access token for account validation
        try:
            await self.oauth_handler.get_valid_token(user_id, account_id)
        except Exception as e:
            raise Exception(f"Instagram account {account_id} authentication failed: {str(e)}")
        
        # Get account info
        client = await self.db.client
        account_result = await client.table("instagram_accounts").select("username, name").eq(
            "user_id", user_id
        ).eq("id", account_id).execute()
        
        if not account_result.data:
            raise Exception(f"Instagram account {account_id} not found")
        
        account_username = account_result.data[0]["username"]
        account_name = account_result.data[0]["name"]
        
        # Create post record for tracking
        post_record_id = str(uuid.uuid4())
        post_data = {
            "id": post_record_id,
            "user_id": user_id,
            "account_id": account_id,
            "caption": params.get("caption", ""),
            "media_type": params.get("media_type", "IMAGE"),
            "post_status": "pending",
            "video_reference_id": video_reference_id,
            "image_reference_ids": image_reference_ids,
        }
        
        result = await client.table("instagram_posts").insert(post_data).execute()
        
        if not result.data:
            raise Exception("Failed to create post record")
        
        # Mark references as used
        references_to_mark = []
        if video_reference_id:
            references_to_mark.append(video_reference_id)
        references_to_mark.extend(image_reference_ids)
        
        if references_to_mark:
            await file_service.mark_references_as_used(references_to_mark)
        
        # Return immediately and process post creation in background
        try:
            logger.info(f"[Instagram Upload] Starting background post creation")
            
            # Update status to posting
            await client.table("instagram_posts").update({
                "post_status": "posting", 
                "status_message": "Creating Instagram post..."
            }).eq("id", post_record_id).execute()
            
            # Start background task for actual post creation
            asyncio.create_task(self._create_post_background(
                post_record_id, user_id, account_id, account_username, account_name,
                params, media_urls, discovered_files
            ))
            
            # Return immediately to prevent connection timeout
            return {
                "post_record_id": post_record_id,
                "account_username": account_username,
                "account_name": account_name,
                "status": "posting",
                "message": f"Instagram post creation started for @{account_username} - processing in background",
                "media_count": len(media_urls),
                "discovered_files": discovered_files,
                "automatic_discovery": auto_discover and bool(discovered_files)
            }
            
        except Exception as upload_error:
            logger.error(f"[Instagram Upload] Failed to start post creation: {upload_error}", exc_info=True)
            
            # Update post record with failure
            await client.table("instagram_posts").update({
                "post_status": "failed",
                "status_message": f"Failed to start post creation: {str(upload_error)}"
            }).eq("id", post_record_id).execute()
            
            raise Exception(f"Failed to create Instagram post: {str(upload_error)}")
    
    async def _create_post_background(
        self,
        post_record_id: str,
        user_id: str,
        account_id: str,
        account_username: str,
        account_name: str,
        params: dict,
        media_urls: List[Dict[str, str]],
        discovered_files: List[Dict[str, str]]
    ):
        """Perform the actual Instagram post creation in background"""
        client = await self.db.client
        
        try:
            logger.info(f"[Instagram Upload Background] Starting actual post creation for account @{account_username}")
            
            # Update status to actively posting
            await client.table("instagram_posts").update({
                "post_status": "creating_container",
                "status_message": "Creating media container..."
            }).eq("id", post_record_id).execute()
            
            # Determine post type and prepare media
            caption = params.get("caption", "")
            
            # For now, we'll use placeholder URLs - in production, you'd upload to your CDN
            image_url = None
            video_url = None
            
            # Process media URLs (simplified for demo - in production you'd upload to CDN)
            for media in media_urls:
                if media["type"] == "video" and not video_url:
                    # This would be replaced with actual CDN upload
                    video_url = f"https://your-cdn.com/videos/{media['reference_id']}.mp4"
                elif media["type"] == "image" and not image_url:
                    # This would be replaced with actual CDN upload
                    image_url = f"https://your-cdn.com/images/{media['reference_id']}.jpg"
            
            # Create media container
            container_result = await self.instagram_service.create_media_container(
                user_id=user_id,
                account_id=account_id,
                image_url=image_url,
                video_url=video_url,
                caption=caption
            )
            
            if not container_result.get("success"):
                error_msg = container_result.get("error", "Container creation failed")
                logger.error(f"[Instagram Upload] Container creation failed: {error_msg}")
                
                await client.table("instagram_posts").update({
                    "post_status": "failed",
                    "status_message": f"Container creation failed: {error_msg}",
                    "error_details": container_result.get("errors", {})
                }).eq("id", post_record_id).execute()
                return
            
            container_id = container_result["container_id"]
            logger.info(f"[Instagram Upload Background] Container created: {container_id}")
            
            # Update status to publishing
            await client.table("instagram_posts").update({
                "post_status": "publishing",
                "status_message": "Publishing to Instagram...",
                "container_id": container_id
            }).eq("id", post_record_id).execute()
            
            # Publish the media
            publish_result = await self.instagram_service.publish_media(
                user_id=user_id,
                account_id=account_id,
                container_id=container_id
            )
            
            if publish_result.get("success"):
                media_id = publish_result["media_id"]
                media_url = publish_result["url"]
                
                logger.info(f"[Instagram Upload Background] Post published successfully: {media_id}")
                
                # Update post record with success
                await client.table("instagram_posts").update({
                    "post_status": "completed",
                    "media_id": media_id,
                    "media_url": media_url,
                    "status_message": "Post published successfully",
                    "completed_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", post_record_id).execute()
                
                logger.info(f"[Instagram Upload Background] Complete! Media ID: {media_id} - {media_url}")
                
            else:
                error_msg = publish_result.get("error", "Publishing failed")
                logger.error(f"[Instagram Upload] Post publishing failed: {error_msg}")
                
                await client.table("instagram_posts").update({
                    "post_status": "failed",
                    "status_message": f"Publishing failed: {error_msg}",
                    "error_details": publish_result.get("errors", {})
                }).eq("id", post_record_id).execute()
                
        except Exception as post_error:
            logger.error(f"[Instagram Upload] Post creation failed: {post_error}", exc_info=True)
            
            # Update post record with failure
            await client.table("instagram_posts").update({
                "post_status": "failed",
                "status_message": f"Post creation failed: {str(post_error)}"
            }).eq("id", post_record_id).execute()
    
    async def create_story(self, user_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create an Instagram story"""
        
        logger.info(f"[Instagram Story] Starting story creation for user {user_id}")
        account_id = params["account_id"]
        
        # Import file service for automatic discovery
        from services.youtube_file_service import YouTubeFileService
        file_service = YouTubeFileService(self.db, user_id)
        
        # Auto-discover media files
        auto_discover = params.get("auto_discover", True)
        media_url = None
        discovered_files = []
        
        if auto_discover:
            uploads = await file_service.get_latest_pending_uploads(user_id)
            
            # Prefer video for stories
            if uploads.get("video"):
                discovered_files.append({"type": "video", "name": uploads["video"]["file_name"]})
                media_url = f"https://your-cdn.com/videos/{uploads['video']['reference_id']}.mp4"
            elif uploads.get("thumbnail"):
                discovered_files.append({"type": "image", "name": uploads["thumbnail"]["file_name"]})
                media_url = f"https://your-cdn.com/images/{uploads['thumbnail']['reference_id']}.jpg"
        
        if not media_url:
            return {
                "success": False,
                "error": "No media found for story creation. Please upload an image or video."
            }
        
        try:
            # Get account info
            client = await self.db.client
            account_result = await client.table("instagram_accounts").select("username, name").eq(
                "user_id", user_id
            ).eq("id", account_id).execute()
            
            if not account_result.data:
                raise Exception(f"Instagram account {account_id} not found")
            
            account_username = account_result.data[0]["username"]
            
            # Create story
            if discovered_files[0]["type"] == "video":
                story_result = await self.instagram_service.create_story(
                    user_id=user_id,
                    account_id=account_id,
                    video_url=media_url
                )
            else:
                story_result = await self.instagram_service.create_story(
                    user_id=user_id,
                    account_id=account_id,
                    image_url=media_url
                )
            
            if story_result.get("success"):
                logger.info(f"[Instagram Story] Story created successfully: {story_result['story_id']}")
                
                return {
                    "success": True,
                    "story_id": story_result["story_id"],
                    "account_username": account_username,
                    "message": f"Story published to @{account_username}",
                    "discovered_files": discovered_files
                }
            else:
                return story_result
                
        except Exception as e:
            logger.error(f"[Instagram Story] Failed to create story: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_post_status(self, user_id: str, post_record_id: str) -> Dict[str, Any]:
        """Get the status of a post creation"""
        client = await self.db.client
        
        result = await client.table("instagram_posts").select("*").eq(
            "user_id", user_id
        ).eq("id", post_record_id).execute()
        
        if not result.data:
            raise Exception(f"Post record {post_record_id} not found")
        
        post = result.data[0]
        
        return {
            "post_record_id": post["id"],
            "caption": post["caption"],
            "status": post["post_status"],
            "media_id": post.get("media_id"),
            "media_url": post.get("media_url"),
            "message": post.get("status_message", ""),
            "created_at": post.get("created_at"),
            "completed_at": post.get("completed_at"),
            "error_details": post.get("error_details", {})
        }
    
    async def delete_post(self, user_id: str, account_id: str, media_id: str) -> Dict[str, Any]:
        """Delete an Instagram post"""
        try:
            # Delete via Instagram API
            delete_result = await self.instagram_service.delete_media(user_id, account_id, media_id)
            
            if delete_result.get("success"):
                # Update local record
                client = await self.db.client
                await client.table("instagram_posts").update({
                    "post_status": "deleted",
                    "status_message": "Post deleted",
                    "deleted_at": datetime.now(timezone.utc).isoformat()
                }).eq("user_id", user_id).eq("media_id", media_id).execute()
                
                logger.info(f"Instagram post {media_id} deleted successfully")
                
                return {
                    "success": True,
                    "media_id": media_id,
                    "message": "Post deleted successfully"
                }
            else:
                return delete_result
                
        except Exception as e:
            logger.error(f"Failed to delete Instagram post {media_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_recent_posts(self, user_id: str, account_id: str, limit: int = 25) -> Dict[str, Any]:
        """Get recent posts from user's Instagram"""
        try:
            posts_result = await self.instagram_service.get_user_media(
                user_id, account_id, limit=limit
            )
            
            if posts_result.get("success"):
                return {
                    "success": True,
                    "posts": posts_result["media"],
                    "count": len(posts_result["media"]),
                    "paging": posts_result.get("paging", {})
                }
            else:
                return posts_result
                
        except Exception as e:
            logger.error(f"Failed to get recent Instagram posts: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_post_insights(self, user_id: str, account_id: str, media_id: str) -> Dict[str, Any]:
        """Get insights for an Instagram post (requires business account)"""
        try:
            insights_result = await self.instagram_service.get_media_insights(
                user_id, account_id, media_id
            )
            
            if insights_result.get("success"):
                return {
                    "success": True,
                    "media_id": media_id,
                    "insights": insights_result["insights"]
                }
            else:
                return insights_result
                
        except Exception as e:
            logger.error(f"Failed to get Instagram post insights: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_hashtag_posts(self, user_id: str, account_id: str, hashtag: str, limit: int = 25) -> Dict[str, Any]:
        """Search for posts by hashtag (requires business account)"""
        try:
            search_result = await self.instagram_service.get_hashtag_media(
                user_id, account_id, hashtag, limit
            )
            
            if search_result.get("success"):
                return {
                    "success": True,
                    "hashtag": hashtag,
                    "posts": search_result["media"],
                    "count": len(search_result["media"])
                }
            else:
                return search_result
                
        except Exception as e:
            logger.error(f"Failed to search Instagram hashtag posts: {e}")
            return {
                "success": False,
                "error": str(e)
            }