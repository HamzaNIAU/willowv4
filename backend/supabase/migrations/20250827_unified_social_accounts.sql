-- Unified Social Media Account System - Single Source of Truth
-- Applies agent detection principles: Direct, Simple, Consistent

BEGIN;

-- Create unified social accounts table (replaces complex toggle system)
CREATE TABLE IF NOT EXISTS agent_social_accounts (
    agent_id UUID NOT NULL REFERENCES agents(agent_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL CHECK (platform IN ('youtube', 'twitter', 'instagram', 'tiktok', 'linkedin', 'facebook')),
    account_id VARCHAR(255) NOT NULL,
    account_name VARCHAR(255) NOT NULL,
    username VARCHAR(255),
    profile_picture TEXT,
    subscriber_count INTEGER DEFAULT 0,
    view_count BIGINT DEFAULT 0,
    video_count INTEGER DEFAULT 0,
    country VARCHAR(10),
    enabled BOOLEAN DEFAULT true,
    connected_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (agent_id, user_id, platform, account_id),
    UNIQUE(agent_id, platform, account_id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_agent_social_accounts_agent_platform 
    ON agent_social_accounts(agent_id, platform) WHERE enabled = true;

CREATE INDEX IF NOT EXISTS idx_agent_social_accounts_user_platform 
    ON agent_social_accounts(user_id, platform) WHERE enabled = true;

-- Enable Row Level Security
ALTER TABLE agent_social_accounts ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
CREATE POLICY "Users can manage their agent social accounts" 
    ON agent_social_accounts
    FOR ALL USING (auth.uid() = user_id);

-- Migrate existing YouTube MCP toggle data to unified system
INSERT INTO agent_social_accounts (agent_id, user_id, platform, account_id, account_name, username, profile_picture, subscriber_count, view_count, video_count, country, enabled, connected_at)
SELECT 
    t.agent_id,
    t.user_id,
    'youtube' as platform,
    REPLACE(t.mcp_id, 'social.youtube.', '') as account_id,
    c.name as account_name,
    c.username,
    c.profile_picture,
    c.subscriber_count,
    c.view_count,
    c.video_count,
    c.country,
    t.enabled,
    c.created_at as connected_at
FROM agent_mcp_toggles t
JOIN youtube_channels c ON c.id = REPLACE(t.mcp_id, 'social.youtube.', '') AND c.user_id = t.user_id
WHERE t.mcp_id LIKE 'social.youtube.%'
ON CONFLICT (agent_id, user_id, platform, account_id) DO UPDATE SET
    enabled = EXCLUDED.enabled,
    updated_at = NOW();

-- Add function to automatically enable accounts for new agents when channels are connected
CREATE OR REPLACE FUNCTION auto_enable_social_accounts_for_new_agents()
RETURNS TRIGGER AS $$
BEGIN
    -- When a new agent is created, enable all user's connected social media accounts for that agent
    INSERT INTO agent_social_accounts (agent_id, user_id, platform, account_id, account_name, username, profile_picture, subscriber_count, view_count, video_count, country, enabled, connected_at)
    SELECT 
        NEW.agent_id,
        NEW.account_id, -- This is actually user_id in agents table
        'youtube' as platform,
        y.id as account_id,
        y.name as account_name,
        y.username,
        y.profile_picture,
        y.subscriber_count,
        y.view_count,
        y.video_count,
        y.country,
        true as enabled, -- Default to enabled for better UX
        y.created_at as connected_at
    FROM youtube_channels y
    WHERE y.user_id = NEW.account_id AND y.is_active = true
    ON CONFLICT (agent_id, user_id, platform, account_id) DO NOTHING;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-enable social accounts for new agents
DROP TRIGGER IF EXISTS auto_enable_social_accounts_trigger ON agents;
CREATE TRIGGER auto_enable_social_accounts_trigger
    AFTER INSERT ON agents
    FOR EACH ROW
    EXECUTE FUNCTION auto_enable_social_accounts_for_new_agents();

-- Add function to auto-enable for all agents when new channels are connected
CREATE OR REPLACE FUNCTION auto_enable_for_all_agents_on_new_channel()
RETURNS TRIGGER AS $$
BEGIN
    -- When a new YouTube channel is connected, enable it for all user's agents
    INSERT INTO agent_social_accounts (agent_id, user_id, platform, account_id, account_name, username, profile_picture, subscriber_count, view_count, video_count, country, enabled, connected_at)
    SELECT 
        a.agent_id,
        NEW.user_id,
        'youtube' as platform,
        NEW.id as account_id,
        NEW.name as account_name,
        NEW.username,
        NEW.profile_picture,
        NEW.subscriber_count,
        NEW.view_count,
        NEW.video_count,
        NEW.country,
        true as enabled, -- Default to enabled for better UX
        NEW.created_at as connected_at
    FROM agents a
    WHERE a.account_id = NEW.user_id
    ON CONFLICT (agent_id, user_id, platform, account_id) DO UPDATE SET
        account_name = EXCLUDED.account_name,
        username = EXCLUDED.username,
        profile_picture = EXCLUDED.profile_picture,
        subscriber_count = EXCLUDED.subscriber_count,
        view_count = EXCLUDED.view_count,
        video_count = EXCLUDED.video_count,
        country = EXCLUDED.country,
        updated_at = NOW();
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for new channel connections
DROP TRIGGER IF EXISTS auto_enable_new_channels_trigger ON youtube_channels;
CREATE TRIGGER auto_enable_new_channels_trigger
    AFTER INSERT OR UPDATE ON youtube_channels
    FOR EACH ROW
    WHEN (NEW.is_active = true)
    EXECUTE FUNCTION auto_enable_for_all_agents_on_new_channel();

-- Add comments for documentation
COMMENT ON TABLE agent_social_accounts IS 'Unified social media account management - single source of truth for agent account access';
COMMENT ON COLUMN agent_social_accounts.enabled IS 'Whether this social media account is enabled for this specific agent';
COMMENT ON COLUMN agent_social_accounts.platform IS 'Social media platform: youtube, twitter, instagram, tiktok, linkedin, facebook';

COMMIT;