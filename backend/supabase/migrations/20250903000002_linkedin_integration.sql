-- LinkedIn Integration Tables

BEGIN;

-- LinkedIn accounts table - stores authenticated LinkedIn accounts
CREATE TABLE IF NOT EXISTS linkedin_accounts (
    id VARCHAR PRIMARY KEY,                  -- LinkedIn user ID
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name VARCHAR NOT NULL,                   -- Display name
    first_name VARCHAR NOT NULL,             -- First name
    last_name VARCHAR NOT NULL,              -- Last name
    email VARCHAR,                           -- Email address
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

-- LinkedIn OAuth sessions table - temporary storage for OAuth flow
CREATE TABLE IF NOT EXISTS linkedin_oauth_sessions (
    state VARCHAR PRIMARY KEY,               -- OAuth state parameter
    session_data TEXT NOT NULL,              -- Encrypted session data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()) + INTERVAL '10 minutes'
);

-- LinkedIn posts tracking table - tracks created posts
CREATE TABLE IF NOT EXISTS linkedin_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    account_id VARCHAR NOT NULL REFERENCES linkedin_accounts(id) ON DELETE CASCADE,
    post_id VARCHAR,                         -- LinkedIn post ID when complete
    text TEXT NOT NULL,                      -- Post content
    visibility VARCHAR DEFAULT 'PUBLIC',     -- PUBLIC, CONNECTIONS
    
    -- Post status
    post_status VARCHAR NOT NULL,            -- pending, posting, completed, failed, deleted
    status_message TEXT,                     -- Status or error message
    error_details JSONB,                     -- Detailed error information
    
    -- URLs and metadata
    post_url VARCHAR,                        -- Direct post URL
    
    -- References to uploaded files
    video_reference_id VARCHAR,              -- Reference to video file
    image_reference_ids VARCHAR[],           -- References to image files (LinkedIn supports 1 image per post in basic API)
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    completed_at TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX idx_linkedin_accounts_user_id ON linkedin_accounts(user_id);
CREATE INDEX idx_linkedin_accounts_is_active ON linkedin_accounts(is_active);
CREATE INDEX idx_linkedin_accounts_email ON linkedin_accounts(email);
CREATE INDEX idx_linkedin_oauth_sessions_expires_at ON linkedin_oauth_sessions(expires_at);
CREATE INDEX idx_linkedin_posts_user_id ON linkedin_posts(user_id);
CREATE INDEX idx_linkedin_posts_account_id ON linkedin_posts(account_id);
CREATE INDEX idx_linkedin_posts_status ON linkedin_posts(post_status);
CREATE INDEX idx_linkedin_posts_post_id ON linkedin_posts(post_id);

-- Row Level Security
ALTER TABLE linkedin_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE linkedin_oauth_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE linkedin_posts ENABLE ROW LEVEL SECURITY;

-- RLS Policies for linkedin_accounts
CREATE POLICY "Users can view their own LinkedIn accounts"
    ON linkedin_accounts FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own LinkedIn accounts"
    ON linkedin_accounts FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own LinkedIn accounts"
    ON linkedin_accounts FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own LinkedIn accounts"
    ON linkedin_accounts FOR DELETE
    USING (auth.uid() = user_id);

-- RLS Policies for linkedin_oauth_sessions (no user-specific access needed)
CREATE POLICY "OAuth sessions are publicly accessible during flow"
    ON linkedin_oauth_sessions FOR ALL
    USING (true);

-- RLS Policies for linkedin_posts
CREATE POLICY "Users can view their own posts"
    ON linkedin_posts FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own posts"
    ON linkedin_posts FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own posts"
    ON linkedin_posts FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own posts"
    ON linkedin_posts FOR DELETE
    USING (auth.uid() = user_id);

-- Functions for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_linkedin_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc', NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_linkedin_accounts_updated_at
    BEFORE UPDATE ON linkedin_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_linkedin_updated_at();

-- Function to cleanup expired OAuth sessions
CREATE OR REPLACE FUNCTION cleanup_expired_linkedin_oauth_sessions()
RETURNS void AS $$
BEGIN
    DELETE FROM linkedin_oauth_sessions
    WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Add LinkedIn accounts to agent_social_accounts when connected
CREATE OR REPLACE FUNCTION sync_linkedin_to_agent_social_accounts()
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
            enabled,
            created_at,
            updated_at
        )
        SELECT 
            agents.agent_id,
            NEW.user_id,
            'linkedin'::varchar,
            NEW.id,
            NEW.name,
            NEW.first_name,
            NEW.last_name,
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
                description,
                profile_image_url,
                enabled,
                created_at,
                updated_at
            ) VALUES (
                'suna-default',
                NEW.user_id,
                'linkedin',
                NEW.id,
                NEW.name,
                NEW.first_name,
                NEW.last_name,
                NEW.profile_image_url,
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
                updated_at = NOW();
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for syncing LinkedIn accounts
CREATE TRIGGER sync_linkedin_accounts_trigger
    AFTER INSERT ON linkedin_accounts
    FOR EACH ROW
    EXECUTE FUNCTION sync_linkedin_to_agent_social_accounts();

-- Update agent_social_accounts when linkedin_accounts is updated
CREATE OR REPLACE FUNCTION update_linkedin_in_agent_social_accounts()
RETURNS TRIGGER AS $$
BEGIN
    -- Update all matching records in agent_social_accounts
    UPDATE agent_social_accounts SET
        account_name = NEW.name,
        username = NEW.first_name,
        description = NEW.last_name,
        profile_image_url = NEW.profile_image_url,
        updated_at = NOW()
    WHERE 
        user_id = NEW.user_id 
        AND platform = 'linkedin' 
        AND account_id = NEW.id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for updating LinkedIn accounts in agent_social_accounts
CREATE TRIGGER update_linkedin_accounts_in_social_trigger
    AFTER UPDATE ON linkedin_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_linkedin_in_agent_social_accounts();

-- Remove from agent_social_accounts when linkedin_accounts is deleted
CREATE OR REPLACE FUNCTION remove_linkedin_from_agent_social_accounts()
RETURNS TRIGGER AS $$
BEGIN
    -- Remove all matching records from agent_social_accounts
    DELETE FROM agent_social_accounts
    WHERE 
        user_id = OLD.user_id 
        AND platform = 'linkedin' 
        AND account_id = OLD.id;
    
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for removing LinkedIn accounts from agent_social_accounts
CREATE TRIGGER remove_linkedin_accounts_from_social_trigger
    AFTER DELETE ON linkedin_accounts
    FOR EACH ROW
    EXECUTE FUNCTION remove_linkedin_from_agent_social_accounts();

COMMIT;