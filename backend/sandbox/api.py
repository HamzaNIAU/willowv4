import os
import urllib.parse
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, APIRouter, Form, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel
from daytona_sdk import AsyncSandbox

from sandbox.sandbox import get_or_start_sandbox, delete_sandbox, create_sandbox
from utils.logger import logger
from utils.auth_utils import get_optional_user_id
from services.supabase import DBConnection
import uuid

# Initialize shared resources
router = APIRouter(tags=["sandbox"])
db = None

def initialize(_db: DBConnection):
    """Initialize the sandbox API with resources from the main API."""
    global db
    db = _db
    logger.debug("Initialized sandbox API with database connection")

class FileInfo(BaseModel):
    """Model for file information"""
    name: str
    path: str
    is_dir: bool
    size: int
    mod_time: str
    permissions: Optional[str] = None

def normalize_path(path: str) -> str:
    """
    Normalize a path to ensure proper UTF-8 encoding and handling.
    
    Args:
        path: The file path, potentially containing URL-encoded characters
        
    Returns:
        Normalized path with proper UTF-8 encoding
    """
    try:
        # First, ensure the path is properly URL-decoded
        decoded_path = urllib.parse.unquote(path)
        
        # Handle Unicode escape sequences like \u0308
        try:
            # Replace Python-style Unicode escapes (\u0308) with actual characters
            # This handles cases where the Unicode escape sequence is part of the URL
            import re
            unicode_pattern = re.compile(r'\\u([0-9a-fA-F]{4})')
            
            def replace_unicode(match):
                hex_val = match.group(1)
                return chr(int(hex_val, 16))
            
            decoded_path = unicode_pattern.sub(replace_unicode, decoded_path)
        except Exception as unicode_err:
            logger.warning(f"Error processing Unicode escapes in path '{path}': {str(unicode_err)}")
        
        logger.debug(f"Normalized path from '{path}' to '{decoded_path}'")
        return decoded_path
    except Exception as e:
        logger.error(f"Error normalizing path '{path}': {str(e)}")
        return path  # Return original path if decoding fails

async def verify_sandbox_access(client, sandbox_id: str, user_id: Optional[str] = None):
    """
    Verify that a user has access to a specific sandbox based on account membership.
    
    Args:
        client: The Supabase client
        sandbox_id: The sandbox ID to check access for
        user_id: The user ID to check permissions for. Can be None for public resource access.
        
    Returns:
        dict: Project data containing sandbox information
        
    Raises:
        HTTPException: If the user doesn't have access to the sandbox or sandbox doesn't exist
    """
    # Find the project that owns this sandbox
    project_result = await client.table('projects').select('*').filter('sandbox->>id', 'eq', sandbox_id).execute()
    
    if not project_result.data or len(project_result.data) == 0:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    
    project_data = project_result.data[0]

    if project_data.get('is_public'):
        return project_data
    
    # For private projects, we must have a user_id
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required for this resource")
    
    account_id = project_data.get('account_id')
    
    # Verify account membership
    if account_id:
        account_user_result = await client.schema('basejump').from_('account_user').select('account_role').eq('user_id', user_id).eq('account_id', account_id).execute()
        if account_user_result.data and len(account_user_result.data) > 0:
            return project_data
    
    raise HTTPException(status_code=403, detail="Not authorized to access this sandbox")

