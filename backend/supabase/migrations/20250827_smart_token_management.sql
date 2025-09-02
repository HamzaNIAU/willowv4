-- Smart Token Management System Enhancement
-- Adds fields for Morphic-inspired intelligent token refresh

BEGIN;

-- Add smart token management columns to youtube_channels
ALTER TABLE youtube_channels 
ADD COLUMN IF NOT EXISTS needs_reauth BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS last_refresh_success TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS last_refresh_error TEXT,
ADD COLUMN IF NOT EXISTS last_refresh_attempt TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS auto_refresh_enabled BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS refresh_failure_count INTEGER DEFAULT 0;

-- Add indexes for smart token management queries
CREATE INDEX IF NOT EXISTS idx_youtube_channels_needs_reauth 
    ON youtube_channels(user_id, needs_reauth) WHERE needs_reauth = TRUE;

CREATE INDEX IF NOT EXISTS idx_youtube_channels_token_expiry 
    ON youtube_channels(user_id, token_expires_at) WHERE is_active = TRUE;

-- Add comments for documentation
COMMENT ON COLUMN youtube_channels.needs_reauth IS 'Whether channel needs manual re-authentication due to refresh failures';
COMMENT ON COLUMN youtube_channels.last_refresh_success IS 'Timestamp of last successful automatic token refresh';
COMMENT ON COLUMN youtube_channels.last_refresh_error IS 'Last token refresh error message for debugging';
COMMENT ON COLUMN youtube_channels.auto_refresh_enabled IS 'Whether automatic token refresh is enabled for this channel';
COMMENT ON COLUMN youtube_channels.refresh_failure_count IS 'Count of consecutive refresh failures for health monitoring';

-- Create function to identify channels needing proactive refresh
CREATE OR REPLACE FUNCTION get_channels_needing_refresh()
RETURNS TABLE (
    user_id UUID,
    channel_id VARCHAR,
    channel_name VARCHAR,
    expires_at TIMESTAMPTZ,
    minutes_until_expiry NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        yc.user_id,
        yc.id as channel_id,
        yc.name as channel_name,
        yc.token_expires_at::TIMESTAMPTZ as expires_at,
        EXTRACT(EPOCH FROM (yc.token_expires_at::TIMESTAMPTZ - NOW())) / 60 as minutes_until_expiry
    FROM youtube_channels yc
    WHERE 
        yc.is_active = TRUE 
        AND yc.auto_refresh_enabled = TRUE
        AND yc.needs_reauth = FALSE
        AND yc.token_expires_at::TIMESTAMPTZ <= NOW() + INTERVAL '10 minutes'  -- Tokens expiring soon
    ORDER BY yc.token_expires_at ASC;
END;
$$ LANGUAGE plpgsql;

-- Create function to reset auth flags after successful re-authentication  
CREATE OR REPLACE FUNCTION reset_channel_auth_flags(p_user_id UUID, p_channel_id VARCHAR)
RETURNS VOID AS $$
BEGIN
    UPDATE youtube_channels SET
        needs_reauth = FALSE,
        last_refresh_error = NULL,
        refresh_failure_count = 0,
        auto_refresh_enabled = TRUE,
        updated_at = NOW()
    WHERE user_id = p_user_id AND id = p_channel_id;
END;
$$ LANGUAGE plpgsql;

-- Create function for smart token health monitoring
CREATE OR REPLACE FUNCTION get_token_health_status(p_user_id UUID)
RETURNS TABLE (
    channel_id VARCHAR,
    channel_name VARCHAR,
    token_status TEXT,
    expires_in_minutes NUMERIC,
    needs_attention BOOLEAN,
    last_refresh TIMESTAMPTZ,
    error_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        yc.id as channel_id,
        yc.name as channel_name,
        CASE 
            WHEN yc.needs_reauth THEN 'needs_reauth'
            WHEN yc.token_expires_at::TIMESTAMPTZ <= NOW() THEN 'expired'
            WHEN yc.token_expires_at::TIMESTAMPTZ <= NOW() + INTERVAL '5 minutes' THEN 'expiring_soon'
            WHEN yc.token_expires_at::TIMESTAMPTZ <= NOW() + INTERVAL '1 hour' THEN 'refresh_window'
            ELSE 'healthy'
        END as token_status,
        EXTRACT(EPOCH FROM (yc.token_expires_at::TIMESTAMPTZ - NOW())) / 60 as expires_in_minutes,
        (yc.needs_reauth OR yc.refresh_failure_count > 2) as needs_attention,
        yc.last_refresh_success,
        yc.refresh_failure_count as error_count
    FROM youtube_channels yc
    WHERE yc.user_id = p_user_id AND yc.is_active = TRUE
    ORDER BY 
        yc.needs_reauth DESC,
        yc.token_expires_at ASC;
END;
$$ LANGUAGE plpgsql;

COMMIT;