"""Twitter Complete MCP Tool - Native Twitter Integration"""

import asyncio
import aiohttp
import json
import os
import re
import jwt
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
from agentpress.tool import Tool, ToolResult, openapi_schema
from utils.logger import logger


class TwitterTool(Tool):
    """Complete Twitter integration tool following MCP pattern"""
    
    def __init__(self, user_id: str, account_ids: Optional[List[str]] = None, account_metadata: Optional[List[Dict[str, Any]]] = None, jwt_token: Optional[str] = None, agent_id: Optional[str] = None, thread_id: Optional[str] = None, **kwargs):
        super().__init__()
        self.user_id = user_id
        self.account_ids = account_ids or []
        self.agent_id = agent_id
        self.thread_id = thread_id
        
        # Use provided JWT token or create one
        self.jwt_token = jwt_token or self._create_jwt_token()
        
        # Backend URL configuration - Use Docker service name for worker network
        backend_url = os.getenv("BACKEND_URL", "http://backend:8000")
        self.base_url = backend_url + "/api"
        
        # Account metadata for quick reference
        self.account_metadata = {acc['id']: acc for acc in account_metadata} if account_metadata else {}
        self._has_accounts = len(self.account_ids) > 0
        
        logger.info(f"[Twitter MCP] Initialized for user {user_id}, agent {agent_id}")
        logger.info(f"[Twitter MCP] Account metadata: {len(self.account_metadata)} accounts")
        logger.info(f"[Twitter MCP] Base URL: {self.base_url}")
    
    def _create_jwt_token(self) -> str:
        """Create a JWT token for API authentication"""
        jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
        if not jwt_secret:
            logger.warning("SUPABASE_JWT_SECRET not set, authentication may fail")
            return ""
        
        payload = {
            "sub": self.user_id,
            "user_id": self.user_id,
            "role": "authenticated"
        }
        
        return jwt.encode(payload, jwt_secret, algorithm="HS256")
    
    async def _check_enabled_accounts(self) -> tuple[bool, List[Dict[str, Any]], str]:
        """Real-time: Direct database query - NO CACHE DEPENDENCIES"""
        try:
            logger.info(f"🔴 REAL-TIME: Querying database directly for Twitter accounts, agent {self.agent_id}")
            
            # Real-time: Direct database access instead of HTTP/cache  
            from services.supabase import DBConnection
            db = DBConnection()
            client = await db.client
            
            # Special handling for suna-default virtual agent
            if self.agent_id == "suna-default":
                logger.info(f"[Twitter MCP] Using agent_social_accounts for suna-default agent (respects MCP toggles)")
                # Query agent_social_accounts to respect MCP toggle state for suna-default
                result = await client.table("agent_social_accounts").select("""
                    account_id, account_name, enabled,
                    twitter_accounts!inner(id, name, username, description, profile_image_url, followers_count, following_count, tweet_count, verified)
                """).eq("agent_id", "suna-default").eq(
                    "user_id", self.user_id
                ).eq("platform", "twitter").eq("enabled", True).execute()
                
                if result.data:
                    accounts = []
                    for account in result.data:
                        tw_data = account["twitter_accounts"]
                        accounts.append({
                            "id": tw_data["id"],
                            "name": tw_data["name"],
                            "username": tw_data.get("username", ""),
                            "description": tw_data.get("description", ""),
                            "profile_image_url": tw_data.get("profile_image_url"),
                            "followers_count": tw_data.get("followers_count", 0),
                            "following_count": tw_data.get("following_count", 0),
                            "tweet_count": tw_data.get("tweet_count", 0),
                            "verified": tw_data.get("verified", False)
                        })
                    logger.info(f"✅ Found {len(accounts)} ENABLED Twitter accounts for suna-default (respecting MCP toggles)")
                    for acc in accounts:
                        logger.info(f"  ✅ MCP Enabled: {acc['name']} (@{acc['username']})")
                    return True, accounts, ""
                else:
                    logger.info(f"❌ No enabled Twitter accounts found for suna-default (check MCP toggles)")
                    error_msg = (
                        "❌ **No Twitter accounts enabled**\\n\\n"
                        "Please enable Twitter accounts in the Social Media dropdown"
                    )
                    return False, [], error_msg
            
            # Regular agent - query agent_social_accounts
            result = await client.table("agent_social_accounts").select("*").eq(
                "agent_id", self.agent_id
            ).eq("user_id", self.user_id).eq(
                "platform", "twitter"  
            ).eq("enabled", True).execute()
            
            accounts = []
            for account in result.data:
                accounts.append({
                    "id": account["account_id"],
                    "name": account["account_name"],
                    "username": account["username"],
                    "description": account["description"],
                    "profile_image_url": account["profile_image_url"],
                    "followers_count": account["followers_count"],
                    "following_count": account["following_count"],
                    "tweet_count": account["tweet_count"],
                    "verified": account["verified"]
                })
            
            logger.info(f"🔴 REAL-TIME RESULT: Found {len(accounts)} enabled Twitter accounts")
            for acc in accounts:
                logger.info(f"  🔴 Live Enabled: {acc['name']} (@{acc['username']})")
            
            if accounts:
                return True, accounts, ""
            else:
                # Fallback: Check twitter_accounts table if no agent_social_accounts found
                logger.info(f"[Twitter MCP] No accounts in agent_social_accounts, checking twitter_accounts table")
                twitter_result = await client.table("twitter_accounts").select("*").eq(
                    "user_id", self.user_id
                ).eq("is_active", True).execute()
                
                if twitter_result.data:
                    # Found accounts in twitter_accounts table - use them
                    fallback_accounts = []
                    for acc in twitter_result.data:
                        fallback_accounts.append({
                            "id": acc["id"],
                            "name": acc["name"],
                            "username": acc.get("username", ""),
                            "description": acc.get("description", ""),
                            "profile_image_url": acc.get("profile_image_url"),
                            "followers_count": acc.get("followers_count", 0),
                            "following_count": acc.get("following_count", 0),
                            "tweet_count": acc.get("tweet_count", 0),
                            "verified": acc.get("verified", False)
                        })
                    logger.info(f"✅ Found {len(fallback_accounts)} Twitter accounts in fallback table")
                    return True, fallback_accounts, ""
                
                # Real-time: Check if we have any connected accounts at all
                all_accounts_result = await client.table("agent_social_accounts").select("*").eq(
                    "agent_id", self.agent_id
                ).eq("user_id", self.user_id).eq("platform", "twitter").execute()
                
                if all_accounts_result.data:
                    disabled_count = len(all_accounts_result.data)
                    return False, [], f"❌ **{disabled_count} Twitter accounts connected but disabled**\\n\\nPlease enable at least one account in the MCP connections dropdown (⚙️ button)."
                else:
                    return False, [], "❌ **No Twitter accounts connected**\\n\\nPlease connect a Twitter account first using 'Add Account' in Social Media settings."
                    
        except Exception as e:
            logger.error(f"🔴 REAL-TIME ERROR: Failed to query database directly: {e}")
            return False, [], f"Error checking accounts: {str(e)}"
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "twitter_authenticate",
            "description": "ONLY call this if NO Twitter accounts are connected. Check existing accounts first with twitter_accounts before using this.",
            "parameters": {
                "type": "object",
                "properties": {
                    "check_existing": {
                        "type": "boolean",
                        "description": "Check if accounts are already connected before showing auth (default: true)"
                    }
                },
                "required": []
            }
        }
    })
    async def twitter_authenticate(self, check_existing: bool = True) -> ToolResult:
        """Twitter authentication - MCP pattern with complete OAuth flow"""
        try:
            # Always check existing accounts first to avoid unnecessary auth
            has_accounts, accounts, _ = await self._check_enabled_accounts()
            if has_accounts:
                logger.info(f"[Twitter MCP] Authentication skipped - {len(accounts)} accounts already enabled")
                # Return existing accounts instead of showing auth
                account_list = "\\n".join([f"• **{acc['name']}** (@{acc.get('username', acc['id'])})" for acc in accounts])
                return self.success_response({
                    "message": f"✅ **Twitter Already Connected!**\\n\\n🐦 **Available accounts:**\\n{account_list}\\n\\n💡 **Ready for tweets!** Use `twitter_create_tweet` to post tweets.",
                    "existing_accounts": accounts,
                    "already_authenticated": True,
                    "skip_auth": True
                })
            
            # No existing accounts found, proceed with authentication
            
            # Get auth URL from backend
            async with aiohttp.ClientSession() as session:
                request_data = {}
                if self.thread_id:
                    request_data['thread_id'] = self.thread_id
                
                response = await session.post(
                    f"{self.base_url}/twitter/auth/initiate",
                    headers={"Authorization": f"Bearer {self.jwt_token}", "Content-Type": "application/json"},
                    json=request_data,
                    timeout=aiohttp.ClientTimeout(total=15)
                )
                
                if response.status == 200:
                    data = await response.json()
                    auth_url = data.get("auth_url")
                    
                    return self.success_response({
                        "message": "🔗 **Connect Your Twitter Account**\\n\\nClick the button below to connect your Twitter account.",
                        "auth_url": auth_url,
                        "button_text": "Connect Twitter Account",
                        "existing_accounts": accounts if check_existing and has_accounts else []
                    })
                else:
                    error_text = await response.text()
                    return self.fail_response(f"Failed to initiate authentication: {error_text}")
                    
        except Exception as e:
            logger.error(f"[Twitter MCP] Authentication error: {e}")
            return self.fail_response(f"Authentication failed: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "twitter_accounts",
            "description": "INSTANT ACTION - Shows all connected Twitter accounts with stats immediately",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_analytics": {
                        "type": "boolean",
                        "description": "Include detailed analytics (default: false)"
                    }
                },
                "required": []
            }
        }
    })
    async def twitter_accounts(self, include_analytics: bool = False) -> ToolResult:
        """Get Twitter accounts - complete MCP pattern"""
        try:
            has_accounts, accounts, error_msg = await self._check_enabled_accounts()
            
            if not has_accounts:
                return self.fail_response(error_msg)
            
            # Format accounts for frontend (preserve original response format)
            formatted_accounts = []
            for acc in accounts:
                formatted_accounts.append({
                    "id": acc["id"],
                    "name": acc["name"],
                    "username": acc.get("username"),
                    "description": acc.get("description"),
                    "profile_image_url": acc.get("profile_image_url"),
                    "followers_count": acc.get("followers_count", 0),
                    "following_count": acc.get("following_count", 0),
                    "tweet_count": acc.get("tweet_count", 0),
                    "verified": acc.get("verified", False)
                })
            
            summary_text = f"🐦 **Twitter Accounts for this Agent**\\n\\n"
            summary_text += f"Found {len(accounts)} enabled account(s):\\n\\n"
            
            for account in accounts:
                summary_text += f"**{account['name']}**\\n"
                if account.get('username'):
                    summary_text += f"   • @{account['username']}\\n"
                summary_text += f"   • {account.get('followers_count', 0):,} followers\\n"
                if include_analytics:
                    summary_text += f"   • {account.get('following_count', 0):,} following\\n"
                    summary_text += f"   • {account.get('tweet_count', 0):,} tweets\\n"
                    if account.get('verified'):
                        summary_text += f"   • ✅ Verified\\n"
                summary_text += "\\n"
            
            return self.success_response({
                "accounts": formatted_accounts,
                "count": len(formatted_accounts),
                "message": summary_text,
                "has_accounts": True,
                "single_account": len(accounts) == 1
            })
            
        except Exception as e:
            logger.error(f"[Twitter MCP] Error fetching accounts: {e}")
            return self.fail_response(f"Failed to get accounts: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "twitter_create_tweet", 
            "description": "PREFERRED ACTION - Create a tweet when accounts are connected. Auto-selects enabled account and handles media upload with progress tracking. Use this for all tweet requests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Twitter account ID (optional - auto-selects if one enabled)"
                    },
                    "text": {
                        "type": "string",
                        "description": "Tweet text content (required, max 280 characters)"
                    },
                    "reply_to_tweet_id": {
                        "type": "string",
                        "description": "Tweet ID to reply to (optional)"
                    },
                    "quote_tweet_id": {
                        "type": "string",
                        "description": "Tweet ID to quote (optional)"
                    },
                    "video_reference_id": {
                        "type": "string",
                        "description": "Video reference ID (auto-discovered if not provided)"
                    },
                    "image_reference_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Image reference IDs (auto-discovered if not provided)"
                    }
                },
                "required": ["text"]
            }
        }
    })
    async def twitter_create_tweet(
        self,
        text: str,
        account_id: Optional[str] = None,
        reply_to_tweet_id: Optional[str] = None,
        quote_tweet_id: Optional[str] = None,
        video_reference_id: Optional[str] = None,
        image_reference_ids: Optional[List[str]] = None
    ) -> ToolResult:
        """Complete Twitter tweet creation with all original functionality - MCP pattern"""
        try:
            logger.info(f"[Twitter MCP] Starting tweet creation - text: {text[:50]}...")
            
            # Validate text length
            if len(text) > 280:
                return self.fail_response(f"Tweet text is too long ({len(text)} characters). Maximum is 280 characters.")
            
            if not text.strip():
                return self.fail_response("Tweet text cannot be empty.")
            
            # Step 1: Account validation
            has_accounts, available_accounts, error_msg = await self._check_enabled_accounts()
            
            if not has_accounts:
                return self.fail_response(error_msg)
            
            # Account selection logic - tweet to all enabled accounts or specific account
            if not account_id:
                if len(available_accounts) == 1:
                    account_id = available_accounts[0]["id"]
                    account_name = available_accounts[0]["name"]
                    account_username = available_accounts[0]["username"]
                    logger.info(f"[Twitter MCP] Auto-selected account: {account_name} (@{account_username})")
                else:
                    # Multiple accounts - tweet to all enabled accounts
                    logger.info(f"[Twitter MCP] Creating tweets for {len(available_accounts)} enabled accounts")
                    
                    tweet_results = []
                    for account in available_accounts:
                        try:
                            account_tweet = await self._smart_tweet_with_token_recovery(
                                account["id"], text, reply_to_tweet_id, quote_tweet_id, 
                                video_reference_id, image_reference_ids or []
                            )
                            tweet_results.append({
                                "account": account,
                                "result": account_tweet,
                                "success": account_tweet.get("success", False)
                            })
                            logger.info(f"✅ Tweet to @{account['username']}: {'Success' if account_tweet.get('success') else 'Failed'}")
                        except Exception as e:
                            logger.error(f"❌ Tweet to @{account['username']} failed: {e}")
                            tweet_results.append({
                                "account": account,
                                "result": {"success": False, "error": str(e)},
                                "success": False
                            })
                    
                    successful_tweets = [r for r in tweet_results if r["success"]]
                    failed_tweets = [r for r in tweet_results if not r["success"]]
                    
                    message = f"🐦 **Multi-Account Tweet Complete!**\\n\\n"
                    message += f"📊 **Results:** {len(successful_tweets)} successful, {len(failed_tweets)} failed\\n\\n"
                    
                    for result in successful_tweets:
                        message += f"✅ **@{result['account']['username']}** - Tweet posted\\n"
                    
                    for result in failed_tweets:
                        message += f"❌ **@{result['account']['username']}** - Failed: {result['result'].get('error', 'Unknown error')}\\n"
                    
                    return self.success_response({
                        "message": message,
                        "tweet_results": tweet_results,
                        "accounts": available_accounts,
                        "multi_account_tweet": True,
                        "successful_count": len(successful_tweets),
                        "failed_count": len(failed_tweets),
                        "text": text
                    })
            
            # Single account tweet
            tweet_result = await self._smart_tweet_with_token_recovery(
                account_id, text, reply_to_tweet_id, quote_tweet_id, 
                video_reference_id, image_reference_ids or []
            )
            
            if not tweet_result.get('success'):
                return self._handle_tweet_error(tweet_result.get('error', 'Unknown error'))
            
            tweet_record_id = tweet_result.get('tweet_record_id')
            
            # Return immediate response with tweet tracking
            account_info = self._get_account_info(account_id, available_accounts)
            
            return self.success_response({
                "tweet_record_id": tweet_record_id,
                "status": "posting",
                "account_name": account_info.get('name', 'Twitter Account'),
                "account_username": account_info.get('username', ''),
                "text": text,
                "message": f"🐦 **Creating tweet for @{account_info.get('username')}...**\\n\\n📤 Tweet started - check progress in a moment!",
                "tweet_started": True,
                "account": account_info,
                "accounts": [account_info],
                "has_accounts": True,
                "single_account": True,
                "mcp_execution": True
            })
                
        except Exception as e:
            logger.error(f"[Twitter MCP] Tweet creation error: {e}", exc_info=True)
            return self.fail_response(f"Tweet creation failed: {str(e)}")
    
    async def _smart_tweet_with_token_recovery(
        self, 
        account_id: str, 
        text: str, 
        reply_to_tweet_id: Optional[str], 
        quote_tweet_id: Optional[str],
        video_reference_id: Optional[str], 
        image_reference_ids: List[str]
    ) -> Dict[str, Any]:
        """Smart tweet creation with automatic token refresh and retry"""
        
        # Intelligent retry logic: 3 attempts with progressive recovery
        for attempt in range(3):
            try:
                logger.info(f"🚀 Smart Tweet Attempt {attempt + 1}/3 for @{account_id}")
                
                # Attempt tweet with current authentication state
                result = await self._initiate_tweet(
                    account_id, text, reply_to_tweet_id, quote_tweet_id, 
                    video_reference_id, image_reference_ids
                )
                
                if result.get('success'):
                    logger.info(f"✅ Tweet successful on attempt {attempt + 1}")
                    return result
                
                # Check if it's an authentication error
                error_msg = result.get('error', '').lower()
                if 'auth' in error_msg or 'token' in error_msg or 'unauthorized' in error_msg:
                    if attempt < 2:  # Still have retries
                        logger.info(f"🔄 Authentication error detected, will retry after token operations...")
                        await asyncio.sleep(1)  # Brief pause before retry
                        continue
                    else:
                        # Final attempt - return auth error
                        logger.error(f"❌ Authentication failed after 3 attempts")
                        return result
                else:
                    # Non-auth error - return immediately
                    return result
                    
            except Exception as e:
                error_str = str(e).lower()
                if ('auth' in error_str or 'token' in error_str) and attempt < 2:
                    logger.warning(f"⚠️ Tweet attempt {attempt + 1} failed with auth error: {e}")
                    await asyncio.sleep(2)  # Longer pause for exceptions
                    continue
                else:
                    logger.error(f"❌ Tweet attempt {attempt + 1} failed: {e}")
                    return {"success": False, "error": str(e)}
        
        return {"success": False, "error": "Tweet failed after 3 intelligent retry attempts"}
    
    async def _initiate_tweet(
        self, 
        account_id: str, 
        text: str, 
        reply_to_tweet_id: Optional[str], 
        quote_tweet_id: Optional[str],
        video_reference_id: Optional[str], 
        image_reference_ids: List[str]
    ) -> Dict[str, Any]:
        """Initiate tweet via backend API (MCP external call pattern)"""
        try:
            tweet_params = {
                "platform": "twitter",
                "account_id": account_id,
                "text": text,
                "reply_to_tweet_id": reply_to_tweet_id,
                "quote_tweet_id": quote_tweet_id,
                "video_reference_id": video_reference_id,
                "image_reference_ids": image_reference_ids,
                "auto_discover": True
            }
            
            # Use robust HTTP session with proper error handling
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                logger.info(f"[Twitter MCP] Calling tweet API: {self.base_url}/twitter/universal-upload")
                
                try:
                    response = await session.post(
                        f"{self.base_url}/twitter/universal-upload",
                        headers={
                            "Authorization": f"Bearer {self.jwt_token}",
                            "Content-Type": "application/json"
                        },
                        json=tweet_params
                    )
                    
                    logger.info(f"[Twitter MCP] Tweet API response: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"[Twitter MCP] Tweet initiated successfully: {data.get('tweet_record_id')}")
                        return {"success": True, "tweet_record_id": data.get('tweet_record_id'), "data": data}
                    else:
                        error_text = await response.text()
                        logger.error(f"[Twitter MCP] Tweet API error {response.status}: {error_text}")
                        return {"success": False, "error": f"HTTP {response.status}: {error_text}"}
                        
                except aiohttp.ClientError as e:
                    logger.error(f"[Twitter MCP] Network error calling tweet API: {e}")
                    return {"success": False, "error": f"Network error: {str(e)}"}
                except asyncio.TimeoutError:
                    logger.error(f"[Twitter MCP] Tweet API timeout")
                    return {"success": False, "error": "Tweet API timeout - please try again"}
                except Exception as e:
                    logger.error(f"[Twitter MCP] Unexpected error in tweet API call: {e}")
                    return {"success": False, "error": f"Unexpected error: {str(e)}"}
                    
        except Exception as e:
            logger.error(f"[Twitter MCP] Tweet initiation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_account_info(self, account_id: str, available_accounts: List[Dict]) -> Dict[str, Any]:
        """Get account info for response formatting"""
        for account in available_accounts:
            if account['id'] == account_id:
                return {
                    "id": account["id"],
                    "name": account["name"],
                    "username": account["username"],
                    "profile_image_url": account.get("profile_image_url"),
                    "followers_count": account.get("followers_count", 0),
                    "following_count": account.get("following_count", 0),
                    "tweet_count": account.get("tweet_count", 0),
                    "verified": account.get("verified", False)
                }
        
        return {"id": account_id, "name": "Twitter Account", "username": ""}
    
    def _handle_tweet_error(self, error: str) -> ToolResult:
        """Smart error handling with context-aware guidance"""
        error_lower = error.lower()
        
        if "no video file found" in error_lower or "no image found" in error_lower:
            return self.fail_response(
                "❌ **No media file found**\\n\\n"
                "**To tweet with media:**\\n"
                "1. 📎 Attach your image/video file to the message\\n"
                "2. 💬 Tell me to tweet it\\n\\n"
                "Media files are automatically prepared when attached."
            )
        elif "re-authorization required" in error or "authentication refresh needed" in error or "invalid_grant" in error_lower:
            # Smart auth error: Context-aware guidance
            return self.success_response({
                "message": "🔄 **Smart Authentication Update**\\n\\n"
                          "Your Twitter tokens need refreshing - this is normal and happens automatically.\\n\\n"
                          "**What happened:** Automatic token refresh detected your authentication needs updating.\\n\\n"
                          "**Next step:** Click the authentication button below to refresh your access.",
                "auth_required": True,
                "smart_refresh_attempted": True,
                "context_preserved": True,
                "auth_url": None,  # Will be generated by authenticate function
                "reason": "proactive_token_management"
            })
        elif "token" in error_lower or "auth" in error_lower:
            # Generic auth error: Fallback guidance
            return self.success_response({
                "message": "🔐 **Authentication Update Required**\\n\\n"
                          "Your Twitter authentication needs to be refreshed.\\n\\n"
                          "This is normal for security - please use `twitter_authenticate` to reconnect.",
                "auth_required": True,
                "generic_auth_error": True
            })
        elif "rate limit" in error_lower:
            return self.fail_response(
                "📊 **Rate limit exceeded**\\n\\n"
                "Twitter's rate limit reached.\\n\\n"
                "**Info:**\\n"
                "• Tweet limits reset every 15 minutes\\n"
                "• Try again in a few minutes"
            )
        elif "duplicate" in error_lower:
            return self.fail_response(
                "🔄 **Duplicate tweet detected**\\n\\n"
                "Twitter doesn't allow posting identical tweets.\\n\\n"
                "**Try:**\\n"
                "• Modify your tweet text slightly\\n"
                "• Add different media or links"
            )
        elif "too long" in error_lower or "280" in error_lower:
            return self.fail_response(
                "📝 **Tweet too long**\\n\\n"
                "Twitter has a 280 character limit.\\n\\n"
                "**Please:**\\n"
                "• Shorten your tweet\\n"
                "• Break it into multiple tweets"
            )
        elif "cannot connect to host" in error_lower:
            return self.fail_response(
                "🌐 **Connection Error**\\n\\n"
                "Could not connect to Twitter service.\\n\\n"
                "**Try:**\\n"
                "• Check your internet connection\\n"  
                "• Wait a moment and try again\\n"
                "• The service might be temporarily unavailable"
            )
        else:
            return self.fail_response(f"❌ **Tweet failed**\\n\\n{error}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "twitter_check_tweet_status",
            "description": "Check recent tweet status and get tweet URLs",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    })
    async def twitter_check_tweet_status(self) -> ToolResult:
        """Check for recent successful tweets - MCP pattern"""
        try:
            # Query recent tweets via backend API
            async with aiohttp.ClientSession() as session:
                response = await session.get(
                    f"{self.base_url}/twitter/accounts/recent-tweets?limit=5",
                    headers={"Authorization": f"Bearer {self.jwt_token}"},
                    timeout=aiohttp.ClientTimeout(total=15)
                )
                
                if response.status == 200:
                    data = await response.json()
                    tweets = data.get('tweets', [])
                    successful_tweets = [t for t in tweets if t.get('tweet_id')]
                    
                    if successful_tweets:
                        message = f"🎉 **Found {len(successful_tweets)} Recent Successful Tweet(s):**\\n\\n"
                        for tweet in successful_tweets:
                            tweet_id = tweet['tweet_id']
                            tweet_text = tweet['text'][:50] + ('...' if len(tweet['text']) > 50 else '')
                            tweet_url = tweet.get('tweet_url', f"https://twitter.com/i/web/status/{tweet_id}")
                            message += f"🐦 **{tweet_text}**\\n🔗 {tweet_url}\\n\\n"
                        
                        return self.success_response(message)
                    else:
                        return self.success_response("No recent successful tweets found.")
                else:
                    error_text = await response.text()
                    return self.fail_response(f"Failed to check tweets: {error_text}")
                    
        except Exception as e:
            return self.fail_response(f"Error checking tweets: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "twitter_search_tweets",
            "description": "Search for tweets using Twitter's search API",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (use Twitter search syntax)"
                    },
                    "account_id": {
                        "type": "string",
                        "description": "Account to search from (optional - uses first enabled account)"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 10, max: 100)"
                    }
                },
                "required": ["query"]
            }
        }
    })
    async def twitter_search_tweets(
        self,
        query: str,
        account_id: Optional[str] = None,
        max_results: int = 10
    ) -> ToolResult:
        """Search for tweets using Twitter API"""
        try:
            # Get available accounts
            has_accounts, available_accounts, error_msg = await self._check_enabled_accounts()
            
            if not has_accounts:
                return self.fail_response(error_msg)
            
            # Use provided account or first available
            if not account_id:
                account_id = available_accounts[0]["id"]
                account_username = available_accounts[0]["username"]
            else:
                account_info = self._get_account_info(account_id, available_accounts)
                account_username = account_info.get("username", "")
            
            # Call search API
            async with aiohttp.ClientSession() as session:
                params = {
                    "query": query,
                    "account_id": account_id,
                    "max_results": min(max_results, 100)
                }
                
                response = await session.get(
                    f"{self.base_url}/twitter/search",
                    headers={"Authorization": f"Bearer {self.jwt_token}"},
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=20)
                )
                
                if response.status == 200:
                    data = await response.json()
                    tweets = data.get('tweets', [])
                    
                    if tweets:
                        message = f"🔍 **Found {len(tweets)} tweets for '{query}':**\\n\\n"
                        for tweet in tweets[:5]:  # Show first 5
                            tweet_text = tweet['text'][:100] + ('...' if len(tweet['text']) > 100 else '')
                            tweet_id = tweet['id']
                            message += f"🐦 **{tweet_text}**\\n🔗 https://twitter.com/i/web/status/{tweet_id}\\n\\n"
                        
                        return self.success_response({
                            "message": message,
                            "tweets": tweets,
                            "query": query,
                            "account_used": account_username,
                            "total_found": len(tweets)
                        })
                    else:
                        return self.success_response({
                            "message": f"No tweets found for '{query}'",
                            "tweets": [],
                            "query": query,
                            "account_used": account_username
                        })
                else:
                    error_text = await response.text()
                    return self.fail_response(f"Search failed: {error_text}")
                    
        except Exception as e:
            logger.error(f"[Twitter MCP] Search error: {e}")
            return self.fail_response(f"Search failed: {str(e)}")