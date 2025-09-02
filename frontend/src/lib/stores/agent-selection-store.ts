import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface Agent {
  agent_id: string;
  name: string;
  avatar?: string;
  metadata?: {
    is_suna_default?: boolean;
  };
}

interface AgentSelectionState {
  selectedAgentId: string | undefined;
  hasInitialized: boolean;
  
  setSelectedAgent: (agentId: string | undefined) => void;
  initializeFromAgents: (agents: Agent[], threadAgentId?: string, onAgentSelect?: (agentId: string | undefined) => void) => void;
  autoSelectAgent: (agents: Agent[], onAgentSelect?: (agentId: string | undefined) => void, currentSelectedAgentId?: string) => void;
  clearSelection: () => void;
  resetToDefault: () => void;
  
  getCurrentAgent: (agents: Agent[]) => Agent | null;
  isSunaAgent: (agents: Agent[]) => boolean;
}

export const useAgentSelectionStore = create<AgentSelectionState>()(
  persist(
    (set, get) => ({
      selectedAgentId: undefined,
      hasInitialized: false,

      setSelectedAgent: (agentId: string | undefined) => {
        set({ selectedAgentId: agentId });
      },

      initializeFromAgents: (agents: Agent[], threadAgentId?: string, onAgentSelect?: (agentId: string | undefined) => void) => {
        if (get().hasInitialized) {
          return;
        }

        let selectedId: string | undefined;

        // Check thread agent ID first
        if (threadAgentId && agents.some(a => a.agent_id === threadAgentId)) {
          selectedId = threadAgentId;
        } else if (typeof window !== 'undefined') {
          // Check URL parameter
          const urlParams = new URLSearchParams(window.location.search);
          const agentIdFromUrl = urlParams.get('agent_id');
          if (agentIdFromUrl && agents.some(a => a.agent_id === agentIdFromUrl)) {
            selectedId = agentIdFromUrl;
          }
        }

        // If no valid ID found yet, check persisted selection
        if (!selectedId) {
          const current = get().selectedAgentId;
          
          if (current && agents.some(a => a.agent_id === current)) {
            selectedId = current;
          }
        }

        // If still no valid ID, select default
        if (!selectedId && agents.length > 0) {
          const defaultSunaAgent = agents.find(agent => agent.metadata?.is_suna_default);
          selectedId = defaultSunaAgent ? defaultSunaAgent.agent_id : agents[0].agent_id;
        }

        // Only set selectedId if it's valid
        if (selectedId && agents.some(a => a.agent_id === selectedId)) {
          set({ selectedAgentId: selectedId });
          if (onAgentSelect) {
            onAgentSelect(selectedId);
          }
        } else {
          // Clear invalid selection
          set({ selectedAgentId: undefined });
          if (onAgentSelect) {
            onAgentSelect(undefined);
          }
        }

        set({ hasInitialized: true });
      },

      autoSelectAgent: (agents: Agent[], onAgentSelect?: (agentId: string | undefined) => void, currentSelectedAgentId?: string) => {
        if (agents.length === 0 || currentSelectedAgentId) {
          return;
        }
        const defaultSunaAgent = agents.find(agent => agent.metadata?.is_suna_default);
        const agentToSelect = defaultSunaAgent || agents[0];
        
        if (agentToSelect) {
          if (onAgentSelect) {
            onAgentSelect(agentToSelect.agent_id);
          } else {
            set({ selectedAgentId: agentToSelect.agent_id });
          }
        }
      },

      clearSelection: () => {
        set({ selectedAgentId: undefined, hasInitialized: false });
      },

      resetToDefault: () => {
        set({ selectedAgentId: 'suna-default' });
      },

      getCurrentAgent: (agents: Agent[]) => {
        const { selectedAgentId } = get();
        return selectedAgentId 
          ? agents.find(agent => agent.agent_id === selectedAgentId) || null
          : null;
      },

      isSunaAgent: (agents: Agent[]) => {
        const { selectedAgentId } = get();
        const currentAgent = selectedAgentId 
          ? agents.find(agent => agent.agent_id === selectedAgentId)
          : null;
        return currentAgent?.metadata?.is_suna_default || selectedAgentId === undefined;
      },
    }),
    {
      name: 'agent-selection-storage',
      partialize: (state) => ({ 
        selectedAgentId: state.selectedAgentId 
      }),
    }
  )
);

export const useAgentSelection = () => {
  const store = useAgentSelectionStore();
  
  return {
    selectedAgentId: store.selectedAgentId,
    hasInitialized: store.hasInitialized,
    setSelectedAgent: store.setSelectedAgent,
    initializeFromAgents: store.initializeFromAgents,
    autoSelectAgent: store.autoSelectAgent,
    clearSelection: store.clearSelection,
    resetToDefault: store.resetToDefault,
    getCurrentAgent: store.getCurrentAgent,
    isSunaAgent: store.isSunaAgent,
  };
}; 