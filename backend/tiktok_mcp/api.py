"""TikTok MCP API Routes"""

from fastapi import APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import json

from services.supabase import DBConnection
from utils.auth_utils import get_current_user_id_from_jwt
from utils.logger import logger
from .oauth import TikTokOAuthHandler
from .accounts import TikTokAccountService
from .upload import TikTokUploadService
from .service import TikTokAPIService
from services.youtube_file_service import YouTubeFileService


router = APIRouter(prefix="/tiktok", tags=["TikTok MCP"])

# Database connection
db: Optional[DBConnection] = None


def initialize(database: DBConnection):
    """Initialize TikTok MCP with database connection"""
    global db
    db = database


@router.post("/auth/initiate")
async def initiate_auth(
    request: Optional[Dict[str, Any]] = None,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Start TikTok OAuth flow with optional thread context"""
    try:
        oauth_handler = TikTokOAuthHandler(db)
        
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
        
        # Encode state
        state = json.dumps(state_data)
        
        # Get OAuth URL with PKCE
        auth_url, code_verifier, oauth_state = oauth_handler.get_auth_url(state)
        
        # Store OAuth session
        await oauth_handler.store_oauth_session(oauth_state, code_verifier, user_id)
        
        return {
            "auth_url": auth_url,
            "state": oauth_state,
            "message": "Click the URL to authorize TikTok access"
        }
        
    except Exception as e:
        logger.error(f"TikTok auth initiation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate TikTok OAuth: {str(e)}")


@router.get("/auth/callback")
async def oauth_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None
) -> HTMLResponse:
    """Handle TikTok OAuth callback"""
    try:
        if error:
            logger.error(f"TikTok OAuth error: {error} - {error_description}")
            return HTMLResponse(
                content=f"""
                <html><body>
                <h1>TikTok Authorization Failed</h1>
                <p>Error: {error}</p>
                <p>Description: {error_description or 'No description provided'}</p>
                <script>window.close();</script>
                </body></html>
                """,
                status_code=400
            )
        
        if not code or not state:
            raise HTTPException(status_code=400, detail="Missing code or state parameter")
        
        # Parse state to get OAuth state and user state
        try:
            oauth_state, user_state = state.split(':', 1)
        except ValueError:
            oauth_state = state
            user_state = "{}"
        
        oauth_handler = TikTokOAuthHandler(db)
        
        # Get OAuth session
        session_data = await oauth_handler.get_oauth_session(oauth_state)
        if not session_data:
            raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
        
        user_id = session_data['user_id']
        code_verifier = session_data['code_verifier']
        
        # Exchange code for tokens
        access_token, refresh_token, expires_at = await oauth_handler.exchange_code_for_tokens(code, code_verifier)
        
        # Get user info
        user_info = await oauth_handler.get_user_info(access_token)
        
        # Save account
        account_id = await oauth_handler.save_account(user_id, user_info, access_token, refresh_token, expires_at)
        
        # Create social media account connection for agents
        account_service = TikTokAccountService(db)
        await account_service.create_agent_connections(user_id, account_id)
        
        # Cleanup OAuth session
        await oauth_handler.cleanup_oauth_session(oauth_state)
        
        # Parse user state for any additional context
        try:
            user_context = json.loads(user_state)
            thread_id = user_context.get("thread_id")
            project_id = user_context.get("project_id")
        except:
            thread_id = None
            project_id = None
        
        # Success page
        account_name = user_info.get('name', 'Unknown')
        return HTMLResponse(
            content=f"""
            <html><body style="font-family: Arial, sans-serif; padding: 20px;">
            <h1 style="color: #fe2c55;">✅ TikTok Connected Successfully!</h1>
            <p>Account: <strong>{account_name}</strong></p>
            <p>You can now close this window and return to your chat.</p>
            <script>
            setTimeout(function() {{
                window.close();
            }}, 3000);
            </script>
            </body></html>
            """
        )
        
    except Exception as e:
        logger.error(f"TikTok OAuth callback failed: {e}")
        return HTMLResponse(
            content=f"""
            <html><body style="font-family: Arial, sans-serif; padding: 20px;">
            <h1 style="color: #fe2c55;">❌ TikTok Authorization Failed</h1>
            <p>Error: {str(e)}</p>
            <p>Please try connecting again.</p>
            <script>
            setTimeout(function() {{
                window.close();
            }}, 5000);
            </script>
            </body></html>
            """,
            status_code=500
        )


@router.get("/accounts")
async def get_accounts(
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get user's connected TikTok accounts"""
    try:
        account_service = TikTokAccountService(db)
        accounts = await account_service.get_user_accounts(user_id)
        
        return {
            "accounts": accounts,
            "count": len(accounts)
        }
        
    except Exception as e:
        logger.error(f"Failed to get TikTok accounts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get accounts: {str(e)}")


@router.get("/accounts/{account_id}")
async def get_account(
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get specific TikTok account details"""
    try:
        account_service = TikTokAccountService(db)
        account = await account_service.get_account(user_id, account_id)
        
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        return {"account": account}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get TikTok account: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get account: {str(e)}")


@router.delete("/accounts/{account_id}")
async def remove_account(
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Remove TikTok account connection"""
    try:
        oauth_handler = TikTokOAuthHandler(db)
        success = await oauth_handler.remove_account(user_id, account_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Account not found or already removed")
        
        return {"message": "Account removed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove TikTok account: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove account: {str(e)}")


@router.post("/prepare-upload")
async def prepare_upload(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Prepare video file for TikTok upload using reference system"""
    try:
        # Check file type
        if not file.content_type or not file.content_type.startswith('video/'):
            raise HTTPException(status_code=400, detail="Only video files are supported")
        
        # Read file data
        file_data = await file.read()
        
        # Use YouTube file service for reference system
        file_service = YouTubeFileService(db)
        
        # Create reference for the video
        reference_id = await file_service.create_video_reference(
            user_id=user_id,
            file_data=file_data,
            file_name=file.filename or "tiktok_video.mp4",
            mime_type=file.content_type
        )
        
        return {
            "reference_id": reference_id,
            "file_name": file.filename,
            "file_size": len(file_data),
            "file_type": "video",
            "message": "File prepared for TikTok upload"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TikTok file preparation failed: {e}")
        raise HTTPException(status_code=500, detail=f"File preparation failed: {str(e)}")


@router.get("/pending-uploads")
async def get_pending_uploads(
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get user's pending upload files for auto-discovery"""
    try:
        file_service = YouTubeFileService(db)
        uploads = await file_service.get_latest_pending_uploads(user_id)
        
        return {
            "uploads": uploads,
            "message": "Retrieved pending uploads"
        }
        
    except Exception as e:
        logger.error(f"Failed to get pending TikTok uploads: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get uploads: {str(e)}")


@router.post("/upload")
async def upload_video(
    title: str = Form(...),
    description: str = Form(""),
    account_id: str = Form(...),
    reference_id: Optional[str] = Form(None),
    privacy_level: str = Form("SELF_ONLY"),  # SELF_ONLY, MUTUAL_FOLLOW_FRIENDS, PUBLIC_TO_EVERYONE
    disable_duet: bool = Form(False),
    disable_comment: bool = Form(False),
    disable_stitch: bool = Form(False),
    brand_content_toggle: bool = Form(False),
    brand_organic_toggle: bool = Form(False),
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Upload video to TikTok"""
    try:
        # Auto-discover file if reference_id not provided
        if not reference_id:
            file_service = YouTubeFileService(db)
            uploads = await file_service.get_latest_pending_uploads(user_id)
            
            if not uploads.get("video"):
                raise HTTPException(status_code=400, detail="No video file found. Please upload a video first.")
            
            reference_id = uploads["video"]["reference_id"]
        
        # Start upload process
        upload_service = TikTokUploadService(db)
        upload_result = await upload_service.upload_video(
            user_id=user_id,
            account_id=account_id,
            reference_id=reference_id,
            title=title,
            description=description,
            privacy_level=privacy_level,
            disable_duet=disable_duet,
            disable_comment=disable_comment,
            disable_stitch=disable_stitch,
            brand_content_toggle=brand_content_toggle,
            brand_organic_toggle=brand_organic_toggle
        )
        
        return upload_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TikTok video upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/upload-status/{upload_id}")
async def get_upload_status(
    upload_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get TikTok upload progress status"""
    try:
        upload_service = TikTokUploadService(db)
        status = await upload_service.get_upload_status(user_id, upload_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Upload not found")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get TikTok upload status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.post("/universal-upload")
async def universal_upload(
    text: str = Form(""),
    account_id: str = Form(...),
    reference_id: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    privacy_level: str = Form("SELF_ONLY"),
    disable_duet: bool = Form(False),
    disable_comment: bool = Form(False),
    disable_stitch: bool = Form(False),
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Universal upload endpoint for social media integration"""
    try:
        # Use title or text as the video title
        video_title = title or text[:100] or "TikTok Video"
        video_description = description or text or ""
        
        # Auto-discover file if reference_id not provided
        if not reference_id:
            file_service = YouTubeFileService(db)
            uploads = await file_service.get_latest_pending_uploads(user_id)
            
            if not uploads.get("video"):
                raise HTTPException(status_code=400, detail="No video file found. Please upload a video first.")
            
            reference_id = uploads["video"]["reference_id"]
        
        # Start upload process
        upload_service = TikTokUploadService(db)
        upload_result = await upload_service.upload_video(
            user_id=user_id,
            account_id=account_id,
            reference_id=reference_id,
            title=video_title,
            description=video_description,
            privacy_level=privacy_level,
            disable_duet=disable_duet,
            disable_comment=disable_comment,
            disable_stitch=disable_stitch
        )
        
        return {
            **upload_result,
            "platform": "tiktok",
            "message": f"TikTok video upload started: {video_title}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TikTok universal upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")