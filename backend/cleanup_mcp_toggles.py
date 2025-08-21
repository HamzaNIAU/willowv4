#!/usr/bin/env python3
"""Script to clean up orphaned MCP toggles and ensure data consistency"""

import asyncio
import os
import sys
from datetime import datetime

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.supabase import DBConnection
from services.mcp_toggles import MCPToggleService
from youtube_mcp.channels import YouTubeChannelService
from utils.logger import logger


class MCPToggleCleanup:
    """Clean up and sync MCP toggles for social media connections"""
    
    def __init__(self):
        self.db = DBConnection()
        self.toggle_service = MCPToggleService(self.db)
        self.channel_service = YouTubeChannelService(self.db)
        self.stats = {
            "orphaned_removed": 0,
            "toggles_created": 0,
            "channels_processed": 0,
            "agents_processed": 0,
            "errors": 0
        }
    
    async def run_cleanup(self):
        """Run the full cleanup process"""
        logger.info("Starting MCP toggle cleanup...")
        
        # Step 1: Remove orphaned toggles
        await self.remove_orphaned_toggles()
        
        # Step 2: Create missing toggles
        await self.create_missing_toggles()
        
        # Step 3: Verify consistency
        await self.verify_consistency()
        
        # Print summary
        self.print_summary()
    
    async def remove_orphaned_toggles(self):
        """Remove toggles for non-existent channels"""
        logger.info("Removing orphaned toggles...")
        
        client = await self.db.client
        
        try:
            # Get all YouTube MCP toggles
            result = await client.table("agent_mcp_toggles").select("*").like(
                "mcp_id", "social.youtube.%"
            ).execute()
            
            for toggle in result.data:
                mcp_id = toggle["mcp_id"]
                channel_id = mcp_id.replace("social.youtube.", "")
                user_id = toggle["user_id"]
                
                # Check if channel exists
                channel_result = await client.table("youtube_channels").select("id").eq(
                    "id", channel_id
                ).eq("user_id", user_id).execute()
                
                if not channel_result.data:
                    # Channel doesn't exist, remove toggle
                    await client.table("agent_mcp_toggles").delete().eq(
                        "id", toggle["id"]
                    ).execute()
                    
                    self.stats["orphaned_removed"] += 1
                    logger.info(f"Removed orphaned toggle for channel {channel_id}")
            
            # Also remove toggles for non-existent agents
            result = await client.table("agent_mcp_toggles").select("*").execute()
            
            for toggle in result.data:
                agent_id = toggle["agent_id"]
                
                # Check if agent exists
                agent_result = await client.table("agents").select("agent_id").eq(
                    "agent_id", agent_id
                ).execute()
                
                if not agent_result.data:
                    # Agent doesn't exist, remove toggle
                    await client.table("agent_mcp_toggles").delete().eq(
                        "id", toggle["id"]
                    ).execute()
                    
                    self.stats["orphaned_removed"] += 1
                    logger.info(f"Removed orphaned toggle for agent {agent_id}")
                    
        except Exception as e:
            logger.error(f"Error removing orphaned toggles: {e}")
            self.stats["errors"] += 1
    
    async def create_missing_toggles(self):
        """Create toggles for channels that don't have them"""
        logger.info("Creating missing toggles...")
        
        client = await self.db.client
        
        try:
            # Get all active YouTube channels
            channels_result = await client.table("youtube_channels").select("*").eq(
                "is_active", True
            ).execute()
            
            for channel in channels_result.data:
                channel_id = channel["id"]
                user_id = channel["user_id"]
                mcp_id = f"social.youtube.{channel_id}"
                
                self.stats["channels_processed"] += 1
                
                # Get all agents for this user
                agents_result = await client.table("agents").select("agent_id").eq(
                    "account_id", user_id
                ).execute()
                
                for agent in agents_result.data:
                    agent_id = agent["agent_id"]
                    
                    # Check if toggle exists
                    toggle_result = await client.table("agent_mcp_toggles").select("id").eq(
                        "agent_id", agent_id
                    ).eq("user_id", user_id).eq("mcp_id", mcp_id).execute()
                    
                    if not toggle_result.data:
                        # Create toggle (disabled by default)
                        success = await self.toggle_service.set_toggle(
                            agent_id=agent_id,
                            user_id=user_id,
                            mcp_id=mcp_id,
                            enabled=False
                        )
                        
                        if success:
                            self.stats["toggles_created"] += 1
                            logger.info(f"Created toggle for agent {agent_id}, channel {channel_id}")
                        else:
                            self.stats["errors"] += 1
                    
                    self.stats["agents_processed"] += 1
                    
        except Exception as e:
            logger.error(f"Error creating missing toggles: {e}")
            self.stats["errors"] += 1
    
    async def verify_consistency(self):
        """Verify that all channels have proper toggles"""
        logger.info("Verifying data consistency...")
        
        client = await self.db.client
        
        try:
            # Count total expected toggles
            channels_result = await client.table("youtube_channels").select("id, user_id").eq(
                "is_active", True
            ).execute()
            
            expected_toggles = 0
            actual_toggles = 0
            
            for channel in channels_result.data:
                channel_id = channel["id"]
                user_id = channel["user_id"]
                mcp_id = f"social.youtube.{channel_id}"
                
                # Count agents for this user
                agents_result = await client.table("agents").select("agent_id").eq(
                    "account_id", user_id
                ).execute()
                
                expected_toggles += len(agents_result.data)
                
                # Count actual toggles
                toggles_result = await client.table("agent_mcp_toggles").select("id").eq(
                    "user_id", user_id
                ).eq("mcp_id", mcp_id).execute()
                
                actual_toggles += len(toggles_result.data)
            
            if expected_toggles == actual_toggles:
                logger.info(f"✓ Data consistency verified: {actual_toggles} toggles exist as expected")
            else:
                logger.warning(f"⚠ Data inconsistency: Expected {expected_toggles} toggles, found {actual_toggles}")
                self.stats["errors"] += 1
                
        except Exception as e:
            logger.error(f"Error verifying consistency: {e}")
            self.stats["errors"] += 1
    
    def print_summary(self):
        """Print cleanup summary"""
        print("\n" + "="*60)
        print("MCP TOGGLE CLEANUP SUMMARY")
        print("="*60)
        print(f"Orphaned toggles removed:  {self.stats['orphaned_removed']}")
        print(f"Missing toggles created:   {self.stats['toggles_created']}")
        print(f"Channels processed:        {self.stats['channels_processed']}")
        print(f"Agents processed:          {self.stats['agents_processed']}")
        print(f"Errors encountered:        {self.stats['errors']}")
        print("="*60)
        
        if self.stats["errors"] == 0:
            print("✓ Cleanup completed successfully!")
        else:
            print(f"⚠ Cleanup completed with {self.stats['errors']} errors")


async def main():
    """Run the cleanup"""
    cleanup = MCPToggleCleanup()
    
    print("\n" + "="*60)
    print("MCP TOGGLE CLEANUP UTILITY")
    print("="*60)
    print("This will:")
    print("1. Remove orphaned toggle entries")
    print("2. Create missing toggle entries")
    print("3. Verify data consistency")
    print("="*60)
    
    # Check for --auto flag to skip prompt
    if "--auto" in sys.argv:
        print("\nRunning in auto mode...")
    else:
        response = input("\nProceed with cleanup? (yes/no): ")
        if response.lower() != "yes":
            print("Cleanup cancelled")
            return
    
    await cleanup.run_cleanup()


if __name__ == "__main__":
    asyncio.run(main())