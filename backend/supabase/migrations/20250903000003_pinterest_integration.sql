-- Pinterest Integration Tables

BEGIN;

-- Pinterest accounts table - stores authenticated Pinterest accounts
CREATE TABLE IF NOT EXISTS pinterest_accounts (
    id VARCHAR PRIMARY KEY,                  -- Pinterest user ID
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    username VARCHAR NOT NULL,               -- Pinterest username (without @)
    name VARCHAR NOT NULL,                   -- Display name or business name
    profile_image_url VARCHAR,               -- Profile picture URL
    website_url VARCHAR,                     -- Website URL
    about TEXT,                              -- Bio/description
    pin_count BIGINT DEFAULT 0,              -- Total pin count
    board_count BIGINT DEFAULT 0,            -- Total board count
    follower_count BIGINT DEFAULT 0,         -- Follower count
    following_count BIGINT DEFAULT 0,        -- Following count
    account_type VARCHAR DEFAULT 'PERSONAL', -- PERSONAL or BUSINESS
    
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

-- Pinterest OAuth sessions table - temporary storage for OAuth flow
CREATE TABLE IF NOT EXISTS pinterest_oauth_sessions (
    state VARCHAR PRIMARY KEY,               -- OAuth state parameter
    session_data TEXT NOT NULL,              -- Encrypted session data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()) + INTERVAL '10 minutes'
);

-- Pinterest pins tracking table - tracks created pins
CREATE TABLE IF NOT EXISTS pinterest_pins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    account_id VARCHAR NOT NULL REFERENCES pinterest_accounts(id) ON DELETE CASCADE,
    pin_id VARCHAR,                          -- Pinterest pin ID when complete
    title VARCHAR NOT NULL,                  -- Pin title
    description TEXT,                        -- Pin description
    board_id VARCHAR NOT NULL,               -- Pinterest board ID (required)
    link VARCHAR,                            -- Optional website link
    
    -- Pin status
    pin_status VARCHAR NOT NULL,             -- pending, pinning, completed, failed, deleted
    status_message TEXT,                     -- Status or error message
    error_details JSONB,                     -- Detailed error information
    
    -- URLs and metadata
    pin_url VARCHAR,                         -- Direct pin URL
    
    -- References to uploaded files
    video_reference_id VARCHAR,              -- Reference to video file
    image_reference_ids VARCHAR[],           -- References to image files (Pinterest supports 1 image per pin)
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    completed_at TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX idx_pinterest_accounts_user_id ON pinterest_accounts(user_id);
CREATE INDEX idx_pinterest_accounts_is_active ON pinterest_accounts(is_active);
CREATE INDEX idx_pinterest_accounts_username ON pinterest_accounts(username);
CREATE INDEX idx_pinterest_oauth_sessions_expires_at ON pinterest_oauth_sessions(expires_at);
CREATE INDEX idx_pinterest_pins_user_id ON pinterest_pins(user_id);
CREATE INDEX idx_pinterest_pins_account_id ON pinterest_pins(account_id);
CREATE INDEX idx_pinterest_pins_status ON pinterest_pins(pin_status);
CREATE INDEX idx_pinterest_pins_pin_id ON pinterest_pins(pin_id);

-- Row Level Security
ALTER TABLE pinterest_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE pinterest_oauth_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE pinterest_pins ENABLE ROW LEVEL SECURITY;

-- RLS Policies for pinterest_accounts
CREATE POLICY "Users can view their own Pinterest accounts"
    ON pinterest_accounts FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own Pinterest accounts"
    ON pinterest_accounts FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own Pinterest accounts"
    ON pinterest_accounts FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own Pinterest accounts"
    ON pinterest_accounts FOR DELETE
    USING (auth.uid() = user_id);

-- RLS Policies for pinterest_oauth_sessions (no user-specific access needed)
CREATE POLICY "OAuth sessions are publicly accessible during flow"
    ON pinterest_oauth_sessions FOR ALL
    USING (true);

-- RLS Policies for pinterest_pins
CREATE POLICY "Users can view their own pins"
    ON pinterest_pins FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own pins"
    ON pinterest_pins FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own pins"
    ON pinterest_pins FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own pins"
    ON pinterest_pins FOR DELETE
    USING (auth.uid() = user_id);

-- Functions for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_pinterest_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc', NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_pinterest_accounts_updated_at
    BEFORE UPDATE ON pinterest_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_pinterest_updated_at();

-- Function to cleanup expired OAuth sessions
CREATE OR REPLACE FUNCTION cleanup_expired_pinterest_oauth_sessions()
RETURNS void AS $$
BEGIN
    DELETE FROM pinterest_oauth_sessions
    WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Add Pinterest accounts to agent_social_accounts when connected
CREATE OR REPLACE FUNCTION sync_pinterest_to_agent_social_accounts()
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
            enabled,
            created_at,
            updated_at
        )
        SELECT 
            agents.agent_id,
            NEW.user_id,
            'pinterest'::varchar,
            NEW.id,
            NEW.name,
            NEW.username,
            NEW.about,
            NEW.profile_image_url,
            NEW.follower_count,
            NEW.following_count,
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
                enabled,
                created_at,
                updated_at
            ) VALUES (
                'suna-default',
                NEW.user_id,
                'pinterest',
                NEW.id,
                NEW.name,
                NEW.username,
                NEW.about,
                NEW.profile_image_url,
                NEW.follower_count,
                NEW.following_count,
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
                updated_at = NOW();
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for syncing Pinterest accounts
CREATE TRIGGER sync_pinterest_accounts_trigger
    AFTER INSERT ON pinterest_accounts
    FOR EACH ROW
    EXECUTE FUNCTION sync_pinterest_to_agent_social_accounts();

-- Update agent_social_accounts when pinterest_accounts is updated
CREATE OR REPLACE FUNCTION update_pinterest_in_agent_social_accounts()
RETURNS TRIGGER AS $$
BEGIN
    -- Update all matching records in agent_social_accounts
    UPDATE agent_social_accounts SET
        account_name = NEW.name,
        username = NEW.username,
        description = NEW.about,
        profile_image_url = NEW.profile_image_url,
        followers_count = NEW.follower_count,
        following_count = NEW.following_count,
        updated_at = NOW()
    WHERE 
        user_id = NEW.user_id 
        AND platform = 'pinterest' 
        AND account_id = NEW.id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for updating Pinterest accounts in agent_social_accounts
CREATE TRIGGER update_pinterest_accounts_in_social_trigger
    AFTER UPDATE ON pinterest_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_pinterest_in_agent_social_accounts();

-- Remove from agent_social_accounts when pinterest_accounts is deleted
CREATE OR REPLACE FUNCTION remove_pinterest_from_agent_social_accounts()
RETURNS TRIGGER AS $$
BEGIN
    -- Remove all matching records from agent_social_accounts
    DELETE FROM agent_social_accounts
    WHERE 
        user_id = OLD.user_id 
        AND platform = 'pinterest' 
        AND account_id = OLD.id;
    
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for removing Pinterest accounts from agent_social_accounts
CREATE TRIGGER remove_pinterest_accounts_from_social_trigger
    AFTER DELETE ON pinterest_accounts
    FOR EACH ROW
    EXECUTE FUNCTION remove_pinterest_from_agent_social_accounts();

COMMIT;