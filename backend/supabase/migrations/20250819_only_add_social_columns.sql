-- Only add the new social media columns to existing file_uploads table
-- This migration assumes the table and policies already exist

-- Add is_social_content column if it doesn't exist
ALTER TABLE file_uploads 
ADD COLUMN IF NOT EXISTS is_social_content BOOLEAN DEFAULT FALSE;

-- Add compatible_platforms column if it doesn't exist  
ALTER TABLE file_uploads 
ADD COLUMN IF NOT EXISTS compatible_platforms TEXT[] DEFAULT '{}';

-- Add comments for the new columns
COMMENT ON COLUMN file_uploads.is_social_content IS 'Whether this file is suitable for social media platforms';
COMMENT ON COLUMN file_uploads.compatible_platforms IS 'Array of social media platforms this file is compatible with';

-- Update table comment
COMMENT ON TABLE file_uploads IS 'Generic file upload storage for all file types with social media metadata';