async def ensure_project_sandbox_if_needed(client, identifier: str) -> tuple[str, bool]:
    """
    Check if the identifier is actually a project_id without a sandbox.
    If so, create a sandbox for the project and return the sandbox_id.
    
    Args:
        client: The Supabase client
        identifier: Either a sandbox_id or project_id
    
    Returns:
        tuple: (actual_sandbox_id, was_created) - The sandbox ID to use and whether it was created
    """
    # First, check if this is a sandbox_id that exists
    sandbox_check = await client.table('projects').select('project_id, sandbox').filter('sandbox->>id', 'eq', identifier).execute()
    
    if sandbox_check.data and len(sandbox_check.data) > 0:
        # It's a valid sandbox_id, use it directly
        logger.debug(f"Identifier {identifier} is a valid sandbox_id")
        return (identifier, False)
    
    # Check if this is a project_id
    project_check = await client.table('projects').select('*').eq('project_id', identifier).execute()
    
    if project_check.data and len(project_check.data) > 0:
        project_data = project_check.data[0]
        sandbox_info = project_data.get('sandbox') or {}
        
        if sandbox_info.get('id'):
            # Project has a sandbox, return it
            logger.debug(f"Project {identifier} has existing sandbox {sandbox_info['id']}")
            return (sandbox_info['id'], False)
        else:
            # Project exists but has no sandbox - create one
            logger.info(f"Project {identifier} has no sandbox, creating one on-demand for file upload")
            
            try:
                # Create a new sandbox for this project
                sandbox_pass = str(uuid.uuid4())
                sandbox_obj = await create_sandbox(sandbox_pass, identifier)
                sandbox_id = sandbox_obj.id
                
                # Get preview links
                try:
                    vnc_link = await sandbox_obj.get_preview_link(6080)
                    website_link = await sandbox_obj.get_preview_link(8080)
                    vnc_url = vnc_link.url if hasattr(vnc_link, 'url') else str(vnc_link).split("url='")[1].split("'")[0]
                    website_url = website_link.url if hasattr(website_link, 'url') else str(website_link).split("url='")[1].split("'")[0]
                    token = vnc_link.token if hasattr(vnc_link, 'token') else (str(vnc_link).split("token='")[1].split("'")[0] if "token='" in str(vnc_link) else None)
                except Exception:
                    logger.warning(f"Failed to extract preview links for sandbox {sandbox_id}", exc_info=True)
                    vnc_url = None
                    website_url = None
                    token = None
                
                # Update project with sandbox info
                update_result = await client.table('projects').update({
                    'sandbox': {
                        'id': sandbox_id,
                        'pass': sandbox_pass,
                        'vnc_preview': vnc_url,
                        'sandbox_url': website_url,
                        'token': token
                    }
                }).eq('project_id', identifier).execute()
                
                if not update_result.data:
                    # Cleanup if update failed
                    try:
                        await delete_sandbox(sandbox_id)
                    except Exception:
                        logger.error(f"Failed to delete sandbox {sandbox_id} after DB update failure")
                    raise HTTPException(status_code=500, detail="Failed to update project with sandbox info")
                
                logger.info(f"Successfully created sandbox {sandbox_id} for project {identifier}")
                return (sandbox_id, True)
                
            except Exception as e:
                logger.error(f"Error creating sandbox for project {identifier}: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to create sandbox: {str(e)}")
    
    # Not a valid sandbox_id or project_id
    raise HTTPException(status_code=404, detail=f"No sandbox or project found with identifier: {identifier}")

async def get_sandbox_by_id_safely(client, sandbox_id: str) -> AsyncSandbox:
    """
    Safely retrieve a sandbox object by its ID, using the project that owns it.
    
    Args:
        client: The Supabase client
        sandbox_id: The sandbox ID to retrieve
    
    Returns:
        AsyncSandbox: The sandbox object
        
    Raises:
        HTTPException: If the sandbox doesn't exist or can't be retrieved
    """
    # Find the project that owns this sandbox
    project_result = await client.table('projects').select('project_id').filter('sandbox->>id', 'eq', sandbox_id).execute()
    
    if not project_result.data or len(project_result.data) == 0:
        logger.error(f"No project found for sandbox ID: {sandbox_id}")
        raise HTTPException(status_code=404, detail="Sandbox not found - no project owns this sandbox ID")
    
    # project_id = project_result.data[0]['project_id']
    # logger.debug(f"Found project {project_id} for sandbox {sandbox_id}")
    
    try:
        # Get the sandbox
        sandbox = await get_or_start_sandbox(sandbox_id)
        # Extract just the sandbox object from the tuple (sandbox, sandbox_id, sandbox_pass)
        # sandbox = sandbox_tuple[0]
            
        return sandbox
    except Exception as e:
        logger.error(f"Error retrieving sandbox {sandbox_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve sandbox: {str(e)}")

@router.post("/sandboxes/{sandbox_id}/files")
async def create_file(
    sandbox_id: str, 
    path: str = Form(...),
    file: UploadFile = File(...),
    request: Request = None,
    user_id: Optional[str] = Depends(get_optional_user_id)
):
    """Create a file in the sandbox using direct file upload"""
    # Normalize the path to handle UTF-8 encoding correctly
    path = normalize_path(path)
    
    logger.debug(f"Received file upload request for sandbox/project {sandbox_id}, path: {path}, user_id: {user_id}")
    client = await db.client
    
    # Check if this is actually a project_id and create sandbox if needed
    actual_sandbox_id, was_created = await ensure_project_sandbox_if_needed(client, sandbox_id)
    
    if was_created:
        logger.info(f"Created sandbox {actual_sandbox_id} on-demand for file upload")
    
    # Verify the user has access to this sandbox
    await verify_sandbox_access(client, actual_sandbox_id, user_id)
    
    try:
        # Get sandbox using the safer method with the actual sandbox_id
        sandbox = await get_sandbox_by_id_safely(client, actual_sandbox_id)
        
        # Read file content directly from the uploaded file
        content = await file.read()
        
        # Create file using raw binary content
        await sandbox.fs.upload_file(content, path)
        logger.debug(f"File created at {path} in sandbox {actual_sandbox_id}")
        
        return {"status": "success", "created": True, "path": path, "sandbox_id": actual_sandbox_id}
    except Exception as e:
        logger.error(f"Error creating file in sandbox {actual_sandbox_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sandboxes/{sandbox_id}/files")
