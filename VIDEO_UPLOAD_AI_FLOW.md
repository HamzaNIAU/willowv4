# Video & Thumbnail Detection and Upload Flow

## Overview

Morphic implements an intelligent file detection system that automatically identifies video and thumbnail files for YouTube uploads. The system uses MIME type detection, automatic file pairing, and a reference-based tracking system to seamlessly handle multi-file uploads.

## Core Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   User File Upload                           │
│  (Drag & Drop / File Input / API Upload)                    │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│              File Type Detection Layer                       │
│  • MIME Type Analysis (video/* vs image/*)                 │
│  • File Extension Validation                                │
│  • Automatic Categorization as 'video' or 'thumbnail'      │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│           Reference ID Generation & Storage                  │
│  • 32-character hex ID (crypto.randomBytes)                │
│  • MongoDB UploadReference with fileType field             │
│  • 30-minute expiration for quick uploads                  │
│  • 24-hour expiration for prepared uploads                 │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│          Automatic File Pairing System                       │
│  • getLatestPendingUploads() finds recent files            │
│  • Automatically pairs latest video + thumbnail            │
│  • No manual linking required                              │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│               YouTube Upload Execution                       │
│  • Retrieves both files via reference IDs                  │
│  • Uploads video first, then thumbnail                     │
│  • Progress tracking for both operations                   │
└─────────────────────────────────────────────────────────────┘
```

## File Detection System

### 1. MIME Type Detection

The system automatically categorizes files based on their MIME type:

```typescript
// Video Detection
const VIDEO_MIMETYPES = [
  'video/mp4',
  'video/quicktime',
  'video/x-msvideo',
  'video/x-ms-wmv',
  'video/x-flv',
  'video/x-matroska',
  'video/webm',
  'video/x-m4v',
  'video/3gpp',
  'video/3gpp2'
]

// Thumbnail Detection
const IMAGE_MIMETYPES = [
  'image/jpeg',
  'image/jpg',
  'image/png',
  'image/gif',
  'image/webp'
]

// Automatic categorization
function detectFileType(file: File): 'video' | 'thumbnail' {
  if (file.type.startsWith('video/')) {
    return 'video'
  }
  if (file.type.startsWith('image/')) {
    return 'thumbnail'
  }
  throw new Error('Unsupported file type')
}
```

### 2. Upload Reference Schema

Each uploaded file is tracked with a categorized reference:

```typescript
interface UploadReference {
  userId: string              // Owner identification
  referenceId: string         // 32-char hex ID
  fileName: string            // Original filename
  fileSize: string            // Human-readable size
  fileType: 'video' | 'thumbnail'  // ← KEY FIELD FOR DETECTION
  mimeType: string            // Exact MIME type
  videoReferenceId?: string   // Links thumbnail to video
  status: 'pending' | 'used' | 'expired'
  createdAt: Date
  expiresAt: Date            // Auto-cleanup time
}
```

### 3. Automatic File Discovery

The system's intelligent discovery mechanism:

```typescript
// MongoDB static method that finds the latest files
UploadReferenceSchema.statics.getLatestPendingUploads = async function(userId: string) {
  // Get last 10 pending uploads for the user
  const uploads = await this.find({
    userId,
    status: 'pending',
    expiresAt: { $gt: new Date() }
  }).sort({ createdAt: -1 }).limit(10)

  // Automatically find the most recent video
  const video = uploads.find(u => u.fileType === 'video')
  
  // Automatically find the most recent thumbnail
  const thumbnail = uploads.find(u => u.fileType === 'thumbnail')

  return { video, thumbnail }
}
```

**Key Points:**
- No manual pairing needed - system finds latest of each type
- Works even if files uploaded at different times
- Automatically ignores expired or used files

## Upload Flow

### Step 1: Video Upload

```typescript
// User uploads video via drag & drop or file input
POST /api/youtube/prepare-upload
FormData: { file: video.mp4 }

// System detects video type
if (file.type.startsWith('video/')) {
  // Create reference with fileType: 'video'
  await UploadReferenceModel.create({
    userId: user.id,
    referenceId: crypto.randomBytes(16).toString('hex'),
    fileName: file.name,
    fileSize: formatBytes(file.size),
    fileType: 'video',  // ← Marked as video
    mimeType: file.type,
    status: 'pending'
  })
}

// Response
{
  referenceId: "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
  fileName: "video.mp4",
  fileSize: "125.5 MB"
}
```

### Step 2: Thumbnail Upload (Optional)

```typescript
// User uploads thumbnail
POST /api/youtube/prepare-thumbnail
FormData: { file: thumbnail.jpg }

// System detects image type
if (file.type.startsWith('image/')) {
  // Process and optimize image
  const processed = await ThumbnailProcessor.processImage(file)
  
  // Create reference with fileType: 'thumbnail'
  await UploadReferenceModel.create({
    userId: user.id,
    referenceId: processed.referenceId,
    fileName: file.name,
    fileSize: formatFileSize(processed.size),
    fileType: 'thumbnail',  // ← Marked as thumbnail
    mimeType: 'image/jpeg',
    status: 'pending'
  })
}

// Response
{
  referenceId: "q1w2e3r4t5y6u7i8o9p0a1s2d3f4g5h6",
  fileName: "thumbnail.jpg",
  dimensions: { width: 1280, height: 720 }
}
```

### Step 3: AI Tool Execution

The upload tool automatically finds both files:

```typescript
// In upload_video tool
execute: async ({ channel_id, title, description }) => {
  // Get current user
  const user = await currentUser()
  
  // ✨ AUTOMATIC DETECTION - finds latest video and thumbnail
  const uploads = await UploadReferenceModel.getLatestPendingUploads(user.id)
  
  if (!uploads.video) {
    throw new Error('No video file found. Please upload a video file first.')
  }
  
  // Extract reference IDs
  const videoReferenceId = uploads.video.referenceId
  const thumbnailReferenceId = uploads.thumbnail?.referenceId  // Optional
  
  console.log('[upload_video] Found video:', videoReferenceId)
  console.log('[upload_video] Found thumbnail:', thumbnailReferenceId || 'none')
  
  // Upload video to YouTube
  const videoId = await uploadToYouTube(videoReferenceId, metadata)
  
  // If thumbnail exists, upload it too
  if (thumbnailReferenceId) {
    await uploadThumbnail(videoId, thumbnailReferenceId)
  }
  
  return { success: true, videoId }
}
```

## Detection Examples

### Scenario 1: Video Only

```javascript
// User uploads: vacation.mp4
// System creates:
{
  referenceId: "abc123...",
  fileType: "video",
  mimeType: "video/mp4"
}

// Tool finds:
uploads.video = { referenceId: "abc123..." }
uploads.thumbnail = null
```

### Scenario 2: Video + Thumbnail

```javascript
// User uploads: vacation.mp4, then cover.jpg
// System creates:
[
  {
    referenceId: "abc123...",
    fileType: "video",
    mimeType: "video/mp4"
  },
  {
    referenceId: "def456...",
    fileType: "thumbnail",
    mimeType: "image/jpeg"
  }
]

// Tool finds both automatically:
uploads.video = { referenceId: "abc123..." }
uploads.thumbnail = { referenceId: "def456..." }
```

### Scenario 3: Multiple Files

```javascript
// User uploads: video1.mp4, video2.mp4, thumb1.jpg, thumb2.jpg
// System finds the LATEST of each type:
uploads.video = { referenceId: "video2_ref" }     // Most recent video
uploads.thumbnail = { referenceId: "thumb2_ref" }  // Most recent thumbnail
```

## Drag & Drop Integration

### Visual Flow

```
1. User drags files over chat area
   ↓
2. System shows drop zone indicator
   ↓
3. On drop, files are analyzed:
   - video.mp4 → Detected as video
   - thumb.jpg → Detected as thumbnail
   ↓
4. Both uploaded simultaneously
   ↓
5. Chat message auto-populated:
   "Upload video 'vacation.mp4' (125MB) to YouTube..."
   ↓
6. AI tool automatically finds both files
```

### Implementation

```typescript
// Handle dropped files
const handleDrop = async (files: FileList) => {
  for (const file of files) {
    if (file.type.startsWith('video/')) {
      // Upload as video
      await uploadVideo(file)
    } else if (file.type.startsWith('image/')) {
      // Upload as thumbnail
      await uploadThumbnail(file)
    }
  }
  
  // Insert smart message for AI
  insertMessage(`Upload video "${videoFile.name}" to YouTube...`)
}
```

## File Type Validation

### Video Validation

```typescript
function validateVideo(file: File) {
  // Check MIME type
  if (!file.type.startsWith('video/')) {
    throw new Error('File must be a video')
  }
  
  // Check file size (YouTube limit: 128GB)
  const maxSize = 128 * 1024 * 1024 * 1024
  if (file.size > maxSize) {
    throw new Error('Video exceeds YouTube\'s 128GB limit')
  }
  
  // Check extension
  const validExtensions = ['.mp4', '.mov', '.avi', '.wmv', '.flv', '.mkv', '.webm', '.m4v', '.3gp', '.3g2']
  const ext = file.name.toLowerCase().substring(file.name.lastIndexOf('.'))
  if (!validExtensions.includes(ext)) {
    throw new Error(`Unsupported video format: ${ext}`)
  }
}
```

### Thumbnail Validation

```typescript
function validateThumbnail(file: File) {
  // Check MIME type
  if (!file.type.startsWith('image/')) {
    throw new Error('Thumbnail must be an image')
  }
  
  // Check file size (YouTube limit: 2MB)
  const maxSize = 2 * 1024 * 1024
  if (file.size > maxSize) {
    throw new Error('Thumbnail must be under 2MB')
  }
  
  // Validate dimensions (processed to 1280x720)
  // YouTube requirements: 1280x720 minimum, 16:9 aspect ratio
}
```

## Progress Tracking

Both video and thumbnail uploads are tracked:

```typescript
// Upload status structure
interface UploadProgress {
  video: {
    status: 'pending' | 'uploading' | 'completed' | 'failed'
    progress: number  // 0-100
    videoId?: string
  }
  thumbnail: {
    status: 'pending' | 'uploading' | 'completed' | 'failed'
    error?: string
  }
}

// Real-time updates via polling
GET /api/youtube/upload-status/:uploadId
```

## MongoDB Collections

### UploadReference Collection

Primary collection for file tracking:

```javascript
{
  _id: ObjectId,
  userId: "user_123",
  referenceId: "a1b2c3d4e5f6g7h8...",  // 32 chars
  fileName: "vacation.mp4",
  fileSize: "125.5 MB",
  fileType: "video",  // or "thumbnail"
  mimeType: "video/mp4",
  status: "pending",
  createdAt: ISODate("2024-01-01T10:00:00Z"),
  expiresAt: ISODate("2024-01-02T10:00:00Z")  // 24h TTL
}
```

### VideoFileReference Collection

Stores actual file data:

```javascript
{
  id: "a1b2c3d4e5f6g7h8...",
  userId: "user_123",
  fileName: "vacation.mp4",
  fileSize: 131596288,  // bytes
  mimeType: "video/mp4",
  fileData: BinData(...),  // Actual video buffer
  uploadedAt: ISODate("2024-01-01T10:00:00Z"),
  expiresAt: ISODate("2024-01-02T10:00:00Z"),
  thumbnailId: "q1w2e3r4...",  // Link to thumbnail
}
```

## Security & Cleanup

### Automatic Expiration

```typescript
// TTL indexes for automatic cleanup
UploadReferenceSchema.index({ expiresAt: 1 }, { expireAfterSeconds: 0 })

// Different expiration times
const QUICK_UPLOAD_EXPIRY = 30 * 60 * 1000      // 30 minutes
const PREPARED_UPLOAD_EXPIRY = 24 * 60 * 60 * 1000  // 24 hours
```

### User Isolation

```typescript
// All queries filtered by userId
const uploads = await UploadReference.find({
  userId: currentUser.id,  // ← Only user's own files
  status: 'pending'
})
```

### Reference Marking

```typescript
// Mark as used after successful upload
UploadReferenceSchema.statics.markAsUsed = async function(referenceIds: string[]) {
  await this.updateMany(
    { referenceId: { $in: referenceIds } },
    { status: 'used' }
  )
}
```

## Implementation Checklist

### Required Components

1. **File Type Detection**
   - [ ] MIME type analyzer
   - [ ] File extension validator
   - [ ] Size limit checker

2. **Reference System**
   - [ ] ID generator (32-char hex)
   - [ ] MongoDB models for tracking
   - [ ] TTL indexes for cleanup

3. **Upload Endpoints**
   - [ ] `/api/youtube/prepare-upload` (video)
   - [ ] `/api/youtube/prepare-thumbnail` (thumbnail)
   - [ ] `/api/youtube/upload-status/:id` (progress)

4. **Automatic Discovery**
   - [ ] `getLatestPendingUploads()` method
   - [ ] File type filtering
   - [ ] Status checking

5. **YouTube Integration**
   - [ ] Video upload handler
   - [ ] Thumbnail upload handler
   - [ ] Progress tracking

## Summary

Morphic's file detection system provides:

1. **Automatic Type Detection**: MIME-based categorization as video or thumbnail
2. **Intelligent Pairing**: Automatically finds and pairs latest video with latest thumbnail
3. **Zero Configuration**: No manual linking or selection required
4. **Reference-Based Tracking**: Secure 32-character IDs for file management
5. **Seamless Integration**: Drag & drop support with automatic detection
6. **Progress Tracking**: Real-time status for both video and thumbnail uploads

The system eliminates manual file selection by automatically detecting file types and pairing them for upload, creating a smooth user experience from file drop to YouTube publication.