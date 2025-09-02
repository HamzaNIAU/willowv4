# Video Reference ID System - Complete Technical Documentation

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [System Overview](#system-overview)
3. [Reference ID Generation](#reference-id-generation)
4. [Complete Data Flow](#complete-data-flow)
5. [Database Architecture](#database-architecture)
6. [API Endpoints](#api-endpoints)
7. [Frontend Integration](#frontend-integration)
8. [AI Agent Detection](#ai-agent-detection)
9. [Security & Lifecycle](#security--lifecycle)
10. [Code Implementation Details](#code-implementation-details)
11. [Troubleshooting Guide](#troubleshooting-guide)
12. [Performance Considerations](#performance-considerations)

---

## Executive Summary

The Video Reference ID system in Morphic is a sophisticated file management architecture that enables seamless video uploads to YouTube without exposing file system paths or requiring manual file selection. Every uploaded video and thumbnail receives a unique **32-character hexadecimal reference ID** that serves as a temporary identifier throughout the upload pipeline.

### Key Characteristics
- **Format**: 32-character hexadecimal string (e.g., `a1b2c3d4e5f6789012345678901234567`)
- **Generation**: `crypto.randomBytes(16).toString('hex')`
- **Lifetime**: 24-30 hours (auto-cleanup via MongoDB TTL)
- **Storage**: MongoDB with Binary data (Buffer)
- **Security**: User-scoped, temporary, non-guessable

---

## System Overview

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            USER INTERACTION                              │
├─────────────────────────────────────────────────────────────────────────┤
│  1. User uploads video/thumbnail via UI                                 │
│  2. File sent to API endpoint                                           │
│  3. Reference ID generated and returned                                 │
│  4. User asks AI to "upload my video"                                   │
│  5. AI auto-detects latest references                                  │
│  6. Upload proceeds to YouTube                                          │
└─────────────────────────────────────────────────────────────────────────┘

                                    ▼

┌─────────────────────────────────────────────────────────────────────────┐
│                          REFERENCE ID FLOW                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Frontend           API              FileManager         MongoDB         │
│     │                │                    │                 │           │
│     │─Upload File───▶│                    │                 │           │
│     │                │─Create Reference──▶│                 │           │
│     │                │                    │─Generate ID────▶│           │
│     │                │                    │                 │           │
│     │                │                    │◀─Store Buffer───│           │
│     │◀──Return ID────│◀──Reference ID─────│                 │           │
│     │                │                    │                 │           │
│     │                                                       │           │
│     │─"Upload video"─────────────────────────────────────▶ AI          │
│     │                                                       │           │
│     │                                     ◀─Get Latest─────│           │
│     │                                     │                 │           │
│     │                                     │─Return Refs────▶│           │
│     │                                                       │           │
│     │◀──────────────Upload to YouTube──────────────────────│           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Core Components

1. **YouTubeFileManager** (`/lib/youtube/youtube-file-manager.ts`)
   - Generates reference IDs
   - Manages file lifecycle
   - Handles Buffer storage

2. **MongoDB Collections**
   - `VideoFileReference` - Video storage
   - `ThumbnailReference` - Thumbnail storage
   - `UploadReference` - Upload tracking

3. **API Routes**
   - `/api/youtube/prepare-upload` - Video preparation
   - `/api/youtube/prepare-thumbnail` - Thumbnail preparation
   - `/api/youtube/upload-status` - Status tracking

4. **AI Tools**
   - `upload_video` - Single channel upload
   - `upload_video_multi` - Multi-channel upload

---

## Reference ID Generation

### Core Implementation

```typescript
// lib/youtube/youtube-file-manager.ts - Line 59
const id = crypto.randomBytes(16).toString('hex')
```

### Detailed Generation Process

```typescript
/**
 * Reference ID Generation Deep Dive
 * Location: YouTubeFileManager.createFileReference()
 */

import crypto from 'crypto'

// Step 1: Generate random bytes
const randomBytes = crypto.randomBytes(16)  
// Creates 16 random bytes (128 bits of randomness)
// Example: <Buffer a1 b2 c3 d4 e5 f6 78 90 12 34 56 78 90 12 34 56>

// Step 2: Convert to hexadecimal string
const id = randomBytes.toString('hex')
// Converts each byte to 2 hex characters
// Result: "a1b2c3d4e5f6789012345678901234567" (32 characters)

// Step 3: Characteristics
// - Length: Always exactly 32 characters
// - Characters: 0-9 and a-f (lowercase)
// - Uniqueness: 2^128 possible values
// - Collision probability: Negligible (1 in 340 undecillion)
```

### Reference ID Formats in System

```typescript
// Different representations throughout the codebase:

// 1. Raw format (most common)
"a1b2c3d4e5f6789012345678901234567"

// 2. In logs
"[video-ref:a1b2c3d4e5f6789012345678901234567]"

// 3. In UI messages
"(ref: a1b2c3d4e5f6789012345678901234567)"

// 4. Pattern matching in tools
/(?:\(ref:\s*([a-f0-9]+)\)|(?:\[video-ref:([a-f0-9]+)\])|(?:\(reference:\s*([a-f0-9]+)\)))/i

// 5. Validation regex
/^[a-f0-9]{32}$/i
```

---

## Complete Data Flow

### 1. Video Upload Flow

```typescript
// STEP 1: User uploads video file via frontend
// File: components/chat-panel.tsx

const uploadVideoFile = async (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await fetch('/api/youtube/prepare-upload', {
    method: 'POST',
    body: formData
  })
  
  const result = await response.json()
  // Returns: { referenceId: "a1b2c3d4e5f6789012345678901234567", ... }
}

// STEP 2: API endpoint processes upload
// File: app/api/youtube/prepare-upload/route.ts

export async function POST(request: NextRequest) {
  const user = await currentUser()
  const formData = await request.formData()
  const file = formData.get('file') as File
  
  // Create file reference with generated ID
  const fileReference = await YouTubeFileManager.createFileReference(
    user.id, 
    file
  )
  
  // Store in UploadReference for AI detection
  await UploadReferenceModel.create({
    userId: user.id,
    referenceId: fileReference.id,  // The 32-char hex ID
    fileName: file.name,
    fileSize: formatBytes(file.size),
    fileType: 'video',
    mimeType: file.type,
    status: 'pending'
  })
  
  return NextResponse.json({
    referenceId: fileReference.id,
    fileName: fileReference.fileName,
    fileSize: formatBytes(fileReference.fileSize),
    expiresAt: fileReference.expiresAt
  })
}

// STEP 3: FileManager creates and stores reference
// File: lib/youtube/youtube-file-manager.ts

static async createFileReference(userId: string, file: File) {
  // Generate the reference ID
  const id = crypto.randomBytes(16).toString('hex')
  console.log('[YouTubeFileManager] Generated reference ID:', id)
  
  // Set expiration (24 hours)
  const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000)
  
  // Convert File to Buffer for MongoDB storage
  const arrayBuffer = await file.arrayBuffer()
  const buffer = Buffer.from(arrayBuffer)
  
  // Create reference object
  const reference = {
    id,                    // The reference ID
    userId,
    fileName: file.name,
    fileSize: file.size,
    mimeType: file.type || 'video/mp4',
    uploadedAt: new Date(),
    expiresAt,
    source: 'upload',
    fileData: buffer       // Binary data stored in MongoDB
  }
  
  // Store in MongoDB
  await VideoFileReferenceModel.create(reference)
  
  return reference
}
```

### 2. AI Agent Detection Flow

```typescript
// STEP 4: User asks AI to upload video
// The AI agent automatically detects the latest uploads

// File: lib/tools/youtube/upload_video.ts

export const uploadVideoTool = tool({
  execute: async ({ channel_id, title, description }) => {
    const user = await currentUser()
    
    // Auto-detect latest pending uploads
    const uploads = await UploadReferenceModel.getLatestPendingUploads(user.id)
    
    if (!uploads.video) {
      throw new Error('No video file found. Please upload a video file first.')
    }
    
    const file_path = uploads.video.referenceId  // The reference ID
    const thumbnail_path = uploads.thumbnail?.referenceId
    
    console.log('[upload_video] Found video reference:', file_path)
    console.log('[upload_video] Found thumbnail reference:', thumbnail_path || 'none')
    
    // Continue with upload process...
  }
})

// STEP 5: getLatestPendingUploads implementation
// File: lib/mongodb/models/UploadReference.ts

UploadReferenceSchema.statics.getLatestPendingUploads = async function(userId: string) {
  // Find user's pending uploads, sorted by newest first
  const uploads = await this.find({
    userId,
    status: 'pending',
    expiresAt: { $gt: new Date() }  // Not expired
  }).sort({ createdAt: -1 }).limit(10)
  
  // Separate video and thumbnail by MIME type
  const video = uploads.find(u => u.fileType === 'video')
  const thumbnail = uploads.find(u => u.fileType === 'thumbnail')
  
  return { video, thumbnail }
}
```

### 3. File Retrieval Flow

```typescript
// STEP 6: Retrieve file data using reference ID
// File: lib/youtube/youtube-file-manager.ts

static async getFileData(userId: string, referenceId: string) {
  await dbConnect()
  
  console.log('[YouTubeFileManager] Looking up reference:', referenceId)
  
  // Find the reference in MongoDB
  const stored = await VideoFileReferenceModel.findOne({
    id: referenceId,
    userId: userId  // User-scoped for security
  })
  
  if (!stored) {
    console.log('[YouTubeFileManager] Reference not found:', referenceId)
    return null
  }
  
  // Check if expired
  if (new Date() > stored.expiresAt) {
    console.log('[YouTubeFileManager] Reference expired:', referenceId)
    await VideoFileReferenceModel.deleteOne({ id: referenceId })
    return null
  }
  
  // Convert Buffer back to Blob for upload
  const blob = new Blob([stored.fileData], { type: stored.mimeType })
  
  return { 
    reference: stored,  // Metadata
    data: blob         // File data
  }
}
```

### 4. Upload to YouTube Flow

```typescript
// STEP 7: Upload to YouTube using reference
// File: lib/youtube/youtube-upload-stream.ts

async uploadLargeVideo(fileData: Blob, metadata: any) {
  // Initialize resumable upload
  const uploadUrl = await this.initiateResumableUpload(metadata)
  
  // Upload the blob data
  const xhr = new XMLHttpRequest()
  xhr.open('PUT', uploadUrl)
  xhr.setRequestHeader('Content-Type', 'video/*')
  xhr.send(fileData)  // The blob retrieved from MongoDB
  
  // Return YouTube video ID
  return response.videoId
}

// STEP 8: Mark references as used
// File: lib/mongodb/models/UploadReference.ts

UploadReferenceSchema.statics.markAsUsed = async function(referenceIds: string[]) {
  await this.updateMany(
    { referenceId: { $in: referenceIds } },
    { status: 'used' }
  )
}

// STEP 9: Clean up after upload
// File: lib/youtube/youtube-file-manager.ts

static async deleteFileReference(userId: string, referenceId: string) {
  const result = await VideoFileReferenceModel.deleteOne({
    id: referenceId,
    userId: userId
  })
  
  console.log('[YouTubeFileManager] Delete result:', result.deletedCount > 0 ? 'Success' : 'Not found')
  return result.deletedCount > 0
}
```

---

## Database Architecture

### 1. VideoFileReference Collection

```typescript
// lib/mongodb/models/VideoFileReference.ts

interface IVideoFileReference {
  // Identification
  _id?: string                    // MongoDB ObjectId
  id: string                      // Reference ID (32-char hex) - PRIMARY KEY
  userId: string                  // User who uploaded (Clerk ID)
  
  // File Information
  fileName: string                // Original filename
  fileSize: number                // Size in bytes
  mimeType: string                // MIME type (video/mp4, etc.)
  
  // Timestamps
  uploadedAt: Date                // When uploaded
  expiresAt: Date                 // TTL expiration (24 hours)
  
  // Data Storage
  source: 'upload' | 'url' | 'blob'  // How file was created
  fileData: Buffer                    // Binary file data (can be large!)
  
  // Optional Metadata
  metadata?: {
    url?: string                // Source URL if applicable
    duration?: number           // Video duration in seconds
    resolution?: string         // Video resolution (e.g., "1920x1080")
  }
  
  // AI Transcription (if enabled)
  transcription?: {
    text: string                // Full transcript
    language: string            // Detected language
    duration?: number          // Processing duration
    processedAt: Date          // When transcribed
  }
  
  // AI Generated Metadata
  generatedMetadata?: {
    title: string
    description: string
    tags: string[]
    hashtags: string[]
    category?: string
    highlights?: string[]
    variations?: Array<{        // Multiple variations for multi-upload
      title: string
      description: string
      tags: string[]
      hashtags: string[]
    }>
  }
  
  // Thumbnail Association
  thumbnailId?: string          // Reference to thumbnail document
  thumbnail?: {
    width: number
    height: number
    format: string
    size: number
    previewUrl?: string         // Base64 preview
  }
}

// Indexes
VideoFileReferenceSchema.index({ expiresAt: 1 }, { expireAfterSeconds: 0 })  // TTL
VideoFileReferenceSchema.index({ userId: 1, id: 1 })  // Query optimization
```

### 2. ThumbnailReference Collection

```typescript
// lib/mongodb/models/ThumbnailReference.ts

interface IThumbnailReference {
  // Identification
  _id?: string
  id: string                    // Reference ID (32-char hex)
  userId: string
  
  // File Information
  fileName: string
  fileSize: number
  mimeType: string              // Always 'image/jpeg' after processing
  
  // Timestamps
  uploadedAt: Date
  expiresAt: Date               // TTL (24 hours)
  
  // Image Data
  imageData: Buffer             // Processed image (1280x720 JPEG)
  
  // Image Metadata
  metadata: {
    width: number               // Always 1280 after processing
    height: number              // Always 720 after processing
    format: string              // 'jpeg'
    originalWidth?: number      // Original dimensions
    originalHeight?: number
  }
  
  // Video Association
  videoReferenceId?: string     // Link to video if paired
}

// Indexes
ThumbnailReferenceSchema.index({ expiresAt: 1 }, { expireAfterSeconds: 0 })
ThumbnailReferenceSchema.index({ userId: 1, id: 1 })
ThumbnailReferenceSchema.index({ videoReferenceId: 1 })  // For lookups
```

### 3. UploadReference Collection

```typescript
// lib/mongodb/models/UploadReference.ts

interface IUploadReference {
  // Core Fields
  userId: string
  referenceId: string           // The 32-char hex ID
  fileName: string
  fileSize: string              // Human-readable (e.g., "25.3 MB")
  fileType: 'video' | 'thumbnail'
  mimeType?: string
  videoReferenceId?: string     // For thumbnail-video pairing
  
  // Status Tracking
  status: 'pending' | 'used' | 'expired'
  
  // Timestamps
  createdAt: Date
  updatedAt: Date
  expiresAt: Date               // 30 minutes by default
}

// Key Methods
getLatestPendingUploads(userId)  // Auto-detection for AI
markAsUsed(referenceIds[])       // Mark as uploaded
```

### MongoDB Storage Strategy

```javascript
// Storage sizes and considerations:

// 1. VideoFileReference
// - fileData: Buffer (can be up to 128GB for YouTube max)
// - MongoDB document limit: 16MB
// - Solution: GridFS for large files OR external storage

// 2. ThumbnailReference  
// - imageData: Buffer (max 2MB after processing)
// - Fits within MongoDB document limit

// 3. UploadReference
// - No binary data, just metadata
// - Very small documents (~1KB)

// TTL Index Configuration
db.videofilereferences.createIndex(
  { "expiresAt": 1 },
  { expireAfterSeconds: 0 }
)
// Documents auto-delete when expiresAt timestamp is reached
```

---

## API Endpoints

### Video Upload Endpoints

```typescript
// 1. POST /api/youtube/prepare-upload
// Prepares video for upload, returns reference ID

Request: FormData {
  file: File (video file)
}

Response: {
  referenceId: "a1b2c3d4e5f6789012345678901234567",
  fileName: "my-video.mp4",
  fileSize: "25.3 MB",
  mimeType: "video/mp4",
  expiresAt: "2024-01-15T10:30:00Z",
  message: "File prepared for upload"
}

// 2. GET /api/youtube/prepare-upload
// Lists user's prepared uploads

Response: {
  files: [{
    referenceId: "a1b2c3d4e5f6789012345678901234567",
    fileName: "my-video.mp4",
    fileSize: "25.3 MB",
    mimeType: "video/mp4",
    uploadedAt: "2024-01-14T10:30:00Z",
    expiresAt: "2024-01-15T10:30:00Z"
  }]
}
```

### Thumbnail Upload Endpoints

```typescript
// 3. POST /api/youtube/prepare-thumbnail
// Processes and prepares thumbnail

Request: FormData {
  file: File (image file),
  videoReferenceId?: string  // Optional pairing
}

Response: {
  referenceId: "b2c3d4e5f6789012345678901234568",
  fileName: "thumbnail.jpg",
  fileSize: "156 KB",
  dimensions: {
    width: 1280,
    height: 720
  },
  previewUrl: "data:image/jpeg;base64,...",
  expiresAt: "2024-01-15T10:30:00Z"
}

// 4. POST /api/youtube/upload-thumbnail
// Uploads thumbnail to YouTube video

Request: {
  videoId: "YouTube_Video_ID",
  thumbnailReferenceId: "b2c3d4e5f6789012345678901234568",
  channelId: "YouTube_Channel_ID"
}

Response: {
  success: true,
  message: "Thumbnail uploaded successfully"
}
```

### Status Tracking Endpoints

```typescript
// 5. GET /api/youtube/upload-status/[uploadId]
// Tracks upload progress

Response: {
  uploadStatus: "uploading" | "completed" | "failed",
  uploadProgress: 75,  // Percentage
  videoId?: "YouTube_Video_ID",
  errorMessage?: "Error details"
}
```

---

## Frontend Integration

### Chat Panel File Upload

```typescript
// components/chat-panel.tsx

const ChatPanel = () => {
  // Upload video file
  const uploadVideoFile = async (file: File) => {
    try {
      const formData = new FormData()
      formData.append('file', file)
      
      const response = await fetch('/api/youtube/prepare-upload', {
        method: 'POST',
        body: formData
      })
      
      const result = await response.json()
      
      // Store reference for display
      setUploadedFiles(prev => [...prev, {
        type: 'video',
        referenceId: result.referenceId,
        fileName: result.fileName,
        fileSize: result.fileSize
      }])
      
      // Log for debugging
      console.log('[ChatPanel] Uploaded video:', result.referenceId)
      
      return result
    } catch (error) {
      console.error('[ChatPanel] Upload failed:', error)
      return null
    }
  }
  
  // Handle file drop/selection
  const handleFileSelect = async (files: FileList) => {
    for (const file of files) {
      if (file.type.startsWith('video/')) {
        const result = await uploadVideoFile(file)
        if (result) {
          // Update UI to show uploaded file
          showNotification(`Video "${file.name}" ready for upload`)
        }
      } else if (file.type.startsWith('image/')) {
        // Similar for thumbnail...
      }
    }
  }
}
```

### File Attachment Display

```typescript
// components/ui/file-attachment.tsx

interface FileAttachment {
  type: 'video' | 'thumbnail'
  referenceId: string
  fileName: string
  fileSize: string
}

const FileAttachmentDisplay = ({ attachment }: { attachment: FileAttachment }) => {
  return (
    <div className="flex items-center gap-2 p-2 bg-gray-100 rounded">
      {attachment.type === 'video' ? <VideoIcon /> : <ImageIcon />}
      <div className="flex-1">
        <p className="font-medium">{attachment.fileName}</p>
        <p className="text-sm text-gray-500">
          {attachment.fileSize} • ID: {attachment.referenceId.slice(0, 8)}...
        </p>
      </div>
    </div>
  )
}
```

---

## AI Agent Detection

### Auto-Detection Mechanism

```typescript
// The AI doesn't need to know reference IDs - it auto-detects!

// 1. User uploads video/thumbnail
// 2. User says: "upload my video to YouTube"
// 3. AI tool automatically finds latest uploads:

// lib/tools/youtube/upload_video_multi.ts
export const uploadVideoMultiTool = tool({
  description: 'Upload a video to ALL enabled YouTube accounts. ' +
    'This tool automatically uses the most recent video and thumbnail files you uploaded.',
  
  // Note: No file_path parameter needed!
  parameters: z.object({
    title: z.string(),
    description: z.string(),
    // ... other metadata
  }),
  
  execute: async ({ title, description }) => {
    const user = await currentUser()
    
    // Magic happens here - auto-detection!
    const uploads = await UploadReferenceModel.getLatestPendingUploads(user.id)
    
    if (!uploads.video) {
      throw new Error('No video file found. Please upload a video file first.')
    }
    
    // Automatically uses the latest uploads
    const file_path = uploads.video.referenceId
    const thumbnail_path = uploads.thumbnail?.referenceId
    
    // The AI never needs to handle or remember reference IDs!
  }
})
```

### Detection Algorithm

```typescript
// How getLatestPendingUploads works:

async function getLatestPendingUploads(userId: string) {
  // Step 1: Query all pending uploads for user
  const uploads = await UploadReference.find({
    userId,
    status: 'pending',
    expiresAt: { $gt: new Date() }  // Not expired
  })
  .sort({ createdAt: -1 })  // Newest first
  .limit(10)                 // Recent uploads only
  
  // Step 2: Separate by MIME type
  const categorized = {
    videos: [],
    thumbnails: []
  }
  
  uploads.forEach(upload => {
    if (upload.mimeType?.startsWith('video/')) {
      categorized.videos.push(upload)
    } else if (upload.mimeType?.startsWith('image/')) {
      categorized.thumbnails.push(upload)
    }
  })
  
  // Step 3: Return the most recent of each type
  return {
    video: categorized.videos[0] || null,
    thumbnail: categorized.thumbnails[0] || null
  }
}
```

### Reference ID Parsing

```typescript
// Sometimes the AI might receive reference IDs in various formats
// The upload tools handle all these patterns:

// Pattern matching in upload_video.ts
const parseReferenceId = (input: string): string => {
  // Pattern 1: (ref: xxx)
  const pattern1 = input.match(/\(ref:\s*([a-f0-9]{32})\)/i)
  if (pattern1) return pattern1[1]
  
  // Pattern 2: [video-ref:xxx]
  const pattern2 = input.match(/\[video-ref:([a-f0-9]{32})\]/i)
  if (pattern2) return pattern2[1]
  
  // Pattern 3: Just the hex string
  const pattern3 = input.match(/^[a-f0-9]{32}$/i)
  if (pattern3) return pattern3[0]
  
  // Pattern 4: Any 32-char hex in the string
  const pattern4 = input.match(/[a-f0-9]{32}/i)
  if (pattern4) return pattern4[0]
  
  // Not a reference ID
  return input
}
```

---

## Security & Lifecycle

### Security Features

```typescript
// 1. User Scoping
// All queries include userId to prevent cross-user access
const reference = await VideoFileReference.findOne({
  id: referenceId,
  userId: userId  // CRITICAL: User isolation
})

// 2. Non-Guessable IDs
// 128 bits of randomness = 2^128 possible values
// Probability of guessing: 1 in 340,282,366,920,938,463,463,374,607,431,768,211,456

// 3. Automatic Expiration
// Files auto-delete after 24 hours via TTL index
expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000)

// 4. Status Tracking
// References marked as 'used' after upload
status: 'pending' | 'used' | 'expired'

// 5. No File System Access
// Files stored as Buffers in MongoDB, not on disk
fileData: Buffer  // Binary data in database
```

### Lifecycle Management

```typescript
// Complete lifecycle of a reference ID:

// 1. CREATION (0 minutes)
const id = crypto.randomBytes(16).toString('hex')
// Status: 'pending'
// ExpiresAt: now + 24 hours

// 2. STORAGE (0-30 minutes)
// File data stored in MongoDB
// Available for AI detection
// User can upload multiple files

// 3. DETECTION (user-initiated)
// AI finds latest pending uploads
// Automatically pairs video/thumbnail

// 4. UPLOAD (varies)
// File uploaded to YouTube
// Progress tracked in real-time

// 5. COMPLETION
// Reference marked as 'used'
// File data deleted immediately
await VideoFileReference.deleteOne({ id: referenceId })

// 6. EXPIRATION (24 hours)
// If not used, TTL index auto-deletes
// No manual cleanup needed
```

### TTL Index Configuration

```javascript
// MongoDB TTL indexes for automatic cleanup

// VideoFileReference collection
db.videofilereferences.createIndex(
  { "expiresAt": 1 },
  { expireAfterSeconds: 0 }
)

// ThumbnailReference collection  
db.thumbnailreferences.createIndex(
  { "expiresAt": 1 },
  { expireAfterSeconds: 0 }
)

// UploadReference collection (30 minutes)
db.uploadreferences.createIndex(
  { "expiresAt": 1 },
  { expireAfterSeconds: 0 }
)

// How TTL works:
// - MongoDB background task runs every 60 seconds
// - Deletes documents where expiresAt < now
// - No application code needed
// - Automatic garbage collection
```

---

## Code Implementation Details

### Reference ID Validation

```typescript
// Utility functions for reference ID handling

class ReferenceIdUtils {
  // Validate format
  static isValidReferenceId(id: string): boolean {
    return /^[a-f0-9]{32}$/i.test(id)
  }
  
  // Generate new ID
  static generateReferenceId(): string {
    return crypto.randomBytes(16).toString('hex')
  }
  
  // Format for display
  static formatForDisplay(id: string): string {
    return `${id.slice(0, 8)}...${id.slice(-4)}`
  }
  
  // Extract from various formats
  static extractFromString(input: string): string | null {
    const patterns = [
      /\(ref:\s*([a-f0-9]{32})\)/i,
      /\[video-ref:([a-f0-9]{32})\]/i,
      /\(reference:\s*([a-f0-9]{32})\)/i,
      /^([a-f0-9]{32})$/i
    ]
    
    for (const pattern of patterns) {
      const match = input.match(pattern)
      if (match) return match[1]
    }
    
    return null
  }
}
```

### Error Handling

```typescript
// Common error scenarios and handling

class ReferenceIdErrors {
  static handleNotFound(referenceId: string): Error {
    return new Error(
      `File reference not found: ${referenceId}. ` +
      `The file may have expired or been deleted. ` +
      `Please upload the file again.`
    )
  }
  
  static handleExpired(referenceId: string): Error {
    return new Error(
      `File reference expired: ${referenceId}. ` +
      `Files are automatically deleted after 24 hours. ` +
      `Please upload the file again.`
    )
  }
  
  static handleInvalidFormat(input: string): Error {
    return new Error(
      `Invalid reference ID format: ${input}. ` +
      `Expected 32-character hexadecimal string.`
    )
  }
  
  static handleUserMismatch(referenceId: string): Error {
    return new Error(
      `Access denied for reference: ${referenceId}. ` +
      `You can only access your own uploaded files.`
    )
  }
}
```

### Performance Optimizations

```typescript
// Optimization strategies for reference ID system

// 1. Indexed queries
VideoFileReferenceSchema.index({ userId: 1, id: 1 })
// Compound index for fast lookups

// 2. Projection to exclude large fields
const reference = await VideoFileReference
  .findOne({ id: referenceId })
  .select('-fileData')  // Don't load binary data unless needed

// 3. Batch operations
await UploadReference.updateMany(
  { referenceId: { $in: referenceIds } },
  { status: 'used' }
)

// 4. Caching strategy (not currently implemented)
class ReferenceCache {
  private cache = new Map<string, any>()
  private maxAge = 5 * 60 * 1000  // 5 minutes
  
  set(id: string, data: any): void {
    this.cache.set(id, {
      data,
      timestamp: Date.now()
    })
  }
  
  get(id: string): any | null {
    const cached = this.cache.get(id)
    if (!cached) return null
    
    if (Date.now() - cached.timestamp > this.maxAge) {
      this.cache.delete(id)
      return null
    }
    
    return cached.data
  }
}
```

---

## Troubleshooting Guide

### Common Issues and Solutions

#### Issue 1: "No video file found"
```typescript
Error: No video file found. Please upload a video file first.

Causes:
1. Video not uploaded yet
2. Video reference expired (>24 hours)
3. Video already used for another upload

Solution:
- Check UploadReference collection for user's pending uploads
- Verify expiresAt timestamp hasn't passed
- Re-upload the video file
```

#### Issue 2: "Reference ID not found"
```typescript
Error: File reference not found: a1b2c3d4...

Causes:
1. Invalid reference ID format
2. Reference belongs to different user
3. Reference already deleted after use

Debugging:
// Check if reference exists
db.videofilereferences.findOne({ id: "a1b2c3d4..." })

// Check UploadReference status
db.uploadreferences.findOne({ referenceId: "a1b2c3d4..." })
```

#### Issue 3: "Reference expired"
```typescript
Error: File reference expired

Causes:
1. More than 24 hours since upload
2. TTL index deleted the document

Solution:
// Check expiration time
const ref = await VideoFileReference.findOne({ id })
console.log('Expires at:', ref.expiresAt)
console.log('Current time:', new Date())

// Re-upload needed if expired
```

#### Issue 4: Multiple uploads confusion
```typescript
Scenario: User uploads multiple videos, AI picks wrong one

Solution:
// The system always picks the LATEST upload
// To handle multiple uploads, use them in order:
1. Upload video A
2. Tell AI to upload
3. Wait for completion
4. Upload video B
5. Tell AI to upload

// Or use specific reference IDs (advanced):
"Upload the video with reference a1b2c3d4..."
```

### Debug Commands

```javascript
// MongoDB queries for debugging

// 1. Check user's pending uploads
db.uploadreferences.find({
  userId: "user_123",
  status: "pending"
}).sort({ createdAt: -1 })

// 2. Check if reference exists
db.videofilereferences.findOne({
  id: "a1b2c3d4e5f6789012345678901234567"
})

// 3. Check reference status
db.uploadreferences.findOne({
  referenceId: "a1b2c3d4e5f6789012345678901234567"
})

// 4. Manual cleanup of expired references
db.videofilereferences.deleteMany({
  expiresAt: { $lt: new Date() }
})

// 5. Check storage size
db.videofilereferences.aggregate([
  { $match: { userId: "user_123" } },
  { $group: {
    _id: null,
    totalSize: { $sum: "$fileSize" },
    count: { $sum: 1 }
  }}
])
```

### Logging for Debugging

```typescript
// Key log points in the system

// 1. Reference generation
console.log('[YouTubeFileManager] Generated reference ID:', id, 'Length:', id.length)

// 2. Storage confirmation
console.log('[YouTubeFileManager] Stored reference in MongoDB:', id)

// 3. Lookup attempts
console.log('[YouTubeFileManager] Looking up reference:', referenceId, 'for user:', userId)

// 4. Auto-detection
console.log('[upload_video] Found video reference:', file_path)
console.log('[upload_video] Found thumbnail reference:', thumbnail_path || 'none')

// 5. Cleanup
console.log('[YouTubeFileManager] Delete result:', deleted ? 'Success' : 'Not found')
```

---

## Performance Considerations

### Storage Optimization

```typescript
// Current storage approach vs alternatives

// CURRENT: MongoDB Binary Storage
Pros:
- Simple implementation
- User isolation built-in
- Automatic TTL cleanup
- Single database solution

Cons:
- 16MB document limit (GridFS needed for large files)
- Memory usage for large Buffers
- Database size growth

// ALTERNATIVE 1: GridFS for large files
if (file.size > 15 * 1024 * 1024) {  // 15MB
  // Use GridFS
  const bucket = new GridFSBucket(db)
  const uploadStream = bucket.openUploadStream(fileName)
  // Store GridFS ID as reference
}

// ALTERNATIVE 2: External storage (S3/CloudStorage)
const uploadToS3 = async (file: Buffer, id: string) => {
  await s3.putObject({
    Bucket: 'youtube-uploads',
    Key: `${userId}/${id}`,
    Body: file,
    Expires: new Date(Date.now() + 24 * 60 * 60 * 1000)
  })
  // Store S3 key in MongoDB
}
```

### Query Performance

```typescript
// Optimization techniques

// 1. Use projections to limit data transfer
const reference = await VideoFileReference
  .findOne({ id, userId })
  .select('id fileName fileSize mimeType')  // Only needed fields
  .lean()  // Plain JavaScript object

// 2. Batch operations
const references = await UploadReference
  .find({ userId, status: 'pending' })
  .limit(10)  // Limit results
  .sort({ createdAt: -1 })  // Use index
  .hint({ userId: 1, status: 1, createdAt: -1 })  // Force index

// 3. Aggregation for statistics
const stats = await VideoFileReference.aggregate([
  { $match: { userId } },
  { $group: {
    _id: null,
    totalFiles: { $sum: 1 },
    totalSize: { $sum: "$fileSize" },
    avgSize: { $avg: "$fileSize" }
  }}
])
```

### Memory Management

```typescript
// Handling large files efficiently

// 1. Stream processing for large files
const processLargeFile = async (fileStream: ReadableStream) => {
  const chunks: Uint8Array[] = []
  const reader = fileStream.getReader()
  
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    chunks.push(value)
  }
  
  return Buffer.concat(chunks)
}

// 2. Cleanup after use
const cleanup = async (referenceId: string) => {
  // Delete from all collections
  await Promise.all([
    VideoFileReference.deleteOne({ id: referenceId }),
    UploadReference.deleteMany({ referenceId }),
    ThumbnailReference.deleteOne({ videoReferenceId: referenceId })
  ])
}

// 3. Memory-efficient retrieval
const getFileStream = async (referenceId: string) => {
  const doc = await VideoFileReference.findOne({ id: referenceId })
  // Convert Buffer to stream
  const stream = new Readable()
  stream.push(doc.fileData)
  stream.push(null)
  return stream
}
```

---

## Summary

The Video Reference ID system is a sophisticated temporary file management solution that enables seamless video uploads to YouTube without exposing file paths or requiring manual file management. Key takeaways:

1. **Reference IDs are 32-character hex strings** generated using cryptographically secure random bytes
2. **Files are stored temporarily in MongoDB** as Buffers with automatic TTL cleanup
3. **AI agents automatically detect** the latest uploads without needing reference IDs
4. **Security is enforced** through user scoping and non-guessable IDs
5. **The system is self-cleaning** with 24-hour expiration and immediate deletion after use

This architecture provides a secure, user-friendly, and maintainable solution for handling file uploads in an AI-powered application.

---

## Appendix: Quick Reference

### Key Files
- `/lib/youtube/youtube-file-manager.ts` - Reference ID generation
- `/lib/mongodb/models/VideoFileReference.ts` - Video storage schema
- `/lib/mongodb/models/UploadReference.ts` - Upload tracking
- `/app/api/youtube/prepare-upload/route.ts` - Upload API
- `/lib/tools/youtube/upload_video.ts` - AI upload tool

### Key Functions
- `crypto.randomBytes(16).toString('hex')` - Generate ID
- `getLatestPendingUploads(userId)` - Auto-detect uploads
- `markAsUsed(referenceIds)` - Mark as uploaded
- `deleteFileReference(userId, referenceId)` - Cleanup

### Reference ID Format
- **Length**: 32 characters
- **Characters**: 0-9, a-f (lowercase)
- **Example**: `a1b2c3d4e5f6789012345678901234567`
- **Generation**: 16 random bytes → hex string
- **Uniqueness**: 2^128 possible values