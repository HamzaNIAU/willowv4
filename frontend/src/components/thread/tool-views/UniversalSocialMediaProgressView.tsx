'use client';

import React, { useEffect, useState } from 'react';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { createClient } from '@/lib/supabase/client';
import { 
  Upload, 
  CheckCircle, 
  AlertCircle, 
  Clock, 
  Users, 
  Eye,
  Heart,
  Share,
  MessageCircle 
} from 'lucide-react';

interface PlatformConfig {
  name: string;
  color: string;
  icon: string;
  gradientFrom: string;
  gradientTo: string;
}

const PLATFORM_CONFIGS: Record<string, PlatformConfig> = {
  youtube: {
    name: 'YouTube',
    color: 'bg-red-500',
    icon: '📺',
    gradientFrom: 'from-red-500',
    gradientTo: 'to-red-600'
  },
  tiktok: {
    name: 'TikTok', 
    color: 'bg-black',
    icon: '🎵',
    gradientFrom: 'from-black',
    gradientTo: 'to-gray-800'
  },
  instagram: {
    name: 'Instagram',
    color: 'bg-gradient-to-r from-purple-500 to-pink-500',
    icon: '📷',
    gradientFrom: 'from-purple-500',
    gradientTo: 'to-pink-500'
  },
  twitter: {
    name: 'Twitter/X',
    color: 'bg-blue-500',
    icon: '🐦',
    gradientFrom: 'from-blue-500', 
    gradientTo: 'to-blue-600'
  },
  linkedin: {
    name: 'LinkedIn',
    color: 'bg-blue-600',
    icon: '💼',
    gradientFrom: 'from-blue-600',
    gradientTo: 'to-blue-700'
  },
  facebook: {
    name: 'Facebook',
    color: 'bg-blue-600',
    icon: '👥',
    gradientFrom: 'from-blue-600',
    gradientTo: 'to-blue-700'
  }
};

interface UniversalSocialMediaProgressProps {
  upload_id: string;
  title: string;
  platform: string;
  account_name?: string;
}

interface UploadStatus {
  success: boolean;
  upload_id: string;
  platform: string;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'failed';
  progress: number;
  bytes_uploaded: number;
  total_bytes: number;
  status_message: string;
  account: {
    id: string;
    name: string;
    username?: string;
    profile_picture?: string;
    follower_count: number;
    is_verified: boolean;
  };
  content: {
    title: string;
    description?: string;
    file_name: string;
    file_size: number;
    privacy_status?: string;
  };
  platform_data: {
    post_id?: string;
    url?: string;
    embed_url?: string;
    metadata: Record<string, any>;
  };
  analytics: {
    view_count: number;
    like_count: number;
    share_count: number;
    comment_count: number;
  };
}

