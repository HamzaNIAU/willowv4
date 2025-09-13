'use client';

import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { PageHeader } from '@/components/ui/page-header';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { 
  Youtube, 
  Instagram, 
  Twitter, 
  Facebook,
  Linkedin,
  Music,
  Video,
  Plus,
  Check,
  X,
  ExternalLink,
  Users,
  Eye,
  PlayCircle,
  AlertCircle,
  Share2,
  Search,
  Settings,
  CheckCircle2,
  XCircle,
  Trash2,
  Copy,
  EyeOff,
  MoreVertical,
  Pin
} from 'lucide-react';
import { LayoutGrid } from 'lucide-react';

// Custom platform SVG components
const YoutubeSvg = ({ className }: { className?: string }) => (
  <img src="/platforms/youtube.svg" alt="YouTube" className={className} />
);

const InstagramSvg = ({ className }: { className?: string }) => (
  <img src="/platforms/instagram.png" alt="Instagram" className={className} />
);

const TwitterSvg = ({ className }: { className?: string }) => (
  <img src="/platforms/x.png" alt="X (Twitter)" className={className} />
);

const TikTokSvg = ({ className }: { className?: string }) => (
  <img src="/platforms/tiktok.png" alt="TikTok" className={className} />
);

const LinkedInSvg = ({ className }: { className?: string }) => (
  <img src="/platforms/linkedin.png" alt="LinkedIn" className={className} />
);

const FacebookSvg = ({ className }: { className?: string }) => (
  <img src="/platforms/facebook.png" alt="Facebook" className={className} />
);

const TwitchSvg = ({ className }: { className?: string }) => (
  <img src="/platforms/twitch.png" alt="Twitch" className={className} />
);
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { backendApi } from '@/lib/api-client';
import { toast } from 'sonner';

interface YouTubeChannel {
  id: string;
  name: string;
  username?: string;
  profile_picture?: string;
  profile_picture_medium?: string;
  profile_picture_small?: string;
  subscriber_count: number;
  view_count: number;
  video_count: number;
  created_at: string;
}

interface PinterestAccount {
  id: string;
  name: string;
  username?: string;
  profile_picture?: string;
  profile_picture_medium?: string;
  profile_picture_small?: string;
  subscriber_count: number;
  view_count: number;
  video_count: number;
  board_count?: number;
  created_at: string;
}

interface SocialMediaAccount {
  platform: string;
  id: string;
  name: string;
  username?: string;
  profile_picture?: string;
  connected: boolean;
  stats?: {
    followers?: number;
    posts?: number;
    views?: number;
  };
}

const platformIcons = {
  youtube: YoutubeSvg,
  instagram: InstagramSvg,
  twitter: TwitterSvg,
  facebook: FacebookSvg,
  linkedin: LinkedInSvg,
  tiktok: TikTokSvg,
  twitch: TwitchSvg,
};

const platformColors = {
  youtube: 'hover:bg-red-50 hover:border-red-200 dark:hover:bg-red-950/20',
  instagram: 'hover:bg-pink-50 hover:border-pink-200 dark:hover:bg-pink-950/20',
  twitter: 'hover:bg-blue-50 hover:border-blue-200 dark:hover:bg-blue-950/20',
  facebook: 'hover:bg-blue-50 hover:border-blue-200 dark:hover:bg-blue-950/20',
  linkedin: 'hover:bg-blue-50 hover:border-blue-200 dark:hover:bg-blue-950/20',
  tiktok: 'hover:bg-gray-50 hover:border-gray-200 dark:hover:bg-gray-950/20',
  twitch: 'hover:bg-purple-50 hover:border-purple-200 dark:hover:bg-purple-950/20',
};

interface SocialPlatformGroup {
  name: string;
  key: 'youtube' | 'pinterest' | 'linkedin' | 'instagram' | 'twitter' | 'tiktok' | 'facebook' | 'twitch' | string;
  icon: any;
  icon_url?: string;
  color: string;
  accounts: (YouTubeChannel | PinterestAccount)[];
  available: boolean;
  description: string;
}

