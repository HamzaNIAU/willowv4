-- Migration: Fix Kortix team templates marking
-- This migration properly marks templates created by the Kortix team as official
-- This was originally in 20250110 but needed to be moved after agent_templates table creation

BEGIN;

-- Check if the agent_templates table exists and has the is_kortix_team column
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'agent_templates'
    ) AND EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'agent_templates' 
        AND column_name = 'is_kortix_team'
    ) THEN
        
        -- Option 1: Mark templates by specific names that are known Kortix team templates
        UPDATE agent_templates
        SET is_kortix_team = true
        WHERE name IN (
            'Sheets Agent',
            'Slides Agent', 
            'Data Analyst',
            'Web Dev Agent',
            'Research Assistant',
            'Code Review Agent',
            'Documentation Writer',
            'API Testing Agent'
        ) AND is_public = true;

        -- Option 3: Mark templates that have specific metadata indicating they're official
        UPDATE agent_templates
        SET is_kortix_team = true
        WHERE metadata->>'is_suna_default' = 'true'
           OR metadata->>'is_official' = 'true';

        -- Log the update
        RAISE NOTICE 'Updated Kortix team templates successfully';
    ELSE
        RAISE NOTICE 'agent_templates table or is_kortix_team column does not exist, skipping update';
    END IF;
END $$;

COMMIT;