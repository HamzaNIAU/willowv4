#!/usr/bin/env python3
"""Migration script to upgrade Fernet encrypted tokens to AES-256-CBC"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Any

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.supabase import DBConnection
from services.encryption_service import EncryptionService
from utils.logger import logger


class EncryptionMigration:
    """Migrate YouTube tokens from Fernet to AES-256-CBC encryption"""
    
    def __init__(self):
        self.db = DBConnection()
        self.encryption = EncryptionService()
        self.stats = {
            "total": 0,
            "migrated": 0,
            "skipped": 0,
            "failed": 0
        }
    
    async def migrate_youtube_channels(self):
        """Migrate all YouTube channel tokens"""
        logger.info("Starting YouTube channel token migration...")
        
        client = await self.db.client
        
        # Get all YouTube channels with tokens
        result = await client.table("youtube_channels").select("*").execute()
        
        if not result.data:
            logger.info("No YouTube channels found")
            return
        
        channels = result.data
        self.stats["total"] = len(channels)
        logger.info(f"Found {len(channels)} YouTube channels to migrate")
        
        for channel in channels:
            await self.migrate_channel(channel)
        
        # Print summary
        logger.info("=" * 50)
        logger.info("Migration Summary:")
        logger.info(f"Total channels: {self.stats['total']}")
        logger.info(f"Successfully migrated: {self.stats['migrated']}")
        logger.info(f"Skipped (already migrated): {self.stats['skipped']}")
        logger.info(f"Failed: {self.stats['failed']}")
    
    async def migrate_channel(self, channel: Dict[str, Any]):
        """Migrate a single channel's tokens"""
        channel_id = channel["id"]
        user_id = channel["user_id"]
        
        try:
            # Check if already migrated (AES tokens start with version byte 0x01)
            access_token = channel.get("access_token")
            refresh_token = channel.get("refresh_token")
            
            if not access_token:
                logger.warning(f"Channel {channel_id} has no access token, skipping")
                self.stats["skipped"] += 1
                return
            
            # Try to decrypt and check format
            try:
                import base64
                decoded = base64.b64decode(access_token)
                if decoded[0] == 1:  # Already AES encrypted
                    logger.info(f"Channel {channel_id} already migrated")
                    self.stats["skipped"] += 1
                    return
            except:
                pass  # Continue with migration
            
            # Migrate access token
            logger.info(f"Migrating channel {channel_id} for user {user_id}")
            
            new_access_token = None
            new_refresh_token = None
            
            # Migrate access token
            try:
                new_access_token = self.encryption.migrate_from_fernet(access_token)
            except Exception as e:
                logger.error(f"Failed to migrate access token for channel {channel_id}: {e}")
                self.stats["failed"] += 1
                return
            
            # Migrate refresh token if exists
            if refresh_token:
                try:
                    new_refresh_token = self.encryption.migrate_from_fernet(refresh_token)
                except Exception as e:
                    logger.warning(f"Failed to migrate refresh token for channel {channel_id}: {e}")
                    # Continue with just access token migration
            
            # Update database
            client = await self.db.client
            update_data = {
                "access_token": new_access_token,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "encryption_version": "aes-256-cbc"  # Add version marker
            }
            
            if new_refresh_token:
                update_data["refresh_token"] = new_refresh_token
            
            result = await client.table("youtube_channels").update(update_data).eq(
                "id", channel_id
            ).eq("user_id", user_id).execute()
            
            if result.data:
                logger.info(f"✓ Successfully migrated channel {channel_id}")
                self.stats["migrated"] += 1
            else:
                logger.error(f"Failed to update channel {channel_id} in database")
                self.stats["failed"] += 1
                
        except Exception as e:
            logger.error(f"Error migrating channel {channel_id}: {e}")
            self.stats["failed"] += 1
    
    async def verify_migration(self):
        """Verify that migration was successful by testing decryption"""
        logger.info("\nVerifying migration...")
        
        client = await self.db.client
        
        # Get a sample of migrated channels
        result = await client.table("youtube_channels").select("*").eq(
            "encryption_version", "aes-256-cbc"
        ).limit(5).execute()
        
        if not result.data:
            logger.warning("No migrated channels found to verify")
            return
        
        logger.info(f"Testing {len(result.data)} migrated channels...")
        
        for channel in result.data:
            try:
                # Try to decrypt tokens
                access_token = self.encryption.decrypt(channel["access_token"])
                
                if channel.get("refresh_token"):
                    refresh_token = self.encryption.decrypt(channel["refresh_token"])
                
                logger.info(f"✓ Channel {channel['id']}: Decryption successful")
                
            except Exception as e:
                logger.error(f"✗ Channel {channel['id']}: Decryption failed - {e}")
    
    async def rollback(self):
        """Rollback migration (requires backup)"""
        logger.warning("Rollback requires a database backup")
        logger.warning("Please restore from backup if migration failed")
        # In production, you would implement proper rollback logic here


async def main():
    """Run the migration"""
    migration = EncryptionMigration()
    
    # Check for master key
    if not os.getenv("YOUTUBE_ENCRYPTION_MASTER_KEY"):
        logger.error("YOUTUBE_ENCRYPTION_MASTER_KEY not set!")
        logger.info("Generate a key with: python -c 'import os, base64; print(base64.b64encode(os.urandom(32)).decode())'")
        return
    
    # Check for Fernet key (needed for migration)
    if not os.getenv("MCP_CREDENTIAL_ENCRYPTION_KEY"):
        logger.error("MCP_CREDENTIAL_ENCRYPTION_KEY not set!")
        logger.info("This is needed to decrypt existing Fernet tokens")
        return
    
    print("\n" + "=" * 50)
    print("YouTube Token Encryption Migration")
    print("Fernet → AES-256-CBC")
    print("=" * 50 + "\n")
    
    print("This will migrate all YouTube channel tokens to AES-256-CBC encryption.")
    print("Make sure you have a database backup before proceeding!")
    
    response = input("\nContinue with migration? (yes/no): ")
    if response.lower() != "yes":
        print("Migration cancelled")
        return
    
    # Run migration
    await migration.migrate_youtube_channels()
    
    # Verify
    await migration.verify_migration()
    
    print("\nMigration complete!")


if __name__ == "__main__":
    asyncio.run(main())