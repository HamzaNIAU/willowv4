#!/usr/bin/env python3
"""YouTube Upload Script for Sandbox Execution"""

import os
import sys
import json
import argparse
import requests
from datetime import datetime, timezone

def get_oauth_token(user_id, channel_id, backend_url, jwt_token):
    """Get OAuth token for YouTube API from backend"""
    try:
        headers = {"Authorization": f"Bearer {jwt_token}"}
        response = requests.get(f"{backend_url}/api/youtube/token/{channel_id}", headers=headers)
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print(f"ERROR: Failed to get OAuth token: {response.status_code}")
            return None
    except Exception as e:
        print(f"ERROR: Exception getting OAuth token: {e}")
        return None

def download_video_file(ref_id, backend_url, jwt_token, output_path):
    """Download video file from backend to workspace"""
    try:
        headers = {"Authorization": f"Bearer {jwt_token}"}
        response = requests.get(f"{backend_url}/api/youtube/file/{ref_id}", headers=headers, stream=True)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        else:
            print(f"ERROR: Failed to download file: {response.status_code}")
            return False
    except Exception as e:
        print(f"ERROR: Exception downloading file: {e}")
        return False

def upload_to_youtube(video_path, title, description, tags, privacy, channel_id, access_token):
    """Upload video to YouTube using Google API"""
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2.credentials import Credentials
        
        # Create credentials
        credentials = Credentials(token=access_token)
        youtube = build('youtube', 'v3', credentials=credentials)
        
        # Prepare video metadata
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': '22'
            },
            'status': {
                'privacyStatus': privacy,
                'madeForKids': False
            }
        }
        
        # Create media upload
        media = MediaFileUpload(video_path, resumable=True, chunksize=1024*1024)
        
        # Execute upload
        insert_request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = insert_request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"PROGRESS: {progress}%")
        
        video_id = response['id']
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        return {
            "success": True,
            "video_id": video_id,
            "video_url": video_url,
            "title": title,
            "message": f"Successfully uploaded '{title}' to YouTube"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to upload to YouTube: {str(e)}"
        }

def main():
    parser = argparse.ArgumentParser(description="Upload video to YouTube")
    parser.add_argument("--title", required=True, help="Video title")
    parser.add_argument("--description", default="", help="Video description")
    parser.add_argument("--tags", default="[]", help="Video tags as JSON array")
    parser.add_argument("--privacy", default="public", help="Privacy setting")
    parser.add_argument("--channel_id", required=True, help="YouTube channel ID")
    parser.add_argument("--video_ref_id", required=True, help="Video reference ID")
    
    args = parser.parse_args()
    
    # Get environment variables
    backend_url = os.getenv("BACKEND_URL")
    user_id = os.getenv("USER_ID")
    jwt_token = os.getenv("JWT_TOKEN")
    
    if not all([backend_url, user_id, jwt_token]):
        result = {"success": False, "error": "Missing environment variables"}
        print(json.dumps(result))
        sys.exit(1)
    
    # Get OAuth token
    access_token = get_oauth_token(user_id, args.channel_id, backend_url, jwt_token)
    if not access_token:
        result = {"success": False, "error": "Failed to get OAuth token"}
        print(json.dumps(result))
        sys.exit(1)
    
    # Download video file
    video_path = f"/workspace/temp_video_{args.video_ref_id}.mp4"
    if not download_video_file(args.video_ref_id, backend_url, jwt_token, video_path):
        result = {"success": False, "error": "Failed to download video file"}
        print(json.dumps(result))
        sys.exit(1)
    
    # Parse tags
    try:
        tags = json.loads(args.tags)
    except:
        tags = []
    
    # Upload to YouTube
    result = upload_to_youtube(
        video_path, 
        args.title, 
        args.description, 
        tags, 
        args.privacy, 
        args.channel_id, 
        access_token
    )
    
    # Clean up temporary file
    try:
        os.remove(video_path)
    except:
        pass
    
    # Output structured result
    print(json.dumps(result))
    
    if result["success"]:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()