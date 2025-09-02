# Smart Upload Detection System

## Overview
The system now intelligently detects when users want to upload to social media vs just attaching files for analysis. This prevents confusion and ensures files are routed correctly.

## How It Works

### 1. Intent Detection
The system analyzes user messages for upload intent:

**Upload Intent Keywords** (triggers reference system):
- `upload`, `post`, `publish`, `share`, `put on`
- `add to youtube`, `youtube video`, `send to youtube`
- `create video`, `make video`, `release`, `submit`
- Mentions of `youtube` or `yt`

**Non-Upload Keywords** (uses regular sandbox):
- `analyze`, `review`, `check`, `look at`, `examine`
- `tell me about`, `what is`, `explain`, `show me`
- `read`, `display`, `open`, `edit`, `modify`

### 2. File Routing

```
User Message Analysis
        ↓
   Intent Detection
        ↓
    ┌───────────┐
    │Upload Intent?│
    └─────┬─────┘
         / \
        /   \
      YES   NO
       ↓     ↓
Reference  Sandbox
 System    Storage
    ↓         ↓
Auto-     Regular
Discovery  Attachment
```

### 3. Implementation Components

#### Backend Components:
- **`youtube_tool.py`**: 
  - `_should_auto_discover_files()` - Detects upload intent
  - Only triggers auto-discovery when intent is clear

- **`youtube_mcp/upload.py`**:
  - Respects `auto_discover` flag
  - Only looks for files when explicitly needed

- **`youtube_file_service.py`**:
  - Stores files with reference IDs
  - Manages TTL and cleanup

#### Frontend Components:
- **`social-media-detection.ts`**: 
  - Client-side intent detection
  - Platform identification

- **`smart-file-handler.tsx`**:
  - Routes files based on intent
  - Creates reference IDs for social media

### 4. Examples

#### Upload Intent Detected ✅
```
User: "Please upload my video to YouTube"
→ Reference ID created
→ Auto-discovery enabled
→ Video uploaded

User: "Post this on my channel"
→ Reference ID created
→ Auto-discovery enabled
→ Video uploaded
```

#### No Upload Intent ❌
```
User: "Analyze this video for me"
→ Sandbox storage
→ No reference ID
→ File available for analysis

User: "What's in this file?"
→ Sandbox storage
→ No reference ID
→ AI can read/analyze file
```

## Benefits

1. **No Confusion**: System knows when you want to upload vs analyze
2. **No Manual Paths**: Upload intent triggers automatic discovery
3. **Privacy**: Files only uploaded to social media when explicitly requested
4. **Efficiency**: Regular attachments don't create unnecessary references

## Migration Applied

The database migration has been created and needs to be applied:

```bash
# Apply via Supabase Dashboard
1. Go to SQL Editor
2. Run: backend/supabase/migrations/20250824_update_reference_id_system.sql
```

## Testing

Run the test to verify detection logic:
```bash
cd backend
uv run test_smart_detection.py
```

## Usage

### For Users:
- **To Upload**: Use words like "upload", "post", "publish" with "YouTube"
- **To Analyze**: Just attach files normally without upload keywords

### For Developers:
- Intent detection happens automatically
- No UI changes needed
- System routes files intelligently based on context

## Current Status

✅ **Completed**:
- Intent detection logic implemented
- YouTube tool updated with smart discovery
- Upload service respects auto-discovery flag
- Test suite created and passing
- Frontend detection library created

⏳ **Pending**:
- Apply database migration
- Test with real uploads
- Monitor usage patterns

## Summary

The system now intelligently determines user intent:
- **"Upload this to YouTube"** → Creates reference ID → Auto-discovery works
- **"Look at this file"** → Regular attachment → No accidental uploads

This ensures files are only uploaded to social media when users explicitly want them to be, while maintaining the convenience of automatic discovery when appropriate.