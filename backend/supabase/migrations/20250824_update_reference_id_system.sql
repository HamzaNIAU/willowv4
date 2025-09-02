-- Update Reference ID System to match Morphic implementation
-- Migration: 20250824_update_reference_id_system

BEGIN;

-- First, backup existing data if tables exist
CREATE TEMP TABLE IF NOT EXISTS upload_references_backup AS 
SELECT * FROM upload_references WHERE EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'upload_references');

CREATE TEMP TABLE IF NOT EXISTS video_file_references_backup AS 
SELECT * FROM video_file_references WHERE EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'video_file_references');

-- Drop existing tables to recreate with proper structure
DROP TABLE IF EXISTS upload_references CASCADE;
DROP TABLE IF EXISTS video_file_references CASCADE;

-- Create social_media_file_references for universal platform support
CREATE TABLE social_media_file_references (
    id VARCHAR(32) PRIMARY KEY,                  -- 32-char hex reference ID
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    file_name VARCHAR NOT NULL,
    file_data BYTEA NOT NULL,                   -- Binary file data (equivalent to MongoDB Buffer)
    file_size BIGINT NOT NULL,
    mime_type VARCHAR NOT NULL,
    checksum VARCHAR,                            -- SHA256 hash for integrity
    
    -- Platform metadata (universal)
    platform VARCHAR,                           -- youtube, tiktok, instagram, twitter, linkedin, facebook, etc.
    file_type VARCHAR NOT NULL,                 -- 'video', 'image', 'audio', 'document', 'thumbnail'
    
    -- File metadata
    dimensions JSONB,                           -- {width, height} for images/videos
    duration_seconds FLOAT,                     -- Duration for videos/audio
    
    -- AI-generated metadata
    transcription JSONB,                        -- AI transcription data
    generated_metadata JSONB,                   -- AI-generated titles, descriptions, hashtags
    detected_platforms TEXT[],                  -- Platforms this file is compatible with
    
    -- Management
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT TIMEZONE('utc', NOW() + INTERVAL '24 hours'),
    is_used BOOLEAN DEFAULT FALSE,
    used_at TIMESTAMP WITH TIME ZONE,
    used_for_platform VARCHAR,                  -- Which platform actually used it
    
    -- Constraints
    CHECK (file_type IN ('video', 'image', 'audio', 'document', 'thumbnail'))
);

-- Keep video_file_references as alias for backward compatibility
CREATE VIEW video_file_references AS 
SELECT * FROM social_media_file_references;

-- Create upload_references queue table (universal)
CREATE TABLE upload_references (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    reference_id VARCHAR(32) NOT NULL,          -- Links to social_media_file_references
    file_name VARCHAR NOT NULL,
    file_size BIGINT NOT NULL,
    file_type VARCHAR NOT NULL,                 -- 'video', 'image', 'audio', 'document', 'thumbnail'
    mime_type VARCHAR NOT NULL,
    
    -- Platform routing
    platform VARCHAR,                           -- Specific platform if known
    detected_platforms TEXT[],                  -- All compatible platforms
    intended_platform VARCHAR,                  -- User's intended platform from context
    
    -- Status tracking
    status VARCHAR DEFAULT 'pending',           -- pending, ready, used, expired
    status_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    ready_at TIMESTAMP WITH TIME ZONE,          -- When file was uploaded and ready
    used_at TIMESTAMP WITH TIME ZONE,           -- When reference was consumed
    used_for_platform VARCHAR,                  -- Which platform actually used it
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT TIMEZONE('utc', NOW() + INTERVAL '24 hours'),
    
    -- Constraints
    CHECK (status IN ('pending', 'ready', 'used', 'expired')),
    CHECK (file_type IN ('video', 'image', 'audio', 'document', 'thumbnail'))
);

-- Create indexes for performance
CREATE INDEX idx_social_media_files_user_id ON social_media_file_references(user_id);
CREATE INDEX idx_social_media_files_expires_at ON social_media_file_references(expires_at);
CREATE INDEX idx_social_media_files_is_used ON social_media_file_references(is_used);
CREATE INDEX idx_social_media_files_created_at ON social_media_file_references(created_at);
CREATE INDEX idx_social_media_files_platform ON social_media_file_references(platform);
CREATE INDEX idx_social_media_files_file_type ON social_media_file_references(file_type);

CREATE INDEX idx_upload_references_user_id ON upload_references(user_id);
CREATE INDEX idx_upload_references_reference_id ON upload_references(reference_id);
CREATE INDEX idx_upload_references_status ON upload_references(status);
CREATE INDEX idx_upload_references_expires_at ON upload_references(expires_at);
CREATE INDEX idx_upload_references_platform ON upload_references(platform);
CREATE INDEX idx_upload_references_intended_platform ON upload_references(intended_platform);

-- Enable Row Level Security
ALTER TABLE social_media_file_references ENABLE ROW LEVEL SECURITY;
ALTER TABLE upload_references ENABLE ROW LEVEL SECURITY;

-- RLS Policies for social_media_file_references
CREATE POLICY "Users can view their own file references"
    ON social_media_file_references FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Service role can view all file references"
    ON social_media_file_references FOR SELECT
    USING (auth.jwt() ->> 'role' = 'service_role');

CREATE POLICY "Users can insert their own file references"
    ON social_media_file_references FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Service role can insert any file references"
    ON social_media_file_references FOR INSERT
    WITH CHECK (auth.jwt() ->> 'role' = 'service_role');

