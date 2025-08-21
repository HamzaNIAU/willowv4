-- Create table for storing agent MCP toggle states
CREATE TABLE IF NOT EXISTS agent_mcp_toggles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agents(agent_id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    mcp_id TEXT NOT NULL,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Ensure unique toggle per agent, user, and MCP
    UNIQUE(agent_id, user_id, mcp_id)
);

-- Create indexes for performance
CREATE INDEX idx_agent_mcp_toggles_agent_id ON agent_mcp_toggles(agent_id);
CREATE INDEX idx_agent_mcp_toggles_user_id ON agent_mcp_toggles(user_id);
CREATE INDEX idx_agent_mcp_toggles_mcp_id ON agent_mcp_toggles(mcp_id);
CREATE INDEX idx_agent_mcp_toggles_enabled ON agent_mcp_toggles(enabled);

-- Enable Row Level Security
ALTER TABLE agent_mcp_toggles ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only manage their own toggles
CREATE POLICY "Users can manage their own MCP toggles" ON agent_mcp_toggles
    FOR ALL
    USING (auth.uid() = user_id);

-- RLS Policy: Service role can manage all toggles
CREATE POLICY "Service role can manage all MCP toggles" ON agent_mcp_toggles
    FOR ALL
    USING (auth.jwt()->>'role' = 'service_role');

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_agent_mcp_toggles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically update updated_at
CREATE TRIGGER update_agent_mcp_toggles_updated_at
    BEFORE UPDATE ON agent_mcp_toggles
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_mcp_toggles_updated_at();

-- Grant permissions
GRANT ALL ON agent_mcp_toggles TO authenticated;
GRANT ALL ON agent_mcp_toggles TO service_role;