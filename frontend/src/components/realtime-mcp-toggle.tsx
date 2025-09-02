'use client';

import React from 'react';
import { Switch } from '@/components/ui/switch';
import { Youtube } from 'lucide-react';
import { useRealtimeYouTubeAccounts, toggleYouTubeAccountRealtime } from '@/hooks/use-realtime-youtube-accounts';
import { toast } from 'sonner';

interface RealtimeMCPToggleProps {
  agentId?: string;
}

export function RealtimeMCPToggle({ agentId }: RealtimeMCPToggleProps) {
  const { accounts, enabledAccounts, loading, error, refreshCount } = useRealtimeYouTubeAccounts(agentId);
  
  const handleToggle = async (accountId: string, currentEnabled: boolean) => {
    const newEnabled = !currentEnabled;
    
    try {
      console.log('🔴 Real-time toggle triggered:', { accountId, newEnabled });
      
      // REAL-TIME: Direct database update (no cache invalidation complexity)
      await toggleYouTubeAccountRealtime(agentId!, accountId, newEnabled);
      
      // Success message
      toast.success(`${newEnabled ? 'Enabled' : 'Disabled'} successfully`);
      
      // Real-time subscriptions automatically update UI - no manual state management!
      
    } catch (error) {
      console.error('❌ Real-time toggle failed:', error);
      toast.error('Failed to update account');
    }
  };
  
  if (!agentId) {
    return (
      <div className="p-3 text-sm text-muted-foreground">
        No agent selected
      </div>
    );
  }
  
  if (loading) {
    return (
      <div className="p-3 text-sm text-muted-foreground">
        🔴 Loading real-time accounts...
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="p-3 text-sm text-red-500">
        ❌ Real-time error: {error}
      </div>
    );
  }
  
  if (accounts.length === 0) {
    return (
      <div className="p-3 text-sm text-muted-foreground">
        📺 No YouTube accounts connected.
        <br />
        <span className="text-xs opacity-70">Connect accounts in Social Media settings.</span>
      </div>
    );
  }
  
  return (
    <div className="space-y-2">
      <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground flex items-center gap-1.5">
        <img 
          src="/platforms/youtube.svg" 
          alt="YouTube"
          className="h-3 w-3"
        />
        YouTube ({refreshCount > 0 && `Live #${refreshCount}`})
      </div>
      
      {accounts.map(account => (
        <div
          key={account.account_id}
          className="flex items-center justify-between rounded-md px-3 py-2 hover:bg-accent"
        >
          <div className="flex items-center gap-2">
            {account.profile_picture ? (
              <>
                <img
                  src={account.profile_picture}
                  alt={account.account_name}
                  className="h-5 w-5 rounded-full object-cover border border-border/50"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                    (e.target as HTMLImageElement).nextElementSibling?.classList.remove('hidden');
                  }}
                />
                <img 
                  src="/platforms/youtube.svg" 
                  alt="YouTube"
                  className="h-5 w-5 hidden"
                />
              </>
            ) : (
              <img 
                src="/platforms/youtube.svg" 
                alt="YouTube"
                className="h-5 w-5"
              />
            )}
            <div>
              <span className="text-sm font-medium">{account.account_name}</span>
              {account.username && (
                <div className="text-xs text-muted-foreground">@{account.username}</div>
              )}
              <div className="text-xs text-blue-600">
                🔴 Real-time • {account.subscriber_count} subscribers
              </div>
            </div>
          </div>
          
          <Switch
            checked={account.enabled}
            onCheckedChange={() => handleToggle(account.account_id, account.enabled)}
            className="scale-90"
          />
        </div>
      ))}
      
      <div className="px-3 pt-2 text-xs text-green-600">
        ✅ {enabledAccounts.length} enabled • Real-time updates active
      </div>
    </div>
  );
}