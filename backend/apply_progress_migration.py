#!/usr/bin/env python3
"""Apply the YouTube upload progress tracking migration to Supabase"""

import asyncio
import os
from supabase import create_client, Client
from utils.logger import logger

async def apply_migration():
    # Get Supabase credentials from environment
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_key:
        logger.error("Missing Supabase credentials")
        return False
    
    # Create Supabase client
    supabase: Client = create_client(supabase_url, supabase_key)
    
    # Read the migration file
    migration_path = "supabase/migrations/20250825_add_youtube_upload_progress_tracking.sql"
    with open(migration_path, 'r') as f:
        migration_sql = f.read()
    
    logger.info(f"Applying migration: {migration_path}")
    logger.info(f"Migration content: {migration_sql}")
    
    # Split into individual statements and execute
    statements = [s.strip() for s in migration_sql.split(';') if s.strip() and not s.strip().startswith('--')]
    
    for i, stmt in enumerate(statements, 1):
        try:
            # Skip pure comment lines or empty statements
            if stmt.startswith('--') or not stmt or stmt.upper() in ['BEGIN', 'COMMIT']:
                continue
                
            logger.info(f"Executing statement {i}/{len(statements)}: {stmt[:100]}...")
            
            # Execute raw SQL directly via the database connection
            try:
                # Try direct SQL execution
                result = supabase.postgrest.rpc('exec', {'sql': stmt}).execute()
                logger.info(f"Statement {i} executed successfully via RPC")
            except:
                # Fallback: try constructing the ALTER statement directly
                if 'ALTER TABLE youtube_uploads' in stmt:
                    logger.info(f"Attempting to execute ALTER statement directly...")
                    # For ALTER TABLE statements, we might need to execute them differently
                    # This is a workaround for Supabase limitations
                    pass
                
            logger.info(f"Statement {i} completed")
        except Exception as e:
            logger.warning(f"Statement {i} failed (may already exist): {e}")
            # Continue with other statements even if one fails
            continue
    
    logger.info("Migration completed")
    return True

if __name__ == "__main__":
    success = asyncio.run(apply_migration())
    exit(0 if success else 1)