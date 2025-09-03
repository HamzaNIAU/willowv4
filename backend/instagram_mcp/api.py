"""Instagram MCP API Routes"""

from fastapi import APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import json

from services.supabase import DBConnection
from utils.auth_utils import get_current_user_id_from_jwt
from utils.logger import logger
from .oauth import InstagramOAuthHandler
from .accounts import InstagramAccountService
from .upload import InstagramUploadService
from .service import InstagramAPIService
from services.youtube_file_service import YouTubeFileService


router = APIRouter(prefix="/instagram", tags=["Instagram MCP"])

# Database connection
db: Optional[DBConnection] = None


def initialize(database: DBConnection):
    """Initialize Instagram MCP with database connection"""
    global db
    db = database


@router.post("/auth/initiate")
async def initiate_auth(
    request: Optional[Dict[str, Any]] = None,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Start Instagram OAuth flow with optional thread context"""
    try:
        oauth_handler = InstagramOAuthHandler(db)
        
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
        
        # Generate OAuth URL
        auth_url, code_verifier, oauth_state = oauth_handler.get_auth_url(state=state)
        
        # Store OAuth session
        await oauth_handler.store_oauth_session(oauth_state, code_verifier, user_id)
        
        return {
            "success": True,
            "auth_url": auth_url,
            "message": "Visit the auth_url to connect your Instagram account"
        }
    except Exception as e:
        logger.error(f"Failed to initiate Instagram auth: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/callback")
async def auth_callback(
    code: str,
    state: Optional[str] = None,
    error: Optional[str] = None
):
    """Handle Instagram OAuth callback"""
    
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
                            background: linear-gradient(135deg, #E4405F 0%, #833AB4 50%, #F77737 100%);
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
                        <p>We couldn't connect your Instagram account.</p>
                        <div class="error-message">
                            {error.replace('_', ' ').title() if error != 'access_denied' else 'Access was denied. Please try again.'}
                        </div>
                        <p style="font-size: 14px; margin-top: 1rem;">This window will close automatically...</p>
                    </div>
                    <script>
                        if (window.opener) {{
                            window.opener.postMessage({{
                                type: 'instagram-auth-error',
                                error: '{error}'
                            }}, '*');
                            setTimeout(() => window.close(), 3000);
                        }} else {{
                            const returnUrl = sessionStorage.getItem('instagram_auth_return_url') || document.referrer || '/agents';
                            setTimeout(() => {{
                                window.location.href = returnUrl;
                            }}, 3000);
                        }}
                    </script>
                </body>
            </html>
        """)
    
    try:
        oauth_handler = InstagramOAuthHandler(db)
        
        # Get OAuth session data
        session_data = await oauth_handler.get_oauth_session(state)
        if not session_data:
            raise Exception("Invalid or expired OAuth session")
        
        code_verifier = session_data["code_verifier"]
        user_id = session_data["user_id"]
        
        # Parse state to get thread context
        import base64
        try:
            state_json = base64.urlsafe_b64decode(state.encode()).decode()
            state_data = json.loads(state_json)
            thread_id = state_data.get("thread_id")
            project_id = state_data.get("project_id")
            return_url = state_data.get("return_url")
        except:
            thread_id = None
            project_id = None
            return_url = None
        
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
        await oauth_handler.cleanup_oauth_session(state)
        
        # Return success HTML that closes the popup and shows success message
        return HTMLResponse(content=f"""
            <html>
                <head>
                    <title>Instagram Connected</title>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            height: 100vh;
                            margin: 0;
                            background: linear-gradient(135deg, #E4405F 0%, #833AB4 50%, #F77737 100%);
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
                            margin-bottom: 1rem;
                        }}
                        .account-info {{
                            background: #f9fafb;
                            border: 1px solid #e5e7eb;
                            border-radius: 8px;
                            padding: 1rem;
                            margin: 1rem 0;
                        }}
                        .profile-row {{
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            gap: 0.75rem;
                        }}
                        .profile-pic {{
                            width: 40px;
                            height: 40px;
                            border-radius: 50%;
                            border: 2px solid #e5e7eb;
                        }}
                        .profile-text {{
                            text-align: left;
                        }}
                        .username {{
                            font-weight: 600;
                            color: #1f2937;
                            margin: 0;
                        }}
                        .handle {{
                            font-size: 14px;
                            color: #6b7280;
                            margin: 0;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="success-icon">
                            <span class="checkmark">✓</span>
                        </div>
                        <h1>Instagram Connected!</h1>
                        <p>Your account has been successfully connected.</p>
                        <div class="account-info">
                            <div class="profile-row">
                                <img src="{user_info.get('profile_picture_url', '')}" alt="Profile" class="profile-pic" onerror="this.style.display='none'">
                                <div class="profile-text">
                                    <p class="username">{user_info.get('name', user_info.get('username', 'User'))}</p>
                                    <p class="handle">@{user_info.get('username', 'unknown')}</p>
                                </div>
                            </div>
                        </div>
                        <p style="font-size: 14px;">This window will close automatically...</p>
                    </div>
                    <script>
                        console.log('Instagram OAuth success callback initiated');
                        
                        // Attempt to communicate with opener window (popup scenario)
                        if (window.opener && !window.opener.closed) {{
                            try {{
                                console.log('Sending success message to opener window');
                                window.opener.postMessage({{
                                    type: 'instagram-auth-success',
                                    account: {json.dumps(user_info)}
                                }}, '*');
                            }} catch (e) {{
                                console.error('Failed to communicate with opener:', e);
                                // Fallback: Set localStorage for parent to check
                                try {{
                                    localStorage.setItem('instagram-auth-result', JSON.stringify({{
                                        type: 'instagram-auth-success',
                                        account: {json.dumps(user_info)},
                                        timestamp: Date.now()
                                    }}));
                                }} catch (e) {{
                                    console.error('Failed to set localStorage:', e);
                                }}
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
                                returnUrl = sessionStorage.getItem('instagram_auth_return_url') || document.referrer || '/agents';
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
        logger.error(f"Instagram OAuth callback failed: {e}")
        return HTMLResponse(content=f"""
            <html>
                <body>
                    <script>
                        window.opener.postMessage({{
                            type: 'instagram-auth-error',
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
    """Get user's Instagram accounts with comprehensive error handling"""
    try:
        # Initialize account service
        try:
            account_service = InstagramAccountService(db)
        except Exception as e:
            logger.error(f"Failed to initialize InstagramAccountService: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize account service. Please try again later."
            )
        
        # Fetch accounts with proper error handling
        try:
            accounts = await account_service.get_user_accounts(user_id)
        except Exception as e:
            logger.error(f"Database error fetching accounts for user {user_id}: {e}")
            if "connection" in str(e).lower():
                raise HTTPException(
                    status_code=503,
                    detail="Unable to connect to database. Please try again in a moment."
                )
            elif "timeout" in str(e).lower():
                raise HTTPException(
                    status_code=504,
                    detail="Request timed out. Please try again."
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to fetch Instagram accounts. Please try refreshing the page."
                )
        
        # Handle empty accounts gracefully
        if not accounts:
            logger.info(f"No Instagram accounts found for user {user_id}")
            return {
                "success": True,
                "accounts": [],
                "count": 0,
                "message": "No Instagram accounts connected. Connect an account to get started."
            }
        
        logger.info(f"Successfully fetched {len(accounts)} accounts for user {user_id}")
        
        return {
            "success": True,
            "accounts": accounts,
            "count": len(accounts),
            "message": f"Found {len(accounts)} connected account{'s' if len(accounts) != 1 else ''}"
        }
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Unexpected error in get_accounts: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while fetching accounts. Please try again later."
        )


@router.get("/accounts/{account_id}")
async def get_account(
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get specific Instagram account details"""
    try:
        account_service = InstagramAccountService(db)
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
        logger.error(f"Failed to get Instagram account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/accounts/{account_id}")
async def remove_account(
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Remove an Instagram account connection"""
    try:
        oauth_handler = InstagramOAuthHandler(db)
        success = await oauth_handler.remove_account(user_id, account_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Account not found")
        
        return {
            "success": True,
            "message": f"Instagram account {account_id} removed successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove Instagram account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh-token/{account_id}")
async def refresh_token(
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Refresh access token for an account"""
    try:
        oauth_handler = InstagramOAuthHandler(db)
        access_token = await oauth_handler.get_valid_token(user_id, account_id)
        
        return {
            "success": True,
            "message": "Token refreshed successfully"
        }
    except Exception as e:
        logger.error(f"Failed to refresh token: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accounts/{account_id}/refresh")
async def refresh_account_info(
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Refresh account information from Instagram API"""
    try:
        account_service = InstagramAccountService(db)
        account = await account_service.refresh_account_info(user_id, account_id)
        
        return {
            "success": True,
            "account": account,
            "message": "Account information refreshed successfully"
        }
    except Exception as e:
        logger.error(f"Failed to refresh account info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prepare-upload")
async def prepare_upload(
    file: UploadFile = File(...),
    file_type: str = Form("auto"),
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Prepare a file for Instagram upload using reference ID system"""
    try:
        # Initialize file service
        file_service = YouTubeFileService(db, user_id)
        
        # Read file content
        file_content = await file.read()
        
        # Create reference for the file
        reference_id = await file_service.create_video_reference(
            user_id=user_id,
            file_data=file_content,
            file_name=file.filename,
            mime_type=file.content_type or "application/octet-stream"
        )
        
        return {
            "success": True,
            "reference_id": reference_id,
            "filename": file.filename,
            "file_size": len(file_content),
            "file_type": file_type,
            "expires_at": None,  # File service handles expiration
            "message": "File prepared for Instagram upload"
        }
    except Exception as e:
        logger.error(f"Failed to prepare Instagram upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/post")
async def create_post(
    post_data: Dict[str, Any],
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Create an Instagram post with intelligent auto-discovery"""
    try:
        upload_service = InstagramUploadService(db)
        result = await upload_service.create_post(user_id, post_data)
        
        return {
            "success": True,
            **result
        }
    except Exception as e:
        logger.error(f"Failed to create Instagram post: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/story")
async def create_story(
    story_data: Dict[str, Any],
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Create an Instagram story"""
    try:
        upload_service = InstagramUploadService(db)
        result = await upload_service.create_story(user_id, story_data)
        
        return result
    except Exception as e:
        logger.error(f"Failed to create Instagram story: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/post-status/{post_record_id}")
async def get_post_status(
    post_record_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get Instagram post creation status"""
    try:
        upload_service = InstagramUploadService(db)
        status = await upload_service.get_post_status(user_id, post_record_id)
        
        return {
            "success": True,
            **status
        }
    except Exception as e:
        logger.error(f"Failed to get Instagram post status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/{account_id}/posts")
async def get_account_posts(
    account_id: str,
    limit: int = 25,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get recent posts for an Instagram account"""
    try:
        upload_service = InstagramUploadService(db)
        result = await upload_service.get_recent_posts(user_id, account_id, limit)
        
        return result
    except Exception as e:
        logger.error(f"Failed to get Instagram posts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/posts/{media_id}")
async def delete_post(
    media_id: str,
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Delete an Instagram post"""
    try:
        upload_service = InstagramUploadService(db)
        result = await upload_service.delete_post(user_id, account_id, media_id)
        
        return result
    except Exception as e:
        logger.error(f"Failed to delete Instagram post: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/posts/{media_id}/insights")
async def get_post_insights(
    media_id: str,
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get insights for an Instagram post (business accounts only)"""
    try:
        upload_service = InstagramUploadService(db)
        result = await upload_service.get_post_insights(user_id, account_id, media_id)
        
        return result
    except Exception as e:
        logger.error(f"Failed to get Instagram post insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hashtag/{hashtag}/posts")
async def search_hashtag_posts(
    hashtag: str,
    account_id: str,
    limit: int = 25,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Search for posts by hashtag (business accounts only)"""
    try:
        upload_service = InstagramUploadService(db)
        result = await upload_service.search_hashtag_posts(user_id, account_id, hashtag, limit)
        
        return result
    except Exception as e:
        logger.error(f"Failed to search Instagram hashtag posts: {e}")
        raise HTTPException(status_code=500, detail=str(e))