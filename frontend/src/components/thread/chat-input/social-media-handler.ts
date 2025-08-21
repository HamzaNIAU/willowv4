/**
 * Social Media Content Handler
 * 
 * Provides metadata about files for social media without auto-routing to platforms.
 * The AI agent decides which platform to use based on user's message.
 */

// File categories for content classification
export type FileCategory = 'video' | 'image' | 'document' | 'audio' | 'other';
export type SocialPlatform = 'youtube' | 'tiktok' | 'instagram' | 'twitter' | 'facebook' | 'linkedin';

// Social media compatibility for different file types
const PLATFORM_COMPATIBILITY: Record<SocialPlatform, {
  supportedTypes: string[];
  maxSizeMB: number;
  features: string[];
}> = {
  youtube: {
    supportedTypes: ['video/mp4', 'video/mov', 'video/avi', 'video/webm', 'image/jpeg', 'image/png'],
    maxSizeMB: 128000, // 128GB
    features: ['videos', 'thumbnails', 'shorts', 'live-streaming']
  },
  tiktok: {
    supportedTypes: ['video/mp4', 'video/mov'],
    maxSizeMB: 287, // 287MB
    features: ['short-videos', 'reels']
  },
  instagram: {
    supportedTypes: ['video/mp4', 'video/mov', 'image/jpeg', 'image/png'],
    maxSizeMB: 100, // 100MB for videos, 30MB for images
    features: ['posts', 'stories', 'reels', 'igtv']
  },
  twitter: {
    supportedTypes: ['video/mp4', 'image/jpeg', 'image/png', 'image/gif'],
    maxSizeMB: 512, // 512MB
    features: ['tweets', 'threads', 'spaces']
  },
  facebook: {
    supportedTypes: ['video/mp4', 'video/mov', 'image/jpeg', 'image/png'],
    maxSizeMB: 10240, // 10GB
    features: ['posts', 'stories', 'reels', 'live']
  },
  linkedin: {
    supportedTypes: ['video/mp4', 'image/jpeg', 'image/png', 'document/pdf'],
    maxSizeMB: 5120, // 5GB
    features: ['posts', 'articles', 'documents']
  }
};

/**
 * Get file category based on MIME type
 */
export function getFileCategory(mimeType: string): FileCategory {
  if (mimeType.startsWith('video/')) return 'video';
  if (mimeType.startsWith('image/')) return 'image';
  if (mimeType.startsWith('audio/')) return 'audio';
  if (
    mimeType.includes('pdf') ||
    mimeType.includes('document') ||
    mimeType.includes('text') ||
    mimeType.includes('spreadsheet') ||
    mimeType.includes('presentation')
  ) {
    return 'document';
  }
  return 'other';
}

/**
 * Check if content is suitable for social media
 */
export function isSocialMediaContent(file: File): boolean {
  const category = getFileCategory(file.type);
  return category === 'video' || category === 'image';
}

/**
 * Get compatible platforms for a file
 */
export function getCompatiblePlatforms(file: File): SocialPlatform[] {
  const compatible: SocialPlatform[] = [];
  const fileSizeMB = file.size / (1024 * 1024);
  
  for (const [platform, config] of Object.entries(PLATFORM_COMPATIBILITY)) {
    // Check if file type is supported
    const typeSupported = config.supportedTypes.some(type => {
      if (type.includes('*')) {
        const prefix = type.split('*')[0];
        return file.type.startsWith(prefix);
      }
      return file.type === type;
    });
    
    // Check if file size is within limits
    const sizeOk = fileSizeMB <= config.maxSizeMB;
    
    if (typeSupported && sizeOk) {
      compatible.push(platform as SocialPlatform);
    }
  }
  
  return compatible;
}

/**
 * Get metadata for a file
 */
export interface FileMetadata {
  fileName: string;
  fileSize: number;
  mimeType: string;
  category: FileCategory;
  isSocialMedia: boolean;
  compatiblePlatforms: SocialPlatform[];
  suggestions: string[];
}

export function getFileMetadata(file: File): FileMetadata {
  const category = getFileCategory(file.type);
  const isSocialMedia = isSocialMediaContent(file);
  const compatiblePlatforms = isSocialMedia ? getCompatiblePlatforms(file) : [];
  
  // Generate suggestions based on file type and compatible platforms
  const suggestions: string[] = [];
  
  if (category === 'video') {
    if (compatiblePlatforms.includes('youtube')) {
      suggestions.push('Upload to YouTube');
    }
    if (compatiblePlatforms.includes('tiktok')) {
      suggestions.push('Create TikTok video');
    }
    if (compatiblePlatforms.includes('instagram')) {
      suggestions.push('Post Instagram Reel');
    }
  } else if (category === 'image') {
    if (compatiblePlatforms.includes('instagram')) {
      suggestions.push('Post to Instagram');
    }
    if (compatiblePlatforms.includes('twitter')) {
      suggestions.push('Tweet with image');
    }
  }
  
  return {
    fileName: file.name,
    fileSize: file.size,
    mimeType: file.type,
    category,
    isSocialMedia,
    compatiblePlatforms,
    suggestions
  };
}

/**
 * Parse user message for platform intent
 */
export function detectPlatformIntent(message: string): SocialPlatform | null {
  const lowerMessage = message.toLowerCase();
  
  const platformKeywords: Record<SocialPlatform, string[]> = {
    youtube: ['youtube', 'yt', 'video upload', 'upload video'],
    tiktok: ['tiktok', 'tik tok', 'tt'],
    instagram: ['instagram', 'insta', 'ig', 'reel', 'story'],
    twitter: ['twitter', 'tweet', 'x.com'],
    facebook: ['facebook', 'fb', 'meta'],
    linkedin: ['linkedin', 'li']
  };
  
  for (const [platform, keywords] of Object.entries(platformKeywords)) {
    if (keywords.some(keyword => lowerMessage.includes(keyword))) {
      return platform as SocialPlatform;
    }
  }
  
  return null;
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
 * Generate smart message based on file metadata
 */
export function generateSmartMessage(
  files: File[],
  userMessage: string = ''
): string | null {
  // Don't generate message if user already has one
  if (userMessage.trim()) return null;
  
  const metadata = files.map(getFileMetadata);
  const videos = metadata.filter(m => m.category === 'video');
  const images = metadata.filter(m => m.category === 'image');
  
  // Only suggest if we have social media content
  if (videos.length === 0 && images.length === 0) return null;
  
  // Build a contextual message
  if (videos.length > 0) {
    const video = videos[0];
    if (video.compatiblePlatforms.length > 0) {
      return `I have a video "${video.fileName}" ready. What would you like to do with it?`;
    }
  }
  
  if (images.length > 0) {
    const image = images[0];
    if (image.compatiblePlatforms.length > 0) {
      return `I have an image "${image.fileName}" ready. Where would you like to share it?`;
    }
  }
  
  return null;
}