"""Pinterest MCP API Routes"""

from fastapi import APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import json

from services.supabase import DBConnection
from utils.auth_utils import get_current_user_id_from_jwt
from utils.logger import logger
from .oauth import PinterestOAuthHandler
from .accounts import PinterestAccountService
from .upload import PinterestUploadService
from .service import PinterestAPIService
from services.youtube_file_service import YouTubeFileService


router = APIRouter(prefix="/pinterest", tags=["Pinterest MCP"])

# Database connection
db: Optional[DBConnection] = None


def initialize(database: DBConnection):
    """Initialize Pinterest MCP with database connection"""
    global db
    db = database


@router.post("/auth/initiate")
async def initiate_auth(
    request: Optional[Dict[str, Any]] = None,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Start Pinterest OAuth flow with optional thread context"""
    try:
        oauth_handler = PinterestOAuthHandler(db)
        
        # Create state with user_id and optional thread context
        state_data = {
            "user_id": user_id
        }
        
        # Add thread context if provided
        if request:
            if "thread_id" in request:
                state_data["thread_id"] = request["thread_id"]
            if "project_id" in request:
                state_data["project_id"] = request["project_id"]
            if "return_url" in request:
                state_data["return_url"] = request["return_url"]
        
        # Encode state as JSON
        import base64
        state_json = json.dumps(state_data)
        state = base64.urlsafe_b64encode(state_json.encode()).decode()
        
        # Generate OAuth URL (following YouTube pattern exactly)
        auth_url = oauth_handler.get_auth_url(state=state)
        
        return {
            "success": True,
            "auth_url": auth_url,
            "message": "Visit the auth_url to connect your Pinterest account"
        }
    except Exception as e:
        logger.error(f"Failed to initiate Pinterest auth: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/callback")
async def auth_callback(
    code: str,
    state: Optional[str] = None,
    error: Optional[str] = None
):
    """Handle Pinterest OAuth callback"""
    
    if error:
        return HTMLResponse(content=f"""
            <html>
                <head><title>Connection Failed</title></head>
                <body>
                    <div style="text-align: center; padding: 2rem;">
                        <h1>Connection Failed</h1>
                        <p>We couldn't connect your Pinterest account.</p>
                        <p>{error.replace('_', ' ').title() if error != 'access_denied' else 'Access was denied. Please try again.'}</p>
                    </div>
                    <script>
                        if (window.opener) {{
                            window.opener.postMessage({{
                                type: 'pinterest-auth-error',
                                error: '{error}'
                            }}, '*');
                            setTimeout(() => window.close(), 3000);
                        }}
                    </script>
                </body>
            </html>
        """)
    
    try:
        oauth_handler = PinterestOAuthHandler(db)
        
        # Parse state to get OAuth state and user state
        oauth_state, user_state = state.split(':', 1)
        
        # Get OAuth session data
        session_data = await oauth_handler.get_oauth_session(oauth_state)
        if not session_data:
            raise Exception("Invalid or expired OAuth session")
        
        code_verifier = session_data["code_verifier"]
        user_id = session_data["user_id"]
        
        # Exchange code for tokens
        access_token, refresh_token, expires_at = await oauth_handler.exchange_code_for_tokens(code, code_verifier)
        
        # Get user info
        user_info = await oauth_handler.get_user_info(access_token)
        
        # Save account to database
        account_id = await oauth_handler.save_account(
            user_id=user_id,
            user_info=user_info,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at
        )
        
        # Cleanup OAuth session
        await oauth_handler.cleanup_oauth_session(oauth_state)
        
        # Return success HTML
        return HTMLResponse(content=f"""
            <html>
                <head><title>Pinterest Connected</title></head>
                <body>
                    <div style="text-align: center; padding: 2rem;">
                        <h1>Connected Successfully!</h1>
                        <p>Pinterest account: {user_info.get('name', 'Pinterest User')} (@{user_info.get('username', '')})</p>
                        <p>Closing this window...</p>
                    </div>
                    <script>
                        if (window.opener && !window.opener.closed) {{
                            window.opener.postMessage({{
                                type: 'pinterest-auth-success',
                                account: {json.dumps(user_info)}
                            }}, '*');
                        }}
                        setTimeout(() => window.close(), 2000);
                    </script>
                </body>
            </html>
        """)
        
    except Exception as e:
        logger.error(f"Pinterest OAuth callback failed: {e}")
        return HTMLResponse(content=f"""
            <html>
                <body>
                    <script>
                        window.opener.postMessage({{
                            type: 'pinterest-auth-error',
                            error: '{str(e)}'
                        }}, '*');
                        window.close();
                    </script>
                </body>
            </html>
        """)


@router.get("/accounts")
async def get_accounts(
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get user's Pinterest accounts"""
    try:
        account_service = PinterestAccountService(db)
        accounts = await account_service.get_user_accounts(user_id)
        
        return {
            "success": True,
            "accounts": accounts,
            "count": len(accounts),
            "message": f"Found {len(accounts)} connected account{'s' if len(accounts) != 1 else ''}" if accounts else "No Pinterest accounts connected. Connect an account to get started."
        }
        
    except Exception as e:
        logger.error(f"Failed to get Pinterest accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pin")
async def create_pin(
    request: Dict[str, Any],
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Create a Pinterest pin with automatic file discovery"""
    try:
        upload_service = PinterestUploadService(db)
        
        # Prepare pin parameters
        pin_params = {
            "account_id": request.get("account_id"),
            "title": request.get("title", ""),
            "description": request.get("description", ""),
            "board_id": request.get("board_id"),
            "link": request.get("link"),
            "video_reference_id": request.get("video_reference_id"),
            "image_reference_ids": request.get("image_reference_ids", []),
            "auto_discover": request.get("auto_discover", True)
        }
        
        # Call upload service (will auto-discover files if not provided)
        result = await upload_service.create_pin(user_id, pin_params)
        
        return {
            "success": True,
            **result
        }
        
    except Exception as e:
        logger.error(f"Pinterest pin creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pin-status/{pin_record_id}")
async def get_pin_status(
    pin_record_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get the status of a Pinterest pin creation"""
    try:
        upload_service = PinterestUploadService(db)
        status = await upload_service.get_pin_status(user_id, pin_record_id)
        
        return {
            "success": True,
            **status
        }
        
    except Exception as e:
        logger.error(f"Failed to get Pinterest pin status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/{account_id}/boards")
async def get_account_boards(
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get boards from a Pinterest account"""
    try:
        upload_service = PinterestUploadService(db)
        result = await upload_service.get_account_boards(user_id, account_id)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Pinterest account boards: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prepare-upload")
async def prepare_upload(
    file: UploadFile = File(...),
    file_type: Optional[str] = Form("auto"),
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Prepare a file for Pinterest upload"""
    try:
        if not file or not file.filename:
            raise HTTPException(
                status_code=400,
                detail="No file provided. Please select a file to upload."
            )
        
        file_service = YouTubeFileService(db)
        file_data = await file.read()
        
        if not file_data or len(file_data) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"The file '{file.filename}' is empty. Please select a valid file."
            )
        
        # Detect file type
        if file_type == "auto":
            detected_type = file_service.detect_file_type(file.content_type, file.filename)
            if detected_type == "unknown":
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not determine if '{file.filename}' is a video or image. Supported formats: MP4, MOV, JPEG, PNG."
                )
            file_type = detected_type
        
        # Create reference
        if file_type == "video":
            result = await file_service.create_video_reference(
                user_id=user_id,
                file_name=file.filename,
                file_data=file_data,
                mime_type=file.content_type
            )
        else:
            result = await file_service.create_thumbnail_reference(
                user_id=user_id,
                file_name=file.filename,
                file_data=file_data,
                mime_type=file.content_type
            )
        
        return {
            "success": True,
            "reference_id": result["reference_id"],
            "file_name": result["file_name"],
            "file_size": result["file_size"],
            "file_type": file_type,
            "expires_at": result["expires_at"],
            "message": f"Successfully prepared {file_type} for Pinterest upload"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pinterest file upload preparation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== UNIFIED SOCIAL ACCOUNTS ENDPOINTS =====

@router.get("/agents/{agent_id}/social-accounts/pinterest/enabled")
async def get_agent_enabled_pinterest_accounts(
    agent_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get ONLY enabled Pinterest accounts for an agent - UNIFIED SYSTEM ENDPOINT"""
    try:
        account_service = PinterestAccountService(db)
        accounts = await account_service.get_accounts_for_agent(user_id, agent_id)
        
        logger.info(f"🎯 Unified System: Agent {agent_id} has {len(accounts)} enabled Pinterest accounts")
        for acc in accounts:
            logger.info(f"  ✅ Enabled: {acc['name']} (@{acc['username']})")
        
        return {
            "success": True,
            "agent_id": agent_id,
            "accounts": accounts,  # Use 'accounts' for tool compatibility
            "count": len(accounts)
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get enabled Pinterest accounts from unified system: {e}")
        return {
            "success": False,
            "error": str(e),
            "agent_id": agent_id,
            "accounts": [],
            "count": 0
        }