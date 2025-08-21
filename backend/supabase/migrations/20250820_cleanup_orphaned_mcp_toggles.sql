-- Migration to clean up orphaned MCP toggles and ensure data consistency
-- This migration:
-- 1. Removes toggles for non-existent YouTube channels
-- 2. Creates missing toggles for existing channels
-- 3. Ensures proper default states

-- First, clean up orphaned YouTube channel toggles
-- (toggles that reference channels that no longer exist)
DELETE FROM agent_mcp_toggles
WHERE mcp_id LIKE 'social.youtube.%'
AND NOT EXISTS (
    SELECT 1 
    FROM youtube_channels yc
    WHERE yc.id = SUBSTRING(agent_mcp_toggles.mcp_id FROM 16)  -- Extract channel ID from 'social.youtube.{id}'
    AND yc.user_id = agent_mcp_toggles.user_id
);

-- Clean up toggles for deleted agents
DELETE FROM agent_mcp_toggles
WHERE NOT EXISTS (
    SELECT 1
    FROM agents a
    WHERE a.agent_id = agent_mcp_toggles.agent_id
);

-- Create a function to ensure all YouTube channels have toggles for all agents
CREATE OR REPLACE FUNCTION ensure_youtube_channel_toggles()
RETURNS void AS $$
DECLARE
    channel_record RECORD;
    agent_record RECORD;
    mcp_id_value TEXT;
BEGIN
    -- Loop through all active YouTube channels
    FOR channel_record IN 
        SELECT DISTINCT yc.id as channel_id, yc.user_id
        FROM youtube_channels yc
        WHERE yc.is_active = true
    LOOP
        -- For each channel, ensure toggles exist for all user's agents
        mcp_id_value := 'social.youtube.' || channel_record.channel_id;
        
        FOR agent_record IN
            SELECT a.agent_id
            FROM agents a
            WHERE a.account_id = channel_record.user_id
        LOOP
            -- Insert toggle if it doesn't exist (default to disabled for security)
            INSERT INTO agent_mcp_toggles (
                agent_id,
                user_id,
                mcp_id,
                enabled,
                created_at,
                updated_at
            )
            VALUES (
                agent_record.agent_id,
                channel_record.user_id,
                mcp_id_value,
                false,  -- Default to disabled for social media
                NOW(),
                NOW()
            )
            ON CONFLICT (agent_id, user_id, mcp_id) 
            DO NOTHING;  -- Skip if toggle already exists
        END LOOP;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Execute the function to create missing toggles
SELECT ensure_youtube_channel_toggles();

-- Drop the function as it's no longer needed
DROP FUNCTION ensure_youtube_channel_toggles();

-- Add a comment to document this migration
COMMENT ON TABLE agent_mcp_toggles IS 'Stores MCP toggle states for agents. Social media MCPs (social.*) default to disabled for security.';

-- Log the migration results
DO $$
DECLARE
    toggle_count INTEGER;
    channel_count INTEGER;
    agent_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO toggle_count FROM agent_mcp_toggles WHERE mcp_id LIKE 'social.youtube.%';
    SELECT COUNT(*) INTO channel_count FROM youtube_channels WHERE is_active = true;
    SELECT COUNT(DISTINCT agent_id) INTO agent_count FROM agents;
    
    RAISE NOTICE 'Migration complete: % YouTube toggles for % channels and % agents', 
                 toggle_count, channel_count, agent_count;
END $$;