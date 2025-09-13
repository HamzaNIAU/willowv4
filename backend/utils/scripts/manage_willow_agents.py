#!/usr/bin/env python3
"""
Willow Default Agent Management Script (Simplified)

This script provides administrative functions for managing Willow default agents across all users.

Usage:
    # 🚀 MAIN COMMANDS
    python manage_willow_agents.py install-all          # Install Willow for all users who don't have it
    python manage_willow_agents.py stats                # Show Willow agent statistics
    python manage_willow_agents.py install-user <id>    # Install Willow for specific user

Examples:
    python manage_willow_agents.py install-all
    python manage_willow_agents.py stats
    python manage_willow_agents.py install-user 123e4567-e89b-12d3-a456-426614174000

Note: Sync is no longer needed - Willow agents automatically use the current configuration from config.py
"""

import asyncio
import argparse
import sys
import json
from pathlib import Path

# Add the backend directory to the path so we can import modules
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from utils.willow_default_agent_service import WillowDefaultAgentService
from services.supabase import DBConnection
from utils.logger import logger


class WillowAgentManager:
    def __init__(self):
        self.service = WillowDefaultAgentService()
    
    async def install_all_users(self):
        """Install Willow agent for all users who don't have it"""
        print("🚀 Installing Willow default agent for all users who don't have it...")
        
        result = await self.service.install_for_all_users()
        
        print(f"✅ Installation completed!")
        print(f"   📦 Installed: {result['installed_count']}")
        print(f"   ❌ Failed: {result['failed_count']}")
        
        if result['failed_count'] > 0:
            print("\n❌ Failed installations:")
            for detail in result['details']:
                if detail['status'] == 'failed':
                    print(f"   - User {detail['account_id']}: {detail.get('error', 'Unknown error')}")
        
        if result['installed_count'] > 0:
            print(f"\n✅ Successfully installed Willow for {result['installed_count']} users")
            
    async def update_config_info(self):
        """Show information about Willow configuration (no sync needed)"""
        print("ℹ️  Willow Configuration Information")
        print("=" * 50)
        print("🔧 Willow agents automatically use the current configuration from config.py")
        print("📝 No sync needed - changes are applied immediately when agents run")
        print("💡 To update Willow behavior, simply modify backend/agent/suna/config.py")
        print("\n✅ All Willow agents are always up-to-date with your latest configuration!")
    
    async def install_user(self, account_id):
        """Install Willow agent for specific user"""
        print(f"🚀 Installing Willow default agent for user {account_id}...")
        
        agent_id = await self.service.install_suna_agent_for_user(account_id)
        
        if agent_id:
            print(f"✅ Successfully installed Willow agent {agent_id} for user {account_id}")
        else:
            print(f"❌ Failed to install Willow agent for user {account_id}")
    
    async def replace_user_agent(self, account_id):
        """Replace Willow agent for specific user (in case of corruption)"""
        print(f"🔄 Replacing Willow agent for user {account_id}...")
        
        # Install/replace the agent with latest config
        agent_id = await self.service.install_suna_agent_for_user(account_id, replace_existing=True)
        
        if agent_id:
            print(f"✅ Successfully replaced Willow agent {agent_id} for user {account_id}")
        else:
            print(f"❌ Failed to replace Willow agent for user {account_id}")
    
    async def show_stats(self):
        """Show Willow agent statistics"""
        print("📊 Willow Default Agent Statistics")
        print("=" * 50)
        
        stats = await self.service.get_suna_agent_stats()
        
        if 'error' in stats:
            print(f"❌ Error getting stats: {stats['error']}")
            return
        
        print(f"Total Agents: {stats.get('total_agents', 0)}")
        print(f"Active Agents: {stats.get('active_agents', 0)}")
        print(f"Inactive Agents: {stats.get('inactive_agents', 0)}")
        
        version_dist = stats.get('version_distribution', {})
        if version_dist:
            print(f"\nVersion Distribution:")
            for version, count in version_dist.items():
                print(f"  {version}: {count} agents")
        
        creation_dates = stats.get('creation_dates', {})
        if creation_dates:
            print(f"\nCreation Dates (Last 12 months):")
            for month, count in sorted(creation_dates.items(), reverse=True):
                print(f"  {month}: {count} agents")


async def main():
    parser = argparse.ArgumentParser(
        description="Manage Willow default agents across all users (Simplified)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Main commands
    subparsers.add_parser('install-all', help='Install Willow agent for all users who don\'t have it')
    subparsers.add_parser('stats', help='Show Willow agent statistics')
    subparsers.add_parser('config-info', help='Show information about Willow configuration')
    
    # User-specific commands
    install_user_parser = subparsers.add_parser('install-user', help='Install Willow agent for specific user')
    install_user_parser.add_argument('account_id', help='Account ID to install Willow for')
    
    replace_user_parser = subparsers.add_parser('replace-user', help='Replace Willow agent for specific user (if corrupted)')
    replace_user_parser.add_argument('account_id', help='Account ID to replace Willow for')
    
    # Legacy commands (deprecated but still functional)
    subparsers.add_parser('sync', help='[DEPRECATED] No longer needed - config is always current')
    subparsers.add_parser('update-all', help='[DEPRECATED] No longer needed - config is always current')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = WillowAgentManager()
    
    try:
        if args.command == 'install-all':
            await manager.install_all_users()
        elif args.command == 'stats':
            await manager.show_stats()
        elif args.command == 'config-info':
            await manager.update_config_info()
        elif args.command == 'install-user':
            await manager.install_user(args.account_id)
        elif args.command == 'replace-user':
            await manager.replace_user_agent(args.account_id)
        elif args.command == 'sync':
            print("⚠️  DEPRECATED: Sync is no longer needed!")
            await manager.update_config_info()
        elif args.command == 'update-all':
            print("⚠️  DEPRECATED: Update-all is no longer needed!")
            await manager.update_config_info()
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        logger.error(f"Script error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main()) 