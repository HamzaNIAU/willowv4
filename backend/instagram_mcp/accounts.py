"""Instagram Account Service for managing connected accounts"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from services.supabase import DBConnection
from utils.logger import logger


class InstagramAccountService:
    """Service for managing Instagram accounts"""
    
    def __init__(self, db: DBConnection):
        self.db = db
    
    async def get_user_accounts(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active Instagram accounts for a user"""
        client = await self.db.client
        
        result = await client.table("instagram_accounts").select("*").eq(
            "user_id", user_id
        ).eq("is_active", True).order("created_at", desc=True).execute()
        
        accounts = []
        for account in result.data:
            accounts.append({
                "id": account["id"],
                "username": account["username"],
                "name": account["name"],
                "biography": account.get("biography"),
                "profile_picture_url": account.get("profile_picture_url"),
                "website": account.get("website"),
                "account_type": account.get("account_type", "PERSONAL"),
                "followers_count": account.get("followers_count", 0),
                "following_count": account.get("following_count", 0),
                "media_count": account.get("media_count", 0),
                "created_at": account.get("created_at"),
                "updated_at": account.get("updated_at"),
            })
        
        return accounts
    
    async def get_account(self, user_id: str, account_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific Instagram account"""
        client = await self.db.client
        
        result = await client.table("instagram_accounts").select("*").eq(
            "user_id", user_id
        ).eq("id", account_id).eq("is_active", True).execute()
        
        if not result.data:
            return None
        
        account = result.data[0]
        return {
            "id": account["id"],
            "username": account["username"],
            "name": account["name"],
            "biography": account.get("biography"),
            "profile_picture_url": account.get("profile_picture_url"),
            "website": account.get("website"),
            "account_type": account.get("account_type", "PERSONAL"),
            "followers_count": account.get("followers_count", 0),
            "following_count": account.get("following_count", 0),
            "media_count": account.get("media_count", 0),
            "created_at": account.get("created_at"),
            "updated_at": account.get("updated_at"),
        }
    
    async def update_account_stats(self, user_id: str, account_id: str, stats: Dict[str, Any]) -> bool:
        """Update account statistics"""
        client = await self.db.client
        
        update_data = {
            "followers_count": stats.get("followers_count"),
            "following_count": stats.get("following_count"),
            "media_count": stats.get("media_count"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Remove None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        result = await client.table("instagram_accounts").update(update_data).eq(
            "user_id", user_id
        ).eq("id", account_id).execute()
        
        if result.data:
            logger.info(f"Updated stats for Instagram account @{account_id}")
            return True
        
        return False
    
    async def refresh_account_info(self, user_id: str, account_id: str) -> Dict[str, Any]:
        """Refresh account information from Instagram API"""
        from .oauth import InstagramOAuthHandler
        
        oauth_handler = InstagramOAuthHandler(self.db)
        
        try:
            # Get valid access token
            access_token = await oauth_handler.get_valid_token(user_id, account_id)
            
            # Fetch updated user info from Instagram API
            user_info = await oauth_handler.get_user_info(access_token)
            
            # Update account in database
            client = await self.db.client
            update_data = {
                "username": user_info["username"],
                "name": user_info["name"],
                "biography": user_info.get("biography"),
                "profile_picture_url": user_info.get("profile_picture_url"),
                "website": user_info.get("website"),
                "account_type": user_info.get("account_type", "PERSONAL"),
                "followers_count": user_info.get("followers_count", 0),
                "following_count": user_info.get("following_count", 0),
                "media_count": user_info.get("media_count", 0),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            
            result = await client.table("instagram_accounts").update(update_data).eq(
                "user_id", user_id
            ).eq("id", account_id).execute()
            
            if not result.data:
                raise Exception("Failed to update account")
            
            logger.info(f"Refreshed account info for @{user_info['username']}")
            
            # Return updated account info
            return await self.get_account(user_id, account_id)
            
        except Exception as e:
            logger.error(f"Failed to refresh account info for {account_id}: {e}")
            raise
    
    async def deactivate_account(self, user_id: str, account_id: str) -> bool:
        """Smart deactivation: Mark for re-auth instead of disconnecting"""
        client = await self.db.client
        
        logger.warning(f"🔄 SMART DEACTIVATION: Marking Instagram account {account_id} for re-auth instead of disconnecting")
        
        # Don't set is_active=False, just mark for re-authentication
        result = await client.table("instagram_accounts").update({
            "needs_reauth": True,  # Mark for re-auth instead of disconnecting
            "last_refresh_error": "Account marked for re-authentication due to system issues",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            # is_active stays TRUE - preserve connection!
        }).eq("user_id", user_id).eq("id", account_id).execute()
        
        if result.data:
            logger.info(f"✅ Smart deactivation: Instagram account {account_id} marked for re-auth (connection preserved)")
            return True
        
        return False
    
    async def account_exists(self, user_id: str, account_id: str) -> bool:
        """Check if an account exists for a user"""
        client = await self.db.client
        
        result = await client.table("instagram_accounts").select("id").eq(
            "user_id", user_id
        ).eq("id", account_id).eq("is_active", True).execute()
        
        return len(result.data) > 0
    
    async def get_accounts_for_agent(self, user_id: str, agent_id: str) -> List[Dict[str, Any]]:
        """Get enabled Instagram accounts for a specific agent with MCP toggle filtering"""
        client = await self.db.client
        
        # Special handling for suna-default virtual agent
        if agent_id == "suna-default":
            logger.info(f"[Instagram Accounts] Using agent_social_accounts for suna-default agent (respects MCP toggles)")
            # Query agent_social_accounts to respect MCP toggle state for suna-default
            result = await client.table("agent_social_accounts").select("""
                account_id, account_name, enabled,
                instagram_accounts!inner(id, username, name, biography, profile_picture_url, account_type, followers_count, following_count, media_count)
            """).eq("agent_id", "suna-default").eq(
                "user_id", user_id
            ).eq("platform", "instagram").eq("enabled", True).execute()
            
            if result.data:
                accounts = []
                for account in result.data:
                    ig_data = account["instagram_accounts"]
                    accounts.append({
                        "id": ig_data["id"],
                        "username": ig_data["username"],
                        "name": ig_data["name"],
                        "biography": ig_data.get("biography", ""),
                        "profile_picture_url": ig_data.get("profile_picture_url"),
                        "account_type": ig_data.get("account_type", "PERSONAL"),
                        "followers_count": ig_data.get("followers_count", 0),
                        "following_count": ig_data.get("following_count", 0),
                        "media_count": ig_data.get("media_count", 0),
                    })
                logger.info(f"✅ Found {len(accounts)} ENABLED Instagram accounts for suna-default (respecting MCP toggles)")
                return accounts
            else:
                logger.info(f"❌ No enabled Instagram accounts found for suna-default (check MCP toggles)")
                return []
        
        # Regular agent - query agent_social_accounts
        result = await client.table("agent_social_accounts").select("*").eq(
            "agent_id", agent_id
        ).eq("user_id", user_id).eq(
            "platform", "instagram"  
        ).eq("enabled", True).execute()
        
        accounts = []
        for account in result.data:
            accounts.append({
                "id": account["account_id"],
                "username": account["account_username"],
                "name": account["account_name"],
                "biography": account["biography"],
                "profile_picture_url": account["profile_picture_url"],
                "account_type": account["account_type"],
                "followers_count": account["followers_count"],
                "following_count": account["following_count"],
                "media_count": account["media_count"],
            })
        
        logger.info(f"🟠 REAL-TIME RESULT: Found {len(accounts)} enabled Instagram accounts for agent {agent_id}")
        return accounts
    
    async def get_account_posts(self, user_id: str, account_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent posts from local database for an account"""
        client = await self.db.client
        
        result = await client.table("instagram_posts").select("*").eq(
            "user_id", user_id
        ).eq("account_id", account_id).eq(
            "post_status", "completed"
        ).order("created_at", desc=True).limit(limit).execute()
        
        posts = []
        for post in result.data:
            posts.append({
                "id": post.get("media_id"),
                "caption": post["caption"],
                "media_type": post.get("media_type", "IMAGE"),
                "created_at": post["created_at"],
                "media_url": post.get("media_url"),
                "container_id": post.get("container_id"),
            })
        
        return posts
    
    async def get_total_stats(self, user_id: str) -> Dict[str, Any]:
        """Get total statistics across all user's Instagram accounts"""
        client = await self.db.client
        
        # Get account stats
        accounts_result = await client.table("instagram_accounts").select(
            "followers_count, following_count, media_count"
        ).eq("user_id", user_id).eq("is_active", True).execute()
        
        total_followers = sum(acc.get("followers_count", 0) for acc in accounts_result.data)
        total_following = sum(acc.get("following_count", 0) for acc in accounts_result.data)
        total_media = sum(acc.get("media_count", 0) for acc in accounts_result.data)
        
        # Get recent post count from local records
        posts_result = await client.table("instagram_posts").select("id").eq(
            "user_id", user_id
        ).eq("post_status", "completed").execute()
        
        recent_posts_count = len(posts_result.data)
        
        return {
            "total_accounts": len(accounts_result.data),
            "total_followers": total_followers,
            "total_following": total_following,
            "total_media": total_media,
            "recent_posts_posted": recent_posts_count
        }