CREATE POLICY "Users can update their own file references"
    ON social_media_file_references FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Service role can update any file references"
    ON social_media_file_references FOR UPDATE
    USING (auth.jwt() ->> 'role' = 'service_role')
    WITH CHECK (auth.jwt() ->> 'role' = 'service_role');

CREATE POLICY "Users can delete their own file references"
    ON social_media_file_references FOR DELETE
    USING (auth.uid() = user_id);

CREATE POLICY "Service role can delete any file references"
    ON social_media_file_references FOR DELETE
    USING (auth.jwt() ->> 'role' = 'service_role');

-- RLS Policies for upload_references
CREATE POLICY "Users can view their own upload references"
    ON upload_references FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Service role can view all upload references"
    ON upload_references FOR SELECT
    USING (auth.jwt() ->> 'role' = 'service_role');

CREATE POLICY "Users can insert their own upload references"
    ON upload_references FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Service role can insert any upload references"
    ON upload_references FOR INSERT
    WITH CHECK (auth.jwt() ->> 'role' = 'service_role');

CREATE POLICY "Users can update their own upload references"
    ON upload_references FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Service role can update any upload references"
    ON upload_references FOR UPDATE
    USING (auth.jwt() ->> 'role' = 'service_role')
    WITH CHECK (auth.jwt() ->> 'role' = 'service_role');

CREATE POLICY "Users can delete their own upload references"
    ON upload_references FOR DELETE
    USING (auth.uid() = user_id);

CREATE POLICY "Service role can delete any upload references"
    ON upload_references FOR DELETE
    USING (auth.jwt() ->> 'role' = 'service_role');

-- Function to clean up expired references (to be called by a cron job)
CREATE OR REPLACE FUNCTION cleanup_expired_references()
RETURNS void AS $$
BEGIN
    -- Delete expired social media file references
    DELETE FROM social_media_file_references
    WHERE expires_at < NOW() AND is_used = FALSE;
    
    -- Update status of expired upload references
    UPDATE upload_references
    SET status = 'expired'
    WHERE expires_at < NOW() AND status IN ('pending', 'ready');
END;
$$ LANGUAGE plpgsql;

-- Function to mark a reference as used (with platform tracking)
CREATE OR REPLACE FUNCTION mark_reference_used(
    ref_id VARCHAR(32),
    platform_name VARCHAR DEFAULT NULL
)
RETURNS void AS $$
BEGIN
    -- Update social_media_file_references
    UPDATE social_media_file_references
    SET is_used = TRUE, 
        used_at = NOW(),
        used_for_platform = COALESCE(platform_name, platform)
    WHERE id = ref_id;
    
    -- Update upload_references
    UPDATE upload_references
    SET status = 'used', 
        used_at = NOW(),
        used_for_platform = COALESCE(platform_name, platform)
    WHERE reference_id = ref_id;
END;
$$ LANGUAGE plpgsql;

-- Add comments for documentation
COMMENT ON TABLE social_media_file_references IS 'Universal storage for social media files with reference IDs - supports all platforms';
COMMENT ON VIEW video_file_references IS 'Backward compatibility view for YouTube-specific code';
COMMENT ON TABLE upload_references IS 'Queue for tracking upload references across all social media platforms';
COMMENT ON FUNCTION cleanup_expired_references() IS 'Removes expired file references - should be called periodically';
COMMENT ON FUNCTION mark_reference_used(ref_id VARCHAR, platform_name VARCHAR) IS 'Marks a reference ID as used when consumed by a specific platform';

-- Platform compatibility tracking table
CREATE TABLE IF NOT EXISTS platform_file_requirements (
    platform VARCHAR PRIMARY KEY,
    max_video_size_mb INTEGER,
    max_image_size_mb INTEGER,
    supported_video_formats TEXT[],
    supported_image_formats TEXT[],
    max_video_duration_seconds INTEGER,
    min_video_duration_seconds INTEGER,
    aspect_ratios JSONB,
    special_requirements JSONB
);

-- Insert known platform requirements
INSERT INTO platform_file_requirements (platform, max_video_size_mb, max_image_size_mb, supported_video_formats, supported_image_formats, max_video_duration_seconds, aspect_ratios) VALUES
('youtube', 128000, 2, ARRAY['mp4', 'mov', 'avi', 'wmv', 'flv', 'mkv', 'webm'], ARRAY['jpg', 'png', 'gif'], 43200, '{"min": "16:9", "max": "16:9", "preferred": ["16:9", "4:3"]}'),
('tiktok', 287, 10, ARRAY['mp4', 'mov'], ARRAY['jpg', 'png'], 600, '{"min": "9:16", "max": "9:16", "preferred": ["9:16"]}'),
('instagram', 100, 30, ARRAY['mp4', 'mov'], ARRAY['jpg', 'png'], 60, '{"feed": ["1:1", "4:5"], "reels": ["9:16"], "stories": ["9:16"]}'),
('twitter', 512, 5, ARRAY['mp4'], ARRAY['jpg', 'png', 'gif'], 140, '{"min": "1:3", "max": "3:1", "preferred": ["16:9", "1:1"]}'),
('facebook', 10240, 30, ARRAY['mp4', 'mov'], ARRAY['jpg', 'png'], 240, '{"min": "9:16", "max": "16:9", "preferred": ["16:9", "1:1", "9:16"]}'),
('linkedin', 5120, 10, ARRAY['mp4'], ARRAY['jpg', 'png'], 600, '{"min": "1:2.4", "max": "2.4:1", "preferred": ["16:9", "1:1"]}')
ON CONFLICT (platform) DO NOTHING;

COMMIT;