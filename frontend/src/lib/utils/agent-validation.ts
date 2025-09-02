/**
 * Validates if a string is a valid UUID v4
 */
export function isValidUUID(id: string): boolean {
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  return uuidRegex.test(id);
}

/**
 * Checks if an agent ID is valid (either a UUID or special case like 'suna-default')
 */
export function isValidAgentId(agentId: string | undefined | null): boolean {
  if (!agentId) return false;
  
  // Special cases
  if (agentId === 'suna-default') return true;
  
  // Check if it's a valid UUID
  return isValidUUID(agentId);
}

/**
 * Validates an agent ID considering feature flags
 */
export function shouldFetchAgent(
  agentId: string | undefined | null, 
  customAgentsEnabled: boolean
): boolean {
  if (!agentId) return false;
  
  // Always allow suna-default
  if (agentId === 'suna-default') return true;
  
  // Only allow other agents if custom agents are enabled
  return customAgentsEnabled && isValidUUID(agentId);
}