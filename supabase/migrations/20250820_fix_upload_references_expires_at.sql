-- Fix: Add missing expires_at column to upload_references table

BEGIN;

-- Add expires_at column to upload_references
ALTER TABLE upload_references 
ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;

-- Set default value for existing rows (24 hours from creation)
UPDATE upload_references 
SET expires_at = created_at + INTERVAL '24 hours'
WHERE expires_at IS NULL;

-- Make the column NOT NULL after setting defaults
ALTER TABLE upload_references 
ALTER COLUMN expires_at SET NOT NULL;

-- Add index for performance when querying by expires_at
CREATE INDEX IF NOT EXISTS idx_upload_references_expires_at 
ON upload_references(expires_at);

-- Add comment for documentation
COMMENT ON COLUMN upload_references.expires_at IS 'Auto-cleanup time for temporary upload references';

COMMIT;