"""
Utility functions for Veo3 MCP service.

This module provides common utility functions for file handling,
GCS operations, MIME type inference, and other helper operations.
"""

import os
import re
import asyncio
import hashlib
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlparse
import logging

from google.cloud import storage
from google.cloud.exceptions import NotFound
import aiofiles
import httpx

logger = logging.getLogger(__name__)


def infer_mime_type_from_uri(uri: str) -> Optional[str]:
    """
    Infer MIME type from a file URI based on its extension.
    
    Args:
        uri: File URI (local path or GCS URI)
    
    Returns:
        MIME type string or None if cannot be determined
    """
    # Extract filename from URI
    if uri.startswith("gs://"):
        path = uri.replace("gs://", "").split("/", 1)[-1]
    else:
        path = uri
    
    # Get extension
    ext = Path(path).suffix.lower()
    
    # Map common video/image extensions
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg", 
        ".jpeg": "image/jpeg",
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".webm": "video/webm",
    }
    
    return mime_map.get(ext) or mimetypes.guess_type(path)[0]


def ensure_gcs_path_prefix(path: str) -> str:
    """
    Ensure a GCS path has the gs:// prefix.
    
    Args:
        path: GCS path with or without prefix
    
    Returns:
        GCS path with gs:// prefix
    """
    if not path:
        return path
    
    if not path.startswith("gs://"):
        return f"gs://{path}"
    return path


def parse_gcs_uri(uri: str) -> Tuple[str, str]:
    """
    Parse a GCS URI into bucket and object path.
    
    Args:
        uri: GCS URI (e.g., gs://bucket/path/to/object)
    
    Returns:
        Tuple of (bucket_name, object_path)
    
    Raises:
        ValueError: If URI is not a valid GCS URI
    """
    if not uri.startswith("gs://"):
        raise ValueError(f"Invalid GCS URI: {uri}")
    
    # Remove gs:// prefix and split
    path = uri[5:]
    parts = path.split("/", 1)
    
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


async def download_from_gcs(
    gcs_uri: str,
    local_path: str,
    storage_client: Optional[storage.Client] = None
) -> str:
    """
    Download a file from GCS to local filesystem.
    
    Args:
        gcs_uri: GCS URI of the file to download
        local_path: Local path to save the file
        storage_client: Optional GCS client (will create if not provided)
    
    Returns:
        Local file path
    
    Raises:
        Exception: If download fails
    """
    if storage_client is None:
        storage_client = storage.Client()
    
    bucket_name, object_path = parse_gcs_uri(gcs_uri)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(object_path)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    
    # Download file with timeout (matching Go implementation)
    loop = asyncio.get_event_loop()
    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, blob.download_to_filename, local_path),
            timeout=120  # 2 minute timeout like Go
        )
    except asyncio.TimeoutError:
        raise TimeoutError(f"Download of {gcs_uri} timed out after 120 seconds")
    
    logger.info(f"Successfully downloaded {gcs_uri} to {local_path}")
    return local_path


