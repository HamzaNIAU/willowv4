"""YouTube MCP API Routes"""

from fastapi import APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import json

from services.supabase import DBConnection
from utils.auth_utils import get_current_user_id_from_jwt
from utils.logger import logger
from .oauth import YouTubeOAuthHandler
from .channels import YouTubeChannelService
from .server import YouTubeMCPServer
from services.youtube_file_service import YouTubeFileService


router = APIRouter(prefix="/youtube", tags=["YouTube MCP"])

# Database connection
db: Optional[DBConnection] = None


def initialize(database: DBConnection):
    """Initialize YouTube MCP with database connection"""
    global db
    db = database


@router.post("/auth/initiate")
async def initiate_auth(
    request: Optional[Dict[str, Any]] = None,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Start YouTube OAuth flow with optional thread context"""
    try:
        oauth_handler = YouTubeOAuthHandler(db)
        
        # Create state with user_id and optional thread context
        state_data = {
            "user_id": user_id
        }
        
        # Add thread context if provided (for returning to correct conversation)
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
        
        auth_url = oauth_handler.get_auth_url(state=state)
        
        return {
            "success": True,
            "auth_url": auth_url,
            "message": "Visit the auth_url to connect your YouTube account"
        }
    except Exception as e:
        logger.error(f"Failed to initiate YouTube auth: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/callback")
async def auth_callback(
    code: str,
    state: Optional[str] = None,
    error: Optional[str] = None
):
    """Handle YouTube OAuth callback"""
    
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
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
                        <p>We couldn't connect your YouTube account.</p>
                        <div class="error-message">
                            {error.replace('_', ' ').title() if error != 'access_denied' else 'Access was denied. Please try again.'}
                        </div>
                        <p style="font-size: 14px; margin-top: 1rem;">This window will close automatically...</p>
                    </div>
                    <script>
                        // Check if we're in a popup or main window
                        if (window.opener) {{
                            // We're in a popup - send message to opener and close
                            window.opener.postMessage({{
                                type: 'youtube-auth-error',
                                error: '{error}'
                            }}, '*');
                            setTimeout(() => window.close(), 3000);
                        }} else {{
                            // We're in the main window - redirect back
                            const returnUrl = sessionStorage.getItem('youtube_auth_return_url') || document.referrer || '/agents';
                            setTimeout(() => {{
                                window.location.href = returnUrl;
                            }}, 3000);
                        }}
                    </script>
                </body>
            </html>
        """)
    
    try:
        oauth_handler = YouTubeOAuthHandler(db)
        
        # Exchange code for tokens
        access_token, refresh_token, expires_at = await oauth_handler.exchange_code_for_tokens(code)
        
        # Get channel info
        channel_info = await oauth_handler.get_channel_info(access_token)
        
        # Parse state to get user_id and thread context
        import base64
        try:
            state_json = base64.urlsafe_b64decode(state.encode()).decode()
            state_data = json.loads(state_json)
            user_id = state_data.get("user_id", state)  # Fallback to state as user_id for backward compatibility
            thread_id = state_data.get("thread_id")
            project_id = state_data.get("project_id")
            return_url = state_data.get("return_url")
        except:
            # Backward compatibility: if state is just user_id
            user_id = state
            thread_id = None
            project_id = None
            return_url = None
        
        # Save channel to database
        channel_id = await oauth_handler.save_channel(
            user_id=user_id,
            channel_info=channel_info,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at
        )
        
        # Return success HTML that closes the popup and shows success message
        return HTMLResponse(content=f"""
            <html>
                <head>
                    <title>YouTube Connected</title>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            height: 100vh;
                            margin: 0;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
                        .channel-info {{
                            display: flex;
                            align-items: center;
                            gap: 1rem;
                            padding: 1rem;
                            background: #f9fafb;
                            border-radius: 8px;
                            margin-bottom: 1rem;
                        }}
                        .channel-avatar {{
                            width: 48px;
                            height: 48px;
                            border-radius: 50%;
                        }}
                        .channel-name {{
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
                        <div class="channel-info">
                            {f'<img src="{channel_info.get("profile_picture", "")}" alt="" class="channel-avatar">' if channel_info.get("profile_picture") else ''}
                            <div style="text-align: left;">
                                <div class="channel-name">{channel_info.get('name', 'YouTube Channel')}</div>
                                <div style="color: #6b7280; font-size: 14px;">@{channel_info.get('username', '')}</div>
                            </div>
                        </div>
                        <p>Closing this window...</p>
                    </div>
                    <script>
                        // Detect if we're in a popup using multiple methods
                        const isPopup = (
                            window.opener !== null ||  // Has opener reference
                            window.name === 'youtube-auth' ||  // Named popup window
                            window.innerWidth <= 700 ||  // Popup size constraints
                            window.location.search.includes('popup=true')  // Explicit popup parameter
                        );
                        
                        if (isPopup) {{
                            // We're in a popup - try to send message to opener
                            try {{
                                // Try to post message to opener if available
                                if (window.opener && !window.opener.closed) {{
                                    window.opener.postMessage({{
                                        type: 'youtube-auth-success',
                                        channel: {json.dumps(channel_info)}
                                    }}, '*');
                                }} else {{
                                    // If no opener, try to communicate via storage event
                                    localStorage.setItem('youtube-auth-result', JSON.stringify({{
                                        type: 'youtube-auth-success',
                                        channel: {json.dumps(channel_info)},
                                        timestamp: Date.now()
                                    }}));
                                }}
                            }} catch (e) {{
                                console.error('Failed to communicate with opener:', e);
                            }}
                            
                            // Always close the popup
                            setTimeout(() => {{
                                window.close();
                                // If close doesn't work (some browsers block it), show manual close message
                                setTimeout(() => {{
                                    document.body.innerHTML = '<div style="text-align: center; padding: 2rem;">You can close this window now.</div>';
                                }}, 500);
                            }}, 2000);
                        }} else {{
                            // Only redirect if we're absolutely sure we're NOT in a popup
                            // This should rarely happen since we're always opening in popup from chat
                            let returnUrl = '{return_url if return_url else ""}';
                            
                            if (!returnUrl && {json.dumps(bool(thread_id))}) {{
                                const projectId = '{project_id if project_id else ""}';
                                const threadId = '{thread_id if thread_id else ""}';
                                if (projectId && threadId) {{
                                    returnUrl = `/projects/${{projectId}}/thread/${{threadId}}`;
                                }}
                            }}
                            
                            if (!returnUrl) {{
                                returnUrl = sessionStorage.getItem('youtube_auth_return_url') || document.referrer || '/agents';
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
        logger.error(f"YouTube OAuth callback failed: {e}")
        return HTMLResponse(content=f"""
            <html>
                <body>
                    <script>
                        window.opener.postMessage({{
                            type: 'youtube-auth-error',
                            error: '{str(e)}'
                        }}, '*');
                        window.close();
                    </script>
                </body>
            </html>
        """)


@router.get("/channels")
async def get_channels(
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get user's YouTube channels"""
    try:
        channel_service = YouTubeChannelService(db)
        channels = await channel_service.get_user_channels(user_id)
        
        return {
            "success": True,
            "channels": channels,
            "count": len(channels)
        }
    except Exception as e:
        logger.error(f"Failed to get YouTube channels: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/channels/{channel_id}")
async def get_channel(
    channel_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get specific YouTube channel details"""
    try:
        channel_service = YouTubeChannelService(db)
        channel = await channel_service.get_channel(user_id, channel_id)
        
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")
        
        return {
            "success": True,
            "channel": channel
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get YouTube channel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/channels/{channel_id}")
async def remove_channel(
    channel_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Remove a YouTube channel connection"""
    try:
        oauth_handler = YouTubeOAuthHandler(db)
        success = await oauth_handler.remove_channel(user_id, channel_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Channel not found")
        
        return {
            "success": True,
            "message": f"Channel {channel_id} removed successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove YouTube channel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh-token/{channel_id}")
async def refresh_token(
    channel_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Refresh access token for a channel"""
    try:
        oauth_handler = YouTubeOAuthHandler(db)
        access_token = await oauth_handler.get_valid_token(user_id, channel_id)
        
        return {
            "success": True,
            "message": "Token refreshed successfully"
        }
    except Exception as e:
        logger.error(f"Failed to refresh token: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/channels/{channel_id}/refresh")
async def refresh_channel_info(
    channel_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Refresh channel information including profile pictures"""
    try:
        oauth_handler = YouTubeOAuthHandler(db)
        
        # Get valid access token
        access_token = await oauth_handler.get_valid_token(user_id, channel_id)
        
        # Fetch updated channel info from YouTube API
        channel_info = await oauth_handler.get_channel_info(access_token)
        
        # Update channel in database
        client = await db.client
        update_data = {
            "name": channel_info["name"],
            "username": channel_info.get("username"),
            "custom_url": channel_info.get("custom_url"),
            "profile_picture": channel_info.get("profile_picture"),
            "profile_picture_medium": channel_info.get("profile_picture_medium"),
            "profile_picture_small": channel_info.get("profile_picture_small"),
            "description": channel_info.get("description"),
            "subscriber_count": channel_info.get("subscriber_count", 0),
            "view_count": channel_info.get("view_count", 0),
            "video_count": channel_info.get("video_count", 0),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        result = await client.table("youtube_channels").update(update_data).eq(
            "user_id", user_id
        ).eq("id", channel_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to update channel")
        
        logger.info(f"Refreshed channel info for {channel_id}")
        
        # Return updated channel info
        channel_service = YouTubeChannelService(db)
        channel = await channel_service.get_channel(user_id, channel_id)
        
        return {
            "success": True,
            "channel": channel,
            "message": "Channel information refreshed successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh channel info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/channels/debug")
async def debug_channels(
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Debug endpoint to check channel data"""
    try:
        client = await db.client
        result = await client.table("youtube_channels").select("*").eq(
            "user_id", user_id
        ).eq("is_active", True).execute()
        
        channels_debug = []
        for channel in result.data:
            channels_debug.append({
                "id": channel["id"],
                "name": channel["name"],
                "username": channel.get("username"),
                "has_profile_picture": bool(channel.get("profile_picture")),
                "profile_picture_url": channel.get("profile_picture"),
                "profile_picture_medium_url": channel.get("profile_picture_medium"),
                "profile_picture_small_url": channel.get("profile_picture_small"),
            })
        
        return {
            "success": True,
            "channels": channels_debug
        }
    except Exception as e:
        logger.error(f"Debug channels error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_video(
    request: Dict[str, Any],
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """
    Upload a video to YouTube with automatic file discovery
    """
    try:
        # Import upload service
        from .upload import YouTubeUploadService
        upload_service = YouTubeUploadService(db)
        
        # Prepare upload parameters
        upload_params = {
            "channel_id": request.get("channel_id"),
            "title": request.get("title", "Untitled Video"),
            "description": request.get("description", ""),
            "tags": request.get("tags", []),
            "category_id": request.get("category_id", "22"),
            "privacy_status": request.get("privacy_status", "public"),
            "made_for_kids": request.get("made_for_kids", False),
            "video_reference_id": request.get("video_reference_id"),
            "thumbnail_reference_id": request.get("thumbnail_reference_id"),
            "scheduled_for": request.get("scheduled_for"),
            "notify_subscribers": request.get("notify_subscribers", True)
        }
        
        # Call upload service (will auto-discover files if not provided)
        result = await upload_service.upload_video(user_id, upload_params)
        
        return {
            "success": True,
            **result
        }
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mcp-url")
async def get_mcp_url() -> Dict[str, Any]:
    """Get the MCP URL for YouTube integration"""
    # This returns the URL that the MCP client should connect to
    import os
    base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    
    return {
        "success": True,
        "mcp_url": f"{base_url}/api/youtube/mcp/stream",
        "name": "YouTube MCP",
        "description": "YouTube integration via Model Context Protocol"
    }


# MCP streaming endpoint
@router.post("/mcp/stream")
async def mcp_stream(request: Request):
    """Handle MCP protocol streaming"""
    # This would be handled by the MCP server
    # For now, return a placeholder
    return JSONResponse(content={
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "youtube-mcp",
                "version": "1.0.0"
            }
        }
    })


# ===== Video & Thumbnail Upload Endpoints =====

@router.post("/prepare-upload")
async def prepare_upload(
    file: UploadFile = File(...),
    file_type: Optional[str] = Form("video"),
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """
    Prepare a video file for YouTube upload.
    Creates a reference that can be used by the AI agent.
    """
    try:
        # Initialize file service
        file_service = YouTubeFileService(db)
        
        # Read file data
        file_data = await file.read()
        
        # Detect file type if not specified
        if file_type == "auto":
            detected_type = file_service.detect_file_type(file.content_type, file.filename)
            if detected_type == "unknown":
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not determine file type for {file.filename}"
                )
            file_type = detected_type
        
        # Validate file type
        if file_type not in ["video", "thumbnail"]:
            raise HTTPException(
                status_code=400,
                detail="file_type must be 'video' or 'thumbnail'"
            )
        
        # Create reference based on file type
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
        
        logger.info(f"Prepared {file_type} upload for user {user_id}: {result['reference_id']}")
        
        return {
            "success": True,
            "reference_id": result["reference_id"],
            "file_name": result["file_name"],
            "file_size": result["file_size"],
            "file_type": file_type,
            "expires_at": result["expires_at"],
            "warnings": result.get("warnings", []),
            **({
                "dimensions": result["dimensions"]
            } if file_type == "thumbnail" and "dimensions" in result else {})
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to prepare {file_type} upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prepare-thumbnail")
async def prepare_thumbnail(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """
    Prepare a thumbnail image for YouTube upload.
    Processes and optimizes the image to meet YouTube requirements.
    """
    try:
        # Initialize file service
        file_service = YouTubeFileService(db)
        
        # Read file data
        file_data = await file.read()
        
        # Validate it's an image
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail="File must be an image (JPEG, PNG, GIF, WebP)"
            )
        
        # Create thumbnail reference (includes processing)
        result = await file_service.create_thumbnail_reference(
            user_id=user_id,
            file_name=file.filename,
            file_data=file_data,
            mime_type=file.content_type
        )
        
        logger.info(f"Prepared thumbnail for user {user_id}: {result['reference_id']}")
        
        return {
            "success": True,
            "reference_id": result["reference_id"],
            "file_name": result["file_name"],
            "file_size": result["file_size"],
            "dimensions": result["dimensions"],
            "expires_at": result["expires_at"],
            "warnings": result.get("warnings", [])
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to prepare thumbnail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upload-status/{upload_id}")
async def get_upload_status(
    upload_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """
    Get the status of a YouTube upload.
    Returns progress information for both video and thumbnail.
    """
    try:
        client = await db.client
        
        # Get upload record
        result = await client.table("youtube_uploads").select("*").eq(
            "user_id", user_id
        ).eq("id", upload_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Upload not found")
        
        upload = result.data[0]
        
        # Prepare response
        response = {
            "success": True,
            "upload_id": upload["id"],
            "status": upload["upload_status"],
            "progress": upload.get("upload_progress", 0),
            "video": {
                "title": upload["title"],
                "file_name": upload["file_name"],
                "file_size": upload["file_size"],
                "status": upload["upload_status"],
                "progress": upload.get("upload_progress", 0),
                "video_id": upload.get("video_id")
            }
        }
        
        # Add thumbnail status if available
        if upload.get("thumbnail_reference_id"):
            # In a real implementation, we'd track thumbnail upload separately
            response["thumbnail"] = {
                "status": "completed" if upload["upload_status"] == "completed" else "pending",
                "reference_id": upload["thumbnail_reference_id"]
            }
        
        # Add timing information
        if upload.get("started_at"):
            response["started_at"] = upload["started_at"]
        if upload.get("completed_at"):
            response["completed_at"] = upload["completed_at"]
        
        # Add any error message
        if upload.get("status_message"):
            response["message"] = upload["status_message"]
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get upload status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending-uploads")
async def get_pending_uploads(
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """
    Get the latest pending video and thumbnail uploads for the user.
    Used by the AI agent to automatically find files to upload.
    """
    try:
        file_service = YouTubeFileService(db)
        
        # Get latest pending uploads
        uploads = await file_service.get_latest_pending_uploads(user_id)
        
        response = {
            "success": True,
            "video": None,
            "thumbnail": None
        }
        
        if uploads["video"]:
            response["video"] = {
                "reference_id": uploads["video"]["reference_id"],
                "file_name": uploads["video"]["file_name"],
                "file_size": uploads["video"]["file_size"],
                "created_at": uploads["video"]["created_at"],
                "expires_at": uploads["video"]["expires_at"]
            }
        
        if uploads["thumbnail"]:
            response["thumbnail"] = {
                "reference_id": uploads["thumbnail"]["reference_id"],
                "file_name": uploads["thumbnail"]["file_name"],
                "file_size": uploads["thumbnail"]["file_size"],
                "created_at": uploads["thumbnail"]["created_at"],
                "expires_at": uploads["thumbnail"]["expires_at"]
            }
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get pending uploads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup-expired")
async def cleanup_expired_references(
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """
    Clean up expired file references.
    This is typically called periodically by a background task.
    """
    try:
        file_service = YouTubeFileService(db)
        
        # Clean up expired references
        count = await file_service.cleanup_expired_references()
        
        return {
            "success": True,
            "cleaned_up": count,
            "message": f"Cleaned up {count} expired references"
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup expired references: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= New Comprehensive YouTube API Endpoints =============

@router.get("/videos/{video_id}/captions")
async def list_video_captions(
    video_id: str,
    channel_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """List available caption tracks for a video"""
    try:
        from .youtube_service import YouTubeAPIService
        youtube_service = YouTubeAPIService(db)
        return await youtube_service.list_captions(user_id, channel_id, video_id)
    except Exception as e:
        logger.error(f"Failed to list captions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/videos/{video_id}/caption/download")
async def download_video_caption(
    video_id: str,
    caption_id: str,
    channel_id: str,
    format: str = "srt",
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Download a specific caption track"""
    try:
        from .youtube_service import YouTubeAPIService
        youtube_service = YouTubeAPIService(db)
        return await youtube_service.download_caption(user_id, channel_id, video_id, caption_id, format)
    except Exception as e:
        logger.error(f"Failed to download caption: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/channels/handle/{handle}")
async def get_channel_by_handle(
    handle: str,
    channel_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get channel information by YouTube handle (@username)"""
    try:
        from .youtube_service import YouTubeAPIService
        youtube_service = YouTubeAPIService(db)
        return await youtube_service.get_channel_by_handle(user_id, channel_id, handle)
    except Exception as e:
        logger.error(f"Failed to get channel by handle: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/channels/{channel_id}/videos")
async def list_channel_videos(
    channel_id: str,
    auth_channel_id: str,
    max_results: int = 50,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """List videos from a YouTube channel"""
    try:
        from .youtube_service import YouTubeAPIService
        youtube_service = YouTubeAPIService(db)
        return await youtube_service.list_channel_videos(user_id, auth_channel_id, channel_id, max_results)
    except Exception as e:
        logger.error(f"Failed to list channel videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/playlists")
async def list_user_playlists(
    channel_id: str,
    max_results: int = 50,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """List user's YouTube playlists"""
    try:
        from .youtube_service import YouTubeAPIService
        youtube_service = YouTubeAPIService(db)
        return await youtube_service.list_playlists(user_id, channel_id, max_results)
    except Exception as e:
        logger.error(f"Failed to list playlists: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subscriptions")
async def list_user_subscriptions(
    channel_id: str,
    max_results: int = 50,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """List user's YouTube channel subscriptions"""
    try:
        from .youtube_service import YouTubeAPIService
        youtube_service = YouTubeAPIService(db)
        return await youtube_service.list_subscriptions(user_id, channel_id, max_results)
    except Exception as e:
        logger.error(f"Failed to list subscriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_youtube(
    query: str,
    channel_id: str,
    search_type: str = "video",
    max_results: int = 25,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Search YouTube for videos, channels, or playlists"""
    try:
        from .youtube_service import YouTubeAPIService
        youtube_service = YouTubeAPIService(db)
        return await youtube_service.search(user_id, channel_id, query, search_type, max_results)
    except Exception as e:
        logger.error(f"Failed to search YouTube: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscribe")
async def subscribe_to_channel(
    target_channel_id: str,
    auth_channel_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Subscribe to a YouTube channel"""
    try:
        from .youtube_service import YouTubeAPIService
        youtube_service = YouTubeAPIService(db)
        return await youtube_service.subscribe_to_channel(user_id, auth_channel_id, target_channel_id)
    except Exception as e:
        logger.error(f"Failed to subscribe to channel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/videos/{video_id}")
async def update_video_metadata(
    video_id: str,
    channel_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    category_id: Optional[str] = None,
    privacy_status: Optional[str] = None,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Update video metadata"""
    try:
        from .youtube_service import YouTubeAPIService
        youtube_service = YouTubeAPIService(db)
        
        updates = {}
        if title is not None:
            updates['title'] = title
        if description is not None:
            updates['description'] = description
        if tags is not None:
            updates['tags'] = tags
        if category_id is not None:
            updates['category_id'] = category_id
        if privacy_status is not None:
            updates['privacy_status'] = privacy_status
        
        return await youtube_service.update_video(user_id, channel_id, video_id, updates)
    except Exception as e:
        logger.error(f"Failed to update video: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/videos/{video_id}/details")
async def get_video_details(
    video_id: str,
    channel_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get detailed information about a video"""
    try:
        from .youtube_service import YouTubeAPIService
        youtube_service = YouTubeAPIService(db)
        return await youtube_service.get_video_details(user_id, channel_id, video_id)
    except Exception as e:
        logger.error(f"Failed to get video details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/videos/{video_id}/thumbnail")
async def update_video_thumbnail(
    video_id: str,
    channel_id: str,
    thumbnail_reference_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Update video thumbnail using a file reference"""
    try:
        # Get thumbnail file path from reference
        file_service = YouTubeFileService(db)
        file_info = await file_service.get_file_info(thumbnail_reference_id)
        
        if not file_info or file_info['user_id'] != user_id:
            raise HTTPException(status_code=404, detail="Thumbnail file not found")
        
        from .youtube_service import YouTubeAPIService
        youtube_service = YouTubeAPIService(db)
        return await youtube_service.update_thumbnail(user_id, channel_id, video_id, file_info['file_path'])
    except Exception as e:
        logger.error(f"Failed to update thumbnail: {e}")
        raise HTTPException(status_code=500, detail=str(e))