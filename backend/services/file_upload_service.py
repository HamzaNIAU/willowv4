"""Generic File Upload Service

Handles temporary file storage for all file types.
Files are stored temporarily and can be accessed by AI agents.
"""

import os
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from pathlib import Path
import tempfile
import aiofiles
from utils.logger import logger

# Store uploaded files in memory/temp storage
# In production, this should use S3 or similar
TEMP_STORAGE_PATH = Path(tempfile.gettempdir()) / "suna_file_uploads"
TEMP_STORAGE_PATH.mkdir(exist_ok=True)

# File size limits
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB general limit
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20MB for images
MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500MB for videos
MAX_DOCUMENT_SIZE = 50 * 1024 * 1024  # 50MB for documents

# Supported file types
SUPPORTED_IMAGE_TYPES = [
    'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 
    'image/webp', 'image/svg+xml', 'image/bmp'
]

SUPPORTED_VIDEO_TYPES = [
    'video/mp4', 'video/mpeg', 'video/quicktime', 'video/x-msvideo',
    'video/x-ms-wmv', 'video/webm', 'video/x-matroska'
]

SUPPORTED_DOCUMENT_TYPES = [
    'application/pdf', 'application/msword', 
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel', 
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain', 'text/csv', 'text/html', 'text/markdown',
    'application/json', 'application/xml', 'text/xml'
]

SUPPORTED_AUDIO_TYPES = [
    'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/ogg',
    'audio/webm', 'audio/aac', 'audio/flac'
]


