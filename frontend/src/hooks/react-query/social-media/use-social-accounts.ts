import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { backendApi } from '@/lib/api-client';
import { toast } from 'sonner';

export interface SocialAccount {
  id: string;
  name: string;
  username?: string;
  profile_picture?: string;
  subscriber_count?: number;
  view_count?: number;
  video_count?: number;
  country?: string;
  enabled: boolean;
  connected_at: string;
  platform: string;
}

export interface SocialAccountsResponse {
  success: boolean;
  agent_id?: string;
  accounts_by_platform: Record<string, SocialAccount[]>;
  total_accounts: number;
  enabled_accounts: number;
}

// Fetch social accounts
export function useSocialAccounts(platform?: string) {
  return useQuery<SocialAccountsResponse>({
    queryKey: ['social-accounts', platform],
    queryFn: async () => {
      // For now, we'll use YouTube channels as a proof of concept
      if (platform === 'youtube') {
        try {
          const response = await backendApi.get('/youtube/channels');
          const channels = response.data.channels || [];
          
          return {
            success: true,
            accounts_by_platform: {
              youtube: channels.map((channel: any) => ({
                id: channel.id,
                name: channel.name,
                username: channel.username,
                profile_picture: channel.profile_picture,
                subscriber_count: channel.subscriber_count,
                view_count: channel.view_count,
                video_count: channel.video_count,
                country: channel.country,
                enabled: channel.is_active,
                connected_at: channel.created_at,
                platform: 'youtube'
              }))
            },
            total_accounts: channels.length,
            enabled_accounts: channels.filter((c: any) => c.is_active).length
          };
        } catch (error) {
          console.error('Error fetching YouTube channels:', error);
          return {
            success: false,
            accounts_by_platform: {},
            total_accounts: 0,
            enabled_accounts: 0
          };
        }
      }
      
      // Return empty for other platforms for now
      return {
        success: true,
        accounts_by_platform: {},
        total_accounts: 0,
        enabled_accounts: 0
      };
    },
    refetchInterval: 30000, // Refetch every 30 seconds
  });
}

// Disconnect social account
export function useDisconnectAccount() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ platform, accountId }: { platform: string; accountId: string }) => {
      if (platform === 'youtube') {
        const response = await backendApi.delete(`/youtube/channels/${accountId}`);
        return response.data;
      }
      throw new Error('Platform not supported yet');
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['social-accounts'] });
      toast.success('Account disconnected successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to disconnect account');
    }
  });
}

// Refresh token for social account
export function useRefreshToken() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ platform, accountId }: { platform: string; accountId: string }) => {
      if (platform === 'youtube') {
        const response = await backendApi.post(`/youtube/channels/${accountId}/refresh`);
        return response.data;
      }
      throw new Error('Platform not supported yet');
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['social-accounts'] });
      toast.success('Token refreshed successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to refresh token');
    }
  });
}

// Connect new social account
export function useConnectAccount() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ platform }: { platform: string }) => {
      if (platform === 'youtube') {
        const response = await backendApi.post('/youtube/auth/initiate', {
          return_url: window.location.href
        });
        return response.data;
      }
      throw new Error('Platform not supported yet');
    },
    onSuccess: (data, variables) => {
      if (data.auth_url) {
        window.open(data.auth_url, '_blank');
      }
      queryClient.invalidateQueries({ queryKey: ['social-accounts'] });
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to connect account');
    }
  });
}