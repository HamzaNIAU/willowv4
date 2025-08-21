-- Alter existing file_uploads table to add social media metadata columns
-- First check if columns exist and add them if they don't

DO $$ 
BEGIN
    -- Add is_social_content column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'file_uploads' 
        AND column_name = 'is_social_content'
    ) THEN
        ALTER TABLE file_uploads 
        ADD COLUMN is_social_content BOOLEAN DEFAULT FALSE;
    END IF;

    -- Add compatible_platforms column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'file_uploads' 
        AND column_name = 'compatible_platforms'
    ) THEN
        ALTER TABLE file_uploads 
        ADD COLUMN compatible_platforms TEXT[] DEFAULT '{}';
    END IF;
END $$;

-- Add comments for the new columns
COMMENT ON COLUMN file_uploads.is_social_content IS 'Whether this file is suitable for social media platforms';
COMMENT ON COLUMN file_uploads.compatible_platforms IS 'Array of social media platforms this file is compatible with';

-- Update table comment
COMMENT ON TABLE file_uploads IS 'Generic file upload storage for all file types with social media metadata';