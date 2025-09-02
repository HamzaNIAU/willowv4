"""
Universal Social Media File Service
Handles file uploads for all social media platforms with intelligent routing
"""

import os
import secrets
import hashlib
import mimetypes
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

from services.supabase import DBConnection
from utils.logger import logger


class SocialMediaFileService:
    """Universal service for social media file uploads across all platforms"""
    
    # Platform requirements (can be overridden from database)
    PLATFORM_REQUIREMENTS = {
        'youtube': {
            'max_video_size_mb': 128000,
            'max_image_size_mb': 2,
            'video_formats': ['mp4', 'mov', 'avi', 'wmv', 'flv', 'mkv', 'webm'],
            'image_formats': ['jpg', 'jpeg', 'png', 'gif'],
            'max_duration_seconds': 43200,  # 12 hours
            'aspect_ratios': ['16:9', '4:3']
        },
        'tiktok': {
            'max_video_size_mb': 287,
            'max_image_size_mb': 10,
            'video_formats': ['mp4', 'mov'],
            'image_formats': ['jpg', 'jpeg', 'png'],
            'max_duration_seconds': 600,  # 10 minutes
            'aspect_ratios': ['9:16']  # Vertical
        },
        'instagram': {
            'max_video_size_mb': 100,
            'max_image_size_mb': 30,
            'video_formats': ['mp4', 'mov'],
            'image_formats': ['jpg', 'jpeg', 'png'],
            'max_duration_seconds': 60,  # 60 seconds for feed, 90 for reels
            'aspect_ratios': ['1:1', '4:5', '9:16']
        },
        'twitter': {
            'max_video_size_mb': 512,
            'max_image_size_mb': 5,
            'video_formats': ['mp4'],
            'image_formats': ['jpg', 'jpeg', 'png', 'gif'],
            'max_duration_seconds': 140,
            'aspect_ratios': ['16:9', '1:1']
        },
        'facebook': {
            'max_video_size_mb': 10240,
            'max_image_size_mb': 30,
            'video_formats': ['mp4', 'mov'],
            'image_formats': ['jpg', 'jpeg', 'png'],
            'max_duration_seconds': 240,
            'aspect_ratios': ['16:9', '1:1', '9:16']
        },
        'linkedin': {
            'max_video_size_mb': 5120,
            'max_image_size_mb': 10,
            'video_formats': ['mp4'],
            'image_formats': ['jpg', 'jpeg', 'png'],
            'max_duration_seconds': 600,
            'aspect_ratios': ['16:9', '1:1']
        }
    }
    
    def __init__(self, db: DBConnection, user_id: str = None):
        self.db = db
        self.user_id = user_id
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        if user_id:
            logger.info(f"SocialMediaFileService initialized for user {user_id}")
    
    def generate_reference_id(self) -> str:
        """Generate a 32-character hex reference ID"""
        return secrets.token_hex(16)
    
    def calculate_checksum(self, file_data: bytes) -> str:
        """Calculate SHA256 checksum of file data"""
        return hashlib.sha256(file_data).hexdigest()
    
    def detect_file_type(self, mime_type: str, file_name: str = "") -> str:
        """
        Detect file type category
        Returns: 'video', 'image', 'audio', 'document', or 'unknown'
        """
        mime_lower = mime_type.lower()
        
        if mime_lower.startswith('video/'):
            return 'video'
        elif mime_lower.startswith('image/'):
            return 'image'
        elif mime_lower.startswith('audio/'):
            return 'audio'
        elif mime_lower in ['application/pdf', 'text/plain', 'application/msword']:
            return 'document'
        
        # Fallback to extension
        if file_name:
            ext = os.path.splitext(file_name.lower())[1].lstrip('.')
            if ext in ['mp4', 'mov', 'avi', 'wmv', 'flv', 'mkv', 'webm']:
                return 'video'
            elif ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']:
                return 'image'
            elif ext in ['mp3', 'wav', 'ogg', 'aac', 'flac']:
                return 'audio'
            elif ext in ['pdf', 'doc', 'docx', 'txt']:
                return 'document'
        
        return 'unknown'
    
    def detect_compatible_platforms(
        self, 
        file_type: str, 
        file_size: int, 
        mime_type: str,
        duration_seconds: Optional[float] = None
    ) -> List[str]:
        """
        Detect which platforms this file is compatible with
        
        Returns list of compatible platform names
        """
        compatible = []
        file_size_mb = file_size / (1024 * 1024)
        
        # Get file extension
        ext = mime_type.split('/')[-1].lower()
        if ext == 'jpeg':
            ext = 'jpg'
        
        for platform, reqs in self.PLATFORM_REQUIREMENTS.items():
            # Check file type compatibility
            if file_type == 'video':
                if ext not in reqs.get('video_formats', []):
                    continue
                if file_size_mb > reqs.get('max_video_size_mb', 0):
                    continue
                if duration_seconds and duration_seconds > reqs.get('max_duration_seconds', 0):
                    continue
            elif file_type == 'image':
                if ext not in reqs.get('image_formats', []):
                    continue
                if file_size_mb > reqs.get('max_image_size_mb', 0):
                    continue
            else:
                # Platform doesn't support this file type
                continue
            
            compatible.append(platform)
        
        return compatible
    
    async def create_file_reference(
        self,
        user_id: str,
        file_name: str,
        file_data: bytes,
        mime_type: str,
        platform: Optional[str] = None,
        file_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expiry_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Create a universal file reference for social media
        
        Args:
            user_id: User ID
            file_name: Original file name
            file_data: Binary file data
            mime_type: MIME type
            platform: Target platform (optional, will detect compatible platforms)
            file_type: Override file type detection
            metadata: Additional metadata (dimensions, duration, etc.)
            expiry_hours: Hours until expiration
        
        Returns:
            Dict with reference_id and file information
        """
        reference_id = self.generate_reference_id()
        file_size = len(file_data)
        checksum = self.calculate_checksum(file_data)
        
        # Detect file type if not provided
        if not file_type:
            file_type = self.detect_file_type(mime_type, file_name)
        
        # Detect compatible platforms
        duration = metadata.get('duration_seconds') if metadata else None
        compatible_platforms = self.detect_compatible_platforms(
            file_type, file_size, mime_type, duration
        )
        
        # Store in database
        client = await self.db.client
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
        
        file_ref_data = {
            "id": reference_id,
            "user_id": user_id,
            "file_name": file_name,
            "file_data": file_data,
            "file_size": file_size,
            "mime_type": mime_type,
            "file_type": file_type,
            "checksum": checksum,
            "platform": platform,
            "detected_platforms": compatible_platforms,
            "expires_at": expires_at.isoformat()
        }
        
        # Add optional metadata
        if metadata:
            if 'dimensions' in metadata:
                file_ref_data['dimensions'] = metadata['dimensions']
            if 'duration_seconds' in metadata:
                file_ref_data['duration_seconds'] = metadata['duration_seconds']
            if 'generated_metadata' in metadata:
                file_ref_data['generated_metadata'] = metadata['generated_metadata']
        
        result = await client.table("social_media_file_references").insert(file_ref_data).execute()
        
        if not result.data:
            raise Exception("Failed to create file reference")
        
        # Create upload reference
        upload_ref_data = {
            "user_id": user_id,
            "reference_id": reference_id,
            "file_name": file_name,
            "file_size": file_size,
            "file_type": file_type,
            "mime_type": mime_type,
            "platform": platform,
            "detected_platforms": compatible_platforms,
            "intended_platform": platform,
            "status": "ready",
            "ready_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat()
        }
        
        await client.table("upload_references").insert(upload_ref_data).execute()
        
        logger.info(f"Created reference {reference_id} for {file_type} compatible with: {compatible_platforms}")
        
        return {
            "reference_id": reference_id,
            "file_name": file_name,
            "file_size": self.format_file_size(file_size),
            "file_size_bytes": file_size,
            "mime_type": mime_type,
            "file_type": file_type,
            "compatible_platforms": compatible_platforms,
            "intended_platform": platform,
            "expires_at": expires_at.isoformat(),
            "checksum": checksum
        }
    
    async def get_latest_pending_uploads(
        self, 
        user_id: str,
        platform: Optional[str] = None
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get the latest pending uploads for a user
        Can filter by platform if specified
        
        Returns dict with file types as keys
        """
        client = await self.db.client
        
        query = client.table("upload_references").select("*").eq(
            "user_id", user_id
        ).eq(
            "status", "ready"
        ).gt(
            "expires_at", datetime.now(timezone.utc).isoformat()
        )
        
        # Filter by platform if specified
        if platform:
            # Either intended for this platform or compatible with it
            query = query.or_(
                f"intended_platform.eq.{platform},detected_platforms.cs.{{{platform}}}"
            )
        
        result = await query.order("created_at", desc=True).limit(10).execute()
        
        uploads = result.data if result.data else []
        
        # Organize by file type
        organized = {
            "video": None,
            "image": None,
            "thumbnail": None,
            "audio": None,
            "document": None
        }
        
        for upload in uploads:
            file_type = upload["file_type"]
            
            # Map 'image' to 'thumbnail' for backward compatibility
            if file_type == "image" and not organized["thumbnail"]:
                organized["thumbnail"] = upload
            
            if file_type in organized and not organized[file_type]:
                organized[file_type] = upload
        
        return organized
    
    async def get_file_data(self, reference_id: str, user_id: str) -> Optional[bytes]:
        """
        Retrieve file data by reference ID
        """
        client = await self.db.client
        
        result = await client.table("social_media_file_references").select("*").eq(
            "id", reference_id
        ).eq("user_id", user_id).execute()
        
        if not result.data:
            logger.warning(f"No reference found for {reference_id}")
            return None
        
        file_info = result.data[0]
        file_data = file_info.get("file_data")
        
        if not file_data:
            logger.warning(f"No file data in reference {reference_id}")
            return None
        
        # Handle different data formats
        if isinstance(file_data, str):
            import base64
            return base64.b64decode(file_data)
        elif isinstance(file_data, bytes):
            return file_data
        else:
            logger.error(f"Unexpected file data type: {type(file_data)}")
            return None
    
    async def mark_reference_used(
        self, 
        reference_id: str,
        platform: str
    ) -> None:
        """Mark a reference as used by a specific platform"""
        client = await self.db.client
        
        # Use the SQL function
        await client.rpc(
            'mark_reference_used',
            {'ref_id': reference_id, 'platform_name': platform}
        ).execute()
        
        logger.info(f"Marked reference {reference_id} as used by {platform}")
    
    async def cleanup_expired_references(self) -> int:
        """Clean up expired references"""
        client = await self.db.client
        
        # Call the cleanup function
        await client.rpc('cleanup_expired_references').execute()
        
        # Get count of cleaned items
        result = await client.table("upload_references").select("id").eq(
            "status", "expired"
        ).execute()
        
        count = len(result.data) if result.data else 0
        logger.info(f"Cleaned up {count} expired references")
        
        return count
    
    def format_file_size(self, size_bytes: int) -> str:
        """Format file size for display"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def validate_file_for_platform(
        self,
        file_data: bytes,
        file_type: str,
        platform: str,
        mime_type: str,
        duration_seconds: Optional[float] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validate if a file meets platform requirements
        
        Returns: (is_valid, list_of_errors)
        """
        errors = []
        file_size_mb = len(file_data) / (1024 * 1024)
        
        if platform not in self.PLATFORM_REQUIREMENTS:
            return True, []  # Unknown platform, allow
        
        reqs = self.PLATFORM_REQUIREMENTS[platform]
        
        # Check size
        if file_type == 'video':
            max_size = reqs.get('max_video_size_mb', float('inf'))
            if file_size_mb > max_size:
                errors.append(f"Video exceeds {platform}'s {max_size}MB limit")
        elif file_type == 'image':
            max_size = reqs.get('max_image_size_mb', float('inf'))
            if file_size_mb > max_size:
                errors.append(f"Image exceeds {platform}'s {max_size}MB limit")
        
        # Check format
        ext = mime_type.split('/')[-1].lower()
        if ext == 'jpeg':
            ext = 'jpg'
        
        if file_type == 'video' and ext not in reqs.get('video_formats', []):
            errors.append(f"{platform} doesn't support {ext} videos")
        elif file_type == 'image' and ext not in reqs.get('image_formats', []):
            errors.append(f"{platform} doesn't support {ext} images")
        
        # Check duration
        if duration_seconds and file_type == 'video':
            max_duration = reqs.get('max_duration_seconds', float('inf'))
            if duration_seconds > max_duration:
                errors.append(f"Video exceeds {platform}'s {max_duration}s duration limit")
        
        return len(errors) == 0, errors