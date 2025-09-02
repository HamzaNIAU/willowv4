'use client'

import React from 'react';
import { ToolViewProps } from './types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ExternalLink, Eye, ThumbsUp, MessageCircle, Calendar } from 'lucide-react';
import { formatTimestamp, extractToolData } from './utils';

interface YouTubeUpload {
  video_id: string;
  title: string;
  url: string;
  upload_date?: string;
  views?: number;
  likes?: number;
  comments?: number;
  channel_name?: string;
  channel_id?: string;
  thumbnail?: string;
}

function formatNumber(num: number | undefined): string {
  if (!num) return '0';
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1).replace(/\.0$/, '') + 'K';
  }
  return num.toString();
}

function getYouTubeThumbnail(videoId: string): string {
  return `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`;
}

function extractVideoIdFromUrl(url: string): string | null {
  const match = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)/);
  return match ? match[1] : null;
}

export function YouTubeUploadHistoryView({
  name = 'youtube-check-upload-status',
  assistantContent,
  toolContent,
  assistantTimestamp,
  toolTimestamp,
  isSuccess = true,
  isStreaming = false,
}: ToolViewProps) {
  // Extract the tool data
  const { toolResult } = extractToolData(toolContent);
  
  // Parse upload data from tool result
  let uploads: YouTubeUpload[] = [];
  let message = '';
  
  if (toolResult?.toolOutput) {
    try {
      let parsedData: any;
      
      if (typeof toolResult.toolOutput === 'string') {
        // Try to parse the string content
        if (toolResult.toolOutput.includes('🎉')) {
          // Parse the formatted message response
          message = toolResult.toolOutput;
          
          // Extract video URLs from the message
          const urlMatches = toolResult.toolOutput.match(/https:\/\/www\.youtube\.com\/watch\?v=([^\\s\\n]+)/g);
          if (urlMatches) {
            uploads = urlMatches.map((url, index) => {
              const videoId = extractVideoIdFromUrl(url);
              const titleMatch = toolResult.toolOutput.match(/🎬 \*\*(.*?)\*\*/g);
              const title = titleMatch && titleMatch[index] 
                ? titleMatch[index].replace(/🎬 \*\*(.*?)\*\*/, '$1')
                : `Upload ${index + 1}`;
              
              return {
                video_id: videoId || '',
                title: title,
                url: url,
                thumbnail: videoId ? getYouTubeThumbnail(videoId) : undefined
              };
            });
          }
        }
      } else {
        parsedData = toolResult.toolOutput;
      }
      
      // Handle array of uploads
      if (Array.isArray(parsedData)) {
        uploads = parsedData;
      } else if (parsedData && parsedData.uploads) {
        uploads = parsedData.uploads;
      }
    } catch (e) {
      console.error('Failed to parse YouTube upload history:', e);
    }
  }

  if (!uploads.length && !message) {
    return (
      <Card className="overflow-hidden border border-border shadow-sm">
        <CardHeader className="pb-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 bg-white rounded-lg shadow-md p-1.5">
              <img 
                src="/platforms/youtube.svg" 
                alt="YouTube"
                className="w-full h-full object-contain"
              />
            </div>
            <div>
              <CardTitle className="text-lg font-bold text-foreground">
                Recent YouTube Uploads
              </CardTitle>
              {toolTimestamp && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  {formatTimestamp(toolTimestamp)}
                </p>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-4">
          <div className="text-center py-6">
            <p className="text-muted-foreground">No recent uploads found</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden border border-border shadow-sm">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 bg-white rounded-lg shadow-md p-1.5">
              <img 
                src="/platforms/youtube.svg" 
                alt="YouTube"
                className="w-full h-full object-contain"
              />
            </div>
            <div>
              <CardTitle className="text-lg font-bold text-foreground">
                Recent YouTube Uploads
              </CardTitle>
              {toolTimestamp && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  {formatTimestamp(toolTimestamp)}
                </p>
              )}
            </div>
          </div>
          <Badge variant="secondary">
            {uploads.length} {uploads.length === 1 ? 'Upload' : 'Uploads'}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="p-4">
        {uploads.length > 0 ? (
          <div className="space-y-4">
            {uploads.map((upload, index) => (
              <Card key={upload.video_id || index} className="overflow-hidden bg-muted/30 border border-border">
                <div className="flex items-center gap-4 p-4">
                  {/* Video Thumbnail */}
                  <div className="shrink-0">
                    {upload.thumbnail ? (
                      <img
                        src={upload.thumbnail}
                        alt={upload.title}
                        className="w-24 h-16 rounded-lg object-cover border border-border"
                        onError={(e) => {
                          // Fallback if thumbnail fails to load
                          (e.target as HTMLImageElement).style.display = 'none';
                        }}
                      />
                    ) : (
                      <div className="w-24 h-16 rounded-lg bg-muted flex items-center justify-center border border-border">
                        <img 
                          src="/platforms/youtube.svg" 
                          alt="YouTube"
                          className="w-6 h-6"
                        />
                      </div>
                    )}
                  </div>

                  {/* Video Info */}
                  <div className="flex-1 min-w-0">
                    <h4 className="font-semibold text-foreground text-base mb-1 truncate">
                      {upload.title}
                    </h4>
                    
                    {/* Stats Row */}
                    <div className="flex items-center gap-4 text-sm text-muted-foreground mb-2">
                      {upload.views !== undefined && (
                        <div className="flex items-center gap-1">
                          <Eye className="h-3 w-3" />
                          <span>{formatNumber(upload.views)} views</span>
                        </div>
                      )}
                      
                      {upload.likes !== undefined && (
                        <div className="flex items-center gap-1">
                          <ThumbsUp className="h-3 w-3" />
                          <span>{formatNumber(upload.likes)}</span>
                        </div>
                      )}
                      
                      {upload.comments !== undefined && (
                        <div className="flex items-center gap-1">
                          <MessageCircle className="h-3 w-3" />
                          <span>{formatNumber(upload.comments)}</span>
                        </div>
                      )}
                      
                      {upload.upload_date && (
                        <div className="flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          <span>{new Date(upload.upload_date).toLocaleDateString()}</span>
                        </div>
                      )}
                    </div>

                    {/* Channel info */}
                    {upload.channel_name && (
                      <p className="text-xs text-muted-foreground">
                        Uploaded to: {upload.channel_name}
                      </p>
                    )}
                  </div>

                  {/* Action Button */}
                  <div className="shrink-0">
                    <Button
                      variant="default"
                      size="sm"
                      onClick={() => window.open(upload.url, '_blank')}
                      className="flex items-center gap-2"
                    >
                      <ExternalLink className="h-4 w-4" />
                      View Video
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <div className="text-center py-6">
            <p className="text-muted-foreground mb-2">No recent uploads found</p>
            <p className="text-xs text-muted-foreground">Upload some videos to see them here!</p>
          </div>
        )}

        {/* Show raw message if available and no structured data */}
        {message && uploads.length === 0 && (
          <div className="bg-muted/50 text-foreground border border-border p-3 rounded-lg">
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <div dangerouslySetInnerHTML={{ __html: message.replace(/\\n/g, '<br />') }} />
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}