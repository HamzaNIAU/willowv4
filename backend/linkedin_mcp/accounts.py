"""LinkedIn Account Management Service"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import aiohttp

from services.supabase import DBConnection
from utils.encryption import decrypt_data
from utils.logger import logger
from .oauth import LinkedInOAuthHandler


class LinkedInAccountService:
    """Service for managing LinkedIn accounts"""
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.oauth_handler = LinkedInOAuthHandler(db)
    
    async def get_user_accounts(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all LinkedIn accounts for a user"""
        try:
            client = await self.db.client
            result = await client.table("linkedin_accounts").select("*").eq(
                "user_id", user_id
            ).eq("is_active", True).order("created_at", desc=True).execute()
            
            accounts = result.data
            
            formatted_accounts = []
            for account in accounts:
                # Check token status
                token_status = "valid"
                if account['needs_reauth']:
                    token_status = "needs_reauth"
                elif account['token_expires_at'] and account['token_expires_at'] <= datetime.utcnow():
                    token_status = "expired"
                
                formatted_accounts.append({
                    "id": account['id'],
                    "name": account['name'],
                    "first_name": account['first_name'],
                    "last_name": account['last_name'],
                    "email": account['email'],
                    "profile_image_url": account['profile_image_url'],
                    "token_status": token_status,
                    "token_expires_at": account['token_expires_at'].isoformat() if account['token_expires_at'] else None,
                    "created_at": account['created_at'].isoformat(),
                    "updated_at": account['updated_at'].isoformat() if account['updated_at'] else None,
                    "platform": "linkedin"
                })
            
            return formatted_accounts
            
        except Exception as e:
            logger.error(f"Failed to get LinkedIn accounts: {e}")
            raise
    
    async def get_account(self, user_id: str, account_id: str) -> Optional[Dict[str, Any]]:
        """Get specific LinkedIn account"""
        try:
            account = await self.db.fetchrow("""
                SELECT 
                    id, name, first_name, last_name, email, profile_image_url,
                    is_active, needs_reauth, token_expires_at,
                    created_at, updated_at
                FROM linkedin_accounts 
                WHERE user_id = $1 AND id = $2 AND is_active = true
            """, user_id, account_id)
            
            if not account:
                return None
            
            # Check token status
            token_status = "valid"
            if account['needs_reauth']:
                token_status = "needs_reauth"
            elif account['token_expires_at'] and account['token_expires_at'] <= datetime.utcnow():
                token_status = "expired"
            
            return {
                "id": account['id'],
                "name": account['name'],
                "first_name": account['first_name'],
                "last_name": account['last_name'],
                "email": account['email'],
                "profile_image_url": account['profile_image_url'],
                "token_status": token_status,
                "token_expires_at": account['token_expires_at'].isoformat() if account['token_expires_at'] else None,
                "created_at": account['created_at'].isoformat(),
                "updated_at": account['updated_at'].isoformat() if account['updated_at'] else None,
                "platform": "linkedin"
            }
            
        except Exception as e:
            logger.error(f"Failed to get LinkedIn account: {e}")
            raise
    
    async def get_accounts_for_agent(self, user_id: str, agent_id: str) -> List[Dict[str, Any]]:
        """Get ONLY enabled LinkedIn accounts for a specific agent via unified system"""
        try:
            # Query unified social accounts table directly
            accounts = await self.db.fetch("""
                SELECT 
                    asa.account_id as id,
                    asa.account_name as name,
                    asa.username as first_name,  -- LinkedIn doesn't have username, use first_name
                    asa.description as last_name,  -- Use description for last_name
                    asa.profile_image_url,
                    asa.followers_count,
                    asa.following_count,
                    asa.verified,
                    asa.enabled,
                    asa.created_at,
                    asa.updated_at,
                    la.email,
                    la.first_name as actual_first_name,
                    la.last_name as actual_last_name,
                    la.needs_reauth,
                    la.token_expires_at
                FROM agent_social_accounts asa
                JOIN linkedin_accounts la ON (
                    asa.account_id = la.id AND 
                    asa.user_id = la.user_id
                )
                WHERE 
                    asa.agent_id = $1 
                    AND asa.user_id = $2 
                    AND asa.platform = 'linkedin'
                    AND asa.enabled = true
                    AND la.is_active = true
                ORDER BY asa.account_name
            """, agent_id, user_id)
            
            formatted_accounts = []
            for account in accounts:
                # Check token status
                token_status = "valid"
                if account['needs_reauth']:
                    token_status = "needs_reauth"
                elif account['token_expires_at'] and account['token_expires_at'] <= datetime.utcnow():
                    token_status = "expired"
                
                formatted_accounts.append({
                    "id": account['id'],
                    "name": account['name'],
                    "first_name": account['actual_first_name'],
                    "last_name": account['actual_last_name'],
                    "email": account['email'],
                    "profile_image_url": account['profile_image_url'],
                    "token_status": token_status,
                    "enabled": account['enabled'],
                    "agent_id": agent_id,
                    "platform": "linkedin"
                })
            
            return formatted_accounts
            
        except Exception as e:
            logger.error(f"Failed to get LinkedIn accounts for agent {agent_id}: {e}")
            return []
    
    async def refresh_account_info(self, user_id: str, account_id: str) -> Dict[str, Any]:
        """Refresh LinkedIn account information from API"""
        try:
            # Get valid access token
            access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
            
            # Get fresh user info from LinkedIn
            user_info = await self.oauth_handler.get_user_info(access_token)
            
            # Update account in database
            await self.db.execute("""
                UPDATE linkedin_accounts SET
                    name = $3,
                    first_name = $4,
                    last_name = $5,
                    email = $6,
                    profile_image_url = $7,
                    updated_at = NOW()
                WHERE user_id = $1 AND id = $2
            """, user_id, account_id, 
                user_info['name'], user_info['first_name'], user_info['last_name'],
                user_info['email'], user_info['profile_image_url']
            )
            
            # Return updated account
            return await self.get_account(user_id, account_id)
            
        except Exception as e:
            logger.error(f"Failed to refresh LinkedIn account info: {e}")
            raise
    
    async def get_account_posts(self, user_id: str, account_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent posts from LinkedIn account"""
        try:
            # Get valid access token
            access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            # Get user's posts using LinkedIn API v2
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.linkedin.com/v2/shares?q=owners&owners=urn:li:person:{account_id}&count={limit}",
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    posts_data = await response.json()
            
            posts = []
            for element in posts_data.get('elements', []):
                post = {
                    "id": element.get('id'),
                    "text": element.get('text', {}).get('text', ''),
                    "created_time": element.get('created', {}).get('time'),
                    "visibility": element.get('visibility', {}).get('com.linkedin.ugc.MemberNetworkVisibility'),
                    "author": element.get('owner'),
                    "activity": element.get('activity')
                }
                posts.append(post)
            
            return posts
            
        except Exception as e:
            logger.error(f"Failed to get LinkedIn account posts: {e}")
            return []
    
    async def validate_account_access(self, user_id: str, account_id: str) -> bool:
        """Validate that user has access to LinkedIn account and token is valid"""
        try:
            # Check if account exists and belongs to user
            account = await self.db.fetchrow("""
                SELECT id, needs_reauth, token_expires_at 
                FROM linkedin_accounts 
                WHERE user_id = $1 AND id = $2 AND is_active = true
            """, user_id, account_id)
            
            if not account:
                return False
            
            # Check if needs reauth
            if account['needs_reauth']:
                return False
            
            # Check if token is expired
            if account['token_expires_at'] and account['token_expires_at'] <= datetime.utcnow():
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to validate LinkedIn account access: {e}")
            return False