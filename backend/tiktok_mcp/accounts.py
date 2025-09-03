"""TikTok Account Management Service"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import json

from services.supabase import DBConnection
from utils.logger import logger
from utils.encryption import decrypt_data


class TikTokAccountService:
    """Service for managing TikTok accounts"""
    
    def __init__(self, db: DBConnection):
        self.db = db
    
    async def get_user_accounts(self, user_id: str, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """Get all TikTok accounts for a user"""
        try:
            query = """
                SELECT 
                    id, user_id, union_id, username, name, profile_image_url,
                    token_expires_at, token_scopes, is_active, needs_reauth,
                    created_at, updated_at
                FROM tiktok_accounts 
                WHERE user_id = $1
            """
            
            if not include_inactive:
                query += " AND is_active = true"
            
            query += " ORDER BY created_at DESC"
            
            rows = await self.db.fetch(query, user_id)
            
            accounts = []
            for row in rows:
                account_data = {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "union_id": row["union_id"],
                    "username": row["username"],
                    "name": row["name"],
                    "profile_image_url": row["profile_image_url"],
                    "token_expires_at": row["token_expires_at"].isoformat() if row["token_expires_at"] else None,
                    "token_scopes": row["token_scopes"] or [],
                    "is_active": row["is_active"],
                    "needs_reauth": row["needs_reauth"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                    "platform": "tiktok"
                }
                accounts.append(account_data)
            
            logger.info(f"Retrieved {len(accounts)} TikTok accounts for user {user_id}")
            return accounts
            
        except Exception as e:
            logger.error(f"Failed to get TikTok accounts for user {user_id}: {e}")
            raise
    
    async def get_account(self, user_id: str, account_id: str) -> Optional[Dict[str, Any]]:
        """Get specific TikTok account"""
        try:
            row = await self.db.fetchrow("""
                SELECT 
                    id, user_id, union_id, username, name, profile_image_url,
                    token_expires_at, token_scopes, is_active, needs_reauth,
                    created_at, updated_at
                FROM tiktok_accounts 
                WHERE user_id = $1 AND id = $2
            """, user_id, account_id)
            
            if not row:
                return None
            
            account_data = {
                "id": row["id"],
                "user_id": row["user_id"],
                "union_id": row["union_id"],
                "username": row["username"],
                "name": row["name"],
                "profile_image_url": row["profile_image_url"],
                "token_expires_at": row["token_expires_at"].isoformat() if row["token_expires_at"] else None,
                "token_scopes": row["token_scopes"] or [],
                "is_active": row["is_active"],
                "needs_reauth": row["needs_reauth"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                "platform": "tiktok"
            }
            
            return account_data
            
        except Exception as e:
            logger.error(f"Failed to get TikTok account {account_id} for user {user_id}: {e}")
            raise
    
    async def update_account_stats(
        self,
        user_id: str,
        account_id: str,
        stats: Dict[str, Any]
    ) -> bool:
        """Update account statistics from TikTok API"""
        try:
            # Note: The current tiktok_accounts table doesn't have stats columns
            # This is a placeholder for future enhancement
            logger.info(f"TikTok account stats update requested for {account_id}: {stats}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update TikTok account stats: {e}")
            return False
    
    async def mark_account_needs_reauth(self, user_id: str, account_id: str, error_message: str = None) -> bool:
        """Mark account as needing re-authentication"""
        try:
            await self.db.execute("""
                UPDATE tiktok_accounts SET
                    needs_reauth = true,
                    last_refresh_error = $3,
                    updated_at = NOW()
                WHERE user_id = $1 AND id = $2
            """, user_id, account_id, error_message)
            
            logger.info(f"Marked TikTok account {account_id} as needing re-auth")
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark TikTok account for re-auth: {e}")
            return False
    
    async def create_agent_connections(self, user_id: str, account_id: str) -> bool:
        """Create agent social account connections for all user agents"""
        try:
            # Get all user agents (including suna-default)
            agents = await self.db.fetch("""
                SELECT agent_id FROM agents 
                WHERE account_id IN (
                    SELECT id FROM accounts WHERE user_id = $1
                )
                UNION
                SELECT 'suna-default' as agent_id
            """, user_id)
            
            # Get account info for the connection
            account = await self.get_account(user_id, account_id)
            if not account:
                raise Exception(f"Account {account_id} not found")
            
            # Create connections for each agent
            for agent in agents:
                agent_id = agent["agent_id"]
                
                await self.db.execute("""
                    INSERT INTO agent_social_accounts (
                        agent_id, user_id, platform, account_id, account_name, enabled, created_at, updated_at
                    ) VALUES (
                        $1, $2, 'tiktok', $3, $4, true, NOW(), NOW()
                    )
                    ON CONFLICT (agent_id, user_id, platform, account_id) 
                    DO UPDATE SET
                        account_name = EXCLUDED.account_name,
                        enabled = true,
                        updated_at = NOW()
                """, agent_id, user_id, account_id, account["name"])
            
            logger.info(f"Created TikTok agent connections for account {account_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create TikTok agent connections: {e}")
            return False
    
    async def get_agent_accounts(self, user_id: str, agent_id: str) -> List[Dict[str, Any]]:
        """Get TikTok accounts enabled for a specific agent"""
        try:
            rows = await self.db.fetch("""
                SELECT ta.*, asa.enabled, asa.account_name as agent_account_name
                FROM tiktok_accounts ta
                JOIN agent_social_accounts asa ON (
                    asa.user_id = ta.user_id AND
                    asa.platform = 'tiktok' AND 
                    asa.account_id = ta.id
                )
                WHERE ta.user_id = $1 
                AND asa.agent_id = $2
                AND ta.is_active = true
                AND asa.enabled = true
                ORDER BY ta.name
            """, user_id, agent_id)
            
            accounts = []
            for row in rows:
                account_data = {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "union_id": row["union_id"],
                    "username": row["username"],
                    "name": row["name"],
                    "profile_image_url": row["profile_image_url"],
                    "enabled": row["enabled"],
                    "platform": "tiktok"
                }
                accounts.append(account_data)
            
            logger.info(f"Retrieved {len(accounts)} enabled TikTok accounts for agent {agent_id}")
            return accounts
            
        except Exception as e:
            logger.error(f"Failed to get TikTok agent accounts: {e}")
            raise
    
    async def toggle_agent_account(
        self,
        user_id: str,
        agent_id: str, 
        account_id: str,
        enabled: bool
    ) -> bool:
        """Toggle TikTok account for specific agent"""
        try:
            await self.db.execute("""
                UPDATE agent_social_accounts SET
                    enabled = $4,
                    updated_at = NOW()
                WHERE user_id = $1 AND agent_id = $2 AND platform = 'tiktok' AND account_id = $3
            """, user_id, agent_id, account_id, enabled)
            
            action = "enabled" if enabled else "disabled"
            logger.info(f"TikTok account {account_id} {action} for agent {agent_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to toggle TikTok account: {e}")
            return False
    
    async def refresh_account_from_api(self, user_id: str, account_id: str) -> bool:
        """Refresh account information from TikTok API"""
        try:
            from .service import TikTokAPIService
            
            api_service = TikTokAPIService(self.db)
            user_info = await api_service.get_user_info(user_id, account_id)
            
            # Update account with fresh data
            await self.db.execute("""
                UPDATE tiktok_accounts SET
                    username = $3,
                    name = $4,
                    profile_image_url = $5,
                    updated_at = NOW()
                WHERE user_id = $1 AND id = $2
            """,
                user_id, account_id,
                user_info.get("display_name", ""),
                user_info.get("display_name", ""),
                user_info.get("avatar_url_200") or user_info.get("avatar_url_100") or user_info.get("avatar_url")
            )
            
            logger.info(f"Refreshed TikTok account {account_id} from API")
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh TikTok account from API: {e}")
            return False
    
    async def get_account_upload_history(
        self,
        user_id: str,
        account_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get upload history for TikTok account"""
        try:
            rows = await self.db.fetch("""
                SELECT * FROM tiktok_videos
                WHERE user_id = $1 AND account_id = $2
                ORDER BY created_at DESC
                LIMIT $3 OFFSET $4
            """, user_id, account_id, limit, offset)
            
            uploads = []
            for row in rows:
                upload_data = {
                    "id": row["id"],
                    "account_id": row["account_id"],
                    "title": row["title"],
                    "description": row["description"],
                    "upload_status": row["video_status"],
                    "video_id": row["video_id"],
                    "video_url": row["video_url"],
                    "status_message": row["status_message"],
                    "error_details": row["error_details"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None
                }
                uploads.append(upload_data)
            
            return uploads
            
        except Exception as e:
            logger.error(f"Failed to get TikTok upload history: {e}")
            raise