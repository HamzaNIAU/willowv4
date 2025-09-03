-- Instagram Integration Tables

BEGIN;

-- Instagram accounts table - stores authenticated Instagram accounts
CREATE TABLE IF NOT EXISTS instagram_accounts (
    id VARCHAR PRIMARY KEY,                  -- Instagram user ID
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    username VARCHAR NOT NULL,               -- Instagram @username (without @)
    name VARCHAR NOT NULL,                   -- Display name
    biography TEXT,                          -- Bio/description
    profile_picture_url VARCHAR,             -- Profile picture URL
    website VARCHAR,                         -- Website URL from profile
    account_type VARCHAR DEFAULT 'PERSONAL', -- PERSONAL, BUSINESS, CREATOR
    followers_count BIGINT DEFAULT 0,        -- Follower count
    following_count BIGINT DEFAULT 0,        -- Following count
    media_count BIGINT DEFAULT 0,            -- Total media count
    
    -- OAuth tokens (encrypted)
    access_token TEXT NOT NULL,              -- Encrypted long-lived access token
    token_expires_at TIMESTAMP NOT NULL,     -- Token expiration time (60 days for long-lived)
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

-- Instagram OAuth sessions table - temporary storage for OAuth flow
CREATE TABLE IF NOT EXISTS instagram_oauth_sessions (
    state VARCHAR PRIMARY KEY,               -- OAuth state parameter
    session_data TEXT NOT NULL,              -- Encrypted session data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()) + INTERVAL '10 minutes'
);

-- Instagram posts tracking table - tracks created posts
CREATE TABLE IF NOT EXISTS instagram_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    account_id VARCHAR NOT NULL REFERENCES instagram_accounts(id) ON DELETE CASCADE,
    media_id VARCHAR,                        -- Instagram media ID when complete
    caption TEXT,                            -- Post caption
    media_type VARCHAR DEFAULT 'IMAGE',      -- IMAGE, VIDEO, CAROUSEL
    
    -- Post status
    post_status VARCHAR NOT NULL,            -- pending, creating_container, publishing, completed, failed, deleted
    status_message TEXT,                     -- Status or error message
    error_details JSONB,                     -- Detailed error information
    
    -- Instagram specific
    container_id VARCHAR,                    -- Media container ID during creation
    media_url VARCHAR,                       -- Direct Instagram post URL
    permalink VARCHAR,                       -- Instagram permalink
    
    -- References to uploaded files
    video_reference_id VARCHAR,              -- Reference to video file
    image_reference_ids VARCHAR[],           -- References to image files
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    completed_at TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Instagram stories tracking table - tracks created stories
CREATE TABLE IF NOT EXISTS instagram_stories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    account_id VARCHAR NOT NULL REFERENCES instagram_accounts(id) ON DELETE CASCADE,
    story_id VARCHAR,                        -- Instagram story ID when complete
    media_type VARCHAR DEFAULT 'IMAGE',      -- IMAGE, VIDEO
    
    -- Story status
    story_status VARCHAR NOT NULL,           -- pending, creating, completed, failed
    status_message TEXT,                     -- Status or error message
    
    -- References to uploaded files
    video_reference_id VARCHAR,              -- Reference to video file
    image_reference_id VARCHAR,              -- Reference to image file
    
    -- Timestamps (stories expire after 24 hours)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    completed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE      -- 24 hours after creation
);

-- Indexes for performance
CREATE INDEX idx_instagram_accounts_user_id ON instagram_accounts(user_id);
CREATE INDEX idx_instagram_accounts_is_active ON instagram_accounts(is_active);
CREATE INDEX idx_instagram_accounts_username ON instagram_accounts(username);
CREATE INDEX idx_instagram_oauth_sessions_expires_at ON instagram_oauth_sessions(expires_at);
CREATE INDEX idx_instagram_posts_user_id ON instagram_posts(user_id);
CREATE INDEX idx_instagram_posts_account_id ON instagram_posts(account_id);
CREATE INDEX idx_instagram_posts_status ON instagram_posts(post_status);
CREATE INDEX idx_instagram_posts_media_id ON instagram_posts(media_id);
CREATE INDEX idx_instagram_stories_user_id ON instagram_stories(user_id);
CREATE INDEX idx_instagram_stories_account_id ON instagram_stories(account_id);
CREATE INDEX idx_instagram_stories_status ON instagram_stories(story_status);

-- Row Level Security
ALTER TABLE instagram_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE instagram_oauth_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE instagram_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE instagram_stories ENABLE ROW LEVEL SECURITY;

-- RLS Policies for instagram_accounts
CREATE POLICY "Users can view their own Instagram accounts"
    ON instagram_accounts FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own Instagram accounts"
    ON instagram_accounts FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own Instagram accounts"
    ON instagram_accounts FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own Instagram accounts"
    ON instagram_accounts FOR DELETE
    USING (auth.uid() = user_id);

