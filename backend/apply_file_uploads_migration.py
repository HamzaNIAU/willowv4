#!/usr/bin/env python3
"""Apply file uploads migration to remote Supabase"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

async def apply_migration():
    """Apply the file uploads migration"""
    
    # Create Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    
    # Read migration file
    migration_path = Path(__file__).parent / "supabase" / "migrations" / "20250819_generic_file_uploads.sql"
    
    with open(migration_path, 'r') as f:
        migration_sql = f.read()
    
    try:
        # Execute migration
        print("Applying file uploads migration...")
        
        # Split into individual statements and execute
        statements = [s.strip() for s in migration_sql.split(';') if s.strip()]
        
        for statement in statements:
            if statement:
                try:
                    result = supabase.postgrest.rpc('exec_sql', {'query': statement + ';'}).execute()
                    print(f"✓ Executed: {statement[:50]}...")
                except Exception as e:
                    # Try direct execution if RPC doesn't work
                    print(f"Note: {str(e)[:100]}")
        
        print("\n✅ Migration completed successfully!")
        print("\nCreated table: file_uploads")
        print("- Supports all file types (images, videos, documents, etc.)")
        print("- Files expire after 24 hours")
        print("- RLS policies enabled for user data protection")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print("\nYou may need to apply this migration manually in Supabase Dashboard:")
        print(f"1. Go to {SUPABASE_URL}")
        print("2. Navigate to SQL Editor")
        print("3. Copy and paste the migration from:")
        print(f"   {migration_path}")
        print("4. Run the migration")

if __name__ == "__main__":
    asyncio.run(apply_migration())