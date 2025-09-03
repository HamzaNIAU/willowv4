"""Twitter Account Service for managing connected accounts"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from services.supabase import DBConnection
from utils.logger import logger


class TwitterAccountService:
    """Service for managing Twitter accounts"""
    
    def __init__(self, db: DBConnection):
        self.db = db
    
    async def get_user_accounts(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active Twitter accounts for a user"""
        client = await self.db.client
        
        result = await client.table("twitter_accounts").select("*").eq(
            "user_id", user_id
        ).eq("is_active", True).order("created_at", desc=True).execute()
        
        accounts = []
        for account in result.data:
            accounts.append({
                "id": account["id"],
                "name": account["name"],
                "username": account["username"],
                "description": account.get("description"),
                "profile_image_url": account.get("profile_image_url"),
                "followers_count": account.get("followers_count", 0),
                "following_count": account.get("following_count", 0),
                "tweet_count": account.get("tweet_count", 0),
                "listed_count": account.get("listed_count", 0),
                "verified": account.get("verified", False),
                "twitter_created_at": account.get("twitter_created_at"),
                "created_at": account.get("created_at"),
                "updated_at": account.get("updated_at"),
            })
        
        return accounts
    
    async def get_account(self, user_id: str, account_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific Twitter account"""
        client = await self.db.client
        
        result = await client.table("twitter_accounts").select("*").eq(
            "user_id", user_id
        ).eq("id", account_id).eq("is_active", True).execute()
        
        if not result.data:
            return None
        
        account = result.data[0]
        return {
            "id": account["id"],
            "name": account["name"],
            "username": account["username"],
            "description": account.get("description"),
            "profile_image_url": account.get("profile_image_url"),
            "followers_count": account.get("followers_count", 0),
            "following_count": account.get("following_count", 0),
            "tweet_count": account.get("tweet_count", 0),
            "listed_count": account.get("listed_count", 0),
            "verified": account.get("verified", False),
            "twitter_created_at": account.get("twitter_created_at"),
            "created_at": account.get("created_at"),
            "updated_at": account.get("updated_at"),
        }
    
    async def update_account_stats(self, user_id: str, account_id: str, stats: Dict[str, Any]) -> bool:
        """Update account statistics"""
        client = await self.db.client
        
        update_data = {
            "followers_count": stats.get("followers_count"),
            "following_count": stats.get("following_count"),
            "tweet_count": stats.get("tweet_count"),
            "listed_count": stats.get("listed_count"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Remove None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        result = await client.table("twitter_accounts").update(update_data).eq(
            "user_id", user_id
        ).eq("id", account_id).execute()
        
        if result.data:
            logger.info(f"Updated stats for Twitter account @{account_id}")
            return True
        
        return False
    
    async def refresh_account_info(self, user_id: str, account_id: str) -> Dict[str, Any]:
        """Refresh account information from Twitter API"""
        from .oauth import TwitterOAuthHandler
        
        oauth_handler = TwitterOAuthHandler(self.db)
        
        try:
            # Get valid access token
            access_token = await oauth_handler.get_valid_token(user_id, account_id)
            
            # Fetch updated user info from Twitter API
            user_info = await oauth_handler.get_user_info(access_token)
            
            # Update account in database
            client = await self.db.client
            update_data = {
                "name": user_info["name"],
                "username": user_info["username"],
                "description": user_info.get("description"),
                "profile_image_url": user_info.get("profile_image_url"),
                "followers_count": user_info.get("followers_count", 0),
                "following_count": user_info.get("following_count", 0),
                "tweet_count": user_info.get("tweet_count", 0),
                "listed_count": user_info.get("listed_count", 0),
                "verified": user_info.get("verified", False),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            
            result = await client.table("twitter_accounts").update(update_data).eq(
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
        
        logger.warning(f"🔄 SMART DEACTIVATION: Marking Twitter account {account_id} for re-auth instead of disconnecting")
        
        # Don't set is_active=False, just mark for re-authentication
        result = await client.table("twitter_accounts").update({
            "needs_reauth": True,  # Mark for re-auth instead of disconnecting
            "last_refresh_error": "Account marked for re-authentication due to system issues",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            # is_active stays TRUE - preserve connection!
        }).eq("user_id", user_id).eq("id", account_id).execute()
        
        if result.data:
            logger.info(f"✅ Smart deactivation: Twitter account {account_id} marked for re-auth (connection preserved)")
            return True
        
        return False
    
    async def account_exists(self, user_id: str, account_id: str) -> bool:
        """Check if an account exists for a user"""
        client = await self.db.client
        
        result = await client.table("twitter_accounts").select("id").eq(
            "user_id", user_id
        ).eq("id", account_id).eq("is_active", True).execute()
        
        return len(result.data) > 0
    
    async def get_accounts_for_agent(self, user_id: str, agent_id: str) -> List[Dict[str, Any]]:
        """Get enabled Twitter accounts for a specific agent with MCP toggle filtering"""
        client = await self.db.client
        
        # Special handling for suna-default virtual agent
        if agent_id == "suna-default":
            logger.info(f"[Twitter Accounts] Using agent_social_accounts for suna-default agent (respects MCP toggles)")
            # Query agent_social_accounts to respect MCP toggle state for suna-default
            result = await client.table("agent_social_accounts").select("""
                account_id, account_name, enabled,
                twitter_accounts!inner(id, name, username, description, profile_image_url, followers_count, following_count, tweet_count, verified)
            """).eq("agent_id", "suna-default").eq(
                "user_id", user_id
            ).eq("platform", "twitter").eq("enabled", True).execute()
            
            if result.data:
                accounts = []
                for account in result.data:
                    tw_data = account["twitter_accounts"]
                    accounts.append({
                        "id": tw_data["id"],
                        "name": tw_data["name"],
                        "username": tw_data["username"],
                        "description": tw_data.get("description", ""),
                        "profile_image_url": tw_data.get("profile_image_url"),
                        "followers_count": tw_data.get("followers_count", 0),
                        "following_count": tw_data.get("following_count", 0),
                        "tweet_count": tw_data.get("tweet_count", 0),
                        "verified": tw_data.get("verified", False)
                    })
                logger.info(f"✅ Found {len(accounts)} ENABLED Twitter accounts for suna-default (respecting MCP toggles)")
                return accounts
            else:
                logger.info(f"❌ No enabled Twitter accounts found for suna-default (check MCP toggles)")
                return []
        
        # Regular agent - query agent_social_accounts
        result = await client.table("agent_social_accounts").select("*").eq(
            "agent_id", agent_id
        ).eq("user_id", user_id).eq(
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
        
        logger.info(f"🔴 REAL-TIME RESULT: Found {len(accounts)} enabled Twitter accounts for agent {agent_id}")
        return accounts
    
    async def get_account_tweets(self, user_id: str, account_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent tweets from local database for an account"""
        client = await self.db.client
        
        result = await client.table("twitter_tweets").select("*").eq(
            "user_id", user_id
        ).eq("account_id", account_id).eq(
            "tweet_status", "completed"
        ).order("created_at", desc=True).limit(limit).execute()
        
        tweets = []
        for tweet in result.data:
            tweets.append({
                "id": tweet.get("tweet_id"),
                "text": tweet["text"],
                "created_at": tweet["created_at"],
                "tweet_url": tweet.get("tweet_url"),
                "media_ids": tweet.get("media_ids", []),
                "reply_to_tweet_id": tweet.get("reply_to_tweet_id"),
                "quote_tweet_id": tweet.get("quote_tweet_id"),
            })
        
        return tweets
    
    async def get_total_stats(self, user_id: str) -> Dict[str, Any]:
        """Get total statistics across all user's Twitter accounts"""
        client = await self.db.client
        
        # Get account stats
        accounts_result = await client.table("twitter_accounts").select(
            "followers_count, following_count, tweet_count"
        ).eq("user_id", user_id).eq("is_active", True).execute()
        
        total_followers = sum(acc.get("followers_count", 0) for acc in accounts_result.data)
        total_following = sum(acc.get("following_count", 0) for acc in accounts_result.data)
        total_tweets = sum(acc.get("tweet_count", 0) for acc in accounts_result.data)
        
        # Get recent tweet count from local records
        tweets_result = await client.table("twitter_tweets").select("id").eq(
            "user_id", user_id
        ).eq("tweet_status", "completed").execute()
        
        recent_tweets_count = len(tweets_result.data)
        
        return {
            "total_accounts": len(accounts_result.data),
            "total_followers": total_followers,
            "total_following": total_following,
            "total_tweets": total_tweets,
            "recent_tweets_posted": recent_tweets_count
        }