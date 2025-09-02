#!/usr/bin/env python3
"""
Script to set feature flags in Redis for temporary agent management access
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from flags.flags import set_flag, list_flags
from utils.logger import logger

async def main():
    logger.info("Setting feature flags in Redis...")
    
    # Enable custom agents temporarily for cleanup
    await set_flag("custom_agents", True, "Temporarily enabled for cleanup")
    
    # Enable default agent
    await set_flag("default_agent", True, "Suna default agent")
    
    # Disable hide_agent_creation to show agents menu
    await set_flag("hide_agent_creation", False, "Show agents menu for cleanup")
    
    # Enable agent marketplace
    await set_flag("agent_marketplace", True, "Agent marketplace features")
    
    # List all flags to confirm
    flags = await list_flags()
    logger.info("Current feature flags:")
    for key, enabled in flags.items():
        logger.info(f"  {key}: {enabled}")
    
    logger.info("✅ Feature flags set successfully!")
    logger.info("The agents page should now be accessible at http://localhost:3000/agents")

if __name__ == "__main__":
    asyncio.run(main())