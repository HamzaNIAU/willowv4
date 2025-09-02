'use client'

import React, { useState } from 'react';
import {
  Play,
  ExternalLink,
  Copy,
  CheckCircle,
  Clock,
  Eye,
  Tag,
  User,
  Calendar,
  Shield,
  Share2
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface VideoDetails {
  video_id: string;
  url: string;
  embed_url: string;
  title: string;
  description: string;
  thumbnail: string;
  channel: {
    id: string;
    name: string;
    profile_picture?: string;
    subscriber_count?: number;
  };
  privacy: string;
  tags: string[];
  duration?: string;
  view_count?: string;
  published_at?: string;
}

interface YouTubeUploadResultViewProps {
  video_details: VideoDetails;
  message: string;
  timestamp?: string;
}

function formatDuration(duration: string): string {
  if (!duration) return '';
  // Parse ISO 8601 duration (PT5M30S -> 5:30)
  const match = duration.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
  if (!match) return duration;
  
  const hours = parseInt(match[1] || '0');
  const minutes = parseInt(match[2] || '0');
  const seconds = parseInt(match[3] || '0');
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

function formatNumber(num: string | number | undefined): string {
  if (!num) return '0';
  const numValue = typeof num === 'string' ? parseInt(num) : num;
  if (numValue >= 1000000) {
    return (numValue / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
  }
  if (numValue >= 1000) {
    return (numValue / 1000).toFixed(1).replace(/\.0$/, '') + 'K';
  }
  return numValue.toString();
}

function getPrivacyColor(privacy: string): string {
  switch (privacy.toLowerCase()) {
    case 'public': return 'bg-green-500';
    case 'unlisted': return 'bg-yellow-500';
    case 'private': return 'bg-red-500';
    default: return 'bg-gray-500';
  }
}

function getPrivacyIcon(privacy: string): React.ReactNode {
  switch (privacy.toLowerCase()) {
    case 'public': return <Eye className="h-3 w-3" />;
    case 'unlisted': return <Share2 className="h-3 w-3" />;
    case 'private': return <Shield className="h-3 w-3" />;
    default: return <Shield className="h-3 w-3" />;
  }
}

export function YouTubeUploadResultView({
  video_details,
  message,
  timestamp
}: YouTubeUploadResultViewProps) {
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [imageError, setImageError] = useState(false);

  const handleCopyUrl = async () => {
    try {
      await navigator.clipboard.writeText(video_details.url);
      setCopiedUrl(true);
      toast.success('YouTube link copied to clipboard!');
      setTimeout(() => setCopiedUrl(false), 2000);
    } catch (error) {
      toast.error('Failed to copy link');
    }
  };

  const handleOpenVideo = () => {
    window.open(video_details.url, '_blank', 'noopener,noreferrer');
  };

  const truncateDescription = (text: string, maxLength: number = 150) => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  };

  return (
    <Card className="overflow-hidden border border-border shadow-sm">
      {/* Header */}
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* YouTube Logo */}
            <div className="flex items-center justify-center w-10 h-10 bg-white rounded-lg shadow-md p-1.5">
              <img 
                src="/platforms/youtube.svg" 
                alt="YouTube"
                className="w-full h-full object-contain"
              />
            </div>
            <div>
              <CardTitle className="text-lg font-bold text-foreground flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-green-500" />
                Upload Complete!
              </CardTitle>
              {timestamp && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  {new Date(timestamp).toLocaleString()}
                </p>
              )}
            </div>
          </div>
          <Badge className="bg-green-500 text-white border-0 hover:bg-green-600">
            <CheckCircle className="h-3 w-3 mr-1" />
            Live
          </Badge>
        </div>
      </CardHeader>

      {/* Content */}
      <CardContent className="p-4 space-y-4">
        {/* Embedded YouTube Player */}
        <div className="relative">
          <div className="aspect-video bg-black rounded-lg overflow-hidden">
            <iframe
              src={`https://www.youtube.com/embed/${video_details.video_id}?autoplay=0&mute=0&controls=1&rel=0`}
              title={video_details.title}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              className="w-full h-full border-0"
            />
          </div>
        </div>

        {/* Video Info */}
        <div className="space-y-4">
          {/* Title */}
          <div>
            <h3 className="text-xl font-bold text-foreground mb-2 line-clamp-2">
              {video_details.title}
            </h3>
            
            {/* Channel Info */}
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                {video_details.channel.profile_picture ? (
                  <img
                    src={video_details.channel.profile_picture}
                    alt={video_details.channel.name}
                    className="w-6 h-6 rounded-full"
                  />
                ) : (
                  <User className="h-4 w-4" />
                )}
                <span className="font-medium">{video_details.channel.name}</span>
              </div>
              
              {video_details.channel.subscriber_count && (
                <div className="flex items-center gap-1">
                  <User className="h-3 w-3" />
                  <span>{formatNumber(video_details.channel.subscriber_count)} subscribers</span>
                </div>
              )}
            </div>
          </div>

          {/* Stats Row */}
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            {video_details.view_count && (
              <div className="flex items-center gap-1">
                <Eye className="h-4 w-4" />
                <span>{formatNumber(video_details.view_count)} views</span>
              </div>
            )}
            
            {video_details.published_at && (
              <div className="flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                <span>{new Date(video_details.published_at).toLocaleDateString()}</span>
              </div>
            )}
            
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge className={`${getPrivacyColor(video_details.privacy)} text-white border-0`}>
                    {getPrivacyIcon(video_details.privacy)}
                    <span className="ml-1 capitalize">{video_details.privacy}</span>
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>
                  <p>{video_details.privacy === 'public' ? 'Visible to everyone' : 
                      video_details.privacy === 'unlisted' ? 'Only people with the link can view' :
                      'Only you can view this video'}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>

          {/* Description */}
          {video_details.description && (
            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3">
              <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                {truncateDescription(video_details.description)}
              </p>
            </div>
          )}

          {/* Tags */}
          {video_details.tags && video_details.tags.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                <Tag className="h-4 w-4" />
                <span>Tags</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {video_details.tags.slice(0, 8).map((tag, index) => (
                  <Badge key={index} variant="outline" className="text-xs">
                    #{tag}
                  </Badge>
                ))}
                {video_details.tags.length > 8 && (
                  <Badge variant="outline" className="text-xs">
                    +{video_details.tags.length - 8} more
                  </Badge>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3 pt-4 border-t border-border">
          <Button
            onClick={handleOpenVideo}
            variant="default"
            className="flex-1"
          >
            <ExternalLink className="h-4 w-4 mr-2" />
            Watch on YouTube
          </Button>
          
          <Button
            variant="outline"
            onClick={handleCopyUrl}
            className="flex items-center gap-2"
          >
            {copiedUrl ? (
              <CheckCircle className="h-4 w-4 text-green-600" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
            {copiedUrl ? 'Copied!' : 'Copy Link'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}