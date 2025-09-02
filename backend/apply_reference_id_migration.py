#!/usr/bin/env python3
"""Apply the Reference ID System migration to Supabase"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# Try to load dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, environment should already be set
    pass

import asyncio
from services.supabase import DBConnection
from utils.logger import logger


async def apply_migration():
    """Apply the reference ID system migration"""
    
    print("\n" + "="*60)
    print("APPLYING REFERENCE ID SYSTEM MIGRATION")
    print("="*60)
    
    # Initialize database connection
    db = DBConnection()
    await db.initialize()
    
    try:
        # Read the migration file
        migration_path = Path(__file__).parent / "supabase" / "migrations" / "20250824_update_reference_id_system.sql"
        
        if not migration_path.exists():
            print(f"❌ Migration file not found: {migration_path}")
            return False
        
        print(f"\n📄 Reading migration from: {migration_path}")
        
        with open(migration_path, 'r') as f:
            migration_sql = f.read()
        
        # Get client
        client = await db.client
        
        # Parse SQL into statements
        # Remove comments and split by semicolons
        statements = []
        current_statement = []
        in_function = False
        
        for line in migration_sql.split('\n'):
            # Skip comment-only lines
            if line.strip().startswith('--') or not line.strip():
                continue
            
            # Track if we're inside a function definition
            if 'CREATE OR REPLACE FUNCTION' in line or 'CREATE FUNCTION' in line:
                in_function = True
            
            current_statement.append(line)
            
            # Check for statement end
            if line.strip().endswith(';'):
                # If we're in a function, look for the end marker
                if in_function:
                    if '$$ LANGUAGE' in line or 'LANGUAGE plpgsql;' in line:
                        in_function = False
                        statements.append('\n'.join(current_statement))
                        current_statement = []
                elif not in_function:
                    statements.append('\n'.join(current_statement))
                    current_statement = []
        
        # Add any remaining statement
        if current_statement:
            statements.append('\n'.join(current_statement))
        
        print(f"\n📊 Found {len(statements)} SQL statements to execute")
        
        # Execute each statement
        success_count = 0
        error_count = 0
        
        for i, stmt in enumerate(statements, 1):
            if not stmt.strip() or stmt.strip() == 'BEGIN;' or stmt.strip() == 'COMMIT;':
                continue
            
            # Show progress
            print(f"\n[{i}/{len(statements)}] Executing statement...")
            
            # Show first 100 chars of statement
            preview = stmt[:100].replace('\n', ' ')
            if len(stmt) > 100:
                preview += "..."
            print(f"   Preview: {preview}")
            
            try:
                # For DDL statements, we need to use raw SQL execution
                # Note: Supabase client doesn't directly support raw SQL execution
                # We'll need to handle this differently
                
                # Check if it's a simple query we can handle
                if stmt.strip().upper().startswith(('CREATE TABLE', 'DROP TABLE', 'CREATE INDEX', 
                                                     'ALTER TABLE', 'CREATE POLICY', 'CREATE FUNCTION')):
                    print(f"   ⚠️  DDL statement - needs to be run via Supabase Dashboard or CLI")
                    print(f"   Statement type: {stmt.strip()[:30]}...")
                else:
                    # Try to execute via RPC if available
                    print(f"   ⚠️  Complex statement - needs manual execution")
                
                error_count += 1
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
                error_count += 1
        
        print("\n" + "="*60)
        print("MIGRATION SUMMARY")
        print("="*60)
        
        print(f"\n⚠️  This migration contains DDL statements that need to be executed via:")
        print("   1. Supabase Dashboard SQL Editor")
        print("   2. Supabase CLI: supabase db push")
        print("   3. Direct PostgreSQL connection")
        
        print(f"\n📋 Migration file location:")
        print(f"   {migration_path}")
        
        print(f"\n📝 To apply via Supabase Dashboard:")
        print(f"   1. Go to your Supabase project")
        print(f"   2. Navigate to SQL Editor")
        print(f"   3. Copy and paste the migration SQL")
        print(f"   4. Click 'Run'")
        
        print(f"\n🔧 To apply via Supabase CLI:")
        print(f"   cd backend")
        print(f"   supabase db push")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        await db.disconnect()


if __name__ == "__main__":
    success = asyncio.run(apply_migration())
    
    if success:
        print("\n✅ Migration prepared successfully!")
        print("   Please apply it using one of the methods above.")
    else:
        print("\n❌ Migration preparation failed")
    
    exit(0 if success else 1)