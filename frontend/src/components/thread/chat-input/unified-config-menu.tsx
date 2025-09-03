'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
    DropdownMenuSeparator,
    DropdownMenuSub,
    DropdownMenuSubContent,
    DropdownMenuSubTrigger,
    DropdownMenuPortal,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Cpu, Search, Check, ChevronDown, Plus, ExternalLink, FileText, BookOpen, Zap, Brain, Database, Youtube } from 'lucide-react';
import { useAgents } from '@/hooks/react-query/agents/use-agents';
import { WillowLogo } from '@/components/sidebar/willow-logo';
import type { ModelOption, SubscriptionStatus } from './_use-model-selection';
import { MODELS } from './_use-model-selection';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { IntegrationsRegistry } from '@/components/agents/integrations-registry';
import { useComposioToolkitIcon } from '@/hooks/react-query/composio/use-composio';
import { Skeleton } from '@/components/ui/skeleton';
import { NewAgentDialog } from '@/components/agents/new-agent-dialog';
import { useAgentWorkflows } from '@/hooks/react-query/agents/use-agent-workflows';
import { PlaybookExecuteDialog } from '@/components/playbooks/playbook-execute-dialog';
import { AgentAvatar } from '@/components/thread/content/agent-avatar';
import { AgentModelSelector } from '@/components/agents/config/model-selector';
import { useFeatureFlag } from '@/lib/feature-flags';
import { useRouter } from 'next/navigation';
import { useAgentMcpConfigurations, useUpdateAgentMcpToggle } from '@/hooks/react-query/agents/use-agent-mcp-toggle';
import { Switch } from '@/components/ui/switch';

type UnifiedConfigMenuProps = {
    isLoggedIn?: boolean;

    // Agent
    selectedAgentId?: string;
    onAgentSelect?: (agentId: string | undefined) => void;

    // Model
    selectedModel: string;
    onModelChange: (modelId: string) => void;
    modelOptions: ModelOption[];
    subscriptionStatus: SubscriptionStatus;
    canAccessModel: (modelId: string) => boolean;
    refreshCustomModels?: () => void;
    onUpgradeRequest?: () => void;
};

