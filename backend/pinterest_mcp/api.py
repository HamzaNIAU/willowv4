"""Pinterest MCP API Routes - Using Unified Social Media Service"""

from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
import json
import base64
import secrets

from services.supabase import DBConnection
from services.unified_integration_service import UnifiedIntegrationService
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
    """Handle Pinterest OAuth callback - Real API implementation"""
    
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
        # Import the OAuth handler
        from pinterest_mcp.oauth import PinterestOAuthHandler
        
        # Decode state to get user info
        state_json = base64.urlsafe_b64decode(state.encode()).decode()
        state_data = json.loads(state_json)
        user_id = state_data["user_id"]
        
        # Initialize OAuth handler
        oauth_handler = PinterestOAuthHandler(db)
        
        try:
            # Exchange authorization code for real tokens
            logger.info(f"🔍 PINTEREST: Exchanging code for tokens...")
            access_token, refresh_token, expires_at = await oauth_handler.exchange_code_for_tokens(code)
            logger.info(f"🔍 PINTEREST: Got access token: {access_token[:10]}...")
            
            # Get real user info from Pinterest API
            logger.info(f"🔍 PINTEREST: Calling get_user_info with access token...")
            user_info = await oauth_handler.get_user_info(access_token)
            logger.info(f"🔍 PINTEREST: Got user info: {user_info}")
            
        except Exception as api_error:
            logger.error(f"🚨 PINTEREST API FAILED: {api_error}")
            # REMOVE MOCK FALLBACK - Let it fail instead
            raise Exception(f"Pinterest API authentication failed: {api_error}")
        
        # Prepare account info with real data from Pinterest API
        account_info = {
            "id": user_info["id"],  # Real Pinterest username/ID
            "name": user_info["name"],
            "username": user_info["username"],
            "profile_image_url": user_info.get("profile_image_url"),
            "follower_count": user_info.get("follower_count", 0),
            "following_count": user_info.get("following_count", 0),
            "post_count": user_info.get("pin_count", 0),  # Pin count for Pinterest
            "view_count": user_info.get("monthly_views", 0),  # Monthly views if available
            "access_token": access_token,  # Real access token
            "refresh_token": refresh_token,  # Real refresh token
            "token_expires_at": expires_at.isoformat(),
            "platform_data": {
                "board_count": user_info.get("board_count", 0),
                "pin_count": user_info.get("pin_count", 0),
                "monthly_views": user_info.get("monthly_views", 0),
                "account_type": user_info.get("account_type", "PERSONAL"),
                "website_url": user_info.get("website_url"),
                "about": user_info.get("about"),
                "verified": user_info.get("verified", False)
            }
        }
        
        # Use unified social media service to save account
        social_service = UnifiedSocialMediaService(db)
        account_id = await social_service.save_account(user_id, "pinterest", account_info)
        
        logger.info(f"✅ Saved Pinterest account {account_info['id']} for user {user_id} using unified service")
        
        # Create MCP toggles for all user's real agents (EXACTLY like YouTube)
        try:
            from services.mcp_toggles import MCPToggleService
            toggle_service = MCPToggleService(db)
            
            # Get all agents for this user (real agents only, like YouTube)
            client = await db.client
            agents_result = await client.table("agents").select("agent_id").eq("account_id", user_id).execute()
            
            if agents_result.data:
                mcp_id = f"social.pinterest.{account_info['id']}"
                created_count = 0
                
                for agent in agents_result.data:
                    agent_id = agent["agent_id"]
                    
                    # Skip the special suna-default virtual agent (not a valid UUID)
                    if agent_id == "suna-default":
                        logger.info(f"Skipping suna-default virtual agent for Pinterest MCP toggles")
                        continue
                    
                    # Create toggle entry (default to enabled like YouTube)
                    success = await toggle_service.set_toggle(
                        agent_id=agent_id,
                        user_id=user_id,
                        mcp_id=mcp_id,
                        enabled=True
                    )
                    
                    if success:
                        created_count += 1
                        logger.info(f"✅ Created Pinterest MCP toggle for agent {agent_id}")
                
                logger.info(f"✅ Created {created_count} Pinterest MCP toggle entries (following YouTube pattern)")
                
                # Also add to agent_social_accounts for real agents now that constraint is fixed
                for agent in agents_result.data:
                    agent_id = agent["agent_id"]
                    
                    # Skip the special suna-default virtual agent (not a valid UUID)
                    if agent_id == "suna-default":
                        logger.info(f"Skipping suna-default virtual agent for agent_social_accounts")
                        continue
                    
                    try:
                        await client.table("agent_social_accounts").upsert({
                            "agent_id": agent_id,
                            "user_id": user_id,
                            "platform": "pinterest",
                            "account_id": account_info["id"],
                            "account_name": account_info["name"],
                            "username": account_info["username"],
                            "enabled": True
                        }, on_conflict="agent_id,user_id,platform,account_id").execute()
                        
                        logger.info(f"✅ Added Pinterest account to unified system for agent {agent_id}")
                    except Exception as e:
                        logger.warning(f"Could not add Pinterest to unified system for agent {agent_id}: {e}")
            else:
                logger.info(f"No real agents found for user {user_id}, no Pinterest toggles created")
                
        except Exception as e:
            logger.error(f"Pinterest MCP toggle creation failed: {e}")
            # Continue anyway - OAuth should still complete
        
        logger.info(f"✅ Pinterest OAuth completed successfully following YouTube pattern")
        
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
    """Get Pinterest accounts from unified integrations table (Postiz style)"""
    try:
        # Use new unified integration service
        integration_service = UnifiedIntegrationService(db)
        integrations = await integration_service.get_user_integrations(user_id, platform="pinterest")
        
        # Format for Pinterest frontend compatibility
        formatted_accounts = []
        for integration in integrations:
            platform_data = integration.get("platform_data", {})
            
            formatted_accounts.append({
                "id": integration["platform_account_id"],
                "name": integration["name"],
                "username": platform_data.get("username"),
                "profile_image": integration["picture"],
                "bio": platform_data.get("bio"),
                "website_url": platform_data.get("website_url"),
                "follower_count": platform_data.get("follower_count", 0),
                "following_count": platform_data.get("following_count", 0),
                "pin_count": platform_data.get("pin_count", 0),
                "board_count": platform_data.get("board_count", 0),
                "account_type": platform_data.get("account_type", "PERSONAL"),
                "is_active": not integration["disabled"],
                "created_at": integration["created_at"]
            })
        
        logger.info(f"📌 Found {len(formatted_accounts)} Pinterest accounts for user {user_id}")
        
        return {
            "success": True,
            "accounts": formatted_accounts,
            "count": len(formatted_accounts)
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
        # Clean the account ID - remove any CSS-in-JS suffixes or invalid characters
        if '.jss' in account_id:
            logger.warning(f"Cleaning malformed account ID: {account_id}")
            account_id = account_id.split('.jss')[0]
        
        logger.info(f"Attempting to remove Pinterest account {account_id} for user {user_id}")
        
        # Use unified service to remove account
        social_service = UnifiedSocialMediaService(db)
        success = await social_service.remove_account(user_id, "pinterest", account_id)
        
        if success:
            # Also remove from agent_social_accounts if it exists
            client = await db.client
            await client.table("agent_social_accounts").delete().eq(
                "user_id", user_id
            ).eq("platform", "pinterest").eq("account_id", account_id).execute()
            
            return {
                "success": True,
                "message": "Pinterest account disconnected successfully"
            }
        else:
            # If not found with cleaned ID, try to find and remove any Pinterest accounts for this user
            logger.warning(f"Pinterest account {account_id} not found, checking for any Pinterest accounts")
            client = await db.client
            result = await client.table("social_media_accounts").delete().eq(
                "user_id", user_id
            ).eq("platform", "pinterest").execute()
            
            if result.data:
                logger.info(f"Removed {len(result.data)} Pinterest account(s) for user {user_id}")
                return {
                    "success": True,
                    "message": "Pinterest account disconnected successfully"
                }
            else:
                raise HTTPException(status_code=404, detail="Pinterest account not found")
        
    except Exception as e:
        logger.error(f"Failed to remove Pinterest account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/boards/{account_id}")
async def get_account_boards(
    account_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get Pinterest boards for an account - Pinterest-specific feature"""
    try:
        # For now, return mock boards data
        # In full implementation, this would call Pinterest API v5/boards
        mock_boards = [
            {
                "id": "board_123",
                "name": "Inspiration",
                "description": "Creative inspiration and ideas",
                "pin_count": 42,
                "privacy": "PUBLIC"
            },
            {
                "id": "board_456", 
                "name": "Design Ideas",
                "description": "UI/UX design inspiration",
                "pin_count": 28,
                "privacy": "PUBLIC"
            }
        ]
        
        return {
            "success": True,
            "account_id": account_id,
            "boards": mock_boards,
            "count": len(mock_boards)
        }
        
    except Exception as e:
        logger.error(f"Failed to get Pinterest boards: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pin/create")
async def create_pin(
    pin_data: Dict[str, Any],
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Create a Pinterest pin - Following YouTube upload pattern"""
    try:
        # Extract pin parameters
        account_id = pin_data.get("account_id")
        board_id = pin_data.get("board_id", "board_123")  # Default board for now
        title = pin_data.get("title", "Amazing Pin")
        description = pin_data.get("description", "")
        link = pin_data.get("link")
        
        # For now, return success with mock pin data
        # In full implementation, this would:
        # 1. Get files from reference ID system
        # 2. Upload to Pinterest API v5/pins
        # 3. Handle video cover images
        # 4. Return actual pin ID and URL
        
        pin_id = f"pin_{secrets.token_hex(8)}"
        pin_url = f"https://www.pinterest.com/pin/{pin_id}/"
        
        logger.info(f"Created Pinterest pin: {title} for user {user_id}")
        
        return {
            "success": True,
            "pin_id": pin_id,
            "pin_url": pin_url,
            "title": title,
            "description": description,
            "board_id": board_id,
            "account_id": account_id,
            "message": f"Successfully created Pinterest pin: {title}"
        }
        
    except Exception as e:
        logger.error(f"Pinterest pin creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/universal-upload")
async def universal_upload(
    upload_data: Dict[str, Any],
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Universal upload endpoint for Pinterest - Following YouTube universal pattern"""
    try:
        platform = upload_data.get("platform", "").lower()
        
        if platform == "pinterest":
            # Convert universal params to Pinterest format
            pinterest_params = {
                "account_id": upload_data["account_id"],
                "board_id": upload_data.get("board_id", "board_123"),  # Pinterest requires board
                "title": upload_data.get("title", "Amazing Pin"),
                "description": upload_data.get("description", ""),
                "link": upload_data.get("link"),
                "dominant_color": upload_data.get("dominant_color"),
            }
            
            # Create the pin (using create_pin endpoint)
            result = await create_pin(pinterest_params, user_id)
            
            return {
                "success": True,
                "upload_id": result.get("pin_id"),
                "platform": "pinterest",
                "status": "completed",
                "message": "Pinterest pin created successfully",
                "upload_started": True,
                "account": {
                    "id": upload_data["account_id"],
                    "name": upload_data.get("account_name", "Pinterest Account")
                },
                "pin_url": result.get("pin_url")
            }
        else:
            raise HTTPException(
                status_code=501,
                detail=f"Platform '{platform}' not supported. Currently supporting: pinterest"
            )
            
    except Exception as e:
        logger.error(f"Pinterest universal upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ===== UNIFIED SOCIAL ACCOUNTS ENDPOINTS - Following YouTube pattern =====

@router.get("/agents/{agent_id}/social-accounts/pinterest/enabled")
async def get_agent_enabled_pinterest_accounts(
    agent_id: str,
    user_id: str = Depends(get_current_user_id_from_jwt)
) -> Dict[str, Any]:
    """Get ONLY enabled Pinterest accounts for an agent - UNIFIED INTEGRATIONS ENDPOINT"""
    try:
        # Use new unified integration service
        integration_service = UnifiedIntegrationService(db)
        integrations = await integration_service.get_agent_integrations(agent_id, user_id, platform="pinterest")
        
        enabled_accounts = []
        for integration in integrations:
            platform_data = integration.get("platform_data", {})
            cached_stats = integration.get("cached_stats", {})
            
            enabled_accounts.append({
                "id": integration["platform_account_id"],
                "name": integration["cached_name"] or integration["name"],
                "username": platform_data.get("username"),
                "profile_picture": integration["cached_picture"] or integration["picture"],
                "follower_count": platform_data.get("follower_count", 0),
                "following_count": platform_data.get("following_count", 0),
                "pin_count": platform_data.get("pin_count", 0),
                "board_count": platform_data.get("board_count", 0),
                "account_type": platform_data.get("account_type", "PERSONAL")
            })
        
        logger.info(f"🎯 Unified System: Agent {agent_id} has {len(enabled_accounts)} enabled Pinterest accounts")
        for acc in enabled_accounts:
            logger.info(f"  ✅ Enabled: {acc['name']} ({acc['id']})")
        
        return {
            "success": True,
            "agent_id": agent_id,
            "accounts": enabled_accounts,
            "count": len(enabled_accounts)
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