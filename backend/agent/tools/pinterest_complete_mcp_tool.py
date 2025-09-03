"""Pinterest Complete MCP Tool - Native Pinterest Integration"""

from typing import Dict, Any, List, Optional
import asyncio
import aiohttp

from agentpress.tool import Tool, openapi_schema, usage_example, ToolResult
from services.supabase import get_db_connection
from pinterest_mcp.oauth import PinterestOAuthHandler
from pinterest_mcp.accounts import PinterestAccountService
from pinterest_mcp.upload import PinterestUploadService
from utils.logger import logger


class PinterestCompleteMCPTool(Tool):
    """Complete Pinterest integration with zero-questions protocol"""
    
    def __init__(self, user_id: str, pinterest_accounts: List[Dict[str, Any]] = None):
        super().__init__()
        self.user_id = user_id
        self.pinterest_accounts = pinterest_accounts or []
        self.db = get_db_connection()
        self.oauth_handler = PinterestOAuthHandler(self.db)
        self.account_service = PinterestAccountService(self.db)
        self.upload_service = PinterestUploadService(self.db)
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "pinterest_authenticate",
            "description": "Connect your Pinterest account - shows OAuth button to authorize pin creation",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    })
    @usage_example("""
    <function_calls>
    <invoke name="pinterest_authenticate">
    </invoke>
    </function_calls>
    """)
    async def pinterest_authenticate(self) -> ToolResult:
        """Zero-questions OAuth initiation"""
        try:
            # Check if already connected
            existing_accounts = await self.account_service.get_user_accounts(self.user_id)
            
            if existing_accounts:
                return self.success_response({
                    "message": f"Already connected to {len(existing_accounts)} Pinterest account(s)",
                    "accounts": existing_accounts,
                    "status": "already_connected"
                })
            
            # Initiate OAuth flow
            oauth_result = await self.oauth_handler.initiate_auth(self.user_id)
            
            return self.success_response({
                "message": "Click the button below to connect your Pinterest account",
                "oauth_url": oauth_result["auth_url"],
                "auth_required": True,
                "provider": "pinterest",
                "platform": "pinterest"
            })
            
        except Exception as e:
            logger.error(f"Pinterest authentication failed: {e}")
            return self.fail_response(f"Authentication failed: {str(e)}")
    
    @openapi_schema({
        "type": "function", 
        "function": {
            "name": "pinterest_accounts",
            "description": "List connected Pinterest accounts with pin and board statistics",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    })
    @usage_example("""
    <function_calls>
    <invoke name="pinterest_accounts">
    </invoke>
    </function_calls>
    """)
    async def pinterest_accounts(self) -> ToolResult:
        """List connected Pinterest accounts"""
        try:
            accounts = await self.account_service.get_user_accounts(self.user_id)
            
            if not accounts:
                return self.success_response({
                    "message": "No Pinterest accounts connected. Use pinterest_authenticate() to connect your account.",
                    "accounts": [],
                    "count": 0
                })
            
            # Format accounts with Pinterest-specific context
            formatted_accounts = []
            for account in accounts:
                formatted_account = {
                    "id": account["id"],
                    "username": account["username"],
                    "name": account["name"],
                    "profile_image_url": account["profile_image_url"],
                    "website_url": account["website_url"],
                    "about": account["about"],
                    "pin_count": account["pin_count"],
                    "board_count": account["board_count"],
                    "follower_count": account["follower_count"],
                    "following_count": account["following_count"],
                    "account_type": account["account_type"],
                    "token_status": account["token_status"],
                    "platform": "pinterest",
                    "connected_at": account["created_at"]
                }
                
                formatted_accounts.append(formatted_account)
            
            return self.success_response({
                "message": f"Found {len(formatted_accounts)} connected Pinterest account(s)",
                "accounts": formatted_accounts,
                "count": len(formatted_accounts),
                "platform": "pinterest"
            })
            
        except Exception as e:
            logger.error(f"Failed to get Pinterest accounts: {e}")
            return self.fail_response(f"Failed to retrieve accounts: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "pinterest_create_pin",
            "description": "Create a Pinterest pin with intelligent auto-discovery of uploaded images/videos",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Pin title (required)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Pin description (optional)"
                    },
                    "board_id": {
                        "type": "string",
                        "description": "Pinterest board ID to pin to (required)"
                    },
                    "link": {
                        "type": "string",
                        "description": "Optional website URL to link to"
                    },
                    "account_id": {
                        "type": "string",
                        "description": "Pinterest account ID (optional if only one account)"
                    },
                    "video_reference_id": {
                        "type": "string",
                        "description": "Reference ID for video file (optional, auto-discovered if not provided)"
                    },
                    "image_reference_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Reference IDs for image files (optional, auto-discovered if not provided)"
                    },
                    "auto_discover": {
                        "type": "boolean",
                        "description": "Automatically find uploaded files if not specified",
                        "default": True
                    }
                },
                "required": ["title", "board_id"]
            }
        }
    })
    @usage_example("""
    <function_calls>
    <invoke name="pinterest_create_pin">
    <parameter name="title">Beautiful sunset photography</parameter>
    <parameter name="description">Captured this amazing sunset at the beach 📸</parameter>
    <parameter name="board_id">board_123456789</parameter>
    <parameter name="link">https://mywebsite.com/photography</parameter>
    </invoke>
    </function_calls>
    """)
    async def pinterest_create_pin(self, title: str, board_id: str, description: str = "",
                                  link: str = None, account_id: str = None,
                                  video_reference_id: str = None,
                                  image_reference_ids: List[str] = None,
                                  auto_discover: bool = True) -> ToolResult:
        """Zero-questions Pinterest pin creation with auto-discovery"""
        try:
            # Smart account selection
            if not account_id:
                available_accounts = await self.get_available_accounts()
                if len(available_accounts) == 1:
                    account_id = available_accounts[0]["id"]
                elif len(available_accounts) > 1:
                    account_names = [f"{acc['name']} (@{acc['username']})" for acc in available_accounts]
                    return self.fail_response(
                        f"Multiple Pinterest accounts available: {', '.join(account_names)}. "
                        "Please specify account_id parameter."
                    )
                else:
                    return self.fail_response("No Pinterest accounts connected. Use pinterest_authenticate() first.")
            
            # Validate required parameters
            if not title or not title.strip():
                return self.fail_response("Pin title is required and cannot be empty.")
            
            if not board_id or not board_id.strip():
                return self.fail_response("board_id is required. Pinterest pins must be added to a board.")
            
            # Initiate pin creation
            pin_params = {
                "account_id": account_id,
                "title": title,
                "description": description,
                "board_id": board_id,
                "link": link,
                "video_reference_id": video_reference_id,
                "image_reference_ids": image_reference_ids or [],
                "auto_discover": auto_discover
            }
            
            result = await self.upload_service.create_pin(self.user_id, pin_params)
            
            return self.success_response({
                "pin_record_id": result["pin_record_id"],
                "status": result["status"],
                "message": f"Pinterest pin creation started: '{title}'",
                "title": title,
                "board_id": board_id,
                "progress_tracking": True,
                "platform": "pinterest"
            })
            
        except Exception as e:
            logger.error(f"Pinterest pin creation failed: {e}")
            return self.fail_response(f"Pin creation failed: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "pinterest_pin_status",
            "description": "Check the status of a Pinterest pin creation",
            "parameters": {
                "type": "object",
                "properties": {
                    "pin_record_id": {
                        "type": "string",
                        "description": "Pin record ID from pinterest_create_pin"
                    }
                },
                "required": ["pin_record_id"]
            }
        }
    })
    async def pinterest_pin_status(self, pin_record_id: str) -> ToolResult:
        """Get Pinterest pin creation status"""
        try:
            status = await self.upload_service.get_pin_status(self.user_id, pin_record_id)
            
            return self.success_response({
                **status,
                "platform": "pinterest"
            })
            
        except Exception as e:
            logger.error(f"Failed to get Pinterest pin status: {e}")
            return self.fail_response(f"Status check failed: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "pinterest_account_boards",
            "description": "Get boards from a Pinterest account",
            "parameters": {
                "type": "object", 
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Pinterest account ID (optional if only one account)"
                    }
                }
            }
        }
    })
    async def pinterest_account_boards(self, account_id: str = None) -> ToolResult:
        """Get Pinterest boards for account"""
        try:
            # Smart account selection
            if not account_id:
                available_accounts = await self.get_available_accounts()
                if len(available_accounts) == 1:
                    account_id = available_accounts[0]["id"]
                elif len(available_accounts) > 1:
                    account_names = [f"{acc['name']} (@{acc['username']})" for acc in available_accounts]
                    return self.fail_response(
                        f"Multiple accounts available: {', '.join(account_names)}. Please specify account_id."
                    )
                else:
                    return self.fail_response("No Pinterest accounts connected.")
            
            result = await self.upload_service.get_account_boards(self.user_id, account_id)
            
            return self.success_response({
                **result,
                "platform": "pinterest"
            })
            
        except Exception as e:
            logger.error(f"Failed to get Pinterest account boards: {e}")
            return self.fail_response(f"Failed to retrieve boards: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "pinterest_recent_pins",
            "description": "Get recent pins from a Pinterest account",
            "parameters": {
                "type": "object", 
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Pinterest account ID (optional if only one account)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of pins to retrieve",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    }
                }
            }
        }
    })
    async def pinterest_recent_pins(self, account_id: str = None, limit: int = 10) -> ToolResult:
        """Get recent Pinterest pins from account"""
        try:
            # Smart account selection
            if not account_id:
                available_accounts = await self.get_available_accounts()
                if len(available_accounts) == 1:
                    account_id = available_accounts[0]["id"]
                elif len(available_accounts) > 1:
                    account_names = [f"{acc['name']} (@{acc['username']})" for acc in available_accounts]
                    return self.fail_response(
                        f"Multiple accounts available: {', '.join(account_names)}. Please specify account_id."
                    )
                else:
                    return self.fail_response("No Pinterest accounts connected.")
            
            result = await self.upload_service.get_recent_pins(self.user_id, account_id, limit)
            
            return self.success_response({
                **result,
                "platform": "pinterest"
            })
            
        except Exception as e:
            logger.error(f"Failed to get Pinterest recent pins: {e}")
            return self.fail_response(f"Failed to retrieve pins: {str(e)}")
    
    async def get_available_accounts(self) -> List[Dict[str, Any]]:
        """Get available Pinterest accounts for user"""
        try:
            # Use pre-computed accounts if available (from agent config)
            if self.pinterest_accounts:
                return self.pinterest_accounts
            
            # Fallback to database query
            accounts = await self.account_service.get_user_accounts(self.user_id)
            return [acc for acc in accounts if acc.get("token_status") == "valid"]
            
        except Exception as e:
            logger.error(f"Failed to get available Pinterest accounts: {e}")
            return []