export default function SocialMediaPage() {
  const queryClient = useQueryClient();
  const [connectingPlatform, setConnectingPlatform] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showMcpDialog, setShowMcpDialog] = useState(false);
  const [selectedChannel, setSelectedChannel] = useState<YouTubeChannel | null>(null);

  // Fetch YouTube channels
  const { data: youtubeChannels, isLoading: loadingYouTube } = useQuery({
    queryKey: ['youtube', 'channels'],
    queryFn: async () => {
      const response = await backendApi.get<{ success: boolean; channels: YouTubeChannel[] }>(
        '/youtube/channels'
      );
      console.log('🐛 DEBUG: YouTube API response:', response.data);
      return response.data.channels;
    },
  });

  // Temporarily disable problematic platform account fetching until backend is fixed
  const instagramAccounts: any[] = [];
  const twitterAccounts: any[] = [];
  const linkedinAccounts: any[] = [];
  const tiktokAccounts: any[] = [];

  // Enable Pinterest account fetching (backend fixed)
  const { data: pinterestAccounts, isLoading: loadingPinterest } = useQuery({
    queryKey: ['pinterest', 'accounts'],
    queryFn: async () => {
      try {
        const response = await backendApi.get<{ success: boolean; accounts: PinterestAccount[] }>(
          '/pinterest/accounts'
        );
        console.log('🐛 DEBUG: Pinterest API response:', response.data);
        return response.data.accounts || [];
      } catch (error) {
        console.warn('Pinterest API not available:', error);
        return [];
      }
    },
  });

  // Initiate YouTube auth
  const initiateYouTubeAuth = useMutation({
    mutationFn: async () => {
      const response = await backendApi.post<{ success: boolean; auth_url: string }>(
        '/youtube/auth/initiate'
      );
      return response.data;
    },
    onSuccess: (data) => {
      if (data.auth_url) {
        // Open OAuth popup
        const popup = window.open(
          data.auth_url,
          'youtube-auth',
          'width=600,height=700,resizable=yes,scrollbars=yes'
        );
        
        // Listen for auth completion
        const handleMessage = (event: MessageEvent) => {
          if (event.data?.type === 'youtube-auth-success') {
            popup?.close();
            queryClient.invalidateQueries({ queryKey: ['youtube', 'channels'] });
            
            // Show success toast with channel info
            const channel = event.data.channel;
            if (channel) {
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
                      {channel.name || 'YouTube Channel'} {channel.username && `• @${channel.username}`}
                    </div>
                  </div>
                </div>
              );
            } else {
              toast.success('YouTube account connected successfully!');
            }
            
            window.removeEventListener('message', handleMessage);
            setConnectingPlatform(null);
          } else if (event.data?.type === 'youtube-auth-error') {
            popup?.close();
            toast.error(`Failed to connect: ${event.data.error}`);
            window.removeEventListener('message', handleMessage);
            setConnectingPlatform(null);
          }
        };
        
        window.addEventListener('message', handleMessage);
      }
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to initiate YouTube authentication');
      setConnectingPlatform(null);
    },
  });

  // Remove YouTube channel
  const removeYouTubeChannel = useMutation({
    mutationFn: async (channelId: string) => {
      const res = await backendApi.delete(`/youtube/channels/${channelId}`);
      if (!res.success) {
        // Ensure errors propagate so onSuccess is not called
        throw (res.error as any) || new Error('Failed to disconnect YouTube channel');
      }
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['youtube', 'channels'] });
      toast.success('YouTube channel disconnected');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to disconnect channel');
    },
  });

  // Remove Pinterest account
  const removePinterestAccount = useMutation({
    mutationFn: async (accountId: string) => {
      const res = await backendApi.delete(`/pinterest/accounts/${accountId}`);
      if (!res.success) {
        throw (res.error as any) || new Error('Failed to disconnect Pinterest account');
      }
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pinterest', 'accounts'] });
      toast.success('Pinterest account disconnected');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to disconnect account');
    },
  });

  // Centralized, key-safe disconnect handler with logging
  const handleDisconnect = (platformKey: string, accountId: string) => {
    try {
      console.log('[SocialMedia] Disconnect clicked', { platformKey, accountId });
      if (platformKey === 'youtube') {
        removeYouTubeChannel.mutate(accountId);
      } else if (platformKey === 'pinterest') {
        removePinterestAccount.mutate(accountId);
      } else {
        toast.info('Disconnect not supported for ' + platformKey);
      }
    } catch (e) {
      console.error('[SocialMedia] Disconnect error', e);
    }
  };

  const handleConnectYouTube = () => {
    setConnectingPlatform('youtube');
    initiateYouTubeAuth.mutate();
  };

  // Initiate Pinterest auth
  const initiatePinterestAuth = useMutation({
    mutationFn: async () => {
      const response = await backendApi.post<{ success: boolean; auth_url: string }>(
        '/pinterest/auth/initiate'
      );
      return response.data;
    },
    onSuccess: (data) => {
      if (data.auth_url) {
        const popup = window.open(
          data.auth_url,
          'pinterest-auth',
          'width=600,height=700,resizable=yes,scrollbars=yes'
        );
        
        const handleMessage = (event: MessageEvent) => {
          if (event.data?.type === 'pinterest-auth-success') {
            popup?.close();
            queryClient.invalidateQueries({ queryKey: ['pinterest', 'accounts'] });
            const account = event.data.account;
            if (account && (account.name || account.username)) {
              toast.success(
                <div className="flex items-center gap-3">
                  {account.profile_image_url && (
                    <img src={account.profile_image_url} alt="" className="w-8 h-8 rounded-full" />
                  )}
                  <div>
                    <div className="font-semibold">Connected Successfully!</div>
                    <div className="text-sm opacity-90">
                      {account.name || account.username} {account.username && `• @${account.username}`}
                    </div>
                  </div>
                </div>
              );
            } else {
              toast.success('Pinterest account connected successfully!');
            }
            window.removeEventListener('message', handleMessage);
            window.removeEventListener('storage', handleStorage);
            setConnectingPlatform(null);
          } else if (event.data?.type === 'pinterest-auth-error') {
            popup?.close();
            toast.error(`Failed to connect: ${event.data.error}`);
            window.removeEventListener('message', handleMessage);
            window.removeEventListener('storage', handleStorage);
            setConnectingPlatform(null);
          }
        };
        // Fallback via localStorage in case postMessage is blocked
        const handleStorage = (event: StorageEvent) => {
          if (event.key === 'pinterest-auth-result' && event.newValue) {
            try {
              const result = JSON.parse(event.newValue);
              if (result.type === 'pinterest-auth-success' || result.type === 'pinterest-auth-error') {
                handleMessage({ data: result } as MessageEvent);
                localStorage.removeItem('pinterest-auth-result');
              }
            } catch (e) {
              console.error('Failed to parse storage event:', e);
            }
          }
        };
        
        window.addEventListener('message', handleMessage);
        window.addEventListener('storage', handleStorage);
      }
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to initiate Pinterest authentication');
      setConnectingPlatform(null);
    },
  });

  const handleConnectPinterest = () => {
    setConnectingPlatform('pinterest');
    initiatePinterestAuth.mutate();
  };

  // Initiate Instagram auth
  const initiateInstagramAuth = useMutation({
    mutationFn: async () => {
      const response = await backendApi.post<{ success: boolean; auth_url: string }>(
        '/instagram/auth/initiate'
      );
      return response.data;
    },
    onSuccess: (data) => {
      if (data.auth_url) {
        const popup = window.open(
          data.auth_url,
          'instagram-auth',
          'width=600,height=700,resizable=yes,scrollbars=yes'
        );
        
        const handleMessage = (event: MessageEvent) => {
          if (event.data?.type === 'instagram-auth-success') {
            popup?.close();
            queryClient.invalidateQueries({ queryKey: ['instagram', 'accounts'] });
            toast.success('Instagram account connected successfully!');
            window.removeEventListener('message', handleMessage);
            setConnectingPlatform(null);
          } else if (event.data?.type === 'instagram-auth-error') {
            popup?.close();
            toast.error(`Failed to connect: ${event.data.error}`);
            window.removeEventListener('message', handleMessage);
            setConnectingPlatform(null);
          }
        };
        
        window.addEventListener('message', handleMessage);
      }
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to initiate Instagram authentication');
      setConnectingPlatform(null);
    },
  });

  // Initiate Twitter auth
  const initiateTwitterAuth = useMutation({
    mutationFn: async () => {
      const response = await backendApi.post<{ success: boolean; auth_url: string }>(
        '/twitter/auth/initiate'
      );
      return response.data;
    },
    onSuccess: (data) => {
      if (data.auth_url) {
        const popup = window.open(
          data.auth_url,
          'twitter-auth',
          'width=600,height=700,resizable=yes,scrollbars=yes'
        );
        
        const handleMessage = (event: MessageEvent) => {
          if (event.data?.type === 'twitter-auth-success') {
            popup?.close();
            queryClient.invalidateQueries({ queryKey: ['twitter', 'accounts'] });
            toast.success('Twitter account connected successfully!');
            window.removeEventListener('message', handleMessage);
            setConnectingPlatform(null);
          } else if (event.data?.type === 'twitter-auth-error') {
            popup?.close();
            toast.error(`Failed to connect: ${event.data.error}`);
            window.removeEventListener('message', handleMessage);
            setConnectingPlatform(null);
          }
        };
        
        window.addEventListener('message', handleMessage);
      }
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to initiate Twitter authentication');
      setConnectingPlatform(null);
    },
  });

  // Initiate LinkedIn auth
  const initiateLinkedInAuth = useMutation({
    mutationFn: async () => {
      const response = await backendApi.post<{ success: boolean; auth_url: string }>(
        '/linkedin/auth/initiate'
      );
      return response.data;
    },
    onSuccess: (data) => {
      if (data.auth_url) {
        const popup = window.open(
          data.auth_url,
          'linkedin-auth',
          'width=600,height=700,resizable=yes,scrollbars=yes'
        );
        
        const handleMessage = (event: MessageEvent) => {
          if (event.data?.type === 'linkedin-auth-success') {
            popup?.close();
            queryClient.invalidateQueries({ queryKey: ['linkedin', 'accounts'] });
            toast.success('LinkedIn account connected successfully!');
            window.removeEventListener('message', handleMessage);
            setConnectingPlatform(null);
          } else if (event.data?.type === 'linkedin-auth-error') {
            popup?.close();
            toast.error(`Failed to connect: ${event.data.error}`);
            window.removeEventListener('message', handleMessage);
            setConnectingPlatform(null);
          }
        };
        
        window.addEventListener('message', handleMessage);
      }
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to initiate LinkedIn authentication');
      setConnectingPlatform(null);
    },
  });

  // Initiate TikTok auth
  const initiateTikTokAuth = useMutation({
    mutationFn: async () => {
      const response = await backendApi.post<{ success: boolean; auth_url: string }>(
        '/tiktok/auth/initiate'
      );
      return response.data;
    },
    onSuccess: (data) => {
      if (data.auth_url) {
        const popup = window.open(
          data.auth_url,
          'tiktok-auth',
          'width=600,height=700,resizable=yes,scrollbars=yes'
        );
        
        const handleMessage = (event: MessageEvent) => {
          if (event.data?.type === 'tiktok-auth-success') {
            popup?.close();
            queryClient.invalidateQueries({ queryKey: ['tiktok', 'accounts'] });
            toast.success('TikTok account connected successfully!');
            window.removeEventListener('message', handleMessage);
            setConnectingPlatform(null);
          } else if (event.data?.type === 'tiktok-auth-error') {
            popup?.close();
            toast.error(`Failed to connect: ${event.data.error}`);
            window.removeEventListener('message', handleMessage);
            setConnectingPlatform(null);
          }
        };
        
        window.addEventListener('message', handleMessage);
      }
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to initiate TikTok authentication');
      setConnectingPlatform(null);
    },
  });

  const handleConnectInstagram = () => {
    setConnectingPlatform('instagram');
    initiateInstagramAuth.mutate();
  };

  const handleConnectTwitter = () => {
    setConnectingPlatform('twitter');
    initiateTwitterAuth.mutate();
  };

  const handleConnectLinkedIn = () => {
    setConnectingPlatform('linkedin');
    initiateLinkedInAuth.mutate();
  };

  const handleConnectTikTok = () => {
    setConnectingPlatform('tiktok');
    initiateTikTokAuth.mutate();
  };

  const formatCount = (count?: number): string => {
    const n = typeof count === 'number' && isFinite(count) ? count : 0;
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
    return `${n}`;
  };

  // Group platforms with their connected accounts
  const socialPlatforms = useMemo((): SocialPlatformGroup[] => {
    const platforms: SocialPlatformGroup[] = [
      {
        name: 'YouTube',
        key: 'youtube',
        icon: YoutubeSvg,
        color: 'text-red-600 dark:text-red-500',
        accounts: youtubeChannels || [],
        available: true,
        description: 'Upload videos, manage playlists, and analyze channel performance'
      },
      {
        name: 'Instagram',
        key: 'instagram',
        icon: InstagramSvg,
        color: 'text-pink-600 dark:text-pink-500',
        accounts: [],
        available: true,
        description: 'Post photos and stories, manage content, and track engagement'
      },
      {
        name: 'X (Twitter)',
        key: 'twitter',
        icon: TwitterSvg,
        color: 'text-blue-600 dark:text-blue-500',
        accounts: [],
        available: true,
        description: 'Tweet, schedule posts, and analyze engagement metrics'
      },
      {
        name: 'TikTok',
        key: 'tiktok',
        icon: TikTokSvg,
        color: 'text-gray-900 dark:text-gray-100',
        accounts: [],
        available: true,
        description: 'Upload short videos, track trends, and manage content'
      },
      {
        name: 'LinkedIn',
        key: 'linkedin',
        icon: LinkedInSvg,
        color: 'text-blue-700 dark:text-blue-600',
        accounts: linkedinAccounts || [],
        available: true,
        description: 'Share professional content and manage company pages'
      },
      {
        name: 'Pinterest',
        key: 'pinterest',
        icon: () => <img src="/platforms/pinterest.png" alt="Pinterest" className="h-6 w-6" />,
        color: 'text-red-600 dark:text-red-500',
        accounts: pinterestAccounts || [],
        available: true,
        description: 'Create pins, manage boards, and track engagement'
      },
      // Facebook and Twitch temporarily hidden from UI
    ];

    // Filter based on search
    if (searchQuery) {
      return platforms.filter(p => 
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.accounts.some(a => 
          a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          a.username?.toLowerCase().includes(searchQuery.toLowerCase())
        )
      );
    }

    return platforms;
  }, [youtubeChannels, linkedinAccounts, pinterestAccounts, searchQuery]);

  const connectedPlatforms = socialPlatforms.filter(p => p.accounts.length > 0);
  const availablePlatforms = socialPlatforms.filter(p => p.available && p.accounts.length === 0);
  const comingSoonPlatforms = socialPlatforms.filter(p => !p.available);


  return (
    <div className="container mx-auto max-w-4xl px-6 py-6">
      <div className="space-y-8">
        <PageHeader icon={Share2}>
          <span className="text-primary">Social Media Connections</span>
        </PageHeader>

        {/* Search Bar */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search platforms or accounts..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 pr-9"
          />
          {searchQuery && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSearchQuery('')}
              className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>

        {/* Connected Platforms */}
        {connectedPlatforms.length > 0 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold">Connected Accounts</h2>
            {connectedPlatforms.map((platform) => (
              <Card key={platform.name}>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 rounded-lg bg-muted border flex items-center justify-center">
                        <platform.icon className={`h-5 w-5 ${platform.color}`} />
                      </div>
                      <div>
                        <CardTitle className="text-base">{platform.name}</CardTitle>
                        <CardDescription className="text-xs">
                          {platform.accounts.length} {platform.accounts.length === 1 ? 'account' : 'accounts'} connected
                        </CardDescription>
                      </div>
                    </div>
                    <Button
                      onClick={
                        platform.key === 'youtube' ? handleConnectYouTube :
                        platform.key === 'pinterest' ? handleConnectPinterest :
                        platform.key === 'linkedin' ? handleConnectLinkedIn :
                        platform.key === 'instagram' ? handleConnectInstagram :
                        platform.key === 'twitter' ? handleConnectTwitter :
                        platform.key === 'tiktok' ? handleConnectTikTok :
                        undefined
                      }
                      disabled={!platform.available || connectingPlatform === platform.key}
                      size="sm"
                    >
                      <Plus className="h-4 w-4 mr-2" />
                      Add Account
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {loadingYouTube && platform.name === 'YouTube' ? (
                    <div className="space-y-2">
                      <Skeleton className="h-16 w-full" />
                      <Skeleton className="h-16 w-full" />
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Account</TableHead>
                          <TableHead>Statistics</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead className="w-[50px]"></TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {platform.accounts.map((channel) => (
                          <TableRow key={channel.id}>
                            <TableCell>
                              <div className="flex items-center gap-3">
                                {(channel.profile_picture_medium || channel.profile_picture || channel.profile_picture_small) ? (
                                  <img
                                    src={channel.profile_picture_medium || channel.profile_picture || channel.profile_picture_small}
                                    alt={channel.name}
                                    className="h-10 w-10 rounded-full object-cover border"
                                    onError={(e) => {
                                      console.error('Failed to load profile picture for:', channel.name, e);
                                      (e.target as HTMLImageElement).style.display = 'none';
                                      (e.target as HTMLImageElement).nextElementSibling?.classList.remove('hidden');
                                    }}
                                  />
                                ) : null}
                                <div className={`h-10 w-10 rounded-full ${
                                  platform.name === 'Pinterest' ? 'bg-red-100 dark:bg-red-900/20' : 
                                  'bg-red-100 dark:bg-red-900/20'
                                } flex items-center justify-center ${
                                  (channel.profile_picture_medium || channel.profile_picture || channel.profile_picture_small) ? 'hidden' : ''
                                }`}>
                                  <img 
                                    src={platform.name === 'Pinterest' ? '/platforms/pinterest.png' : '/platforms/youtube.svg'} 
                                    alt={platform.name}
                                    className="h-5 w-5"
                                  />
                                </div>
                                <div>
                                  <div className="font-medium">{channel.name}</div>
                                  {channel.username && (
                                    <div className="text-sm text-muted-foreground">@{channel.username}</div>
                                  )}
                                </div>
                              </div>
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-6 text-sm">
                                {/* Followers / Subscribers */}
                                <div className="flex flex-col items-center min-w-[72px]">
                                  <div className="flex items-center gap-1">
                                    <Users className="h-3.5 w-3.5 text-muted-foreground" />
                                    <span>{formatCount(channel.subscriber_count)}</span>
                                  </div>
                                  <div className="text-[10px] text-muted-foreground">
                                    {platform.name === 'Pinterest' ? 'Followers' : 'Subscribers'}
                                  </div>
                                </div>
                                {/* Views (YouTube) or Monthly Views (Pinterest) */}
                                <div className="flex flex-col items-center min-w-[72px]">
                                  <div className="flex items-center gap-1">
                                    <Eye className="h-3.5 w-3.5 text-muted-foreground" />
                                    <span>{formatCount(channel.view_count)}</span>
                                  </div>
                                  <div className="text-[10px] text-muted-foreground">Views</div>
                                </div>
                                {/* Videos (YouTube) or Pins (Pinterest), with board count badge for Pinterest */}
                                <div className="flex flex-col items-center min-w-[72px]">
                                  <div className="flex items-center gap-2">
                                    <div className="flex items-center gap-1">
                                      {platform.name === 'Pinterest' ? (
                                        <Pin className="h-3.5 w-3.5 text-muted-foreground" />
                                      ) : (
                                        <PlayCircle className="h-3.5 w-3.5 text-muted-foreground" />
                                      )}
                                      <span>{formatCount(channel.video_count)}</span>
                                    </div>
                                    {platform.name === 'Pinterest' && typeof (channel as PinterestAccount).board_count !== 'undefined' && (
                                      <Badge variant="secondary" className="h-5 px-1.5 py-0 text-[10px] flex items-center gap-1">
                                        <LayoutGrid className="h-3 w-3" />
                                        {formatCount((channel as PinterestAccount).board_count)}
                                      </Badge>
                                    )}
                                  </div>
                                  <div className="text-[10px] text-muted-foreground">
                                    {platform.name === 'Pinterest' ? 'Pins' : 'Videos'}
                                  </div>
                                </div>
                              </div>
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-1.5">
                                <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-500" />
                                <span className="text-sm text-green-600 dark:text-green-500">Connected</span>
                              </div>
                            </TableCell>
                            <TableCell>
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                    <MoreVertical className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem 
                                    onClick={() => {
                                      const url = platform.key === 'youtube' 
                                        ? `https://youtube.com/channel/${channel.id}`
                                        : platform.key === 'pinterest'
                                        ? `https://pinterest.com/${channel.username || 'profile'}`
                                        : '#';
                                      window.open(url, '_blank');
                                    }}
                                  >
                                    <ExternalLink className="h-4 w-4 mr-2" />
                                    View {platform.name === 'Pinterest' ? 'Profile' : 'Channel'}
                                  </DropdownMenuItem>
                                  {platform.key === 'youtube' && (
                                    <>
                                      <DropdownMenuItem
                                        onClick={() => {
                                          setSelectedChannel(channel);
                                          setShowMcpDialog(true);
                                        }}
                                      >
                                        <Settings className="h-4 w-4 mr-2" />
                                        MCP Settings
                                      </DropdownMenuItem>
                                      <DropdownMenuSeparator />
                                    </>
                                  )}
                                  {platform.key !== 'youtube' && <DropdownMenuSeparator />}
                                  <DropdownMenuItem
                                    onClick={() => {
                                      // Capture platform key explicitly to avoid any stale/portal issues
                                      const platformKey = (platform.key as string) || '';
                                      handleDisconnect(platformKey, (channel as any).id);
                                    }}
                                    className="text-destructive"
                                  >
                                    <Trash2 className="h-4 w-4 mr-2" />
                                    Disconnect
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Available Platforms */}
        {availablePlatforms.length > 0 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold">Available Integrations</h2>
            <div className="grid gap-4">
              {availablePlatforms.map((platform) => (
                <Card key={platform.name} className="hover:shadow-sm transition-shadow">
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="h-12 w-12 rounded-lg bg-muted border flex items-center justify-center">
                          <platform.icon className={`h-6 w-6 ${platform.color}`} />
                        </div>
                        <div className="flex-1">
                          <h3 className="font-semibold">{platform.name}</h3>
                          <p className="text-sm text-muted-foreground">{platform.description}</p>
                        </div>
                      </div>
                      <Button
                        onClick={
                          platform.key === 'youtube' ? handleConnectYouTube :
                          platform.key === 'pinterest' ? handleConnectPinterest :
                          platform.key === 'linkedin' ? handleConnectLinkedIn :
                          platform.key === 'instagram' ? handleConnectInstagram :
                          platform.key === 'twitter' ? handleConnectTwitter :
                          platform.key === 'tiktok' ? handleConnectTikTok :
                          undefined
                        }
                        disabled={connectingPlatform === platform.key}
                      >
                        <Plus className="h-4 w-4 mr-2" />
                        Connect
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Coming Soon Platforms */}
        {comingSoonPlatforms.length > 0 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold">Coming Soon</h2>
            <div className="grid gap-4 md:grid-cols-2">
              {comingSoonPlatforms.map((platform) => (
                <Card key={platform.name} className="opacity-60">
                  <CardContent className="p-6">
                    <div className="flex items-center gap-4">
                      <div className="h-12 w-12 rounded-lg bg-muted border flex items-center justify-center">
                        <platform.icon className={`h-6 w-6 ${platform.color} opacity-50`} />
                      </div>
                      <div className="flex-1">
                        <h3 className="font-semibold">{platform.name}</h3>
                        <p className="text-sm text-muted-foreground">{platform.description}</p>
                        <p className="text-xs text-muted-foreground mt-1">Integration coming soon</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* MCP URL Dialog */}
        {showMcpDialog && selectedChannel && (
          <Dialog open={showMcpDialog} onOpenChange={setShowMcpDialog}>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-3">
                  <div className="h-14 w-14 rounded-lg bg-muted border flex items-center justify-center overflow-hidden">
                    {selectedChannel.profile_picture ? (
                      <img 
                        src={selectedChannel.profile_picture} 
                        alt={selectedChannel.name}
                        className="h-10 w-10 rounded-full object-cover"
                      />
                    ) : (
                      <img 
                        src="/platforms/youtube.svg" 
                        alt="YouTube"
                        className="h-6 w-6"
                      />
                    )}
                  </div>
                  <div>
                    <span>{selectedChannel.name}</span>
                    <div className="text-sm text-muted-foreground flex items-center gap-1 mt-1">
                      <ExternalLink className="h-3 w-3" />
                      <span>YouTube MCP Settings</span>
                    </div>
                  </div>
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-6">
                <Alert className="border-amber-400/50 dark:border-amber-600/30 bg-amber-400/10 dark:bg-amber-900/10">
                  <AlertDescription className="text-amber-800 dark:text-amber-600">
                    <strong>MCP URL:</strong> Use this URL to configure YouTube tools in your AI agents
                  </AlertDescription>
                </Alert>
                <div className="space-y-3">
                  <label className="text-sm font-medium">MCP Connection URL</label>
                  <div className="flex items-center gap-2 p-3 bg-muted rounded-lg border font-mono text-sm">
                    <code className="flex-1 break-all">
                      http://localhost:8000/api/youtube/mcp/stream
                    </code>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={async () => {
                        await navigator.clipboard.writeText('http://localhost:8000/api/youtube/mcp/stream');
                        toast.success('MCP URL copied to clipboard');
                      }}
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <div className="flex justify-end gap-3">
                  <Button variant="outline" onClick={() => setShowMcpDialog(false)}>
                    Close
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        )}
      </div>
    </div>
  );
}