async def download_from_gcs_as_bytes(
    gcs_uri: str,
    storage_client: Optional[storage.Client] = None,
    max_retries: int = 5
) -> bytes:
    """
    Download a file from GCS as bytes with retry logic.
    
    Args:
        gcs_uri: GCS URI of the file to download
        storage_client: Optional GCS client
        max_retries: Maximum number of retries
    
    Returns:
        File contents as bytes
    
    Raises:
        Exception: If download fails after retries
    """
    if storage_client is None:
        storage_client = storage.Client()
    
    bucket_name, object_path = parse_gcs_uri(gcs_uri)
    bucket = storage_client.bucket(bucket_name)
    
    last_error = None
    for attempt in range(max_retries):
        try:
            blob = bucket.blob(object_path)
            loop = asyncio.get_event_loop()
            try:
                data = await asyncio.wait_for(
                    loop.run_in_executor(None, blob.download_as_bytes),
                    timeout=30  # 30 second timeout per attempt
                )
                return data
            except asyncio.TimeoutError:
                raise TimeoutError(f"Download attempt timed out after 30 seconds")
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                logger.warning(f"Object {gcs_uri} not found, retrying in 3 seconds... (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(3)
            else:
                break
    
    raise Exception(f"Failed to download {gcs_uri} after {max_retries} attempts: {last_error}")


async def upload_to_gcs(
    local_path: str = None,
    gcs_uri: str = None,
    bucket_name: str = None,
    object_name: str = None,
    data: bytes = None,
    storage_client: Optional[storage.Client] = None,
    content_type: Optional[str] = None
) -> str:
    """
    Upload a file or data to GCS with content type inference.
    
    Args:
        local_path: Local path of the file to upload (if uploading file)
        gcs_uri: Target GCS URI (alternative to bucket_name/object_name)
        bucket_name: Bucket name (alternative to gcs_uri)
        object_name: Object name (alternative to gcs_uri)
        data: Raw data to upload (alternative to local_path)
        storage_client: Optional GCS client
        content_type: Optional content type to set
    
    Returns:
        GCS URI of uploaded file
    
    Raises:
        Exception: If upload fails
    """
    if storage_client is None:
        storage_client = storage.Client()
    
    # Parse bucket and object name
    if gcs_uri:
        bucket_name, object_name = parse_gcs_uri(gcs_uri)
    elif not bucket_name or not object_name:
        raise ValueError("Must provide either gcs_uri or bucket_name/object_name")
    
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    
    # Infer content type if not provided (matching Go implementation)
    if not content_type and object_name:
        ext = Path(object_name).suffix.lower()
        content_type_map = {
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.mp4': 'video/mp4',
            '.mov': 'video/quicktime',
            '.mkv': 'video/x-matroska',
            '.webm': 'video/webm',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif'
        }
        content_type = content_type_map.get(ext)
        if content_type:
            logger.info(f"Setting ContentType to '{content_type}' for object '{object_name}'")
    
    # Set content type if determined
    if content_type:
        blob.content_type = content_type
    
    # Upload file or data
    loop = asyncio.get_event_loop()
    if local_path:
        await loop.run_in_executor(None, blob.upload_from_filename, local_path)
    elif data:
        await loop.run_in_executor(None, blob.upload_from_string, data)
    else:
        raise ValueError("Must provide either local_path or data to upload")
    
    final_uri = f"gs://{bucket_name}/{object_name}"
    logger.info(f"Successfully uploaded to {final_uri}")
    return final_uri


def generate_operation_id(prefix: str = "veo3") -> str:
    """
    Generate a unique operation ID.
    
    Args:
        prefix: Prefix for the operation ID
    
    Returns:
        Unique operation ID
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    random_suffix = hashlib.md5(os.urandom(16)).hexdigest()[:8]
    return f"{prefix}-{timestamp}-{random_suffix}"


def generate_filename(
    model_name: str,
    mode: str = "video",
    index: int = 0,
    extension: str = "mp4"
) -> str:
    """
    Generate a descriptive filename for generated content.
    Matches Go implementation pattern: veo-{model}-{timestamp}-{index}.mp4
    
    Args:
        model_name: Name of the model used
        mode: Generation mode (video, image, etc.)
        index: Index for multiple outputs
        extension: File extension
    
    Returns:
        Generated filename
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    # Match Go implementation pattern exactly
    return f"veo-{model_name}-{timestamp}-{index}.{extension}"


def sanitize_prompt(prompt: str, max_length: int = 100) -> str:
    """
    Sanitize a prompt for use in filenames or logs.
    
    Args:
        prompt: Original prompt text
        max_length: Maximum length of sanitized prompt
    
    Returns:
        Sanitized prompt string
    """
    # Remove special characters and normalize whitespace
    sanitized = re.sub(r'[^\w\s-]', '', prompt)
    sanitized = re.sub(r'\s+', '_', sanitized)
    
    # Truncate if needed
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized.lower()


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, calls_per_minute: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            calls_per_minute: Maximum calls allowed per minute
        """
        self.calls_per_minute = calls_per_minute
        self.calls: List[datetime] = []
    
    async def acquire(self) -> None:
        """Wait if necessary to respect rate limit."""
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        
        # Remove old calls
        self.calls = [call for call in self.calls if call > minute_ago]
        
        # Check if we need to wait
        if len(self.calls) >= self.calls_per_minute:
            oldest_call = min(self.calls)
            wait_time = (oldest_call + timedelta(minutes=1) - now).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        
        # Record this call
        self.calls.append(now)


def cache_result(ttl_seconds: int = 300) -> Callable:
    """
    Decorator to cache function results with TTL.
    
    Args:
        ttl_seconds: Time to live in seconds
    """
    def decorator(func):
        cache: Dict[str, tuple[Any, datetime]] = {}
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key
            key = f"{args}:{kwargs}"
            
            # Check cache
            if key in cache:
                result, timestamp = cache[key]
                if datetime.utcnow() - timestamp < timedelta(seconds=ttl_seconds):
                    return result
            
            # Call function and cache result
            result = await func(*args, **kwargs)
            cache[key] = (result, datetime.now(timezone.utc))
            return result
        
        # Add method to clear cache
        wrapper.clear_cache = lambda: cache.clear()
        return wrapper
    
    return decorator


async def fetch_with_retry(
    url: str,
    max_retries: int = 3,
    timeout: int = 30,
    **kwargs
) -> httpx.Response:
    """
    Fetch URL with retry logic.
    
    Args:
        url: URL to fetch
        max_retries: Maximum number of retries
        timeout: Request timeout in seconds
        **kwargs: Additional arguments for httpx
    
    Returns:
        HTTP response
    
    Raises:
        Exception: If all retries fail
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(max_retries):
            try:
                response = await client.get(url, **kwargs)
                response.raise_for_status()
                return response
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff


def format_duration(seconds: int) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds}s"
    
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    
    if minutes < 60:
        return f"{minutes}m {remaining_seconds}s" if remaining_seconds else f"{minutes}m"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    parts = [f"{hours}h"]
    if remaining_minutes:
        parts.append(f"{remaining_minutes}m")
    if remaining_seconds:
        parts.append(f"{remaining_seconds}s")
    
    return " ".join(parts)