export function UniversalSocialMediaProgressView({
  upload_id,
  title,
  platform,
  account_name
}: UniversalSocialMediaProgressProps) {
  const [uploadStatus, setUploadStatus] = useState<UploadStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const platformConfig = PLATFORM_CONFIGS[platform.toLowerCase()] || {
    name: platform.charAt(0).toUpperCase() + platform.slice(1),
    color: 'bg-gray-500',
    icon: '📤',
    gradientFrom: 'from-gray-500',
    gradientTo: 'to-gray-600'
  };

  useEffect(() => {
    const fetchUploadStatus = async () => {
      try {
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        
        if (!session?.access_token) {
          setError('Authentication required');
          return;
        }

        const response = await fetch(`/api/social-media/upload-status/${upload_id}`, {
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json'
          }
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data: UploadStatus = await response.json();
        setUploadStatus(data);

        // If upload is complete, stop polling
        if (data.status === 'completed' || data.status === 'failed') {
          return;
        }
      } catch (err) {
        console.error('Failed to fetch upload status:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
      }
    };

    // Initial fetch
    fetchUploadStatus();

    // Poll every 2 seconds for active uploads
    const interval = setInterval(fetchUploadStatus, 2000);

    return () => clearInterval(interval);
  }, [upload_id]);

  if (error) {
    return (
      <Card className="max-w-2xl mx-auto">
        <CardContent className="pt-6">
          <div className="flex items-center gap-3 text-red-600">
            <AlertCircle className="h-5 w-5" />
            <span>Error loading upload status: {error}</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!uploadStatus) {
    return (
      <Card className="max-w-2xl mx-auto">
        <CardContent className="pt-6">
          <div className="flex items-center gap-3">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-gray-900"></div>
            <span>Loading upload status...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'failed':
        return <AlertCircle className="h-5 w-5 text-red-500" />;
      case 'uploading':
      case 'processing':
        return <Upload className="h-5 w-5 text-blue-500 animate-pulse" />;
      default:
        return <Clock className="h-5 w-5 text-yellow-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'failed':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'uploading':
      case 'processing':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      default:
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    }
  };

  const isCompleted = uploadStatus.status === 'completed';
  const hasPlatformData = uploadStatus.platform_data.post_id;

  return (
    <Card className="max-w-2xl mx-auto">
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className={`flex items-center justify-center w-12 h-12 rounded-full bg-gradient-to-r ${platformConfig.gradientFrom} ${platformConfig.gradientTo} text-white text-xl`}>
            {platformConfig.icon}
          </div>
          <div className="flex-1">
            <CardTitle className="text-lg">{platformConfig.name} Upload</CardTitle>
            <p className="text-sm text-muted-foreground">{uploadStatus.content.title}</p>
          </div>
          <Badge className={`${getStatusColor(uploadStatus.status)} border`}>
            <div className="flex items-center gap-1">
              {getStatusIcon(uploadStatus.status)}
              {uploadStatus.status.charAt(0).toUpperCase() + uploadStatus.status.slice(1)}
            </div>
          </Badge>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-6">
        {/* Account Info */}
        <div className="flex items-center gap-3 p-3 bg-muted rounded-lg">
          <Avatar className="h-10 w-10">
            <AvatarImage 
              src={uploadStatus.account.profile_picture} 
              alt={uploadStatus.account.name} 
            />
            <AvatarFallback>
              {uploadStatus.account.name.charAt(0).toUpperCase()}
            </AvatarFallback>
          </Avatar>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="font-medium">{uploadStatus.account.name}</span>
              {uploadStatus.account.is_verified && (
                <CheckCircle className="h-4 w-4 text-blue-500" />
              )}
            </div>
            {uploadStatus.account.username && (
              <span className="text-sm text-muted-foreground">
                @{uploadStatus.account.username}
              </span>
            )}
            {uploadStatus.account.follower_count > 0 && (
              <div className="flex items-center gap-1 text-sm text-muted-foreground">
                <Users className="h-3 w-3" />
                {uploadStatus.account.follower_count.toLocaleString()} followers
              </div>
            )}
          </div>
        </div>

        {/* Progress Bar */}
        {!isCompleted && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Upload Progress</span>
              <span>{Math.round(uploadStatus.progress)}%</span>
            </div>
            <Progress value={uploadStatus.progress} className="h-2" />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>{formatFileSize(uploadStatus.bytes_uploaded)} uploaded</span>
              <span>{formatFileSize(uploadStatus.total_bytes)} total</span>
            </div>
            {uploadStatus.status_message && (
              <p className="text-sm text-muted-foreground">{uploadStatus.status_message}</p>
            )}
          </div>
        )}

        {/* Completion Info */}
        {isCompleted && hasPlatformData && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-green-600">
              <CheckCircle className="h-5 w-5" />
              <span className="font-medium">Upload completed successfully!</span>
            </div>
            
            {/* Analytics (if available) */}
            {(uploadStatus.analytics.view_count > 0 || 
              uploadStatus.analytics.like_count > 0 || 
              uploadStatus.analytics.share_count > 0) && (
              <div className="grid grid-cols-4 gap-4 p-3 bg-muted rounded-lg">
                <div className="text-center">
                  <div className="flex items-center justify-center gap-1">
                    <Eye className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">
                      {uploadStatus.analytics.view_count.toLocaleString()}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground">Views</span>
                </div>
                <div className="text-center">
                  <div className="flex items-center justify-center gap-1">
                    <Heart className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">
                      {uploadStatus.analytics.like_count.toLocaleString()}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground">Likes</span>
                </div>
                <div className="text-center">
                  <div className="flex items-center justify-center gap-1">
                    <Share className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">
                      {uploadStatus.analytics.share_count.toLocaleString()}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground">Shares</span>
                </div>
                <div className="text-center">
                  <div className="flex items-center justify-center gap-1">
                    <MessageCircle className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">
                      {uploadStatus.analytics.comment_count.toLocaleString()}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground">Comments</span>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            {uploadStatus.platform_data.url && (
              <div className="flex gap-2">
                <a
                  href={uploadStatus.platform_data.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white px-4 py-2 rounded-lg text-center font-medium transition-colors"
                >
                  View on {platformConfig.name}
                </a>
                {uploadStatus.platform_data.embed_url && (
                  <button
                    onClick={() => navigator.clipboard.writeText(uploadStatus.platform_data.embed_url || '')}
                    className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    Copy Embed
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* Error State */}
        {uploadStatus.status === 'failed' && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center gap-2 text-red-800">
              <AlertCircle className="h-5 w-5" />
              <span className="font-medium">Upload Failed</span>
            </div>
            {uploadStatus.status_message && (
              <p className="text-sm text-red-700 mt-1">{uploadStatus.status_message}</p>
            )}
          </div>
        )}

        {/* File Info */}
        <div className="text-xs text-muted-foreground space-y-1">
          <div>File: {uploadStatus.content.file_name}</div>
          <div>Size: {formatFileSize(uploadStatus.content.file_size)}</div>
          {uploadStatus.content.privacy_status && (
            <div>Privacy: {uploadStatus.content.privacy_status.charAt(0).toUpperCase() + uploadStatus.content.privacy_status.slice(1)}</div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}