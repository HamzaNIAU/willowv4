'use client';

import React, { forwardRef, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Paperclip, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { createClient } from '@/lib/supabase/client';
import { useQueryClient } from '@tanstack/react-query';
import { fileQueryKeys } from '@/hooks/react-query/files/use-file-queries';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { UploadedFile } from './chat-input';
import { normalizeFilenameToNFC } from '@/lib/utils/unicode';
import { handleSmartFileUpload } from './smart-file-handler';
import { shouldUseReferenceSystem } from '@/lib/social-media-detection';

const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL || '';

const handleLocalFiles = (
  files: File[],
  setPendingFiles: React.Dispatch<React.SetStateAction<File[]>>,
  setUploadedFiles: React.Dispatch<React.SetStateAction<UploadedFile[]>>,
) => {
  const filteredFiles = files.filter((file) => {
    if (file.size > 50 * 1024 * 1024) {
      toast.error(`File size exceeds 50MB limit: ${file.name}`);
      return false;
    }
    return true;
  });

  setPendingFiles((prevFiles) => [...prevFiles, ...filteredFiles]);

  const newUploadedFiles: UploadedFile[] = filteredFiles.map((file) => {
    // Normalize filename to NFC
    const normalizedName = normalizeFilenameToNFC(file.name);

    return {
      name: normalizedName,
      path: `/workspace/${normalizedName}`,
      size: file.size,
      type: file.type || 'application/octet-stream',
      localUrl: URL.createObjectURL(file)
    };
  });

  setUploadedFiles((prev) => [...prev, ...newUploadedFiles]);
  filteredFiles.forEach((file) => {
    const normalizedName = normalizeFilenameToNFC(file.name);
    toast.success(`File attached: ${normalizedName}`);
  });
};

const uploadFiles = async (
  files: File[],
  sandboxId: string,
  setUploadedFiles: React.Dispatch<React.SetStateAction<UploadedFile[]>>,
  setIsUploading: React.Dispatch<React.SetStateAction<boolean>>,
  messages: any[] = [], // Add messages parameter to check for existing files
  queryClient?: any, // Add queryClient parameter for cache invalidation
  uploadedFilesWithUrls?: UploadedFile[], // Pass in files that already have localUrl
  setSandboxId?: (id: string) => void, // Add callback to update sandbox ID
) => {
  try {
    // Early return if no sandboxId
    if (!sandboxId) {
      console.warn('No sandboxId provided for file upload');
      return;
    }
    
    setIsUploading(true);

    const newUploadedFiles: UploadedFile[] = [];

    for (const file of files) {
      if (file.size > 50 * 1024 * 1024) {
        toast.error(`File size exceeds 50MB limit: ${file.name}`);
        continue;
      }

      // Normalize filename to NFC
      const normalizedName = normalizeFilenameToNFC(file.name);
      const uploadPath = `/workspace/${normalizedName}`;

      // Check if this filename already exists in chat messages
      const isFileInChat = messages.some(message => {
        const content = typeof message.content === 'string' ? message.content : '';
        return content.includes(`[Uploaded File: ${uploadPath}]`);
      });

      const formData = new FormData();
      // If the filename was normalized, append with the normalized name in the field name
      // The server will use the path parameter for the actual filename
      formData.append('file', file, normalizedName);
      formData.append('path', uploadPath);

      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session?.access_token) {
        throw new Error('No access token available');
      }

      const response = await fetch(`${API_URL}/sandboxes/${sandboxId}/files`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${session.access_token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }

      // Parse response to get sandbox_id if it was created
      const responseData = await response.json();
      if (responseData.sandbox_id && setSandboxId) {
        // Update the sandbox ID if it was created on-demand
        setSandboxId(responseData.sandbox_id);
        console.log(`Updated sandbox ID to: ${responseData.sandbox_id}`);
      }

      // If file was already in chat and we have queryClient, invalidate its cache
      if (isFileInChat && queryClient) {
        // Invalidate all content types for this file
        ['text', 'blob', 'json'].forEach(contentType => {
          const queryKey = fileQueryKeys.content(sandboxId, uploadPath, contentType);
          queryClient.removeQueries({ queryKey });
        });

        // Also invalidate directory listing
        const directoryPath = uploadPath.substring(0, uploadPath.lastIndexOf('/'));
        queryClient.invalidateQueries({
          queryKey: fileQueryKeys.directory(sandboxId, directoryPath),
        });
      }

      // Find the corresponding uploaded file with localUrl if it exists
      const existingFile = uploadedFilesWithUrls?.find(f => f.name === normalizedName);
      
      newUploadedFiles.push({
        name: normalizedName,
        path: uploadPath,
        size: file.size,
        type: file.type || 'application/octet-stream',
        localUrl: existingFile?.localUrl, // Preserve the blob URL
        referenceId: existingFile?.referenceId, // Preserve reference metadata
        expiresAt: existingFile?.expiresAt,
      });

      toast.success(`File uploaded: ${normalizedName}`);
    }

    setUploadedFiles((prev) => [...prev, ...newUploadedFiles]);
  } catch (error) {
    console.error('File upload failed:', error);
    toast.error(
      typeof error === 'string'
        ? error
        : error instanceof Error
          ? error.message
          : 'Failed to upload file',
    );
  } finally {
    setIsUploading(false);
  }
};

const handleFiles = async (
  files: File[],
  sandboxId: string | undefined,
  setPendingFiles: React.Dispatch<React.SetStateAction<File[]>>,
  setUploadedFiles: React.Dispatch<React.SetStateAction<UploadedFile[]>>,
  setIsUploading: React.Dispatch<React.SetStateAction<boolean>>,
  messages: any[] = [], // Add messages parameter
  queryClient?: any, // Add queryClient parameter
  userMessage?: string, // Add user's message for intent detection
  userId?: string, // Add user ID for reference system
  setSandboxId?: (id: string) => void, // Add callback to update sandbox ID
) => {
  // Process all files normally first
  const uploadedFiles: UploadedFile[] = [];
  
  for (const file of files) {
    // Create normal file entry
    const normalizedName = normalizeFilenameToNFC(file.name);
    const fileInfo: UploadedFile = {
      name: normalizedName,
      path: `/workspace/${normalizedName}`,
      size: file.size,
      type: file.type || 'application/octet-stream',
      localUrl: URL.createObjectURL(file)
    };
    
    // Check if we should add reference metadata for social media
    // For video/image files attached without a message, always create reference ID
    const shouldCreateReference = shouldUseReferenceSystem(userMessage || '', file.type, file.name) ||
                                 (!userMessage && (file.type.startsWith('video/') || file.type.startsWith('image/')));
    
    if (shouldCreateReference && userId) {
      try {
        console.log(`[FileUploadHandler] Adding reference metadata for ${file.name}${!userMessage ? ' (auto-detected media file)' : ''}`);
        
        // Create reference ID for social media upload
        const formData = new FormData();
        formData.append('file', file);
        formData.append('file_type', file.type.startsWith('video/') ? 'video' : 'thumbnail');
        
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        
        if (session?.access_token) {
          const response = await fetch(`${API_URL}/youtube/prepare-upload`, {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${session.access_token}`,
            },
            body: formData,
          });
          
          if (response.ok) {
            const data = await response.json();
            // Add reference metadata to the file info
            fileInfo.referenceId = data.reference_id;
            fileInfo.expiresAt = data.expires_at;
            console.log(`[FileUploadHandler] Reference ID added: ${data.reference_id}`);
          }
        }
      } catch (error) {
        console.error('[FileUploadHandler] Failed to create reference:', error);
        // Continue without reference - file still works normally
      }
    }
    
    uploadedFiles.push(fileInfo);
  }
  
  // Handle sandbox upload if needed
  if (sandboxId && uploadedFiles.length > 0) {
    // Upload to sandbox (but files already have localUrl for display)
    await uploadFiles(files, sandboxId, setUploadedFiles, setIsUploading, messages, queryClient, uploadedFiles, setSandboxId);
  } else {
    // Just add to uploaded files
    setUploadedFiles((prev) => [...prev, ...uploadedFiles]);
    uploadedFiles.forEach((file) => {
      toast.success(`File attached: ${file.name}`);
    });
  }
};

interface FileUploadHandlerProps {
  loading: boolean;
  disabled: boolean;
  isAgentRunning: boolean;
  isUploading: boolean;
  sandboxId?: string;
  setSandboxId?: (id: string) => void; // Add callback to update sandbox ID
  setPendingFiles: React.Dispatch<React.SetStateAction<File[]>>;
  setUploadedFiles: React.Dispatch<React.SetStateAction<UploadedFile[]>>;
  setIsUploading: React.Dispatch<React.SetStateAction<boolean>>;
  messages?: any[]; // Add messages prop
  isLoggedIn?: boolean;
  userMessage?: string; // Current message for intent detection
  userId?: string; // User ID for reference system
}

export const FileUploadHandler = forwardRef<
  HTMLInputElement,
  FileUploadHandlerProps
>(
  (
    {
      loading,
      disabled,
      isAgentRunning,
      isUploading,
      sandboxId,
      setSandboxId,
      setPendingFiles,
      setUploadedFiles,
      setIsUploading,
      messages = [],
      isLoggedIn = true,
      userMessage,
      userId,
    },
    ref,
  ) => {
    const queryClient = useQueryClient();

    const handleFileUpload = () => {
      if (ref && 'current' in ref && ref.current) {
        ref.current.click();
      }
    };
    
    // Get current user ID if not provided
    const [currentUserId, setCurrentUserId] = useState(userId);
    useEffect(() => {
      if (!userId && isLoggedIn) {
        const supabase = createClient();
        supabase.auth.getUser().then(({ data }) => {
          if (data?.user?.id) {
            setCurrentUserId(data.user.id);
          }
        });
      }
    }, [userId, isLoggedIn]);

    const processFileUpload = async (
      event: React.ChangeEvent<HTMLInputElement>,
    ) => {
      if (!event.target.files || event.target.files.length === 0) return;

      const files = Array.from(event.target.files);
      
      // Use the simplified helper function
      handleFiles(
        files,
        sandboxId,
        setPendingFiles,
        setUploadedFiles,
        setIsUploading,
        messages,
        queryClient,
        userMessage, // Pass current message for intent detection
        currentUserId || userId, // Pass user ID for reference system
        setSandboxId, // Pass callback to update sandbox ID
      );

      event.target.value = '';
    };

    return (
      <>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-block">
                <Button
                  type="button"
                  onClick={handleFileUpload}
                  variant="outline"
                  size="sm"
                  className="h-8 w-8 p-2 bg-transparent border border-border rounded-xl text-muted-foreground hover:text-foreground hover:bg-accent/50 flex items-center justify-center"
                  disabled={
                    !isLoggedIn || loading || (disabled && !isAgentRunning) || isUploading
                  }
                >
                  {isUploading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Paperclip className="h-4 w-4" />
                  )}
                </Button>
              </span>
            </TooltipTrigger>
            <TooltipContent side="top">
              <p>{isLoggedIn ? 'Attach files (images, documents, videos, etc.)' : 'Please login to attach files'}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <input
          type="file"
          ref={ref}
          className="hidden"
          onChange={processFileUpload}
          multiple
          accept="*/*"
        />
      </>
    );
  },
);

FileUploadHandler.displayName = 'FileUploadHandler';
export { handleFiles, handleLocalFiles, uploadFiles };
