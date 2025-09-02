#!/usr/bin/env python3
"""
Utility script to auto-enable connected YouTube channels for all users.
This fixes the issue where channels were disabled by default.

Usage: 
    python fix_youtube_channels.py                    # Fix all users
    python fix_youtube_channels.py --user-id USER_ID  # Fix specific user
"""

import asyncio
import os
import argparse
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.supabase import DBConnection
from services.mcp_toggles import MCPToggleService
from utils.logger import logger


async def fix_user_channels(user_id: str, toggle_service: MCPToggleService) -> int:
    """Fix YouTube channels for a specific user"""
    try:
        enabled_count = await toggle_service.auto_enable_connected_channels(user_id)
        if enabled_count > 0:
            print(f"✅ Fixed {enabled_count} channel-agent pairs for user {user_id}")
        else:
            print(f"ℹ️  No channels to fix for user {user_id}")
        return enabled_count
    except Exception as e:
        print(f"❌ Error fixing channels for user {user_id}: {e}")
        return 0


async def fix_all_users():
    """Fix YouTube channels for all users"""
    print("🔧 Starting YouTube channel auto-enable fix...")
    
    try:
        # Initialize services
        db = DBConnection()
        await db.initialize()
        toggle_service = MCPToggleService(db)
        
        # Get all users who have YouTube channels
        client = await db.client
        result = await client.table("youtube_channels").select("user_id").eq(
            "is_active", True
        ).execute()
        
        if not result.data:
            print("ℹ️  No YouTube channels found.")
            return
        
        # Get unique user IDs
        user_ids = list(set(row["user_id"] for row in result.data))
        print(f"📋 Found {len(user_ids)} users with YouTube channels")
        
        total_fixed = 0
        for i, user_id in enumerate(user_ids, 1):
            print(f"[{i}/{len(user_ids)}] Processing user {user_id}...")
            fixed_count = await fix_user_channels(user_id, toggle_service)
            total_fixed += fixed_count
        
        print(f"\n🎉 Done! Fixed {total_fixed} total channel-agent pairs across {len(user_ids)} users")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return


async def fix_specific_user(user_id: str):
    """Fix YouTube channels for a specific user"""
    print(f"🔧 Fixing YouTube channels for user {user_id}...")
    
    try:
        # Initialize services
        db = DBConnection()
        await db.initialize()
        toggle_service = MCPToggleService(db)
        
        fixed_count = await fix_user_channels(user_id, toggle_service)
        
        if fixed_count > 0:
            print(f"\n🎉 Successfully fixed {fixed_count} channel-agent pairs!")
        else:
            print("\nℹ️  No channels needed fixing.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return


async def main():
    parser = argparse.ArgumentParser(description="Fix YouTube channel auto-enable for users")
    parser.add_argument("--user-id", help="Fix channels for a specific user ID")
    
    args = parser.parse_args()
    
    if args.user_id:
        await fix_specific_user(args.user_id)
    else:
        await fix_all_users()


if __name__ == "__main__":
    asyncio.run(main())