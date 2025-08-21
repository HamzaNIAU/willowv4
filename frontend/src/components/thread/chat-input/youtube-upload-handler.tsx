/**
 * YouTube Upload Handler
 * Handles video and thumbnail file uploads with automatic detection and pairing
 * Based on Morphic AI flow for intelligent file categorization
 */

import { toast } from 'sonner';
import { createClient } from '@/lib/supabase/client';

const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL || '';

// Video file extensions and MIME types supported by YouTube
const VIDEO_EXTENSIONS = [
  '.mp4', '.mov', '.avi', '.wmv', '.flv', '.3gpp', '.webm', '.mkv', '.m4v', '.mpg', '.mpeg', '.3gp', '.3g2'
];

const VIDEO_MIME_TYPES = [
  'video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/x-ms-wmv', 
  'video/x-flv', 'video/3gpp', 'video/webm', 'video/x-matroska', 
  'video/x-m4v', 'video/mpeg', 'video/3gpp2'
];

// Image MIME types for thumbnails
const IMAGE_MIME_TYPES = [
  'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'
];

// Maximum file sizes
const MAX_VIDEO_SIZE = 128 * 1024 * 1024 * 1024; // 128GB (YouTube limit)
const MAX_THUMBNAIL_SIZE = 2 * 1024 * 1024; // 2MB (YouTube limit)

// Upload reference interface matching Morphic pattern
export interface YouTubeUploadReference {
  referenceId: string;
  fileName: string;
  fileSize: string;
  fileType: 'video' | 'thumbnail';
  expiresAt: string;
  dimensions?: { width: number; height: number }; // For thumbnails
  warnings?: string[];
}

// Upload progress tracking
export interface UploadProgress {
  video: {
    status: 'pending' | 'uploading' | 'completed' | 'failed';
    progress: number;
    referenceId?: string;
    error?: string;
  };
  thumbnail: {
    status: 'pending' | 'uploading' | 'completed' | 'failed';
    referenceId?: string;
    error?: string;
  };
}

/**
 * Detect file type based on MIME type and extension
 * Returns 'video', 'thumbnail', or 'unknown'
 */
export function detectFileType(file: File): 'video' | 'thumbnail' | 'unknown' {
  // Check MIME type first
  if (file.type.startsWith('video/') || VIDEO_MIME_TYPES.includes(file.type)) {
    return 'video';
  }
  
  if (file.type.startsWith('image/') || IMAGE_MIME_TYPES.includes(file.type)) {
    return 'thumbnail';
  }
  
  // Fallback to extension checking
  const fileName = file.name.toLowerCase();
  const extension = fileName.substring(fileName.lastIndexOf('.'));
  
  if (VIDEO_EXTENSIONS.includes(extension)) {
    return 'video';
  }
  
  const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp'];
  if (imageExtensions.includes(extension)) {
    return 'thumbnail';
  }
  
  return 'unknown';
}

/**
 * Check if a file is a video file supported by YouTube
 */
export function isVideoFile(file: File): boolean {
  return detectFileType(file) === 'video';
}

/**
 * Check if a file is a thumbnail image
 */
export function isThumbnailFile(file: File): boolean {
  return detectFileType(file) === 'thumbnail';
}

/**
 * Format file size for display
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
}

/**
 * Validate video file for YouTube upload
 */
export function validateVideoFile(file: File): { valid: boolean; errors: string[]; warnings: string[] } {
  const result = { valid: true, errors: [] as string[], warnings: [] as string[] };
  
  // Check file size
  if (file.size > MAX_VIDEO_SIZE) {
    result.valid = false;
    result.errors.push(`Video exceeds YouTube's 128GB limit (${formatFileSize(file.size)})`);
  }
  
  // Check MIME type
  if (!file.type.startsWith('video/') && !VIDEO_MIME_TYPES.includes(file.type)) {
    result.warnings.push(`Unusual video type: ${file.type || 'unknown'}`);
  }
  
  return result;
}

/**
 * Validate thumbnail image for YouTube
 */
export function validateThumbnailFile(file: File): { valid: boolean; errors: string[]; warnings: string[] } {
  const result = { valid: true, errors: [] as string[], warnings: [] as string[] };
  
  // Check file size
  if (file.size > MAX_THUMBNAIL_SIZE) {
    result.valid = false;
    result.errors.push(`Thumbnail exceeds YouTube's 2MB limit (${formatFileSize(file.size)})`);
  }
  
  // Check MIME type
  if (!file.type.startsWith('image/') && !IMAGE_MIME_TYPES.includes(file.type)) {
    result.valid = false;
    result.errors.push(`Invalid image type: ${file.type || 'unknown'}`);
  }
  
  // Note: Dimension checking would be done server-side after processing
  
  return result;
}

/**
 * Prepare a file for YouTube upload (video or thumbnail)
 * Creates a reference that can be used by the AI agent
 */
