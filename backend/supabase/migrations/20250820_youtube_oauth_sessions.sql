-- Create table for YouTube OAuth sessions with PKCE support
CREATE TABLE IF NOT EXISTS youtube_oauth_sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    state TEXT NOT NULL,
    code_verifier TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Indexes for fast lookups
    UNIQUE(user_id, state)
);

-- Create index for cleanup of expired sessions
CREATE INDEX IF NOT EXISTS idx_youtube_oauth_sessions_expires_at 
ON youtube_oauth_sessions(expires_at);

-- Add RLS policies
ALTER TABLE youtube_oauth_sessions ENABLE ROW LEVEL SECURITY;

-- Users can only access their own OAuth sessions
CREATE POLICY "Users can view own oauth sessions" ON youtube_oauth_sessions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own oauth sessions" ON youtube_oauth_sessions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own oauth sessions" ON youtube_oauth_sessions
    FOR DELETE USING (auth.uid() = user_id);

-- Add comment
COMMENT ON TABLE youtube_oauth_sessions IS 'Temporary storage for YouTube OAuth2 PKCE parameters during authorization flow';