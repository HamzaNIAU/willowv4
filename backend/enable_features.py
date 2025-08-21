#!/usr/bin/env python3
"""Enable all feature flags for local development"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flags.flags import FeatureFlagManager

async def enable_all_features():
    """Enable all feature flags"""
    manager = FeatureFlagManager()
    
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
        success = await manager.set_flag(flag_name, True, description)
        if success:
            print(f"✅ Enabled: {flag_name}")
        else:
            print(f"❌ Failed to enable: {flag_name}")
    
    # List all flags
    print("\nCurrent feature flags status:")
    flags = await manager.list_flags()
    for flag, enabled in flags.items():
        status = "✅" if enabled else "❌"
        print(f"  {status} {flag}: {enabled}")

if __name__ == "__main__":
    asyncio.run(enable_all_features())