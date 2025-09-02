# Universal Social Media Upload System

## Overview
A platform-agnostic system that intelligently handles file uploads for **all social media platforms**, not just YouTube. The system automatically detects compatible platforms, validates files against platform requirements, and routes uploads appropriately.

## ✨ Key Features

### 1. **Universal Platform Support**
- YouTube, TikTok, Instagram, Twitter/X, Facebook, LinkedIn
- Snapchat, Pinterest, Reddit, Discord
- Easy to add new platforms

### 2. **Smart Intent Detection**
Detects which platform user wants based on context:
- "Upload to YouTube" → YouTube
- "Post on TikTok" → TikTok
- "Share on Instagram" → Instagram
- Generic "upload" → All compatible platforms

### 3. **Automatic Compatibility Detection**
System automatically determines which platforms support your file:
```
Video (16:9, 50MB MP4) → Compatible: YouTube ✓, Facebook ✓, LinkedIn ✓
Video (9:16, 10MB MP4) → Compatible: TikTok ✓, Instagram Reels ✓, YouTube Shorts ✓
Image (1:1, 2MB JPG) → Compatible: All platforms ✓
```

### 4. **Platform Requirements Validation**
Each platform has specific requirements stored in database:
- Max file sizes
- Supported formats
- Duration limits
- Aspect ratios

## 📊 Database Schema

### Main Tables

#### `social_media_file_references`
Universal file storage for all platforms:
```sql
- id: 32-char reference ID
- file_data: Binary data (BYTEA)
- platform: Target platform (optional)
- file_type: video/image/audio/document
- detected_platforms: Array of compatible platforms
- dimensions: {width, height}
- duration_seconds: For videos/audio
```

#### `upload_references`
Tracks upload queue:
```sql
- reference_id: Links to file
- intended_platform: User's target
- detected_platforms: All compatible
- status: pending/ready/used/expired
- used_for_platform: Which platform consumed it
```

#### `platform_file_requirements`
Platform-specific requirements:
```sql
- platform: Platform name
- max_video_size_mb
- supported_formats
- aspect_ratios
- special_requirements
```

## 🔄 How It Works

### Upload Flow
```
1. User uploads file with message
   ↓
2. Intent detection identifies platform
   ↓
3. File validated against requirements
   ↓
4. Compatible platforms detected
   ↓
5. Reference ID created
   ↓
6. File ready for any compatible platform
```

### Intent Detection Logic
```python
# Positive signals (triggers upload)
"upload to [platform]" → Upload
"post on [platform]" → Upload
"share this video" → Upload

# Negative signals (regular attachment)
"analyze this" → Sandbox
"review this file" → Sandbox
"check this video" → Sandbox
```

## 🚀 API Endpoints

### Universal Endpoints

#### `POST /api/social-media/prepare-upload`
Prepare file for any platform:
```json
{
  "file": <binary>,
  "platform": "instagram",  // Optional
  "file_type": "video"      // Optional auto-detect
}
```

Response:
```json
{
  "reference_id": "abc123...",
  "compatible_platforms": ["instagram", "tiktok", "youtube"],
  "intended_platform": "instagram",
  "expires_at": "2024-08-25T..."
}
```

#### `GET /api/social-media/pending-uploads`
Get pending uploads, optionally filtered:
```
/api/social-media/pending-uploads?platform=tiktok
```

#### `GET /api/social-media/platform-requirements`
Get requirements for all or specific platform:
```
/api/social-media/platform-requirements?platform=instagram
```

### Platform-Specific Endpoints (existing)
- `/api/youtube/upload` - YouTube uploads
- `/api/tiktok/upload` - TikTok uploads (when implemented)
- `/api/instagram/upload` - Instagram uploads (when implemented)

## 🎯 Platform Detection

### Automatic Platform Detection
Based on file characteristics:

| File Type | Size | Aspect Ratio | Duration | Compatible Platforms |
|-----------|------|--------------|----------|---------------------|
| Video MP4 | 50MB | 16:9 | 2 min | YouTube, Facebook, LinkedIn, Twitter |
| Video MP4 | 10MB | 9:16 | 30 sec | TikTok, Instagram Reels, YouTube Shorts |
| Image JPG | 2MB | 1:1 | - | All platforms |
| Video MP4 | 500MB | 16:9 | 10 min | YouTube, Facebook |

## 🛠️ Implementation

### Backend Services

#### `SocialMediaFileService`
Universal file service for all platforms:
```python
service = SocialMediaFileService(db)

# Create reference for any platform
result = await service.create_file_reference(
    user_id=user_id,
    file_name="video.mp4",
    file_data=data,
    platform="tiktok"  # Optional
)

# Auto-discovers compatible platforms
print(result["compatible_platforms"])
# ["tiktok", "instagram", "youtube_shorts"]
```

#### Platform Validation
```python
is_valid, errors = service.validate_file_for_platform(
    file_data=data,
    platform="instagram",
    file_type="video"
)
```

### Frontend Detection
```typescript
import { detectSocialMediaIntent } from '@/lib/social-media-detection';

const intent = detectSocialMediaIntent(
    message,
    file.type,
    file.name
);

if (intent.detected) {
    // Use reference system
    platform = intent.platform;  // "instagram", "tiktok", etc.
}
```

## 🔮 Future Platform Support

Adding a new platform is simple:

1. **Add to platform_file_requirements table:**
```sql
INSERT INTO platform_file_requirements VALUES (
    'new_platform',
    max_sizes,
    formats,
    ...
);
```

2. **Add detection keywords:**
```typescript
SOCIAL_PLATFORMS.new_platform = ['keywords'];
```

3. **Implement upload endpoint:**
```python
@router.post("/new_platform/upload")
async def upload_to_new_platform(...):
    # Platform-specific logic
```

## 🚦 Migration Status

### ✅ Completed
- Universal database schema
- Platform-agnostic file service
- Multi-platform intent detection
- Compatibility validation
- Universal API endpoints

### ⏳ Ready to Apply
Run the migration:
```sql
-- File: backend/supabase/migrations/20250824_update_reference_id_system.sql
-- This creates universal tables that work for ALL platforms
```

## 📝 Examples

### User Scenarios

#### Scenario 1: Explicit Platform
```
User: "Upload this to TikTok"
System: Creates reference → Validates for TikTok → Ready for upload
```

#### Scenario 2: Multiple Platforms
```
User: "Post this video on my socials"
System: Detects all compatible platforms → Creates reference → Available for all
```

#### Scenario 3: Auto-Detection
```
User: Uploads 9:16 vertical video
System: Detects → Compatible with TikTok, Instagram Reels, YouTube Shorts
```

#### Scenario 4: No Upload Intent
```
User: "Analyze this video for me"
System: Regular sandbox storage → No reference ID → No social media routing
```

## 🔧 Testing

Test the universal system:
```bash
# Test detection
python test_smart_detection.py

# Test file service
python test_social_media_service.py
```

## 🎉 Benefits

1. **One System, All Platforms**: No need for separate implementations
2. **Future-Proof**: Easy to add new platforms
3. **Smart Routing**: Files go to right place automatically
4. **User-Friendly**: Works with natural language
5. **Efficient**: Only creates references when needed
6. **Validated**: Ensures files meet platform requirements

## Summary

This universal system replaces platform-specific implementations with a single, intelligent system that:
- Works with **all social media platforms**
- **Automatically detects** compatible platforms
- **Validates** against platform requirements
- **Routes intelligently** based on user intent
- **Scales easily** to new platforms

The migration is ready to apply and will work seamlessly with your existing YouTube implementation while enabling support for all other platforms!