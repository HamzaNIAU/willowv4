#!/usr/bin/env python3
"""Enable all feature flags for local development with localhost Redis"""

import asyncio
import redis.asyncio as redis

async def enable_all_features():
    """Enable all feature flags"""
    # Connect directly to Redis on localhost:6380
    client = redis.Redis(host='localhost', port=6380, decode_responses=True)
    
    flag_prefix = "feature_flag:"
    flag_list_key = "feature_flags:list"
    
    features = [
        ("custom_agents", "Enable custom agents functionality"),
        ("agent_marketplace", "Enable agent marketplace"),
        ("default_agent", "Enable default agent selection"),
        ("triggers", "Enable triggers functionality"),
        ("agent_triggers", "Enable agent triggers functionality"),
        ("knowledge_base", "Enable knowledge base"),
        ("mcp_servers", "Enable MCP servers"),
        ("composio_integration", "Enable Composio integration"),
        ("pipedream_integration", "Enable Pipedream integration"),
    ]
    
    for flag_name, description in features:
        try:
            flag_key = f"{flag_prefix}{flag_name}"
            flag_data = {
                'enabled': 'true',
                'description': description,
                'updated_at': '2025-01-18T00:00:00'
            }
            
            await client.hset(flag_key, mapping=flag_data)
            await client.sadd(flag_list_key, flag_name)
            print(f"✅ Enabled: {flag_name}")
        except Exception as e:
            print(f"❌ Failed to enable {flag_name}: {e}")
    
    # List all flags
    print("\nCurrent feature flags status:")
    try:
        flag_keys = await client.smembers(flag_list_key)
        for key in flag_keys:
            flag_key = f"{flag_prefix}{key}"
            enabled = await client.hget(flag_key, 'enabled')
            status = "✅" if enabled == 'true' else "❌"
            print(f"  {status} {key}: {enabled == 'true'}")
    except Exception as e:
        print(f"Failed to list flags: {e}")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(enable_all_features())