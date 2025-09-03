"""LinkedIn Complete MCP Tool - Native LinkedIn Integration"""

from typing import Dict, Any, List, Optional
import asyncio
import aiohttp

from agentpress.tool import Tool, openapi_schema, usage_example, ToolResult
from services.supabase import get_db_connection
from linkedin_mcp.oauth import LinkedInOAuthHandler
from linkedin_mcp.accounts import LinkedInAccountService
from linkedin_mcp.upload import LinkedInUploadService
from utils.logger import logger


class LinkedInCompleteMCPTool(Tool):
    """Complete LinkedIn integration with zero-questions protocol"""
    
    def __init__(self, user_id: str, linkedin_accounts: List[Dict[str, Any]] = None):
        super().__init__()
        self.user_id = user_id
        self.linkedin_accounts = linkedin_accounts or []
        self.db = get_db_connection()
        self.oauth_handler = LinkedInOAuthHandler(self.db)
        self.account_service = LinkedInAccountService(self.db)
        self.upload_service = LinkedInUploadService(self.db)
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "linkedin_authenticate",
            "description": "Connect your LinkedIn account - shows OAuth button to authorize professional posting",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    })
    @usage_example("""
    <function_calls>
    <invoke name="linkedin_authenticate">
    </invoke>
    </function_calls>
    """)
    async def linkedin_authenticate(self) -> ToolResult:
        """Zero-questions OAuth initiation"""
        try:
            # Check if already connected
            existing_accounts = await self.account_service.get_user_accounts(self.user_id)
            
            if existing_accounts:
                return self.success_response({
                    "message": f"Already connected to {len(existing_accounts)} LinkedIn account(s)",
                    "accounts": existing_accounts,
                    "status": "already_connected"
                })
            
            # Initiate OAuth flow
            oauth_result = await self.oauth_handler.initiate_auth(self.user_id)
            
            return self.success_response({
                "message": "Click the button below to connect your LinkedIn account",
                "oauth_url": oauth_result["auth_url"],
                "auth_required": True,
                "provider": "linkedin",
                "platform": "linkedin"
            })
            
        except Exception as e:
            logger.error(f"LinkedIn authentication failed: {e}")
            return self.fail_response(f"Authentication failed: {str(e)}")
    
    @openapi_schema({
        "type": "function", 
        "function": {
            "name": "linkedin_accounts",
            "description": "List connected LinkedIn accounts with professional information",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_analytics": {
                        "type": "boolean",
                        "description": "Include account analytics data",
                        "default": False
                    }
                }
            }
        }
    })
    @usage_example("""
    <function_calls>
    <invoke name="linkedin_accounts">
    </invoke>
    </function_calls>
    """)
    async def linkedin_accounts(self, include_analytics: bool = False) -> ToolResult:
        """List connected LinkedIn accounts"""
        try:
            accounts = await self.account_service.get_user_accounts(self.user_id)
            
            if not accounts:
                return self.success_response({
                    "message": "No LinkedIn accounts connected. Use linkedin_authenticate() to connect your account.",
                    "accounts": [],
                    "count": 0
                })
            
            # Format accounts with professional context
            formatted_accounts = []
            for account in accounts:
                formatted_account = {
                    "id": account["id"],
                    "name": account["name"],
                    "email": account["email"],
                    "profile_image_url": account["profile_image_url"],
                    "token_status": account["token_status"],
                    "platform": "linkedin",
                    "connected_at": account["created_at"]
                }
                
                # Add analytics if requested
                if include_analytics:
                    try:
                        posts = await self.upload_service.get_recent_posts(
                            self.user_id, account["id"], limit=5
                        )
                        formatted_account["recent_posts_count"] = posts.get("count", 0)
                    except Exception as e:
                        logger.warning(f"Failed to get analytics for LinkedIn account {account['id']}: {e}")
                        formatted_account["recent_posts_count"] = 0
                
                formatted_accounts.append(formatted_account)
            
            return self.success_response({
                "message": f"Found {len(formatted_accounts)} connected LinkedIn account(s)",
                "accounts": formatted_accounts,
                "count": len(formatted_accounts),
                "platform": "linkedin"
            })
            
        except Exception as e:
            logger.error(f"Failed to get LinkedIn accounts: {e}")
            return self.fail_response(f"Failed to retrieve accounts: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "linkedin_create_post",
            "description": "Create a LinkedIn post with intelligent auto-discovery of uploaded files",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Post content text (required)"
                    },
                    "visibility": {
                        "type": "string",
                        "description": "Post visibility",
                        "enum": ["PUBLIC", "CONNECTIONS"],
                        "default": "PUBLIC"
                    },
                    "account_id": {
                        "type": "string",
                        "description": "LinkedIn account ID (optional if only one account)"
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
                "required": ["text"]
            }
        }
    })
    @usage_example("""
    <function_calls>
    <invoke name="linkedin_create_post">
    <parameter name="text">Excited to share my latest professional insights! 🚀</parameter>
    <parameter name="visibility">PUBLIC</parameter>
    </invoke>
    </function_calls>
    """)
    async def linkedin_create_post(self, text: str, visibility: str = "PUBLIC",
                                 account_id: str = None, video_reference_id: str = None,
                                 image_reference_ids: List[str] = None,
                                 auto_discover: bool = True) -> ToolResult:
        """Zero-questions LinkedIn post creation with auto-discovery"""
        try:
            # Smart account selection
            if not account_id:
                available_accounts = await self.get_available_accounts()
                if len(available_accounts) == 1:
                    account_id = available_accounts[0]["id"]
                elif len(available_accounts) > 1:
                    account_names = [f"{acc['name']} ({acc['email']})" for acc in available_accounts]
                    return self.fail_response(
                        f"Multiple LinkedIn accounts available: {', '.join(account_names)}. "
                        "Please specify account_id parameter."
                    )
                else:
                    return self.fail_response("No LinkedIn accounts connected. Use linkedin_authenticate() first.")
            
            # Validate post content
            if not text or not text.strip():
                return self.fail_response("Post text is required and cannot be empty.")
            
            # Validate visibility
            if visibility not in ["PUBLIC", "CONNECTIONS"]:
                visibility = "PUBLIC"
            
            # Initiate post creation
            post_params = {
                "account_id": account_id,
                "text": text,
                "visibility": visibility,
                "video_reference_id": video_reference_id,
                "image_reference_ids": image_reference_ids or [],
                "auto_discover": auto_discover
            }
            
            result = await self.upload_service.create_post(self.user_id, post_params)
            
            return self.success_response({
                "post_record_id": result["post_record_id"],
                "status": result["status"],
                "message": f"LinkedIn post creation started for '{account_id}'",
                "text": text,
                "visibility": visibility,
                "progress_tracking": True,
                "platform": "linkedin"
            })
            
        except Exception as e:
            logger.error(f"LinkedIn post creation failed: {e}")
            return self.fail_response(f"Post creation failed: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "linkedin_post_status",
            "description": "Check the status of a LinkedIn post creation",
            "parameters": {
                "type": "object",
                "properties": {
                    "post_record_id": {
                        "type": "string",
                        "description": "Post record ID from linkedin_create_post"
                    }
                },
                "required": ["post_record_id"]
            }
        }
    })
    @usage_example("""
    <function_calls>
    <invoke name="linkedin_post_status">
    <parameter name="post_record_id">uuid-from-create-post</parameter>
    </invoke>
    </function_calls>
    """)
    async def linkedin_post_status(self, post_record_id: str) -> ToolResult:
        """Get LinkedIn post creation status"""
        try:
            status = await self.upload_service.get_post_status(self.user_id, post_record_id)
            
            return self.success_response({
                **status,
                "platform": "linkedin"
            })
            
        except Exception as e:
            logger.error(f"Failed to get LinkedIn post status: {e}")
            return self.fail_response(f"Status check failed: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "linkedin_account_posts",
            "description": "Get recent posts from a LinkedIn account",
            "parameters": {
                "type": "object", 
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "LinkedIn account ID (optional if only one account)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of posts to retrieve",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    }
                }
            }
        }
    })
    @usage_example("""
    <function_calls>
    <invoke name="linkedin_account_posts">
    <parameter name="limit">5</parameter>
    </invoke>
    </function_calls>
    """)
    async def linkedin_account_posts(self, account_id: str = None, limit: int = 10) -> ToolResult:
        """Get recent LinkedIn posts from account"""
        try:
            # Smart account selection
            if not account_id:
                available_accounts = await self.get_available_accounts()
                if len(available_accounts) == 1:
                    account_id = available_accounts[0]["id"]
                elif len(available_accounts) > 1:
                    account_names = [f"{acc['name']} ({acc['email']})" for acc in available_accounts]
                    return self.fail_response(
                        f"Multiple accounts available: {', '.join(account_names)}. Please specify account_id."
                    )
                else:
                    return self.fail_response("No LinkedIn accounts connected.")
            
            result = await self.upload_service.get_recent_posts(self.user_id, account_id, limit)
            
            return self.success_response({
                **result,
                "platform": "linkedin"
            })
            
        except Exception as e:
            logger.error(f"Failed to get LinkedIn account posts: {e}")
            return self.fail_response(f"Failed to retrieve posts: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "linkedin_delete_post",
            "description": "Delete a LinkedIn post",
            "parameters": {
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "LinkedIn post ID to delete"
                    },
                    "account_id": {
                        "type": "string",
                        "description": "LinkedIn account ID (optional if only one account)"
                    }
                },
                "required": ["post_id"]
            }
        }
    })
    @usage_example("""
    <function_calls>
    <invoke name="linkedin_delete_post">
    <parameter name="post_id">urn:li:share:123456789</parameter>
    </invoke>
    </function_calls>
    """)
    async def linkedin_delete_post(self, post_id: str, account_id: str = None) -> ToolResult:
        """Delete a LinkedIn post"""
        try:
            # Smart account selection
            if not account_id:
                available_accounts = await self.get_available_accounts()
                if len(available_accounts) == 1:
                    account_id = available_accounts[0]["id"]
                else:
                    return self.fail_response("Multiple accounts available. Please specify account_id.")
            
            result = await self.upload_service.delete_post(self.user_id, account_id, post_id)
            
            return self.success_response({
                **result,
                "platform": "linkedin"
            })
            
        except Exception as e:
            logger.error(f"Failed to delete LinkedIn post: {e}")
            return self.fail_response(f"Post deletion failed: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "linkedin_post_analytics",
            "description": "Get analytics for a LinkedIn post (likes, comments, shares, impressions)",
            "parameters": {
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "LinkedIn post ID"
                    },
                    "account_id": {
                        "type": "string", 
                        "description": "LinkedIn account ID (optional if only one account)"
                    }
                },
                "required": ["post_id"]
            }
        }
    })
    @usage_example("""
    <function_calls>
    <invoke name="linkedin_post_analytics">
    <parameter name="post_id">urn:li:share:123456789</parameter>
    </invoke>
    </function_calls>
    """)
    async def linkedin_post_analytics(self, post_id: str, account_id: str = None) -> ToolResult:
        """Get LinkedIn post analytics"""
        try:
            # Smart account selection
            if not account_id:
                available_accounts = await self.get_available_accounts()
                if len(available_accounts) == 1:
                    account_id = available_accounts[0]["id"]
                else:
                    return self.fail_response("Multiple accounts available. Please specify account_id.")
            
            result = await self.upload_service.get_post_analytics(self.user_id, account_id, post_id)
            
            return self.success_response({
                **result,
                "platform": "linkedin"
            })
            
        except Exception as e:
            logger.error(f"Failed to get LinkedIn post analytics: {e}")
            return self.fail_response(f"Analytics retrieval failed: {str(e)}")
    
    async def get_available_accounts(self) -> List[Dict[str, Any]]:
        """Get available LinkedIn accounts for user"""
        try:
            # Use pre-computed accounts if available (from agent config)
            if self.linkedin_accounts:
                return self.linkedin_accounts
            
            # Fallback to database query
            accounts = await self.account_service.get_user_accounts(self.user_id)
            return [acc for acc in accounts if acc.get("token_status") == "valid"]
            
        except Exception as e:
            logger.error(f"Failed to get available LinkedIn accounts: {e}")
            return []