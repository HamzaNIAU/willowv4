'use client';

import React from 'react';
import { Switch } from '@/components/ui/switch';
import { Youtube } from 'lucide-react';
import { useRealtimeYouTubeAccounts } from '@/hooks/use-realtime-youtube-accounts';
import { useRealtimePinterestAccounts } from '@/hooks/use-realtime-pinterest-accounts';
import {
  useRealtimeInstagramAccounts,
  useRealtimeTwitterAccounts,
  useRealtimeLinkedInAccounts,
  useRealtimeTikTokAccounts,
  toggleSocialAccountRealtime,
} from '@/hooks/use-realtime-social-accounts';
import { toast } from 'sonner';

interface RealtimeMCPToggleProps {
  agentId?: string;
}

export function RealtimeMCPToggle({ agentId }: RealtimeMCPToggleProps) {
  const { accounts, enabledAccounts, loading, error, refreshCount } = useRealtimeYouTubeAccounts(agentId);
  const { accounts: pinAccounts, enabledAccounts: pinEnabled, loading: pinLoading, error: pinError, refreshCount: pinRefresh } = useRealtimePinterestAccounts(agentId);
  const { accounts: igAccounts, enabledAccounts: igEnabled, loading: igLoading, error: igError, refreshCount: igRefresh } = useRealtimeInstagramAccounts(agentId);
  const { accounts: twAccounts, enabledAccounts: twEnabled, loading: twLoading, error: twError, refreshCount: twRefresh } = useRealtimeTwitterAccounts(agentId);
  const { accounts: liAccounts, enabledAccounts: liEnabled, loading: liLoading, error: liError, refreshCount: liRefresh } = useRealtimeLinkedInAccounts(agentId);
  const { accounts: ttAccounts, enabledAccounts: ttEnabled, loading: ttLoading, error: ttError, refreshCount: ttRefresh } = useRealtimeTikTokAccounts(agentId);
  
  const handleToggle = async (accountId: string, currentEnabled: boolean) => {
    const newEnabled = !currentEnabled;
    
    try {
      console.log('🔴 YouTube integration toggle:', { accountId, newEnabled });
      if (!agentId) return;
      await toggleSocialAccountRealtime(agentId, 'youtube', accountId, newEnabled);
      
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
  
  if (loading || pinLoading || igLoading || twLoading || liLoading || ttLoading) {
    return (
      <div className="p-3 text-sm text-muted-foreground">
        🔴 Loading real-time accounts...
      </div>
    );
  }
  
  if (error || pinError || igError || twError || liError || ttError) {
    return (
      <div className="p-3 text-sm text-red-500">
        ❌ Real-time error: {error || pinError || igError || twError || liError || ttError}
      </div>
    );
  }
  
  return (
    <div className="space-y-2">
      {/* YouTube Section */}
      <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground flex items-center gap-1.5">
        <img 
          src="/platforms/youtube.svg" 
          alt="YouTube"
          className="h-3 w-3"
        />
        YouTube ({refreshCount > 0 && `Live #${refreshCount}`})
      </div>
      {accounts.length === 0 && (
        <div className="px-3 pb-1 text-xs text-muted-foreground">No YouTube accounts. Connect in Social Media.</div>
      )}
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

      {/* Divider */}
      <div className="h-px bg-border mx-3 my-2" />

      {/* Pinterest Section */}
      <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground flex items-center gap-1.5">
        <img src="/platforms/pinterest.png" alt="Pinterest" className="h-3 w-3" />
        Pinterest ({pinRefresh > 0 && `Live #${pinRefresh}`})
      </div>
      {pinAccounts.length === 0 && (
        <div className="px-3 pb-1 text-xs text-muted-foreground">No Pinterest accounts. Connect in Social Media.</div>
      )}
      {pinAccounts.map(account => (
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
                <img src="/platforms/pinterest.png" alt="Pinterest" className="h-5 w-5 hidden" />
              </>
            ) : (
              <img src="/platforms/pinterest.png" alt="Pinterest" className="h-5 w-5" />
            )}
            <div>
              <span className="text-sm font-medium">{account.account_name}</span>
              {account.username && (
                <div className="text-xs text-muted-foreground">@{account.username}</div>
              )}
              <div className="text-xs text-blue-600">
                📌 {account.pin_count ?? 0} pins • {account.board_count ?? 0} boards
              </div>
            </div>
          </div>
          <Switch
            checked={account.enabled}
            onCheckedChange={async () => {
              try {
                if (!agentId) return;
                await toggleSocialAccountRealtime(agentId, 'pinterest', account.account_id, !account.enabled);
              } catch (e) {
                toast.error('Failed to update account');
              }
            }}
            className="scale-90"
          />
        </div>
      ))}
      <div className="px-3 pt-2 text-xs text-green-600">
        ✅ {pinEnabled.length} enabled • Real-time updates active
      </div>

      {/* Divider */}
      <div className="h-px bg-border mx-3 my-2" />

      {/* Instagram Section */}
      <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground flex items-center gap-1.5">
        <img src="/platforms/instagram.png" alt="Instagram" className="h-3 w-3" />
        Instagram ({igRefresh > 0 && `Live #${igRefresh}`})
      </div>
      {igAccounts.length === 0 && (
        <div className="px-3 pb-1 text-xs text-muted-foreground">No Instagram accounts. Connect in Social Media.</div>
      )}
      {igAccounts.map(account => (
        <div key={account.account_id} className="flex items-center justify-between rounded-md px-3 py-2 hover:bg-accent">
          <div className="flex items-center gap-2">
            {account.profile_picture ? (
              <img src={account.profile_picture} alt={account.account_name} className="h-5 w-5 rounded-full object-cover border border-border/50" />
            ) : (
              <img src="/platforms/instagram.png" alt="Instagram" className="h-5 w-5" />
            )}
            <div>
              <span className="text-sm font-medium">{account.account_name}</span>
              {account.username && <div className="text-xs text-muted-foreground">@{account.username}</div>}
            </div>
          </div>
          <Switch
            checked={account.enabled}
            onCheckedChange={async () => {
              if (!agentId) return;
              try {
                await toggleSocialAccountRealtime(agentId, 'instagram', account.account_id, !account.enabled);
              } catch (e) { toast.error('Failed to update account'); }
            }}
            className="scale-90"
          />
        </div>
      ))}
      <div className="px-3 pt-2 text-xs text-green-600">✅ {igEnabled.length} enabled • Real-time updates active</div>

      {/* Divider */}
      <div className="h-px bg-border mx-3 my-2" />

      {/* X/Twitter Section */}
      <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground flex items-center gap-1.5">
        <img src="/platforms/x.png" alt="X" className="h-3 w-3" />
        X (Twitter) ({twRefresh > 0 && `Live #${twRefresh}`})
      </div>
      {twAccounts.length === 0 && (
        <div className="px-3 pb-1 text-xs text-muted-foreground">No X accounts. Connect in Social Media.</div>
      )}
      {twAccounts.map(account => (
        <div key={account.account_id} className="flex items-center justify-between rounded-md px-3 py-2 hover:bg-accent">
          <div className="flex items-center gap-2">
            {account.profile_picture ? (
              <img src={account.profile_picture} alt={account.account_name} className="h-5 w-5 rounded-full object-cover border border-border/50" />
            ) : (
              <img src="/platforms/x.png" alt="X" className="h-5 w-5" />
            )}
            <div>
              <span className="text-sm font-medium">{account.account_name}</span>
              {account.username && <div className="text-xs text-muted-foreground">@{account.username}</div>}
            </div>
          </div>
          <Switch
            checked={account.enabled}
            onCheckedChange={async () => {
              if (!agentId) return;
              try {
                await toggleSocialAccountRealtime(agentId, 'twitter', account.account_id, !account.enabled);
              } catch (e) { toast.error('Failed to update account'); }
            }}
            className="scale-90"
          />
        </div>
      ))}
      <div className="px-3 pt-2 text-xs text-green-600">✅ {twEnabled.length} enabled • Real-time updates active</div>

      {/* Divider */}
      <div className="h-px bg-border mx-3 my-2" />

      {/* LinkedIn Section */}
      <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground flex items-center gap-1.5">
        <img src="/platforms/linkedin.png" alt="LinkedIn" className="h-3 w-3" />
        LinkedIn ({liRefresh > 0 && `Live #${liRefresh}`})
      </div>
      {liAccounts.length === 0 && (
        <div className="px-3 pb-1 text-xs text-muted-foreground">No LinkedIn accounts. Connect in Social Media.</div>
      )}
      {liAccounts.map(account => (
        <div key={account.account_id} className="flex items-center justify-between rounded-md px-3 py-2 hover:bg-accent">
          <div className="flex items-center gap-2">
            {account.profile_picture ? (
              <img src={account.profile_picture} alt={account.account_name} className="h-5 w-5 rounded-full object-cover border border-border/50" />
            ) : (
              <img src="/platforms/linkedin.png" alt="LinkedIn" className="h-5 w-5" />
            )}
            <div>
              <span className="text-sm font-medium">{account.account_name}</span>
              {account.username && <div className="text-xs text-muted-foreground">{account.username}</div>}
            </div>
          </div>
          <Switch
            checked={account.enabled}
            onCheckedChange={async () => {
              if (!agentId) return;
              try {
                await toggleSocialAccountRealtime(agentId, 'linkedin', account.account_id, !account.enabled);
              } catch (e) { toast.error('Failed to update account'); }
            }}
            className="scale-90"
          />
        </div>
      ))}
      <div className="px-3 pt-2 text-xs text-green-600">✅ {liEnabled.length} enabled • Real-time updates active</div>

      {/* Divider */}
      <div className="h-px bg-border mx-3 my-2" />

      {/* TikTok Section */}
      <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground flex items-center gap-1.5">
        <img src="/platforms/tiktok.png" alt="TikTok" className="h-3 w-3" />
        TikTok ({ttRefresh > 0 && `Live #${ttRefresh}`})
      </div>
      {ttAccounts.length === 0 && (
        <div className="px-3 pb-1 text-xs text-muted-foreground">No TikTok accounts. Connect in Social Media.</div>
      )}
      {ttAccounts.map(account => (
        <div key={account.account_id} className="flex items-center justify-between rounded-md px-3 py-2 hover:bg-accent">
          <div className="flex items-center gap-2">
            {account.profile_picture ? (
              <img src={account.profile_picture} alt={account.account_name} className="h-5 w-5 rounded-full object-cover border border-border/50" />
            ) : (
              <img src="/platforms/tiktok.png" alt="TikTok" className="h-5 w-5" />
            )}
            <div>
              <span className="text-sm font-medium">{account.account_name}</span>
              {account.username && <div className="text-xs text-muted-foreground">@{account.username}</div>}
            </div>
          </div>
          <Switch
            checked={account.enabled}
            onCheckedChange={async () => {
              if (!agentId) return;
              try {
                await toggleSocialAccountRealtime(agentId, 'tiktok', account.account_id, !account.enabled);
              } catch (e) { toast.error('Failed to update account'); }
            }}
            className="scale-90"
          />
        </div>
      ))}
      <div className="px-3 pt-2 text-xs text-green-600">✅ {ttEnabled.length} enabled • Real-time updates active</div>
    </div>
  );
}
