"""Twitter MCP API Routes"""

from fastapi import APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import json

from services.supabase import DBConnection
from utils.auth_utils import get_current_user_id_from_jwt
from utils.logger import logger
from .oauth import TwitterOAuthHandler
from .accounts import TwitterAccountService
from .upload import TwitterUploadService
from .twitter_service import TwitterAPIService
from services.youtube_file_service import YouTubeFileService


router = APIRouter(prefix="/twitter", tags=["Twitter MCP"])

# Database connection
db: Optional[DBConnection] = None


def initialize(database: DBConnection):
    """Initialize Twitter MCP with database connection"""
    global db
    db = database


@router.post("/auth/initiate")
async def initiate_auth(
    request: Optional[Dict[str, Any]] = None,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Start Twitter OAuth flow with optional thread context"""
    try:
        oauth_handler = TwitterOAuthHandler(db)
        
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
        
        # Generate OAuth URL with PKCE
        auth_url, code_verifier, oauth_state = oauth_handler.get_auth_url(state=state)
        
        # Store OAuth session
        await oauth_handler.store_oauth_session(oauth_state, code_verifier, user_id)
        
        return {
            "success": True,
            "auth_url": auth_url,
            "message": "Visit the auth_url to connect your Twitter account"
        }
    except Exception as e:
        logger.error(f"Failed to initiate Twitter auth: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/callback")
async def auth_callback(
    code: str,
    state: Optional[str] = None,
    error: Optional[str] = None
):
    """Handle Twitter OAuth callback"""
    
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
                            background: linear-gradient(135deg, #1DA1F2 0%, #0D8BD9 100%);
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
                        <p>We couldn't connect your Twitter account.</p>
                        <div class="error-message">
                            {error.replace('_', ' ').title() if error != 'access_denied' else 'Access was denied. Please try again.'}
                        </div>
                        <p style="font-size: 14px; margin-top: 1rem;">This window will close automatically...</p>
                    </div>
                    <script>
                        if (window.opener) {{
                            window.opener.postMessage({{
                                type: 'twitter-auth-error',
                                error: '{error}'
                            }}, '*');
                            setTimeout(() => window.close(), 3000);
                        }} else {{
                            const returnUrl = sessionStorage.getItem('twitter_auth_return_url') || document.referrer || '/agents';
                            setTimeout(() => {{
                                window.location.href = returnUrl;
                            }}, 3000);
                        }}
                    </script>
                </body>
            </html>
        """)
    
    try:
        oauth_handler = TwitterOAuthHandler(db)
        
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
                    <title>Twitter Connected</title>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            height: 100vh;
                            margin: 0;
                            background: linear-gradient(135deg, #1DA1F2 0%, #0D8BD9 100%);
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
                                <div class="account-name">{user_info.get('name', 'Twitter User')}</div>
                                <div style="color: #6b7280; font-size: 14px;">@{user_info.get('username', '')}</div>
                            </div>
                        </div>
                        <p>Closing this window...</p>
                    </div>
                    <script>
                        const isPopup = (
                            window.opener !== null ||
                            window.name === 'twitter-auth' ||
                            window.innerWidth <= 700 ||
                            window.location.search.includes('popup=true')
                        );
                        
                        if (isPopup) {{
                            try {{
                                if (window.opener && !window.opener.closed) {{
                                    window.opener.postMessage({{
                                        type: 'twitter-auth-success',
                                        account: {json.dumps(user_info)}
                                    }}, '*');
                                }} else {{
                                    localStorage.setItem('twitter-auth-result', JSON.stringify({{
                                        type: 'twitter-auth-success',
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
                                returnUrl = sessionStorage.getItem('twitter_auth_return_url') || document.referrer || '/agents';
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
        logger.error(f"Twitter OAuth callback failed: {e}")
        return HTMLResponse(content=f"""
            <html>
                <body>
                    <script>
                        window.opener.postMessage({{
                            type: 'twitter-auth-error',
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
    """Get user's Twitter accounts with comprehensive error handling"""
    try:
        # Initialize account service
        try:
            account_service = TwitterAccountService(db)
        except Exception as e:
            logger.error(f"Failed to initialize TwitterAccountService: {e}")
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
                    detail="Failed to fetch Twitter accounts. Please try refreshing the page."
                )
        
        # Handle empty accounts gracefully
        if not accounts:
            logger.info(f"No Twitter accounts found for user {user_id}")
            return {
                "success": True,
                "accounts": [],
                "count": 0,
                "message": "No Twitter accounts connected. Connect an account to get started."
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
    """Get specific Twitter account details"""
    try:
        account_service = TwitterAccountService(db)
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
        logger.error(f"Failed to get Twitter account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/accounts/{account_id}")
async def remove_account(
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Remove a Twitter account connection"""
    try:
        oauth_handler = TwitterOAuthHandler(db)
        success = await oauth_handler.remove_account(user_id, account_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Account not found")
        
        return {
            "success": True,
            "message": f"Twitter account {account_id} removed successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove Twitter account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh-token/{account_id}")
async def refresh_token(
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Refresh access token for an account"""
    try:
        oauth_handler = TwitterOAuthHandler(db)
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
    """Refresh account information including profile pictures"""
    try:
        account_service = TwitterAccountService(db)
        account = await account_service.refresh_account_info(user_id, account_id)
        
        return {
            "success": True,
            "account": account,
            "message": "Account information refreshed successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh account info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tweet")
async def create_tweet(
    request: Dict[str, Any],
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Create a tweet with automatic file discovery"""
    try:
        upload_service = TwitterUploadService(db)
        
        # Prepare tweet parameters
        tweet_params = {
            "account_id": request.get("account_id"),
            "text": request.get("text", ""),
            "reply_to_tweet_id": request.get("reply_to_tweet_id"),
            "quote_tweet_id": request.get("quote_tweet_id"),
            "video_reference_id": request.get("video_reference_id"),
            "image_reference_ids": request.get("image_reference_ids", []),
            "auto_discover": request.get("auto_discover", True)
        }
        
        # Call upload service (will auto-discover files if not provided)
        result = await upload_service.create_tweet(user_id, tweet_params)
        
        return {
            "success": True,
            **result
        }
        
    except Exception as e:
        logger.error(f"Tweet creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tweet-status/{tweet_record_id}")
async def get_tweet_status(
    tweet_record_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get the status of a tweet creation"""
    try:
        upload_service = TwitterUploadService(db)
        status = await upload_service.get_tweet_status(user_id, tweet_record_id)
        
        return {
            "success": True,
            **status
        }
        
    except Exception as e:
        logger.error(f"Failed to get tweet status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tweet/{tweet_id}")
async def delete_tweet(
    tweet_id: str,
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Delete a tweet"""
    try:
        upload_service = TwitterUploadService(db)
        result = await upload_service.delete_tweet(user_id, account_id, tweet_id)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to delete tweet: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/{account_id}/tweets")
async def get_account_tweets(
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt),
    limit: int = 10
) -> Dict[str, Any]:
    """Get recent tweets from an account"""
    try:
        upload_service = TwitterUploadService(db)
        result = await upload_service.get_recent_tweets(user_id, account_id, limit)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get account tweets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_tweets(
    query: str,
    account_id: str,
    max_results: int = 10,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Search for tweets"""
    try:
        upload_service = TwitterUploadService(db)
        result = await upload_service.search_tweets(user_id, account_id, query, max_results)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to search tweets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== File Upload Endpoints =====

@router.post("/prepare-upload")
async def prepare_upload(
    file: UploadFile = File(...),
    file_type: Optional[str] = Form("auto"),
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Prepare a file for Twitter upload with comprehensive error handling"""
    try:
        # Validate file exists and has content
        if not file or not file.filename:
            logger.error(f"No file provided for upload")
            raise HTTPException(
                status_code=400,
                detail="No file provided. Please select a file to upload."
            )
        
        # Initialize file service
        try:
            file_service = YouTubeFileService(db)  # Reuse YouTube file service
        except Exception as e:
            logger.error(f"Failed to initialize file service: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize upload service. Please try again later."
            )
        
        # Read file data with size validation
        try:
            file_data = await file.read()
            
            # Check if file is empty
            if not file_data or len(file_data) == 0:
                logger.error(f"Empty file uploaded: {file.filename}")
                raise HTTPException(
                    status_code=400,
                    detail=f"The file '{file.filename}' is empty. Please select a valid file."
                )
            
            # Check file size (Twitter limits)
            if file.content_type and file.content_type.startswith("video/"):
                max_size = 512 * 1024 * 1024  # 512MB for videos
            else:
                max_size = 5 * 1024 * 1024  # 5MB for images
                
            if len(file_data) > max_size:
                logger.error(f"File too large: {len(file_data)} bytes")
                raise HTTPException(
                    status_code=400,
                    detail=f"File size exceeds maximum allowed ({max_size // (1024*1024)}MB). Your file is {len(file_data) / (1024*1024):.2f}MB."
                )
                
        except HTTPException:
            raise  # Re-raise HTTP exceptions
        except Exception as e:
            logger.error(f"Failed to read file data: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to read file data. The file may be corrupted or inaccessible."
            )
        
        # Detect file type
        if file_type == "auto":
            try:
                detected_type = file_service.detect_file_type(file.content_type, file.filename)
                if detected_type == "unknown":
                    logger.error(f"Unknown file type: {file.content_type} for {file.filename}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Could not determine if '{file.filename}' is a video or image. Supported formats: MP4, MOV, JPEG, PNG, GIF."
                    )
                file_type = detected_type
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error detecting file type: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to detect file type. Please specify if this is a video or image."
                )
        
        # Validate file type
        if file_type not in ["video", "thumbnail", "image"]:
            logger.error(f"Invalid file type specified: {file_type}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type '{file_type}'. Must be 'video', 'image', or 'thumbnail'."
            )
        
        # Create reference
        try:
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
                
            logger.info(f"Successfully prepared {file_type} upload for user {user_id}: {result['reference_id']}")
            
        except ValueError as ve:
            logger.error(f"Validation error: {ve}")
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logger.error(f"Failed to create {file_type} reference: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process {file_type}. Please try again or contact support if the problem persists."
            )
        
        # Return success response
        return {
            "success": True,
            "reference_id": result["reference_id"],
            "file_name": result["file_name"],
            "file_size": result["file_size"],
            "file_type": file_type,
            "expires_at": result["expires_at"],
            "warnings": result.get("warnings", []),
            "message": f"Successfully prepared {file_type} for Twitter upload",
            **({
                "dimensions": result["dimensions"]
            } if file_type in ["thumbnail", "image"] and "dimensions" in result else {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in prepare_upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again later."
        )


@router.post("/universal-upload")
async def universal_upload(
    upload_data: Dict[str, Any],
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Universal upload endpoint for Twitter social media platform"""
    try:
        platform = upload_data.get("platform", "").lower()
        
        if platform == "twitter":
            # Delegate to Twitter upload
            upload_service = TwitterUploadService(db)
            
            # Convert universal params to Twitter format
            twitter_params = {
                "account_id": upload_data["account_id"],
                "text": upload_data.get("text", upload_data.get("title", "")),
                "reply_to_tweet_id": upload_data.get("reply_to_tweet_id"),
                "quote_tweet_id": upload_data.get("quote_tweet_id"),
                "video_reference_id": upload_data.get("video_reference_id"),
                "image_reference_ids": upload_data.get("image_reference_ids", []),
                "auto_discover": upload_data.get("auto_discover", True)
            }
            
            # Start Twitter tweet creation
            result = await upload_service.create_tweet(user_id, twitter_params)
            
            return {
                "success": True,
                "tweet_record_id": result.get("tweet_record_id"),
                "platform": "twitter",
                "status": "posting",
                "message": "Tweet creation started",
                "tweet_started": True,
                "account": {
                    "id": upload_data["account_id"],
                    "name": result.get("account_name", "Twitter Account"),
                    "username": result.get("account_username", "")
                }
            }
        else:
            raise HTTPException(
                status_code=501, 
                detail=f"Platform '{platform}' not yet supported. Currently supporting: twitter"
            )
            
    except Exception as e:
        logger.error(f"Universal upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ===== UNIFIED SOCIAL ACCOUNTS ENDPOINTS =====

@router.get("/agents/{agent_id}/social-accounts/twitter/enabled")
async def get_agent_enabled_twitter_accounts(
    agent_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get ONLY enabled Twitter accounts for an agent - UNIFIED SYSTEM ENDPOINT"""
    try:
        account_service = TwitterAccountService(db)
        accounts = await account_service.get_accounts_for_agent(user_id, agent_id)
        
        logger.info(f"🎯 Unified System: Agent {agent_id} has {len(accounts)} enabled Twitter accounts")
        for acc in accounts:
            logger.info(f"  ✅ Enabled: {acc['name']} (@{acc['username']})")
        
        return {
            "success": True,
            "agent_id": agent_id,
            "accounts": accounts,  # Use 'accounts' for tool compatibility
            "count": len(accounts)
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get enabled Twitter accounts from unified system: {e}")
        return {
            "success": False,
            "error": str(e),
            "agent_id": agent_id,
            "accounts": [],
            "count": 0
        }