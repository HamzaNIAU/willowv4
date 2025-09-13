'use client';

import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { RealtimeMCPToggle } from '../../realtime-mcp-toggle';
import { useRealtimeYouTubeAccounts } from '@/hooks/use-realtime-youtube-accounts';
import {
  useRealtimeInstagramAccounts,
  useRealtimeTwitterAccounts,
  useRealtimeLinkedInAccounts,
  useRealtimeTikTokAccounts,
  useRealtimeSocialAccounts,
} from '@/hooks/use-realtime-social-accounts';

type Props = { agentId?: string };

export const EnabledSocialSummary: React.FC<Props> = ({ agentId }) => {
  const [open, setOpen] = React.useState(false);
  const yt = useRealtimeYouTubeAccounts(agentId);
  const pin = useRealtimeSocialAccounts('pinterest', agentId);
  const ig = useRealtimeInstagramAccounts(agentId);
  const tw = useRealtimeTwitterAccounts(agentId);
  const li = useRealtimeLinkedInAccounts(agentId);
  const tt = useRealtimeTikTokAccounts(agentId);

  const items = [
    { key: 'youtube', label: 'YouTube', icon: '/platforms/youtube.svg', count: yt.enabledAccounts.length },
    { key: 'pinterest', label: 'Pinterest', icon: '/platforms/pinterest.png', count: pin.enabledAccounts.length },
    { key: 'instagram', label: 'Instagram', icon: '/platforms/instagram.png', count: ig.enabledAccounts.length },
    { key: 'twitter', label: 'X', icon: '/platforms/x.png', count: tw.enabledAccounts.length },
    { key: 'linkedin', label: 'LinkedIn', icon: '/platforms/linkedin.png', count: li.enabledAccounts.length },
    { key: 'tiktok', label: 'TikTok', icon: '/platforms/tiktok.png', count: tt.enabledAccounts.length },
  ];

  return (
    <>
      <div className="hidden sm:flex items-center gap-1.5 ml-1">
        {items.map((it) => (
          <button
            key={it.key}
            type="button"
            onClick={(e) => {
              if (e.metaKey || e.ctrlKey) {
                // Deep-jump to Social Media section in the unified menu
                const event = new CustomEvent('unified-social-open', { detail: { platform: it.key } });
                window.dispatchEvent(event);
              } else {
                setOpen(true);
              }
            }}
            className="flex items-center gap-1 px-1.5 py-0.5 rounded-md border border-border bg-background text-xs text-muted-foreground hover:bg-accent/40"
            title={`${it.label}: ${it.count} enabled (click to manage)`}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={it.icon}
              alt={it.label}
              className={`h-3.5 w-3.5 ${it.key === 'pinterest' ? 'rounded-full' : ''}`}
            />
            <span className={`font-medium ${it.count > 0 ? 'text-foreground' : 'text-muted-foreground'}`}>
              {it.count}
            </span>
          </button>
        ))}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Connected Accounts</DialogTitle>
          </DialogHeader>
          <div className="mt-1">
            <RealtimeMCPToggle agentId={agentId} />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};
