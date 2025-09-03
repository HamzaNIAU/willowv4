-- TikTok Integration Tables

BEGIN;

-- TikTok accounts table - stores authenticated TikTok accounts
CREATE TABLE IF NOT EXISTS tiktok_accounts (
    id VARCHAR PRIMARY KEY,                  -- TikTok open_id
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    union_id VARCHAR,                        -- TikTok union_id (persistent across apps)
    username VARCHAR NOT NULL,               -- TikTok display name
    name VARCHAR NOT NULL,                   -- Display name
    profile_image_url VARCHAR,               -- Profile picture URL
    
    -- OAuth tokens (encrypted)
    access_token TEXT NOT NULL,              -- Encrypted access token
    refresh_token TEXT,                      -- Encrypted refresh token
    token_expires_at TIMESTAMP NOT NULL,     -- Token expiration time
    token_scopes TEXT[],                     -- OAuth scopes granted
    
    -- Token management
    needs_reauth BOOLEAN DEFAULT FALSE,      -- Requires re-authentication
    last_refresh_success TIMESTAMP,          -- Last successful token refresh
    last_refresh_error TEXT,                 -- Last refresh error message
    last_refresh_attempt TIMESTAMP,          -- Last refresh attempt time
    refresh_failure_count INTEGER DEFAULT 0, -- Number of consecutive refresh failures
    
    -- Metadata
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    
    UNIQUE(id, user_id)
);

-- TikTok OAuth sessions table - temporary storage for OAuth flow
CREATE TABLE IF NOT EXISTS tiktok_oauth_sessions (
    state VARCHAR PRIMARY KEY,               -- OAuth state parameter
    session_data TEXT NOT NULL,              -- Encrypted session data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()) + INTERVAL '10 minutes'
);

-- TikTok videos tracking table - tracks uploaded videos
CREATE TABLE IF NOT EXISTS tiktok_videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    account_id VARCHAR NOT NULL REFERENCES tiktok_accounts(id) ON DELETE CASCADE,
    video_id VARCHAR,                        -- TikTok video ID when complete
    title VARCHAR NOT NULL,                  -- Video title/caption
    description TEXT,                        -- Video description
    
    -- Video status
    video_status VARCHAR NOT NULL,           -- pending, uploading, processing, completed, failed, deleted
    status_message TEXT,                     -- Status or error message
    error_details JSONB,                     -- Detailed error information
    
    -- URLs and metadata
    video_url VARCHAR,                       -- TikTok video URL
    
    -- References to uploaded files
    video_reference_id VARCHAR,              -- Reference to video file
    thumbnail_reference_id VARCHAR,          -- Reference to thumbnail file
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    completed_at TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX idx_tiktok_accounts_user_id ON tiktok_accounts(user_id);
CREATE INDEX idx_tiktok_accounts_is_active ON tiktok_accounts(is_active);
CREATE INDEX idx_tiktok_accounts_username ON tiktok_accounts(username);
CREATE INDEX idx_tiktok_oauth_sessions_expires_at ON tiktok_oauth_sessions(expires_at);
CREATE INDEX idx_tiktok_videos_user_id ON tiktok_videos(user_id);
CREATE INDEX idx_tiktok_videos_account_id ON tiktok_videos(account_id);
CREATE INDEX idx_tiktok_videos_status ON tiktok_videos(video_status);
CREATE INDEX idx_tiktok_videos_video_id ON tiktok_videos(video_id);

-- Row Level Security
ALTER TABLE tiktok_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE tiktok_oauth_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE tiktok_videos ENABLE ROW LEVEL SECURITY;

-- RLS Policies for tiktok_accounts
CREATE POLICY "Users can view their own TikTok accounts"
    ON tiktok_accounts FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own TikTok accounts"
    ON tiktok_accounts FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own TikTok accounts"
    ON tiktok_accounts FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own TikTok accounts"
    ON tiktok_accounts FOR DELETE
    USING (auth.uid() = user_id);

-- RLS Policies for tiktok_oauth_sessions (no user-specific access needed)
CREATE POLICY "OAuth sessions are publicly accessible during flow"
    ON tiktok_oauth_sessions FOR ALL
    USING (true);

