/* Real-Time YouTube Accounts Hook - No Cache Dependencies */

import { useState, useEffect } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useAuth } from '@/components/AuthProvider';

interface RealtimeYouTubeAccount {
  account_id: string;
  account_name: string;
  username?: string;
  profile_picture?: string;
  subscriber_count: number;
  enabled: boolean;
  platform: string;
  connected_at: string;
}

interface UseRealtimeYouTubeAccountsResult {
  accounts: RealtimeYouTubeAccount[];
  enabledAccounts: RealtimeYouTubeAccount[];
  loading: boolean;
  error: string | null;
  refreshCount: number;
}

export function useRealtimeYouTubeAccounts(agentId?: string): UseRealtimeYouTubeAccountsResult {
  const [accounts, setAccounts] = useState<RealtimeYouTubeAccount[]>([]);
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
    
    // REAL-TIME: Initial fetch directly from database
    const fetchInitialAccounts = async () => {
      try {
        console.log('🔴 REAL-TIME: Fetching YouTube accounts directly from database');
        
        const { data, error: fetchError } = await supabase
          .from('agent_social_accounts')
          .select('*')
          .eq('agent_id', agentId)
          .eq('user_id', user.id)
          .eq('platform', 'youtube')
          .order('account_name');
        
        if (fetchError) {
          console.error('❌ Real-time fetch error:', fetchError);
          setError(fetchError.message);
        } else {
          console.log(`🔴 REAL-TIME RESULT: Found ${data?.length || 0} YouTube accounts`);
          data?.forEach(acc => {
            console.log(`  🔴 ${acc.enabled ? 'ENABLED' : 'DISABLED'}: ${acc.account_name} (${acc.account_id})`);
          });
          
          setAccounts(data || []);
          setError(null);
        }
      } catch (err) {
        console.error('❌ Real-time fetch exception:', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch accounts');
      } finally {
        setLoading(false);
      }
    };
    
    fetchInitialAccounts();
    
    // REAL-TIME: Subscribe to live database changes  
    const subscription = supabase
      .channel(`youtube_accounts_${agentId}`)
      .on(
        'postgres_changes',
        {
          event: '*', // All events (INSERT, UPDATE, DELETE)
          schema: 'public',
          table: 'agent_social_accounts',
          filter: `agent_id=eq.${agentId} AND user_id=eq.${user.id} AND platform=eq.youtube`
        },
        (payload) => {
          console.log('📡 REAL-TIME UPDATE: YouTube accounts changed', payload);
          
          // Immediately update state based on database change
          setAccounts(current => {
            let updated = [...current];
            
            if (payload.eventType === 'INSERT') {
              updated.push(payload.new as RealtimeYouTubeAccount);
              console.log(`🆕 Account added: ${payload.new.account_name}`);
            } else if (payload.eventType === 'UPDATE') {
              const index = updated.findIndex(acc => acc.account_id === payload.new.account_id);
              if (index >= 0) {
                updated[index] = payload.new as RealtimeYouTubeAccount;
                console.log(`🔄 Account updated: ${payload.new.account_name} (enabled: ${payload.new.enabled})`);
              }
            } else if (payload.eventType === 'DELETE') {
              updated = updated.filter(acc => acc.account_id !== payload.old.account_id);
              console.log(`🗑️ Account removed: ${payload.old.account_name}`);
            }
            
            setRefreshCount(count => count + 1);
            return updated.sort((a, b) => a.account_name.localeCompare(b.account_name));
          });
        }
      )
      .subscribe();
    
    console.log('📡 Real-time subscription active for YouTube accounts');
    
    // Cleanup subscription
    return () => {
      subscription.unsubscribe();
      console.log('📡 Unsubscribed from real-time YouTube accounts updates');
    };
  }, [agentId, user]);
  
  // Compute enabled accounts in real-time
  const enabledAccounts = accounts.filter(acc => acc.enabled);
  
  console.log(`🔴 REAL-TIME STATUS: ${accounts.length} total, ${enabledAccounts.length} enabled (refresh #${refreshCount})`);
  
  return {
    accounts,
    enabledAccounts,
    loading,
    error,
    refreshCount
  };
}

// Real-time toggle function with instant database updates
export async function toggleYouTubeAccountRealtime(
  agentId: string,
  accountId: string,
  enabled: boolean
): Promise<void> {
  const supabase = createClient();
  
  console.log(`🔴 REAL-TIME TOGGLE: ${accountId} → ${enabled ? 'ENABLED' : 'DISABLED'}`);
  
  try {
    const { error } = await supabase
      .from('agent_social_accounts')
      .update({ 
        enabled, 
        updated_at: new Date().toISOString() 
      })
      .eq('agent_id', agentId)
      .eq('account_id', accountId)
      .eq('platform', 'youtube');
    
    if (error) {
      console.error('❌ Real-time toggle failed:', error);
      throw error;
    }
    
    console.log('✅ Real-time toggle success - database updated immediately');
    
    // No cache invalidation needed - real-time subscriptions handle UI updates!
    
  } catch (err) {
    console.error('❌ Real-time toggle exception:', err);
    throw err;
  }
}