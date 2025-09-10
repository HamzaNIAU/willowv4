-- =====================================================
-- UNIFIED INTEGRATIONS MIGRATION - POSTIZ STYLE
-- =====================================================
-- This migration consolidates ALL social media platforms into a single 
-- unified integrations table based on Postiz's proven architecture
-- =====================================================

-- Create the new unified integrations table (based on Postiz Integration model)
CREATE TABLE integrations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Core identification
    internal_id VARCHAR(255) NOT NULL, -- Kortix internal identifier  
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Account information
    name VARCHAR(255) NOT NULL, -- Display name (e.g., "My YouTube Channel")
    picture TEXT, -- Profile picture URL
    platform_account_id VARCHAR(255) NOT NULL, -- Platform's internal ID (e.g., "UCxxxxx" for YouTube)
    platform VARCHAR(50) NOT NULL CHECK (platform IN (
        'youtube', 'pinterest', 'twitter', 'instagram', 'linkedin', 
        'tiktok', 'facebook', 'threads', 'mastodon', 'discord'
    )),
    
    -- OAuth tokens
    access_token TEXT NOT NULL, -- Encrypted access token
    refresh_token TEXT, -- Encrypted refresh token  
    token_expires_at TIMESTAMP WITH TIME ZONE,
    token_scopes TEXT, -- OAuth scopes as comma-separated string
    
    -- Platform-specific data (the magic sauce from Postiz)
    platform_data JSONB DEFAULT '{}', -- ALL platform-specific fields go here
    additional_settings JSONB DEFAULT '[]', -- Platform-specific settings
    
    -- Status and control
    disabled BOOLEAN DEFAULT FALSE,
    refresh_needed BOOLEAN DEFAULT FALSE,
    in_between_steps BOOLEAN DEFAULT FALSE, -- For multi-step OAuth flows
    
    -- Posting configuration
    posting_times JSONB DEFAULT '[{"time":120}, {"time":400}, {"time":700}]',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE,
    
    -- Constraints
    UNIQUE(user_id, platform, platform_account_id),
    UNIQUE(user_id, internal_id)
);

-- Indexes for performance (based on Postiz patterns)
CREATE INDEX idx_integrations_user_id ON integrations(user_id);
CREATE INDEX idx_integrations_platform ON integrations(platform);
CREATE INDEX idx_integrations_platform_account_id ON integrations(platform_account_id);
CREATE INDEX idx_integrations_disabled ON integrations(disabled);
CREATE INDEX idx_integrations_refresh_needed ON integrations(refresh_needed);
CREATE INDEX idx_integrations_deleted_at ON integrations(deleted_at);
CREATE INDEX idx_integrations_created_at ON integrations(created_at);
CREATE INDEX idx_integrations_updated_at ON integrations(updated_at);

-- Agent-specific integration permissions (replaces agent_social_accounts)
CREATE TABLE agent_integrations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    integration_id UUID NOT NULL REFERENCES integrations(id) ON DELETE CASCADE,
    
    -- Permission settings
    enabled BOOLEAN DEFAULT TRUE,
    
    -- Cached data for performance (updated periodically)
    cached_name VARCHAR(255),
    cached_picture TEXT,
    cached_stats JSONB DEFAULT '{}', -- Platform-specific stats
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(agent_id, user_id, integration_id)
);

-- Indexes for agent_integrations
CREATE INDEX idx_agent_integrations_agent_id ON agent_integrations(agent_id);
CREATE INDEX idx_agent_integrations_user_id ON agent_integrations(user_id);
CREATE INDEX idx_agent_integrations_integration_id ON agent_integrations(integration_id);
CREATE INDEX idx_agent_integrations_enabled ON agent_integrations(enabled);

-- Row Level Security policies
ALTER TABLE integrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_integrations ENABLE ROW LEVEL SECURITY;

-- RLS Policies for integrations
CREATE POLICY "Users can manage their own integrations" ON integrations
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY "Service role can manage all integrations" ON integrations
    FOR ALL USING (auth.role() = 'service_role');

-- RLS Policies for agent_integrations  
CREATE POLICY "Users can manage their own agent integrations" ON agent_integrations
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY "Service role can manage all agent integrations" ON agent_integrations
    FOR ALL USING (auth.role() = 'service_role');

-- =====================================================
-- DATA MIGRATION SECTION
-- =====================================================

