-- Fix youtube_channels view to only return YouTube accounts
-- This prevents Pinterest and other social media accounts from appearing in YouTube sections

-- Drop the existing youtube_channels view/table if it exists
DROP VIEW IF EXISTS youtube_channels CASCADE;

-- Create a proper youtube_channels view that filters for YouTube only
CREATE VIEW youtube_channels AS
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
WHERE platform = 'youtube';  -- CRITICAL: Only return YouTube accounts!

-- Grant appropriate permissions
GRANT SELECT ON youtube_channels TO authenticated;
GRANT SELECT ON youtube_channels TO anon;

-- Add comment for documentation
COMMENT ON VIEW youtube_channels IS 'Backward compatibility view for YouTube channels - filters social_media_accounts for YouTube platform only';