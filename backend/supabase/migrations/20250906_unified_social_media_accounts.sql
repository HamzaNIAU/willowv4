-- Unified Social Media Accounts Table
-- This creates a single table to handle ALL social media platforms
-- replacing the need for separate tables for each platform

BEGIN;

-- Create the unified social media accounts table
CREATE TABLE IF NOT EXISTS social_media_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL CHECK (platform IN (
        'youtube', 'twitter', 'instagram', 'pinterest', 'linkedin', 
        'tiktok', 'facebook', 'threads', 'snapchat', 'reddit', 'discord'
    )),
    platform_account_id VARCHAR(255) NOT NULL,  -- Platform's ID for this account
    
    -- Common account info
    account_name VARCHAR(255) NOT NULL,
    username VARCHAR(255),
    email VARCHAR(255),
    profile_image_url TEXT,
    bio TEXT,
    website_url TEXT,
    
    -- Common metrics (platforms use what's relevant)
    follower_count BIGINT DEFAULT 0,
    following_count BIGINT DEFAULT 0,
    post_count BIGINT DEFAULT 0,
    view_count BIGINT DEFAULT 0,
    subscriber_count BIGINT DEFAULT 0,  -- For YouTube
    
    -- OAuth tokens (encrypted)
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_expires_at TIMESTAMP,
    token_scopes TEXT[],
    
    -- Token management
    is_active BOOLEAN DEFAULT TRUE,
    needs_reauth BOOLEAN DEFAULT FALSE,
    last_refresh_success TIMESTAMP,
    last_refresh_error TEXT,
    last_refresh_attempt TIMESTAMP,
    refresh_failure_count INTEGER DEFAULT 0,
    
    -- Platform-specific data
    platform_data JSONB DEFAULT '{}',  -- Flexible storage for platform-specific fields
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    
    -- Ensure unique account per platform per user
    UNIQUE(user_id, platform, platform_account_id)
);

-- Create indexes for performance
CREATE INDEX idx_social_media_accounts_user_platform ON social_media_accounts(user_id, platform);
CREATE INDEX idx_social_media_accounts_active ON social_media_accounts(is_active) WHERE is_active = true;

-- Migrate existing YouTube data if youtube_channels table exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'youtube_channels') THEN
        INSERT INTO social_media_accounts (
            user_id, platform, platform_account_id, account_name, username,
            profile_image_url, bio, subscriber_count, view_count, post_count,
            access_token, refresh_token, token_expires_at, token_scopes,
            is_active, needs_reauth, last_refresh_success, last_refresh_error,
            last_refresh_attempt, refresh_failure_count, created_at, updated_at,
            platform_data
        )
        SELECT 
            user_id, 
            'youtube' as platform,
            id as platform_account_id,
            name as account_name,
            username,
            profile_picture as profile_image_url,
            description as bio,
            subscriber_count,
            view_count,
            video_count as post_count,
            access_token,
            refresh_token,
            token_expires_at,
            token_scopes,
            is_active,
            needs_reauth,
            last_refresh_success,
            last_refresh_error,
            last_refresh_attempt,
            refresh_failure_count,
            created_at,
            updated_at,
            jsonb_build_object(
                'channel_id', id,
                'custom_url', custom_url,
                'country', country,
                'published_at', published_at,
                'profile_picture_medium', profile_picture_medium,
                'profile_picture_small', profile_picture_small,
                'auto_refresh_enabled', auto_refresh_enabled
            ) as platform_data
        FROM youtube_channels
        WHERE NOT EXISTS (
            SELECT 1 FROM social_media_accounts 
            WHERE platform = 'youtube' 
            AND platform_account_id = youtube_channels.id
        );
        
        RAISE NOTICE 'Migrated % YouTube channels to unified table', (SELECT COUNT(*) FROM youtube_channels);
    END IF;
END $$;

-- Create view for backward compatibility with YouTube code
CREATE OR REPLACE VIEW youtube_channels_compat AS
SELECT 
    platform_account_id as id,
    user_id,
    account_name as name,
    username,
    (platform_data->>'custom_url')::varchar as custom_url,
    profile_image_url as profile_picture,
    (platform_data->>'profile_picture_medium')::varchar as profile_picture_medium,
    (platform_data->>'profile_picture_small')::varchar as profile_picture_small,
    bio as description,
    subscriber_count,
    view_count,
    post_count as video_count,
    (platform_data->>'country')::varchar as country,
    (platform_data->>'published_at')::timestamp as published_at,
    access_token,
    refresh_token,
    token_expires_at,
    token_scopes,
    is_active,
    created_at,
    updated_at,
    needs_reauth,
    last_refresh_success,
    last_refresh_error,
    last_refresh_attempt,
    (COALESCE((platform_data->>'auto_refresh_enabled')::boolean, true)) as auto_refresh_enabled,
    refresh_failure_count
FROM social_media_accounts
WHERE platform = 'youtube';

-- Update RLS policies
ALTER TABLE social_media_accounts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own social accounts"
    ON social_media_accounts FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "Users can insert their own social accounts"
    ON social_media_accounts FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update their own social accounts"
    ON social_media_accounts FOR UPDATE
    USING (user_id = auth.uid());

CREATE POLICY "Users can delete their own social accounts"
    ON social_media_accounts FOR DELETE
    USING (user_id = auth.uid());

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_social_media_accounts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_social_media_accounts_updated_at
    BEFORE UPDATE ON social_media_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_social_media_accounts_updated_at();

-- Add comment to table
COMMENT ON TABLE social_media_accounts IS 'Unified table for all social media platform accounts - replaces platform-specific tables';

COMMIT;

-- Log successful migration
DO $$
BEGIN
    RAISE NOTICE 'Unified social media accounts table created successfully';
    RAISE NOTICE 'Platforms supported: youtube, twitter, instagram, pinterest, linkedin, tiktok, facebook, threads, snapchat, reddit, discord';
END $$;