class FileUploadService:
    """Service for handling generic file uploads"""
    
    def __init__(self, db_connection):
        self.db = db_connection
        self.storage_path = TEMP_STORAGE_PATH
        
    def _get_file_category(self, mime_type: str) -> str:
        """Determine file category based on MIME type"""
        if mime_type in SUPPORTED_IMAGE_TYPES:
            return "image"
        elif mime_type in SUPPORTED_VIDEO_TYPES:
            return "video"
        elif mime_type in SUPPORTED_DOCUMENT_TYPES:
            return "document"
        elif mime_type in SUPPORTED_AUDIO_TYPES:
            return "audio"
        else:
            return "other"
    
    def _is_social_media_content(self, file_category: str) -> bool:
        """Check if content is suitable for social media"""
        return file_category in ["video", "image"]
    
    def _get_compatible_platforms(self, mime_type: str, file_size: int) -> List[str]:
        """Get list of compatible social media platforms"""
        platforms = []
        file_size_mb = file_size / (1024 * 1024)
        
        # YouTube
        if mime_type in SUPPORTED_VIDEO_TYPES + SUPPORTED_IMAGE_TYPES and file_size_mb <= 128000:
            platforms.append("youtube")
        
        # TikTok
        if mime_type in ['video/mp4', 'video/quicktime'] and file_size_mb <= 287:
            platforms.append("tiktok")
        
        # Instagram
        if mime_type in ['video/mp4', 'video/quicktime'] + SUPPORTED_IMAGE_TYPES and file_size_mb <= 100:
            platforms.append("instagram")
        
        # Twitter/X
        if mime_type in ['video/mp4'] + SUPPORTED_IMAGE_TYPES and file_size_mb <= 512:
            platforms.append("twitter")
        
        # Facebook
        if mime_type in SUPPORTED_VIDEO_TYPES + SUPPORTED_IMAGE_TYPES and file_size_mb <= 10240:
            platforms.append("facebook")
        
        # LinkedIn
        if mime_type in ['video/mp4', 'application/pdf'] + SUPPORTED_IMAGE_TYPES and file_size_mb <= 5120:
            platforms.append("linkedin")
        
        return platforms
    
    def _validate_file_size(self, file_size: int, file_category: str) -> tuple[bool, str]:
        """Validate file size based on category"""
        if file_category == "image" and file_size > MAX_IMAGE_SIZE:
            return False, f"Image file too large. Maximum size is {MAX_IMAGE_SIZE // (1024*1024)}MB"
        elif file_category == "video" and file_size > MAX_VIDEO_SIZE:
            return False, f"Video file too large. Maximum size is {MAX_VIDEO_SIZE // (1024*1024)}MB"
        elif file_category == "document" and file_size > MAX_DOCUMENT_SIZE:
            return False, f"Document file too large. Maximum size is {MAX_DOCUMENT_SIZE // (1024*1024)}MB"
        elif file_size > MAX_FILE_SIZE:
            return False, f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
        
        return True, ""
    
    def _generate_file_id(self) -> str:
        """Generate a unique file ID"""
        return f"file_{uuid.uuid4().hex[:12]}"
    
    def _calculate_checksum(self, file_data: bytes) -> str:
        """Calculate SHA256 checksum of file data"""
        return hashlib.sha256(file_data).hexdigest()
    
    async def create_file_reference(
        self,
        user_id: str,
        file_name: str,
        file_data: bytes,
        mime_type: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a reference for an uploaded file
        
        Args:
            user_id: User ID
            file_name: Original file name
            file_data: File content as bytes
            mime_type: MIME type of the file
            description: Optional description
            
        Returns:
            Dictionary with file reference details
        """
        try:
            # Determine file category
            file_category = self._get_file_category(mime_type)
            
            # Validate file size
            file_size = len(file_data)
            valid, error_msg = self._validate_file_size(file_size, file_category)
            if not valid:
                raise ValueError(error_msg)
            
            # Generate file ID and checksum
            file_id = self._generate_file_id()
            checksum = self._calculate_checksum(file_data)
            
            # Save file to temporary storage
            file_path = self.storage_path / f"{file_id}_{file_name}"
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_data)
            
            # Get social media metadata
            is_social_content = self._is_social_media_content(file_category)
            compatible_platforms = self._get_compatible_platforms(mime_type, file_size) if is_social_content else []
            
            # Create database record
            client = await self.db.client
            expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
            
            record = {
                "file_id": file_id,
                "user_id": user_id,
                "file_name": file_name,
                "file_size": file_size,
                "mime_type": mime_type,
                "file_category": file_category,
                "is_social_content": is_social_content,
                "compatible_platforms": compatible_platforms,
                "checksum": checksum,
                "storage_path": str(file_path),
                "description": description,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": expires_at.isoformat(),
                "is_active": True
            }
            
            # Store in database
            result = await client.table("file_uploads").insert(record).execute()
            
            if not result.data:
                raise Exception("Failed to create file reference in database")
            
            logger.info(f"Created file reference {file_id} for user {user_id}")
            
            return {
                "file_id": file_id,
                "file_name": file_name,
                "file_size": self._format_file_size(file_size),
                "file_size_bytes": file_size,
                "mime_type": mime_type,
                "file_category": file_category,
                "is_social_content": is_social_content,
                "compatible_platforms": compatible_platforms,
                "checksum": checksum,
                "expires_at": expires_at.isoformat(),
                "description": description
            }
            
        except Exception as e:
            logger.error(f"Failed to create file reference: {e}")
            raise
    
    async def get_file_reference(
        self,
        file_id: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get file reference by ID
        
        Args:
            file_id: File ID
            user_id: User ID
            
        Returns:
            File reference data or None
        """
        try:
            client = await self.db.client
            
            result = await client.table("file_uploads").select("*").eq(
                "file_id", file_id
            ).eq("user_id", user_id).eq("is_active", True).execute()
            
            if not result.data:
                return None
            
            file_data = result.data[0]
            
            # Check if expired
            expires_at = datetime.fromisoformat(file_data["expires_at"].replace('Z', '+00:00'))
            if expires_at < datetime.now(timezone.utc):
                logger.info(f"File {file_id} has expired")
                return None
            
            return file_data
            
        except Exception as e:
            logger.error(f"Failed to get file reference: {e}")
            return None
    
    async def get_file_content(
        self,
        file_id: str,
        user_id: str
    ) -> Optional[bytes]:
        """
        Get actual file content
        
        Args:
            file_id: File ID
            user_id: User ID
            
        Returns:
            File content as bytes or None
        """
        try:
            # Get file reference
            file_ref = await self.get_file_reference(file_id, user_id)
            if not file_ref:
                return None
            
            # Read file from storage
            file_path = Path(file_ref["storage_path"])
            if not file_path.exists():
                logger.error(f"File not found at path: {file_path}")
                return None
            
            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read()
            
            return content
            
        except Exception as e:
            logger.error(f"Failed to get file content: {e}")
            return None
    
    async def list_user_files(
        self,
        user_id: str,
        file_category: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List user's uploaded files
        
        Args:
            user_id: User ID
            file_category: Optional category filter
            limit: Maximum number of files to return
            
        Returns:
            List of file references
        """
        try:
            client = await self.db.client
            
            query = client.table("file_uploads").select("*").eq(
                "user_id", user_id
            ).eq("is_active", True)
            
            if file_category:
                query = query.eq("file_category", file_category)
            
            # Filter out expired files
            now = datetime.now(timezone.utc).isoformat()
            query = query.gt("expires_at", now)
            
            # Order by created_at desc and limit
            query = query.order("created_at", desc=True).limit(limit)
            
            result = await query.execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Failed to list user files: {e}")
            return []
    
    async def delete_file(
        self,
        file_id: str,
        user_id: str
    ) -> bool:
        """
        Delete a file reference and its content
        
        Args:
            file_id: File ID
            user_id: User ID
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            # Get file reference
            file_ref = await self.get_file_reference(file_id, user_id)
            if not file_ref:
                return False
            
            # Delete physical file
            file_path = Path(file_ref["storage_path"])
            if file_path.exists():
                file_path.unlink()
            
            # Mark as inactive in database
            client = await self.db.client
            await client.table("file_uploads").update({
                "is_active": False,
                "deleted_at": datetime.now(timezone.utc).isoformat()
            }).eq("file_id", file_id).eq("user_id", user_id).execute()
            
            logger.info(f"Deleted file {file_id} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            return False
    
    async def cleanup_expired_files(self) -> int:
        """
        Clean up expired file references and their content
        
        Returns:
            Number of files cleaned up
        """
        try:
            client = await self.db.client
            
            # Get expired files
            now = datetime.now(timezone.utc).isoformat()
            result = await client.table("file_uploads").select("*").eq(
                "is_active", True
            ).lt("expires_at", now).execute()
            
            if not result.data:
                return 0
            
            count = 0
            for file_ref in result.data:
                try:
                    # Delete physical file
                    file_path = Path(file_ref["storage_path"])
                    if file_path.exists():
                        file_path.unlink()
                    
                    # Mark as inactive
                    await client.table("file_uploads").update({
                        "is_active": False,
                        "deleted_at": now
                    }).eq("file_id", file_ref["file_id"]).execute()
                    
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to cleanup file {file_ref['file_id']}: {e}")
            
            logger.info(f"Cleaned up {count} expired files")
            return count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired files: {e}")
            return 0
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size for display"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"