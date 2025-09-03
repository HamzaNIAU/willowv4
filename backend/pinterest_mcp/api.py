"""Pinterest MCP API Routes - Simplified to use existing tables"""

from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import json
import base64
import secrets

from services.supabase import DBConnection
from utils.auth_utils import get_current_user_id_from_jwt
from utils.logger import logger


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
    """Start Pinterest OAuth flow - Simplified implementation"""
    try:
        # Pinterest OAuth configuration
        client_id = "1509701"  # From environment
        redirect_uri = "http://localhost:8000/api/pinterest/auth/callback"
        
        # Create state with user_id
        state_data = {"user_id": user_id}
        if request:
            if "thread_id" in request:
                state_data["thread_id"] = request["thread_id"]
            if "project_id" in request:
                state_data["project_id"] = request["project_id"]
        
        # Encode state as JSON
        state_json = json.dumps(state_data)
        state = base64.urlsafe_b64encode(state_json.encode()).decode()
        
        # Pinterest OAuth URL
        scopes = "pins:read,pins:write,boards:read,boards:write,user_accounts:read"
        auth_url = f"https://www.pinterest.com/oauth/?client_id={client_id}&redirect_uri={redirect_uri}&scope={scopes}&response_type=code&state={state}"
        
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
    """Handle Pinterest OAuth callback - Simplified implementation"""
    
    if error:
        return HTMLResponse(content=f"""
        <html>
            <script>
                window.opener.postMessage({{
                    type: 'pinterest-auth-error',
                    error: '{error}'
                }}, '*');
                window.close();
            </script>
        </html>
        """)
    
    try:
        # Decode state to get user info
        state_json = base64.urlsafe_b64decode(state.encode()).decode()
        state_data = json.loads(state_json)
        user_id = state_data["user_id"]
        
        # Create mock account info (for now, until we can properly connect to Pinterest API)
        account_info = {
            "id": f"pinterest_user_{user_id}",
            "name": "Pinterest Account",
            "username": "pinterest_user",
            "profile_image_url": "/platforms/pinterest.png"
        }
        
        # Store in unified social accounts table (which exists)
        client = await db.client
        await client.table("agent_social_accounts").upsert({
            "agent_id": "suna-default",
            "user_id": user_id,
            "platform": "pinterest",
            "account_id": account_info["id"],
            "account_name": account_info["name"],
            "username": account_info["username"],
            "profile_picture": account_info["profile_image_url"],
            "subscriber_count": 0,
            "view_count": 0,
            "video_count": 0,
            "enabled": True
        }, on_conflict="agent_id,user_id,platform,account_id").execute()
        
        return HTMLResponse(content=f"""
        <html>
            <script>
                window.opener.postMessage({{
                    type: 'pinterest-auth-success',
                    account: {json.dumps(account_info)}
                }}, '*');
                window.close();
            </script>
        </html>
        """)
        
    except Exception as e:
        logger.error(f"Pinterest OAuth callback failed: {e}")
        return HTMLResponse(content=f"""
        <html>
            <script>
                window.opener.postMessage({{
                    type: 'pinterest-auth-error',
                    error: 'Connection failed'
                }}, '*');
                window.close();
            </script>
        </html>
        """)


@router.get("/accounts")
async def get_accounts(
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get Pinterest accounts - Using unified social accounts table"""
    try:
        client = await db.client
        
        # Query unified social accounts table for Pinterest accounts
        result = await client.table("agent_social_accounts").select("*").eq(
            "user_id", user_id
        ).eq("platform", "pinterest").eq("enabled", True).execute()
        
        accounts = []
        for account in result.data or []:
            accounts.append({
                "id": account["account_id"],
                "name": account["account_name"],
                "username": account.get("username"),
                "profile_picture": account.get("profile_picture"),
                "profile_picture_medium": account.get("profile_picture"),
                "profile_picture_small": account.get("profile_picture"),
                "subscriber_count": account.get("subscriber_count", 0),
                "view_count": account.get("view_count", 0),
                "video_count": account.get("video_count", 0),
                "created_at": account.get("created_at"),
                "updated_at": account.get("updated_at"),
            })
        
        return {
            "success": True,
            "accounts": accounts
        }
        
    except Exception as e:
        logger.error(f"Failed to get Pinterest accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/accounts/{account_id}")
async def remove_account(
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Remove Pinterest account connection"""
    try:
        client = await db.client
        
        # Remove from unified social accounts table
        await client.table("agent_social_accounts").delete().eq(
            "user_id", user_id
        ).eq("platform", "pinterest").eq("account_id", account_id).execute()
        
        return {
            "success": True,
            "message": "Pinterest account disconnected successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to remove Pinterest account: {e}")
        raise HTTPException(status_code=500, detail=str(e))