def format_bytes(bytes_value: int) -> str:
    """
    Format bytes to human-readable string (matching Go FormatBytes).
    
    Args:
        bytes_value: Size in bytes
    
    Returns:
        Human-readable size string
    """
    if bytes_value < 1024:
        return f"{bytes_value} B"
    
    units = "KMGTPE"
    div = 1024
    exp = 0
    
    n = bytes_value // 1024
    while n >= 1024 and exp < len(units) - 1:
        div *= 1024
        n //= 1024
        exp += 1
    
    return f"{bytes_value / div:.1f} {units[exp]}B"


def get_tail(text: str, n: int = 50) -> str:
    """
    Get the last n lines of a string (matching Go GetTail).
    
    Args:
        text: Input text
        n: Number of lines to return
    
    Returns:
        Last n lines of text
    """
    lines = text.split('\n')
    if len(lines) <= n:
        return text
    return '\n'.join(lines[-n:])


def validate_project_id(project_id: str) -> bool:
    """
    Validate Google Cloud project ID format.
    
    Args:
        project_id: Project ID to validate
    
    Returns:
        True if valid, False otherwise
    """
    # GCP project ID rules:
    # - 6-30 characters
    # - Lowercase letters, digits, hyphens
    # - Must start with a letter
    # - Cannot end with a hyphen
    pattern = r'^[a-z][a-z0-9-]{4,28}[a-z0-9]$'
    return bool(re.match(pattern, project_id))


class AsyncContextManager:
    """Base class for async context managers."""
    
    async def __aenter__(self):
        """Enter the context."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context."""
        pass


async def prepare_input_file(
    file_uri: str,
    purpose: str = "processing",
    project_id: Optional[str] = None
) -> Tuple[str, Callable]:
    """
    Prepare an input file for processing (matching Go PrepareInputFile).
    
    If the file is on GCS, downloads it to a temporary directory.
    If it's local, verifies it exists.
    
    Args:
        file_uri: GCS URI or local path
        purpose: Purpose description for logging
        project_id: GCP project ID (required for GCS)
    
    Returns:
        Tuple of (local_path, cleanup_function)
    """
    cleanup_func = lambda: None
    
    if file_uri.startswith("gs://"):
        if not project_id:
            raise ValueError("PROJECT_ID not set, cannot download from GCS")
        
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp(prefix="input_")
        base_name = Path(file_uri).name
        if not base_name or base_name in [".", "/"]:
            base_name = f"gcs_download_{purpose}_{generate_operation_id()}"
        
        local_path = os.path.join(temp_dir, base_name)
        
        logger.info(f"Downloading GCS file {file_uri} to temporary path {local_path} for {purpose}")
        
        # Download from GCS
        storage_client = storage.Client(project=project_id)
        await download_from_gcs(file_uri, local_path, storage_client)
        
        def cleanup():
            logger.info(f"Cleaning up temporary directory for GCS download: {temp_dir}")
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        return local_path, cleanup
    
    # Local file
    if not os.path.exists(file_uri):
        raise FileNotFoundError(f"Local input file {file_uri} does not exist for {purpose}")
    
    logger.info(f"Using local input file {file_uri} for {purpose}")
    return file_uri, cleanup_func


