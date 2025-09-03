"""Pinterest Upload Service"""

import uuid
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import base64

from services.supabase import DBConnection
from services.youtube_file_service import YouTubeFileService
from utils.logger import logger
from utils.encryption import decrypt_data
from .service import PinterestAPIService
from .oauth import PinterestOAuthHandler
from .accounts import PinterestAccountService


class PinterestUploadService:
    """Service for handling Pinterest pin creation and uploads"""
    
    def __init__(self, db: DBConnection):
        self.db = db
        self.file_service = YouTubeFileService(db)
        self.api_service = PinterestAPIService()
        self.oauth_handler = PinterestOAuthHandler(db)
        self.account_service = PinterestAccountService(db)
    
    async def create_pin(self, user_id: str, pin_params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Pinterest pin with automatic file discovery"""
        try:
            # Validate required parameters
            if not pin_params.get("account_id"):
                raise ValueError("account_id is required")
            
            if not pin_params.get("title"):
                raise ValueError("title is required")
            
            account_id = pin_params["account_id"]
            title = pin_params["title"]
            description = pin_params.get("description", "")
            board_id = pin_params.get("board_id")  # Required for Pinterest
            link = pin_params.get("link")  # Optional website link
            
            if not board_id:
                raise ValueError("board_id is required for Pinterest pins")
            
            # Validate account access
            if not await self.account_service.validate_account_access(user_id, account_id):
                raise ValueError("Invalid account or expired token. Please re-authenticate.")
            
            # Auto-discover files if enabled
            video_reference_id = pin_params.get("video_reference_id")
            image_reference_ids = pin_params.get("image_reference_ids", [])
            
            if pin_params.get("auto_discover", True) and not video_reference_id and not image_reference_ids:
                uploads = await self.file_service.get_latest_pending_uploads(user_id)
                
                if uploads.get("video"):
                    video_reference_id = uploads["video"]["reference_id"]
                    logger.info(f"Auto-discovered video: {video_reference_id}")
                
                if uploads.get("thumbnail"):
                    image_reference_ids = [uploads["thumbnail"]["reference_id"]]
                    logger.info(f"Auto-discovered image: {image_reference_ids}")
            
            # Pinterest requires at least one image or video
            if not video_reference_id and not image_reference_ids:
                raise ValueError("Pinterest pins require at least one image or video. Please upload a file first.")
            
            # Create pin record
            pin_record_id = str(uuid.uuid4())
            
            await self.db.execute("""
                INSERT INTO pinterest_pins (
                    id, user_id, account_id, title, description, board_id, link,
                    video_reference_id, image_reference_ids,
                    pin_status, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'pending', NOW())
            """, pin_record_id, user_id, account_id, title, description, board_id, link,
                video_reference_id, image_reference_ids
            )
            
            # Start background pin creation
            asyncio.create_task(self._create_pin_background(pin_record_id, user_id, pin_params))
            
            # Get account info for response
            account_info = await self.account_service.get_account(user_id, account_id)
            
            return {
                "pin_record_id": pin_record_id,
                "status": "pinning",
                "message": "Pinterest pin creation started",
                "account_name": account_info.get("name", "Pinterest User") if account_info else "Pinterest User",
                "title": title
            }
            
        except Exception as e:
            logger.error(f"Failed to create Pinterest pin: {e}")
            raise
    
    async def _create_pin_background(self, pin_record_id: str, user_id: str, pin_params: Dict[str, Any]):
        """Background task to create Pinterest pin"""
        try:
            # Update status to pinning
            await self.db.execute("""
                UPDATE pinterest_pins 
                SET pin_status = 'pinning', status_message = 'Creating Pinterest pin...'
                WHERE id = $1
            """, pin_record_id)
            
            # Get pin details
            pin = await self.db.fetchrow("""
                SELECT * FROM pinterest_pins WHERE id = $1
            """, pin_record_id)
            
            if not pin:
                raise Exception("Pin record not found")
            
            account_id = pin['account_id']
            title = pin['title']
            description = pin['description']
            board_id = pin['board_id']
            link = pin['link']
            video_reference_id = pin['video_reference_id']
            image_reference_ids = pin['image_reference_ids'] or []
            
            # Get valid access token
            access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
            
            # Determine pin type and create accordingly
            if video_reference_id:
                # Video pin
                video_data = await self.file_service.get_file_data(video_reference_id)
                
                # Get thumbnail if available
                thumbnail_data = None
                if image_reference_ids:
                    thumbnail_data = await self.file_service.get_file_data(image_reference_ids[0])
                
                result = await self.api_service.create_video_pin(
                    access_token, board_id, title, description, video_data,
                    thumbnail_data, link
                )
                
                # Mark video reference as used
                await self.file_service.mark_reference_as_used(video_reference_id)
                if image_reference_ids:
                    await self.file_service.mark_reference_as_used(image_reference_ids[0])
                
            elif image_reference_ids:
                # Image pin (Pinterest supports one image per pin)
                image_data = await self.file_service.get_file_data(image_reference_ids[0])
                
                result = await self.api_service.create_pin(
                    access_token, board_id, title, description, link,
                    image_data=image_data
                )
                
                # Mark image reference as used
                await self.file_service.mark_reference_as_used(image_reference_ids[0])
                
            else:
                raise Exception("No media files found for pin creation")
            
            # Update pin record with success
            await self.db.execute("""
                UPDATE pinterest_pins SET
                    pin_id = $2,
                    pin_url = $3,
                    pin_status = 'completed',
                    status_message = 'Pin created successfully',
                    completed_at = NOW()
                WHERE id = $1
            """, pin_record_id, result['pin_id'], result['pin_url'])
            
            logger.info(f"Successfully created Pinterest pin {result['pin_id']} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Background Pinterest pin creation failed: {e}")
            
            # Update pin record with error
            await self.db.execute("""
                UPDATE pinterest_pins SET
                    pin_status = 'failed',
                    status_message = $2,
                    error_details = $3
                WHERE id = $1
            """, pin_record_id, str(e), {"error": str(e), "timestamp": datetime.utcnow().isoformat()})
    
    async def get_pin_status(self, user_id: str, pin_record_id: str) -> Dict[str, Any]:
        """Get the status of a Pinterest pin creation"""
        try:
            pin = await self.db.fetchrow("""
                SELECT 
                    id, account_id, title, description, board_id, pin_id, pin_url,
                    pin_status, status_message, error_details,
                    created_at, completed_at,
                    video_reference_id, image_reference_ids
                FROM pinterest_pins
                WHERE id = $1 AND user_id = $2
            """, pin_record_id, user_id)
            
            if not pin:
                raise Exception("Pin not found")
            
            # Get account info
            account_info = await self.account_service.get_account(user_id, pin['account_id'])
            
            response = {
                "pin_record_id": pin['id'],
                "status": pin['pin_status'],
                "message": pin['status_message'],
                "title": pin['title'],
                "description": pin['description'],
                "board_id": pin['board_id'],
                "created_at": pin['created_at'].isoformat() if pin['created_at'] else None,
                "completed_at": pin['completed_at'].isoformat() if pin['completed_at'] else None,
                "account": {
                    "id": pin['account_id'],
                    "name": account_info.get("name", "Pinterest User") if account_info else "Pinterest User"
                }
            }
            
            # Add success details if completed
            if pin['pin_status'] == 'completed' and pin['pin_id']:
                response.update({
                    "pin_id": pin['pin_id'],
                    "pin_url": pin['pin_url'],
                    "platform": "pinterest"
                })
            
            # Add error details if failed
            if pin['pin_status'] == 'failed' and pin['error_details']:
                response["error_details"] = pin['error_details']
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to get Pinterest pin status: {e}")
            raise
    
    async def delete_pin(self, user_id: str, account_id: str, pin_id: str) -> Dict[str, Any]:
        """Delete a Pinterest pin"""
        try:
            # Validate account access
            if not await self.account_service.validate_account_access(user_id, account_id):
                raise ValueError("Invalid account or expired token")
            
            # Get valid access token
            access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
            
            # Delete via API
            success = await self.api_service.delete_pin(access_token, pin_id)
            
            if success:
                # Update database record
                await self.db.execute("""
                    UPDATE pinterest_pins SET
                        pin_status = 'deleted',
                        deleted_at = NOW()
                    WHERE user_id = $1 AND account_id = $2 AND pin_id = $3
                """, user_id, account_id, pin_id)
                
                return {
                    "success": True,
                    "message": f"Pinterest pin {pin_id} deleted successfully"
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to delete Pinterest pin {pin_id}"
                }
                
        except Exception as e:
            logger.error(f"Failed to delete Pinterest pin: {e}")
            raise
    
    async def get_recent_pins(self, user_id: str, account_id: str, limit: int = 10) -> Dict[str, Any]:
        """Get recent pins from Pinterest account"""
        try:
            # Get pins from database
            pins = await self.db.fetch("""
                SELECT 
                    id, pin_id, title, description, pin_url, pin_status,
                    created_at, completed_at, board_id
                FROM pinterest_pins
                WHERE user_id = $1 AND account_id = $2
                AND pin_status IN ('completed', 'pinning')
                ORDER BY created_at DESC
                LIMIT $3
            """, user_id, account_id, limit)
            
            # Format pins
            formatted_pins = []
            for pin in pins:
                formatted_pin = {
                    "id": pin['pin_id'],
                    "title": pin['title'],
                    "description": pin['description'],
                    "pin_url": pin['pin_url'],
                    "board_id": pin['board_id'],
                    "status": pin['pin_status'],
                    "created_at": pin['created_at'].isoformat() if pin['created_at'] else None,
                    "platform": "pinterest"
                }
                formatted_pins.append(formatted_pin)
            
            # Get account info
            account_info = await self.account_service.get_account(user_id, account_id)
            
            return {
                "success": True,
                "pins": formatted_pins,
                "count": len(formatted_pins),
                "account": {
                    "id": account_id,
                    "name": account_info.get("name", "Pinterest User") if account_info else "Pinterest User"
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get Pinterest recent pins: {e}")
            raise
    
    async def get_pin_analytics(self, user_id: str, account_id: str, pin_id: str) -> Dict[str, Any]:
        """Get analytics for a specific Pinterest pin"""
        try:
            # Validate account access
            if not await self.account_service.validate_account_access(user_id, account_id):
                raise ValueError("Invalid account or expired token")
            
            # Get valid access token
            access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
            
            # Get analytics from API
            analytics = await self.api_service.get_pin_analytics(access_token, pin_id)
            
            return {
                "success": True,
                "pin_id": pin_id,
                "analytics": analytics
            }
            
        except Exception as e:
            logger.error(f"Failed to get Pinterest pin analytics: {e}")
            raise
    
    async def get_account_boards(self, user_id: str, account_id: str) -> Dict[str, Any]:
        """Get boards for Pinterest account"""
        try:
            # Validate account access
            if not await self.account_service.validate_account_access(user_id, account_id):
                raise ValueError("Invalid account or expired token")
            
            # Get valid access token
            access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
            
            # Get boards from API
            boards = await self.api_service.get_boards(access_token)
            
            return {
                "success": True,
                "boards": boards,
                "count": len(boards),
                "account_id": account_id
            }
            
        except Exception as e:
            logger.error(f"Failed to get Pinterest account boards: {e}")
            raise
    
    async def create_board(self, user_id: str, account_id: str, name: str, 
                          description: str = "", privacy: str = "PUBLIC") -> Dict[str, Any]:
        """Create a new Pinterest board"""
        try:
            # Validate account access
            if not await self.account_service.validate_account_access(user_id, account_id):
                raise ValueError("Invalid account or expired token")
            
            # Get valid access token
            access_token = await self.oauth_handler.get_valid_token(user_id, account_id)
            
            # Create board via API
            result = await self.api_service.create_board(access_token, name, description, privacy)
            
            return {
                "success": True,
                "board": result
            }
            
        except Exception as e:
            logger.error(f"Failed to create Pinterest board: {e}")
            raise