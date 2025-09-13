'use client';

/* Generic Real-Time Social Accounts Hook
 * Reads enabled accounts for a given platform from agent_social_accounts
 * and subscribes to live updates using Supabase Realtime.
 */

import { useEffect, useState } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useAuth } from '@/components/AuthProvider';

export type RealtimeSocialAccount = {
  account_id: string;
  account_name: string;
  username?: string;
  profile_picture?: string;
  subscriber_count?: number;
  view_count?: number;
  video_count?: number;
  enabled: boolean;
  platform: string;
  connected_at?: string;
};

export type UseRealtimeSocialAccountsResult = {
  accounts: RealtimeSocialAccount[];
  enabledAccounts: RealtimeSocialAccount[];
  loading: boolean;
  error: string | null;
  refreshCount: number;
};

export function useRealtimeSocialAccounts(
  platform: 'youtube' | 'pinterest' | 'instagram' | 'twitter' | 'linkedin' | 'tiktok',
  agentId?: string,
): UseRealtimeSocialAccountsResult {
  const [accounts, setAccounts] = useState<RealtimeSocialAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshCount, setRefreshCount] = useState(0);
  const { user } = useAuth();

  useEffect(() => {
    if (!agentId || !user) {
      setAccounts([]);
      setLoading(false);
      return;
    }

    const supabase = createClient();

    const fetchInitial = async () => {
      try {
        const { data, error: fetchError } = await supabase
          .from('agent_social_accounts')
          .select('*')
          .eq('agent_id', agentId)
          .eq('user_id', user.id)
          .eq('platform', platform)
          .order('account_name');
        if (fetchError) {
          setError(fetchError.message);
        } else {
          setAccounts((data || []) as RealtimeSocialAccount[]);
          setError(null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch accounts');
      } finally {
        setLoading(false);
      }
    };

    fetchInitial();

    const channelName = `${platform}_accounts_${agentId}`;
    const subscription = supabase
      .channel(channelName)
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'agent_social_accounts',
          filter: `agent_id=eq.${agentId} AND user_id=eq.${user.id} AND platform=eq.${platform}`,
        },
        (payload) => {
          setAccounts((current) => {
            let updated = [...current];
            if (payload.eventType === 'INSERT') {
              updated.push(payload.new as RealtimeSocialAccount);
            } else if (payload.eventType === 'UPDATE') {
              const ix = updated.findIndex((a) => a.account_id === (payload.new as any).account_id);
              if (ix >= 0) updated[ix] = payload.new as RealtimeSocialAccount;
            } else if (payload.eventType === 'DELETE') {
              updated = updated.filter((a) => a.account_id !== (payload.old as any).account_id);
            }
            setRefreshCount((c) => c + 1);
            return updated.sort((a, b) => a.account_name.localeCompare(b.account_name));
          });
        },
      )
      .subscribe();

    return () => {
      subscription.unsubscribe();
    };
  }, [agentId, user, platform]);

  const enabledAccounts = accounts.filter((a) => a.enabled);
  return { accounts, enabledAccounts, loading, error, refreshCount };
}

// Convenience wrappers per platform
export const useRealtimeInstagramAccounts = (agentId?: string) =>
  useRealtimeSocialAccounts('instagram', agentId);

export const useRealtimeTwitterAccounts = (agentId?: string) =>
  useRealtimeSocialAccounts('twitter', agentId);

export const useRealtimeLinkedInAccounts = (agentId?: string) =>
  useRealtimeSocialAccounts('linkedin', agentId);

export const useRealtimeTikTokAccounts = (agentId?: string) =>
  useRealtimeSocialAccounts('tiktok', agentId);

// Toggle helper that persists directly in the unified table
export async function toggleSocialAccountRealtime(
  agentId: string,
  platform: 'youtube' | 'pinterest' | 'instagram' | 'twitter' | 'linkedin' | 'tiktok',
  accountId: string,
  enabled: boolean,
): Promise<void> {
  const supabase = createClient();
  const { error } = await supabase
    .from('agent_social_accounts')
    .update({ enabled, updated_at: new Date().toISOString() })
    .eq('agent_id', agentId)
    .eq('platform', platform)
    .eq('account_id', accountId);
  if (error) throw error;
}
