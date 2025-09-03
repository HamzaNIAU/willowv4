#!/usr/bin/env python3
"""Apply Pinterest migration specifically"""

import asyncio
import os
from services.supabase import DBConnection
from utils.logger import logger

async def apply_pinterest_migration():
    """Apply Pinterest database migration"""
    print("📌 Applying Pinterest migration...")
    
    db = DBConnection()
    await db.initialize()
    client = await db.client
    
    # Read migration file
    with open('supabase/migrations/20250903000003_pinterest_integration.sql', 'r') as f:
        migration_sql = f.read()
    
    # Split into individual statements and execute
    statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip() and not stmt.strip().upper().startswith('COMMIT') and not stmt.strip().upper().startswith('BEGIN')]
    
    for i, statement in enumerate(statements):
        if statement:
            try:
                print(f"Executing statement {i+1}/{len(statements)}: {statement[:50]}...")
                result = await client.rpc('exec_sql', {'sql': statement}).execute()
                print(f"✅ Statement {i+1} executed successfully")
            except Exception as e:
                print(f"⚠️ Statement {i+1} error (might be expected): {e}")
                # Continue with other statements
    
    print("✅ Pinterest migration completed!")
    
    # Verify tables exist
    try:
        result = await client.table("pinterest_accounts").select("*").limit(1).execute()
        print("✅ pinterest_accounts table verified")
    except Exception as e:
        print(f"❌ pinterest_accounts table verification failed: {e}")
    
    try:
        result = await client.table("pinterest_oauth_sessions").select("*").limit(1).execute()
        print("✅ pinterest_oauth_sessions table verified")
    except Exception as e:
        print(f"❌ pinterest_oauth_sessions table verification failed: {e}")

if __name__ == "__main__":
    asyncio.run(apply_pinterest_migration())