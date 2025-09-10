'use client'

import React from 'react';
import {
  CheckCircle,
  Copy,
  ExternalLink,
  User,
  Users,
  Eye,
  Pin
} from 'lucide-react';
import { ToolViewProps } from './types';
import { formatTimestamp, getToolTitle, extractToolData } from './utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from "@/components/ui/scroll-area";
import { LoadingState } from './shared/LoadingState';
import { toast } from 'sonner';

interface PinterestAccount {
  id: string;
  name: string;
  username?: string;
  profile_picture?: string;
  subscriber_count?: number;
  view_count?: number;
  video_count?: number;
}

interface PinterestPin {
  pin_id: string;
  pin_url: string;
  title: string;
  description?: string;
  board_id?: string;
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

export function PinterestToolView({
  name = 'pinterest-accounts',
  assistantContent,
  toolContent,
  assistantTimestamp,
  toolTimestamp,
  isSuccess = true,
  isStreaming = false,
}: ToolViewProps) {
  const [copiedId, setCopiedId] = React.useState<string | null>(null);
  const [liveRefresh, setLiveRefresh] = React.useState(0);
  
  // Add real-time refresh capability
  React.useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'pinterest_toggle_changed') {
        console.log('🔄 Pinterest toggle changed - triggering live refresh');
        setLiveRefresh(prev => prev + 1);
      }
    };
    
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);
  
  React.useEffect(() => {
    if (toolContent) {
      setLiveRefresh(prev => prev + 1);
    }
  }, [toolContent]);

  const handleCopyAccountId = (accountId: string) => {
    navigator.clipboard.writeText(accountId);
    setCopiedId(accountId);
    toast.success('Pinterest account ID copied to clipboard');
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Extract the tool data
  const { toolResult } = extractToolData(toolContent);
  
  if (isStreaming || (!toolResult?.toolOutput && !toolContent)) {
    const loadingTitle = name?.includes('create_pin') ? "Creating Pinterest pin..." : 
                        name?.includes('authenticate') ? "Connecting to Pinterest..." :
                        name?.includes('boards') ? "Loading Pinterest boards..." :
                        "Loading Pinterest data...";
    return <LoadingState title={loadingTitle} />;
  }

  // Parse the output
  let accounts: PinterestAccount[] = [];
  let boards: any[] = [];
  let pinResult: PinterestPin | null = null;
  let message = '';
  let authUrl = '';
  let buttonText = '';
  let outputToParse: any = null;
  
  try {
    if (toolContent) {
      if (typeof toolContent === 'object' && toolContent !== null) {
        const toolContentObj = toolContent as any;
        if ('tool_execution' in toolContentObj) {
          outputToParse = toolContentObj.tool_execution.result?.output;
        }
      } else if (typeof toolContent === 'string') {
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
    }
    
    if (!outputToParse && toolResult?.toolOutput) {
      outputToParse = toolResult.toolOutput;
    }
    
    if (outputToParse) {
      let parsedData: any;
      
      if (typeof outputToParse === 'string') {
        try {
          parsedData = JSON.parse(outputToParse);
        } catch {
          // Handle plain text responses
          if (outputToParse.includes('Pinterest')) {
            message = outputToParse;
          }
        }
      } else {
        parsedData = outputToParse;
      }
      
      if (parsedData) {
        // Check if this is a pin creation result
        if (parsedData.pin_created && parsedData.pin_id) {
          pinResult = {
            pin_id: parsedData.pin_id,
            pin_url: parsedData.pin_url,
            title: parsedData.title,
            description: parsedData.description,
            board_id: parsedData.board_id
          };
          message = parsedData.message || '';
        }
        // Check for accounts
        else if (parsedData.accounts !== undefined) {
          accounts = parsedData.accounts || [];
          message = parsedData.message || '';
          authUrl = parsedData.auth_url || '';
          buttonText = parsedData.button_text || '';
        }
        // Check for boards
        else if (parsedData.boards !== undefined) {
          boards = parsedData.boards || [];
          message = parsedData.message || '';
        }
        else if (Array.isArray(parsedData)) {
          accounts = parsedData;
        }
        else if (parsedData.id && parsedData.name) {
          accounts = [parsedData];
        }
      }
    }
  } catch (e) {
    console.error('Failed to parse Pinterest data:', e);
    accounts = [];
    boards = [];
  }

  const hasAccounts = accounts.length > 0;

  // Show pin creation result
  if (pinResult) {
    return (
      <Card className="overflow-hidden border-border shadow-sm">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-10 h-10 bg-white rounded-lg shadow-md p-1.5">
                <img 
                  src="/platforms/pinterest.png" 
                  alt="Pinterest"
                  className="w-full h-full object-contain"
                />
              </div>
              <div>
                <CardTitle className="text-lg font-bold flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-green-500" />
                  Pinterest Pin Created!
                </CardTitle>
                {toolTimestamp && (
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {formatTimestamp(toolTimestamp)}
                  </p>
                )}
              </div>
            </div>
            <Badge className="bg-green-500 text-white border-0 hover:bg-green-600">
              <CheckCircle className="h-3 w-3 mr-1" />
              Live on Pinterest
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="p-4 space-y-4">
          <div>
            <h3 className="text-xl font-bold text-foreground mb-2">
              {pinResult.title}
            </h3>
            {pinResult.description && (
              <p className="text-sm text-muted-foreground mb-4">
                {pinResult.description}
              </p>
            )}
          </div>
          
          <div className="flex gap-3">
            <Button
              onClick={() => window.open(pinResult.pin_url, '_blank')}
              variant="default"
              className="flex-1"
            >
              <ExternalLink className="h-4 w-4 mr-2" />
              View on Pinterest
            </Button>
            
            <Button
              variant="outline"
              onClick={() => {
                navigator.clipboard.writeText(pinResult.pin_url);
                toast.success('Pinterest pin URL copied!');
              }}
            >
              <Copy className="h-4 w-4" />
            </Button>
          </div>
          
          {message && (
            <div className="mt-4 p-3 bg-muted/50 rounded-lg border border-border">
              <div dangerouslySetInnerHTML={{ __html: message.replace(/\\n/g, '<br />') }} />
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  // Show boards list
  if (boards.length > 0) {
    return (
      <Card className="overflow-hidden border-border shadow-lg">
        <CardHeader className="pb-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 bg-white rounded-lg shadow-md p-1.5">
              <img 
                src="/platforms/pinterest.png" 
                alt="Pinterest"
                className="w-full h-full object-contain"
              />
            </div>
            <div>
              <CardTitle className="text-lg font-bold">
                Pinterest Boards
              </CardTitle>
              <p className="text-xs text-muted-foreground">
                {boards.length} board{boards.length !== 1 ? 's' : ''} available
              </p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-4">
          <ScrollArea className="max-h-[400px]">
            <div className="space-y-3">
              {boards.map((board) => (
                <div
                  key={board.id}
                  className="flex items-center justify-between p-3 bg-muted/30 rounded-lg border border-border"
                >
                  <div>
                    <h4 className="font-semibold text-foreground">{board.name}</h4>
                    <p className="text-sm text-muted-foreground">
                      📌 {board.pin_count || 0} pins • {board.privacy || 'PUBLIC'}
                    </p>
                    {board.description && (
                      <p className="text-xs text-muted-foreground mt-1">
                        {board.description}
                      </p>
                    )}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleCopyAccountId(board.id)}
                  >
                    {copiedId === board.id ? (
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                    {copiedId === board.id ? 'Copied!' : 'Copy ID'}
                  </Button>
                </div>
              ))}
            </div>
          </ScrollArea>
          
          {message && (
            <div className="mt-4 p-3 bg-muted/50 rounded-lg">
              <div dangerouslySetInnerHTML={{ __html: message.replace(/\\n/g, '<br />') }} />
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden border-zinc-200 dark:border-zinc-700 shadow-lg">
      {/* Header */}
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Pinterest Logo */}
            <div className="flex items-center justify-center w-10 h-10 bg-white rounded-lg shadow-md p-1.5">
              <img 
                src="/platforms/pinterest.png" 
                alt="Pinterest"
                className="w-full h-full object-contain"
              />
            </div>
            <div>
              <CardTitle className="text-lg font-bold flex items-center gap-2">
                Pinterest Accounts
              </CardTitle>
              {toolTimestamp && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  {formatTimestamp(toolTimestamp)}
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isSuccess && hasAccounts && (
              <Badge className="bg-green-500 text-white border-0 hover:bg-green-600">
                <CheckCircle className="h-3 w-3 mr-1" />
                Connected
              </Badge>
            )}
            <Badge variant="secondary">
              {accounts.length} {accounts.length === 1 ? 'Account' : 'Accounts'}
            </Badge>
          </div>
        </div>
      </CardHeader>

      {/* Content */}
      <CardContent className="p-4">
        {!hasAccounts ? (
          <div className="py-6">
            {message ? (
              <div className="space-y-4">
                <div className="flex justify-center mb-4">
                  <img 
                    src="/platforms/pinterest.png" 
                    alt="Pinterest"
                    className="h-12 w-12 opacity-40"
                  />
                </div>
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <div dangerouslySetInnerHTML={{ __html: message.replace(/\\n/g, '<br />') }} />
                </div>
              </div>
            ) : (
              <div className="text-center">
                <img 
                  src="/platforms/pinterest.png" 
                  alt="Pinterest"
                  className="h-12 w-12 mx-auto opacity-40 mb-3"
                />
                <p className="text-sm text-zinc-600 dark:text-zinc-400 font-medium">
                  No Pinterest accounts enabled
                </p>
                <div className="text-xs text-zinc-500 dark:text-zinc-500 mt-2 space-y-1">
                  <p>Click the MCP connections button (⚙️) to enable accounts</p>
                  <p>Or use `pinterest_authenticate` to connect new accounts</p>
                </div>
                
                <div className="mt-3 flex items-center justify-center gap-2 text-xs text-blue-600">
                  <div className="w-1 h-1 bg-blue-600 rounded-full animate-pulse"></div>
                  <span>Checking for account updates... (refresh #{liveRefresh})</span>
                </div>
              </div>
            )}
          </div>
        ) : (
          <ScrollArea className="max-h-[500px]">
            <div className="space-y-4">
              {accounts.map((account) => (
                <Card 
                  key={account.id} 
                  className="overflow-hidden bg-card border border-border hover:bg-accent/5 transition-all duration-200"
                >
                  <div className="flex items-stretch">
                    <div className="flex items-center gap-4 p-4 flex-1">
                      {/* Account Avatar */}
                      <div className="shrink-0 relative">
                        {account.profile_picture ? (
                          <div className="relative group">
                            <img
                              src={account.profile_picture}
                              alt={account.name}
                              className="w-20 h-20 rounded-full border-3 border-white dark:border-zinc-700 shadow-lg object-cover"
                              onError={(e) => {
                                const target = e.target as HTMLImageElement;
                                target.onerror = null;
                                target.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODAiIGhlaWdodD0iODAiIHZpZXdCb3g9IjAgMCA4MCA4MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjgwIiBoZWlnaHQ9IjgwIiByeD0iNDAiIGZpbGw9IiNFNjAwMjMiLz4KPHBhdGggZD0iTTQwIDIwQzMwIDIwIDIyIDI4IDIyIDM4UzMwIDU2IDQwIDU2UzU4IDQ4IDU4IDM4UzUwIDIwIDQwIDIwWiIgZmlsbD0id2hpdGUiLz4KPC9zdmc+';
                              }}
                            />
                            <div className="absolute -bottom-1 -right-1 w-7 h-7 bg-white dark:bg-zinc-900 rounded-full flex items-center justify-center shadow-md border border-zinc-200 dark:border-zinc-700 p-1">
                              <img 
                                src="/platforms/pinterest.png" 
                                alt="Pinterest"
                                className="w-full h-full object-contain"
                              />
                            </div>
                          </div>
                        ) : (
                          <div className="w-20 h-20 rounded-full bg-muted flex items-center justify-center">
                            <img 
                              src="/platforms/pinterest.png" 
                              alt="Pinterest"
                              className="h-10 w-10 opacity-60"
                            />
                          </div>
                        )}
                      </div>

                      {/* Account Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between">
                          <div>
                            <h4 className="text-lg font-semibold text-foreground">
                              {account.name}
                            </h4>
                            {account.username && (
                              <p className="text-sm text-muted-foreground flex items-center gap-1">
                                <span className="text-muted-foreground">@</span>{account.username}
                              </p>
                            )}
                            
                            {/* Stats Row */}
                            <div className="flex flex-wrap items-center gap-4 mt-3">
                              <div className="flex items-center gap-1.5">
                                <Users className="h-4 w-4 text-muted-foreground" />
                                <span className="text-sm font-medium text-foreground">
                                  {formatNumber(account.subscriber_count)}
                                </span>
                                <span className="text-xs text-muted-foreground">followers</span>
                              </div>

                              <div className="flex items-center gap-1.5">
                                <Pin className="h-4 w-4 text-muted-foreground" />
                                <span className="text-sm font-medium text-foreground">
                                  {formatNumber(account.video_count)}
                                </span>
                                <span className="text-xs text-muted-foreground">pins</span>
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
                        onClick={() => window.open(`https://pinterest.com/${account.username}`, '_blank')}
                      >
                        <ExternalLink className="h-4 w-4" />
                        View Profile
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
                        src="/platforms/pinterest.png" 
                        alt="Pinterest"
                        className="w-full h-full object-contain"
                      />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground">
                        Connect Pinterest Account
                      </h3>
                      <p className="text-sm text-muted-foreground">
                        Click to authorize access to your Pinterest account
                      </p>
                    </div>
                  </div>
                  <Button
                    onClick={() => {
                      const popup = window.open(
                        authUrl,
                        'pinterest-auth',
                        'width=600,height=700,resizable=yes,scrollbars=yes'
                      );
                      
                      const handleMessage = (event: MessageEvent) => {
                        if (event.data?.type === 'pinterest-auth-success') {
                          popup?.close();
                          toast.success('Pinterest account connected successfully!');
                          window.removeEventListener('message', handleMessage);
                          
                          setTimeout(() => {
                            window.dispatchEvent(new CustomEvent('pinterest-connected'));
                          }, 1000);
                        } else if (event.data?.type === 'pinterest-auth-error') {
                          popup?.close();
                          toast.error(`Failed to connect: ${event.data.error || 'Unknown error'}`);
                          window.removeEventListener('message', handleMessage);
                        }
                      };
                      
                      window.addEventListener('message', handleMessage);
                    }}
                    className="bg-primary hover:bg-primary/90 text-primary-foreground"
                  >
                    <img 
                      src="/platforms/pinterest.png" 
                      alt=""
                      className="w-4 h-4 mr-2 brightness-0 invert"
                    />
                    {buttonText || 'Connect Pinterest'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </CardContent>
    </Card>
  );
}