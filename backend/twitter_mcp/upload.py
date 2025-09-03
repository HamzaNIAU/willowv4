"""Twitter Upload Service - Handles tweet creation and media uploads"""

import os
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from services.supabase import DBConnection
from utils.logger import logger
from .oauth import TwitterOAuthHandler
from .twitter_service import TwitterAPIService


class TwitterUploadService:
    """Service for uploading tweets and media to Twitter"""
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.oauth_handler = TwitterOAuthHandler(db)
        self.twitter_service = TwitterAPIService(db)
    
    async def create_tweet(self, user_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a tweet with intelligent auto-discovery"""
        
        logger.info(f"[Twitter Upload] Starting tweet creation for user {user_id} with params: {params}")
        account_id = params["account_id"]
        
        # Import file service for automatic discovery
        from services.youtube_file_service import YouTubeFileService  # Reuse the file service
        file_service = YouTubeFileService(self.db, user_id)
        
        # Check if auto-discovery is enabled
        auto_discover = params.get("auto_discover", True)
        video_reference_id = params.get("video_reference_id")
        image_reference_ids = params.get("image_reference_ids", [])
        
        logger.info(f"[Twitter Upload] Auto-discover: {auto_discover}, Video ref: {video_reference_id}, Image refs: {image_reference_ids}")
        
        # Auto-discover media files if enabled
        media_ids = []
        discovered_files = []
        
        if auto_discover:
            logger.info(f"[Twitter Upload] Auto-discovery enabled - looking for recent uploads for user {user_id}")
            uploads = await file_service.get_latest_pending_uploads(user_id)
            
            logger.info(f"[Twitter Upload] Found uploads: Video={bool(uploads.get('video'))}, Thumbnail={bool(uploads.get('thumbnail'))}")
            
            # Upload video if found
            if uploads.get("video"):
                video_data = await file_service.get_file_data(uploads["video"]["reference_id"], user_id)
                if video_data:
                    media_result = await self.twitter_service.upload_media(
                        user_id, account_id, video_data, "video/mp4"
                    )
                    if media_result.get("success"):
                        media_ids.append(media_result["media_id"])
                        discovered_files.append({"type": "video", "name": uploads["video"]["file_name"]})
                        logger.info(f"[Twitter Upload] Auto-uploaded video: {uploads['video']['file_name']}")
            
            # Upload thumbnail/image if found
            if uploads.get("thumbnail"):
                image_data = await file_service.get_file_data(uploads["thumbnail"]["reference_id"], user_id)
                if image_data:
                    media_result = await self.twitter_service.upload_media(
                        user_id, account_id, image_data, "image/jpeg"
                    )
                    if media_result.get("success"):
                        media_ids.append(media_result["media_id"])
                        discovered_files.append({"type": "image", "name": uploads["thumbnail"]["file_name"]})
                        logger.info(f"[Twitter Upload] Auto-uploaded image: {uploads['thumbnail']['file_name']}")
        
        # Upload specific reference files if provided
        if video_reference_id:
            video_data = await file_service.get_file_data(video_reference_id, user_id)
            if video_data:
                media_result = await self.twitter_service.upload_media(
                    user_id, account_id, video_data, "video/mp4"
                )
                if media_result.get("success"):
                    media_ids.append(media_result["media_id"])
        
        for img_ref_id in image_reference_ids:
            image_data = await file_service.get_file_data(img_ref_id, user_id)
            if image_data:
                media_result = await self.twitter_service.upload_media(
                    user_id, account_id, image_data, "image/jpeg"
                )
                if media_result.get("success"):
                    media_ids.append(media_result["media_id"])
        
        # Get valid access token for account validation
        try:
            await self.oauth_handler.get_valid_token(user_id, account_id)
        except Exception as e:
            raise Exception(f"Twitter account {account_id} authentication failed: {str(e)}")
        
        # Get account info
        client = await self.db.client
        account_result = await client.table("twitter_accounts").select("name, username").eq(
            "user_id", user_id
        ).eq("id", account_id).execute()
        
        if not account_result.data:
            raise Exception(f"Twitter account {account_id} not found")
        
        account_name = account_result.data[0]["name"]
        account_username = account_result.data[0]["username"]
        
        # Create tweet record for tracking
        tweet_record_id = str(uuid.uuid4())
        tweet_data = {
            "id": tweet_record_id,
            "user_id": user_id,
            "account_id": account_id,
            "text": params["text"],
            "media_ids": media_ids,
            "reply_to_tweet_id": params.get("reply_to_tweet_id"),
            "quote_tweet_id": params.get("quote_tweet_id"),
            "tweet_status": "pending",
            "video_reference_id": video_reference_id,
            "image_reference_ids": image_reference_ids,
        }
        
        result = await client.table("twitter_tweets").insert(tweet_data).execute()
        
        if not result.data:
            raise Exception("Failed to create tweet record")
        
        # Mark references as used
        references_to_mark = []
        if video_reference_id:
            references_to_mark.append(video_reference_id)
        references_to_mark.extend(image_reference_ids)
        
        if references_to_mark:
            await file_service.mark_references_as_used(references_to_mark)
        
        # Return immediately and process tweet creation in background
        try:
            logger.info(f"[Twitter Upload] Starting background tweet creation")
            
            # Update status to posting
            await client.table("twitter_tweets").update({
                "tweet_status": "posting", 
                "status_message": "Creating tweet..."
            }).eq("id", tweet_record_id).execute()
            
            # Start background task for actual tweet creation
            asyncio.create_task(self._create_tweet_background(
                tweet_record_id, user_id, account_id, account_name, account_username,
                params, media_ids, discovered_files
            ))
            
            # Return immediately to prevent connection timeout
            return {
                "tweet_record_id": tweet_record_id,
                "account_name": account_name,
                "account_username": account_username,
                "status": "posting",
                "message": f"Tweet creation started for @{account_username} - processing in background",
                "media_count": len(media_ids),
                "discovered_files": discovered_files,
                "automatic_discovery": auto_discover and bool(discovered_files)
            }
            
        except Exception as upload_error:
            logger.error(f"[Twitter Upload] Failed to start tweet creation: {upload_error}", exc_info=True)
            
            # Update tweet record with failure
            await client.table("twitter_tweets").update({
                "tweet_status": "failed",
                "status_message": f"Failed to start tweet creation: {str(upload_error)}"
            }).eq("id", tweet_record_id).execute()
            
            raise Exception(f"Failed to create tweet: {str(upload_error)}")
    
    async def _create_tweet_background(
        self,
        tweet_record_id: str,
        user_id: str,
        account_id: str,
        account_name: str,
        account_username: str,
        params: dict,
        media_ids: List[str],
        discovered_files: List[Dict[str, str]]
    ):
        """Perform the actual tweet creation in background"""
        client = await self.db.client
        
        try:
            logger.info(f"[Twitter Upload Background] Starting actual tweet creation for '{params['text'][:50]}...'")
            
            # Update status to actively posting
            await client.table("twitter_tweets").update({
                "tweet_status": "posting",
                "status_message": "Posting to Twitter..."
            }).eq("id", tweet_record_id).execute()
            
            # Create the tweet
            tweet_result = await self.twitter_service.create_tweet(
                user_id=user_id,
                account_id=account_id,
                text=params["text"],
                media_ids=media_ids if media_ids else None,
                reply_to_tweet_id=params.get("reply_to_tweet_id"),
                quote_tweet_id=params.get("quote_tweet_id")
            )
            
            if tweet_result.get("success"):
                tweet_id = tweet_result["tweet_id"]
                tweet_url = tweet_result["url"]
                
                logger.info(f"[Twitter Upload Background] Tweet created successfully: {tweet_id}")
                
                # Update tweet record with success
                await client.table("twitter_tweets").update({
                    "tweet_status": "completed",
                    "tweet_id": tweet_id,
                    "tweet_url": tweet_url,
                    "status_message": "Tweet posted successfully",
                    "completed_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", tweet_record_id).execute()
                
                logger.info(f"[Twitter Upload Background] Complete! Tweet ID: {tweet_id} - {tweet_url}")
                
            else:
                error_msg = tweet_result.get("error", "Unknown error")
                logger.error(f"[Twitter Upload] Tweet creation failed: {error_msg}")
                
                await client.table("twitter_tweets").update({
                    "tweet_status": "failed",
                    "status_message": f"Tweet creation failed: {error_msg}",
                    "error_details": tweet_result.get("errors", [])
                }).eq("id", tweet_record_id).execute()
                
        except Exception as tweet_error:
            logger.error(f"[Twitter Upload] Tweet creation failed: {tweet_error}", exc_info=True)
            
            # Update tweet record with failure
            await client.table("twitter_tweets").update({
                "tweet_status": "failed",
                "status_message": f"Tweet creation failed: {str(tweet_error)}"
            }).eq("id", tweet_record_id).execute()
    
    async def get_tweet_status(self, user_id: str, tweet_record_id: str) -> Dict[str, Any]:
        """Get the status of a tweet creation"""
        client = await self.db.client
        
        result = await client.table("twitter_tweets").select("*").eq(
            "user_id", user_id
        ).eq("id", tweet_record_id).execute()
        
        if not result.data:
            raise Exception(f"Tweet record {tweet_record_id} not found")
        
        tweet = result.data[0]
        
        return {
            "tweet_record_id": tweet["id"],
            "text": tweet["text"],
            "status": tweet["tweet_status"],
            "tweet_id": tweet.get("tweet_id"),
            "tweet_url": tweet.get("tweet_url"),
            "message": tweet.get("status_message", ""),
            "created_at": tweet.get("created_at"),
            "completed_at": tweet.get("completed_at"),
            "error_details": tweet.get("error_details", [])
        }
    
    async def delete_tweet(self, user_id: str, account_id: str, tweet_id: str) -> Dict[str, Any]:
        """Delete a tweet"""
        try:
            # Delete via Twitter API
            delete_result = await self.twitter_service.delete_tweet(user_id, account_id, tweet_id)
            
            if delete_result.get("success"):
                # Update local record
                client = await self.db.client
                await client.table("twitter_tweets").update({
                    "tweet_status": "deleted",
                    "status_message": "Tweet deleted",
                    "deleted_at": datetime.now(timezone.utc).isoformat()
                }).eq("user_id", user_id).eq("tweet_id", tweet_id).execute()
                
                logger.info(f"Tweet {tweet_id} deleted successfully")
                
                return {
                    "success": True,
                    "tweet_id": tweet_id,
                    "message": "Tweet deleted successfully"
                }
            else:
                return delete_result
                
        except Exception as e:
            logger.error(f"Failed to delete tweet {tweet_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_recent_tweets(self, user_id: str, account_id: str, limit: int = 10) -> Dict[str, Any]:
        """Get recent tweets from user's timeline"""
        try:
            tweets_result = await self.twitter_service.get_user_tweets(
                user_id, account_id, max_results=limit
            )
            
            if tweets_result.get("success"):
                return {
                    "success": True,
                    "tweets": tweets_result["tweets"],
                    "users": tweets_result.get("users", []),
                    "count": len(tweets_result["tweets"])
                }
            else:
                return tweets_result
                
        except Exception as e:
            logger.error(f"Failed to get recent tweets: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_tweets(self, user_id: str, account_id: str, query: str, max_results: int = 10) -> Dict[str, Any]:
        """Search for tweets"""
        try:
            search_result = await self.twitter_service.search_tweets(
                user_id, account_id, query, max_results
            )
            
            if search_result.get("success"):
                return {
                    "success": True,
                    "tweets": search_result["tweets"],
                    "users": search_result.get("users", []),
                    "query": query,
                    "count": len(search_result["tweets"])
                }
            else:
                return search_result
                
        except Exception as e:
            logger.error(f"Failed to search tweets: {e}")
            return {
                "success": False,
                "error": str(e)
            }