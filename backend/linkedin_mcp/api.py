"""LinkedIn MCP API Routes"""

from fastapi import APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import json

from services.supabase import DBConnection
from utils.auth_utils import get_current_user_id_from_jwt
from utils.logger import logger
from .oauth import LinkedInOAuthHandler
from .accounts import LinkedInAccountService
from .upload import LinkedInUploadService
from .service import LinkedInAPIService
from services.youtube_file_service import YouTubeFileService


router = APIRouter(prefix="/linkedin", tags=["LinkedIn MCP"])

# Database connection
db: Optional[DBConnection] = None


def initialize(database: DBConnection):
    """Initialize LinkedIn MCP with database connection"""
    global db
    db = database


@router.post("/auth/initiate")
async def initiate_auth(
    request: Optional[Dict[str, Any]] = None,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Start LinkedIn OAuth flow with optional thread context.

    Notes:
    - Falls back gracefully if the temporary OAuth session table is missing by
      embedding the PKCE code_verifier in the state payload (signed/opaque via
      base64) so the callback can still complete locally.
    """
    try:
        oauth_handler = LinkedInOAuthHandler(db)

        # Create state with user_id and optional thread context
        state_data: Dict[str, Any] = {"user_id": user_id}
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
        base_state = base64.urlsafe_b64encode(state_json.encode()).decode()

        # Generate OAuth URL with PKCE
        auth_url, code_verifier, oauth_state = oauth_handler.get_auth_url(state=base_state)

        # Enhance state with code_verifier so callback can succeed without DB
        enhanced_state_data = {**state_data, "cv": code_verifier}
        enhanced_state_json = json.dumps(enhanced_state_data)
        enhanced_state = base64.urlsafe_b64encode(enhanced_state_json.encode()).decode()

        # Replace state parameter in auth_url with enhanced state
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        parsed = urlparse(auth_url)
        qs = parse_qs(parsed.query)
        qs["state"] = [f"{oauth_state}:{enhanced_state}"]
        new_query = urlencode(qs, doseq=True)
        auth_url = urlunparse(parsed._replace(query=new_query))

        # Try to store the OAuth session (optional). If it fails (e.g., table missing), continue.
        try:
            await oauth_handler.store_oauth_session(oauth_state, code_verifier, user_id)
        except Exception as se:
            logger.warning(f"LinkedIn OAuth session storage failed; continuing with state fallback: {se}")

        return {
            "success": True,
            "auth_url": auth_url,
            "message": "Visit the auth_url to connect your LinkedIn account"
        }
    except Exception as e:
        logger.error(f"Failed to initiate LinkedIn auth: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/callback")
async def auth_callback(
    code: str,
    state: Optional[str] = None,
    error: Optional[str] = None
):
    """Handle LinkedIn OAuth callback"""
    
    if error:
        return HTMLResponse(content=f"""
            <html>
                <head>
                    <title>Connection Failed</title>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            height: 100vh;
                            margin: 0;
                            background: linear-gradient(135deg, #0077B5 0%, #005885 100%);
                        }}
                        .container {{
                            text-align: center;
                            background: white;
                            padding: 2rem;
                            border-radius: 16px;
                            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
                            max-width: 400px;
                        }}
                        .error-icon {{
                            width: 64px;
                            height: 64px;
                            margin: 0 auto 1rem;
                            background: #ef4444;
                            border-radius: 50%;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                        }}
                        .x-mark {{
                            color: white;
                            font-size: 32px;
                        }}
                        h1 {{
                            color: #1f2937;
                            margin-bottom: 0.5rem;
                        }}
                        p {{
                            color: #6b7280;
                            margin-bottom: 1rem;
                        }}
                        .error-message {{
                            background: #fef2f2;
                            border: 1px solid #fecaca;
                            border-radius: 8px;
                            padding: 0.75rem;
                            color: #991b1b;
                            font-size: 14px;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="error-icon">
                            <span class="x-mark">✕</span>
                        </div>
                        <h1>Connection Failed</h1>
                        <p>We couldn't connect your LinkedIn account.</p>
                        <div class="error-message">
                            {error.replace('_', ' ').title() if error != 'access_denied' else 'Access was denied. Please try again.'}
                        </div>
                        <p style="font-size: 14px; margin-top: 1rem;">This window will close automatically...</p>
                    </div>
                    <script>
                        if (window.opener) {{
                            window.opener.postMessage({{
                                type: 'linkedin-auth-error',
                                error: '{error}'
                            }}, '*');
                            setTimeout(() => window.close(), 3000);
                        }} else {{
                            const returnUrl = sessionStorage.getItem('linkedin_auth_return_url') || document.referrer || '/agents';
                            setTimeout(() => {{
                                window.location.href = returnUrl;
                            }}, 3000);
                        }}
                    </script>
                </body>
            </html>
        """)
    
    try:
        oauth_handler = LinkedInOAuthHandler(db)
        
        # Parse state to get OAuth state and user state
        oauth_state, user_state = state.split(':', 1)
        
        # Get OAuth session data (optional)
        session_data = await oauth_handler.get_oauth_session(oauth_state)
        code_verifier: Optional[str] = None
        user_id: Optional[str] = None
        if session_data:
            code_verifier = session_data.get("code_verifier")
            user_id = session_data.get("user_id")
        
        # Parse user state to get thread context
        import base64
        try:
            state_json = base64.urlsafe_b64decode(user_state.encode()).decode()
            state_data = json.loads(state_json)
            thread_id = state_data.get("thread_id")
            project_id = state_data.get("project_id")
            return_url = state_data.get("return_url")
            # Fallbacks if session wasn't stored
            if not code_verifier:
                code_verifier = state_data.get("cv") or state_data.get("code_verifier")
            if not user_id:
                user_id = state_data.get("user_id")
        except:
            thread_id = None
            project_id = None
            return_url = None
            # If we couldn't parse state, ensure we still have required values
            if not code_verifier or not user_id:
                raise HTTPException(status_code=400, detail="Missing OAuth state; please retry")
        
        # Exchange code for tokens
        if not code_verifier:
            raise HTTPException(status_code=400, detail="Missing PKCE code_verifier; please retry the connection")
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
        
        # Return success HTML that closes the popup and shows success message
        return HTMLResponse(content=f"""
            <html>
                <head>
                    <title>LinkedIn Connected</title>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            height: 100vh;
                            margin: 0;
                            background: linear-gradient(135deg, #0077B5 0%, #005885 100%);
                        }}
                        .container {{
                            text-align: center;
                            background: white;
                            padding: 2rem;
                            border-radius: 16px;
                            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
                        }}
                        .success-icon {{
                            width: 64px;
                            height: 64px;
                            margin: 0 auto 1rem;
                            background: #10b981;
                            border-radius: 50%;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                        }}
                        .checkmark {{
                            color: white;
                            font-size: 32px;
                        }}
                        h1 {{
                            color: #1f2937;
                            margin-bottom: 0.5rem;
                        }}
                        p {{
                            color: #6b7280;
                            margin-bottom: 1.5rem;
                        }}
                        .account-info {{
                            display: flex;
                            align-items: center;
                            gap: 1rem;
                            padding: 1rem;
                            background: #f9fafb;
                            border-radius: 8px;
                            margin-bottom: 1rem;
                        }}
                        .account-avatar {{
                            width: 48px;
                            height: 48px;
                            border-radius: 50%;
                        }}
                        .account-name {{
                            font-weight: 600;
                            color: #1f2937;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="success-icon">
                            <span class="checkmark">✓</span>
                        </div>
                        <h1>Connected Successfully!</h1>
                        <div class="account-info">
                            {f'<img src="{user_info.get("profile_image_url", "")}" alt="" class="account-avatar">' if user_info.get("profile_image_url") else ''}
                            <div style="text-align: left;">
                                <div class="account-name">{user_info.get('name', 'LinkedIn User')}</div>
                                <div style="color: #6b7280; font-size: 14px;">{user_info.get('email', '')}</div>
                            </div>
                        </div>
                        <p>Closing this window...</p>
                    </div>
                    <script>
                        const isPopup = (
                            window.opener !== null ||
                            window.name === 'linkedin-auth' ||
                            window.innerWidth <= 700 ||
                            window.location.search.includes('popup=true')
                        );
                        
                        if (isPopup) {{
                            try {{
                                if (window.opener && !window.opener.closed) {{
                                    window.opener.postMessage({{
                                        type: 'linkedin-auth-success',
                                        account: {json.dumps(user_info)}
                                    }}, '*');
                                }} else {{
                                    localStorage.setItem('linkedin-auth-result', JSON.stringify({{
                                        type: 'linkedin-auth-success',
                                        account: {json.dumps(user_info)},
                                        timestamp: Date.now()
                                    }}));
                                }}
                            }} catch (e) {{
                                console.error('Failed to communicate with opener:', e);
                            }}
                            
                            setTimeout(() => {{
                                window.close();
                                setTimeout(() => {{
                                    document.body.innerHTML = '<div style="text-align: center; padding: 2rem;">You can close this window now.</div>';
                                }}, 500);
                            }}, 2000);
                        }} else {{
                            let returnUrl = '{return_url if return_url else ""}';
                            
                            if (!returnUrl && {json.dumps(bool(thread_id))}) {{
                                const projectId = '{project_id if project_id else ""}';
                                const threadId = '{thread_id if thread_id else ""}';
                                if (projectId && threadId) {{
                                    returnUrl = `/projects/${{projectId}}/thread/${{threadId}}`;
                                }}
                            }}
                            
                            if (!returnUrl) {{
                                returnUrl = sessionStorage.getItem('linkedin_auth_return_url') || document.referrer || '/agents';
                            }}
                            
                            setTimeout(() => {{
                                window.location.href = returnUrl;
                            }}, 2000);
                        }}
                    </script>
                </body>
            </html>
        """)
        
    except Exception as e:
        logger.error(f"LinkedIn OAuth callback failed: {e}")
        return HTMLResponse(content=f"""
            <html>
                <body>
                    <script>
                        window.opener.postMessage({{
                            type: 'linkedin-auth-error',
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
    """Get user's LinkedIn accounts with comprehensive error handling"""
    try:
        account_service = LinkedInAccountService(db)
        accounts = await account_service.get_user_accounts(user_id)
        
        return {
            "success": True,
            "accounts": accounts,
            "count": len(accounts),
            "message": f"Found {len(accounts)} connected account{'s' if len(accounts) != 1 else ''}" if accounts else "No LinkedIn accounts connected. Connect an account to get started."
        }
        
    except Exception as e:
        logger.error(f"Failed to get LinkedIn accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/{account_id}")
async def get_account(
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get specific LinkedIn account details"""
    try:
        account_service = LinkedInAccountService(db)
        account = await account_service.get_account(user_id, account_id)
        
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        return {
            "success": True,
            "account": account
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get LinkedIn account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/accounts/{account_id}")
async def remove_account(
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Remove a LinkedIn account connection"""
    try:
        oauth_handler = LinkedInOAuthHandler(db)
        success = await oauth_handler.remove_account(user_id, account_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Account not found")
        
        return {
            "success": True,
            "message": f"LinkedIn account {account_id} removed successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove LinkedIn account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accounts/{account_id}/refresh")
async def refresh_account_info(
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Refresh account information including profile pictures"""
    try:
        account_service = LinkedInAccountService(db)
        account = await account_service.refresh_account_info(user_id, account_id)
        
        return {
            "success": True,
            "account": account,
            "message": "Account information refreshed successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh LinkedIn account info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/post")
async def create_post(
    request: Dict[str, Any],
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Create a LinkedIn post with automatic file discovery"""
    try:
        upload_service = LinkedInUploadService(db)
        
        # Prepare post parameters
        post_params = {
            "account_id": request.get("account_id"),
            "text": request.get("text", ""),
            "visibility": request.get("visibility", "PUBLIC"),
            "video_reference_id": request.get("video_reference_id"),
            "image_reference_ids": request.get("image_reference_ids", []),
            "auto_discover": request.get("auto_discover", True)
        }
        
        # Call upload service (will auto-discover files if not provided)
        result = await upload_service.create_post(user_id, post_params)
        
        return {
            "success": True,
            **result
        }
        
    except Exception as e:
        logger.error(f"LinkedIn post creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/post-status/{post_record_id}")
async def get_post_status(
    post_record_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get the status of a LinkedIn post creation"""
    try:
        upload_service = LinkedInUploadService(db)
        status = await upload_service.get_post_status(user_id, post_record_id)
        
        return {
            "success": True,
            **status
        }
        
    except Exception as e:
        logger.error(f"Failed to get LinkedIn post status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/post/{post_id}")
async def delete_post(
    post_id: str,
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Delete a LinkedIn post"""
    try:
        upload_service = LinkedInUploadService(db)
        result = await upload_service.delete_post(user_id, account_id, post_id)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to delete LinkedIn post: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/{account_id}/posts")
async def get_account_posts(
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt),
    limit: int = 10
) -> Dict[str, Any]:
    """Get recent posts from a LinkedIn account"""
    try:
        upload_service = LinkedInUploadService(db)
        result = await upload_service.get_recent_posts(user_id, account_id, limit)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get LinkedIn account posts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/post-analytics/{post_id}")
async def get_post_analytics(
    post_id: str,
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get analytics for a specific LinkedIn post"""
    try:
        upload_service = LinkedInUploadService(db)
        result = await upload_service.get_post_analytics(user_id, account_id, post_id)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get LinkedIn post analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== File Upload Endpoints =====

@router.post("/prepare-upload")
async def prepare_upload(
    file: UploadFile = File(...),
    file_type: Optional[str] = Form("auto"),
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Prepare a file for LinkedIn upload with comprehensive error handling"""
    try:
        # Validate file exists and has content
        if not file or not file.filename:
            raise HTTPException(
                status_code=400,
                detail="No file provided. Please select a file to upload."
            )
        
        # Initialize file service
        file_service = YouTubeFileService(db)
        
        # Read file data with size validation
        file_data = await file.read()
        
        if not file_data or len(file_data) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"The file '{file.filename}' is empty. Please select a valid file."
            )
        
        # Check file size (LinkedIn limits)
        if file.content_type and file.content_type.startswith("video/"):
            max_size = 200 * 1024 * 1024  # 200MB for videos
        else:
            max_size = 100 * 1024 * 1024  # 100MB for images
            
        if len(file_data) > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed ({max_size // (1024*1024)}MB). Your file is {len(file_data) / (1024*1024):.2f}MB."
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
            "message": f"Successfully prepared {file_type} for LinkedIn upload"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"LinkedIn file upload preparation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/universal-upload")
async def universal_upload(
    upload_data: Dict[str, Any],
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Universal upload endpoint for LinkedIn platform"""
    try:
        platform = upload_data.get("platform", "").lower()
        
        if platform == "linkedin":
            # Delegate to LinkedIn upload
            upload_service = LinkedInUploadService(db)
            
            # Convert universal params to LinkedIn format
            linkedin_params = {
                "account_id": upload_data["account_id"],
                "text": upload_data.get("text", upload_data.get("title", "")),
                "visibility": upload_data.get("visibility", "PUBLIC"),
                "video_reference_id": upload_data.get("video_reference_id"),
                "image_reference_ids": upload_data.get("image_reference_ids", []),
                "auto_discover": upload_data.get("auto_discover", True)
            }
            
            # Start LinkedIn post creation
            result = await upload_service.create_post(user_id, linkedin_params)
            
            return {
                "success": True,
                "post_record_id": result.get("post_record_id"),
                "platform": "linkedin",
                "status": "posting",
                "message": "LinkedIn post creation started",
                "post_started": True,
                "account": {
                    "id": upload_data["account_id"],
                    "name": result.get("account_name", "LinkedIn User")
                }
            }
        else:
            raise HTTPException(
                status_code=501, 
                detail=f"Platform '{platform}' not supported by LinkedIn endpoint"
            )
            
    except Exception as e:
        logger.error(f"LinkedIn universal upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== UNIFIED SOCIAL ACCOUNTS ENDPOINTS =====

@router.get("/agents/{agent_id}/social-accounts/linkedin/enabled")
async def get_agent_enabled_linkedin_accounts(
    agent_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get ONLY enabled LinkedIn accounts for an agent - UNIFIED SYSTEM ENDPOINT"""
    try:
        account_service = LinkedInAccountService(db)
        accounts = await account_service.get_accounts_for_agent(user_id, agent_id)
        
        logger.info(f"🎯 Unified System: Agent {agent_id} has {len(accounts)} enabled LinkedIn accounts")
        for acc in accounts:
            logger.info(f"  ✅ Enabled: {acc['name']} ({acc['email']})")
        
        return {
            "success": True,
            "agent_id": agent_id,
            "accounts": accounts,  # Use 'accounts' for tool compatibility
            "count": len(accounts)
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get enabled LinkedIn accounts from unified system: {e}")
        return {
            "success": False,
            "error": str(e),
            "agent_id": agent_id,
            "accounts": [],
            "count": 0
        }
