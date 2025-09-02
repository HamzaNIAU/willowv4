"""Unified Social Media Account API - Single Source of Truth"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from utils.auth_utils import get_current_user_id_from_jwt
from services.supabase import DBConnection
from utils.logger import logger

router = APIRouter(prefix="/agents", tags=["Unified Social Accounts"])

# Database connection
db: Optional[DBConnection] = None

def initialize(database: DBConnection):
    """Initialize with database connection"""
    global db
    db = database


class SocialAccountToggleRequest(BaseModel):
    enabled: bool


@router.get("/{agent_id}/social-accounts")
async def get_agent_social_accounts(
    agent_id: str,
    platform: Optional[str] = None,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get all social media accounts for an agent - SINGLE SOURCE OF TRUTH"""
    try:
        client = await db.client
        
        query = client.table("agent_social_accounts").select("*").eq(
            "agent_id", agent_id
        ).eq("user_id", user_id)
        
        # Filter by platform if specified
        if platform:
            query = query.eq("platform", platform.lower())
        
        result = await query.order("platform", desc=False).order("account_name", desc=False).execute()
        
        # Group by platform for easy access
        accounts_by_platform = {}
        for account in result.data:
            platform_key = account["platform"]
            if platform_key not in accounts_by_platform:
                accounts_by_platform[platform_key] = []
            
            accounts_by_platform[platform_key].append({
                "id": account["account_id"],
                "name": account["account_name"],
                "username": account["username"],
                "profile_picture": account["profile_picture"],
                "subscriber_count": account["subscriber_count"],
                "view_count": account["view_count"],
                "video_count": account["video_count"],
                "country": account["country"],
                "enabled": account["enabled"],
                "connected_at": account["connected_at"],
                "platform": account["platform"]
            })
        
        return {
            "success": True,
            "agent_id": agent_id,
            "accounts_by_platform": accounts_by_platform,
            "total_accounts": len(result.data),
            "enabled_accounts": len([a for a in result.data if a["enabled"]])
        }
        
    except Exception as e:
        logger.error(f"Failed to get agent social accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/social-accounts/youtube")
async def get_agent_youtube_accounts(
    agent_id: str,
    enabled_only: bool = True,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get YouTube accounts for an agent - DIRECT FILTERING"""
    try:
        client = await db.client
        
        query = client.table("agent_social_accounts").select("*").eq(
            "agent_id", agent_id
        ).eq("user_id", user_id).eq("platform", "youtube")
        
        # Filter to enabled only if requested
        if enabled_only:
            query = query.eq("enabled", True)
        
        result = await query.order("account_name", desc=False).execute()
        
        accounts = []
        for account in result.data:
            accounts.append({
                "id": account["account_id"],
                "name": account["account_name"],
                "username": account["username"],
                "profile_picture": account["profile_picture"],
                "subscriber_count": account["subscriber_count"],
                "view_count": account["view_count"],
                "video_count": account["video_count"],
                "country": account["country"],
                "enabled": account["enabled"],
                "connected_at": account["connected_at"]
            })
        
        logger.info(f"Found {len(accounts)} YouTube accounts for agent {agent_id} (enabled_only: {enabled_only})")
        
        return {
            "success": True,
            "agent_id": agent_id,
            "platform": "youtube",
            "accounts": accounts,
            "count": len(accounts)
        }
        
    except Exception as e:
        logger.error(f"Failed to get agent YouTube accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/social-accounts/{platform}/{account_id}/toggle")
async def toggle_social_account(
    agent_id: str,
    platform: str,
    account_id: str,
    request: SocialAccountToggleRequest,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Toggle social media account for agent - DIRECT UPDATE"""
    try:
        client = await db.client
        
        # Update account enabled state directly
        result = await client.table("agent_social_accounts").update({
            "enabled": request.enabled,
            "updated_at": "now()"
        }).eq("agent_id", agent_id).eq(
            "user_id", user_id
        ).eq("platform", platform.lower()).eq("account_id", account_id).execute()
        
        if result.data:
            logger.info(f"Toggled {platform} account {account_id} to {request.enabled} for agent {agent_id}")
            return {
                "success": True,
                "agent_id": agent_id,
                "platform": platform,
                "account_id": account_id,
                "enabled": request.enabled
            }
        else:
            raise HTTPException(status_code=404, detail="Social media account not found for this agent")
        
    except Exception as e:
        logger.error(f"Failed to toggle social account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/social-accounts/youtube/enabled")
async def get_enabled_youtube_accounts(
    agent_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get ONLY enabled YouTube accounts for an agent - FOR TOOLS"""
    try:
        client = await db.client
        
        # Direct query for enabled accounts only
        result = await client.table("agent_social_accounts").select("*").eq(
            "agent_id", agent_id
        ).eq("user_id", user_id).eq(
            "platform", "youtube"
        ).eq("enabled", True).order("account_name", desc=False).execute()
        
        enabled_accounts = []
        for account in result.data:
            enabled_accounts.append({
                "id": account["account_id"],
                "name": account["account_name"],
                "username": account["username"],
                "profile_picture": account["profile_picture"],
                "subscriber_count": account["subscriber_count"],
                "view_count": account["view_count"],
                "video_count": account["video_count"],
                "country": account["country"]
            })
        
        logger.info(f"Agent {agent_id} has {len(enabled_accounts)} enabled YouTube accounts")
        for acc in enabled_accounts:
            logger.info(f"  - {acc['name']} ({acc['id']})")
        
        return {
            "success": True,
            "agent_id": agent_id,
            "channels": enabled_accounts,  # Use 'channels' for backwards compatibility
            "count": len(enabled_accounts)
        }
        
    except Exception as e:
        logger.error(f"Failed to get enabled YouTube accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))