"""YouTube API Service - Comprehensive YouTube Data API v3 operations"""

import os
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from google.oauth2.credentials import Credentials
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    build = None
    HttpError = Exception
    Credentials = None

from services.supabase import DBConnection
from utils.logger import logger
from .oauth import YouTubeOAuthHandler


class YouTubeAPIService:
    """Comprehensive service for YouTube Data API v3 operations"""
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.oauth_handler = YouTubeOAuthHandler(db)
    
    async def _get_youtube_service(self, user_id: str, channel_id: str):
        """Get authenticated YouTube API service"""
        if not GOOGLE_API_AVAILABLE:
            raise Exception("Google API client not available. Please install google-api-python-client")
        
        # Get valid access token
        access_token = await self.oauth_handler.get_valid_token(user_id, channel_id)
        
        # Create credentials
        credentials = Credentials(token=access_token)
        
        # Build YouTube service
        return build('youtube', 'v3', credentials=credentials)
    
    async def list_captions(self, user_id: str, channel_id: str, video_id: str) -> Dict[str, Any]:
        """List available caption tracks for a video"""
        try:
            service = await self._get_youtube_service(user_id, channel_id)
            
            request = service.captions().list(
                videoId=video_id,
                part="id,snippet"
            )
            response = request.execute()
            
            captions = []
            for item in response.get('items', []):
                captions.append({
                    'id': item['id'],
                    'name': item['snippet'].get('name', ''),
                    'language': item['snippet']['language'],
                    'trackKind': item['snippet'].get('trackKind', 'standard'),
                    'isAutoSynced': item['snippet'].get('isAutoSynced', False),
                    'isDraft': item['snippet'].get('isDraft', False)
                })
            
            return {
                'success': True,
                'video_id': video_id,
                'captions': captions,
                'count': len(captions)
            }
            
        except HttpError as e:
            logger.error(f"YouTube API error listing captions: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to list captions'
            }
        except Exception as e:
            logger.error(f"Error listing captions: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def download_caption(self, user_id: str, channel_id: str, video_id: str, caption_id: str, format: str = 'srt') -> Dict[str, Any]:
        """Download a caption track"""
        try:
            service = await self._get_youtube_service(user_id, channel_id)
            
            # Download caption track
            request = service.captions().download(
                id=caption_id,
                tfmt=format  # 'srt', 'ttml', or 'vtt'
            )
            response = request.execute()
            
            return {
                'success': True,
                'video_id': video_id,
                'caption_id': caption_id,
                'format': format,
                'content': response.decode('utf-8') if isinstance(response, bytes) else response
            }
            
        except HttpError as e:
            logger.error(f"YouTube API error downloading caption: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to download caption'
            }
        except Exception as e:
            logger.error(f"Error downloading caption: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_channel_by_handle(self, user_id: str, channel_id: str, handle: str) -> Dict[str, Any]:
        """Get channel ID from a YouTube handle (e.g., @username)"""
        try:
            service = await self._get_youtube_service(user_id, channel_id)
            
            # Remove @ if present
            handle = handle.lstrip('@')
            
            # Search for channel by handle
            request = service.channels().list(
                forHandle=handle,
                part="id,snippet,statistics"
            )
            response = request.execute()
            
            if not response.get('items'):
                return {
                    'success': False,
                    'message': f'No channel found for handle @{handle}'
                }
            
            channel_info = response['items'][0]
            
            return {
                'success': True,
                'channel_id': channel_info['id'],
                'title': channel_info['snippet']['title'],
                'description': channel_info['snippet'].get('description', ''),
                'handle': f'@{handle}',
                'thumbnail': channel_info['snippet']['thumbnails'].get('high', {}).get('url'),
                'subscriber_count': channel_info['statistics'].get('subscriberCount', '0'),
                'video_count': channel_info['statistics'].get('videoCount', '0'),
                'view_count': channel_info['statistics'].get('viewCount', '0')
            }
            
        except HttpError as e:
            logger.error(f"YouTube API error getting channel by handle: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to find channel @{handle}'
            }
        except Exception as e:
            logger.error(f"Error getting channel by handle: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def list_channel_videos(self, user_id: str, channel_id: str, target_channel_id: Optional[str] = None, max_results: int = 50) -> Dict[str, Any]:
        """List videos from a channel"""
        try:
            service = await self._get_youtube_service(user_id, channel_id)
            
            # Use provided channel or default to authenticated channel
            channel_to_list = target_channel_id or channel_id
            
            # Get channel's uploads playlist
            channels_request = service.channels().list(
                id=channel_to_list,
                part="contentDetails"
            )
            channels_response = channels_request.execute()
            
            if not channels_response.get('items'):
                return {
                    'success': False,
                    'message': 'Channel not found'
                }
            
            uploads_playlist_id = channels_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            
            # Get videos from uploads playlist
            videos = []
            next_page_token = None
            
            while len(videos) < max_results:
                playlist_request = service.playlistItems().list(
                    playlistId=uploads_playlist_id,
                    part="snippet,contentDetails",
                    maxResults=min(50, max_results - len(videos)),
                    pageToken=next_page_token
                )
                playlist_response = playlist_request.execute()
                
                for item in playlist_response.get('items', []):
                    videos.append({
                        'video_id': item['contentDetails']['videoId'],
                        'title': item['snippet']['title'],
                        'description': item['snippet'].get('description', ''),
                        'published_at': item['snippet']['publishedAt'],
                        'thumbnail': item['snippet']['thumbnails'].get('high', {}).get('url'),
                        'channel_title': item['snippet']['channelTitle']
                    })
                
                next_page_token = playlist_response.get('nextPageToken')
                if not next_page_token:
                    break
            
            return {
                'success': True,
                'channel_id': channel_to_list,
                'videos': videos[:max_results],
                'count': len(videos[:max_results])
            }
            
        except HttpError as e:
            logger.error(f"YouTube API error listing channel videos: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to list channel videos'
            }
        except Exception as e:
            logger.error(f"Error listing channel videos: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def list_playlists(self, user_id: str, channel_id: str, max_results: int = 50) -> Dict[str, Any]:
        """List user's playlists"""
        try:
            service = await self._get_youtube_service(user_id, channel_id)
            
            playlists = []
            next_page_token = None
            
            while len(playlists) < max_results:
                request = service.playlists().list(
                    part="id,snippet,contentDetails",
                    mine=True,
                    maxResults=min(50, max_results - len(playlists)),
                    pageToken=next_page_token
                )
                response = request.execute()
                
                for item in response.get('items', []):
                    playlists.append({
                        'playlist_id': item['id'],
                        'title': item['snippet']['title'],
                        'description': item['snippet'].get('description', ''),
                        'published_at': item['snippet']['publishedAt'],
                        'thumbnail': item['snippet']['thumbnails'].get('high', {}).get('url'),
                        'item_count': item['contentDetails']['itemCount'],
                        'privacy_status': item['snippet'].get('privacyStatus', 'private')
                    })
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
            
            return {
                'success': True,
                'playlists': playlists[:max_results],
                'count': len(playlists[:max_results])
            }
            
        except HttpError as e:
            logger.error(f"YouTube API error listing playlists: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to list playlists'
            }
        except Exception as e:
            logger.error(f"Error listing playlists: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def list_subscriptions(self, user_id: str, channel_id: str, max_results: int = 50) -> Dict[str, Any]:
        """List user's channel subscriptions"""
        try:
            service = await self._get_youtube_service(user_id, channel_id)
            
            subscriptions = []
            next_page_token = None
            
            while len(subscriptions) < max_results:
                request = service.subscriptions().list(
                    part="id,snippet",
                    mine=True,
                    maxResults=min(50, max_results - len(subscriptions)),
                    pageToken=next_page_token
                )
                response = request.execute()
                
                for item in response.get('items', []):
                    subscriptions.append({
                        'subscription_id': item['id'],
                        'channel_id': item['snippet']['resourceId']['channelId'],
                        'channel_title': item['snippet']['title'],
                        'description': item['snippet'].get('description', ''),
                        'published_at': item['snippet']['publishedAt'],
                        'thumbnail': item['snippet']['thumbnails'].get('high', {}).get('url')
                    })
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
            
            return {
                'success': True,
                'subscriptions': subscriptions[:max_results],
                'count': len(subscriptions[:max_results])
            }
            
        except HttpError as e:
            logger.error(f"YouTube API error listing subscriptions: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to list subscriptions'
            }
        except Exception as e:
            logger.error(f"Error listing subscriptions: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def search(self, user_id: str, channel_id: str, query: str, search_type: str = 'video', max_results: int = 25) -> Dict[str, Any]:
        """Search YouTube for videos, channels, or playlists"""
        try:
            service = await self._get_youtube_service(user_id, channel_id)
            
            request = service.search().list(
                q=query,
                part="id,snippet",
                type=search_type,  # 'video', 'channel', or 'playlist'
                maxResults=min(50, max_results)
            )
            response = request.execute()
            
            results = []
            for item in response.get('items', []):
                result = {
                    'id': item['id'].get(f'{search_type}Id', item['id']),
                    'title': item['snippet']['title'],
                    'description': item['snippet'].get('description', ''),
                    'published_at': item['snippet']['publishedAt'],
                    'thumbnail': item['snippet']['thumbnails'].get('high', {}).get('url'),
                    'channel_title': item['snippet']['channelTitle'],
                    'channel_id': item['snippet']['channelId']
                }
                
                if search_type == 'video':
                    result['video_id'] = item['id']['videoId']
                elif search_type == 'channel':
                    result['channel_id'] = item['id']['channelId']
                elif search_type == 'playlist':
                    result['playlist_id'] = item['id']['playlistId']
                
                results.append(result)
            
            return {
                'success': True,
                'query': query,
                'type': search_type,
                'results': results,
                'count': len(results)
            }
            
        except HttpError as e:
            logger.error(f"YouTube API error searching: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Search failed'
            }
        except Exception as e:
            logger.error(f"Error searching YouTube: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def subscribe_to_channel(self, user_id: str, channel_id: str, target_channel_id: str) -> Dict[str, Any]:
        """Subscribe to a YouTube channel"""
        try:
            service = await self._get_youtube_service(user_id, channel_id)
            
            request = service.subscriptions().insert(
                part="snippet",
                body={
                    "snippet": {
                        "resourceId": {
                            "kind": "youtube#channel",
                            "channelId": target_channel_id
                        }
                    }
                }
            )
            response = request.execute()
            
            return {
                'success': True,
                'subscription_id': response['id'],
                'channel_id': target_channel_id,
                'channel_title': response['snippet']['title'],
                'message': f'Successfully subscribed to {response["snippet"]["title"]}'
            }
            
        except HttpError as e:
            if e.resp.status == 400 and 'subscriptionDuplicate' in str(e):
                return {
                    'success': False,
                    'message': 'Already subscribed to this channel'
                }
            logger.error(f"YouTube API error subscribing: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to subscribe to channel'
            }
        except Exception as e:
            logger.error(f"Error subscribing to channel: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def update_video(self, user_id: str, channel_id: str, video_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update video metadata"""
        try:
            service = await self._get_youtube_service(user_id, channel_id)
            
            # First get current video details
            request = service.videos().list(
                id=video_id,
                part="snippet,status"
            )
            response = request.execute()
            
            if not response.get('items'):
                return {
                    'success': False,
                    'message': 'Video not found'
                }
            
            video = response['items'][0]
            snippet = video['snippet']
            status = video['status']
            
            # Update fields if provided
            if 'title' in updates:
                snippet['title'] = updates['title']
            if 'description' in updates:
                snippet['description'] = updates['description']
            if 'tags' in updates:
                snippet['tags'] = updates['tags']
            if 'category_id' in updates:
                snippet['categoryId'] = updates['category_id']
            if 'privacy_status' in updates:
                status['privacyStatus'] = updates['privacy_status']
            
            # Update video
            update_request = service.videos().update(
                part="snippet,status",
                body={
                    "id": video_id,
                    "snippet": snippet,
                    "status": status
                }
            )
            update_response = update_request.execute()
            
            return {
                'success': True,
                'video_id': video_id,
                'title': snippet['title'],
                'description': snippet.get('description', ''),
                'tags': snippet.get('tags', []),
                'privacy_status': status.get('privacyStatus', 'private'),
                'message': 'Video updated successfully'
            }
            
        except HttpError as e:
            logger.error(f"YouTube API error updating video: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to update video'
            }
        except Exception as e:
            logger.error(f"Error updating video: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_video_details(self, user_id: str, channel_id: str, video_id: str) -> Dict[str, Any]:
        """Get detailed information about a video"""
        try:
            service = await self._get_youtube_service(user_id, channel_id)
            
            request = service.videos().list(
                id=video_id,
                part="snippet,statistics,status,contentDetails"
            )
            response = request.execute()
            
            if not response.get('items'):
                return {
                    'success': False,
                    'message': 'Video not found'
                }
            
            video = response['items'][0]
            
            return {
                'success': True,
                'video_id': video_id,
                'title': video['snippet']['title'],
                'description': video['snippet'].get('description', ''),
                'published_at': video['snippet']['publishedAt'],
                'channel_id': video['snippet']['channelId'],
                'channel_title': video['snippet']['channelTitle'],
                'tags': video['snippet'].get('tags', []),
                'category_id': video['snippet'].get('categoryId'),
                'duration': video['contentDetails']['duration'],
                'dimension': video['contentDetails'].get('dimension'),
                'definition': video['contentDetails'].get('definition'),
                'caption': video['contentDetails'].get('caption', 'false'),
                'privacy_status': video['status']['privacyStatus'],
                'embeddable': video['status'].get('embeddable', False),
                'view_count': video['statistics'].get('viewCount', '0'),
                'like_count': video['statistics'].get('likeCount', '0'),
                'comment_count': video['statistics'].get('commentCount', '0'),
                'thumbnail': video['snippet']['thumbnails'].get('high', {}).get('url')
            }
            
        except HttpError as e:
            logger.error(f"YouTube API error getting video details: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to get video details'
            }
        except Exception as e:
            logger.error(f"Error getting video details: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def update_thumbnail(self, user_id: str, channel_id: str, video_id: str, thumbnail_path: str) -> Dict[str, Any]:
        """Update video thumbnail"""
        try:
            if not GOOGLE_API_AVAILABLE:
                raise Exception("Google API client not available")
            
            service = await self._get_youtube_service(user_id, channel_id)
            
            # Upload thumbnail
            from googleapiclient.http import MediaFileUpload
            
            media = MediaFileUpload(
                thumbnail_path,
                mimetype='image/jpeg',
                resumable=True
            )
            
            request = service.thumbnails().set(
                videoId=video_id,
                media_body=media
            )
            response = request.execute()
            
            return {
                'success': True,
                'video_id': video_id,
                'thumbnail_url': response['items'][0]['high']['url'] if response.get('items') else None,
                'message': 'Thumbnail updated successfully'
            }
            
        except HttpError as e:
            logger.error(f"YouTube API error updating thumbnail: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to update thumbnail'
            }
        except Exception as e:
            logger.error(f"Error updating thumbnail: {e}")
            return {
                'success': False,
                'error': str(e)
            }