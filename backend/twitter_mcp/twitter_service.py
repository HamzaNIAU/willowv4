"""Twitter API Service - Handles Twitter API v2 interactions"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

import aiohttp

from services.supabase import DBConnection
from utils.logger import logger
from .oauth import TwitterOAuthHandler


class TwitterAPIService:
    """Service for interacting with Twitter API v2"""
    
    BASE_URL = "https://api.twitter.com/2"
    UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.oauth_handler = TwitterOAuthHandler(db)
    
    async def create_tweet(
        self,
        user_id: str,
        account_id: str,
        text: str,
        media_ids: Optional[List[str]] = None,
        reply_to_tweet_id: Optional[str] = None,
        quote_tweet_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new tweet"""
        
        # Get valid access token
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        # Prepare tweet data
        tweet_data = {
            "text": text
        }
        
        if media_ids:
            tweet_data["media"] = {
                "media_ids": media_ids
            }
        
        if reply_to_tweet_id:
            tweet_data["reply"] = {
                "in_reply_to_tweet_id": reply_to_tweet_id
            }
        
        if quote_tweet_id:
            tweet_data["quote_tweet_id"] = quote_tweet_id
        
        # Make API request
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with session.post(
                f"{self.BASE_URL}/tweets",
                headers=headers,
                json=tweet_data
            ) as response:
                if response.status == 201:
                    result = await response.json()
                    tweet_id = result["data"]["id"]
                    tweet_text = result["data"]["text"]
                    
                    logger.info(f"Tweet created successfully: {tweet_id}")
                    
                    return {
                        "success": True,
                        "tweet_id": tweet_id,
                        "text": tweet_text,
                        "url": f"https://twitter.com/{account_id}/status/{tweet_id}",
                        "data": result["data"]
                    }
                else:
                    error_data = await response.json()
                    logger.error(f"Failed to create tweet: {error_data}")
                    
                    return {
                        "success": False,
                        "error": error_data.get("detail", "Unknown error"),
                        "errors": error_data.get("errors", [])
                    }
    
    async def upload_media(
        self,
        user_id: str,
        account_id: str,
        media_data: bytes,
        media_type: str,
        alt_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload media to Twitter for use in tweets"""
        
        # Get valid access token
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        media_category = self._get_media_category(media_type)
        
        try:
            # For large files, use chunked upload
            if len(media_data) > 5 * 1024 * 1024:  # 5MB threshold
                return await self._chunked_media_upload(
                    access_token, media_data, media_type, media_category, alt_text
                )
            else:
                return await self._simple_media_upload(
                    access_token, media_data, media_type, media_category, alt_text
                )
        
        except Exception as e:
            logger.error(f"Media upload failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _simple_media_upload(
        self,
        access_token: str,
        media_data: bytes,
        media_type: str,
        media_category: str,
        alt_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """Simple media upload for small files"""
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {access_token}"
            }
            
            data = aiohttp.FormData()
            data.add_field("media", media_data, content_type=media_type)
            data.add_field("media_category", media_category)
            
            async with session.post(
                self.UPLOAD_URL,
                headers=headers,
                data=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    media_id = result["media_id_string"]
                    
                    # Add alt text if provided
                    if alt_text:
                        await self._add_alt_text(access_token, media_id, alt_text)
                    
                    logger.info(f"Media uploaded successfully: {media_id}")
                    
                    return {
                        "success": True,
                        "media_id": media_id,
                        "size": result.get("size", 0),
                        "expires_after_secs": result.get("expires_after_secs"),
                        "image": result.get("image", {})
                    }
                else:
                    error_data = await response.json()
                    return {
                        "success": False,
                        "error": error_data.get("message", "Upload failed")
                    }
    
    async def _chunked_media_upload(
        self,
        access_token: str,
        media_data: bytes,
        media_type: str,
        media_category: str,
        alt_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """Chunked media upload for large files"""
        
        total_bytes = len(media_data)
        chunk_size = 5 * 1024 * 1024  # 5MB chunks
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {access_token}"
            }
            
            # INIT phase
            init_data = aiohttp.FormData()
            init_data.add_field("command", "INIT")
            init_data.add_field("total_bytes", str(total_bytes))
            init_data.add_field("media_type", media_type)
            init_data.add_field("media_category", media_category)
            
            async with session.post(self.UPLOAD_URL, headers=headers, data=init_data) as response:
                if response.status != 202:
                    error_data = await response.json()
                    return {"success": False, "error": error_data.get("message", "Init failed")}
                
                init_result = await response.json()
                media_id = init_result["media_id_string"]
            
            # APPEND phases
            segment_index = 0
            for i in range(0, total_bytes, chunk_size):
                chunk = media_data[i:i + chunk_size]
                
                append_data = aiohttp.FormData()
                append_data.add_field("command", "APPEND")
                append_data.add_field("media_id", media_id)
                append_data.add_field("segment_index", str(segment_index))
                append_data.add_field("media", chunk)
                
                async with session.post(self.UPLOAD_URL, headers=headers, data=append_data) as response:
                    if response.status != 204:
                        error_data = await response.json()
                        return {"success": False, "error": f"Chunk {segment_index} failed"}
                
                segment_index += 1
                
                # Progress logging
                progress = min(100, (i + len(chunk)) * 100 // total_bytes)
                logger.info(f"Upload progress: {progress}%")
            
            # FINALIZE phase
            finalize_data = aiohttp.FormData()
            finalize_data.add_field("command", "FINALIZE")
            finalize_data.add_field("media_id", media_id)
            
            async with session.post(self.UPLOAD_URL, headers=headers, data=finalize_data) as response:
                if response.status != 201:
                    error_data = await response.json()
                    return {"success": False, "error": "Finalize failed"}
                
                result = await response.json()
                
                # Check for processing (for videos)
                if "processing_info" in result:
                    await self._wait_for_processing(access_token, media_id, session, headers)
                
                # Add alt text if provided
                if alt_text:
                    await self._add_alt_text(access_token, media_id, alt_text)
                
                logger.info(f"Chunked media upload completed: {media_id}")
                
                return {
                    "success": True,
                    "media_id": media_id,
                    "size": result.get("size", total_bytes),
                    "expires_after_secs": result.get("expires_after_secs"),
                    "processing_info": result.get("processing_info")
                }
    
    async def _wait_for_processing(
        self,
        access_token: str,
        media_id: str,
        session: aiohttp.ClientSession,
        headers: Dict[str, str],
        max_wait_time: int = 300
    ):
        """Wait for media processing to complete"""
        
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < max_wait_time:
            status_params = {
                "command": "STATUS",
                "media_id": media_id
            }
            
            async with session.get(
                self.UPLOAD_URL,
                headers=headers,
                params=status_params
            ) as response:
                if response.status == 200:
                    status_data = await response.json()
                    processing_info = status_data.get("processing_info", {})
                    state = processing_info.get("state")
                    
                    if state == "succeeded":
                        logger.info(f"Media processing completed: {media_id}")
                        return
                    elif state == "failed":
                        error = processing_info.get("error", {})
                        logger.error(f"Media processing failed: {error}")
                        return
                    
                    # Still processing, wait before checking again
                    check_after_secs = processing_info.get("check_after_secs", 5)
                    await asyncio.sleep(check_after_secs)
                else:
                    logger.warning("Failed to check processing status")
                    await asyncio.sleep(5)
        
        logger.warning(f"Media processing timeout for {media_id}")
    
    async def _add_alt_text(self, access_token: str, media_id: str, alt_text: str):
        """Add alt text to uploaded media"""
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            metadata = {
                "media_id": media_id,
                "alt_text": {
                    "text": alt_text
                }
            }
            
            async with session.post(
                f"{self.UPLOAD_URL}/metadata/create.json",
                headers=headers,
                json=metadata
            ) as response:
                if response.status == 200:
                    logger.info(f"Alt text added to media {media_id}")
                else:
                    logger.warning(f"Failed to add alt text to media {media_id}")
    
    def _get_media_category(self, media_type: str) -> str:
        """Get Twitter media category based on MIME type"""
        if media_type.startswith("image/"):
            return "tweet_image"
        elif media_type.startswith("video/"):
            return "tweet_video"
        elif media_type.startswith("application/") or media_type == "image/gif":
            return "tweet_gif"
        else:
            return "tweet_image"  # Default fallback
    
    async def get_tweet(
        self,
        user_id: str,
        account_id: str,
        tweet_id: str,
        expansions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get a specific tweet by ID"""
        
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        params = {
            "tweet.fields": "id,text,author_id,created_at,public_metrics,context_annotations,entities,geo,in_reply_to_user_id,lang,possibly_sensitive,referenced_tweets,reply_settings,source,withheld"
        }
        
        if expansions:
            params["expansions"] = ",".join(expansions)
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {access_token}"
            }
            
            async with session.get(
                f"{self.BASE_URL}/tweets/{tweet_id}",
                headers=headers,
                params=params
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "tweet": result["data"]
                    }
                else:
                    error_data = await response.json()
                    return {
                        "success": False,
                        "error": error_data.get("detail", "Tweet not found")
                    }
    
    async def delete_tweet(self, user_id: str, account_id: str, tweet_id: str) -> Dict[str, Any]:
        """Delete a tweet"""
        
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {access_token}"
            }
            
            async with session.delete(
                f"{self.BASE_URL}/tweets/{tweet_id}",
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "deleted": result["data"]["deleted"]
                    }
                else:
                    error_data = await response.json()
                    return {
                        "success": False,
                        "error": error_data.get("detail", "Failed to delete tweet")
                    }
    
    async def get_user_tweets(
        self,
        user_id: str,
        account_id: str,
        target_user_id: Optional[str] = None,
        max_results: int = 10
    ) -> Dict[str, Any]:
        """Get tweets from a user timeline"""
        
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        # If no target_user_id provided, get tweets from the authenticated user
        if not target_user_id:
            target_user_id = account_id
        
        params = {
            "max_results": min(max_results, 100),  # Twitter API limit
            "tweet.fields": "id,text,author_id,created_at,public_metrics,referenced_tweets",
            "user.fields": "id,name,username,profile_image_url,verified",
            "expansions": "author_id"
        }
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {access_token}"
            }
            
            async with session.get(
                f"{self.BASE_URL}/users/{target_user_id}/tweets",
                headers=headers,
                params=params
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "tweets": result.get("data", []),
                        "users": result.get("includes", {}).get("users", []),
                        "meta": result.get("meta", {})
                    }
                else:
                    error_data = await response.json()
                    return {
                        "success": False,
                        "error": error_data.get("detail", "Failed to get tweets")
                    }
    
    async def search_tweets(
        self,
        user_id: str,
        account_id: str,
        query: str,
        max_results: int = 10
    ) -> Dict[str, Any]:
        """Search for tweets"""
        
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        params = {
            "query": query,
            "max_results": min(max_results, 100),
            "tweet.fields": "id,text,author_id,created_at,public_metrics,context_annotations",
            "user.fields": "id,name,username,profile_image_url,verified",
            "expansions": "author_id"
        }
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {access_token}"
            }
            
            async with session.get(
                f"{self.BASE_URL}/tweets/search/recent",
                headers=headers,
                params=params
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "tweets": result.get("data", []),
                        "users": result.get("includes", {}).get("users", []),
                        "meta": result.get("meta", {})
                    }
                else:
                    error_data = await response.json()
                    return {
                        "success": False,
                        "error": error_data.get("detail", "Search failed")
                    }
    
    async def get_user_followers(
        self,
        user_id: str,
        account_id: str,
        target_user_id: Optional[str] = None,
        max_results: int = 100
    ) -> Dict[str, Any]:
        """Get followers of a user"""
        
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        if not target_user_id:
            target_user_id = account_id
        
        params = {
            "max_results": min(max_results, 1000),
            "user.fields": "id,name,username,description,profile_image_url,public_metrics,verified"
        }
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {access_token}"
            }
            
            async with session.get(
                f"{self.BASE_URL}/users/{target_user_id}/followers",
                headers=headers,
                params=params
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "users": result.get("data", []),
                        "meta": result.get("meta", {})
                    }
                else:
                    error_data = await response.json()
                    return {
                        "success": False,
                        "error": error_data.get("detail", "Failed to get followers")
                    }