-- Fix Pinterest Integration - Add Pinterest to Platform Constraints

BEGIN;

-- Step 1: Update platform constraint to include Pinterest
ALTER TABLE agent_social_accounts 
DROP CONSTRAINT IF EXISTS agent_social_accounts_platform_check;

ALTER TABLE agent_social_accounts 
ADD CONSTRAINT agent_social_accounts_platform_check 
CHECK (platform IN ('youtube', 'twitter', 'instagram', 'tiktok', 'linkedin', 'facebook', 'pinterest'));

-- Step 2: Test Pinterest platform insertion works
INSERT INTO agent_social_accounts (
    agent_id, 
    user_id, 
    platform, 
    account_id, 
    account_name, 
    enabled
) 
SELECT 
    agent_id,
    '00000000-0000-0000-0000-000000000000',
    'pinterest',
    'test_pinterest',
    'Test Pinterest Account', 
    true
FROM agents 
WHERE account_id = '00000000-0000-0000-0000-000000000000'
LIMIT 1
ON CONFLICT (agent_id, user_id, platform, account_id) DO NOTHING;

-- Remove test entry
DELETE FROM agent_social_accounts 
WHERE account_id = 'test_pinterest' 
AND platform = 'pinterest' 
AND user_id = '00000000-0000-0000-0000-000000000000';

COMMIT;

-- Log successful migration
DO $$
BEGIN
    RAISE NOTICE 'Pinterest platform constraint updated - Pinterest OAuth should now work';
END $$;