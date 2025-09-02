"""Enhanced YouTube File Service with multi-channel parallel upload support"""

import os
import hashlib
import secrets
import asyncio
import json
import base64
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta, timezone
import mimetypes
from io import BytesIO
from PIL import Image
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import aiofiles
import aiohttp

from services.supabase import DBConnection
from services.channel_cache import get_channel_cache
from services.token_refresh_manager import get_refresh_manager
from services.encryption_service import get_token_encryption
from utils.logger import logger


class UploadRequest:
    """Represents a file upload request"""
    
    def __init__(
        self,
        file_path: str,
        file_type: str,
        channel_id: str,
        metadata: Dict[str, Any] = None
    ):
        self.file_path = file_path
        self.file_type = file_type  # 'video' or 'thumbnail'
        self.channel_id = channel_id
        self.metadata = metadata or {}
        self.status = "pending"
        self.progress = 0
        self.error = None
        self.result = None
        self.video_id = None  # For thumbnail association
        
    @property
    def is_video(self) -> bool:
        return self.file_type == "video"
    
    @property
    def is_thumbnail(self) -> bool:
        return self.file_type == "thumbnail"


class YouTubeFileService:
    """Service for managing YouTube video and thumbnail file references"""
    
    # File type extensions
    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.mpg', '.mpeg', '.3gp'}
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}
    
    # Video MIME types supported by YouTube
    VIDEO_MIME_TYPES = [
        'video/mp4',
        'video/quicktime',
        'video/x-msvideo',
        'video/x-ms-wmv',
        'video/x-flv',
        'video/x-matroska',
        'video/webm',
        'video/x-m4v',
        'video/3gpp',
        'video/3gpp2',
        'video/mpeg'
    ]
    
    # Image MIME types for thumbnails
    IMAGE_MIME_TYPES = [
        'image/jpeg',
        'image/jpg',
        'image/png',
        'image/gif',
        'image/webp'
    ]
    
    # File size limits
    MAX_VIDEO_SIZE = 128 * 1024 * 1024 * 1024  # 128GB (YouTube limit)
    MAX_THUMBNAIL_SIZE = 2 * 1024 * 1024  # 2MB (YouTube limit)
    MAX_TITLE_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 5000
    
    # Expiration times
    QUICK_UPLOAD_EXPIRY = timedelta(minutes=30)
    PREPARED_UPLOAD_EXPIRY = timedelta(hours=24)
    
    def __init__(self, db: DBConnection, user_id: str = None):
        self.db = db
        self.user_id = user_id
        self.cache = get_channel_cache()
        self.refresh_manager = get_refresh_manager()
        self.encryption = get_token_encryption()
        
        # Thread pool for file operations
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Upload tracking
        self.active_uploads: Dict[str, UploadRequest] = {}
        self.upload_queue: asyncio.Queue = asyncio.Queue()
        self.upload_workers: List[asyncio.Task] = []
        
        if user_id:
            logger.info(f"YouTubeFileService initialized for user {user_id}")
    
    def detect_file_type(self, mime_type: str, file_name: str = "") -> str:
        """
        Detect whether a file is a video or thumbnail based on MIME type
        
        Args:
            mime_type: MIME type of the file
            file_name: Optional filename for extension-based detection
        
        Returns:
            'video', 'thumbnail', or 'unknown'
        """
        # Check MIME type first
        if mime_type in self.VIDEO_MIME_TYPES or mime_type.startswith('video/'):
            return 'video'
        
        if mime_type in self.IMAGE_MIME_TYPES or mime_type.startswith('image/'):
            return 'thumbnail'
        
        # Fallback to extension if MIME type is unclear
        if file_name:
            ext = os.path.splitext(file_name.lower())[1]
            video_extensions = ['.mp4', '.mov', '.avi', '.wmv', '.flv', '.mkv', '.webm', '.m4v', '.3gp', '.3g2', '.mpg', '.mpeg']
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
            
            if ext in video_extensions:
                return 'video'
            if ext in image_extensions:
                return 'thumbnail'
        
        return 'unknown'
    
    def generate_reference_id(self) -> str:
        """Generate a 32-character hex reference ID"""
        return secrets.token_hex(16)
    
    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def calculate_checksum(self, file_data: bytes) -> str:
        """Calculate SHA256 checksum of file data"""
        return hashlib.sha256(file_data).hexdigest()
    
    async def validate_video_file(self, file_data: bytes, file_name: str, mime_type: str) -> Dict[str, Any]:
        """
        Validate a video file for YouTube upload
        
        Returns:
            Dict with validation results and any errors
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check file size
        file_size = len(file_data)
        if file_size > self.MAX_VIDEO_SIZE:
            result["valid"] = False
            result["errors"].append(f"Video exceeds YouTube's 128GB limit ({self.format_file_size(file_size)})")
        
        # Check MIME type
        if mime_type not in self.VIDEO_MIME_TYPES and not mime_type.startswith('video/'):
            result["warnings"].append(f"Unusual video MIME type: {mime_type}")
        
        # Check extension
        ext = os.path.splitext(file_name.lower())[1]
        valid_extensions = ['.mp4', '.mov', '.avi', '.wmv', '.flv', '.mkv', '.webm', '.m4v', '.3gp', '.3g2', '.mpg', '.mpeg']
        if ext not in valid_extensions:
            result["warnings"].append(f"Unusual video extension: {ext}")
        
        return result
    
    async def validate_thumbnail_file(self, file_data: bytes, file_name: str, mime_type: str) -> Dict[str, Any]:
        """
        Validate a thumbnail file for YouTube upload
        
        Returns:
            Dict with validation results and any errors
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "dimensions": None
        }
        
        # Check file size
        file_size = len(file_data)
        if file_size > self.MAX_THUMBNAIL_SIZE:
            result["valid"] = False
            result["errors"].append(f"Thumbnail exceeds YouTube's 2MB limit ({self.format_file_size(file_size)})")
        
        # Check MIME type
        if mime_type not in self.IMAGE_MIME_TYPES and not mime_type.startswith('image/'):
            result["valid"] = False
            result["errors"].append(f"Invalid image MIME type: {mime_type}")
        
        # Check dimensions
        try:
            img = Image.open(BytesIO(file_data))
            width, height = img.size
            result["dimensions"] = {"width": width, "height": height}
            
            # YouTube recommends 1280x720 minimum, 16:9 aspect ratio
            if width < 1280 or height < 720:
                result["warnings"].append(f"Thumbnail resolution ({width}x{height}) is below recommended 1280x720")
            
            aspect_ratio = width / height
            if abs(aspect_ratio - 16/9) > 0.1:  # Allow some tolerance
                result["warnings"].append(f"Thumbnail aspect ratio ({aspect_ratio:.2f}) differs from recommended 16:9")
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Failed to process image: {str(e)}")
        
        return result
    
    async def process_thumbnail(self, file_data: bytes, file_name: str) -> Tuple[bytes, Dict[str, Any]]:
        """
        Process and optimize thumbnail image for YouTube
        Resizes to 1280x720 if needed and optimizes file size
        
        Returns:
            Tuple of (processed_data, metadata)
        """
        try:
            img = Image.open(BytesIO(file_data))
            
            # Convert to RGB if necessary
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGB')
            
            # Calculate target dimensions (16:9 aspect ratio)
            target_width = 1280
            target_height = 720
            
            # Resize to target dimensions, maintaining aspect ratio with padding if needed
            img_ratio = img.width / img.height
            target_ratio = target_width / target_height
            
            if img_ratio > target_ratio:
                # Image is wider, fit to width
                new_width = target_width
                new_height = int(target_width / img_ratio)
            else:
                # Image is taller, fit to height
                new_height = target_height
                new_width = int(target_height * img_ratio)
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Create a new image with padding if needed
            if new_width != target_width or new_height != target_height:
                padded = Image.new('RGB', (target_width, target_height), (0, 0, 0))
                x_offset = (target_width - new_width) // 2
                y_offset = (target_height - new_height) // 2
                padded.paste(img, (x_offset, y_offset))
                img = padded
            
            # Save optimized image
            output = BytesIO()
            img.save(output, format='JPEG', quality=90, optimize=True)
            processed_data = output.getvalue()
            
            metadata = {
                "original_size": len(file_data),
                "processed_size": len(processed_data),
                "dimensions": {"width": target_width, "height": target_height},
                "format": "JPEG"
            }
            
            return processed_data, metadata
            
        except Exception as e:
            logger.error(f"Failed to process thumbnail: {e}")
            raise
    
    async def create_video_reference(
        self,
        user_id: str,
        file_name: str,
        file_data: bytes,
        mime_type: str,
        expiry_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Create a video file reference in the database
        
        Returns:
            Dict with reference_id and file information
        """
        reference_id = self.generate_reference_id()
        file_size = len(file_data)
        checksum = self.calculate_checksum(file_data)
        
        # Validate video file
        validation = await self.validate_video_file(file_data, file_name, mime_type)
        if not validation["valid"]:
            raise ValueError(f"Invalid video file: {', '.join(validation['errors'])}")
        
        # Store in video_file_references table
        client = await self.db.client
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
        
        video_ref_data = {
            "id": reference_id,
            "user_id": user_id,
            "file_name": file_name,
            "file_data": base64.b64encode(file_data).decode('utf-8'),  # Base64 encode for JSON serialization
            "file_size": file_size,
            "mime_type": mime_type,
            "file_type": "video",
            "checksum": checksum,
            "expires_at": expires_at.isoformat(),
            "platform": "youtube"
        }
        
        result = await client.table("video_file_references").insert(video_ref_data).execute()
        
        if not result.data:
            raise Exception("Failed to create video reference")
        
        # Create upload reference
        upload_ref_data = {
            "user_id": user_id,
            "reference_id": reference_id,
            "file_name": file_name,
            "file_size": file_size,  # Store as integer, not formatted string
            "file_type": "video",
            "mime_type": mime_type,
            "platform": "youtube",
            "status": "ready",  # Mark as ready since file is uploaded
            "created_at": datetime.now(timezone.utc).isoformat(),
            "ready_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat()
        }
        
        await client.table("upload_references").insert(upload_ref_data).execute()
        
        return {
            "reference_id": reference_id,
            "file_name": file_name,
            "file_size": file_size,  # Return numeric size, not formatted string
            "mime_type": mime_type,
            "expires_at": expires_at.isoformat(),
            "warnings": validation.get("warnings", [])
        }
    
    async def create_thumbnail_reference(
        self,
        user_id: str,
        file_name: str,
        file_data: bytes,
        mime_type: str,
        expiry_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Create a thumbnail file reference in the database
        Processes and optimizes the image before storing
        
        Returns:
            Dict with reference_id and file information
        """
        # Validate thumbnail
        validation = await self.validate_thumbnail_file(file_data, file_name, mime_type)
        if not validation["valid"]:
            raise ValueError(f"Invalid thumbnail file: {', '.join(validation['errors'])}")
        
        # Process and optimize thumbnail
        processed_data, metadata = await self.process_thumbnail(file_data, file_name)
        
        reference_id = self.generate_reference_id()
        checksum = self.calculate_checksum(processed_data)
        
        # Store in video_file_references table (also used for thumbnails)
        client = await self.db.client
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
        
        thumb_ref_data = {
            "id": reference_id,
            "user_id": user_id,
            "file_name": file_name,
            "file_data": base64.b64encode(processed_data).decode('utf-8'),  # Base64 encode for JSON serialization
            "file_size": len(processed_data),
            "mime_type": "image/jpeg",  # Always JPEG after processing
            "file_type": "thumbnail",
            "checksum": checksum,
            "expires_at": expires_at.isoformat(),
            "platform": "youtube",
            "generated_metadata": metadata  # Store processing metadata
        }
        
        result = await client.table("video_file_references").insert(thumb_ref_data).execute()
        
        if not result.data:
            raise Exception("Failed to create thumbnail reference")
        
        # Create upload reference
        upload_ref_data = {
            "user_id": user_id,
            "reference_id": reference_id,
            "file_name": file_name,
            "file_size": len(processed_data),  # Store as integer, not formatted string
            "file_type": "thumbnail",
            "mime_type": "image/jpeg",
            "platform": "youtube",
            "status": "ready",  # Mark as ready since file is uploaded
            "created_at": datetime.now(timezone.utc).isoformat(),
            "ready_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat()
        }
        
        await client.table("upload_references").insert(upload_ref_data).execute()
        
        return {
            "reference_id": reference_id,
            "file_name": file_name,
            "file_size": len(processed_data),  # Return numeric size, not formatted string
            "dimensions": metadata["dimensions"],
            "mime_type": "image/jpeg",
            "expires_at": expires_at.isoformat(),
            "warnings": validation.get("warnings", [])
        }
    
    async def get_latest_pending_uploads(self, user_id: str) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get the latest pending video and thumbnail uploads for a user
        Automatically pairs the most recent of each type
        
        Returns:
            Dict with 'video' and 'thumbnail' keys
        """
        logger.info(f"[FileService] Looking for pending uploads for user {user_id}")
        client = await self.db.client
        
        # Get last 10 ready uploads for the user  
        result = await client.table("upload_references").select("*").eq(
            "user_id", user_id
        ).eq(
            "status", "ready"  # Look for ready uploads, not pending
        ).gt(
            "expires_at", datetime.now(timezone.utc).isoformat()
        ).order(
            "created_at", desc=True
        ).limit(10).execute()
        
        uploads = result.data if result.data else []
        logger.info(f"[FileService] Found {len(uploads)} ready uploads in database")
        
        # Find the most recent video and thumbnail
        video = None
        thumbnail = None
        
        for upload in uploads:
            logger.debug(f"[FileService] Upload: {upload['file_name']} - Type: {upload['file_type']} - Ref: {upload['reference_id']}")
            if upload["file_type"] == "video" and not video:
                video = upload
                logger.info(f"[FileService] Found video: {upload['file_name']} (ref: {upload['reference_id']})")
            elif upload["file_type"] == "thumbnail" and not thumbnail:
                thumbnail = upload
                logger.info(f"[FileService] Found thumbnail: {upload['file_name']} (ref: {upload['reference_id']})")
            
            # Stop if we found both
            if video and thumbnail:
                break
        
        if not video:
            logger.warning(f"[FileService] No video found for user {user_id}")
        if not thumbnail:
            logger.debug(f"[FileService] No thumbnail found for user {user_id} (optional)")
        
        return {
            "video": video,
            "thumbnail": thumbnail
        }
    
    async def mark_references_as_used(self, reference_ids: List[str]) -> None:
        """Mark upload references as used after successful upload"""
        client = await self.db.client
        
        for ref_id in reference_ids:
            await client.table("upload_references").update({
                "status": "used"
            }).eq("reference_id", ref_id).execute()
    
    async def get_file_data(self, reference_id: str, user_id: str) -> Optional[bytes]:
        """
        Retrieve file data by reference ID from database
        
        Returns the actual binary file data stored in the database
        """
        client = await self.db.client
        logger.info(f"[FileService] Getting file data for reference_id: {reference_id}")
        
        # First check upload_references for metadata
        upload_ref_result = await client.table("upload_references").select("*").eq(
            "reference_id", reference_id
        ).eq("user_id", user_id).execute()
        
        if upload_ref_result.data:
            logger.info(f"[FileService] Found reference in upload_references table")
            # upload_references found, but file_data is in video_file_references
            # Use the reference_id to get the actual file data
            video_ref_result = await client.table("video_file_references").select("*").eq(
                "id", reference_id
            ).eq("user_id", user_id).execute()
            
            if video_ref_result.data:
                logger.info(f"[FileService] Found file data in video_file_references table")
                file_info = video_ref_result.data[0]
                file_data = file_info.get("file_data")
            else:
                logger.warning(f"[FileService] Reference {reference_id} found in upload_references but no file_data in video_file_references")
                return None
        else:
            # Fallback to old table for backward compatibility
            logger.info(f"Reference {reference_id} not found in upload_references, trying video_file_references directly")
            result = await client.table("video_file_references").select("*").eq(
                "id", reference_id
            ).eq("user_id", user_id).execute()
            
            if not result.data:
                logger.warning(f"No reference found for {reference_id} in either table")
                return None
            
            file_info = result.data[0]
            file_data = file_info.get("file_data")
        
        if not file_data:
            logger.warning(f"No file data in reference {reference_id}")
            return None
        
        # Log file data info for debugging
        logger.info(f"[FileService] Retrieved file_data type: {type(file_data)}, size: {len(file_data) if hasattr(file_data, '__len__') else 'unknown'}")
        
        # Handle different data formats (bytes or base64 string)
        if isinstance(file_data, str):
            # PostgreSQL BYTEA columns return hex-encoded data through JSON API
            # Format: \x followed by hex characters
            if file_data.startswith('\\x'):
                # Decode from hex first
                try:
                    hex_str = file_data[2:]  # Remove \x prefix
                    # Convert hex to bytes
                    hex_bytes = bytes.fromhex(hex_str)
                    # The hex_bytes now contains the base64 string as bytes
                    base64_str = hex_bytes.decode('utf-8')
                    logger.info(f"Decoded hex to base64 string: {base64_str[:50]}...")
                    # Now decode the base64
                    return base64.b64decode(base64_str)
                except Exception as e:
                    logger.error(f"Failed to decode hex-encoded data: {e}")
                    logger.error(f"Data prefix: {file_data[:100]}")
                    raise
            else:
                # Direct base64 string (shouldn't happen with BYTEA columns)
                logger.info(f"Retrieved direct base64 string of length {len(file_data)}")
                try:
                    return base64.b64decode(file_data)
                except Exception as e:
                    logger.error(f"Failed to decode base64 data: {e}")
                    logger.error(f"Data length: {len(file_data)}")
                    logger.error(f"First 100 chars: {file_data[:100]}")
                    raise
        elif isinstance(file_data, bytes):
            logger.info(f"[FileService] Retrieved raw bytes data, size: {len(file_data)} bytes")
            # Validate file data is not empty and has reasonable size
            if len(file_data) < 100:
                logger.warning(f"[FileService] File data suspiciously small: {len(file_data)} bytes")
            elif len(file_data) > 100000000:  # 100MB
                logger.info(f"[FileService] Large file detected: {len(file_data)} bytes")
            return file_data
        else:
            logger.error(f"Unexpected file data type: {type(file_data)}")
            return None
    
    async def cleanup_expired_references(self) -> int:
        """
        Clean up expired file references
        
        Returns:
            Number of references cleaned up
        """
        client = await self.db.client
        
        # First, update status of expired references to 'expired'
        await client.table("upload_references").update({
            "status": "expired"
        }).lt(
            "expires_at", datetime.now(timezone.utc).isoformat()
        ).neq("status", "used").execute()
        
        # Delete expired upload references that are not used
        result = await client.table("upload_references").delete().lt(
            "expires_at", datetime.now(timezone.utc).isoformat()
        ).neq("status", "used").execute()
        
        upload_count = len(result.data) if result.data else 0
        
        # Delete expired video file references that haven't been used
        result = await client.table("video_file_references").delete().lt(
            "expires_at", datetime.now(timezone.utc).isoformat()
        ).eq("is_used", False).execute()
        
        file_count = len(result.data) if result.data else 0
        
        logger.info(f"Cleaned up {upload_count} upload references and {file_count} file references")
        
        return upload_count + file_count
    
    async def detect_file_type_enhanced(self, file_path: str) -> str:
        """
        Intelligently detect if file is video or thumbnail
        
        Args:
            file_path: Path to file
            
        Returns:
            'video', 'thumbnail', or 'unknown'
        """
        # Get file extension
        ext = Path(file_path).suffix.lower()
        
        # Check by extension
        if ext in self.VIDEO_EXTENSIONS:
            return "video"
        elif ext in self.IMAGE_EXTENSIONS:
            return "thumbnail"
        
        # Check by MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type:
            if mime_type.startswith('video/'):
                return "video"
            elif mime_type.startswith('image/'):
                return "thumbnail"
        
        # Check file size as last resort
        try:
            size = os.path.getsize(file_path)
            if size > 10 * 1024 * 1024:  # > 10MB likely video
                return "video"
            elif size < 5 * 1024 * 1024:  # < 5MB likely thumbnail
                return "thumbnail"
        except:
            pass
        
        return "unknown"
    
    async def pair_files(self, files: List[str]) -> List[Tuple[str, Optional[str]]]:
        """
        Intelligently pair video files with their thumbnails
        
        Args:
            files: List of file paths
            
        Returns:
            List of (video_path, thumbnail_path) tuples
        """
        videos = []
        thumbnails = []
        
        # Categorize files
        for file_path in files:
            file_type = await self.detect_file_type_enhanced(file_path)
            if file_type == "video":
                videos.append(file_path)
            elif file_type == "thumbnail":
                thumbnails.append(file_path)
        
        # Pair based on filename similarity
        pairs = []
        used_thumbnails = set()
        
        for video in videos:
            video_name = Path(video).stem.lower()
            best_match = None
            best_score = 0
            
            for thumbnail in thumbnails:
                if thumbnail in used_thumbnails:
                    continue
                
                thumb_name = Path(thumbnail).stem.lower()
                
                # Calculate similarity score
                score = self._calculate_similarity(video_name, thumb_name)
                
                # Check for common patterns
                if thumb_name == video_name:
                    score = 1.0
                elif thumb_name == f"{video_name}_thumb":
                    score = 0.95
                elif thumb_name == f"{video_name}_thumbnail":
                    score = 0.95
                elif video_name in thumb_name or thumb_name in video_name:
                    score = max(score, 0.8)
                
                if score > best_score:
                    best_score = score
                    best_match = thumbnail
            
            # Pair if good match found
            if best_match and best_score > 0.5:
                pairs.append((video, best_match))
                used_thumbnails.add(best_match)
            else:
                pairs.append((video, None))
        
        # Add unpaired thumbnails
        for thumbnail in thumbnails:
            if thumbnail not in used_thumbnails:
                logger.warning(f"Unpaired thumbnail: {thumbnail}")
        
        return pairs
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity using character overlap and position"""
        if str1 == str2:
            return 1.0
        
        len1, len2 = len(str1), len(str2)
        if len1 == 0 or len2 == 0:
            return 0.0
        
        # Check if one string contains the other
        if str1 in str2 or str2 in str1:
            shorter = min(len1, len2)
            longer = max(len1, len2)
            return shorter / longer
        
        # Character overlap with position weighting
        common_chars = set(str1) & set(str2)
        if not common_chars:
            return 0.0
        
        # Calculate overlap ratio
        overlap_score = len(common_chars) / len(set(str1) | set(str2))
        
        # Bonus for matching prefix
        prefix_match = 0
        for i in range(min(len1, len2)):
            if str1[i] == str2[i]:
                prefix_match += 1
            else:
                break
        
        prefix_score = prefix_match / max(len1, len2)
        
        # Combined score
        return (overlap_score + prefix_score) / 2
    
    async def upload_to_channels(
        self,
        files: List[str],
        channel_ids: List[str],
        metadata: Dict[str, Any] = None,
        parallel: bool = True
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Upload files to multiple YouTube channels
        
        Args:
            files: List of file paths to upload
            channel_ids: List of YouTube channel IDs
            metadata: Upload metadata (title, description, etc.)
            parallel: Whether to upload to channels in parallel
            
        Returns:
            Dictionary mapping channel_id to list of upload results
        """
        logger.info(f"Starting multi-channel upload: {len(files)} files to {len(channel_ids)} channels")
        
        # Pair videos with thumbnails
        file_pairs = await self.pair_files(files)
        
        # Validate channels
        valid_channels = await self._validate_channels(channel_ids)
        if not valid_channels:
            raise ValueError("No valid channels found for upload")
        
        # Prepare upload requests
        upload_tasks = []
        results = {}
        
        for channel_id in valid_channels:
            for video_path, thumbnail_path in file_pairs:
                # Create upload request for video
                video_req = UploadRequest(
                    file_path=video_path,
                    file_type="video",
                    channel_id=channel_id,
                    metadata=metadata
                )
                
                # Create upload request for thumbnail if exists
                thumb_req = None
                if thumbnail_path:
                    thumb_req = UploadRequest(
                        file_path=thumbnail_path,
                        file_type="thumbnail",
                        channel_id=channel_id,
                        metadata={}
                    )
                
                if parallel:
                    # Queue for parallel processing
                    upload_tasks.append(
                        self._upload_video_with_thumbnail(video_req, thumb_req)
                    )
                else:
                    # Process sequentially
                    result = await self._upload_video_with_thumbnail(video_req, thumb_req)
                    if channel_id not in results:
                        results[channel_id] = []
                    results[channel_id].append(result)
        
        # Process parallel uploads
        if parallel and upload_tasks:
            results = {}
            upload_results = await asyncio.gather(*upload_tasks, return_exceptions=True)
            
            # Group results by channel
            for i, result in enumerate(upload_results):
                channel_id = valid_channels[i % len(valid_channels)]
                if channel_id not in results:
                    results[channel_id] = []
                
                if isinstance(result, Exception):
                    results[channel_id].append({
                        "success": False,
                        "error": str(result)
                    })
                else:
                    results[channel_id].append(result)
            
            return results
        
        return results if not parallel else {}
    
    async def _validate_channels(self, channel_ids: List[str]) -> List[str]:
        """Validate and filter channels that are ready for upload"""
        valid_channels = []
        
        for channel_id in channel_ids:
            # Check if channel exists and is active
            client = await self.db.client
            result = await client.table("youtube_channels").select("*").eq(
                "user_id", self.user_id
            ).eq("id", channel_id).eq("is_active", True).execute()
            
            if result.data:
                channel = result.data[0]
                
                # Check token validity
                token_expires = channel.get("token_expires_at")
                if token_expires:
                    expiry = datetime.fromisoformat(token_expires.replace('Z', '+00:00'))
                    
                    # Refresh if needed (5 min buffer)
                    if expiry <= datetime.now(timezone.utc) + timedelta(minutes=5):
                        logger.info(f"Refreshing token for channel {channel_id}")
                        
                        try:
                            encrypted_refresh = channel.get("refresh_token")
                            if encrypted_refresh:
                                refresh_token = self.encryption.decrypt_token(encrypted_refresh)
                                await self.refresh_manager.refresh_token(
                                    self.user_id,
                                    channel_id,
                                    refresh_token,
                                    priority=1  # High priority for active upload
                                )
                                valid_channels.append(channel_id)
                            else:
                                logger.warning(f"No refresh token for channel {channel_id}")
                        except Exception as e:
                            logger.error(f"Failed to refresh token for channel {channel_id}: {e}")
                    else:
                        valid_channels.append(channel_id)
                else:
                    logger.warning(f"No token expiry for channel {channel_id}")
            else:
                logger.warning(f"Channel {channel_id} not found or inactive")
        
        return valid_channels
    
    async def _upload_video_with_thumbnail(
        self,
        video_request: UploadRequest,
        thumbnail_request: Optional[UploadRequest] = None
    ) -> Dict[str, Any]:
        """
        Upload a video and optionally its thumbnail
        
        Args:
            video_request: Video upload request
            thumbnail_request: Optional thumbnail upload request
            
        Returns:
            Upload result dictionary
        """
        try:
            # Upload video first
            logger.info(f"Uploading video {video_request.file_path} to channel {video_request.channel_id}")
            
            # Get channel tokens
            access_token = await self._get_channel_token(video_request.channel_id)
            
            # Prepare video metadata
            video_metadata = self._prepare_video_metadata(
                video_request.file_path,
                video_request.metadata
            )
            
            # Upload video to YouTube
            video_result = await self._youtube_upload_video(
                access_token,
                video_request.file_path,
                video_metadata
            )
            
            video_id = video_result.get("id")
            video_request.video_id = video_id
            
            # Upload thumbnail if provided
            thumbnail_result = None
            if thumbnail_request and video_id:
                logger.info(f"Uploading thumbnail for video {video_id}")
                
                thumbnail_result = await self._youtube_upload_thumbnail(
                    access_token,
                    video_id,
                    thumbnail_request.file_path
                )
            
            # Store upload record
            await self._store_upload_record(
                video_request.channel_id,
                video_id,
                video_request.file_path,
                thumbnail_request.file_path if thumbnail_request else None,
                video_metadata
            )
            
            return {
                "success": True,
                "channel_id": video_request.channel_id,
                "video_id": video_id,
                "video_url": f"https://youtube.com/watch?v={video_id}",
                "thumbnail_uploaded": thumbnail_result is not None,
                "metadata": video_metadata
            }
            
        except Exception as e:
            logger.error(f"Upload failed for {video_request.file_path}: {e}")
            return {
                "success": False,
                "channel_id": video_request.channel_id,
                "error": str(e),
                "file_path": video_request.file_path
            }
    
    async def _get_channel_token(self, channel_id: str) -> str:
        """Get decrypted access token for channel"""
        # Check cache first
        cached = await self.cache.get_channel_tokens(self.user_id, channel_id)
        if cached:
            access_token, _, expiry = cached
            if expiry > datetime.now(timezone.utc) + timedelta(minutes=5):
                return access_token
        
        # Get from database
        client = await self.db.client
        result = await client.table("youtube_channels").select(
            "access_token, refresh_token, token_expires_at"
        ).eq("user_id", self.user_id).eq("id", channel_id).execute()
        
        if not result.data:
            raise ValueError(f"Channel {channel_id} not found")
        
        channel = result.data[0]
        encrypted_access = channel["access_token"]
        
        # Decrypt token
        access_token = self.encryption.decrypt_token(encrypted_access)
        
        # Check if needs refresh
        token_expires = channel.get("token_expires_at")
        if token_expires:
            expiry = datetime.fromisoformat(token_expires.replace('Z', '+00:00'))
            
            if expiry <= datetime.now(timezone.utc) + timedelta(minutes=5):
                # Refresh token
                encrypted_refresh = channel["refresh_token"]
                refresh_token = self.encryption.decrypt_token(encrypted_refresh)
                
                access_token, expiry = await self.refresh_manager.refresh_token(
                    self.user_id,
                    channel_id,
                    refresh_token,
                    priority=2
                )
        
        return access_token
    
    def _prepare_video_metadata(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Prepare video metadata for upload"""
        # Default metadata
        default_title = Path(file_path).stem
        default_description = f"Uploaded via Rzvi on {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        
        # Merge with provided metadata
        final_metadata = {
            "title": default_title,
            "description": default_description,
            "tags": [],
            "category_id": "22",  # People & Blogs
            "privacy": "private",  # Default to private
            "made_for_kids": False,
            "notify_subscribers": False
        }
        
        if metadata:
            final_metadata.update(metadata)
        
        # Validate and truncate
        final_metadata["title"] = final_metadata["title"][:self.MAX_TITLE_LENGTH]
        final_metadata["description"] = final_metadata["description"][:self.MAX_DESCRIPTION_LENGTH]
        
        return final_metadata
    
    async def _youtube_upload_video(
        self,
        access_token: str,
        file_path: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Upload video to YouTube using resumable upload"""
        # This would implement the actual YouTube Data API v3 resumable upload
        # For now, returning mock result
        logger.info(f"Would upload video: {file_path} with metadata: {metadata}")
        
        # In production, this would:
        # 1. Create upload session
        # 2. Upload file in chunks
        # 3. Handle resumable upload protocol
        # 4. Return video ID and details
        
        import uuid
        return {
            "id": f"mock_{uuid.uuid4().hex[:11]}",
            "status": "uploaded",
            "title": metadata["title"]
        }
    
    async def _youtube_upload_thumbnail(
        self,
        access_token: str,
        video_id: str,
        thumbnail_path: str
    ) -> Dict[str, Any]:
        """Upload thumbnail for a video"""
        # This would implement the actual YouTube thumbnail upload
        logger.info(f"Would upload thumbnail: {thumbnail_path} for video: {video_id}")
        
        return {
            "success": True,
            "video_id": video_id
        }
    
    async def _store_upload_record(
        self,
        channel_id: str,
        video_id: str,
        video_path: str,
        thumbnail_path: Optional[str],
        metadata: Dict[str, Any]
    ):
        """Store upload record in database"""
        client = await self.db.client
        
        # Check if table exists, if not create minimal record
        try:
            record = {
                "user_id": self.user_id,
                "channel_id": channel_id,
                "video_id": video_id,
                "video_path": video_path,
                "thumbnail_path": thumbnail_path,
                "metadata": metadata,
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "status": "completed"
            }
            
            await client.table("youtube_uploads").insert(record).execute()
            logger.info(f"Stored upload record for video {video_id}")
        except Exception as e:
            logger.warning(f"Could not store upload record (table may not exist): {e}")
    
    async def get_upload_history(
        self,
        channel_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get upload history for user or specific channel"""
        try:
            client = await self.db.client
            
            query = client.table("youtube_uploads").select("*").eq(
                "user_id", self.user_id
            )
            
            if channel_id:
                query = query.eq("channel_id", channel_id)
            
            result = await query.order(
                "uploaded_at", desc=True
            ).limit(limit).execute()
            
            return result.data if result.data else []
        except Exception as e:
            logger.warning(f"Could not fetch upload history: {e}")
            return []
    
    async def cleanup(self):
        """Cleanup resources"""
        self.executor.shutdown(wait=False)
        logger.info("YouTubeFileService cleaned up")