"""LinkedIn API Service"""

import aiohttp
import json
import base64
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from utils.logger import logger


class LinkedInAPIService:
    """Service for LinkedIn API interactions"""
    
    def __init__(self):
        self.api_base_url = "https://api.linkedin.com/v2"
        self.upload_base_url = "https://api.linkedin.com/v2"
    
    async def create_text_post(self, access_token: str, user_id: str, text: str, 
                              visibility: str = "PUBLIC") -> Dict[str, Any]:
        """Create a text post on LinkedIn"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Prepare post data using UGC API
            post_data = {
                "author": f"urn:li:person:{user_id}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": text
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": visibility
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/ugcPosts",
                    headers=headers,
                    json=post_data
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
            
            post_id = result.get('id')
            post_url = f"https://www.linkedin.com/feed/update/{post_id}"
            
            logger.info(f"Successfully created LinkedIn text post: {post_id}")
            
            return {
                "post_id": post_id,
                "post_url": post_url,
                "text": text,
                "visibility": visibility,
                "created_at": datetime.utcnow().isoformat(),
                "media_type": "text"
            }
            
        except Exception as e:
            logger.error(f"Failed to create LinkedIn text post: {e}")
            raise
    
    async def create_image_post(self, access_token: str, user_id: str, text: str,
                               image_data: bytes, image_filename: str,
                               visibility: str = "PUBLIC") -> Dict[str, Any]:
        """Create an image post on LinkedIn"""
        try:
            # First, upload the image
            image_urn = await self._upload_image(access_token, user_id, image_data, image_filename)
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Create post with image
            post_data = {
                "author": f"urn:li:person:{user_id}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": text
                        },
                        "shareMediaCategory": "IMAGE",
                        "media": [
                            {
                                "status": "READY",
                                "description": {
                                    "text": f"Image from {image_filename}"
                                },
                                "media": image_urn,
                                "title": {
                                    "text": image_filename
                                }
                            }
                        ]
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": visibility
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/ugcPosts",
                    headers=headers,
                    json=post_data
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
            
            post_id = result.get('id')
            post_url = f"https://www.linkedin.com/feed/update/{post_id}"
            
            logger.info(f"Successfully created LinkedIn image post: {post_id}")
            
            return {
                "post_id": post_id,
                "post_url": post_url,
                "text": text,
                "visibility": visibility,
                "image_urn": image_urn,
                "created_at": datetime.utcnow().isoformat(),
                "media_type": "image"
            }
            
        except Exception as e:
            logger.error(f"Failed to create LinkedIn image post: {e}")
            raise
    
    async def create_video_post(self, access_token: str, user_id: str, text: str,
                               video_data: bytes, video_filename: str,
                               thumbnail_data: Optional[bytes] = None,
                               visibility: str = "PUBLIC") -> Dict[str, Any]:
        """Create a video post on LinkedIn"""
        try:
            # Upload the video
            video_urn = await self._upload_video(access_token, user_id, video_data, video_filename, thumbnail_data)
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Create post with video
            post_data = {
                "author": f"urn:li:person:{user_id}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": text
                        },
                        "shareMediaCategory": "VIDEO",
                        "media": [
                            {
                                "status": "READY",
                                "description": {
                                    "text": f"Video from {video_filename}"
                                },
                                "media": video_urn,
                                "title": {
                                    "text": video_filename
                                }
                            }
                        ]
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": visibility
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/ugcPosts",
                    headers=headers,
                    json=post_data
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
            
            post_id = result.get('id')
            post_url = f"https://www.linkedin.com/feed/update/{post_id}"
            
            logger.info(f"Successfully created LinkedIn video post: {post_id}")
            
            return {
                "post_id": post_id,
                "post_url": post_url,
                "text": text,
                "visibility": visibility,
                "video_urn": video_urn,
                "created_at": datetime.utcnow().isoformat(),
                "media_type": "video"
            }
            
        except Exception as e:
            logger.error(f"Failed to create LinkedIn video post: {e}")
            raise
    
    async def _upload_image(self, access_token: str, user_id: str, 
                           image_data: bytes, filename: str) -> str:
        """Upload image to LinkedIn and return asset URN"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Register upload
            register_data = {
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": f"urn:li:person:{user_id}",
                    "serviceRelationships": [
                        {
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent"
                        }
                    ]
                }
            }
            
            async with aiohttp.ClientSession() as session:
                # Register upload
                async with session.post(
                    f"{self.api_base_url}/assets?action=registerUpload",
                    headers=headers,
                    json=register_data
                ) as response:
                    response.raise_for_status()
                    upload_data = await response.json()
                
                # Get upload URL and asset URN
                upload_mechanism = upload_data['value']['uploadMechanism']
                upload_url = upload_mechanism['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
                asset_urn = upload_data['value']['asset']
                
                # Upload image data
                upload_headers = {
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/octet-stream'
                }
                
                async with session.post(upload_url, headers=upload_headers, data=image_data) as response:
                    response.raise_for_status()
            
            logger.info(f"Successfully uploaded LinkedIn image: {asset_urn}")
            return asset_urn
            
        except Exception as e:
            logger.error(f"Failed to upload LinkedIn image: {e}")
            raise
    
    async def _upload_video(self, access_token: str, user_id: str, 
                           video_data: bytes, filename: str,
                           thumbnail_data: Optional[bytes] = None) -> str:
        """Upload video to LinkedIn and return asset URN"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Register video upload
            register_data = {
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],
                    "owner": f"urn:li:person:{user_id}",
                    "serviceRelationships": [
                        {
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent"
                        }
                    ]
                }
            }
            
            async with aiohttp.ClientSession() as session:
                # Register upload
                async with session.post(
                    f"{self.api_base_url}/assets?action=registerUpload",
                    headers=headers,
                    json=register_data
                ) as response:
                    response.raise_for_status()
                    upload_data = await response.json()
                
                # Get upload URL and asset URN
                upload_mechanism = upload_data['value']['uploadMechanism']
                upload_url = upload_mechanism['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
                asset_urn = upload_data['value']['asset']
                
                # Upload video data
                upload_headers = {
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/octet-stream'
                }
                
                async with session.post(upload_url, headers=upload_headers, data=video_data) as response:
                    response.raise_for_status()
            
            logger.info(f"Successfully uploaded LinkedIn video: {asset_urn}")
            return asset_urn
            
        except Exception as e:
            logger.error(f"Failed to upload LinkedIn video: {e}")
            raise
    
    async def get_post_analytics(self, access_token: str, post_id: str) -> Dict[str, Any]:
        """Get analytics for a specific post"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}/socialActions/{post_id}",
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    analytics_data = await response.json()
            
            return {
                "post_id": post_id,
                "likes_count": analytics_data.get('likesSummary', {}).get('totalLikes', 0),
                "comments_count": analytics_data.get('commentsSummary', {}).get('totalComments', 0),
                "shares_count": analytics_data.get('sharesSummary', {}).get('totalShares', 0),
                "clicks_count": analytics_data.get('clicksSummary', {}).get('totalClicks', 0),
                "impressions_count": analytics_data.get('impressionsSummary', {}).get('totalImpressions', 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to get LinkedIn post analytics: {e}")
            return {
                "post_id": post_id,
                "likes_count": 0,
                "comments_count": 0,
                "shares_count": 0,
                "clicks_count": 0,
                "impressions_count": 0
            }
    
    async def delete_post(self, access_token: str, post_id: str) -> bool:
        """Delete a LinkedIn post"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"{self.api_base_url}/ugcPosts/{post_id}",
                    headers=headers
                ) as response:
                    response.raise_for_status()
            
            logger.info(f"Successfully deleted LinkedIn post: {post_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete LinkedIn post: {e}")
            return False