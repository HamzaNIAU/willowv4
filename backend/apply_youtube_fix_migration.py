#!/usr/bin/env python3
"""Apply the YouTube upload_references fix migration to Supabase"""

import os
import sys
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent / ".env")

def apply_migration():
    # Get Supabase credentials
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Error: Missing Supabase credentials")
        print("Make sure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set in your .env file")
        return False
    
    print(f"📡 Connecting to Supabase at {supabase_url}...")
    
    # Create Supabase client with service role key
    supabase: Client = create_client(supabase_url, supabase_key)
    
    # Read the migration file
    migration_path = Path(__file__).parent / "supabase/migrations/20250820_fix_upload_references_expires_at.sql"
    
    if not migration_path.exists():
        print(f"❌ Error: Migration file not found at {migration_path}")
        return False
    
    print(f"📄 Reading migration from {migration_path.name}...")
    
    with open(migration_path, 'r') as f:
        migration_sql = f.read()
    
    # Remove BEGIN and COMMIT statements as we'll handle transactions differently
    migration_sql = migration_sql.replace('BEGIN;', '').replace('COMMIT;', '')
    
    # Split into individual statements
    statements = []
    for stmt in migration_sql.split(';'):
        stmt = stmt.strip()
        if stmt and not stmt.startswith('--'):
            statements.append(stmt)
    
    print(f"🔧 Found {len(statements)} SQL statements to execute")
    
    # Execute each statement
    success_count = 0
    for i, stmt in enumerate(statements, 1):
        try:
            print(f"  [{i}/{len(statements)}] Executing: {stmt[:50]}...")
            
            # For Supabase, we need to execute raw SQL through a stored procedure
            # Note: You may need to create an exec_sql function in your database
            # or use the Supabase SQL editor directly
            
            # Try to execute via RPC if available
            try:
                result = supabase.rpc('exec_sql', {'query': stmt + ';'}).execute()
                print(f"  ✅ Statement {i} executed successfully")
                success_count += 1
            except Exception as rpc_error:
                # If RPC doesn't work, provide instructions
                print(f"  ⚠️  Cannot execute via RPC. Please run this in Supabase SQL Editor:")
                print(f"      {stmt};")
                
        except Exception as e:
            print(f"  ❌ Statement {i} failed: {str(e)}")
            # Continue with other statements
    
    if success_count == len(statements):
        print(f"\n✅ Migration completed successfully! All {success_count} statements executed.")
        return True
    else:
        print(f"\n⚠️  Migration partially complete. {success_count}/{len(statements)} statements executed.")
        print("\n📝 To complete the migration manually:")
        print("1. Go to your Supabase dashboard")
        print("2. Navigate to SQL Editor")
        print("3. Copy and run the migration file content from:")
        print(f"   {migration_path}")
        return False

def main():
    print("🚀 YouTube Upload Fix Migration")
    print("=" * 50)
    
    # Check if migration is already applied
    print("\n⚠️  Note: This script will add the missing 'expires_at' column to the upload_references table.")
    
    response = input("\nDo you want to proceed? (y/n): ")
    if response.lower() != 'y':
        print("❌ Migration cancelled")
        return 1
    
    print()
    success = apply_migration()
    
    if success:
        print("\n🎉 Your YouTube uploads should now work properly!")
        print("Try uploading a video again to test the fix.")
        return 0
    else:
        print("\n⚠️  Please complete the migration manually using the Supabase SQL Editor")
        return 1

if __name__ == "__main__":
    sys.exit(main())