async def handle_output_preparation(
    desired_filename: str = "",
    default_ext: str = "mp4"
) -> Tuple[str, str, Callable]:
    """
    Prepare output file handling (matching Go HandleOutputPreparation).
    
    Args:
        desired_filename: Desired output filename
        default_ext: Default file extension
    
    Returns:
        Tuple of (temp_output_path, final_filename, cleanup_function)
    """
    import tempfile
    import shutil
    
    temp_dir = tempfile.mkdtemp(prefix="output_")
    
    if desired_filename:
        final_filename = desired_filename
        current_ext = Path(final_filename).suffix
        if not current_ext:
            final_filename = f"{final_filename}.{default_ext}"
        elif current_ext.lower() != f".{default_ext.lower()}":
            logger.warning(f"Output filename '{desired_filename}' has extension '{current_ext}', expected '.{default_ext}'")
    else:
        final_filename = f"output_{generate_operation_id()}.{default_ext}"
    
    temp_output_path = os.path.join(temp_dir, final_filename)
    
    def cleanup():
        logger.info(f"Cleaning up temporary output directory: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    logger.info(f"Will write temporary output to: {temp_output_path}")
    logger.info(f"Final output filename will be: {final_filename}")
    
    return temp_output_path, final_filename, cleanup


async def process_output_after_generation(
    temp_output_path: str,
    final_filename: str,
    output_local_dir: Optional[str] = None,
    output_gcs_bucket: Optional[str] = None,
    project_id: Optional[str] = None
) -> Tuple[str, str]:
    """
    Process output after generation (matching Go ProcessOutputAfterFFmpeg).
    
    Args:
        temp_output_path: Temporary output file path
        final_filename: Final output filename
        output_local_dir: Optional local directory to save to
        output_gcs_bucket: Optional GCS bucket to upload to
        project_id: GCP project ID (required for GCS)
    
    Returns:
        Tuple of (final_local_path, final_gcs_path)
    """
    import shutil
    
    final_local_path = temp_output_path
    final_gcs_path = ""
    
    if output_local_dir:
        os.makedirs(output_local_dir, exist_ok=True)
        dest_local_path = os.path.join(output_local_dir, final_filename)
        
        logger.info(f"Moving output from {temp_output_path} to {dest_local_path}")
        
        try:
            shutil.move(temp_output_path, dest_local_path)
        except Exception as e:
            # If move fails, try copy
            logger.warning(f"Move failed ({e}), attempting copy")
            shutil.copy2(temp_output_path, dest_local_path)
            try:
                os.remove(temp_output_path)
            except Exception as rm_err:
                logger.warning(f"Failed to remove original after copy: {rm_err}")
        
        final_local_path = dest_local_path
        logger.info(f"Output saved to local directory: {final_local_path}")
    
    if output_gcs_bucket:
        if not project_id:
            raise ValueError("PROJECT_ID not set, cannot upload to GCS")
        
        if not os.path.exists(final_local_path):
            raise FileNotFoundError(f"Output file {final_local_path} not found for GCS upload")
        
        logger.info(f"Uploading {final_local_path} to GCS bucket {output_gcs_bucket} as {final_filename}")
        
        # Read file data
        with open(final_local_path, 'rb') as f:
            file_data = f.read()
        
        # Upload to GCS
        storage_client = storage.Client(project=project_id)
        await upload_to_gcs(
            gcs_uri=f"gs://{output_gcs_bucket}/{final_filename}",
            data=file_data,
            storage_client=storage_client
        )
        
        final_gcs_path = f"gs://{output_gcs_bucket}/{final_filename}"
        logger.info(f"Output uploaded to GCS: {final_gcs_path}")
    
    return final_local_path, final_gcs_path