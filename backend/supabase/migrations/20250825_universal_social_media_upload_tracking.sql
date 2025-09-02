-- Universal Social Media Upload Progress Tracking System
-- This replaces platform-specific tables with a unified system

BEGIN;

-- Create universal social media uploads table
CREATE TABLE IF NOT EXISTS social_media_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Platform identification
    platform VARCHAR(50) NOT NULL, -- 'youtube', 'tiktok', 'instagram', 'twitter', etc.
    platform_account_id VARCHAR NOT NULL, -- Channel/Account ID on the platform
    platform_account_name VARCHAR, -- Channel/Account display name
    
    -- Content metadata
    title VARCHAR NOT NULL,
    description TEXT,
    tags TEXT[],
    category_id VARCHAR,
    privacy_status VARCHAR DEFAULT 'public', -- public, private, unlisted, etc.
    
    -- File information
    video_reference_id VARCHAR, -- Reference to video file
    thumbnail_reference_id VARCHAR, -- Reference to thumbnail
    file_name VARCHAR NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR,
    
    -- Universal upload progress tracking
    upload_status VARCHAR NOT NULL, -- pending, uploading, processing, completed, failed
    upload_progress FLOAT DEFAULT 0, -- Progress percentage (0-100)
    bytes_uploaded BIGINT DEFAULT 0, -- Bytes uploaded so far
    total_bytes BIGINT DEFAULT 0, -- Total bytes to upload
    status_message TEXT, -- Human-readable status or error message
    
    -- Platform-specific data (JSON for flexibility)
    platform_metadata JSONB DEFAULT '{}', -- Platform-specific fields
    platform_settings JSONB DEFAULT '{}', -- Platform-specific upload settings
    
    -- Scheduling and notifications
    scheduled_for TIMESTAMP, -- For scheduled uploads
    notify_followers BOOLEAN DEFAULT TRUE,
    
    -- Platform response data
    platform_post_id VARCHAR, -- Video/Post ID from platform (when complete)
    platform_url VARCHAR, -- Direct URL to the uploaded content
    embed_url VARCHAR, -- Embeddable URL if available
    
    -- Analytics (populated after upload)
    view_count BIGINT DEFAULT 0,
    like_count BIGINT DEFAULT 0,
    share_count BIGINT DEFAULT 0,
    comment_count BIGINT DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_social_media_uploads_user_id ON social_media_uploads(user_id);
CREATE INDEX IF NOT EXISTS idx_social_media_uploads_platform ON social_media_uploads(platform);
CREATE INDEX IF NOT EXISTS idx_social_media_uploads_status ON social_media_uploads(upload_status);
CREATE INDEX IF NOT EXISTS idx_social_media_uploads_account ON social_media_uploads(platform, platform_account_id);
CREATE INDEX IF NOT EXISTS idx_social_media_uploads_created ON social_media_uploads(created_at);

-- Create composite index for efficient querying
CREATE INDEX IF NOT EXISTS idx_social_media_uploads_user_platform_status 
    ON social_media_uploads(user_id, platform, upload_status);

-- Enable Row Level Security
ALTER TABLE social_media_uploads ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users can view their own social media uploads"
    ON social_media_uploads FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own social media uploads"
    ON social_media_uploads FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own social media uploads"
    ON social_media_uploads FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own social media uploads"
    ON social_media_uploads FOR DELETE
    USING (auth.uid() = user_id);

-- Create function for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_social_media_uploads_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = TIMEZONE('utc', NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for last_updated
CREATE TRIGGER update_social_media_uploads_last_updated
    BEFORE UPDATE ON social_media_uploads
    FOR EACH ROW
    EXECUTE FUNCTION update_social_media_uploads_timestamp();

-- Create universal social media accounts table
CREATE TABLE IF NOT EXISTS social_media_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Platform identification
    platform VARCHAR(50) NOT NULL, -- 'youtube', 'tiktok', 'instagram', etc.
    platform_account_id VARCHAR NOT NULL, -- Unique ID from platform
    username VARCHAR, -- @handle or username
    display_name VARCHAR NOT NULL, -- Channel/Account display name
    
    -- Account metadata
    profile_picture VARCHAR, -- Profile picture URL
    profile_banner VARCHAR, -- Banner/cover image URL
    description TEXT, -- Bio/description
    website_url VARCHAR, -- Associated website
    
    -- Account stats
    follower_count BIGINT DEFAULT 0,
    following_count BIGINT DEFAULT 0,
    post_count BIGINT DEFAULT 0,
    total_views BIGINT DEFAULT 0,
    
    -- OAuth and authentication
    access_token TEXT, -- Encrypted access token
    refresh_token TEXT, -- Encrypted refresh token
    token_expires_at TIMESTAMP,
    token_scopes TEXT[], -- OAuth scopes granted
    
    -- Platform-specific metadata
    platform_metadata JSONB DEFAULT '{}',
    
    -- Account status
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE, -- Platform verification status
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    last_sync_at TIMESTAMP WITH TIME ZONE, -- Last time we synced account data
    
    UNIQUE(platform, platform_account_id, user_id)
);

-- Indexes for social_media_accounts
CREATE INDEX IF NOT EXISTS idx_social_media_accounts_user_id ON social_media_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_social_media_accounts_platform ON social_media_accounts(platform);
CREATE INDEX IF NOT EXISTS idx_social_media_accounts_active ON social_media_accounts(is_active);
CREATE INDEX IF NOT EXISTS idx_social_media_accounts_user_platform 
    ON social_media_accounts(user_id, platform);

-- Enable RLS for accounts
ALTER TABLE social_media_accounts ENABLE ROW LEVEL SECURITY;

-- RLS Policies for accounts
CREATE POLICY "Users can view their own social media accounts"
    ON social_media_accounts FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own social media accounts"
    ON social_media_accounts FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own social media accounts"
    ON social_media_accounts FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own social media accounts"
    ON social_media_accounts FOR DELETE
    USING (auth.uid() = user_id);

-- Trigger for updated_at on accounts
CREATE TRIGGER update_social_media_accounts_updated_at
    BEFORE UPDATE ON social_media_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_social_media_uploads_timestamp();

-- Add comments for documentation
COMMENT ON TABLE social_media_uploads IS 'Universal table for tracking uploads across all social media platforms';
COMMENT ON COLUMN social_media_uploads.platform IS 'Platform identifier: youtube, tiktok, instagram, twitter, linkedin, etc.';
COMMENT ON COLUMN social_media_uploads.platform_metadata IS 'Platform-specific data stored as JSON (e.g., YouTube category, TikTok effects, etc.)';
COMMENT ON COLUMN social_media_uploads.bytes_uploaded IS 'Number of bytes uploaded so far for progress tracking';
COMMENT ON COLUMN social_media_uploads.total_bytes IS 'Total file size in bytes for progress calculation';

COMMENT ON TABLE social_media_accounts IS 'Universal table for storing authenticated social media accounts';
COMMENT ON COLUMN social_media_accounts.platform IS 'Platform identifier: youtube, tiktok, instagram, twitter, linkedin, etc.';
COMMENT ON COLUMN social_media_accounts.platform_metadata IS 'Platform-specific account data stored as JSON';

COMMIT;