-- Twitter Integration Tables

BEGIN;

-- Twitter accounts table - stores authenticated Twitter accounts
CREATE TABLE IF NOT EXISTS twitter_accounts (
    id VARCHAR PRIMARY KEY,                  -- Twitter user ID
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name VARCHAR NOT NULL,                   -- Display name
    username VARCHAR NOT NULL,               -- Twitter @handle (without @)
    description TEXT,                        -- Bio/description
    profile_image_url VARCHAR,               -- Profile picture URL
    followers_count BIGINT DEFAULT 0,        -- Follower count
    following_count BIGINT DEFAULT 0,        -- Following count
    tweet_count BIGINT DEFAULT 0,            -- Total tweet count
    listed_count BIGINT DEFAULT 0,           -- Listed count
    verified BOOLEAN DEFAULT FALSE,          -- Verification status
    twitter_created_at TIMESTAMP,            -- Account creation date on Twitter
    
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

-- Twitter OAuth sessions table - temporary storage for OAuth flow
CREATE TABLE IF NOT EXISTS twitter_oauth_sessions (
    state VARCHAR PRIMARY KEY,               -- OAuth state parameter
    session_data TEXT NOT NULL,              -- Encrypted session data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()) + INTERVAL '10 minutes'
);

-- Twitter tweets tracking table - tracks created tweets
CREATE TABLE IF NOT EXISTS twitter_tweets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    account_id VARCHAR NOT NULL REFERENCES twitter_accounts(id) ON DELETE CASCADE,
    tweet_id VARCHAR,                        -- Twitter tweet ID when complete
    text TEXT NOT NULL,                      -- Tweet content
    media_ids TEXT[],                        -- Twitter media IDs
    reply_to_tweet_id VARCHAR,               -- Reply to tweet ID
    quote_tweet_id VARCHAR,                  -- Quote tweet ID
    
    -- Tweet status
    tweet_status VARCHAR NOT NULL,           -- pending, posting, completed, failed, deleted
    status_message TEXT,                     -- Status or error message
    error_details JSONB,                     -- Detailed error information
    
    -- URLs and metadata
    tweet_url VARCHAR,                       -- Direct tweet URL
    
    -- References to uploaded files
    video_reference_id VARCHAR,              -- Reference to video file
    image_reference_ids VARCHAR[],           -- References to image files
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    completed_at TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX idx_twitter_accounts_user_id ON twitter_accounts(user_id);
CREATE INDEX idx_twitter_accounts_is_active ON twitter_accounts(is_active);
CREATE INDEX idx_twitter_accounts_username ON twitter_accounts(username);
CREATE INDEX idx_twitter_oauth_sessions_expires_at ON twitter_oauth_sessions(expires_at);
CREATE INDEX idx_twitter_tweets_user_id ON twitter_tweets(user_id);
CREATE INDEX idx_twitter_tweets_account_id ON twitter_tweets(account_id);
CREATE INDEX idx_twitter_tweets_status ON twitter_tweets(tweet_status);
CREATE INDEX idx_twitter_tweets_tweet_id ON twitter_tweets(tweet_id);

-- Row Level Security
ALTER TABLE twitter_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE twitter_oauth_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE twitter_tweets ENABLE ROW LEVEL SECURITY;

-- RLS Policies for twitter_accounts
CREATE POLICY "Users can view their own Twitter accounts"
    ON twitter_accounts FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own Twitter accounts"
    ON twitter_accounts FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own Twitter accounts"
    ON twitter_accounts FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own Twitter accounts"
    ON twitter_accounts FOR DELETE
    USING (auth.uid() = user_id);

-- RLS Policies for twitter_oauth_sessions (no user-specific access needed)
CREATE POLICY "OAuth sessions are publicly accessible during flow"
    ON twitter_oauth_sessions FOR ALL
    USING (true);

-- RLS Policies for twitter_tweets
CREATE POLICY "Users can view their own tweets"
    ON twitter_tweets FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own tweets"
    ON twitter_tweets FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own tweets"
    ON twitter_tweets FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own tweets"
    ON twitter_tweets FOR DELETE
    USING (auth.uid() = user_id);

-- Functions for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_twitter_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc', NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_twitter_accounts_updated_at
    BEFORE UPDATE ON twitter_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_twitter_updated_at();

-- Function to cleanup expired OAuth sessions
CREATE OR REPLACE FUNCTION cleanup_expired_twitter_oauth_sessions()
RETURNS void AS $$
BEGIN
    DELETE FROM twitter_oauth_sessions
    WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Add Twitter accounts to agent_social_accounts when connected
CREATE OR REPLACE FUNCTION sync_twitter_to_agent_social_accounts()
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
            tweet_count,
            verified,
            enabled,
            created_at,
            updated_at
        )
        SELECT 
            agents.agent_id,
            NEW.user_id,
            'twitter'::varchar,
            NEW.id,
            NEW.name,
            NEW.username,
            NEW.description,
            NEW.profile_image_url,
            NEW.followers_count,
            NEW.following_count,
            NEW.tweet_count,
            NEW.verified,
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
                tweet_count,
                verified,
                enabled,
                created_at,
                updated_at
            ) VALUES (
                'suna-default',
                NEW.user_id,
                'twitter',
                NEW.id,
                NEW.name,
                NEW.username,
                NEW.description,
                NEW.profile_image_url,
                NEW.followers_count,
                NEW.following_count,
                NEW.tweet_count,
                NEW.verified,
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
                tweet_count = EXCLUDED.tweet_count,
                verified = EXCLUDED.verified,
                updated_at = NOW();
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for syncing Twitter accounts
CREATE TRIGGER sync_twitter_accounts_trigger
    AFTER INSERT ON twitter_accounts
    FOR EACH ROW
    EXECUTE FUNCTION sync_twitter_to_agent_social_accounts();

-- Update agent_social_accounts when twitter_accounts is updated
CREATE OR REPLACE FUNCTION update_twitter_in_agent_social_accounts()
RETURNS TRIGGER AS $$
BEGIN
    -- Update all matching records in agent_social_accounts
    UPDATE agent_social_accounts SET
        account_name = NEW.name,
        username = NEW.username,
        description = NEW.description,
        profile_image_url = NEW.profile_image_url,
        followers_count = NEW.followers_count,
        following_count = NEW.following_count,
        tweet_count = NEW.tweet_count,
        verified = NEW.verified,
        updated_at = NOW()
    WHERE 
        user_id = NEW.user_id 
        AND platform = 'twitter' 
        AND account_id = NEW.id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for updating Twitter accounts in agent_social_accounts
CREATE TRIGGER update_twitter_accounts_in_social_trigger
    AFTER UPDATE ON twitter_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_twitter_in_agent_social_accounts();

-- Remove from agent_social_accounts when twitter_accounts is deleted
CREATE OR REPLACE FUNCTION remove_twitter_from_agent_social_accounts()
RETURNS TRIGGER AS $$
BEGIN
    -- Remove all matching records from agent_social_accounts
    DELETE FROM agent_social_accounts
    WHERE 
        user_id = OLD.user_id 
        AND platform = 'twitter' 
        AND account_id = OLD.id;
    
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for removing Twitter accounts from agent_social_accounts
CREATE TRIGGER remove_twitter_accounts_from_social_trigger
    AFTER DELETE ON twitter_accounts
    FOR EACH ROW
    EXECUTE FUNCTION remove_twitter_from_agent_social_accounts();

COMMIT;