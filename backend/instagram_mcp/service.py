"""Instagram API Service - Handles Instagram Graph API interactions"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

import aiohttp

from services.supabase import DBConnection
from utils.logger import logger
from .oauth import InstagramOAuthHandler


class InstagramAPIService:
    """Service for interacting with Instagram Graph API"""
    
    BASE_URL = "https://graph.instagram.com"
    CONTENT_PUBLISHING_API = "https://graph.instagram.com"
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.oauth_handler = InstagramOAuthHandler(db)
    
    async def create_media_container(
        self,
        user_id: str,
        account_id: str,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
        caption: Optional[str] = None,
        location_id: Optional[str] = None,
        user_tags: Optional[List[Dict[str, Any]]] = None,
        children: Optional[List[str]] = None  # For carousel posts
    ) -> Dict[str, Any]:
        """Create a media container for publishing"""
        
        # Get valid access token
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        # Prepare media data
        media_data = {}
        
        if children:
            # Carousel post
            media_data["media_type"] = "CAROUSEL"
            media_data["children"] = ",".join(children)
        elif video_url:
            media_data["media_type"] = "VIDEO"
            media_data["video_url"] = video_url
        elif image_url:
            media_data["media_type"] = "IMAGE"
            media_data["image_url"] = image_url
        else:
            return {
                "success": False,
                "error": "Either image_url, video_url, or children must be provided"
            }
        
        if caption:
            media_data["caption"] = caption
        
        if location_id:
            media_data["location_id"] = location_id
        
        if user_tags:
            media_data["user_tags"] = json.dumps(user_tags)
        
        media_data["access_token"] = access_token
        
        # Make API request
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/{account_id}/media",
                data=media_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    container_id = result["id"]
                    
                    logger.info(f"Media container created successfully: {container_id}")
                    
                    return {
                        "success": True,
                        "container_id": container_id,
                        "data": result
                    }
                else:
                    error_data = await response.json()
                    logger.error(f"Failed to create media container: {error_data}")
                    
                    return {
                        "success": False,
                        "error": error_data.get("error", {}).get("message", "Unknown error"),
                        "errors": error_data.get("error", {})
                    }
    
    async def publish_media(
        self,
        user_id: str,
        account_id: str,
        container_id: str
    ) -> Dict[str, Any]:
        """Publish a media container to Instagram"""
        
        # Get valid access token
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        data = {
            "creation_id": container_id,
            "access_token": access_token
        }
        
        # Make API request
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/{account_id}/media_publish",
                data=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    media_id = result["id"]
                    
                    logger.info(f"Media published successfully: {media_id}")
                    
                    return {
                        "success": True,
                        "media_id": media_id,
                        "url": f"https://www.instagram.com/p/{media_id}",
                        "data": result
                    }
                else:
                    error_data = await response.json()
                    logger.error(f"Failed to publish media: {error_data}")
                    
                    return {
                        "success": False,
                        "error": error_data.get("error", {}).get("message", "Publish failed"),
                        "errors": error_data.get("error", {})
                    }
    
    async def create_story(
        self,
        user_id: str,
        account_id: str,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create an Instagram Story"""
        
        # Get valid access token
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        # Prepare story data
        story_data = {
            "media_type": "STORIES"
        }
        
        if video_url:
            story_data["video_url"] = video_url
        elif image_url:
            story_data["image_url"] = image_url
        else:
            return {
                "success": False,
                "error": "Either image_url or video_url must be provided for story"
            }
        
        story_data["access_token"] = access_token
        
        # Make API request to create story container
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/{account_id}/media",
                data=story_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    container_id = result["id"]
                    
                    # Publish the story
                    publish_result = await self.publish_media(user_id, account_id, container_id)
                    
                    if publish_result["success"]:
                        return {
                            "success": True,
                            "story_id": publish_result["media_id"],
                            "container_id": container_id,
                            "message": "Story published successfully"
                        }
                    else:
                        return publish_result
                else:
                    error_data = await response.json()
                    logger.error(f"Failed to create story: {error_data}")
                    
                    return {
                        "success": False,
                        "error": error_data.get("error", {}).get("message", "Story creation failed"),
                        "errors": error_data.get("error", {})
                    }
    
    async def get_media(
        self,
        user_id: str,
        account_id: str,
        media_id: str,
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get Instagram media by ID"""
        
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        default_fields = [
            "id", "caption", "media_type", "media_url", "permalink",
            "thumbnail_url", "timestamp", "like_count", "comments_count"
        ]
        
        params = {
            "fields": ",".join(fields or default_fields),
            "access_token": access_token
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/{media_id}",
                params=params
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "media": result
                    }
                else:
                    error_data = await response.json()
                    return {
                        "success": False,
                        "error": error_data.get("error", {}).get("message", "Media not found")
                    }
    
    async def get_user_media(
        self,
        user_id: str,
        account_id: str,
        limit: int = 25,
        before: Optional[str] = None,
        after: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get user's Instagram media"""
        
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        params = {
            "fields": "id,caption,media_type,media_url,permalink,thumbnail_url,timestamp,like_count,comments_count",
            "limit": min(limit, 100),  # Instagram API limit
            "access_token": access_token
        }
        
        if before:
            params["before"] = before
        if after:
            params["after"] = after
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/{account_id}/media",
                params=params
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "media": result.get("data", []),
                        "paging": result.get("paging", {})
                    }
                else:
                    error_data = await response.json()
                    return {
                        "success": False,
                        "error": error_data.get("error", {}).get("message", "Failed to get media")
                    }
    
    async def get_media_insights(
        self,
        user_id: str,
        account_id: str,
        media_id: str,
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get insights for Instagram media (requires business account)"""
        
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        # Default metrics for different media types
        default_metrics = [
            "impressions", "reach", "engagement", "saved", "video_views"
        ]
        
        params = {
            "metric": ",".join(metrics or default_metrics),
            "access_token": access_token
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/{media_id}/insights",
                params=params
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "insights": result.get("data", [])
                    }
                else:
                    error_data = await response.json()
                    return {
                        "success": False,
                        "error": error_data.get("error", {}).get("message", "Failed to get insights")
                    }
    
    async def get_hashtag_media(
        self,
        user_id: str,
        account_id: str,
        hashtag_name: str,
        limit: int = 25
    ) -> Dict[str, Any]:
        """Search for recent media by hashtag (requires business account)"""
        
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        # First, get the hashtag ID
        hashtag_params = {
            "q": hashtag_name,
            "access_token": access_token
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/ig_hashtag_search",
                params=hashtag_params
            ) as response:
                if response.status != 200:
                    error_data = await response.json()
                    return {
                        "success": False,
                        "error": error_data.get("error", {}).get("message", "Hashtag search failed")
                    }
                
                hashtag_result = await response.json()
                if not hashtag_result.get("data"):
                    return {
                        "success": False,
                        "error": f"Hashtag #{hashtag_name} not found"
                    }
                
                hashtag_id = hashtag_result["data"][0]["id"]
            
            # Get recent media for the hashtag
            media_params = {
                "user_id": account_id,
                "fields": "id,media_type,media_url,permalink,timestamp,caption",
                "limit": min(limit, 50),
                "access_token": access_token
            }
            
            async with session.get(
                f"{self.BASE_URL}/{hashtag_id}/recent_media",
                params=media_params
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "hashtag": hashtag_name,
                        "media": result.get("data", []),
                        "paging": result.get("paging", {})
                    }
                else:
                    error_data = await response.json()
                    return {
                        "success": False,
                        "error": error_data.get("error", {}).get("message", "Failed to get hashtag media")
                    }
    
    async def get_account_insights(
        self,
        user_id: str,
        account_id: str,
        period: str = "day",
        since: Optional[str] = None,
        until: Optional[str] = None,
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get account insights (requires business account)"""
        
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        # Default metrics for account insights
        default_metrics = [
            "impressions", "reach", "profile_views", "website_clicks",
            "follower_count", "email_contacts", "phone_call_clicks",
            "text_message_clicks", "get_directions_clicks"
        ]
        
        params = {
            "metric": ",".join(metrics or default_metrics),
            "period": period,
            "access_token": access_token
        }
        
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/{account_id}/insights",
                params=params
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "insights": result.get("data", []),
                        "period": period
                    }
                else:
                    error_data = await response.json()
                    return {
                        "success": False,
                        "error": error_data.get("error", {}).get("message", "Failed to get account insights")
                    }
    
    async def delete_media(
        self,
        user_id: str,
        account_id: str,
        media_id: str
    ) -> Dict[str, Any]:
        """Delete Instagram media"""
        
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"{self.BASE_URL}/{media_id}",
                params={"access_token": access_token}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "deleted": result.get("success", True)
                    }
                else:
                    error_data = await response.json()
                    return {
                        "success": False,
                        "error": error_data.get("error", {}).get("message", "Failed to delete media")
                    }
    
    async def get_comments(
        self,
        user_id: str,
        account_id: str,
        media_id: str,
        limit: int = 25
    ) -> Dict[str, Any]:
        """Get comments on Instagram media"""
        
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        params = {
            "fields": "id,text,timestamp,username,like_count,replies",
            "limit": min(limit, 100),
            "access_token": access_token
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/{media_id}/comments",
                params=params
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "comments": result.get("data", []),
                        "paging": result.get("paging", {})
                    }
                else:
                    error_data = await response.json()
                    return {
                        "success": False,
                        "error": error_data.get("error", {}).get("message", "Failed to get comments")
                    }
    
    async def reply_to_comment(
        self,
        user_id: str,
        account_id: str,
        comment_id: str,
        message: str
    ) -> Dict[str, Any]:
        """Reply to a comment on Instagram media"""
        
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        data = {
            "message": message,
            "access_token": access_token
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/{comment_id}/replies",
                data=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "reply_id": result["id"]
                    }
                else:
                    error_data = await response.json()
                    return {
                        "success": False,
                        "error": error_data.get("error", {}).get("message", "Failed to reply to comment")
                    }
    
    def _get_media_category(self, media_type: str) -> str:
        """Get Instagram media category based on MIME type"""
        if media_type.startswith("image/"):
            return "IMAGE"
        elif media_type.startswith("video/"):
            return "VIDEO"
        else:
            return "IMAGE"  # Default fallback