export async function prepareYouTubeUpload(
  file: File,
  fileType?: 'video' | 'thumbnail' | 'auto'
): Promise<YouTubeUploadReference | null> {
  try {
    // Auto-detect file type if not specified
    if (!fileType || fileType === 'auto') {
      const detected = detectFileType(file);
      if (detected === 'unknown') {
        toast.error(`Cannot determine file type for: ${file.name}`);
        return null;
      }
      fileType = detected;
    }
    
    // Validate based on file type
    if (fileType === 'video') {
      const validation = validateVideoFile(file);
      if (!validation.valid) {
        validation.errors.forEach(error => toast.error(error));
        return null;
      }
      validation.warnings.forEach(warning => toast.warning(warning));
    } else {
      const validation = validateThumbnailFile(file);
      if (!validation.valid) {
        validation.errors.forEach(error => toast.error(error));
        return null;
      }
      validation.warnings.forEach(warning => toast.warning(warning));
    }
    
    // Create form data
    const formData = new FormData();
    formData.append('file', file);
    formData.append('file_type', fileType);
    
    // Get auth token
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    
    if (!session?.access_token) {
      toast.error('Please sign in to upload files');
      return null;
    }
    
    // Upload to prepare endpoint
    const response = await fetch(`${API_URL}/youtube/prepare-upload`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${session.access_token}`,
      },
      body: formData,
    });
    
    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || `Failed to prepare ${fileType}`);
    }
    
    const data = await response.json();
    
    // Show success message with file type icon
    const icon = fileType === 'video' ? '🎬' : '🖼️';
    toast.success(
      `${icon} ${fileType === 'video' ? 'Video' : 'Thumbnail'} prepared: ${file.name}`,
      {
        description: `Size: ${data.file_size}${data.dimensions ? ` • ${data.dimensions.width}x${data.dimensions.height}` : ''}`,
      }
    );
    
    return {
      referenceId: data.reference_id,
      fileName: data.file_name,
      fileSize: data.file_size,
      fileType: fileType,
      expiresAt: data.expires_at,
      dimensions: data.dimensions,
      warnings: data.warnings,
    };
    
  } catch (error) {
    console.error('Failed to prepare YouTube upload:', error);
    toast.error(`Failed to prepare ${fileType}: ${error instanceof Error ? error.message : 'Unknown error'}`);
    return null;
  }
}

/**
 * Handle multiple files for YouTube upload
 * Automatically detects and categorizes video and thumbnail files
 */
export async function handleYouTubeFiles(
  files: File[],
  onUploadPrepared?: (references: YouTubeUploadReference[]) => void
): Promise<{
  videos: YouTubeUploadReference[];
  thumbnails: YouTubeUploadReference[];
}> {
  const references = {
    videos: [] as YouTubeUploadReference[],
    thumbnails: [] as YouTubeUploadReference[],
  };
  
  // Categorize files
  const videoFiles = files.filter(isVideoFile);
  const thumbnailFiles = files.filter(isThumbnailFile);
  const unknownFiles = files.filter(f => detectFileType(f) === 'unknown');
  
  // Notify about file detection
  if (videoFiles.length > 0) {
    toast.info(`Detected ${videoFiles.length} video file${videoFiles.length > 1 ? 's' : ''}`);
  }
  if (thumbnailFiles.length > 0) {
    toast.info(`Detected ${thumbnailFiles.length} thumbnail${thumbnailFiles.length > 1 ? 's' : ''}`);
  }
  if (unknownFiles.length > 0) {
    toast.warning(`${unknownFiles.length} file${unknownFiles.length > 1 ? 's' : ''} of unknown type`);
  }
  
  // Process video files
  for (const file of videoFiles) {
    const reference = await prepareYouTubeUpload(file, 'video');
    if (reference) {
      references.videos.push(reference);
    }
  }
  
  // Process thumbnail files
  for (const file of thumbnailFiles) {
    const reference = await prepareYouTubeUpload(file, 'thumbnail');
    if (reference) {
      references.thumbnails.push(reference);
    }
  }
  
  // Callback with all prepared references
  const allReferences = [...references.videos, ...references.thumbnails];
  if (onUploadPrepared && allReferences.length > 0) {
    onUploadPrepared(allReferences);
  }
  
  // Show summary if files were prepared
  if (allReferences.length > 0) {
    const summary = [];
    if (references.videos.length > 0) {
      summary.push(`${references.videos.length} video${references.videos.length > 1 ? 's' : ''}`);
    }
    if (references.thumbnails.length > 0) {
      summary.push(`${references.thumbnails.length} thumbnail${references.thumbnails.length > 1 ? 's' : ''}`);
    }
    
    const description = references.videos.length > 0 
      ? `Prepared ${summary.join(' and ')}. You can now ask the AI to upload to YouTube.`
      : `Thumbnail prepared. It will be used when you upload a video.`;
    
    toast.success(
      `YouTube files ready`,
      {
        description,
        duration: 5000,
      }
    );
  }
  
  return references;
}

/**
 * Get the latest pending uploads for the current user
 * Used to display what files are ready for upload
 */
export async function getLatestPendingUploads(): Promise<{
  video?: YouTubeUploadReference;
  thumbnail?: YouTubeUploadReference;
} | null> {
  try {
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    
    if (!session?.access_token) {
      return null;
    }
    
    const response = await fetch(`${API_URL}/youtube/pending-uploads`, {
      headers: {
        'Authorization': `Bearer ${session.access_token}`,
      },
    });
    
    if (!response.ok) {
      throw new Error('Failed to get pending uploads');
    }
    
    const data = await response.json();
    
    const result: { video?: YouTubeUploadReference; thumbnail?: YouTubeUploadReference } = {};
    
    if (data.video) {
      result.video = {
        referenceId: data.video.reference_id,
        fileName: data.video.file_name,
        fileSize: data.video.file_size,
        fileType: 'video',
        expiresAt: data.video.expires_at,
      };
    }
    
    if (data.thumbnail) {
      result.thumbnail = {
        referenceId: data.thumbnail.reference_id,
        fileName: data.thumbnail.file_name,
        fileSize: data.thumbnail.file_size,
        fileType: 'thumbnail',
        expiresAt: data.thumbnail.expires_at,
      };
    }
    
    return result;
    
  } catch (error) {
    console.error('Failed to get pending uploads:', error);
    return null;
  }
}

/**
 * Get upload status for tracking progress
 */
export async function getUploadStatus(uploadId: string): Promise<UploadProgress | null> {
  try {
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    
    if (!session?.access_token) {
      return null;
    }
    
    const response = await fetch(`${API_URL}/youtube/upload-status/${uploadId}`, {
      headers: {
        'Authorization': `Bearer ${session.access_token}`,
      },
    });
    
    if (!response.ok) {
      throw new Error('Failed to get upload status');
    }
    
    const data = await response.json();
    
    return {
      video: {
        status: data.video.status,
        progress: data.video.progress,
        referenceId: data.video.reference_id,
        error: data.video.error,
      },
      thumbnail: data.thumbnail ? {
        status: data.thumbnail.status,
        referenceId: data.thumbnail.reference_id,
        error: data.thumbnail.error,
      } : {
        status: 'pending',
      },
    };
    
  } catch (error) {
    console.error('Failed to get upload status:', error);
    return null;
  }
}

/**
 * Generate a smart message for the AI when YouTube files are detected
 */
export function generateYouTubeUploadMessage(
  videoFile?: string,
  thumbnailFile?: string
): string {
  if (videoFile && thumbnailFile) {
    return `Upload video "${videoFile}" with thumbnail "${thumbnailFile}" to YouTube. Use an engaging title and description based on the video content.`;
  } else if (videoFile) {
    return `Upload video "${videoFile}" to YouTube. Generate an engaging title and description based on the video content.`;
  } else if (thumbnailFile) {
    // Only having a thumbnail without a video is less common, just notify
    return `Thumbnail "${thumbnailFile}" is ready for your next YouTube video upload.`;
  }
  return '';
}

/**
 * Component to show YouTube upload status in chat
 */
export function YouTubeUploadStatus({ 
  references 
}: { 
  references: YouTubeUploadReference[] 
}) {
  if (references.length === 0) return null;
  
  const videos = references.filter(r => r.fileType === 'video');
  const thumbnails = references.filter(r => r.fileType === 'thumbnail');
  
  return (
    <div className="flex flex-col gap-2 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
      <div className="flex items-center gap-2">
        <svg className="w-5 h-5 text-red-600" fill="currentColor" viewBox="0 0 24 24">
          <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
        </svg>
        <span className="text-red-600 dark:text-red-400 font-medium">
          YouTube Upload Ready
        </span>
      </div>
      
      {videos.length > 0 && (
        <div className="space-y-1">
          <div className="text-sm font-medium text-red-700 dark:text-red-300">
            Video{videos.length > 1 ? 's' : ''}:
          </div>
          {videos.map(video => (
            <div key={video.referenceId} className="text-sm text-red-600 dark:text-red-400 pl-4">
              🎬 {video.fileName} ({video.fileSize})
            </div>
          ))}
        </div>
      )}
      
      {thumbnails.length > 0 && (
        <div className="space-y-1">
          <div className="text-sm font-medium text-red-700 dark:text-red-300">
            Thumbnail{thumbnails.length > 1 ? 's' : ''}:
          </div>
          {thumbnails.map(thumbnail => (
            <div key={thumbnail.referenceId} className="text-sm text-red-600 dark:text-red-400 pl-4">
              🖼️ {thumbnail.fileName} ({thumbnail.fileSize})
              {thumbnail.dimensions && (
                <span className="text-xs ml-2">
                  {thumbnail.dimensions.width}x{thumbnail.dimensions.height}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
      
      <div className="text-xs text-red-500 dark:text-red-500 mt-1">
        {videos.length > 0 && thumbnails.length > 0 
          ? 'Video and thumbnail will be automatically paired for upload'
          : videos.length > 0 
          ? 'Video ready for upload (thumbnail optional)'
          : 'Thumbnail will be used with your next video upload'}
      </div>
    </div>
  );
}