async def list_files(
    sandbox_id: str, 
    path: str,
    request: Request = None,
    user_id: Optional[str] = Depends(get_optional_user_id)
):
    """List files and directories at the specified path"""
    # Normalize the path to handle UTF-8 encoding correctly
    path = normalize_path(path)
    
    logger.debug(f"Received list files request for sandbox/project {sandbox_id}, path: {path}, user_id: {user_id}")
    client = await db.client
    
    # Check if this is actually a project_id and get the actual sandbox_id
    actual_sandbox_id, _ = await ensure_project_sandbox_if_needed(client, sandbox_id)
    
    # Verify the user has access to this sandbox
    await verify_sandbox_access(client, actual_sandbox_id, user_id)
    
    try:
        # Get sandbox using the safer method with the actual sandbox_id
        sandbox = await get_sandbox_by_id_safely(client, actual_sandbox_id)
        
        # List files
        files = await sandbox.fs.list_files(path)
        result = []
        
        for file in files:
            # Convert file information to our model
            # Ensure forward slashes are used for paths, regardless of OS
            full_path = f"{path.rstrip('/')}/{file.name}" if path != '/' else f"/{file.name}"
            file_info = FileInfo(
                name=file.name,
                path=full_path, # Use the constructed path
                is_dir=file.is_dir,
                size=file.size,
                mod_time=str(file.mod_time),
                permissions=getattr(file, 'permissions', None)
            )
            result.append(file_info)
        
        logger.debug(f"Successfully listed {len(result)} files in sandbox {actual_sandbox_id}")
        return {"files": [file.dict() for file in result], "sandbox_id": actual_sandbox_id}
    except Exception as e:
        logger.error(f"Error listing files in sandbox {actual_sandbox_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sandboxes/{sandbox_id}/files/content")
async def read_file(
    sandbox_id: str, 
    path: str,
    request: Request = None,
    user_id: Optional[str] = Depends(get_optional_user_id)
):
    """Read a file from the sandbox"""
    # Normalize the path to handle UTF-8 encoding correctly
    original_path = path
    path = normalize_path(path)
    
    logger.debug(f"Received file read request for sandbox/project {sandbox_id}, path: {path}, user_id: {user_id}")
    if original_path != path:
        logger.debug(f"Normalized path from '{original_path}' to '{path}'")
    
    client = await db.client
    
    # Check if this is actually a project_id and get the actual sandbox_id
    logger.info(f"Checking if {sandbox_id} is a project_id that needs a sandbox...")
    actual_sandbox_id, was_created = await ensure_project_sandbox_if_needed(client, sandbox_id)
    if was_created:
        logger.info(f"Created sandbox {actual_sandbox_id} on-demand for file read")
    else:
        logger.debug(f"Using existing sandbox {actual_sandbox_id}")
    
    # Verify the user has access to this sandbox
    await verify_sandbox_access(client, actual_sandbox_id, user_id)
    
    try:
        # Get sandbox using the safer method with the actual sandbox_id
        sandbox = await get_sandbox_by_id_safely(client, actual_sandbox_id)
        
        # Read file directly - don't check existence first with a separate call
        try:
            content = await sandbox.fs.download_file(path)
        except Exception as download_err:
            logger.error(f"Error downloading file {path} from sandbox {actual_sandbox_id}: {str(download_err)}")
            raise HTTPException(
                status_code=404, 
                detail=f"Failed to download file: {str(download_err)}"
            )
        
        # Return a Response object with the content directly
        filename = os.path.basename(path)
        logger.debug(f"Successfully read file {filename} from sandbox {actual_sandbox_id}")
        
        # Ensure proper encoding by explicitly using UTF-8 for the filename in Content-Disposition header
        # This applies RFC 5987 encoding for the filename to support non-ASCII characters
        encoded_filename = filename.encode('utf-8').decode('latin-1')
        content_disposition = f"attachment; filename*=UTF-8''{encoded_filename}"
        
        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": content_disposition,
                "X-Sandbox-Id": actual_sandbox_id
            }
        )
    except HTTPException:
        # Re-raise HTTP exceptions without wrapping
        raise
    except Exception as e:
        logger.error(f"Error reading file in sandbox {actual_sandbox_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sandboxes/{sandbox_id}/files")
