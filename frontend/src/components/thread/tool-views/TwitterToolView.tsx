'use client'

import React from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { LoadingState } from './shared/LoadingState';
import { ToolViewProps } from './types';
import { extractToolData, formatTimestamp } from './utils';
import { CheckCircle, ExternalLink, Users, Check } from 'lucide-react';
import { useAgentSelection } from '@/lib/stores/agent-selection-store';
import { useRealtimeTwitterAccounts } from '@/hooks/use-realtime-social-accounts';

type TwAccount = {
  id: string;
  name: string;
  username?: string;
  profile_image_url?: string;
  followers_count?: number;
  verified?: boolean;
};

export function TwitterToolView({
  name = 'twitter-accounts',
  assistantContent,
  toolContent,
  assistantTimestamp,
  toolTimestamp,
  isSuccess = true,
  isStreaming = false,
}: ToolViewProps) {
  const { toolResult } = extractToolData(toolContent);
  const { selectedAgentId } = useAgentSelection();
  const { enabledAccounts: rtEnabled } = useRealtimeTwitterAccounts(selectedAgentId || 'suna-default');
  if (isStreaming || (!toolResult?.toolOutput && !toolContent)) {
    const loadingTitle = name?.includes('create_tweet') ? 'Posting tweet...' : 'Loading Twitter data...';
    return <LoadingState title={loadingTitle} />;
  }

  let accounts: TwAccount[] = [];
  let message = '';
  let output: any = null;
  try {
    const raw = toolContent || toolResult?.toolOutput;
    if (typeof raw === 'string') {
      try { const parsed = JSON.parse(raw); output = parsed?.tool_execution?.result?.output ?? parsed; } catch { output = raw; }
    } else if (typeof raw === 'object' && raw) {
      const obj: any = raw;
      if ('tool_execution' in obj) output = obj.tool_execution?.result?.output; else if ('output' in obj) output = obj.output; else output = obj;
    }
    if (typeof output === 'string') { try { output = JSON.parse(output); } catch {} }
    if (output) {
      if (output.accounts) accounts = output.accounts; else if (Array.isArray(output)) accounts = output;
      if (output.message) message = output.message;
    }
  } catch (e) { console.error('TwitterToolView parse error:', e); }

  // Prefer real-time enabled accounts
  const realtimeAccounts: TwAccount[] = rtEnabled.map((a: any) => ({
    id: a.account_id,
    name: a.account_name,
    username: a.username,
    profile_image_url: a.profile_picture,
    followers_count: a.subscriber_count,
    verified: undefined,
  }));
  const effectiveAccounts = realtimeAccounts.length > 0 ? realtimeAccounts : accounts;

  return (
    <Card className="overflow-hidden border-zinc-200 dark:border-zinc-700 shadow-lg">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 bg-white rounded-lg shadow-md p-1.5">
              <img src="/platforms/x.png" alt="X" className="w-full h-full object-contain" />
            </div>
            <div>
              <CardTitle className="text-lg font-bold">X (Twitter) Accounts</CardTitle>
              {toolTimestamp && <p className="text-xs text-muted-foreground mt-0.5">{formatTimestamp(toolTimestamp)}</p>}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isSuccess && effectiveAccounts.length > 0 && (
              <Badge className="bg-green-500 text-white border-0 hover:bg-green-600"><CheckCircle className="h-3 w-3 mr-1" /> Connected</Badge>
            )}
            <Badge variant="secondary">{effectiveAccounts.length} {effectiveAccounts.length === 1 ? 'Account' : 'Accounts'}</Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-4">
        {effectiveAccounts.length === 0 ? (
          <LoadingState title={message || 'No X accounts connected'} />
        ) : (
          <ScrollArea className="max-h-[500px]">
            <div className="space-y-4">
              {effectiveAccounts.map((acc) => (
                <Card key={acc.id} className="overflow-hidden bg-card border border-border">
                  <div className="flex items-stretch">
                    <div className="flex items-center gap-4 p-4 flex-1">
                      <div className="shrink-0">
                        {acc.profile_image_url ? (
                          <img src={acc.profile_image_url} alt="" className="w-16 h-16 rounded-full object-cover" />
                        ) : (
                          <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center">
                            <img src="/platforms/x.png" alt="X" className="h-8 w-8 opacity-60" />
                          </div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h4 className="font-semibold truncate">{acc.name}</h4>
                          {acc.verified && <Badge variant="outline" className="h-5 px-1.5"><Check className="h-3 w-3" /> Verified</Badge>}
                        </div>
                        {acc.username && <p className="text-sm text-muted-foreground">@{acc.username}</p>}
                        <div className="mt-2 text-sm flex items-center gap-3">
                          <span className="flex items-center gap-1"><Users className="h-4 w-4" /> {acc.followers_count ?? 0} followers</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex flex-col justify-center gap-2 p-4 bg-transparent">
                      {acc.username && (
                        <Button variant="secondary" size="sm" onClick={() => window.open(`https://x.com/${acc.username}`, '_blank')}>
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
