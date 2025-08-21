#!/usr/bin/env python3
"""Test MCP toggles with local Supabase"""

import asyncio
from supabase import create_client
import uuid

# Local Supabase credentials
SUPABASE_URL = "http://127.0.0.1:54321"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"

async def test_mcp_toggles():
    # Create Supabase client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Create test data
    test_agent_id = str(uuid.uuid4())
    test_user_id = str(uuid.uuid4())
    
    # First create a test agent
    agent_result = supabase.table('agents').insert({
        'agent_id': test_agent_id,
        'account_id': str(uuid.uuid4()),
        'name': 'Test Agent',
        'system_prompt': 'Test prompt',
        'configured_mcps': [],
        'agentpress_tools': {}
    }).execute()
    
    print(f"Created test agent: {test_agent_id}")
    
    # Create a test user (we'll use a dummy UUID since auth.users is protected)
    # In production, this would be a real user ID from auth
    
    # Test inserting MCP toggle
    toggle_result = supabase.table('agent_mcp_toggles').insert({
        'agent_id': test_agent_id,
        'user_id': test_user_id,
        'mcp_id': 'social.youtube.channel123',
        'enabled': True
    }).execute()
    
    print(f"Created toggle: {toggle_result.data}")
    
    # Test updating toggle
    update_result = supabase.table('agent_mcp_toggles').update({
        'enabled': False
    }).eq('agent_id', test_agent_id).eq('user_id', test_user_id).eq('mcp_id', 'social.youtube.channel123').execute()
    
    print(f"Updated toggle: {update_result.data}")
    
    # Test querying toggles
    query_result = supabase.table('agent_mcp_toggles').select('*').eq('agent_id', test_agent_id).execute()
    
    print(f"Queried toggles: {query_result.data}")
    
    # Clean up
    supabase.table('agent_mcp_toggles').delete().eq('agent_id', test_agent_id).execute()
    supabase.table('agents').delete().eq('agent_id', test_agent_id).execute()
    
    print("Test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_mcp_toggles())