-- Function to generate internal_id
CREATE OR REPLACE FUNCTION generate_internal_id(platform_val TEXT, account_id TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN platform_val || '_' || SUBSTRING(account_id, 1, 20) || '_' || EXTRACT(EPOCH FROM NOW())::TEXT;
END;
$$ LANGUAGE plpgsql;

-- Migrate YouTube channels
INSERT INTO integrations (
    internal_id,
    user_id, 
    name,
    picture,
    platform_account_id,
    platform,
    access_token,
    refresh_token,
    token_expires_at,
    platform_data,
    disabled,
    created_at,
    updated_at
)
SELECT 
    generate_internal_id('youtube', id) as internal_id,
    user_id,
    name,
    profile_picture as picture,
    id as platform_account_id,
    'youtube' as platform,
    access_token,
    refresh_token, 
    expires_at as token_expires_at,
    jsonb_build_object(
        'channel_id', id,
        'username', username,
        'custom_url', custom_url,
        'description', description,
        'subscriber_count', subscriber_count,
        'view_count', view_count,
        'video_count', video_count,
        'country', country,
        'published_at', published_at,
        'profile_pictures', jsonb_build_object(
            'default', profile_picture,
            'medium', profile_picture_medium,
            'small', profile_picture_small
        )
    ) as platform_data,
    NOT is_active as disabled,
    created_at,
    updated_at
FROM youtube_channels
WHERE deleted_at IS NULL;

-- Migrate Pinterest accounts (if they exist in social_media_accounts)
INSERT INTO integrations (
    internal_id,
    user_id,
    name, 
    picture,
    platform_account_id,
    platform,
    access_token,
    refresh_token,
    token_expires_at,
    platform_data,
    disabled,
    created_at,
    updated_at
)
SELECT
    generate_internal_id('pinterest', platform_account_id) as internal_id,
    user_id,
    account_name as name,
    profile_image_url as picture,
    platform_account_id,
    platform,
    access_token,
    refresh_token,
    token_expires_at,
    jsonb_build_object(
        'account_id', platform_account_id,
        'username', username,
        'bio', bio,
        'website_url', website_url,
        'follower_count', follower_count,
        'following_count', following_count,
        'post_count', post_count,
        'board_count', platform_data->>'board_count',
        'pin_count', platform_data->>'pin_count'
    ) as platform_data,
    NOT is_active as disabled,
    created_at,
    updated_at
FROM social_media_accounts
WHERE platform = 'pinterest';

-- Migrate Twitter accounts (if they exist in platform-specific tables or social_media_accounts)
INSERT INTO integrations (
    internal_id,
    user_id,
    name,
    picture, 
    platform_account_id,
    platform,
    access_token,
    refresh_token,
    token_expires_at,
    platform_data,
    disabled,
    created_at,
    updated_at
)
SELECT
    generate_internal_id('twitter', platform_account_id) as internal_id,
    user_id,
    account_name as name,
    profile_image_url as picture,
    platform_account_id,
    platform,
    access_token,
    refresh_token,
    token_expires_at,
    jsonb_build_object(
        'account_id', platform_account_id,
        'username', username,
        'bio', bio,
        'follower_count', follower_count,
        'following_count', following_count,
        'post_count', post_count,
        'verified', platform_data->>'verified',
        'location', platform_data->>'location'
    ) as platform_data,
    NOT is_active as disabled,
    created_at,
    updated_at
FROM social_media_accounts
WHERE platform = 'twitter';

-- Migrate Instagram accounts
INSERT INTO integrations (
    internal_id,
    user_id,
    name,
    picture,
    platform_account_id, 
    platform,
    access_token,
    refresh_token,
    token_expires_at,
    platform_data,
    disabled,
    created_at,
    updated_at
)
SELECT
    generate_internal_id('instagram', platform_account_id) as internal_id,
    user_id,
    account_name as name,
    profile_image_url as picture,
    platform_account_id,
    platform,
    access_token,
    refresh_token,
    token_expires_at,
    jsonb_build_object(
        'account_id', platform_account_id,
        'username', username,
        'bio', bio,
        'website_url', website_url,
        'follower_count', follower_count,
        'following_count', following_count,
        'media_count', post_count,
        'account_type', platform_data->>'account_type'
    ) as platform_data,
    NOT is_active as disabled,
    created_at,
    updated_at  
FROM social_media_accounts
WHERE platform = 'instagram';

-- Migrate LinkedIn accounts  
INSERT INTO integrations (
    internal_id,
    user_id,
    name,
    picture,
    platform_account_id,
    platform, 
    access_token,
    refresh_token,
    token_expires_at,
    platform_data,
    disabled,
    created_at,
    updated_at
)
SELECT
    generate_internal_id('linkedin', platform_account_id) as internal_id,
    user_id,
    account_name as name,
    profile_image_url as picture,
    platform_account_id,
    platform,
    access_token,
    refresh_token,
    token_expires_at,
    jsonb_build_object(
        'account_id', platform_account_id,
        'username', username,  
        'bio', bio,
        'follower_count', follower_count,
        'connection_count', following_count,
        'first_name', platform_data->>'first_name',
        'last_name', platform_data->>'last_name',
        'email', platform_data->>'email',
        'industry', platform_data->>'industry'
    ) as platform_data,
    NOT is_active as disabled,
    created_at,
    updated_at
FROM social_media_accounts  
WHERE platform = 'linkedin';

-- =====================================================
-- AGENT INTEGRATION MIGRATION
-- =====================================================

-- Migrate agent_social_accounts to agent_integrations
INSERT INTO agent_integrations (
    agent_id,
    user_id,
    integration_id,
    enabled,
    cached_name,
    cached_picture,
    cached_stats,
    created_at,
    updated_at
)
SELECT 
    asa.agent_id,
    asa.user_id,
    i.id as integration_id,
    asa.enabled,
    asa.account_name as cached_name,
    asa.profile_picture as cached_picture,
    jsonb_build_object(
        'subscriber_count', asa.subscriber_count,
        'view_count', asa.view_count,
        'video_count', asa.video_count,
        'country', asa.country
    ) as cached_stats,
    asa.created_at,
    asa.updated_at
FROM agent_social_accounts asa
JOIN integrations i ON (
    asa.user_id = i.user_id 
    AND asa.platform = i.platform 
    AND asa.account_id = i.platform_account_id
);

-- =====================================================
-- COMPATIBILITY VIEWS (For backward compatibility during transition)
-- =====================================================

-- YouTube channels compatibility view
CREATE VIEW youtube_channels_unified AS 
SELECT 
    platform_account_id as id,
    user_id,
    name,
    (platform_data->>'username') as username,
    picture as profile_picture,
    (platform_data->>'profile_pictures'->>'medium') as profile_picture_medium,
    (platform_data->>'profile_pictures'->>'small') as profile_picture_small,
    (platform_data->>'custom_url') as custom_url,
    (platform_data->>'description') as description,
    COALESCE((platform_data->>'subscriber_count')::BIGINT, 0) as subscriber_count,
    COALESCE((platform_data->>'view_count')::BIGINT, 0) as view_count,
    COALESCE((platform_data->>'video_count')::BIGINT, 0) as video_count,
    (platform_data->>'country') as country,
    access_token,
    refresh_token,
    token_expires_at as expires_at,
    NOT disabled as is_active,
    created_at,
    updated_at
FROM integrations 
WHERE platform = 'youtube' AND deleted_at IS NULL;

-- Pinterest accounts compatibility view
CREATE VIEW pinterest_accounts_unified AS
SELECT 
    platform_account_id as id,
    user_id,
    name,
    (platform_data->>'username') as username,
    picture as profile_image,
    (platform_data->>'bio') as bio,
    COALESCE((platform_data->>'follower_count')::BIGINT, 0) as follower_count,
    COALESCE((platform_data->>'following_count')::BIGINT, 0) as following_count,
    COALESCE((platform_data->>'pin_count')::BIGINT, 0) as pin_count,
    COALESCE((platform_data->>'board_count')::BIGINT, 0) as board_count,
    access_token,
    refresh_token,
    token_expires_at,
    NOT disabled as is_active,
    created_at,
    updated_at
FROM integrations
WHERE platform = 'pinterest' AND deleted_at IS NULL;

-- Update triggers for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_integrations_updated_at 
    BEFORE UPDATE ON integrations 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agent_integrations_updated_at 
    BEFORE UPDATE ON agent_integrations 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- SUCCESS MESSAGE
-- =====================================================
DO $$
BEGIN
    RAISE NOTICE '✅ UNIFIED INTEGRATIONS MIGRATION COMPLETED SUCCESSFULLY!';
    RAISE NOTICE '📊 Migrated data from all platform-specific tables to unified integrations table';
    RAISE NOTICE '🔗 Created agent_integrations table for per-agent permissions';
    RAISE NOTICE '👁️ Created compatibility views for backward compatibility';
    RAISE NOTICE '🛡️ Applied Row Level Security policies';
    RAISE NOTICE '⚡ Added performance indexes';
    RAISE NOTICE '🚀 Platform architecture is now consistent and scalable!';
END $$;