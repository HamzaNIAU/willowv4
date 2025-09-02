'use client';

import React from 'react';
import { useAgent } from '@/hooks/react-query/agents/use-agents';
import { WillowLogo } from '@/components/sidebar/willow-logo';
import { Skeleton } from '@/components/ui/skeleton';
import { useFeatureFlag } from '@/lib/feature-flags';

interface AgentAvatarProps {
  agentId?: string;
  size?: number;
  className?: string;
  fallbackName?: string;
}

export const AgentAvatar: React.FC<AgentAvatarProps> = ({ 
  agentId, 
  size = 16, 
  className = "", 
  fallbackName = "Willow" 
}) => {
  const { enabled: customAgentsEnabled } = useFeatureFlag('custom_agents');
  
  // Skip fetching if agentId is invalid
  const shouldFetchAgent = agentId && (
    agentId === 'suna-default' || 
    customAgentsEnabled
  );
  
  const { data: agent, isLoading } = useAgent(shouldFetchAgent ? agentId : '');

  if (isLoading && agentId) {
    return (
      <div 
        className={`bg-muted animate-pulse rounded ${className}`}
        style={{ width: size, height: size }}
      />
    );
  }

  if (!agent && !agentId) {
    return <WillowLogo size={size} />;
  }

  const isSuna = agent?.metadata?.is_suna_default;
  if (isSuna) {
    return <WillowLogo size={size} />;
  }

  if (agent?.profile_image_url) {
    return (
      <img 
        src={agent.profile_image_url} 
        alt={agent.name || fallbackName}
        className={`rounded object-cover ${className}`}
        style={{ width: size, height: size }}
      />
    );
  }


  return <WillowLogo size={size} />;
};

interface AgentNameProps {
  agentId?: string;
  fallback?: string;
}

export const AgentName: React.FC<AgentNameProps> = ({ 
  agentId, 
  fallback = "Willow" 
}) => {
  const { enabled: customAgentsEnabled } = useFeatureFlag('custom_agents');
  
  // Skip fetching if agentId is invalid
  const shouldFetchAgent = agentId && (
    agentId === 'suna-default' || 
    customAgentsEnabled
  );
  
  const { data: agent, isLoading } = useAgent(shouldFetchAgent ? agentId : '');

  if (isLoading && agentId) {
    return <span className="text-muted-foreground">Loading...</span>;
  }

  return <span>{agent?.name || fallback}</span>;
}; 