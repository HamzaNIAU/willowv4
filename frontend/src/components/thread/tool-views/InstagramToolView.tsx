'use client'

import React from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { LoadingState } from './shared/LoadingState';
import { ToolViewProps } from './types';
import { extractToolData, formatTimestamp } from './utils';
import { CheckCircle, ExternalLink, Image as ImageIcon, Users, Video } from 'lucide-react';
import { useAgentSelection } from '@/lib/stores/agent-selection-store';
import { useRealtimeInstagramAccounts } from '@/hooks/use-realtime-social-accounts';

type IGAccount = {
  id: string;
  name: string;
  username?: string;
  profile_picture?: string;
  follower_count?: number;
  post_count?: number;
};

export function InstagramToolView({
  name = 'instagram-accounts',
  assistantContent,
  toolContent,
  assistantTimestamp,
  toolTimestamp,
  isSuccess = true,
  isStreaming = false,
}: ToolViewProps) {
  const { toolResult } = extractToolData(toolContent);
  const { selectedAgentId } = useAgentSelection();
  const { enabledAccounts: rtEnabled, refreshCount: rtRefresh } = useRealtimeInstagramAccounts(selectedAgentId || 'suna-default');

  if (isStreaming || (!toolResult?.toolOutput && !toolContent)) {
    const loadingTitle = name?.includes('create_story')
      ? 'Creating Instagram story...'
      : name?.includes('create_post')
      ? 'Publishing Instagram post...'
      : 'Loading Instagram data...';
    return <LoadingState title={loadingTitle} />;
  }

  let accounts: IGAccount[] = [];
  let posts: any[] = [];
  let message = '';
  let authUrl = '';
  let output: any = null;

  try {
    const raw = toolContent || toolResult?.toolOutput;
    if (typeof raw === 'string') {
      try {
        const parsed = JSON.parse(raw);
        output = parsed?.tool_execution?.result?.output ?? parsed;
      } catch {
        output = raw;
      }
    } else if (typeof raw === 'object' && raw) {
      const obj: any = raw;
      if ('tool_execution' in obj) output = (obj as any).tool_execution?.result?.output;
      else if ('output' in obj) output = (obj as any).output;
      else output = obj;
    }

    if (typeof output === 'string') {
      try { output = JSON.parse(output); } catch {}
    }

    if (output) {
      if (Array.isArray(output)) accounts = output as IGAccount[];
      else {
        if (output.accounts) accounts = output.accounts;
        if (output.posts) posts = output.posts;
        if (output.message) message = output.message;
        if (output.auth_url) authUrl = output.auth_url;
      }
    }
  } catch (e) {
    console.error('InstagramToolView parse error:', e);
  }

  // Prefer real-time enabled accounts for the selected agent
  const realtimeAccounts: IGAccount[] = rtEnabled.map((a: any) => ({
    id: a.account_id,
    name: a.account_name,
    username: a.username,
    profile_picture: a.profile_picture,
    follower_count: a.subscriber_count,
    post_count: a.video_count,
  }));
  const effectiveAccounts = realtimeAccounts.length > 0 ? realtimeAccounts : accounts;

  if (posts.length > 0) {
    return (
      <Card className="overflow-hidden border-border shadow-lg">
        <CardHeader className="pb-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 bg-white rounded-lg shadow-md p-1.5">
              <img src="/platforms/instagram.png" alt="Instagram" className="w-full h-full object-contain" />
            </div>
            <div>
              <CardTitle className="text-lg font-bold">Recent Instagram Posts</CardTitle>
              {toolTimestamp && <p className="text-xs text-muted-foreground">{formatTimestamp(toolTimestamp)}</p>}
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-4">
          <ScrollArea className="max-h-[560px]">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {posts.map((p, i) => (
                <Card key={i} className="overflow-hidden border bg-card">
                  {p.image_url && <img src={p.image_url} alt="" className="w-full h-44 object-cover" />}
                  <CardContent className="p-3">
                    <h4 className="text-sm font-medium line-clamp-1">{p.caption || 'Post'}</h4>
                    <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1"><ImageIcon className="h-3 w-3" /> {p.media_type || 'image'}</span>
                      {p.video && <span className="flex items-center gap-1"><Video className="h-3 w-3" /> video</span>}
                    </div>
                    {p.permalink && (
                      <div className="mt-3">
                        <Button variant="secondary" size="sm" onClick={() => window.open(p.permalink, '_blank')}>
                          <ExternalLink className="h-4 w-4 mr-1" /> View
                        </Button>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    );
  }

  // Accounts list
  return (
    <Card className="overflow-hidden border-zinc-200 dark:border-zinc-700 shadow-lg">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 bg-white rounded-lg shadow-md p-1.5">
              <img src="/platforms/instagram.png" alt="Instagram" className="w-full h-full object-contain" />
            </div>
            <div>
              <CardTitle className="text-lg font-bold">Instagram Accounts</CardTitle>
              {toolTimestamp && <p className="text-xs text-muted-foreground mt-0.5">{formatTimestamp(toolTimestamp)}</p>}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isSuccess && effectiveAccounts.length > 0 && (
              <Badge className="bg-green-500 text-white border-0 hover:bg-green-600">
                <CheckCircle className="h-3 w-3 mr-1" /> Connected
              </Badge>
            )}
            <Badge variant="secondary">{effectiveAccounts.length} {effectiveAccounts.length === 1 ? 'Account' : 'Accounts'}</Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-4">
        {effectiveAccounts.length === 0 ? (
          <LoadingState title={message || 'No Instagram accounts connected'} />
        ) : (
          <ScrollArea className="max-h-[500px]">
            <div className="space-y-4">
              {effectiveAccounts.map((acc) => (
                <Card key={acc.id} className="overflow-hidden bg-card border border-border">
                  <div className="flex items-stretch">
                    <div className="flex items-center gap-4 p-4 flex-1">
                      <div className="shrink-0">
                        {acc.profile_picture ? (
                          <img src={acc.profile_picture} alt="" className="w-16 h-16 rounded-full object-cover" />
                        ) : (
                          <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center">
                            <img src="/platforms/instagram.png" alt="Instagram" className="h-8 w-8 opacity-60" />
                          </div>
                        )}
                      </div>
                      <div className="flex-1">
                        <h4 className="font-semibold">{acc.name}</h4>
                        {acc.username && <p className="text-sm text-muted-foreground">@{acc.username}</p>}
                        <div className="flex items-center gap-4 mt-3">
                          <span className="flex items-center gap-1 text-sm"><Users className="h-4 w-4" /> {acc.follower_count ?? 0} followers</span>
                          <span className="text-sm">{acc.post_count ?? 0} posts</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex flex-col justify-center gap-2 p-4 bg-transparent">
                      {acc.username && (
                        <Button variant="secondary" size="sm" onClick={() => window.open(`https://instagram.com/${acc.username}`, '_blank')}>
                          <ExternalLink className="h-4 w-4 mr-1" /> View Profile
                        </Button>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}
