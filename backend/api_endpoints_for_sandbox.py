"""
Backend API endpoints for sandbox YouTube tool access
These endpoints allow the Daytona sandbox to communicate with backend services
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from utils.auth_utils import get_current_user_id_from_jwt
from services.supabase import DBConnection
from services.mcp_toggles import MCPToggleService
from youtube_mcp.channels import YouTubeChannelService
from youtube_mcp.oauth import YouTubeOAuthHandler
from services.youtube_file_service import YouTubeFileService
from utils.logger import logger

router = APIRouter(prefix="/youtube/sandbox", tags=["YouTube Sandbox API"])
db: Optional[DBConnection] = None

def initialize(database: DBConnection):
    """Initialize with database connection"""
    global db
    db = database

@router.get("/channels/enabled/{agent_id}")
async def get_enabled_channels_for_sandbox(
    agent_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get enabled YouTube channels for sandbox access"""
    try:
        toggle_service = MCPToggleService(db)
        channel_service = YouTubeChannelService(db)
        
        # Get all connected channels
        all_channels = await channel_service.get_user_channels(user_id)
        
        # Filter to enabled channels via MCP toggles
        enabled_channels = []
        for channel in all_channels:
            mcp_id = f"social.youtube.{channel['id']}"
            is_enabled = await toggle_service.is_enabled(agent_id, user_id, mcp_id)
            if is_enabled:
                enabled_channels.append(channel)
        
        return {
            "success": True,
            "channels": enabled_channels,
            "count": len(enabled_channels)
        }
    except Exception as e:
        logger.error(f"Failed to get enabled channels for sandbox: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/token/{channel_id}")
async def get_youtube_token_for_sandbox(
    channel_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get YouTube OAuth token for sandbox access"""
    try:
        oauth_handler = YouTubeOAuthHandler(db)
        access_token = await oauth_handler.get_valid_token(user_id, channel_id)
        
        return {
            "success": True,
            "access_token": access_token
        }
    except Exception as e:
        logger.error(f"Failed to get YouTube token for sandbox: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/file/{reference_id}")
async def get_video_file_for_sandbox(
    reference_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
):
    """Download video file for sandbox access"""
    try:
        file_service = YouTubeFileService(db, user_id)
        file_data = await file_service.get_file_data(reference_id, user_id)
        
        if not file_data:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Return binary file data
        from fastapi.responses import Response
        return Response(
            content=file_data,
            media_type="video/mp4",
            headers={"Content-Disposition": f"attachment; filename=video_{reference_id}.mp4"}
        )
    except Exception as e:
        logger.error(f"Failed to get video file for sandbox: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/file/auto/{user_id}")
async def get_latest_video_for_sandbox(
    user_id: str,
    authenticated_user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get latest video file reference ID for auto-discovery"""
    try:
        if user_id != authenticated_user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        file_service = YouTubeFileService(db, user_id)
        uploads = await file_service.get_latest_pending_uploads(user_id)
        
        if uploads.get("video"):
            return {
                "success": True,
                "video_reference_id": uploads["video"]["reference_id"],
                "file_name": uploads["video"]["file_name"],
                "file_size": uploads["video"]["file_size"]
            }
        else:
            return {
                "success": False,
                "error": "No recent video files found"
            }
    except Exception as e:
        logger.error(f"Failed to get latest video for sandbox: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recent-uploads")
async def get_recent_uploads_for_sandbox(
    limit: int = 5,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get recent YouTube uploads for sandbox access"""
    try:
        from datetime import datetime, timedelta, timezone
        
        client = await db.client
        
        # Get uploads from last 24 hours
        one_day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        
        result = await client.table("youtube_uploads").select("*").eq(
            "user_id", user_id
        ).gte(
            "created_at", one_day_ago.isoformat()
        ).order("created_at", desc=True).limit(limit).execute()
        
        uploads = []
        for upload in result.data:
            uploads.append({
                "id": upload["id"],
                "title": upload["title"],
                "channel_id": upload["channel_id"],
                "video_id": upload.get("video_id"),
                "upload_status": upload["upload_status"],
                "status_message": upload.get("status_message"),
                "created_at": upload["created_at"],
                "completed_at": upload.get("completed_at")
            })
        
        return {
            "success": True,
            "uploads": uploads,
            "count": len(uploads)
        }
        
    except Exception as e:
        logger.error(f"Failed to get recent uploads for sandbox: {e}")
        raise HTTPException(status_code=500, detail=str(e))