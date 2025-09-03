"""TikTok API Service - Handles TikTok Content API interactions"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, List, BinaryIO
from datetime import datetime, timezone
import aiohttp
import base64

from services.supabase import DBConnection
from utils.logger import logger
from .oauth import TikTokOAuthHandler


class TikTokAPIService:
    """Service for interacting with TikTok Content API"""
    
    BASE_URL = "https://open.tiktokapis.com/v2"
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.oauth_handler = TikTokOAuthHandler(db)
    
    async def get_user_info(
        self,
        user_id: str,
        account_id: str
    ) -> Dict[str, Any]:
        """Get TikTok user information"""
        
        # Get valid access token
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        data = {
            "fields": [
                "open_id",
                "union_id", 
                "avatar_url",
                "avatar_url_100",
                "avatar_url_200",
                "display_name",
                "bio_description",
                "profile_deep_link",
                "is_verified",
                "follower_count",
                "following_count",
                "likes_count",
                "video_count"
            ]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/user/info/",
                headers=headers,
                json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('data', {}).get('user', {})
                else:
                    response_text = await response.text()
                    logger.error(f"TikTok user info failed: {response.status} - {response_text}")
                    raise Exception(f"Failed to get user info: {response.status}")
    
    async def create_video_upload(
        self,
        user_id: str,
        account_id: str,
        video_data: bytes,
        title: str,
        description: str = "",
        privacy_level: str = "SELF_ONLY",
        disable_duet: bool = False,
        disable_comment: bool = False,
        disable_stitch: bool = False,
        brand_content_toggle: bool = False,
        brand_organic_toggle: bool = False
    ) -> Dict[str, Any]:
        """Upload video to TikTok using Content API"""
        
        # Get valid access token
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        # Step 1: Initialize video upload
        upload_url, upload_id = await self._initialize_video_upload(
            access_token=access_token,
            video_size=len(video_data),
            title=title,
            description=description,
            privacy_level=privacy_level,
            disable_duet=disable_duet,
            disable_comment=disable_comment,
            disable_stitch=disable_stitch,
            brand_content_toggle=brand_content_toggle,
            brand_organic_toggle=brand_organic_toggle
        )
        
        # Step 2: Upload video data
        await self._upload_video_data(upload_url, video_data)
        
        # Step 3: Commit the upload
        result = await self._commit_video_upload(access_token, upload_id)
        
        return {
            "upload_id": upload_id,
            "publish_id": result.get("publish_id"),
            "status": "uploaded",
            "message": "Video uploaded successfully to TikTok"
        }
    
    async def _initialize_video_upload(
        self,
        access_token: str,
        video_size: int,
        title: str,
        description: str = "",
        privacy_level: str = "SELF_ONLY",
        disable_duet: bool = False,
        disable_comment: bool = False,
        disable_stitch: bool = False,
        brand_content_toggle: bool = False,
        brand_organic_toggle: bool = False
    ) -> tuple[str, str]:
        """Initialize video upload and get upload URL"""
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Build post info
        post_info = {
            "title": title[:150],  # TikTok title limit
            "privacy_level": privacy_level,
            "disable_duet": disable_duet,
            "disable_comment": disable_comment,
            "disable_stitch": disable_stitch,
            "brand_content_toggle": brand_content_toggle,
            "brand_organic_toggle": brand_organic_toggle
        }
        
        if description:
            post_info["description"] = description[:2200]  # TikTok description limit
        
        data = {
            "post_info": post_info,
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": min(video_size, 10 * 1024 * 1024),  # Max 10MB chunks
                "total_chunk_count": (video_size + 10 * 1024 * 1024 - 1) // (10 * 1024 * 1024)
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/post/publish/video/init/",
                headers=headers,
                json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    data = result.get('data', {})
                    return data.get('upload_url'), data.get('publish_id')
                else:
                    response_text = await response.text()
                    logger.error(f"TikTok upload init failed: {response.status} - {response_text}")
                    raise Exception(f"Failed to initialize upload: {response.status}")
    
    async def _upload_video_data(self, upload_url: str, video_data: bytes):
        """Upload video data to TikTok's upload URL"""
        
        headers = {
            'Content-Type': 'video/mp4',
            'Content-Range': f'bytes 0-{len(video_data)-1}/{len(video_data)}'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.put(
                upload_url,
                headers=headers,
                data=video_data
            ) as response:
                if response.status not in [200, 201]:
                    response_text = await response.text()
                    logger.error(f"TikTok video upload failed: {response.status} - {response_text}")
                    raise Exception(f"Failed to upload video data: {response.status}")
    
    async def _commit_video_upload(self, access_token: str, publish_id: str) -> Dict[str, Any]:
        """Commit the video upload to publish it"""
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        data = {
            "publish_id": publish_id
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/post/publish/status/fetch/",
                headers=headers,
                json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('data', {})
                else:
                    response_text = await response.text()
                    logger.error(f"TikTok upload commit failed: {response.status} - {response_text}")
                    raise Exception(f"Failed to commit upload: {response.status}")
    
    async def get_video_status(
        self,
        user_id: str,
        account_id: str,
        publish_id: str
    ) -> Dict[str, Any]:
        """Get video upload/publish status"""
        
        # Get valid access token
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        data = {
            "publish_id": publish_id
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/post/publish/status/fetch/",
                headers=headers,
                json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('data', {})
                else:
                    response_text = await response.text()
                    logger.error(f"TikTok status check failed: {response.status} - {response_text}")
                    raise Exception(f"Failed to get video status: {response.status}")
    
    async def get_user_videos(
        self,
        user_id: str,
        account_id: str,
        max_count: int = 20,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get user's uploaded videos"""
        
        # Get valid access token
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        data = {
            "max_count": min(max_count, 20),  # TikTok API limit
            "fields": [
                "id",
                "title",
                "video_description", 
                "create_time",
                "cover_image_url",
                "share_url",
                "embed_html",
                "embed_link",
                "like_count",
                "comment_count",
                "share_count",
                "view_count"
            ]
        }
        
        if cursor:
            data["cursor"] = cursor
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/video/list/",
                headers=headers,
                json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('data', {})
                else:
                    response_text = await response.text()
                    logger.error(f"TikTok video list failed: {response.status} - {response_text}")
                    raise Exception(f"Failed to get videos: {response.status}")
    
    async def search_videos(
        self,
        user_id: str,
        account_id: str,
        query: str,
        count: int = 10,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search TikTok videos (if available through API)"""
        
        # Note: TikTok's search functionality may be limited or require special permissions
        # This is a placeholder implementation
        
        logger.warning("TikTok video search may not be available through Content API")
        
        # For now, return user's own videos that might match the query
        user_videos = await self.get_user_videos(user_id, account_id, count, cursor)
        
        # Filter videos that contain the query in title or description
        videos = user_videos.get('videos', [])
        filtered_videos = []
        
        query_lower = query.lower()
        for video in videos:
            title = video.get('title', '').lower()
            description = video.get('video_description', '').lower()
            if query_lower in title or query_lower in description:
                filtered_videos.append(video)
        
        return {
            'videos': filtered_videos,
            'cursor': user_videos.get('cursor'),
            'has_more': user_videos.get('has_more', False),
            'total': len(filtered_videos)
        }
    
    async def delete_video(
        self,
        user_id: str,
        account_id: str,
        video_id: str
    ) -> Dict[str, Any]:
        """Delete a TikTok video"""
        
        # Get valid access token
        access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        data = {
            "video_id": video_id
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/post/publish/video/delete/",
                headers=headers,
                json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('data', {})
                else:
                    response_text = await response.text()
                    logger.error(f"TikTok video delete failed: {response.status} - {response_text}")
                    raise Exception(f"Failed to delete video: {response.status}")