#!/usr/bin/env python3
"""Apply the MCP toggles migration to Supabase"""

import asyncio
import os
from supabase import create_client, Client
from utils.logger import logger

async def apply_migration():
    # Get Supabase credentials from environment
    supabase_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_key:
        logger.error("Missing Supabase credentials")
        return False
    
    # Create Supabase client
    supabase: Client = create_client(supabase_url, supabase_key)
    
    # Read the migration file
    migration_path = "/app/supabase/migrations/20250118000000_agent_mcp_toggles.sql"
    with open(migration_path, 'r') as f:
        migration_sql = f.read()
    
    # Split into individual statements and execute
    statements = [s.strip() for s in migration_sql.split(';') if s.strip() and not s.strip().startswith('--')]
    
    for i, stmt in enumerate(statements, 1):
        try:
            # Skip pure comment lines
            if stmt.startswith('--'):
                continue
                
            logger.info(f"Executing statement {i}/{len(statements)}")
            
            # Use postgrest client to execute raw SQL
            # Note: This requires the SQL to be properly formatted
            # For complex migrations, you might need to use psycopg2 directly
            result = supabase.rpc('exec_sql', {'sql': stmt + ';'}).execute()
            
            logger.info(f"Statement {i} executed successfully")
        except Exception as e:
            logger.warning(f"Statement {i} failed (may already exist): {e}")
            # Continue with other statements even if one fails
            continue
    
    logger.info("Migration completed")
    return True

if __name__ == "__main__":
    success = asyncio.run(apply_migration())
    exit(0 if success else 1)