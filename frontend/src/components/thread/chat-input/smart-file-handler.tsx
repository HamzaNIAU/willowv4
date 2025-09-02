'use client';

import { toast } from 'sonner';
import { createClient } from '@/lib/supabase/client';
import { 
  detectSocialMediaIntent, 
  getReferenceFileType,
  shouldUseReferenceSystem 
} from '@/lib/social-media-detection';
import { UploadedFile } from './chat-input';

const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL || '';

export interface SmartUploadResult {
  type: 'reference' | 'sandbox';
  referenceId?: string;
  sandboxPath?: string;
  platform?: string;
  fileInfo: UploadedFile;
}

/**
 * Smart file handler that routes files based on intent detection
 */
export async function handleSmartFileUpload(
  file: File,
  message: string,
  sandboxId?: string,
  userId?: string
): Promise<SmartUploadResult> {
  try {
    // Detect if this is for social media
    const shouldUseReference = shouldUseReferenceSystem(
      message,
      file.type,
      file.name
    );
    
    if (shouldUseReference && userId) {
      // Use reference system for social media uploads
      return await uploadToReferenceSystem(file, userId, message);
    } else if (sandboxId) {
      // Use sandbox for regular attachments
      return await uploadToSandbox(file, sandboxId);
    } else {
      // No sandbox available, still check if we should use reference
      if (userId) {
        // Fallback to reference system if no sandbox
        return await uploadToReferenceSystem(file, userId, message);
      }
      throw new Error('No upload destination available');
    }
  } catch (error) {
    console.error('Smart file upload failed:', error);
    throw error;
  }
}

/**
 * Upload file to reference system for social media
 */
async function uploadToReferenceSystem(
  file: File,
  userId: string,
  message: string
): Promise<SmartUploadResult> {
  console.log(`[SmartHandler] Uploading to reference system - File: ${file.name}, Type: ${file.type}, Size: ${file.size}`);
  
  let fileType = getReferenceFileType(file.type);
  
  if (!fileType) {
    console.warn(`[SmartHandler] Unsupported file type: ${file.type}, defaulting to 'video'`);
    // Default to video for video files
    if (file.type.startsWith('video/')) {
      fileType = 'video';
    } else if (file.type.startsWith('image/')) {
      fileType = 'thumbnail';
    } else {
      throw new Error(`Unsupported file type for social media: ${file.type}`);
    }
  }
  
  // Detect platform from message
  const intent = detectSocialMediaIntent(message, file.type, file.name);
  console.log(`[SmartHandler] Detected intent:`, intent);
  
  // Prepare form data
  const formData = new FormData();
  formData.append('file', file);
  formData.append('file_type', fileType);
  
  // Get auth token
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  
  if (!session?.access_token) {
    throw new Error('Authentication required for social media uploads');
  }
  
  console.log(`[SmartHandler] Calling API: ${API_URL}/youtube/prepare-upload`);
  
  // Upload to reference system
  const response = await fetch(`${API_URL}/youtube/prepare-upload`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${session.access_token}`,
    },
    body: formData,
  });
  
  if (!response.ok) {
    const error = await response.text();
    console.error(`[SmartHandler] API error:`, error);
    throw new Error(`Reference upload failed: ${error}`);
  }
  
  const data = await response.json();
  console.log(`[SmartHandler] API response:`, data);
  
  // Show success message with platform info and full reference ID for debugging
  const platformName = intent.platform === 'youtube' ? 'YouTube' : 
                      intent.platform === 'twitter' ? 'Twitter' : 
                      intent.platform === 'instagram' ? 'Instagram' : 
                      'social media';
  
  // Enhanced success message with clear reference ID
  toast.success(
    <div>
      <strong>✅ File ready for {platformName} upload</strong>
      <br />
      <span style={{ fontSize: '0.9em', opacity: 0.9 }}>
        Reference ID: {data.reference_id}
      </span>
      <br />
      <span style={{ fontSize: '0.85em', opacity: 0.7 }}>
        File will be available for upload for 24 hours
      </span>
    </div>,
    { duration: 5000 }
  );
  
  console.log(`[Smart Upload] File prepared for ${platformName}:`, {
    referenceId: data.reference_id,
    fileName: file.name,
    fileType: fileType,
    platform: intent.platform
  });
  
  // Return normal file info with reference metadata
  // Keep the path as a normal path for display purposes
  return {
    type: 'reference',
    referenceId: data.reference_id,
    platform: intent.platform,
    fileInfo: {
      name: file.name,
      path: `/workspace/${file.name}`,  // Normal path for display
      size: file.size,
      type: file.type,
      localUrl: URL.createObjectURL(file),  // Create blob URL for immediate display
      referenceId: data.reference_id,  // Reference metadata for upload
      expiresAt: data.expires_at
    }
  };
}

/**
 * Upload file to sandbox for regular attachments
 */
async function uploadToSandbox(
  file: File,
  sandboxId: string
): Promise<SmartUploadResult> {
  const uploadPath = `/workspace/${file.name}`;
  
  const formData = new FormData();
  formData.append('file', file);
  formData.append('path', uploadPath);
  
  // Get auth token
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  
  if (!session?.access_token) {
    throw new Error('Authentication required');
  }
  
  // Upload to sandbox
  const response = await fetch(`${API_URL}/sandboxes/${sandboxId}/files`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${session.access_token}`,
    },
    body: formData,
  });
  
  if (!response.ok) {
    throw new Error(`Sandbox upload failed: ${response.statusText}`);
  }
  
  toast.success(`File uploaded: ${file.name}`);
  
  return {
    type: 'sandbox',
    sandboxPath: uploadPath,
    fileInfo: {
      name: file.name,
      path: uploadPath,
      size: file.size,
      type: file.type
    }
  };
}

/**
 * Process multiple files with smart routing
 */
export async function handleSmartFiles(
  files: File[],
  message: string,
  sandboxId?: string,
  userId?: string,
  setUploadedFiles?: React.Dispatch<React.SetStateAction<UploadedFile[]>>
): Promise<SmartUploadResult[]> {
  const results: SmartUploadResult[] = [];
  
  for (const file of files) {
    try {
      const result = await handleSmartFileUpload(
        file,
        message,
        sandboxId,
        userId
      );
      
      results.push(result);
      
      // Update UI if setter provided
      if (setUploadedFiles) {
        setUploadedFiles(prev => [...prev, result.fileInfo]);
      }
    } catch (error) {
      console.error(`Failed to upload ${file.name}:`, error);
      toast.error(`Failed to upload ${file.name}`);
    }
  }
  
  return results;
}