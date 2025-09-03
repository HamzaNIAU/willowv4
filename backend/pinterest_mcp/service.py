"""Pinterest API Service"""

import aiohttp
import json
import base64
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from utils.logger import logger


class PinterestAPIService:
    """Service for Pinterest API interactions"""
    
    def __init__(self):
        self.api_base_url = "https://api.pinterest.com/v5"
    
    async def create_pin(self, access_token: str, board_id: str, title: str,
                        description: str, link: Optional[str] = None,
                        image_url: Optional[str] = None, image_data: Optional[bytes] = None,
                        alt_text: Optional[str] = None) -> Dict[str, Any]:
        """Create a pin on Pinterest"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Prepare pin data
            pin_data = {
                "board_id": board_id,
                "title": title,
                "description": description
            }
            
            # Add optional fields
            if link:
                pin_data["link"] = link
            if alt_text:
                pin_data["alt_text"] = alt_text
            
            # Handle image - Pinterest v5 API supports both URL and upload
            if image_url:
                pin_data["media_source"] = {
                    "source_type": "image_url",
                    "url": image_url
                }
            elif image_data:
                # For image uploads, we need to use multipart form data
                pin_data["media_source"] = {
                    "source_type": "image_base64",
                    "data": base64.b64encode(image_data).decode('utf-8')
                }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/pins",
                    headers=headers,
                    json=pin_data
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
            
            pin_id = result.get('id')
            pin_url = f"https://pinterest.com/pin/{pin_id}"
            
            logger.info(f"Successfully created Pinterest pin: {pin_id}")
            
            return {
                "pin_id": pin_id,
                "pin_url": pin_url,
                "title": title,
                "description": description,
                "board_id": board_id,
                "created_at": datetime.utcnow().isoformat(),
                "media_type": "image"
            }
            
        except Exception as e:
            logger.error(f"Failed to create Pinterest pin: {e}")
            raise
    
    async def create_video_pin(self, access_token: str, board_id: str, title: str,
                              description: str, video_data: bytes,
                              thumbnail_data: Optional[bytes] = None,
                              link: Optional[str] = None) -> Dict[str, Any]:
        """Create a video pin on Pinterest"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Prepare video pin data
            pin_data = {
                "board_id": board_id,
                "title": title,
                "description": description,
                "media_source": {
                    "source_type": "video_id",
                    "cover_image_url": None  # Will be set after video upload
                }
            }
            
            if link:
                pin_data["link"] = link
            
            # First, upload the video (Pinterest requires separate video upload)
            video_id = await self._upload_video(access_token, video_data)
            pin_data["media_source"]["video_id"] = video_id
            
            # Upload thumbnail if provided
            if thumbnail_data:
                thumbnail_url = await self._upload_image(access_token, thumbnail_data)
                pin_data["media_source"]["cover_image_url"] = thumbnail_url
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/pins",
                    headers=headers,
                    json=pin_data
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
            
            pin_id = result.get('id')
            pin_url = f"https://pinterest.com/pin/{pin_id}"
            
            logger.info(f"Successfully created Pinterest video pin: {pin_id}")
            
            return {
                "pin_id": pin_id,
                "pin_url": pin_url,
                "title": title,
                "description": description,
                "board_id": board_id,
                "video_id": video_id,
                "created_at": datetime.utcnow().isoformat(),
                "media_type": "video"
            }
            
        except Exception as e:
            logger.error(f"Failed to create Pinterest video pin: {e}")
            raise
    
    async def _upload_video(self, access_token: str, video_data: bytes) -> str:
        """Upload video to Pinterest and return video ID"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'video/mp4'  # Adjust based on actual video type
            }
            
            # Pinterest video upload endpoint
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/media",
                    headers=headers,
                    data=video_data
                ) as response:
                    response.raise_for_status()
                    upload_data = await response.json()
            
            video_id = upload_data.get('media_id')
            logger.info(f"Successfully uploaded Pinterest video: {video_id}")
            return video_id
            
        except Exception as e:
            logger.error(f"Failed to upload Pinterest video: {e}")
            raise
    
    async def _upload_image(self, access_token: str, image_data: bytes) -> str:
        """Upload image to Pinterest and return image URL"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'image/jpeg'  # Adjust based on actual image type
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/media",
                    headers=headers,
                    data=image_data
                ) as response:
                    response.raise_for_status()
                    upload_data = await response.json()
            
            image_url = upload_data.get('url')
            logger.info(f"Successfully uploaded Pinterest image: {image_url}")
            return image_url
            
        except Exception as e:
            logger.error(f"Failed to upload Pinterest image: {e}")
            raise
    
    async def get_boards(self, access_token: str) -> List[Dict[str, Any]]:
        """Get user's Pinterest boards"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            boards = []
            bookmark = None
            
            # Pinterest API uses pagination
            while True:
                url = f"{self.api_base_url}/boards"
                params = {"page_size": 25}
                if bookmark:
                    params["bookmark"] = bookmark
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, params=params) as response:
                        response.raise_for_status()
                        data = await response.json()
                
                items = data.get('items', [])
                for item in items:
                    board = {
                        "id": item.get('id'),
                        "name": item.get('name'),
                        "description": item.get('description'),
                        "pin_count": item.get('pin_count', 0),
                        "follower_count": item.get('follower_count', 0),
                        "privacy": item.get('privacy', 'PUBLIC'),
                        "created_at": item.get('created_at'),
                        "board_url": f"https://pinterest.com/board/{item.get('id')}"
                    }
                    boards.append(board)
                
                bookmark = data.get('bookmark')
                if not bookmark:
                    break
            
            return boards
            
        except Exception as e:
            logger.error(f"Failed to get Pinterest boards: {e}")
            return []
    
    async def create_board(self, access_token: str, name: str, description: str = "",
                          privacy: str = "PUBLIC") -> Dict[str, Any]:
        """Create a new Pinterest board"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            board_data = {
                "name": name,
                "description": description,
                "privacy": privacy  # PUBLIC or SECRET
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/boards",
                    headers=headers,
                    json=board_data
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
            
            board_id = result.get('id')
            board_url = f"https://pinterest.com/board/{board_id}"
            
            logger.info(f"Successfully created Pinterest board: {board_id}")
            
            return {
                "board_id": board_id,
                "board_url": board_url,
                "name": name,
                "description": description,
                "privacy": privacy,
                "created_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to create Pinterest board: {e}")
            raise
    
    async def get_pin_analytics(self, access_token: str, pin_id: str) -> Dict[str, Any]:
        """Get analytics for a specific pin"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}/pins/{pin_id}/analytics",
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    analytics_data = await response.json()
            
            return {
                "pin_id": pin_id,
                "impressions": analytics_data.get('IMPRESSION', 0),
                "saves": analytics_data.get('SAVE', 0),
                "pin_clicks": analytics_data.get('PIN_CLICK', 0),
                "outbound_clicks": analytics_data.get('OUTBOUND_CLICK', 0),
                "video_starts": analytics_data.get('VIDEO_MRC_VIEW', 0) if 'VIDEO_MRC_VIEW' in analytics_data else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get Pinterest pin analytics: {e}")
            return {
                "pin_id": pin_id,
                "impressions": 0,
                "saves": 0,
                "pin_clicks": 0,
                "outbound_clicks": 0,
                "video_starts": 0
            }
    
    async def delete_pin(self, access_token: str, pin_id: str) -> bool:
        """Delete a Pinterest pin"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"{self.api_base_url}/pins/{pin_id}",
                    headers=headers
                ) as response:
                    response.raise_for_status()
            
            logger.info(f"Successfully deleted Pinterest pin: {pin_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete Pinterest pin: {e}")
            return False