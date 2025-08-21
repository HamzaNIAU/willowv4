#!/usr/bin/env python3
"""Apply the MCP toggles migration to Supabase"""

import asyncio
import sys
import os
sys.path.append('/app')

from services.supabase import DBConnection
from utils.logger import logger

async def apply_migration():
    try:
        db = DBConnection()
        client = await db.client
        
        # Check if the table already exists
        check_query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'agent_mcp_toggles'
        );
        """
        
        result = await client.rpc('exec_sql', {'sql': check_query}).execute()
        
        if result.data and result.data[0].get('exists'):
            logger.info("Table agent_mcp_toggles already exists")
            return True
        
        # Create the table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS agent_mcp_toggles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
            user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
            mcp_id TEXT NOT NULL,
            enabled BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(agent_id, user_id, mcp_id)
        );
        """
        
        await client.rpc('exec_sql', {'sql': create_table_sql}).execute()
        logger.info("Table agent_mcp_toggles created")
        
        # Create indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_agent_mcp_toggles_agent_id ON agent_mcp_toggles(agent_id);",
            "CREATE INDEX IF NOT EXISTS idx_agent_mcp_toggles_user_id ON agent_mcp_toggles(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_agent_mcp_toggles_mcp_id ON agent_mcp_toggles(mcp_id);",
            "CREATE INDEX IF NOT EXISTS idx_agent_mcp_toggles_enabled ON agent_mcp_toggles(enabled);"
        ]
        
        for idx_sql in indexes:
            await client.rpc('exec_sql', {'sql': idx_sql}).execute()
        
        logger.info("Indexes created")
        
        # Enable RLS
        rls_sql = "ALTER TABLE agent_mcp_toggles ENABLE ROW LEVEL SECURITY;"
        await client.rpc('exec_sql', {'sql': rls_sql}).execute()
        logger.info("RLS enabled")
        
        # Create policies
        policies = [
            """
            CREATE POLICY "Users can manage their own MCP toggles" ON agent_mcp_toggles
            FOR ALL USING (auth.uid() = user_id);
            """,
            """
            CREATE POLICY "Service role can manage all MCP toggles" ON agent_mcp_toggles
            FOR ALL USING (auth.jwt()->>'role' = 'service_role');
            """
        ]
        
        for policy_sql in policies:
            try:
                await client.rpc('exec_sql', {'sql': policy_sql}).execute()
            except Exception as e:
                logger.warning(f"Policy may already exist: {e}")
        
        logger.info("Policies created")
        
        # Create trigger function
        trigger_func_sql = """
        CREATE OR REPLACE FUNCTION update_agent_mcp_toggles_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
        
        await client.rpc('exec_sql', {'sql': trigger_func_sql}).execute()
        logger.info("Trigger function created")
        
        # Create trigger
        trigger_sql = """
        CREATE TRIGGER update_agent_mcp_toggles_updated_at
        BEFORE UPDATE ON agent_mcp_toggles
        FOR EACH ROW
        EXECUTE FUNCTION update_agent_mcp_toggles_updated_at();
        """
        
        try:
            await client.rpc('exec_sql', {'sql': trigger_sql}).execute()
            logger.info("Trigger created")
        except Exception as e:
            logger.warning(f"Trigger may already exist: {e}")
        
        # Grant permissions
        grant_sql = """
        GRANT ALL ON agent_mcp_toggles TO authenticated;
        GRANT ALL ON agent_mcp_toggles TO service_role;
        """
        
        await client.rpc('exec_sql', {'sql': grant_sql}).execute()
        logger.info("Permissions granted")
        
        logger.info("Migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        # Try alternative approach - direct table operations
        try:
            db = DBConnection()
            client = await db.client
            
            # Try to create table using Supabase's table API if available
            logger.info("Attempting alternative migration approach...")
            
            # Check if table exists by trying to query it
            try:
                test_result = await client.table('agent_mcp_toggles').select('id').limit(1).execute()
                logger.info("Table agent_mcp_toggles already exists (verified by query)")
                return True
            except Exception:
                logger.error("Table doesn't exist and couldn't be created via RPC")
                logger.error("Please run the migration manually in Supabase dashboard")
                return False
                
        except Exception as e2:
            logger.error(f"Alternative approach also failed: {e2}")
            return False

if __name__ == "__main__":
    success = asyncio.run(apply_migration())
    exit(0 if success else 1)