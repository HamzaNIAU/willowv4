#!/usr/bin/env python3
"""Configure single agent mode - hide agent creation while keeping agent features"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flags.flags import FeatureFlagManager

async def configure_single_agent_mode(enable: bool = True):
    """Configure the system for single agent mode"""
    manager = FeatureFlagManager()
    
    if enable:
        print("🔧 Configuring single agent mode...")
        print("This will:")
        print("  - Keep custom agents features enabled (Knowledge, Triggers, etc.)")
        print("  - Show only the default Willow agent")
        print("  - Hide agent creation UI")
        print("  - Hide agents page\n")
        
        # Enable necessary flags
        flags_to_set = [
            ("custom_agents", True, "Keep custom agents functionality for features"),
            ("default_agent", True, "Enable default Willow agent"),
            ("hide_agent_creation", True, "Hide agent creation UI elements"),
            # Keep other important flags enabled
            ("knowledge_base", True, "Enable knowledge base"),
            ("triggers", True, "Enable triggers functionality"),
            ("agent_triggers", True, "Enable agent triggers functionality"),
        ]
        
    else:
        print("🔧 Disabling single agent mode...")
        print("This will:")
        print("  - Re-enable agent creation UI")
        print("  - Show agents page")
        print("  - Allow creating custom agents\n")
        
        flags_to_set = [
            ("hide_agent_creation", False, "Show agent creation UI elements"),
            # Keep other flags as they were
        ]
    
    for flag_name, value, description in flags_to_set:
        success = await manager.set_flag(flag_name, value, description)
        if success:
            status = "✅ Enabled" if value else "❌ Disabled"
            print(f"{status}: {flag_name}")
        else:
            print(f"⚠️ Failed to set: {flag_name}")
    
    print("\n📋 Current relevant flags:")
    relevant_flags = [
        "custom_agents",
        "default_agent", 
        "hide_agent_creation",
        "knowledge_base",
        "triggers",
        "agent_triggers"
    ]
    
    for flag in relevant_flags:
        enabled = await manager.is_enabled(flag)
        status = "✅" if enabled else "❌"
        print(f"  {status} {flag}: {enabled}")

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Configure single agent mode")
    parser.add_argument(
        "--disable",
        action="store_true",
        help="Disable single agent mode and re-enable agent creation"
    )
    args = parser.parse_args()
    
    await configure_single_agent_mode(enable=not args.disable)

if __name__ == "__main__":
    asyncio.run(main())