"""Generic File Upload API

Universal file upload endpoints for all file types.
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from typing import Dict, Any, Optional, List
from utils.auth_utils import get_current_user_id_from_jwt
from utils.logger import logger
from services.supabase import DBConnection
from services.file_upload_service import FileUploadService

router = APIRouter(prefix="/files", tags=["Files"])

# Database connection
db: Optional[DBConnection] = None


def initialize(database: DBConnection):
    """Initialize Files API with database connection"""
    global db
    db = database


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """
    Upload a file and create a reference.
    Supports all file types - images, documents, videos, etc.
    
    Args:
        file: The file to upload
        description: Optional description of the file
        user_id: User ID from JWT
        
    Returns:
        File reference information
    """
    try:
        # Initialize file service
        file_service = FileUploadService(db)
        
        # Read file data
        file_data = await file.read()
        
        # Get MIME type
        mime_type = file.content_type or "application/octet-stream"
        
        # Create file reference
        result = await file_service.create_file_reference(
            user_id=user_id,
            file_name=file.filename,
            file_data=file_data,
            mime_type=mime_type,
            description=description
        )
        
        logger.info(f"File uploaded for user {user_id}: {result['file_id']}")
        
        return {
            "success": True,
            **result
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_files(
    category: Optional[str] = None,
    limit: int = 50,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """
    List user's uploaded files.
    
    Args:
        category: Optional filter by file category (image, video, document, audio, other)
        limit: Maximum number of files to return (default 50)
        user_id: User ID from JWT
        
    Returns:
        List of file references
    """
    try:
        file_service = FileUploadService(db)
        
        files = await file_service.list_user_files(
            user_id=user_id,
            file_category=category,
            limit=limit
        )
        
        return {
            "success": True,
            "files": files,
            "count": len(files)
        }
        
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{file_id}")
async def get_file_info(
    file_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """
    Get file reference information.
    
    Args:
        file_id: File ID
        user_id: User ID from JWT
        
    Returns:
        File reference information
    """
    try:
        file_service = FileUploadService(db)
        
        file_ref = await file_service.get_file_reference(
            file_id=file_id,
            user_id=user_id
        )
        
        if not file_ref:
            raise HTTPException(status_code=404, detail="File not found")
        
        return {
            "success": True,
            "file": file_ref
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{file_id}/content")
async def get_file_content(
    file_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> bytes:
    """
    Get actual file content.
    
    Args:
        file_id: File ID
        user_id: User ID from JWT
        
    Returns:
        File content as bytes
    """
    try:
        file_service = FileUploadService(db)
        
        # Get file reference first to check permissions and get mime type
        file_ref = await file_service.get_file_reference(
            file_id=file_id,
            user_id=user_id
        )
        
        if not file_ref:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Get file content
        content = await file_service.get_file_content(
            file_id=file_id,
            user_id=user_id
        )
        
        if content is None:
            raise HTTPException(status_code=404, detail="File content not found")
        
        # Return with appropriate headers
        from fastapi.responses import Response
        return Response(
            content=content,
            media_type=file_ref["mime_type"],
            headers={
                "Content-Disposition": f'inline; filename="{file_ref["file_name"]}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """
    Delete a file.
    
    Args:
        file_id: File ID
        user_id: User ID from JWT
        
    Returns:
        Success status
    """
    try:
        file_service = FileUploadService(db)
        
        success = await file_service.delete_file(
            file_id=file_id,
            user_id=user_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="File not found")
        
        return {
            "success": True,
            "message": f"File {file_id} deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def cleanup_expired_files(
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """
    Clean up expired files.
    This is typically called by a background task.
    
    Returns:
        Number of files cleaned up
    """
    try:
        file_service = FileUploadService(db)
        
        count = await file_service.cleanup_expired_files()
        
        return {
            "success": True,
            "cleaned_up": count,
            "message": f"Cleaned up {count} expired files"
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup expired files: {e}")
        raise HTTPException(status_code=500, detail=str(e))