async def delete_file(
    sandbox_id: str, 
    path: str,
    request: Request = None,
    user_id: Optional[str] = Depends(get_optional_user_id)
):
    """Delete a file from the sandbox"""
    # Normalize the path to handle UTF-8 encoding correctly
    path = normalize_path(path)
    
    logger.debug(f"Received file delete request for sandbox/project {sandbox_id}, path: {path}, user_id: {user_id}")
    client = await db.client
    
    # Check if this is actually a project_id and get the actual sandbox_id
    actual_sandbox_id, _ = await ensure_project_sandbox_if_needed(client, sandbox_id)
    
    # Verify the user has access to this sandbox
    await verify_sandbox_access(client, actual_sandbox_id, user_id)
    
    try:
        # Get sandbox using the safer method with the actual sandbox_id
        sandbox = await get_sandbox_by_id_safely(client, actual_sandbox_id)
        
        # Delete file
        await sandbox.fs.delete_file(path)
        logger.debug(f"File deleted at {path} in sandbox {actual_sandbox_id}")
        
        return {"status": "success", "deleted": True, "path": path, "sandbox_id": actual_sandbox_id}
    except Exception as e:
        logger.error(f"Error deleting file in sandbox {actual_sandbox_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sandboxes/{sandbox_id}")
async def delete_sandbox_route(
    sandbox_id: str,
    request: Request = None,
    user_id: Optional[str] = Depends(get_optional_user_id)
):
    """Delete an entire sandbox"""
    logger.debug(f"Received sandbox delete request for sandbox {sandbox_id}, user_id: {user_id}")
    client = await db.client
    
    # Verify the user has access to this sandbox
    await verify_sandbox_access(client, sandbox_id, user_id)
    
    try:
        # Delete the sandbox using the sandbox module function
        await delete_sandbox(sandbox_id)
        
        return {"status": "success", "deleted": True, "sandbox_id": sandbox_id}
    except Exception as e:
        logger.error(f"Error deleting sandbox {sandbox_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Should happen on server-side fully
@router.post("/project/{project_id}/sandbox/ensure-active")
async def ensure_project_sandbox_active(
    project_id: str,
    request: Request = None,
    user_id: Optional[str] = Depends(get_optional_user_id)
):
    """
    Ensure that a project's sandbox is active and running.
    Checks the sandbox status and starts it if it's not running.
    """
    logger.debug(f"Received ensure sandbox active request for project {project_id}, user_id: {user_id}")
    client = await db.client
    
    # Find the project and sandbox information
    project_result = await client.table('projects').select('*').eq('project_id', project_id).execute()
    
    if not project_result.data or len(project_result.data) == 0:
        logger.error(f"Project not found: {project_id}")
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_data = project_result.data[0]
    
    # For public projects, no authentication is needed
    if not project_data.get('is_public'):
        # For private projects, we must have a user_id
        if not user_id:
            logger.error(f"Authentication required for private project {project_id}")
            raise HTTPException(status_code=401, detail="Authentication required for this resource")
            
        account_id = project_data.get('account_id')
        
        # Verify account membership
        if account_id:
            account_user_result = await client.schema('basejump').from_('account_user').select('account_role').eq('user_id', user_id).eq('account_id', account_id).execute()
            if not (account_user_result.data and len(account_user_result.data) > 0):
                logger.error(f"User {user_id} not authorized to access project {project_id}")
                raise HTTPException(status_code=403, detail="Not authorized to access this project")
    
    try:
        # Get sandbox ID from project data
        sandbox_info = project_data.get('sandbox', {})
        if not sandbox_info.get('id'):
            raise HTTPException(status_code=404, detail="No sandbox found for this project")
            
        sandbox_id = sandbox_info['id']
        
        # Get or start the sandbox
        logger.debug(f"Ensuring sandbox is active for project {project_id}")
        sandbox = await get_or_start_sandbox(sandbox_id)
        
        logger.debug(f"Successfully ensured sandbox {sandbox_id} is active for project {project_id}")
        
        return {
            "status": "success", 
            "sandbox_id": sandbox_id,
            "message": "Sandbox is active"
        }
    except Exception as e:
        logger.error(f"Error ensuring sandbox is active for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
