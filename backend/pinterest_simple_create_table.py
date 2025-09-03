#!/usr/bin/env python3
"""Simple Pinterest table creation"""
import asyncio
from services.supabase import DBConnection

async def create_pinterest_tables():
    db = DBConnection()
    await db.initialize()
    client = await db.client
    
    # Create basic Pinterest accounts table
    create_accounts_sql = """
    CREATE TABLE IF NOT EXISTS pinterest_accounts (
        id VARCHAR PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
        username VARCHAR NOT NULL,
        name VARCHAR NOT NULL,
        profile_image_url VARCHAR,
        access_token TEXT NOT NULL,
        refresh_token TEXT,
        token_expires_at TIMESTAMP NOT NULL,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """
    
    # Create OAuth sessions table
    create_sessions_sql = """
    CREATE TABLE IF NOT EXISTS pinterest_oauth_sessions (
        state VARCHAR PRIMARY KEY,
        session_data TEXT NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        expires_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '10 minutes'
    );
    """
    
    try:
        print("Creating pinterest_accounts table...")
        # Use raw SQL execution
        await client.rpc('exec_sql', {'sql': create_accounts_sql}).execute()
        print("✅ pinterest_accounts table created")
    except Exception as e:
        print(f"pinterest_accounts: {e}")
    
    try:
        print("Creating pinterest_oauth_sessions table...")
        await client.rpc('exec_sql', {'sql': create_sessions_sql}).execute()
        print("✅ pinterest_oauth_sessions table created")
    except Exception as e:
        print(f"pinterest_oauth_sessions: {e}")

if __name__ == "__main__":
    asyncio.run(create_pinterest_tables())