/* Real-Time Pinterest Accounts Hook - Mirrors YouTube pattern */

import { useState, useEffect } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useAuth } from '@/components/AuthProvider';

interface RealtimePinterestAccount {
  account_id: string;
  account_name: string;
  username?: string;
  profile_picture?: string;
  follower_count: number;
  board_count?: number;
  pin_count?: number;
  enabled: boolean;
  platform: string;
  connected_at: string;
}

interface UseRealtimePinterestAccountsResult {
  accounts: RealtimePinterestAccount[];
  enabledAccounts: RealtimePinterestAccount[];
  loading: boolean;
  error: string | null;
  refreshCount: number;
}

export function useRealtimePinterestAccounts(agentId?: string): UseRealtimePinterestAccountsResult {
  const [accounts, setAccounts] = useState<RealtimePinterestAccount[]>([]);
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
          .eq('platform', 'pinterest')
          .order('account_name');
        if (fetchError) {
          setError(fetchError.message);
        } else {
          setAccounts((data || []) as RealtimePinterestAccount[]);
          setError(null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch accounts');
      } finally {
        setLoading(false);
      }
    };

    fetchInitial();

    const subscription = supabase
      .channel(`pinterest_accounts_${agentId}`)
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'agent_social_accounts',
          filter: `agent_id=eq.${agentId} AND user_id=eq.${user.id} AND platform=eq.pinterest`
        },
        (payload) => {
          setAccounts((current) => {
            let updated = [...current];
            if (payload.eventType === 'INSERT') {
              updated.push(payload.new as RealtimePinterestAccount);
            } else if (payload.eventType === 'UPDATE') {
              const ix = updated.findIndex(a => a.account_id === payload.new.account_id);
              if (ix >= 0) updated[ix] = payload.new as RealtimePinterestAccount;
            } else if (payload.eventType === 'DELETE') {
              updated = updated.filter(a => a.account_id !== payload.old.account_id);
            }
            setRefreshCount(c => c + 1);
            return updated.sort((a,b) => a.account_name.localeCompare(b.account_name));
          });
        }
      )
      .subscribe();

    return () => { subscription.unsubscribe(); };
  }, [agentId]);

  const enabledAccounts = accounts.filter(acc => acc.enabled);
  return { accounts, enabledAccounts, loading, error, refreshCount };
}

export async function togglePinterestAccountRealtime(
  agentId: string,
  accountId: string,
  enabled: boolean
): Promise<void> {
  const supabase = createClient();
  const { error } = await supabase
    .from('agent_social_accounts')
    .update({ enabled, updated_at: new Date().toISOString() })
    .eq('agent_id', agentId)
    .eq('account_id', accountId)
    .eq('platform', 'pinterest');
  if (error) throw error;
}

