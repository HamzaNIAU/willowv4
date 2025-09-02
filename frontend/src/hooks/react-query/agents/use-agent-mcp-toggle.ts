import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAgent } from './use-agents';
import { useComposioCredentialsProfiles } from '../composio/use-composio-profiles';
import { backendApi } from '@/lib/api-client';
import { toast } from 'sonner';

interface UpdateMcpToggleParams {
  agentId: string;
  mcpId: string;
  enabled: boolean;
}

interface MCPToggle {
  [mcpId: string]: boolean;
}

// Hook to fetch MCP toggle states from backend
export const useAgentMcpToggles = (agentId?: string) => {
  return useQuery({
    queryKey: ['agent-mcp-toggles', agentId],
    queryFn: async () => {
      if (!agentId) return {};
      
      try {
        const response = await backendApi.get<{ success: boolean; toggles: MCPToggle }>(
          `/agents/${agentId}/mcp-toggles`
        );
        return response.data.toggles || {};
      } catch (error) {
        console.error('Failed to fetch MCP toggles:', error);
        return {};
      }
    },
    enabled: !!agentId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

export const useUpdateAgentMcpToggle = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ agentId, mcpId, enabled }: UpdateMcpToggleParams) => {
      // Call the real backend API endpoint
      const response = await backendApi.put(`/agents/${agentId}/mcp-toggle`, {
        mcp_id: mcpId,
        enabled: enabled,
      });
      
      return response.data;
    },
    onSuccess: (data, variables) => {
      // Invalidate relevant queries to refresh the data
      queryClient.invalidateQueries({ queryKey: ['agent', variables.agentId] });
      queryClient.invalidateQueries({ queryKey: ['agent-mcp-toggles', variables.agentId] });
      queryClient.invalidateQueries({ queryKey: ['composio-credentials-profiles'] });
      
      // REAL-TIME: Invalidate YouTube channels when YouTube toggles change
      if (variables.mcpId.startsWith('social.youtube.')) {
        queryClient.invalidateQueries({ queryKey: ['youtube', 'channels'] });
        queryClient.invalidateQueries({ queryKey: ['youtube'] }); // Invalidate all YouTube queries
        
        // Trigger live refresh of YouTube tool views via localStorage event
        localStorage.setItem('youtube_toggle_changed', Date.now().toString());
        localStorage.removeItem('youtube_toggle_changed'); // Trigger storage event
        
        console.log('🔄 Triggered real-time YouTube tool refresh');
      }
      
      // Show success message
      toast.success(`${variables.enabled ? 'Enabled' : 'Disabled'} successfully`);
    },
    onError: (error) => {
      console.error('Failed to update MCP toggle:', error);
      toast.error('Failed to update connection');
    },
  });
};

// Hook to get YouTube channels
const useYouTubeChannels = () => {
  return useQuery({
    queryKey: ['youtube', 'channels'],
    queryFn: async () => {
      try {
        const response = await backendApi.get<{ success: boolean; channels: any[] }>(
          '/youtube/channels'
        );
        return response.data.channels || [];
      } catch (error) {
        console.error('Failed to fetch YouTube channels:', error);
        return [];
      }
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

// Hook to get MCP configurations for an agent
export const useAgentMcpConfigurations = (agentId?: string) => {
  // Special handling for suna-default virtual agent
  const isVirtualAgent = agentId === 'suna-default';
  
  // Only call useAgent for non-virtual agents
  // The useAgent hook internally checks for valid agentId
  const { data: agent, isLoading: agentLoading, error: agentError } = useAgent(
    isVirtualAgent ? '' : (agentId || '')
  );
  const { data: composioProfiles, isLoading: composioLoading } = useComposioCredentialsProfiles();
  const { data: youtubeChannels, isLoading: youtubeLoading } = useYouTubeChannels();
  const { data: toggleStates, isLoading: togglesLoading } = useAgentMcpToggles(agentId);
  
  // Don't fetch agent data for virtual agents
  const shouldFetch = !!agentId && !isVirtualAgent;
  
  // Extract MCP configurations from agent data
  // The agent stores MCPs in 'configured_mcps' field
  const mcpConfigurations = React.useMemo(() => {
    const allMcps = [];
    
    // Add YouTube channels as social media MCPs
    if (youtubeChannels && youtubeChannels.length > 0) {
      youtubeChannels.forEach((channel: any) => {
        const mcpId = `social.youtube.${channel.id}`;
        allMcps.push({
          name: channel.username || channel.name,
          qualifiedName: mcpId,
          enabled: toggleStates?.[mcpId] !== undefined ? toggleStates[mcpId] : true, // Use saved state or default to true
          isSocialMedia: true,
          customType: 'social-media',
          platform: 'youtube',
          config: {
            channel_id: channel.id,
            channel_name: channel.name,
            username: channel.username,
            profile_picture: channel.profile_picture_medium || channel.profile_picture,
            mcp_url: 'http://localhost:8000/api/youtube/mcp/stream',
          },
          icon_url: channel.profile_picture_medium || channel.profile_picture,
          profile_picture: channel.profile_picture_medium || channel.profile_picture,
        });
      });
    }
    
    // Get Composio profiles and convert them to MCP format
    if (composioProfiles && composioProfiles.length > 0) {
      const composioMcps = composioProfiles.map((profile: any) => {
        // Extract the app name properly
        const appSlug = profile.toolkit_slug || profile.app_slug || '';
        const appName = profile.toolkit_name || profile.app_name || appSlug || 'Unknown';
        const mcpId = `composio.${appSlug}`;
        
        return {
          name: appName.charAt(0).toUpperCase() + appName.slice(1), // Capitalize first letter
          qualifiedName: mcpId,
          enabled: toggleStates?.[mcpId] !== undefined ? toggleStates[mcpId] : true, // Use saved state or default to true
          isComposio: true,
          customType: 'composio',
          config: {
            profile_id: profile.profile_id,
            profile_name: profile.profile_name,
          },
          selectedProfileId: profile.profile_id,
          toolkit_slug: appSlug,
          toolkitSlug: appSlug, // Add both variations
          app_slug: appSlug,
        };
      });
      allMcps.push(...composioMcps);
    }
    
    // Also get MCPs from agent configuration if available
    if (shouldFetch && agent) {
      const configured = agent.configured_mcps || [];
      const custom = agent.custom_mcps || [];
      
      // Extract other non-Composio MCPs and apply toggle states
      const otherMcps = configured
        .filter((mcp: any) => !(mcp.customType === 'composio' || mcp.isComposio || (mcp.qualifiedName && mcp.qualifiedName.startsWith('composio.'))))
        .concat(custom)
        .map((mcp: any) => ({
          ...mcp,
          enabled: toggleStates?.[mcp.qualifiedName] !== undefined ? toggleStates[mcp.qualifiedName] : mcp.enabled !== undefined ? mcp.enabled : true
        }));
      
      allMcps.push(...otherMcps);
    }
    
    return allMcps;
  }, [shouldFetch, agent, composioProfiles, youtubeChannels, toggleStates]);
  
  return React.useMemo(() => ({
    data: mcpConfigurations,
    isLoading: isVirtualAgent 
      ? (composioLoading || youtubeLoading || togglesLoading)
      : (shouldFetch 
        ? (agentLoading || composioLoading || youtubeLoading || togglesLoading) 
        : (composioLoading || youtubeLoading)),
    error: isVirtualAgent ? null : (shouldFetch ? agentError : null),
  }), [mcpConfigurations, agentLoading, composioLoading, youtubeLoading, togglesLoading, agentError, shouldFetch, isVirtualAgent]);
};