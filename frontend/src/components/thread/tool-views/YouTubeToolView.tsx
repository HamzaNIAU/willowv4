'use client'

import React from 'react';
import {
  Youtube,
  Users,
  Eye,
  Video,
  CheckCircle,
  Copy,
  ExternalLink,
  TrendingUp,
  Clock,
  PlayCircle
} from 'lucide-react';
import { ToolViewProps } from './types';
import { formatTimestamp, getToolTitle, extractToolData } from './utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from "@/components/ui/scroll-area";
import { LoadingState } from './shared/LoadingState';
import { toast } from 'sonner';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { YouTubeUploadResultView } from './YouTubeUploadResultView';
import { YouTubeUploadProgressView } from './YouTubeUploadProgressView';
import { useAgentSelection } from '@/lib/stores/agent-selection-store';
import { useRealtimeYouTubeAccounts } from '@/hooks/use-realtime-youtube-accounts';

interface YouTubeChannel {
  id: string;
  name: string;
  username?: string;
  profile_picture?: string;
  subscriber_count?: number;
  view_count?: number;
  video_count?: number;
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

function formatLargeNumber(num: number | undefined): string {
  if (!num) return '0';
  return num.toLocaleString();
}

export function YouTubeToolView({
  name = 'youtube-channels',
  assistantContent,
  toolContent,
  assistantTimestamp,
  toolTimestamp,
  isSuccess = true,
  isStreaming = false,
}: ToolViewProps) {
  const [copiedId, setCopiedId] = React.useState<string | null>(null);
  const [liveRefresh, setLiveRefresh] = React.useState(0);
  const { selectedAgentId } = useAgentSelection();
  const { enabledAccounts: rtEnabled, refreshCount: rtRefresh } = useRealtimeYouTubeAccounts(selectedAgentId || 'suna-default');
  
  // Add real-time refresh capability
  React.useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'youtube_toggle_changed') {
        console.log('🔄 YouTube toggle changed - triggering live refresh');
        setLiveRefresh(prev => prev + 1);
      }
    };
    
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);
  
  // Trigger live refresh when component receives new content
  React.useEffect(() => {
    if (toolContent) {
      setLiveRefresh(prev => prev + 1);
    }
  }, [toolContent]);

  const handleCopyChannelId = (channelId: string) => {
    navigator.clipboard.writeText(channelId);
    setCopiedId(channelId);
    toast.success('Channel ID copied to clipboard');
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Extract the tool data
  const { toolResult } = extractToolData(toolContent);
  
  if (isStreaming || (!toolResult?.toolOutput && !toolContent)) {
    // Show appropriate loading message based on tool name
    const loadingTitle = name?.includes('upload') ? "Processing video upload..." : 
                        name?.includes('authenticate') ? "Connecting to YouTube..." :
                        "Loading YouTube data...";
    return <LoadingState title={loadingTitle} />;
  }

  // Parse the output
  let channels: YouTubeChannel[] = [];
  let message = '';
  let actionNeeded = '';
  let authUrl = '';
  let buttonText = '';
  let outputToParse: any = null;
  let uploadResult: any = null;
  
  try {
    // First check if toolContent has the structured tool_execution format
    
    if (toolContent) {
      // Handle structured tool_execution format from backend
      if (typeof toolContent === 'object' && toolContent !== null) {
        const toolContentObj = toolContent as any;
        if ('tool_execution' in toolContentObj) {
          const toolExecution = toolContentObj.tool_execution;
          if (toolExecution?.result?.output) {
            outputToParse = toolExecution.result.output;
          }
        }
      } 
      // Handle string that might be JSON with tool_execution
      else if (typeof toolContent === 'string') {
        try {
          const parsed = JSON.parse(toolContent);
          if (parsed?.tool_execution?.result?.output) {
            outputToParse = parsed.tool_execution.result.output;
          } else {
            outputToParse = parsed;
          }
        } catch {
          outputToParse = toolContent;
        }
      }
      // Handle other object formats
      else if (typeof toolContent === 'object' && toolContent !== null) {
        const obj = toolContent as any;
        // Check if it's wrapped in content field
        if ('content' in obj) {
          // Content might be a string with tool_execution JSON
          if (typeof obj.content === 'string') {
            try {
              const parsed = JSON.parse(obj.content);
              if (parsed?.tool_execution?.result?.output) {
                outputToParse = parsed.tool_execution.result.output;
              } else {
                outputToParse = parsed;
              }
            } catch {
              outputToParse = obj.content;
            }
          } else {
            outputToParse = obj.content;
          }
        } else if ('output' in obj) {
          outputToParse = obj.output;
        } else {
          outputToParse = obj;
        }
      }
    }
    
    // Fallback to toolResult if available
    if (!outputToParse && toolResult?.toolOutput) {
      outputToParse = toolResult.toolOutput;
    }
    
    // Now parse the output
    if (outputToParse) {
      let parsedData: any;
      
      // If it's a string, try to parse as JSON
      if (typeof outputToParse === 'string') {
        try {
          parsedData = JSON.parse(outputToParse);
        } catch (jsonError) {
          // If JSON parsing fails, check if it's a Python ToolResult string
          const toolResultMatch = outputToParse.match(/ToolResult\(success=(\w+),\s*output="(.*)"\)/);
          if (toolResultMatch) {
            const isSuccess = toolResultMatch[1] === 'True';
            const outputStr = toolResultMatch[2];
            if (isSuccess && outputStr) {
              try {
                // The output might have escaped quotes, try to parse it
                const unescaped = outputStr.replace(/\\"/g, '"').replace(/\\n/g, '\n');
                parsedData = JSON.parse(unescaped);
              } catch {
                console.error('Failed to parse ToolResult output:', outputStr);
              }
            }
          }
        }
      } else {
        parsedData = outputToParse;
      }
      
      // Extract channels and message from parsed data
      if (parsedData) {
        // Check if this is an upload result (completed)
        if (parsedData.upload_complete && parsedData.video_details) {
          uploadResult = parsedData;
          message = parsedData.message || '';
        }
        // Check if this is an upload initiation (show progress)
        else if (parsedData.upload_id && parsedData.status && !parsedData.upload_complete) {
          // This is an upload in progress - we need to show the progress view
          uploadResult = {
            upload_started: true,
            upload_id: parsedData.upload_id,
            status: parsedData.status,
            channel_name: parsedData.channel_name,
            message: parsedData.message || '',
            title: parsedData.title || 'Untitled Video'
          };
        } else if (parsedData.channel && !parsedData.channels) {
          // Single channel format
          channels = [parsedData.channel];
          message = parsedData.message || `Analytics for ${parsedData.channel.name}`;
        } else if (parsedData.channels !== undefined) {
          // Multiple channels format
          channels = parsedData.channels || [];
          message = parsedData.message || '';
          actionNeeded = parsedData.action_needed || '';
          authUrl = parsedData.auth_url || '';
          buttonText = parsedData.button_text || '';
        } else if (parsedData.existing_channels !== undefined) {
          // Authentication response format with existing channels
          channels = parsedData.existing_channels || [];
          message = parsedData.message || '';
          authUrl = parsedData.auth_url || '';
          buttonText = parsedData.button_text || '';
          // Don't show action_needed for existing channels
        } else if (Array.isArray(parsedData)) {
          // Direct array of channels
          channels = parsedData;
        } else if (parsedData.id && parsedData.name) {
          // Single channel object directly
          channels = [parsedData];
        }
      }
    }
  } catch (e) {
    console.error('Failed to parse YouTube channels data:', e);
    console.error('Tool content:', toolContent);
    console.error('Tool result:', toolResult);
    console.error('Parsed channels:', channels);
    console.error('Output to parse:', outputToParse);
    channels = [];
  }

  // Prefer realtime enabled channels for the selected agent
  const realtimeChannels: YouTubeChannel[] = rtEnabled.map((a: any) => ({
    id: a.account_id,
    name: a.account_name,
    username: a.username,
    profile_picture: a.profile_picture,
    subscriber_count: a.subscriber_count,
    view_count: a.view_count,
    video_count: a.video_count,
  }));
  const effectiveChannels = realtimeChannels.length > 0 ? realtimeChannels : channels;
  const hasChannels = effectiveChannels.length > 0;

  // Debug logging for development
  if (toolContent) {
    console.log('[YouTubeToolView] Debug info:', {
      hasChannels,
      channelsCount: channels.length,
      channels,
      uploadResult: uploadResult ? 'present' : 'absent',
      hasVideoDetails: uploadResult?.video_details ? 'yes' : 'no',
      message: message?.substring(0, 100) + (message?.length > 100 ? '...' : ''),
      authUrl: authUrl ? 'present' : 'absent',
      buttonText,
      toolContentType: typeof toolContent,
      hasToolExecution: typeof toolContent === 'object' && toolContent !== null && 'tool_execution' in (toolContent as any)
    });
  }

  // Check if this is an upload - render appropriate upload view
  if (uploadResult) {
    // If we have video_details, show the completed result
    if (uploadResult.video_details) {
      return (
        <YouTubeUploadResultView
          video_details={uploadResult.video_details}
          message={message}
          timestamp={toolTimestamp}
        />
      );
    }
    // If we have upload_started flag, show the progress view
    else if (uploadResult.upload_started && uploadResult.upload_id) {
      return (
        <YouTubeUploadProgressView
          upload_id={uploadResult.upload_id}
          title={uploadResult.title}
          channel_name={uploadResult.channel_name}
          onComplete={(videoDetails) => {
            // When upload completes, we could trigger a refresh or update state
            console.log('Upload completed:', videoDetails);
          }}
        />
      );
    }
  }

  return (
    <Card className="overflow-hidden border-zinc-200 dark:border-zinc-700 shadow-lg">
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
              <CardTitle className="text-lg font-bold flex items-center gap-2">
                YouTube Channels
              </CardTitle>
              {toolTimestamp && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  {formatTimestamp(toolTimestamp)}
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isSuccess && hasChannels && (
              <Badge className="bg-green-500 text-white border-0 hover:bg-green-600">
                <CheckCircle className="h-3 w-3 mr-1" />
                Connected
              </Badge>
            )}
            <Badge variant="secondary">
              {effectiveChannels.length} {effectiveChannels.length === 1 ? 'Channel' : 'Channels'}
            </Badge>
          </div>
        </div>
      </CardHeader>

      {/* Content */}
      <CardContent className="p-4">
        {!hasChannels ? (
          <div className="py-6">
            {message ? (
              // Display the backend's helpful message
              <div className="space-y-4">
                <div className="flex justify-center mb-4">
                  <img 
                    src="/platforms/youtube.svg" 
                    alt="YouTube"
                    className="h-12 w-12 opacity-40"
                  />
                </div>
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <div dangerouslySetInnerHTML={{ __html: message.replace(/\n/g, '<br />') }} />
                </div>
                {actionNeeded === 'connect_channels' && (
                  <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-950/30 rounded-lg border border-blue-200 dark:border-blue-800">
                    <p className="text-sm text-blue-700 dark:text-blue-300">
                      💡 Tip: You can also connect channels from Settings → Social Media
                    </p>
                  </div>
                )}
                {actionNeeded === 'enable_channels' && (
                  <div className="mt-4 p-3 bg-yellow-50 dark:bg-yellow-950/30 rounded-lg border border-yellow-200 dark:border-yellow-800">
                    <p className="text-sm text-yellow-700 dark:text-yellow-300">
                      ⚡ Quick fix: Click the MCP button below to enable your channels
                    </p>
                  </div>
                )}
              </div>
            ) : (
              // Enhanced error state with live recovery
              <div className="text-center">
                <img 
                  src="/platforms/youtube.svg" 
                  alt="YouTube"
                  className="h-12 w-12 mx-auto opacity-40 mb-3"
                />
                <p className="text-sm text-zinc-600 dark:text-zinc-400 font-medium">
                  No YouTube channels enabled
                </p>
                <div className="text-xs text-zinc-500 dark:text-zinc-500 mt-2 space-y-1">
                  <p>Click the MCP connections button (⚙️) to enable channels</p>
                  <p>Or use `youtube_authenticate` to connect new channels</p>
                </div>
                
                {/* Live retry indicator */}
                <div className="mt-3 flex items-center justify-center gap-2 text-xs text-blue-600">
                  <div className="w-1 h-1 bg-blue-600 rounded-full animate-pulse"></div>
                  <span>Checking for channel updates... (refresh #{liveRefresh})</span>
                </div>
              </div>
            )}
          </div>
        ) : (
          <ScrollArea className="max-h-[500px]">
            <div className="space-y-4">
              {effectiveChannels.map((channel) => (
                <Card 
                  key={channel.id} 
                  className="overflow-hidden bg-card border border-border hover:bg-accent/5 transition-all duration-200"
                >
                  <div className="flex items-stretch">
                    {/* Left side - Avatar and main info */}
                    <div className="flex items-center gap-4 p-4 flex-1">
                      {/* Channel Avatar */}
                      <div className="shrink-0 relative">
                        {channel.profile_picture ? (
                          <div className="relative group">
                            <img
                              src={channel.profile_picture}
                              alt={channel.name}
                              className="w-20 h-20 rounded-full border-3 border-white dark:border-zinc-700 shadow-lg object-cover"
                              onError={(e) => {
                                const target = e.target as HTMLImageElement;
                                target.onerror = null;
                                target.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODAiIGhlaWdodD0iODAiIHZpZXdCb3g9IjAgMCA4MCA4MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjgwIiBoZWlnaHQ9IjgwIiByeD0iNDAiIGZpbGw9IiNGRjAwMDAiLz4KPHBhdGggZD0iTTU1IDQwTDMzIDI4VjUyTDU1IDQwWiIgZmlsbD0id2hpdGUiLz4KPC9zdmc+';
                              }}
                            />
                            <div className="absolute -bottom-1 -right-1 w-7 h-7 bg-white dark:bg-zinc-900 rounded-full flex items-center justify-center shadow-md border border-zinc-200 dark:border-zinc-700 p-1">
                              <img 
                                src="/platforms/youtube.svg" 
                                alt="YouTube"
                                className="w-full h-full object-contain"
                              />
                            </div>
                          </div>
                        ) : (
                          <div className="w-20 h-20 rounded-full bg-muted flex items-center justify-center">
                            <img 
                              src="/platforms/youtube.svg" 
                              alt="YouTube"
                              className="h-10 w-10 opacity-60"
                            />
                          </div>
                        )}
                      </div>

                      {/* Channel Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between">
                          <div>
                            <h4 className="text-lg font-semibold text-foreground">
                              {channel.name}
                            </h4>
                            {channel.username && (
                              <p className="text-sm text-muted-foreground flex items-center gap-1">
                                <span className="text-muted-foreground">@</span>{channel.username}
                              </p>
                            )}
                            
                            {/* Stats Row */}
                            <div className="flex flex-wrap items-center gap-4 mt-3">
                              <div className="flex items-center gap-1.5">
                                <Users className="h-4 w-4 text-muted-foreground" />
                                <span className="text-sm font-medium text-foreground">
                                  {formatNumber(channel.subscriber_count)}
                                </span>
                                <span className="text-xs text-muted-foreground">subscribers</span>
                              </div>

                              <div className="flex items-center gap-1.5">
                                <Eye className="h-4 w-4 text-muted-foreground" />
                                <span className="text-sm font-medium text-foreground">
                                  {formatNumber(channel.view_count)}
                                </span>
                                <span className="text-xs text-muted-foreground">views</span>
                              </div>

                              <div className="flex items-center gap-1.5">
                                <PlayCircle className="h-4 w-4 text-muted-foreground" />
                                <span className="text-sm font-medium text-foreground">
                                  {channel.video_count}
                                </span>
                                <span className="text-xs text-muted-foreground">videos</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Right side - Action buttons */}
                    <div className="flex flex-col justify-center gap-2 p-4 bg-muted/30">
                      <Button
                        variant="default"
                        size="sm"
                        className="flex items-center gap-2"
                        onClick={() => window.open(`https://youtube.com/channel/${channel.id}`, '_blank')}
                      >
                        <ExternalLink className="h-4 w-4" />
                        View Channel
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </ScrollArea>
        )}

        {/* OAuth Button if auth URL is present */}
        {authUrl && (
          <div className="mt-4">
            <Card className="border bg-muted/30 border-border">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg overflow-hidden bg-white dark:bg-zinc-800 flex items-center justify-center p-2">
                      <img 
                        src="/platforms/youtube.svg" 
                        alt="YouTube"
                        className="w-full h-full object-contain"
                      />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground">
                        Connect YouTube Account
                      </h3>
                      <p className="text-sm text-muted-foreground">
                        Click to authorize access to your YouTube channel
                      </p>
                    </div>
                  </div>
                  <Button
                    onClick={() => {
                      // Open OAuth in popup like Social Media page
                      const popup = window.open(
                        authUrl,
                        'youtube-auth',
                        'width=600,height=700,resizable=yes,scrollbars=yes'
                      );
                      
                      // Listen for auth completion
                      const handleMessage = (event: MessageEvent) => {
                        if (event.data?.type === 'youtube-auth-success') {
                          popup?.close();
                          
                          // Show success toast with channel info
                          const channel = event.data.channel;
                          if (channel && channel.name) {
                            toast.success(
                              <div className="flex items-center gap-3">
                                {channel.profile_picture && (
                                  <img 
                                    src={channel.profile_picture} 
                                    alt="" 
                                    className="w-8 h-8 rounded-full"
                                  />
                                )}
                                <div>
                                  <div className="font-semibold">Connected Successfully!</div>
                                  <div className="text-sm opacity-90">
                                    {channel.name} {channel.username && `• @${channel.username}`}
                                  </div>
                                </div>
                              </div>
                            );
                          } else {
                            toast.success('YouTube account connected successfully!');
                          }
                          
                          window.removeEventListener('message', handleMessage);
                          window.removeEventListener('storage', handleStorage);
                          
                          // Refresh the thread to show updated channels
                          // This is better than full page reload
                          setTimeout(() => {
                            // Trigger a refresh of the conversation
                            window.dispatchEvent(new CustomEvent('youtube-connected'));
                          }, 1000);
                        } else if (event.data?.type === 'youtube-auth-error') {
                          popup?.close();
                          toast.error(`Failed to connect: ${event.data.error || 'Unknown error'}`);
                          window.removeEventListener('message', handleMessage);
                          window.removeEventListener('storage', handleStorage);
                        }
                      };
                      
                      // Fallback: Listen for storage events in case postMessage fails
                      const handleStorage = (event: StorageEvent) => {
                        if (event.key === 'youtube-auth-result' && event.newValue) {
                          try {
                            const result = JSON.parse(event.newValue);
                            if (result.type === 'youtube-auth-success') {
                              handleMessage({ data: result } as MessageEvent);
                              // Clean up the storage
                              localStorage.removeItem('youtube-auth-result');
                            }
                          } catch (e) {
                            console.error('Failed to parse storage event:', e);
                          }
                        }
                      };
                      
                      window.addEventListener('message', handleMessage);
                      window.addEventListener('storage', handleStorage);
                    }}
                    className="bg-primary hover:bg-primary/90 text-primary-foreground"
                  >
                    <img 
                      src="/platforms/youtube.svg" 
                      alt=""
                      className="w-4 h-4 mr-2 brightness-0 invert"
                    />
                    {buttonText || 'Connect YouTube'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Summary Message - Hidden for cleaner UI */}
        {false && message && !authUrl && (
          <div className="mt-4 p-3 bg-zinc-50 dark:bg-zinc-900/50 rounded-lg border border-zinc-200 dark:border-zinc-700">
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              {message}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