-- RLS Policies for tiktok_videos
CREATE POLICY "Users can view their own videos"
    ON tiktok_videos FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own videos"
    ON tiktok_videos FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own videos"
    ON tiktok_videos FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own videos"
    ON tiktok_videos FOR DELETE
    USING (auth.uid() = user_id);

-- Functions for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_tiktok_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc', NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_tiktok_accounts_updated_at
    BEFORE UPDATE ON tiktok_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_tiktok_updated_at();

-- Function to cleanup expired OAuth sessions
CREATE OR REPLACE FUNCTION cleanup_expired_tiktok_oauth_sessions()
RETURNS void AS $$
BEGIN
    DELETE FROM tiktok_oauth_sessions
    WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Add TikTok accounts to agent_social_accounts when connected
CREATE OR REPLACE FUNCTION sync_tiktok_to_agent_social_accounts()
RETURNS TRIGGER AS $$
BEGIN
    -- Only process INSERT operations
    IF TG_OP = 'INSERT' THEN
        -- Insert into agent_social_accounts for all user's agents
        INSERT INTO agent_social_accounts (
            agent_id, 
            user_id, 
            platform, 
            account_id, 
            account_name, 
            username,
            profile_image_url,
            enabled,
            created_at,
            updated_at
        )
        SELECT 
            agents.agent_id,
            NEW.user_id,
            'tiktok'::varchar,
            NEW.id,
            NEW.name,
            NEW.username,
            NEW.profile_image_url,
            true, -- Default to enabled
            NOW(),
            NOW()
        FROM agents
        WHERE agents.account_id = NEW.user_id;
        
        -- Also add for suna-default virtual agent if user has agents
        IF EXISTS (SELECT 1 FROM agents WHERE account_id = NEW.user_id) THEN
            INSERT INTO agent_social_accounts (
                agent_id, 
                user_id, 
                platform, 
                account_id, 
                account_name, 
                username,
                profile_image_url,
                enabled,
                created_at,
                updated_at
            ) VALUES (
                'suna-default',
                NEW.user_id,
                'tiktok',
                NEW.id,
                NEW.name,
                NEW.username,
                NEW.profile_image_url,
                true, -- Default to enabled for suna-default
                NOW(),
                NOW()
            )
            ON CONFLICT (agent_id, user_id, platform, account_id) 
            DO UPDATE SET
                account_name = EXCLUDED.account_name,
                username = EXCLUDED.username,
                profile_image_url = EXCLUDED.profile_image_url,
                updated_at = NOW();
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for syncing TikTok accounts
CREATE TRIGGER sync_tiktok_accounts_trigger
    AFTER INSERT ON tiktok_accounts
    FOR EACH ROW
    EXECUTE FUNCTION sync_tiktok_to_agent_social_accounts();

-- Update agent_social_accounts when tiktok_accounts is updated
CREATE OR REPLACE FUNCTION update_tiktok_in_agent_social_accounts()
RETURNS TRIGGER AS $$
BEGIN
    -- Update all matching records in agent_social_accounts
    UPDATE agent_social_accounts SET
        account_name = NEW.name,
        username = NEW.username,
        profile_image_url = NEW.profile_image_url,
        updated_at = NOW()
    WHERE 
        user_id = NEW.user_id 
        AND platform = 'tiktok' 
        AND account_id = NEW.id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for updating TikTok accounts in agent_social_accounts
CREATE TRIGGER update_tiktok_accounts_in_social_trigger
    AFTER UPDATE ON tiktok_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_tiktok_in_agent_social_accounts();

-- Remove from agent_social_accounts when tiktok_accounts is deleted
CREATE OR REPLACE FUNCTION remove_tiktok_from_agent_social_accounts()
RETURNS TRIGGER AS $$
BEGIN
    -- Remove all matching records from agent_social_accounts
    DELETE FROM agent_social_accounts
    WHERE 
        user_id = OLD.user_id 
        AND platform = 'tiktok' 
        AND account_id = OLD.id;
    
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for removing TikTok accounts from agent_social_accounts
CREATE TRIGGER remove_tiktok_accounts_from_social_trigger
    AFTER DELETE ON tiktok_accounts
    FOR EACH ROW
    EXECUTE FUNCTION remove_tiktok_from_agent_social_accounts();

COMMIT;