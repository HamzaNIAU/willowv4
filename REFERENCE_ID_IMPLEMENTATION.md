# YouTube Reference ID System - Implementation Complete

## Overview
The reference ID system from your Morphic project has been successfully implemented in Willow/Kortix. This system allows users to upload video files and the AI automatically discovers and uses them for YouTube uploads.

## What Was Implemented

### 1. Database Schema Updates
**File:** `backend/supabase/migrations/20250824_update_reference_id_system.sql`
- Added `file_data BYTEA` column to store actual binary data
- Updated table structure to match Morphic schema
- Added proper indexes and constraints
- Implemented cleanup functions for expired references

### 2. YouTubeFileService Updates
**File:** `backend/services/youtube_file_service.py`

#### Updated Methods:
- **`create_video_reference()`**: Now stores binary data directly in database
- **`create_thumbnail_reference()`**: Stores processed thumbnail data in database
- **`get_file_data()`**: Retrieves actual binary data from database (not filesystem)
- **`get_latest_pending_uploads()`**: Looks for "ready" status uploads
- **`cleanup_expired_references()`**: Properly cleans up expired, unused references

#### Key Changes:
- Reference IDs are 32-character hex strings (`secrets.token_hex(16)`)
- Files are stored as BYTEA in PostgreSQL
- Status tracking: `pending` → `ready` → `used` → `expired`
- 24-hour TTL for unused references

### 3. API Endpoints (Already Existed)
**File:** `backend/youtube_mcp/api.py`
- `/youtube/prepare-upload` - Upload video files and get reference ID
- `/youtube/prepare-thumbnail` - Upload thumbnail and get reference ID
- `/youtube/upload` - Upload to YouTube (auto-discovers files)

### 4. YouTube Tool Integration
**File:** `backend/agent/tools/youtube_tool.py`
- Already accepts `video_reference_id` and `thumbnail_reference_id` parameters
- Auto-discovery works when parameters are not provided

### 5. Frontend Integration
**File:** `frontend/src/components/thread/chat-input/youtube-upload-handler.tsx`
- Already calls `/youtube/prepare-upload` endpoint
- Handles file uploads and reference ID creation

## How It Works

### Upload Flow:
1. **User uploads file** → Frontend sends to `/youtube/prepare-upload`
2. **Backend creates reference** → Generates 32-char hex ID, stores binary data
3. **Returns reference ID** → User gets ID and expiration time
4. **AI auto-discovers** → When uploading, finds latest ready uploads
5. **Marks as used** → Prevents reuse of same file
6. **Cleanup** → Expired, unused references deleted after 24 hours

### Auto-Discovery Logic:
```python
# If no reference ID provided, automatically find latest uploads
if not video_reference_id:
    uploads = await file_service.get_latest_pending_uploads(user_id)
    if uploads["video"]:
        video_reference_id = uploads["video"]["reference_id"]
```

## Testing
**File:** `backend/test_reference_system.py`
- Tests complete flow from upload to retrieval
- Verifies data integrity
- Checks auto-discovery
- Tests reference lifecycle

Run test:
```bash
cd backend
python test_reference_system.py
```

## Migration Steps

1. **Apply Database Migration:**
```bash
# Via Supabase CLI
supabase db push

# Or via Supabase Dashboard
# Upload: backend/supabase/migrations/20250824_update_reference_id_system.sql
```

2. **Restart Services:**
```bash
python start.py
```

3. **Test Upload Flow:**
- Upload a video file
- Check that reference ID is created
- Use YouTube tool without specifying reference
- Verify auto-discovery works

## Benefits

✅ **Secure**: Non-guessable 32-character IDs  
✅ **Automatic**: AI discovers uploads without manual paths  
✅ **User-scoped**: Each user only sees their own uploads  
✅ **TTL Management**: Auto-cleanup after 24 hours  
✅ **Binary Storage**: Files stored directly in database  
✅ **Status Tracking**: Clear lifecycle (ready → used → expired)  

## Usage Example

### User uploads video:
```
User: "Upload my latest video to YouTube"
AI: "I'll help you upload your video. First, please attach the video file."
[User attaches video.mp4]
[System creates reference: a1b2c3d4e5f6...]
AI: "Video prepared! Now uploading to YouTube..."
[AI auto-discovers reference and uploads]
```

### Direct upload with existing file:
```
User: "I already uploaded a video, please post it to YouTube with title 'My Amazing Video'"
[AI checks for recent uploads, finds reference]
AI: "Found your recent video upload. Publishing to YouTube with title 'My Amazing Video'..."
```

## Next Steps

1. **Monitor Usage**: Check Supabase logs for reference creation/cleanup
2. **Adjust TTL**: Currently 24 hours, can be modified in `create_video_reference()`
3. **Add Metrics**: Track upload success rates and auto-discovery usage
4. **Optimize Storage**: Consider moving to object storage for very large files

## Troubleshooting

### If auto-discovery doesn't work:
1. Check that status is "ready" not "pending"
2. Verify expires_at is in the future
3. Ensure user_id matches

### If data retrieval fails:
1. Check that file_data column exists in database
2. Verify binary data was stored (not null)
3. Check Supabase connection and permissions

## Summary
The reference ID system is now fully implemented and matches the functionality from your Morphic project. Users can upload files, get reference IDs, and the AI will automatically discover and use them for YouTube uploads without requiring manual file path management.