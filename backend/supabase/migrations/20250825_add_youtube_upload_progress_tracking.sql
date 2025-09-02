-- Add progress tracking columns to youtube_uploads table

BEGIN;

-- Add progress tracking columns
ALTER TABLE youtube_uploads 
ADD COLUMN IF NOT EXISTS bytes_uploaded BIGINT DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_bytes BIGINT DEFAULT 0;

-- Add comments for documentation
COMMENT ON COLUMN youtube_uploads.bytes_uploaded IS 'Number of bytes uploaded so far for progress tracking';
COMMENT ON COLUMN youtube_uploads.total_bytes IS 'Total file size in bytes for progress calculation';

COMMIT;