#!/usr/bin/env python3
"""
Comprehensive Social Media Integration Test
Validates all platform implementations and Supabase setup
"""

import asyncio
import os
import sys
from typing import Dict, Any
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import logger
from services.supabase import DBConnection


class SocialMediaIntegrationValidator:
    """Validates all social media platform integrations"""
    
    def __init__(self):
        self.db = DBConnection()
        self.platforms = {
            'youtube': {'module': 'youtube_mcp', 'tool': 'youtube_complete_mcp_tool'},
            'twitter': {'module': 'twitter_mcp', 'tool': 'twitter_complete_mcp_tool'},
            'instagram': {'module': 'instagram_mcp', 'tool': 'instagram_complete_mcp_tool'},
            'linkedin': {'module': 'linkedin_mcp', 'tool': 'linkedin_complete_mcp_tool'},
            'pinterest': {'module': 'pinterest_mcp', 'tool': 'pinterest_complete_mcp_tool'},
            'tiktok': {'module': 'tiktok_mcp', 'tool': 'tiktok_complete_mcp_tool'}
        }
        
    async def run_validation(self):
        """Run complete validation suite"""
        print("🔍 Starting Complete Social Media Integration Validation\n")
        
        results = {
            'environment_variables': await self.validate_environment_variables(),
            'database_setup': await self.validate_database_setup(),
            'platform_modules': await self.validate_platform_modules(),
            'api_registration': await self.validate_api_registration(),
            'tool_registration': await self.validate_tool_registration(),
            'agent_configuration': await self.validate_agent_configuration()
        }
        
        # Print summary
        print("\n" + "="*80)
        print("📊 VALIDATION SUMMARY")
        print("="*80)
        
        total_checks = 0
        passed_checks = 0
        
        for category, tests in results.items():
            category_name = category.replace('_', ' ').title()
            print(f"\n{category_name}:")
            for test_name, passed in tests.items():
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"  {test_name}: {status}")
                total_checks += 1
                if passed:
                    passed_checks += 1
        
        print(f"\n📈 Overall Score: {passed_checks}/{total_checks} ({int(passed_checks/total_checks*100)}%)")
        
        if passed_checks == total_checks:
            print("\n🎉 ALL VALIDATIONS PASSED - SOCIAL MEDIA SYSTEM IS READY!")
        else:
            print(f"\n⚠️  {total_checks - passed_checks} validation(s) failed - see details above")
        
        return passed_checks == total_checks

    async def validate_environment_variables(self) -> Dict[str, bool]:
        """Validate all required environment variables"""
        print("🔧 Validating Environment Variables...")
        
        results = {}
        
        # Check platform-specific credentials
        platform_vars = {
            'Twitter': ['TWITTER_CLIENT_ID', 'TWITTER_CLIENT_SECRET', 'TWITTER_API_KEY', 'TWITTER_BEARER_TOKEN'],
            'Instagram': ['INSTAGRAM_APP_ID', 'INSTAGRAM_APP_SECRET', 'INSTAGRAM_ACCESS_TOKEN'],
            'LinkedIn': ['LINKEDIN_CLIENT_ID', 'LINKEDIN_CLIENT_SECRET'],
            'Pinterest': ['PINTEREST_CLIENT_ID', 'PINTEREST_CLIENT_SECRET'],
            'TikTok': ['TIKTOK_CLIENT_KEY', 'TIKTOK_CLIENT_SECRET']
        }
        
        for platform, vars_list in platform_vars.items():
            platform_complete = True
            for var in vars_list:
                if not os.getenv(var):
                    platform_complete = False
                    break
            results[f'{platform} credentials'] = platform_complete
        
        # Check shared credentials
        results['MCP encryption key'] = bool(os.getenv('MCP_CREDENTIAL_ENCRYPTION_KEY'))
        results['Supabase JWT secret'] = bool(os.getenv('SUPABASE_JWT_SECRET'))
        
        return results

    async def validate_database_setup(self) -> Dict[str, bool]:
        """Validate database tables and migrations"""
        print("🗄️ Validating Database Setup...")
        
        results = {}
        
        try:
            await self.db.initialize()
            
            # Check core tables exist
            core_tables = [
                'agent_social_accounts',
                'video_file_references',
                'upload_references'
            ]
            
            for table in core_tables:
                try:
                    await self.db.fetch_one(f"SELECT 1 FROM {table} LIMIT 1")
                    results[f'Core table: {table}'] = True
                except Exception:
                    results[f'Core table: {table}'] = False
            
            # Check platform-specific tables
            platform_tables = [
                'youtube_channels',
                'twitter_accounts', 
                'instagram_accounts',
                'linkedin_accounts',
                'pinterest_accounts',
                'tiktok_accounts'
            ]
            
            for table in platform_tables:
                try:
                    await self.db.fetch_one(f"SELECT 1 FROM {table} LIMIT 1")
                    results[f'Platform table: {table}'] = True
                except Exception:
                    results[f'Platform table: {table}'] = False
            
        except Exception as e:
            logger.error(f"Database validation failed: {e}")
            results['Database connection'] = False
        
        return results

    async def validate_platform_modules(self) -> Dict[str, bool]:
        """Validate platform module imports"""
        print("📦 Validating Platform Modules...")
        
        results = {}
        
        for platform_name, platform_info in self.platforms.items():
            try:
                # Test module import
                module_name = platform_info['module']
                exec(f"import {module_name}.api")
                exec(f"import {module_name}.oauth") 
                exec(f"import {module_name}.service")
                exec(f"import {module_name}.upload")
                exec(f"import {module_name}.accounts")
                results[f'{platform_name.title()} module import'] = True
            except Exception as e:
                logger.warning(f"Failed to import {platform_name} module: {e}")
                results[f'{platform_name.title()} module import'] = False
                
            try:
                # Test tool import
                tool_name = platform_info['tool'] 
                exec(f"from agent.tools.{tool_name} import *")
                results[f'{platform_name.title()} tool import'] = True
            except Exception as e:
                logger.warning(f"Failed to import {platform_name} tool: {e}")
                results[f'{platform_name.title()} tool import'] = False
        
        return results

    async def validate_api_registration(self) -> Dict[str, bool]:
        """Validate API router registration"""
        print("🔌 Validating API Registration...")
        
        results = {}
        
        try:
            # Check main API file contains platform imports
            with open('api.py', 'r') as f:
                api_content = f.read()
            
            platform_apis = [
                'youtube_mcp',
                'twitter_mcp',
                'instagram_mcp', 
                'linkedin_mcp',
                'pinterest_mcp',
                'tiktok_mcp'
            ]
            
            for api_name in platform_apis:
                has_import = f"from {api_name} import api" in api_content
                has_registration = f"{api_name.replace('_mcp', '_api')}.initialize(db)" in api_content
                has_router = f"api_router.include_router({api_name.replace('_mcp', '_api')}.router)" in api_content
                
                platform_name = api_name.replace('_mcp', '').title()
                results[f'{platform_name} API registered'] = has_import and has_registration and has_router
                
        except Exception as e:
            logger.error(f"API registration validation failed: {e}")
            for platform in self.platforms.keys():
                results[f'{platform.title()} API registered'] = False
        
        return results

    async def validate_tool_registration(self) -> Dict[str, bool]:
        """Validate tool registration in agent system"""
        print("🔧 Validating Tool Registration...")
        
        results = {}
        
        try:
            # Check run.py contains tool registrations
            with open('agent/run.py', 'r') as f:
                run_content = f.read()
            
            for platform_name in self.platforms.keys():
                tool_check = f"{platform_name}_tool" in run_content
                import_check = f"from agent.tools.{platform_name}_complete_mcp_tool import" in run_content
                register_check = f"Complete {platform_name.title()} MCP Tool" in run_content
                
                results[f'{platform_name.title()} tool registration'] = tool_check and import_check and register_check
                
        except Exception as e:
            logger.error(f"Tool registration validation failed: {e}")
            for platform in self.platforms.keys():
                results[f'{platform.title()} tool registration'] = False
        
        return results

    async def validate_agent_configuration(self) -> Dict[str, bool]:
        """Validate agent configuration includes all tools"""
        print("⚙️ Validating Agent Configuration...")
        
        results = {}
        
        try:
            from agent.suna_config import SUNA_CONFIG
            
            agentpress_tools = SUNA_CONFIG.get('agentpress_tools', {})
            
            expected_tools = [
                'youtube_tool',
                'twitter_tool', 
                'instagram_tool',
                'linkedin_tool',
                'pinterest_tool',
                'tiktok_tool'
            ]
            
            for tool in expected_tools:
                platform_name = tool.replace('_tool', '').title()
                results[f'{platform_name} tool in Suna config'] = agentpress_tools.get(tool, False)
                
        except Exception as e:
            logger.error(f"Agent configuration validation failed: {e}")
            for platform in self.platforms.keys():
                results[f'{platform.title()} tool in Suna config'] = False
        
        return results


async def main():
    """Run the complete validation suite"""
    validator = SocialMediaIntegrationValidator()
    success = await validator.run_validation()
    
    if success:
        print("\n🚀 System is ready for social media integrations!")
        return 0
    else:
        print("\n🔧 Some issues found - please review and fix before deployment")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)