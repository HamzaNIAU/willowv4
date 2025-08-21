# YouTube Upload Fix - Missing expires_at Column

## Problem
YouTube video uploads were failing with the error:
```
column upload_references.expires_at does not exist
```

## Root Cause
The `upload_references` table was missing the `expires_at` column that the Python code expected. The code was trying to:
1. Insert `expires_at` values when creating upload references
2. Filter by `expires_at` when retrieving pending uploads

## Solution
Added the missing `expires_at` column to the `upload_references` table via a database migration.

## How to Apply the Fix

### Option 1: Using the Migration Script (Recommended)
```bash
cd backend
python apply_youtube_fix_migration.py
```

### Option 2: Manual via Supabase Dashboard
1. Go to your Supabase dashboard
2. Navigate to SQL Editor
3. Copy and run the migration from:
   - `backend/supabase/migrations/20250820_fix_upload_references_expires_at.sql`
   - or `supabase/migrations/20250820_fix_upload_references_expires_at.sql`

### Option 3: Using Supabase CLI
If you have Supabase CLI configured:
```bash
supabase db push
```

## What the Migration Does
1. Adds `expires_at` column (TIMESTAMP WITH TIME ZONE) to `upload_references` table
2. Sets default values for existing rows (24 hours from creation)
3. Makes the column NOT NULL
4. Adds an index for performance
5. Adds documentation comment

## Testing
After applying the migration:
1. Try uploading a video to YouTube again
2. The upload should now proceed without database errors
3. Check that the video appears in your YouTube channel

## Files Changed
- **Created**: `backend/supabase/migrations/20250820_fix_upload_references_expires_at.sql`
- **Created**: `supabase/migrations/20250820_fix_upload_references_expires_at.sql`
- **Created**: `backend/apply_youtube_fix_migration.py`
- **No changes needed**: `backend/services/youtube_file_service.py` (code was correct, just needed the column)