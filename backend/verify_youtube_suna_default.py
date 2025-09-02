#!/usr/bin/env python3
"""
Verification script for YouTube upload flow with suna-default agent.
Tests:
1. Channel detection for suna-default agent
2. Reference ID creation for file attachments
3. Upload flow completion
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

load_dotenv()

from services.supabase import DBConnection
from utils.logger import logger

async def verify_youtube_channels(user_id: str):
    """Verify YouTube channels are properly detected for suna-default"""
    logger.info("=" * 60)
    logger.info("VERIFYING YOUTUBE CHANNEL DETECTION")
    logger.info("=" * 60)
    
    try:
        db = DBConnection()
        client = await db.client
        
        # Check youtube_channels table (used by suna-default)
        logger.info(f"Checking youtube_channels table for user {user_id}...")
        result = await client.table("youtube_channels").select("*").eq(
            "user_id", user_id
        ).eq("is_active", True).execute()
        
        channels = result.data if result.data else []
        
        if channels:
            logger.info(f"✅ Found {len(channels)} active YouTube channel(s):")
            for channel in channels:
                logger.info(f"  - {channel.get('channel_name', 'Unknown')} (ID: {channel.get('channel_id', 'Unknown')})")
                logger.info(f"    Username: @{channel.get('username', 'N/A')}")
                logger.info(f"    Subscribers: {channel.get('subscriber_count', 0):,}")
        else:
            logger.warning("❌ No active YouTube channels found!")
            logger.info("Please connect channels via the Social Media page")
            
        return channels
        
    except Exception as e:
        logger.error(f"Error checking channels: {e}")
        return []

async def verify_reference_system(user_id: str):
    """Verify reference ID system is working"""
    logger.info("=" * 60)
    logger.info("VERIFYING REFERENCE ID SYSTEM")
    logger.info("=" * 60)
    
    try:
        db = DBConnection()
        client = await db.client
        
        # Check for recent reference IDs
        logger.info(f"Checking video_file_references table...")
        result = await client.table("video_file_references").select("*").eq(
            "user_id", user_id
        ).order("created_at", desc=True).limit(5).execute()
        
        references = result.data if result.data else []
        
        if references:
            logger.info(f"✅ Found {len(references)} recent reference(s):")
            for ref in references:
                logger.info(f"  - Reference ID: {ref.get('reference_id', 'Unknown')[:8]}...")
                logger.info(f"    File Type: {ref.get('file_type', 'Unknown')}")
                logger.info(f"    Created: {ref.get('created_at', 'Unknown')}")
                logger.info(f"    Expires: {ref.get('expires_at', 'Unknown')}")
        else:
            logger.info("ℹ️ No reference IDs found (normal if no files uploaded recently)")
            
        return references
        
    except Exception as e:
        logger.error(f"Error checking references: {e}")
        return []

async def verify_upload_references(user_id: str):
    """Verify upload references table"""
    logger.info("=" * 60)
    logger.info("VERIFYING UPLOAD REFERENCES")
    logger.info("=" * 60)
    
    try:
        db = DBConnection()
        client = await db.client
        
        # Check for recent uploads
        logger.info(f"Checking upload_references table...")
        result = await client.table("upload_references").select("*").eq(
            "user_id", user_id
        ).order("created_at", desc=True).limit(5).execute()
        
        uploads = result.data if result.data else []
        
        if uploads:
            logger.info(f"✅ Found {len(uploads)} recent upload(s):")
            for upload in uploads:
                logger.info(f"  - Upload ID: {upload.get('upload_id', 'Unknown')[:8]}...")
                logger.info(f"    Platform: {upload.get('platform', 'Unknown')}")
                logger.info(f"    Status: {upload.get('status', 'Unknown')}")
                logger.info(f"    Video ID: {upload.get('metadata', {}).get('video_id', 'Not yet available')}")
                logger.info(f"    Created: {upload.get('created_at', 'Unknown')}")
        else:
            logger.info("ℹ️ No uploads found (normal if no uploads attempted recently)")
            
        return uploads
        
    except Exception as e:
        logger.error(f"Error checking uploads: {e}")
        return []

async def main():
    """Main verification function"""
    # Get user ID from environment or prompt
    user_id = os.getenv("TEST_USER_ID")
    
    if not user_id:
        logger.error("Please set TEST_USER_ID in .env file")
        logger.info("You can find your user ID by running:")
        logger.info("  SELECT id FROM auth.users WHERE email = 'your-email@example.com';")
        return
    
    logger.info(f"Running verification for user: {user_id}")
    logger.info("")
    
    # Run verifications
    channels = await verify_youtube_channels(user_id)
    logger.info("")
    
    references = await verify_reference_system(user_id)
    logger.info("")
    
    uploads = await verify_upload_references(user_id)
    logger.info("")
    
    # Summary
    logger.info("=" * 60)
    logger.info("VERIFICATION SUMMARY")
    logger.info("=" * 60)
    
    if channels:
        logger.info("✅ YouTube channels: CONFIGURED")
    else:
        logger.warning("❌ YouTube channels: NOT CONFIGURED")
        
    if references:
        logger.info("✅ Reference IDs: FOUND")
    else:
        logger.info("ℹ️ Reference IDs: NONE (attach files to create)")
        
    if uploads:
        logger.info("✅ Upload history: FOUND")
    else:
        logger.info("ℹ️ Upload history: NONE (upload videos to create)")
    
    logger.info("")
    logger.info("Verification complete!")
    
    # Provide next steps
    if not channels:
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Go to the Social Media page")
        logger.info("2. Click 'Connect YouTube Account'")
        logger.info("3. Authorize your YouTube channels")
        logger.info("4. Run this script again to verify")

if __name__ == "__main__":
    asyncio.run(main())