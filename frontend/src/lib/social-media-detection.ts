/**
 * Social Media Intent Detection
 * 
 * Intelligently detects when users intend to upload content to social media platforms
 * based on message content and file types.
 */

// Social media platform keywords and patterns
const SOCIAL_PLATFORMS = {
  youtube: ['youtube', 'yt', 'video upload', 'publish video', 'post video', 'youtube channel'],
  tiktok: ['tiktok', 'tik tok', 'short video', 'vertical video', 'fyp', 'for you page'],
  instagram: ['instagram', 'insta', 'ig', 'story', 'reel', 'igtv', 'feed post', 'carousel'],
  twitter: ['twitter', 'tweet', 'x.com', 'x platform', 'post on x', 'thread'],
  facebook: ['facebook', 'fb', 'meta', 'fb post', 'facebook page', 'facebook video'],
  linkedin: ['linkedin', 'professional post', 'linkedin post', 'career update', 'professional network'],
  snapchat: ['snapchat', 'snap', 'story', 'spotlight'],
  pinterest: ['pinterest', 'pin', 'board', 'pinterest board'],
  reddit: ['reddit', 'subreddit', 'post to reddit', 'r/'],
  discord: ['discord', 'discord server', 'discord channel']
};

// Upload intent keywords
const UPLOAD_KEYWORDS = [
  'upload', 'post', 'publish', 'share', 'submit',
  'put on', 'add to', 'send to', 'create post',
  'make a post', 'schedule', 'release'
];

// Content creation keywords that might indicate future upload
const CREATION_KEYWORDS = [
  'for youtube', 'for tiktok', 'for instagram',
  'social media', 'content', 'viral', 'thumbnail'
];

export interface SocialMediaIntent {
  detected: boolean;
  platform?: string;
  confidence: 'high' | 'medium' | 'low';
  shouldCreateReference: boolean;
}

/**
 * Detects if a message indicates intent to upload to social media
 */
export function detectSocialMediaIntent(
  message: string,
  fileType?: string,
  fileName?: string
): SocialMediaIntent {
  const lowerMessage = message.toLowerCase();
  
  // ONLY check for explicit platform mentions
  // Don't trigger on generic upload keywords or file types
  for (const [platform, keywords] of Object.entries(SOCIAL_PLATFORMS)) {
    for (const keyword of keywords) {
      if (lowerMessage.includes(keyword)) {
        // High confidence only if both platform AND upload action are mentioned
        const hasUploadKeyword = UPLOAD_KEYWORDS.some(k => lowerMessage.includes(k));
        
        // Only return high confidence if BOTH platform and action are present
        // This prevents "I made this for YouTube" from triggering without upload intent
        if (hasUploadKeyword) {
          return {
            detected: true,
            platform,
            confidence: 'high',
            shouldCreateReference: true
          };
        }
        
        // Medium confidence if only platform is mentioned
        // Won't trigger reference system due to shouldUseReferenceSystem requiring 'high'
        return {
          detected: true,
          platform,
          confidence: 'medium',
          shouldCreateReference: false
        };
      }
    }
  }
  
  // Don't check for generic upload keywords without platform
  // Don't check for creation keywords
  // Don't check filename hints
  // This ensures regular file uploads work normally
  
  // No social media intent detected
  return {
    detected: false,
    confidence: 'low',
    shouldCreateReference: false
  };
}

/**
 * Determines the best upload endpoint based on file type and intent
 */
export function getUploadEndpoint(
  fileType: string,
  platform?: string
): string {
  // For now, we only have YouTube endpoints
  // In the future, add more platform-specific endpoints
  
  if (platform === 'youtube' || fileType.startsWith('video/')) {
    return '/api/youtube/prepare-upload';
  }
  
  if (fileType.startsWith('image/')) {
    // Could be thumbnail
    return '/api/youtube/prepare-thumbnail';
  }
  
  // Default to regular file upload
  return null;
}

/**
 * Checks if we should use reference ID system for this upload
 */
export function shouldUseReferenceSystem(
  message: string,
  fileType: string,
  fileName: string
): boolean {
  // Only use reference system when social media platforms are explicitly mentioned
  // Regular file uploads should work normally
  const intent = detectSocialMediaIntent(message, fileType, fileName);
  
  // Only activate for high confidence social media intent
  // This ensures reference system doesn't interfere with regular files
  return intent.detected && intent.confidence === 'high';
}

/**
 * Get appropriate file type for reference system
 */
export function getReferenceFileType(mimeType: string): 'video' | 'thumbnail' | null {
  if (mimeType.startsWith('video/')) {
    return 'video';
  }
  
  if (mimeType.startsWith('image/')) {
    return 'thumbnail';
  }
  
  return null;
}