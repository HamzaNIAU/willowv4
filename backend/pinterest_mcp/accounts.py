"""Pinterest Account Management Service"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import aiohttp

from services.supabase import DBConnection
from utils.encryption import decrypt_data
from utils.logger import logger
from .oauth import PinterestOAuthHandler


class PinterestAccountService:
    """Service for managing Pinterest accounts"""
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.oauth_handler = PinterestOAuthHandler(db)
    
    async def get_user_accounts(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all Pinterest accounts for a user"""
        try:
            client = await self.db.client
            result = await client.table("pinterest_accounts").select("*").eq(
                "user_id", user_id
            ).eq("is_active", True).order("created_at", desc=True).execute()
            
            accounts = result.data or []
            
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
                    "username": account['username'],
                    "name": account['name'],
                    "profile_image_url": account['profile_image_url'],
                    "website_url": account['website_url'],
                    "about": account['about'],
                    "pin_count": account['pin_count'],
                    "board_count": account['board_count'],
                    "follower_count": account['follower_count'],
                    "following_count": account['following_count'],
                    "account_type": account['account_type'],
                    "token_status": token_status,
                    "token_expires_at": account['token_expires_at'].isoformat() if account['token_expires_at'] else None,
                    "created_at": account['created_at'].isoformat(),
                    "updated_at": account['updated_at'].isoformat() if account['updated_at'] else None,
                    "platform": "pinterest"
                })
            
            return formatted_accounts
            
        except Exception as e:
            logger.error(f"Failed to get Pinterest accounts: {e}")
            raise
    
    async def get_account(self, user_id: str, account_id: str) -> Optional[Dict[str, Any]]:
        """Get specific Pinterest account"""
        try:
            account = await self.db.fetchrow("""
                SELECT 
                    id, username, name, profile_image_url, website_url, about,
                    pin_count, board_count, follower_count, following_count,
                    account_type, is_active, needs_reauth, token_expires_at,
                    created_at, updated_at
                FROM pinterest_accounts 
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
                "username": account['username'],
                "name": account['name'],
                "profile_image_url": account['profile_image_url'],
                "website_url": account['website_url'],
                "about": account['about'],
                "pin_count": account['pin_count'],
                "board_count": account['board_count'],
                "follower_count": account['follower_count'],
                "following_count": account['following_count'],
                "account_type": account['account_type'],
                "token_status": token_status,
                "token_expires_at": account['token_expires_at'].isoformat() if account['token_expires_at'] else None,
                "created_at": account['created_at'].isoformat(),
                "updated_at": account['updated_at'].isoformat() if account['updated_at'] else None,
                "platform": "pinterest"
            }
            
        except Exception as e:
            logger.error(f"Failed to get Pinterest account: {e}")
            raise
    
    async def get_accounts_for_agent(self, user_id: str, agent_id: str) -> List[Dict[str, Any]]:
        """Get ONLY enabled Pinterest accounts for a specific agent via unified system"""
        try:
            # Query unified social accounts table directly
            accounts = await self.db.fetch("""
                SELECT 
                    asa.account_id as id,
                    asa.account_name as name,
                    asa.username,
                    asa.profile_image_url,
                    asa.followers_count,
                    asa.following_count,
                    asa.enabled,
                    asa.created_at,
                    asa.updated_at,
                    pa.website_url,
                    pa.about,
                    pa.pin_count,
                    pa.board_count,
                    pa.account_type,
                    pa.needs_reauth,
                    pa.token_expires_at
                FROM agent_social_accounts asa
                JOIN pinterest_accounts pa ON (
                    asa.account_id = pa.id AND 
                    asa.user_id = pa.user_id
                )
                WHERE 
                    asa.agent_id = $1 
                    AND asa.user_id = $2 
                    AND asa.platform = 'pinterest'
                    AND asa.enabled = true
                    AND pa.is_active = true
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
                    "username": account['username'],
                    "name": account['name'],
                    "profile_image_url": account['profile_image_url'],
                    "website_url": account['website_url'],
                    "about": account['about'],
                    "pin_count": account['pin_count'],
                    "board_count": account['board_count'],
                    "follower_count": account['followers_count'],
                    "following_count": account['following_count'],
                    "account_type": account['account_type'],
                    "token_status": token_status,
                    "enabled": account['enabled'],
                    "agent_id": agent_id,
                    "platform": "pinterest"
                })
            
            return formatted_accounts
            
        except Exception as e:
            logger.error(f"Failed to get Pinterest accounts for agent {agent_id}: {e}")
            return []
    
    async def refresh_account_info(self, user_id: str, account_id: str) -> Dict[str, Any]:
        """Refresh Pinterest account information from API"""
        try:
            # Get valid access token
            access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
            
            # Get fresh user info from Pinterest
            user_info = await self.oauth_handler.get_user_info(access_token)
            
            # Update account in database
            await self.db.execute("""
                UPDATE pinterest_accounts SET
                    username = $3,
                    name = $4,
                    profile_image_url = $5,
                    website_url = $6,
                    about = $7,
                    pin_count = $8,
                    board_count = $9,
                    follower_count = $10,
                    following_count = $11,
                    account_type = $12,
                    updated_at = NOW()
                WHERE user_id = $1 AND id = $2
            """, user_id, account_id, 
                user_info['username'], user_info['name'], user_info['profile_image_url'],
                user_info['website_url'], user_info['about'], user_info['pin_count'],
                user_info['board_count'], user_info['follower_count'], user_info['following_count'],
                user_info['account_type']
            )
            
            # Return updated account
            return await self.get_account(user_id, account_id)
            
        except Exception as e:
            logger.error(f"Failed to refresh Pinterest account info: {e}")
            raise
    
    async def get_account_boards(self, user_id: str, account_id: str) -> List[Dict[str, Any]]:
        """Get boards from Pinterest account"""
        try:
            # Get valid access token
            access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            # Get user's boards using Pinterest API v5
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.pinterest.com/v5/boards",
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    boards_data = await response.json()
            
            boards = []
            for item in boards_data.get('items', []):
                board = {
                    "id": item.get('id'),
                    "name": item.get('name'),
                    "description": item.get('description'),
                    "pin_count": item.get('pin_count', 0),
                    "follower_count": item.get('follower_count', 0),
                    "privacy": item.get('privacy', 'PUBLIC'),  # PUBLIC or SECRET
                    "created_at": item.get('created_at'),
                    "board_url": f"https://pinterest.com/{item.get('owner', {}).get('username', '')}/{item.get('name', '')}"
                }
                boards.append(board)
            
            return boards
            
        except Exception as e:
            logger.error(f"Failed to get Pinterest account boards: {e}")
            return []
    
    async def validate_account_access(self, user_id: str, account_id: str) -> bool:
        """Validate that user has access to Pinterest account and token is valid"""
        try:
            # Check if account exists and belongs to user
            account = await self.db.fetchrow("""
                SELECT id, needs_reauth, token_expires_at 
                FROM pinterest_accounts 
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
            logger.error(f"Failed to validate Pinterest account access: {e}")
            return False