const LoggedInMenu: React.FC<UnifiedConfigMenuProps> = ({
    isLoggedIn = true,
    selectedAgentId,
    onAgentSelect,
    selectedModel,
    onModelChange,
    modelOptions,
    canAccessModel,
    subscriptionStatus,
    onUpgradeRequest,
}) => {
    const [isOpen, setIsOpen] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const searchContainerRef = useRef<HTMLDivElement>(null);
    const [integrationsOpen, setIntegrationsOpen] = useState(false);
    const [showNewAgentDialog, setShowNewAgentDialog] = useState(false);
    const searchInputRef = useRef<HTMLInputElement>(null);
    const [execDialog, setExecDialog] = useState<{ open: boolean; playbook: any | null; agentId: string | null }>({ open: false, playbook: null, agentId: null });
    const router = useRouter();
    
    // YouTube toggle functionality
    const { data: mcpConfigurations = [], isLoading: mcpLoading } = useAgentMcpConfigurations(selectedAgentId);
    const updateMcpToggle = useUpdateAgentMcpToggle();
    const [localToggles, setLocalToggles] = useState<Record<string, boolean>>({});

    const { data: agentsResponse } = useAgents({}, { enabled: isLoggedIn });
    const agents: any[] = agentsResponse?.agents || [];
    const { enabled: hideAgentCreation } = useFeatureFlag('hide_agent_creation');
    const { enabled: customAgentsEnabled } = useFeatureFlag('custom_agents');



    // Only fetch integration icons when authenticated AND the menu is open
    const iconsEnabled = isLoggedIn && isOpen;
    const { data: googleDriveIcon } = useComposioToolkitIcon('googledrive', { enabled: iconsEnabled });
    const { data: slackIcon } = useComposioToolkitIcon('slack', { enabled: iconsEnabled });
    const { data: notionIcon } = useComposioToolkitIcon('notion', { enabled: iconsEnabled });

    useEffect(() => {
        if (isOpen) {
            setTimeout(() => searchInputRef.current?.focus(), 30);
        } else {
            setSearchQuery('');
        }
    }, [isOpen]);



    // Keep focus stable even when list size changes
    useEffect(() => {
        if (isOpen) searchInputRef.current?.focus();
    }, [searchQuery, isOpen]);

    const handleSearchInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        // Prevent Radix dropdown from stealing focus/navigation
        e.stopPropagation();
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
        }
    };

    // Filtered agents with selected first
    const filteredAgents = useMemo(() => {
        let list = [...agents];
        
        // When custom agents disabled, create virtual Willow agent
        if (!customAgentsEnabled) {
            list = [{
                agent_id: 'suna-default',
                name: 'Suna',
                description: 'Default AI assistant',
                metadata: { is_suna_default: true }
            }];
        }
        
        const selected = selectedAgentId ? list.find(a => a.agent_id === selectedAgentId) : undefined;
        const rest = selected ? list.filter(a => a.agent_id !== selectedAgentId) : list;
        const ordered = selected ? [selected, ...rest] : rest;
        return ordered.filter(a => (
            a?.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            a?.description?.toLowerCase().includes(searchQuery.toLowerCase())
        ));
    }, [agents, selectedAgentId, searchQuery, customAgentsEnabled]);

    // Top 3 slice
    const topAgents = useMemo(() => filteredAgents.slice(0, 3), [filteredAgents]);





    const handleAgentClick = (agentId: string | undefined) => {
        onAgentSelect?.(agentId);
        setIsOpen(false);
    };



    const renderAgentIcon = (agent: any) => {
        return <AgentAvatar agentId={agent?.agent_id} size={16} className="h-4 w-4" fallbackName={agent?.name} />;
    };

    const displayAgent = useMemo(() => {
        // When custom agents disabled, create virtual Willow agent
        if (!customAgentsEnabled) {
            return {
                agent_id: 'suna-default',
                name: 'Willow',
                description: 'Default AI assistant',
                metadata: { is_suna_default: true }
            };
        }
        
        const found = agents.find(a => a.agent_id === selectedAgentId) || agents[0];
        return found;
    }, [agents, selectedAgentId, customAgentsEnabled]);

    const currentAgentIdForPlaybooks = isLoggedIn ? displayAgent?.agent_id || '' : '';
    const { data: playbooks = [], isLoading: playbooksLoading } = useAgentWorkflows(currentAgentIdForPlaybooks);
    const [playbooksExpanded, setPlaybooksExpanded] = useState(true);
    
    // Initialize local toggles from MCP configurations
    React.useEffect(() => {
        const initialToggles: Record<string, boolean> = {};
        mcpConfigurations.forEach((mcp: any) => {
            const mcpId = mcp.qualifiedName || mcp.mcp_qualified_name || `${mcp.name}`;
            initialToggles[mcpId] = mcp.enabled !== false;
        });
        setLocalToggles(initialToggles);
    }, [mcpConfigurations]);
    
    // Handle YouTube channel toggle
    const handleYouTubeToggle = React.useCallback(async (mcpId: string) => {
        // Update local state immediately for responsive UI
        const currentEnabled = localToggles[mcpId] ?? true;
        const newEnabled = !currentEnabled;
        
        setLocalToggles(prev => ({
            ...prev,
            [mcpId]: newEnabled
        }));

        // Persist the change if agent is selected
        if (selectedAgentId) {
            try {
                await updateMcpToggle.mutateAsync({
                    agentId: selectedAgentId,
                    mcpId,
                    enabled: newEnabled,
                });
            } catch (error) {
                // Revert on error
                setLocalToggles(prev => ({
                    ...prev,
                    [mcpId]: currentEnabled
                }));
            }
        }
    }, [selectedAgentId, updateMcpToggle, localToggles]);
    
    // Filter YouTube channels from MCP configurations
    const youtubeChannels = React.useMemo(() => {
        return mcpConfigurations.filter((mcp: any) => 
            mcp.platform === 'youtube' && mcp.isSocialMedia
        );
    }, [mcpConfigurations]);

    return (
        <>
            {/* Reusable list of workflows to avoid re-fetch storms; each instance fetches scoped to agentId */}

            <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
                <DropdownMenuTrigger asChild>
                    <Button
                        variant="outline"
                        size="sm"
                        className="h-8 px-3 py-2 bg-transparent border border-border rounded-xl text-muted-foreground hover:text-foreground hover:bg-accent/50 flex items-center gap-1.5"
                        aria-label="Config menu"
                    >
                        {onAgentSelect ? (
                            <div className="flex items-center gap-2 max-w-[140px]">
                                <div className="flex-shrink-0">
                                    {renderAgentIcon(displayAgent)}
                                </div>
                                <span className="truncate text-sm">
                                    {displayAgent?.name || 'Suna'}
                                </span>
                            </div>
                        ) : (
                            <div className="flex items-center gap-1.5">
                                <Cpu className="h-4 w-4" />
                                <ChevronDown size={12} className="opacity-60" />
                            </div>
                        )}
                    </Button>
                </DropdownMenuTrigger>

                <DropdownMenuContent align="end" className="w-80 p-0" sideOffset={6}>
                    <div className="p-2" ref={searchContainerRef}>
                        <div className="relative">
                            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                            <input
                                ref={searchInputRef}
                                type="text"
                                placeholder="Search..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                onKeyDown={handleSearchInputKeyDown}
                                className="w-full h-8 pl-8 pr-2 rounded-lg text-sm bg-muted focus:outline-none"
                            />
                        </div>
                    </div>

                    {/* Agents */}
                    {onAgentSelect && (
                        <div className="px-1.5">
                            <div className="px-3 py-1 text-[11px] font-medium text-muted-foreground flex items-center justify-between">
                                <span>Agents</span>
                                {!hideAgentCreation && (
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground"
                                        onClick={() => { setIsOpen(false); setShowNewAgentDialog(true); }}
                                    >
                                        <Plus className="h-3.5 w-3.5" />
                                    </Button>
                                )}
                            </div>
                            {topAgents.length === 0 ? (
                                <div className="px-3 py-2 text-xs text-muted-foreground">No agents</div>
                            ) : (
                                <DropdownMenuSub>
                                    <DropdownMenuSubTrigger className="text-sm px-3 py-2 mx-0 my-0.5 flex items-center cursor-pointer rounded-lg">
                                        <div className="flex items-center gap-2 min-w-0">
                                            {renderAgentIcon(displayAgent)}
                                            <span className="truncate">{displayAgent?.name || 'Suna'}</span>
                                        </div>
                                    </DropdownMenuSubTrigger>
                                    <DropdownMenuPortal>
                                        <DropdownMenuSubContent className="w-64 rounded-xl">
                                            {/* Playbooks */}
                                            <DropdownMenuSub>
                                                <DropdownMenuSubTrigger className="px-3 py-2 text-sm cursor-pointer rounded-lg flex items-center gap-2">
                                                    <BookOpen className="h-4 w-4" />
                                                    <span>Playbooks</span>
                                                </DropdownMenuSubTrigger>
                                                <DropdownMenuPortal>
                                                    <DropdownMenuSubContent className="w-72 rounded-xl max-h-80 overflow-y-auto">
                                                        {/* Manage Playbooks Link */}
                                                        <DropdownMenuItem
                                                            className="text-sm px-3 py-2 mx-0 my-0.5 flex items-center gap-2 cursor-pointer rounded-lg border-b border-border/50 mb-1"
                                                            onClick={() => {
                                                                setIsOpen(false);
                                                                router.push(`/agents/config/suna-default?tab=configuration&accordion=workflows`);
                                                            }}
                                                        >
                                                            <BookOpen className="h-4 w-4" />
                                                            <span className="font-medium">Manage Playbooks</span>
                                                        </DropdownMenuItem>
                                                        
                                                        {/* Individual Playbooks */}
                                                        {playbooksLoading ? (
                                                            <div className="px-3 py-2 text-xs text-muted-foreground">Loading…</div>
                                                        ) : playbooks && playbooks.length > 0 ? (
                                                            playbooks.map((wf: any) => (
                                                                <DropdownMenuItem
                                                                    key={`pb-${wf.id}`}
                                                                    className="text-sm px-3 py-2 mx-0 my-0.5 flex items-center justify-between cursor-pointer rounded-lg"
                                                                    onClick={(e) => { e.stopPropagation(); setExecDialog({ open: true, playbook: wf, agentId: currentAgentIdForPlaybooks }); setIsOpen(false); }}
                                                                >
                                                                    <span className="truncate">{wf.name}</span>
                                                                </DropdownMenuItem>
                                                            ))
                                                        ) : (
                                                            <div className="px-3 py-2 text-xs text-muted-foreground">No playbooks</div>
                                                        )}
                                                    </DropdownMenuSubContent>
                                                </DropdownMenuPortal>
                                            </DropdownMenuSub>
                                            
                                            {/* Instructions */}
                                            <DropdownMenuItem 
                                                className="px-3 py-2 text-sm cursor-pointer rounded-lg flex items-center gap-2"
                                                onClick={() => {
                                                    setIsOpen(false);
                                                    router.push(`/agents/config/suna-default?tab=configuration&accordion=instructions`);
                                                }}
                                            >
                                                <FileText className="h-4 w-4" />
                                                <span>Instructions</span>
                                            </DropdownMenuItem>
                                            
                                            {/* Knowledge */}
                                            <DropdownMenuItem 
                                                className="px-3 py-2 text-sm cursor-pointer rounded-lg flex items-center gap-2"
                                                onClick={() => {
                                                    setIsOpen(false);
                                                    router.push(`/agents/config/suna-default?tab=configuration&accordion=knowledge`);
                                                }}
                                            >
                                                <Database className="h-4 w-4" />
                                                <span>Knowledge</span>
                                            </DropdownMenuItem>
                                            
                                            {/* Triggers */}
                                            <DropdownMenuItem 
                                                className="px-3 py-2 text-sm cursor-pointer rounded-lg flex items-center gap-2"
                                                onClick={() => {
                                                    setIsOpen(false);
                                                    router.push(`/agents/config/suna-default?tab=configuration&accordion=triggers`);
                                                }}
                                            >
                                                <Zap className="h-4 w-4" />
                                                <span>Triggers</span>
                                            </DropdownMenuItem>
                                        </DropdownMenuSubContent>
                                    </DropdownMenuPortal>
                                </DropdownMenuSub>
                            )}

                            {/* Agents "see all" removed; scroll container shows all */}
                            {/* Playbooks moved below (as hover submenu) */}
                        </div>
                    )}

                    {onAgentSelect && <DropdownMenuSeparator className="!mt-0" />}

                    {/* Models */}
                    <div className="px-1.5">
                        <div className="px-3 py-1 text-[11px] font-medium text-muted-foreground">Models</div>
                        <AgentModelSelector
                            value={selectedModel}
                            onChange={onModelChange}
                            disabled={false}
                            variant="menu-item"
                        />
                    </div>

                    <DropdownMenuSeparator />

                    {/* Social Media */}
                    <div className="px-1.5">
                        <div className="px-3 py-1 text-[11px] font-medium text-muted-foreground">Social Media</div>
                        <DropdownMenuSub>
                            <DropdownMenuSubTrigger className="flex items-center gap-2 px-3 py-2 mx-0 my-0.5 text-sm cursor-pointer rounded-lg">
                                <img 
                                    src="/platforms/youtube.svg" 
                                    alt="YouTube"
                                    className="h-4 w-4"
                                />
                                <span>YouTube</span>
                                {youtubeChannels.length > 0 && (
                                    <span className="ml-auto text-xs text-muted-foreground">
                                        {youtubeChannels.filter(ch => localToggles[ch.qualifiedName] !== false).length}
                                    </span>
                                )}
                            </DropdownMenuSubTrigger>
                            <DropdownMenuPortal>
                                <DropdownMenuSubContent className="w-72 rounded-xl max-h-80 overflow-y-auto">
                                    {youtubeChannels.length === 0 ? (
                                        <div className="px-3 py-4 text-center">
                                            <div className="text-sm text-muted-foreground mb-2">No YouTube channels connected</div>
                                            <Button
                                                size="sm"
                                                onClick={() => {
                                                    setIsOpen(false);
                                                    router.push('/social-media');
                                                }}
                                                className="text-xs"
                                            >
                                                Connect YouTube Channel
                                            </Button>
                                        </div>
                                    ) : (
                                        <>
                                            <div className="px-3 py-2 border-b border-border/50">
                                                <div className="text-xs font-medium text-muted-foreground mb-1">Connected Channels</div>
                                                <div className="text-xs text-muted-foreground">
                                                    Toggle channels on/off for this agent
                                                </div>
                                            </div>
                                            {youtubeChannels.map((channel: any) => {
                                                const mcpId = channel.qualifiedName;
                                                const isEnabled = localToggles[mcpId] ?? (channel.enabled !== false);
                                                const profilePicture = channel.profile_picture || channel.config?.profile_picture;
                                                
                                                return (
                                                    <div
                                                        key={mcpId}
                                                        className="flex items-center justify-between px-3 py-2 hover:bg-accent/50"
                                                    >
                                                        <div className="flex items-center gap-2 min-w-0">
                                                            {profilePicture ? (
                                                                <img
                                                                    src={profilePicture}
                                                                    alt={channel.name}
                                                                    className="h-5 w-5 rounded-full object-cover border border-border/50"
                                                                />
                                                            ) : (
                                                                <img 
                                                                  src="/platforms/youtube.svg" 
                                                                  alt="YouTube"
                                                                  className="h-5 w-5"
                                                                />
                                                            )}
                                                            <span className="text-sm truncate">{channel.name}</span>
                                                        </div>
                                                        <Switch
                                                            checked={isEnabled}
                                                            onCheckedChange={() => handleYouTubeToggle(mcpId)}
                                                            className="scale-90"
                                                        />
                                                    </div>
                                                );
                                            })}
                                            <div className="px-3 py-2 border-t border-border/50">
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    onClick={() => {
                                                        setIsOpen(false);
                                                        router.push('/social-media');
                                                    }}
                                                    className="w-full text-xs justify-center"
                                                >
                                                    Manage YouTube Accounts
                                                </Button>
                                            </div>
                                        </>
                                    )}
                                </DropdownMenuSubContent>
                            </DropdownMenuPortal>
                        </DropdownMenuSub>
                    </div>

                    <DropdownMenuSeparator />

                    {/* Quick Integrations */}
                    {(
                        <div className="px-1.5 pb-1.5">
                            <TooltipProvider>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <DropdownMenuItem
                                            className="text-sm px-3 py-2 mx-0 my-0.5 flex items-center justify-between cursor-pointer rounded-lg"
                                            onClick={() => setIntegrationsOpen(true)}
                                        >
                                            <span className="font-medium">Integrations</span>
                                            <div className="flex items-center gap-1.5">
                                                {googleDriveIcon?.icon_url && slackIcon?.icon_url && notionIcon?.icon_url ? (
                                                    <>
                                                        {/* eslint-disable-next-line @next/next/no-img-element */}
                                                        <img src={googleDriveIcon.icon_url} className="w-4 h-4" alt="Google Drive" />
                                                        {/* eslint-disable-next-line @next/next/no-img-element */}
                                                        <img src={slackIcon.icon_url} className="w-3.5 h-3.5" alt="Slack" />
                                                        {/* eslint-disable-next-line @next/next/no-img-element */}
                                                        <img src={notionIcon.icon_url} className="w-3.5 h-3.5" alt="Notion" />
                                                    </>
                                                ) : (
                                                    <>
                                                        <Skeleton className="w-4 h-4 rounded" />
                                                        <Skeleton className="w-3.5 h-3.5 rounded" />
                                                        <Skeleton className="w-3.5 h-3.5 rounded" />
                                                    </>
                                                )}
                                                <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
                                            </div>
                                        </DropdownMenuItem>
                                    </TooltipTrigger>
                                    <TooltipContent side="left" className="text-xs max-w-xs">
                                        <p>Open integrations</p>
                                    </TooltipContent>
                                </Tooltip>
                            </TooltipProvider>
                        </div>
                    )}
                </DropdownMenuContent>
            </DropdownMenu>

            {/* Integrations manager */}
            <Dialog open={integrationsOpen} onOpenChange={setIntegrationsOpen}>
                <DialogContent className="p-0 max-w-6xl h-[90vh] overflow-hidden">
                    <DialogHeader className="sr-only">
                        <DialogTitle>Integrations</DialogTitle>
                    </DialogHeader>
                    <IntegrationsRegistry
                        showAgentSelector={true}
                        selectedAgentId={selectedAgentId}
                        onAgentChange={onAgentSelect}
                        onClose={() => setIntegrationsOpen(false)}
                    />
                </DialogContent>
            </Dialog>

            {/* Create Agent - Only show when agent creation is not hidden */}
            {!hideAgentCreation && (
                <NewAgentDialog open={showNewAgentDialog} onOpenChange={setShowNewAgentDialog} />
            )}

            {/* Execute Playbook */}
            <PlaybookExecuteDialog
                open={execDialog.open}
                onOpenChange={(open) => setExecDialog((s) => ({ ...s, open }))}
                playbook={execDialog.playbook as any}
                agentId={execDialog.agentId || ''}
            />


        </>
    );
};

const GuestMenu: React.FC<UnifiedConfigMenuProps> = () => {
    return (
        <TooltipProvider>
            <Tooltip>
                <TooltipTrigger asChild>
                    <span className="inline-flex">
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-8 px-3 py-2 bg-transparent border border-border rounded-xl text-muted-foreground hover:text-foreground hover:bg-accent/50 flex items-center gap-1.5 cursor-not-allowed opacity-80 pointer-events-none"
                            disabled
                        >
                            <div className="flex items-center gap-2 max-w-[160px]">
                                <div className="flex-shrink-0">
                                    <WillowLogo size={16} />
                                </div>
                                <span className="truncate text-sm">Willow</span>
                            </div>
                        </Button>
                    </span>
                </TooltipTrigger>
                <TooltipContent side="top" className="text-xs">
                    <p>Log in to change agent</p>
                </TooltipContent>
            </Tooltip>
        </TooltipProvider>
    );
};

export const UnifiedConfigMenu: React.FC<UnifiedConfigMenuProps> = (props) => {
    if (props.isLoggedIn) {
        return <LoggedInMenu {...props} />;
    }
    return <GuestMenu {...props} />;
};

export default UnifiedConfigMenu;