-- RLS Policies for instagram_oauth_sessions (no user-specific access needed)
CREATE POLICY "OAuth sessions are publicly accessible during flow"
    ON instagram_oauth_sessions FOR ALL
    USING (true);

-- RLS Policies for instagram_posts
CREATE POLICY "Users can view their own posts"
    ON instagram_posts FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own posts"
    ON instagram_posts FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own posts"
    ON instagram_posts FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own posts"
    ON instagram_posts FOR DELETE
    USING (auth.uid() = user_id);

-- RLS Policies for instagram_stories
CREATE POLICY "Users can view their own stories"
    ON instagram_stories FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own stories"
    ON instagram_stories FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own stories"
    ON instagram_stories FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own stories"
    ON instagram_stories FOR DELETE
    USING (auth.uid() = user_id);

-- Functions for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_instagram_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc', NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_instagram_accounts_updated_at
    BEFORE UPDATE ON instagram_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_instagram_updated_at();

-- Function to cleanup expired OAuth sessions
CREATE OR REPLACE FUNCTION cleanup_expired_instagram_oauth_sessions()
RETURNS void AS $$
BEGIN
    DELETE FROM instagram_oauth_sessions
    WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Add Instagram accounts to agent_social_accounts when connected
CREATE OR REPLACE FUNCTION sync_instagram_to_agent_social_accounts()
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
            description,
            profile_image_url,
            followers_count,
            following_count,
            media_count,
            account_type,
            enabled,
            created_at,
            updated_at
        )
        SELECT 
            agents.agent_id,
            NEW.user_id,
            'instagram'::varchar,
            NEW.id,
            NEW.name,
            NEW.username,
            NEW.biography,
            NEW.profile_picture_url,
            NEW.followers_count,
            NEW.following_count,
            NEW.media_count,
            NEW.account_type,
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
                description,
                profile_image_url,
                followers_count,
                following_count,
                media_count,
                account_type,
                enabled,
                created_at,
                updated_at
            ) VALUES (
                'suna-default',
                NEW.user_id,
                'instagram',
                NEW.id,
                NEW.name,
                NEW.username,
                NEW.biography,
                NEW.profile_picture_url,
                NEW.followers_count,
                NEW.following_count,
                NEW.media_count,
                NEW.account_type,
                true, -- Default to enabled for suna-default
                NOW(),
                NOW()
            )
            ON CONFLICT (agent_id, user_id, platform, account_id) 
            DO UPDATE SET
                account_name = EXCLUDED.account_name,
                username = EXCLUDED.username,
                description = EXCLUDED.description,
                profile_image_url = EXCLUDED.profile_image_url,
                followers_count = EXCLUDED.followers_count,
                following_count = EXCLUDED.following_count,
                media_count = EXCLUDED.media_count,
                account_type = EXCLUDED.account_type,
                updated_at = NOW();
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for syncing Instagram accounts
CREATE TRIGGER sync_instagram_accounts_trigger
    AFTER INSERT ON instagram_accounts
    FOR EACH ROW
    EXECUTE FUNCTION sync_instagram_to_agent_social_accounts();

-- Update agent_social_accounts when instagram_accounts is updated
CREATE OR REPLACE FUNCTION update_instagram_in_agent_social_accounts()
RETURNS TRIGGER AS $$
BEGIN
    -- Update all matching records in agent_social_accounts
    UPDATE agent_social_accounts SET
        account_name = NEW.name,
        username = NEW.username,
        description = NEW.biography,
        profile_image_url = NEW.profile_picture_url,
        followers_count = NEW.followers_count,
        following_count = NEW.following_count,
        media_count = NEW.media_count,
        account_type = NEW.account_type,
        updated_at = NOW()
    WHERE 
        user_id = NEW.user_id 
        AND platform = 'instagram' 
        AND account_id = NEW.id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for updating Instagram accounts in agent_social_accounts
CREATE TRIGGER update_instagram_accounts_in_social_trigger
    AFTER UPDATE ON instagram_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_instagram_in_agent_social_accounts();

-- Remove from agent_social_accounts when instagram_accounts is deleted
CREATE OR REPLACE FUNCTION remove_instagram_from_agent_social_accounts()
RETURNS TRIGGER AS $$
BEGIN
    -- Remove all matching records from agent_social_accounts
    DELETE FROM agent_social_accounts
    WHERE 
        user_id = OLD.user_id 
        AND platform = 'instagram' 
        AND account_id = OLD.id;
    
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for removing Instagram accounts from agent_social_accounts
CREATE TRIGGER remove_instagram_accounts_from_social_trigger
    AFTER DELETE ON instagram_accounts
    FOR EACH ROW
    EXECUTE FUNCTION remove_instagram_from_agent_social_accounts();

COMMIT;