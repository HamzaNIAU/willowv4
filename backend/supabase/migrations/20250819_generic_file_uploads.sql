-- Create table for generic file uploads
CREATE TABLE IF NOT EXISTS file_uploads (
    file_id TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type TEXT NOT NULL,
    file_category TEXT NOT NULL, -- image, video, document, audio, other
    is_social_content BOOLEAN DEFAULT FALSE,
    compatible_platforms TEXT[] DEFAULT '{}', -- Array of platform names
    checksum TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    deleted_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS file_uploads_user_id_idx ON file_uploads(user_id);
CREATE INDEX IF NOT EXISTS file_uploads_expires_at_idx ON file_uploads(expires_at);
CREATE INDEX IF NOT EXISTS file_uploads_is_active_idx ON file_uploads(is_active);
CREATE INDEX IF NOT EXISTS file_uploads_file_category_idx ON file_uploads(file_category);

-- Enable RLS
ALTER TABLE file_uploads ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
CREATE POLICY "Users can view their own files" ON file_uploads
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own files" ON file_uploads
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own files" ON file_uploads
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own files" ON file_uploads
    FOR DELETE
    USING (auth.uid() = user_id);

-- Add comments
COMMENT ON TABLE file_uploads IS 'Generic file upload storage for all file types with social media metadata';
COMMENT ON COLUMN file_uploads.file_category IS 'Category of file: image, video, document, audio, or other';
COMMENT ON COLUMN file_uploads.is_social_content IS 'Whether this file is suitable for social media platforms';
COMMENT ON COLUMN file_uploads.compatible_platforms IS 'Array of social media platforms this file is compatible with';
COMMENT ON COLUMN file_uploads.expires_at IS 'When the file reference expires and can be cleaned up';
COMMENT ON COLUMN file_uploads.checksum IS 'SHA256 hash of the file content for integrity checking';