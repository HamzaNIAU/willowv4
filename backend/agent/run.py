import os
import json
import asyncio
import datetime
import jwt
from typing import Optional, Dict, List, Any, AsyncGenerator
from dataclasses import dataclass

from agent.tools.message_tool import MessageTool
from agent.tools.sb_deploy_tool import SandboxDeployTool
from agent.tools.sb_expose_tool import SandboxExposeTool
from agent.tools.web_search_tool import SandboxWebSearchTool
from dotenv import load_dotenv
from utils.config import config
from agent.agent_builder_prompt import get_agent_builder_prompt
from agentpress.thread_manager import ThreadManager
from agentpress.response_processor import ProcessorConfig
from agent.tools.sb_shell_tool import SandboxShellTool
from agent.tools.sb_files_tool import SandboxFilesTool
from agent.tools.data_providers_tool import DataProvidersTool
from agent.tools.expand_msg_tool import ExpandMessageTool
from agent.prompt import get_system_prompt

from utils.logger import logger
from utils.auth_utils import get_account_id_from_thread, _get_user_id_from_account_cached
from services.billing import check_billing_status
from agent.tools.sb_vision_tool import SandboxVisionTool
from agent.tools.sb_image_edit_tool import SandboxImageEditTool
from agent.tools.sb_presentation_outline_tool import SandboxPresentationOutlineTool
from agent.tools.sb_presentation_tool_v2 import SandboxPresentationToolV2
from services.langfuse import langfuse
from langfuse.client import StatefulTraceClient

from agent.tools.mcp_tool_wrapper import MCPToolWrapper
from agent.tools.task_list_tool import TaskListTool
from agentpress.tool import SchemaType
from agent.tools.sb_sheets_tool import SandboxSheetsTool
from agent.tools.sb_web_dev_tool import SandboxWebDevTool
from agent.tools.youtube_complete_mcp_tool import YouTubeTool
from agent.tools.twitter_complete_mcp_tool import TwitterTool
from agent.tools.instagram_complete_mcp_tool import InstagramTool
from agent.tools.pinterest_complete_mcp_tool import PinterestTool

load_dotenv()


@dataclass
class AgentConfig:
    thread_id: str
    project_id: str
    stream: bool
    native_max_auto_continues: int = 25
    max_iterations: int = 100
    model_name: str = "openrouter/moonshotai/kimi-k2"
    enable_thinking: Optional[bool] = False
    reasoning_effort: Optional[str] = 'low'
    enable_context_manager: bool = True
    agent_config: Optional[dict] = None
    trace: Optional[StatefulTraceClient] = None
    is_agent_builder: Optional[bool] = False
    target_agent_id: Optional[str] = None


class ToolManager:
    def __init__(self, thread_manager: ThreadManager, project_id: str, thread_id: str, user_id: Optional[str] = None, agent_id: Optional[str] = None, agent_config: Optional[dict] = None):
        self.thread_manager = thread_manager
        self.project_id = project_id
        self.thread_id = thread_id
        self.user_id = user_id
        self.agent_id = agent_id
        self.agent_config = agent_config
    
    async def register_all_tools(self, agent_id: Optional[str] = None, disabled_tools: Optional[List[str]] = None):
        """Register all available tools by default, with optional exclusions.
        
        Args:
            agent_id: Optional agent ID for agent builder tools
            disabled_tools: List of tool names to exclude from registration
        """
        disabled_tools = disabled_tools or []
        
        logger.debug(f"Registering tools with disabled list: {disabled_tools}")
        
        # Core tools - always enabled
        self._register_core_tools()
        
        # Sandbox tools
        self._register_sandbox_tools(disabled_tools)
        
        # Data and utility tools
        await self._register_utility_tools(disabled_tools)
        
        # Agent builder tools - register if agent_id provided
        if agent_id:
            self._register_agent_builder_tools(agent_id, disabled_tools)
        
        # Browser tool
        self._register_browser_tool(disabled_tools)
        
        registered_tools = list(self.thread_manager.tool_registry.tools.keys())
        logger.info(f"🔧 Tool registration complete. Total tools: {len(registered_tools)}")
        logger.info(f"🔧 Registered tools: {registered_tools}")
        
        # Specifically check for social media tool registration visibility
        def _log_platform(name: str):
            matched = [t for t in registered_tools if name in t.lower()]
            if matched:
                logger.info(f"✅ {name.capitalize()} tools registered: {matched}")
            else:
                logger.warning(f"⚠️ No {name.capitalize()} tools found in registry")

        for platform in [
            'youtube', 'twitter', 'instagram', 'pinterest', 'linkedin', 'tiktok'
        ]:
            _log_platform(platform)
        
        # Return YouTube channels for use in system prompt
        return getattr(self, 'youtube_channels', [])
    
    def _register_core_tools(self):
        """Register core tools that are always available."""
        self.thread_manager.add_tool(ExpandMessageTool, thread_id=self.thread_id, thread_manager=self.thread_manager)
        self.thread_manager.add_tool(MessageTool)
        self.thread_manager.add_tool(TaskListTool, project_id=self.project_id, thread_manager=self.thread_manager, thread_id=self.thread_id)
    
    def _register_sandbox_tools(self, disabled_tools: List[str]):
        """Register sandbox-related tools."""
        sandbox_tools = [
            ('sb_shell_tool', SandboxShellTool, {'project_id': self.project_id, 'thread_manager': self.thread_manager}),
            ('sb_files_tool', SandboxFilesTool, {'project_id': self.project_id, 'thread_manager': self.thread_manager}),
            ('sb_deploy_tool', SandboxDeployTool, {'project_id': self.project_id, 'thread_manager': self.thread_manager}),
            ('sb_expose_tool', SandboxExposeTool, {'project_id': self.project_id, 'thread_manager': self.thread_manager}),
            ('web_search_tool', SandboxWebSearchTool, {'project_id': self.project_id, 'thread_manager': self.thread_manager}),
            ('sb_vision_tool', SandboxVisionTool, {'project_id': self.project_id, 'thread_id': self.thread_id, 'thread_manager': self.thread_manager}),
            ('sb_image_edit_tool', SandboxImageEditTool, {'project_id': self.project_id, 'thread_id': self.thread_id, 'thread_manager': self.thread_manager}),
            ('sb_presentation_outline_tool', SandboxPresentationOutlineTool, {'project_id': self.project_id, 'thread_manager': self.thread_manager}),
            ('sb_presentation_tool_v2', SandboxPresentationToolV2, {'project_id': self.project_id, 'thread_manager': self.thread_manager}),
            ('sb_sheets_tool', SandboxSheetsTool, {'project_id': self.project_id, 'thread_manager': self.thread_manager}),
            ('sb_web_dev_tool', SandboxWebDevTool, {'project_id': self.project_id, 'thread_id': self.thread_id, 'thread_manager': self.thread_manager}),
        ]
        
        for tool_name, tool_class, kwargs in sandbox_tools:
            if tool_name not in disabled_tools:
                self.thread_manager.add_tool(tool_class, **kwargs)
                logger.debug(f"Registered {tool_name}")
    
    async def _register_utility_tools(self, disabled_tools: List[str]):
        """Register utility and data provider tools."""
        if config.RAPID_API_KEY and 'data_providers_tool' not in disabled_tools:
            self.thread_manager.add_tool(DataProvidersTool)
            logger.debug("Registered data_providers_tool")
        
        # Register YouTube sandbox tool if not disabled
        if 'youtube_tool' not in disabled_tools:
            # Use pre-computed YouTube channels from agent config or fallback to database
            channel_ids = []
            channel_metadata = []
            db = None  # Initialize db variable
            
            # Check if we have pre-computed channels from agent config
            logger.debug(f"Checking for pre-computed channels - agent_config exists: {self.agent_config is not None}, agent_id: {self.agent_id}")
            if self.agent_config:
                logger.debug(f"Agent config keys: {list(self.agent_config.keys())}")
                if 'youtube_channels' in self.agent_config:
                    logger.debug(f"Found 'youtube_channels' key in agent_config")
                else:
                    logger.debug(f"No 'youtube_channels' key in agent_config")
            
            if self.agent_config and 'youtube_channels' in self.agent_config:
                channel_metadata = self.agent_config['youtube_channels']
                channel_ids = [channel['id'] for channel in channel_metadata]
                if channel_ids:
                    logger.info(f"✅ Using pre-computed YouTube channels from agent config: {len(channel_ids)} channels for agent {self.agent_id}")
                    for channel in channel_metadata:
                        logger.debug(f"   - Pre-computed channel: {channel.get('name')} ({channel.get('id')})")
                else:
                    logger.info(f"⚠️ Pre-computed channels list is empty in agent config for agent {self.agent_id}")
            else:
                # Universal system: fetch YouTube integrations and precompute metadata
                logger.info("Using universal integrations to precompute YouTube channels for tool registration")
                from services.supabase import DBConnection
                from services.unified_integration_service import UnifiedIntegrationService
                db = DBConnection()

                try:
                    integration_service = UnifiedIntegrationService(db)
                    if self.user_id and self.agent_id:
                        integrations = await integration_service.get_agent_integrations(self.agent_id, self.user_id, platform="youtube")
                    elif self.user_id:
                        integrations = await integration_service.get_user_integrations(self.user_id, platform="youtube")
                    else:
                        integrations = []

                    # Map to channel-like metadata the tool expects
                    channel_metadata = []
                    for integ in integrations:
                        pdata = integ.get('platform_data', {})
                        channel_metadata.append({
                            'id': integ['platform_account_id'],
                            'name': integ.get('cached_name') or integ['name'],
                            'username': pdata.get('username'),
                            'profile_picture': integ.get('cached_picture') or integ.get('picture'),
                            'subscriber_count': pdata.get('subscriber_count', 0),
                            'view_count': pdata.get('view_count', 0),
                            'video_count': pdata.get('video_count', 0),
                        })
                    channel_ids = [c['id'] for c in channel_metadata]
                    logger.info(f"Loaded {len(channel_ids)} YouTube channels from universal integrations")
                except Exception as e:
                    logger.warning(f"Could not load YouTube channels from universal integrations: {e}")
            
            # Ensure db is available for YouTubeTool (create if not already created)
            if db is None:
                from services.supabase import DBConnection
                db = DBConnection()
            
            # Store channel metadata for later use in system prompt
            self.youtube_channels = channel_metadata
            
            # Create JWT token for YouTube tool API calls
            jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "")
            jwt_token = None
            if jwt_secret and self.user_id:
                payload = {
                    "sub": self.user_id,
                    "user_id": self.user_id,
                    "role": "authenticated"
                }
                jwt_token = jwt.encode(payload, jwt_secret, algorithm="HS256")
                logger.debug(f"Created JWT token for YouTube tool")
            
            # Register complete YouTube MCP tool (preserves all functionality)
            logger.info(f"🎬 Registering Complete YouTube MCP Tool for agent {self.agent_id}")
            self.thread_manager.add_tool(
                YouTubeTool,
                user_id=self.user_id or "",
                channel_ids=channel_ids,
                channel_metadata=channel_metadata,
                jwt_token=jwt_token,
                agent_id=self.agent_id,
                thread_id=self.thread_id
                # MCP pattern - no sandbox dependencies
            )
            logger.info(f"✅ Successfully registered Complete YouTube MCP Tool with {len(channel_ids)} channels")
        
        # Register Twitter tool if not disabled
        if 'twitter_tool' not in disabled_tools:
            # Use pre-computed Twitter accounts from agent config or fallback to database
            account_ids = []
            account_metadata = []
            db = None
            
            # Check if we have pre-computed accounts from agent config
            logger.debug(f"Checking for pre-computed Twitter accounts - agent_config exists: {self.agent_config is not None}, agent_id: {self.agent_id}")
            if self.agent_config and 'twitter_accounts' in self.agent_config:
                account_metadata = self.agent_config['twitter_accounts']
                account_ids = [account['id'] for account in account_metadata]
                if account_ids:
                    logger.info(f"✅ Using pre-computed Twitter accounts from agent config: {len(account_ids)} accounts for agent {self.agent_id}")
                    for account in account_metadata:
                        logger.debug(f"   - Pre-computed account: {account.get('name')} (@{account.get('username')})")
                else:
                    logger.info(f"⚠️ Pre-computed Twitter accounts list is empty in agent config for agent {self.agent_id}")
            else:
                # Fallback to database fetch (legacy behavior)
                logger.warning(f"No pre-computed Twitter accounts found in agent config, falling back to database fetch")
                from services.supabase import DBConnection
                from twitter_mcp.accounts import TwitterAccountService
                from services.mcp_toggles import MCPToggleService
                db = DBConnection()
                
                try:
                    if self.user_id and self.agent_id:
                        account_service = TwitterAccountService(db)
                        toggle_service = MCPToggleService(db)
                        
                        # Get enabled accounts via MCP toggles
                        enabled_accounts = await account_service.get_accounts_for_agent(self.user_id, self.agent_id)
                        
                        account_ids = [account['id'] for account in enabled_accounts]
                        account_metadata = enabled_accounts
                        
                        if account_ids:
                            logger.info(f"Loaded {len(account_ids)} enabled Twitter accounts from database fallback")
                        else:
                            logger.info(f"No Twitter accounts are enabled for agent {self.agent_id} (fallback)")
                except Exception as e:
                    logger.warning(f"Could not load Twitter accounts from database fallback: {e}")
            
            # Ensure db is available for TwitterTool
            if db is None:
                from services.supabase import DBConnection
                db = DBConnection()
            
            # Store account metadata for later use in system prompt
            self.twitter_accounts = account_metadata
            
            # Create JWT token for Twitter tool API calls
            jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "")
            jwt_token = None
            if jwt_secret and self.user_id:
                payload = {
                    "sub": self.user_id,
                    "user_id": self.user_id,
                    "role": "authenticated"
                }
                jwt_token = jwt.encode(payload, jwt_secret, algorithm="HS256")
                logger.debug(f"Created JWT token for Twitter tool")
            
            # Register complete Twitter MCP tool
            logger.info(f"🐦 Registering Complete Twitter MCP Tool for agent {self.agent_id}")
            self.thread_manager.add_tool(
                TwitterTool,
                user_id=self.user_id or "",
                account_ids=account_ids,
                account_metadata=account_metadata,
                jwt_token=jwt_token,
                agent_id=self.agent_id,
                thread_id=self.thread_id
            )
            logger.info(f"✅ Successfully registered Complete Twitter MCP Tool with {len(account_ids)} accounts")
        
        # Register Instagram tool if not disabled
        if 'instagram_tool' not in disabled_tools:
            # Use pre-computed Instagram accounts from agent config or fallback to database
            account_ids = []
            account_metadata = []
            db = None
            
            # Check if we have pre-computed accounts from agent config
            logger.debug(f"Checking for pre-computed Instagram accounts - agent_config exists: {self.agent_config is not None}, agent_id: {self.agent_id}")
            if self.agent_config and 'instagram_accounts' in self.agent_config:
                account_metadata = self.agent_config['instagram_accounts']
                account_ids = [account['id'] for account in account_metadata]
                if account_ids:
                    logger.info(f"✅ Using pre-computed Instagram accounts from agent config: {len(account_ids)} accounts for agent {self.agent_id}")
                    for account in account_metadata:
                        logger.debug(f"   - Pre-computed account: {account.get('name')} (@{account.get('username')})")
                else:
                    logger.info(f"⚠️ Pre-computed Instagram accounts list is empty in agent config for agent {self.agent_id}")
            else:
                # Fallback to database fetch (legacy behavior)
                logger.warning(f"No pre-computed Instagram accounts found in agent config, falling back to database fetch")
                from services.supabase import DBConnection
                from instagram_mcp.accounts import InstagramAccountService
                from services.mcp_toggles import MCPToggleService
                db = DBConnection()
                
                try:
                    if self.user_id and self.agent_id:
                        account_service = InstagramAccountService(db)
                        toggle_service = MCPToggleService(db)
                        
                        # Get enabled accounts via MCP toggles
                        enabled_accounts = await account_service.get_accounts_for_agent(self.user_id, self.agent_id)
                        
                        account_ids = [account['id'] for account in enabled_accounts]
                        account_metadata = enabled_accounts
                        
                        if account_ids:
                            logger.info(f"Loaded {len(account_ids)} enabled Instagram accounts from database fallback")
                        else:
                            logger.info(f"No Instagram accounts are enabled for agent {self.agent_id} (fallback)")
                except Exception as e:
                    logger.warning(f"Could not load Instagram accounts from database fallback: {e}")
            
            # Ensure db is available for InstagramTool
            if db is None:
                from services.supabase import DBConnection
                db = DBConnection()
            
            # Store account metadata for later use in system prompt
            self.instagram_accounts = account_metadata
            
            # Create JWT token for Instagram tool API calls
            jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "")
            jwt_token = None
            if jwt_secret and self.user_id:
                payload = {
                    "sub": self.user_id,
                    "user_id": self.user_id,
                    "role": "authenticated"
                }
                jwt_token = jwt.encode(payload, jwt_secret, algorithm="HS256")
                logger.debug(f"Created JWT token for Instagram tool")
            
            # Register complete Instagram MCP tool
            logger.info(f"📸 Registering Complete Instagram MCP Tool for agent {self.agent_id}")
            self.thread_manager.add_tool(
                InstagramTool,
                user_id=self.user_id or "",
                account_ids=account_ids,
                account_metadata=account_metadata,
                jwt_token=jwt_token,
                agent_id=self.agent_id,
                thread_id=self.thread_id
            )
            logger.info(f"✅ Successfully registered Complete Instagram MCP Tool with {len(account_ids)} accounts")
        
        # Register Pinterest tool if not disabled
        if 'pinterest_tool' not in disabled_tools:
            # Use pre-computed Pinterest accounts from agent config or fallback to database
            account_ids = []
            account_metadata = []
            db = None
            
            # Check if we have pre-computed accounts from agent config
            logger.debug(f"Checking for pre-computed Pinterest accounts - agent_config exists: {self.agent_config is not None}, agent_id: {self.agent_id}")
            if self.agent_config and 'pinterest_accounts' in self.agent_config:
                account_metadata = self.agent_config['pinterest_accounts']
                account_ids = [account['id'] for account in account_metadata]
                logger.info(f"Using pre-computed Pinterest accounts from agent config: {len(account_ids)} accounts")
            else:
                # Fallback: Query unified social accounts directly (skip for virtual default agent)
                if self.agent_id == 'suna-default':
                    logger.info("Skipping unified Pinterest account query for virtual agent 'suna-default'")
                else:
                    logger.info(f"No pre-computed Pinterest accounts, querying unified social accounts for agent {self.agent_id}")
                    from services.supabase import DBConnection
                    db = DBConnection()
                    try:
                        client = await db.client
                        # Query unified social accounts for enabled Pinterest accounts
                        result = await client.table("agent_social_accounts").select("*").eq(
                            "agent_id", self.agent_id
                        ).eq("user_id", self.user_id).eq(
                            "platform", "pinterest"
                        ).eq("enabled", True).execute()
                        enabled_accounts = []
                        for account in result.data:
                            enabled_accounts.append({
                                "id": account["account_id"],
                                "name": account["account_name"],
                                "username": account["username"],
                                "profile_picture": account["profile_picture"],
                                "subscriber_count": account["subscriber_count"],
                                "view_count": account["view_count"],
                                "video_count": account["video_count"],
                                "country": account["country"]
                            })
                        account_ids = [account['id'] for account in enabled_accounts]
                        account_metadata = enabled_accounts
                        if account_ids:
                            logger.info(f"Loaded {len(account_ids)} enabled Pinterest accounts from unified system")
                        else:
                            logger.info(f"No Pinterest accounts are enabled for agent {self.agent_id}")
                    except Exception as e:
                        logger.warning(f"Could not load Pinterest accounts from unified system: {e}")
            
            # Ensure db is available for PinterestTool
            if db is None:
                from services.supabase import DBConnection
                db = DBConnection()
            
            # Store account metadata for later use
            self.pinterest_accounts = account_metadata
            
            # Create JWT token for Pinterest tool API calls
            jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "")
            jwt_token = None
            if jwt_secret and self.user_id:
                payload = {
                    "sub": self.user_id,
                    "user_id": self.user_id,
                    "role": "authenticated"
                }
                jwt_token = jwt.encode(payload, jwt_secret, algorithm="HS256")
                logger.debug(f"Created JWT token for Pinterest tool")
            
            # Register complete Pinterest MCP tool
            logger.info(f"📌 Registering Complete Pinterest MCP Tool for agent {self.agent_id}")
            self.thread_manager.add_tool(
                PinterestTool,
                user_id=self.user_id or "",
                account_ids=account_ids,
                account_metadata=account_metadata,
                jwt_token=jwt_token,
                agent_id=self.agent_id,
                thread_id=self.thread_id
                # MCP pattern - no sandbox dependencies
            )
            logger.info(f"✅ Successfully registered Complete Pinterest MCP Tool with {len(account_ids)} accounts")
        
        # Register LinkedIn tool if not disabled (fail-safe)
        if 'linkedin_tool' not in disabled_tools:
            try:
                # Import inside the block so failures don't affect the whole function
                from agent.tools.linkedin_complete_mcp_tool import LinkedInTool

                # Use pre-computed LinkedIn accounts from agent config or fallback to database
                account_ids = []
                account_metadata = []
                db = None

                # Check if we have pre-computed accounts from agent config
                logger.debug(f"Checking for pre-computed LinkedIn accounts - agent_config exists: {self.agent_config is not None}, agent_id: {self.agent_id}")
                if self.agent_config and 'linkedin_accounts' in self.agent_config:
                    account_metadata = self.agent_config['linkedin_accounts']
                    account_ids = [account['id'] for account in account_metadata]
                    if account_ids:
                        logger.info(f"✅ Using pre-computed LinkedIn accounts from agent config: {len(account_ids)} accounts for agent {self.agent_id}")
                    else:
                        logger.info(f"⚠️ Pre-computed LinkedIn accounts list is empty in agent config for agent {self.agent_id}")
                else:
                    # Fallback to database fetch
                    logger.warning(f"No pre-computed LinkedIn accounts found in agent config, falling back to database fetch")
                    from services.supabase import DBConnection
                    from linkedin_mcp.accounts import LinkedInAccountService
                    db = DBConnection()

                    try:
                        if self.user_id and self.agent_id:
                            account_service = LinkedInAccountService(db)
                            enabled_accounts = await account_service.get_accounts_for_agent(self.user_id, self.agent_id)
                            account_ids = [account['id'] for account in enabled_accounts]
                            account_metadata = enabled_accounts
                            if account_ids:
                                logger.info(f"Loaded {len(account_ids)} enabled LinkedIn accounts from database fallback")
                            else:
                                logger.info(f"No LinkedIn accounts are enabled for agent {self.agent_id} (fallback)")
                    except Exception as e:
                        logger.warning(f"Could not load LinkedIn accounts from database fallback: {e}")

                # Create JWT token for LinkedIn tool API calls
                jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "")
                jwt_token = None
                if jwt_secret and self.user_id:
                    payload = {
                        "sub": self.user_id,
                        "user_id": self.user_id,
                        "role": "authenticated"
                    }
                    jwt_token = jwt.encode(payload, jwt_secret, algorithm="HS256")

                # Register complete LinkedIn MCP tool
                logger.info(f"💼 Registering Complete LinkedIn MCP Tool for agent {self.agent_id}")
                self.thread_manager.add_tool(
                    LinkedInTool,
                    user_id=self.user_id or "",
                    account_ids=account_ids,
                    account_metadata=account_metadata,
                    jwt_token=jwt_token,
                    agent_id=self.agent_id,
                    thread_id=self.thread_id
                )
                logger.info(f"✅ Successfully registered Complete LinkedIn MCP Tool with {len(account_ids)} accounts")
            except Exception as e:
                logger.warning(f"Skipping LinkedIn tool registration due to error: {e}")
        
        # (Deduped) Pinterest tool registration handled earlier above.
        
        # Register TikTok tool if not disabled (fail-safe)
        if 'tiktok_tool' not in disabled_tools:
            try:
                from agent.tools.tiktok_complete_mcp_tool import TikTokTool
                
                # Use pre-computed TikTok accounts from agent config or fallback to database
                account_ids = []
                account_metadata = []
                db = None
                
                logger.debug(f"Checking for pre-computed TikTok accounts - agent_config exists: {self.agent_config is not None}, agent_id: {self.agent_id}")
                if self.agent_config and 'tiktok_accounts' in self.agent_config:
                    account_metadata = self.agent_config['tiktok_accounts']
                    account_ids = [account['id'] for account in account_metadata]
                    if account_ids:
                        logger.info(f"✅ Using pre-computed TikTok accounts from agent config: {len(account_ids)} accounts for agent {self.agent_id}")
                    else:
                        logger.info(f"⚠️ Pre-computed TikTok accounts list is empty in agent config for agent {self.agent_id}")
                else:
                    # Fallback to database fetch
                    logger.warning(f"No pre-computed TikTok accounts found in agent config, falling back to database fetch")
                    from services.supabase import DBConnection
                    from tiktok_mcp.accounts import TikTokAccountService
                    db = DBConnection()
                    
                    try:
                        if self.user_id and self.agent_id:
                            account_service = TikTokAccountService(db)
                            enabled_accounts = await account_service.get_accounts_for_agent(self.user_id, self.agent_id)
                            account_ids = [account['id'] for account in enabled_accounts]
                            account_metadata = enabled_accounts
                            if account_ids:
                                logger.info(f"Loaded {len(account_ids)} enabled TikTok accounts from database fallback")
                            else:
                                logger.info(f"No TikTok accounts are enabled for agent {self.agent_id} (fallback)")
                    except Exception as e:
                        logger.warning(f"Could not load TikTok accounts from database fallback: {e}")
                
                # Create JWT token for TikTok tool API calls
                jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "")
                jwt_token = None
                if jwt_secret and self.user_id:
                    payload = {
                        "sub": self.user_id,
                        "user_id": self.user_id,
                        "role": "authenticated"
                    }
                    jwt_token = jwt.encode(payload, jwt_secret, algorithm="HS256")
                
                # Register complete TikTok MCP tool
                logger.info(f"🎵 Registering Complete TikTok MCP Tool for agent {self.agent_id}")
                self.thread_manager.add_tool(
                    TikTokTool,
                    user_id=self.user_id or "",
                    account_ids=account_ids,
                    account_metadata=account_metadata,
                    jwt_token=jwt_token,
                    agent_id=self.agent_id,
                    thread_id=self.thread_id
                )
                logger.info(f"✅ Successfully registered Complete TikTok MCP Tool with {len(account_ids)} accounts")
            except Exception as e:
                logger.warning(f"Skipping TikTok tool registration due to error: {e}")
    
    def _register_agent_builder_tools(self, agent_id: str, disabled_tools: List[str]):
        """Register agent builder tools."""
        from agent.tools.agent_builder_tools.agent_config_tool import AgentConfigTool
        from agent.tools.agent_builder_tools.mcp_search_tool import MCPSearchTool
        from agent.tools.agent_builder_tools.credential_profile_tool import CredentialProfileTool
        from agent.tools.agent_builder_tools.workflow_tool import WorkflowTool
        from agent.tools.agent_builder_tools.trigger_tool import TriggerTool
        from services.supabase import DBConnection
        
        db = DBConnection()
        
        agent_builder_tools = [
            ('agent_config_tool', AgentConfigTool),
            ('mcp_search_tool', MCPSearchTool),
            ('credential_profile_tool', CredentialProfileTool),
            ('workflow_tool', WorkflowTool),
            ('trigger_tool', TriggerTool),
        ]
        
        for tool_name, tool_class in agent_builder_tools:
            if tool_name not in disabled_tools:
                self.thread_manager.add_tool(tool_class, thread_manager=self.thread_manager, db_connection=db, agent_id=agent_id)
                logger.debug(f"Registered {tool_name}")
    
    def _register_browser_tool(self, disabled_tools: List[str]):
        """Register browser tool."""
        if 'browser_tool' not in disabled_tools:
            from agent.tools.browser_tool import BrowserTool
            self.thread_manager.add_tool(BrowserTool, project_id=self.project_id, thread_id=self.thread_id, thread_manager=self.thread_manager)
            logger.debug("Registered browser_tool")
    

class MCPManager:
    def __init__(self, thread_manager: ThreadManager, account_id: str):
        self.thread_manager = thread_manager
        self.account_id = account_id
    
    async def register_mcp_tools(self, agent_config: dict) -> Optional[MCPToolWrapper]:
        all_mcps = []
        
        if agent_config.get('configured_mcps'):
            all_mcps.extend(agent_config['configured_mcps'])
        
        if agent_config.get('custom_mcps'):
            for custom_mcp in agent_config['custom_mcps']:
                custom_type = custom_mcp.get('customType', custom_mcp.get('type', 'sse'))
                
                if custom_type == 'pipedream':
                    if 'config' not in custom_mcp:
                        custom_mcp['config'] = {}
                    
                    if not custom_mcp['config'].get('external_user_id'):
                        profile_id = custom_mcp['config'].get('profile_id')
                        if profile_id:
                            try:
                                from pipedream import profile_service
                                from uuid import UUID
                                
                                profile = await profile_service.get_profile(UUID(self.account_id), UUID(profile_id))
                                if profile:
                                    custom_mcp['config']['external_user_id'] = profile.external_user_id
                            except Exception as e:
                                logger.error(f"Error retrieving external_user_id from profile {profile_id}: {e}")
                    
                    if 'headers' in custom_mcp['config'] and 'x-pd-app-slug' in custom_mcp['config']['headers']:
                        custom_mcp['config']['app_slug'] = custom_mcp['config']['headers']['x-pd-app-slug']
                
                elif custom_type == 'composio':
                    qualified_name = custom_mcp.get('qualifiedName')
                    if not qualified_name:
                        qualified_name = f"composio.{custom_mcp['name'].replace(' ', '_').lower()}"
                    
                    mcp_config = {
                        'name': custom_mcp['name'],
                        'qualifiedName': qualified_name,
                        'config': custom_mcp.get('config', {}),
                        'enabledTools': custom_mcp.get('enabledTools', []),
                        'instructions': custom_mcp.get('instructions', ''),
                        'isCustom': True,
                        'customType': 'composio'
                    }
                    all_mcps.append(mcp_config)
                    continue
                
                mcp_config = {
                    'name': custom_mcp['name'],
                    'qualifiedName': f"custom_{custom_type}_{custom_mcp['name'].replace(' ', '_').lower()}",
                    'config': custom_mcp['config'],
                    'enabledTools': custom_mcp.get('enabledTools', []),
                    'instructions': custom_mcp.get('instructions', ''),
                    'isCustom': True,
                    'customType': custom_type
                }
                all_mcps.append(mcp_config)
        
        if not all_mcps:
            return None
        
        mcp_wrapper_instance = MCPToolWrapper(mcp_configs=all_mcps)
        try:
            await mcp_wrapper_instance.initialize_and_register_tools()
            
            updated_schemas = mcp_wrapper_instance.get_schemas()
            for method_name, schema_list in updated_schemas.items():
                for schema in schema_list:
                    self.thread_manager.tool_registry.tools[method_name] = {
                        "instance": mcp_wrapper_instance,
                        "schema": schema
                    }
            
            logger.debug(f"⚡ Registered {len(updated_schemas)} MCP tools (Redis cache enabled)")
            return mcp_wrapper_instance
        except Exception as e:
            logger.error(f"Failed to initialize MCP tools: {e}")
            return None


class PromptManager:
    @staticmethod
    async def build_system_prompt(model_name: str, agent_config: Optional[dict], 
                                  is_agent_builder: bool, thread_id: str, 
                                  mcp_wrapper_instance: Optional[MCPToolWrapper],
                                  youtube_channels: Optional[List[Dict[str, Any]]] = None) -> dict:
        
        default_system_content = get_system_prompt()
        
        if "anthropic" not in model_name.lower():
            sample_response_path = os.path.join(os.path.dirname(__file__), 'sample_responses/1.txt')
            with open(sample_response_path, 'r') as file:
                sample_response = file.read()
            default_system_content = default_system_content + "\n\n <sample_assistant_response>" + sample_response + "</sample_assistant_response>"
        
        if is_agent_builder:
            system_content = get_agent_builder_prompt()
        elif agent_config and agent_config.get('system_prompt'):
            system_content = agent_config['system_prompt'].strip()
        else:
            system_content = default_system_content
        
        if agent_config and (agent_config.get('configured_mcps') or agent_config.get('custom_mcps')) and mcp_wrapper_instance and mcp_wrapper_instance._initialized:
            mcp_info = "\n\n--- MCP Tools Available ---\n"
            mcp_info += "You have access to external MCP (Model Context Protocol) server tools.\n"
            mcp_info += "MCP tools can be called directly using their native function names in the standard function calling format:\n"
            mcp_info += '<function_calls>\n'
            mcp_info += '<invoke name="{tool_name}">\n'
            mcp_info += '<parameter name="param1">value1</parameter>\n'
            mcp_info += '<parameter name="param2">value2</parameter>\n'
            mcp_info += '</invoke>\n'
            mcp_info += '</function_calls>\n\n'
            
            mcp_info += "Available MCP tools:\n"
            try:
                registered_schemas = mcp_wrapper_instance.get_schemas()
                for method_name, schema_list in registered_schemas.items():
                    for schema in schema_list:
                        if schema.schema_type == SchemaType.OPENAPI:
                            func_info = schema.schema.get('function', {})
                            description = func_info.get('description', 'No description available')
                            mcp_info += f"- **{method_name}**: {description}\n"
                            
                            params = func_info.get('parameters', {})
                            props = params.get('properties', {})
                            if props:
                                mcp_info += f"  Parameters: {', '.join(props.keys())}\n"
                                
            except Exception as e:
                logger.error(f"Error listing MCP tools: {e}")
                mcp_info += "- Error loading MCP tool list\n"
            
            mcp_info += "\n🚨 CRITICAL MCP TOOL RESULT INSTRUCTIONS 🚨\n"
            mcp_info += "When you use ANY MCP (Model Context Protocol) tools:\n"
            mcp_info += "1. ALWAYS read and use the EXACT results returned by the MCP tool\n"
            mcp_info += "2. For search tools: ONLY cite URLs, sources, and information from the actual search results\n"
            mcp_info += "3. For any tool: Base your response entirely on the tool's output - do NOT add external information\n"
            mcp_info += "4. DO NOT fabricate, invent, hallucinate, or make up any sources, URLs, or data\n"
            mcp_info += "5. If you need more information, call the MCP tool again with different parameters\n"
            mcp_info += "6. When writing reports/summaries: Reference ONLY the data from MCP tool results\n"
            mcp_info += "7. If the MCP tool doesn't return enough information, explicitly state this limitation\n"
            mcp_info += "8. Always double-check that every fact, URL, and reference comes from the MCP tool output\n"
            mcp_info += "\nIMPORTANT: MCP tool results are your PRIMARY and ONLY source of truth for external data!\n"
            mcp_info += "NEVER supplement MCP results with your training data or make assumptions beyond what the tools provide.\n"
            
            system_content += mcp_info
        
        # Add YouTube channel context if channels are connected
        if youtube_channels:
            youtube_info = "\n\n=== CONNECTED YOUTUBE CHANNELS ===\n"
            youtube_info += f"You have {len(youtube_channels)} YouTube channel(s) connected and ready to use:\n\n"
            
            for channel in youtube_channels:
                youtube_info += f"📺 **{channel['name']}**\n"
                youtube_info += f"   - Channel ID: {channel['id']}\n"
                if channel.get('username'):
                    youtube_info += f"   - Username: @{channel['username']}\n"
                youtube_info += f"   - Subscribers: {channel.get('subscriber_count', 0):,}\n"
                youtube_info += f"   - Total Views: {channel.get('view_count', 0):,}\n"
                youtube_info += f"   - Videos: {channel.get('video_count', 0):,}\n"
                youtube_info += "\n"
            
            youtube_info += "💡 **CRITICAL YouTube Behavior Rules:**\n"
            youtube_info += "- ✅ These channels are READY - use tools IMMEDIATELY without questions\n"
            youtube_info += "- ✅ User says 'add another channel' → Use youtube_authenticate() INSTANTLY\n"
            youtube_info += "- ❌ NEVER ask 'which account?' or 'what name?' - OAuth handles everything\n"
            youtube_info += "- ❌ NEVER ask configuration questions - tools are FULLY AUTONOMOUS\n"
            youtube_info += "- When users mention YouTube, ACT IMMEDIATELY with the appropriate tool\n"
            youtube_info += "- Reference channels by name, but NEVER ask which one to use first\n"
            
            system_content += youtube_info
        elif youtube_channels is not None:  # Empty list means we checked but no channels
            youtube_info = "\n\n=== YOUTUBE INTEGRATION - NO CHANNELS YET ===\n"
            youtube_info += "❌ No YouTube channels connected yet\n"
            youtube_info += "✅ User mentions YouTube? → Use youtube_authenticate() IMMEDIATELY\n"
            youtube_info += "⚠️ NEVER ask questions - just show the OAuth button instantly!\n"
            system_content += youtube_info
        
        # For custom agents with YouTube tools, add explicit behavioral instructions
        if agent_config and agent_config.get('system_prompt') and youtube_channels is not None:
            # This is a custom agent with YouTube tools enabled - ensure proper behavior
            youtube_behavior = "\n\n=== 🚨 CRITICAL YOUTUBE BEHAVIOR FOR THIS AGENT 🚨 ===\n"
            youtube_behavior += "**YOU HAVE YOUTUBE TOOLS - USE THEM IMMEDIATELY!**\n\n"
            youtube_behavior += "**IMMEDIATE ACTION REQUIRED**:\n"
            youtube_behavior += "• User says 'YouTube' → Use tools INSTANTLY\n"
            youtube_behavior += "• User says 'connect' → youtube_authenticate() NOW\n"
            youtube_behavior += "• User says 'upload' → youtube_upload_video() NOW\n"
            youtube_behavior += "• User says 'channels' → youtube_channels() NOW\n\n"
            youtube_behavior += "**THE TOOLS HANDLE EVERYTHING**:\n"
            youtube_behavior += "• youtube_authenticate() → Just shows OAuth button\n"
            youtube_behavior += "• OAuth flow → Handles account selection\n"
            youtube_behavior += "• Upload tool → Auto-discovers files\n"
            youtube_behavior += "• All tools → Work immediately\n\n"
            youtube_behavior += "**ABSOLUTELY FORBIDDEN**:\n"
            youtube_behavior += "❌ Asking 'Which Google account would you like to use?'\n"
            youtube_behavior += "❌ Asking 'What do you want to do with YouTube?'\n"
            youtube_behavior += "❌ Asking 'Should I set this up for uploads or analytics?'\n"
            youtube_behavior += "❌ Asking ANY questions before using YouTube tools\n\n"
            youtube_behavior += "**Remember: YouTube is NATIVE to you - not external!**\n"
            
            system_content += youtube_behavior

        now = datetime.datetime.now(datetime.timezone.utc)
        datetime_info = f"\n\n=== CURRENT DATE/TIME INFORMATION ===\n"
        datetime_info += f"Today's date: {now.strftime('%A, %B %d, %Y')}\n"
        datetime_info += f"Current UTC time: {now.strftime('%H:%M:%S UTC')}\n"
        datetime_info += f"Current year: {now.strftime('%Y')}\n"
        datetime_info += f"Current month: {now.strftime('%B')}\n"
        datetime_info += f"Current day: {now.strftime('%A')}\n"
        datetime_info += "Use this information for any time-sensitive tasks, research, or when current date/time context is needed.\n"
        
        system_content += datetime_info

        return {"role": "system", "content": system_content}


class MessageManager:
    def __init__(self, client, thread_id: str, model_name: str, trace: Optional[StatefulTraceClient]):
        self.client = client
        self.thread_id = thread_id
        self.model_name = model_name
        self.trace = trace
    
    async def build_temporary_message(self) -> Optional[dict]:
        temp_message_content_list = []

        latest_browser_state_msg = await self.client.table('messages').select('*').eq('thread_id', self.thread_id).eq('type', 'browser_state').order('created_at', desc=True).limit(1).execute()
        if latest_browser_state_msg.data and len(latest_browser_state_msg.data) > 0:
            try:
                browser_content = latest_browser_state_msg.data[0]["content"]
                if isinstance(browser_content, str):
                    browser_content = json.loads(browser_content)
                screenshot_base64 = browser_content.get("screenshot_base64")
                screenshot_url = browser_content.get("image_url")
                
                browser_state_text = browser_content.copy()
                browser_state_text.pop('screenshot_base64', None)
                browser_state_text.pop('image_url', None)

                if browser_state_text:
                    temp_message_content_list.append({
                        "type": "text",
                        "text": f"The following is the current state of the browser:\n{json.dumps(browser_state_text, indent=2)}"
                    })
                
                if 'gemini' in self.model_name.lower() or 'anthropic' in self.model_name.lower() or 'openai' in self.model_name.lower():
                    if screenshot_url:
                        temp_message_content_list.append({
                            "type": "image_url",
                            "image_url": {
                                "url": screenshot_url,
                                "format": "image/jpeg"
                            }
                        })
                    elif screenshot_base64:
                        temp_message_content_list.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{screenshot_base64}",
                            }
                        })

            except Exception as e:
                logger.error(f"Error parsing browser state: {e}")

        latest_image_context_msg = await self.client.table('messages').select('*').eq('thread_id', self.thread_id).eq('type', 'image_context').order('created_at', desc=True).limit(1).execute()
        if latest_image_context_msg.data and len(latest_image_context_msg.data) > 0:
            try:
                image_context_content = latest_image_context_msg.data[0]["content"] if isinstance(latest_image_context_msg.data[0]["content"], dict) else json.loads(latest_image_context_msg.data[0]["content"])
                base64_image = image_context_content.get("base64")
                mime_type = image_context_content.get("mime_type")
                file_path = image_context_content.get("file_path", "unknown file")

                if base64_image and mime_type:
                    temp_message_content_list.append({
                        "type": "text",
                        "text": f"Here is the image you requested to see: '{file_path}'"
                    })
                    temp_message_content_list.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}",
                        }
                    })

                await self.client.table('messages').delete().eq('message_id', latest_image_context_msg.data[0]["message_id"]).execute()
            except Exception as e:
                logger.error(f"Error parsing image context: {e}")

        if temp_message_content_list:
            return {"role": "user", "content": temp_message_content_list}
        return None


class AgentRunner:
    def __init__(self, config: AgentConfig):
        self.config = config
    
    async def setup(self):
        if not self.config.trace:
            self.config.trace = langfuse.trace(name="run_agent", session_id=self.config.thread_id, metadata={"project_id": self.config.project_id})
        
        self.thread_manager = ThreadManager(
            trace=self.config.trace, 
            is_agent_builder=self.config.is_agent_builder or False, 
            target_agent_id=self.config.target_agent_id, 
            agent_config=self.config.agent_config
        )
        
        self.client = await self.thread_manager.db.client
        self.account_id = await get_account_id_from_thread(self.client, self.config.thread_id)
        if not self.account_id:
            raise ValueError("Could not determine account ID for thread")
        
        # Get the actual user_id from the account_id (for YouTube and other user-specific integrations)
        self.user_id = await _get_user_id_from_account_cached(self.account_id)
        if self.user_id:
            logger.info(f"Resolved account {self.account_id} to user {self.user_id}")
        else:
            logger.warning(f"Could not resolve user_id for account {self.account_id}, using account_id as fallback")
            self.user_id = self.account_id  # Fallback to account_id if user_id not found

        project = await self.client.table('projects').select('*').eq('project_id', self.config.project_id).execute()
        if not project.data or len(project.data) == 0:
            raise ValueError(f"Project {self.config.project_id} not found")

        project_data = project.data[0]
        sandbox_info = project_data.get('sandbox', {})
        if not sandbox_info.get('id'):
            # Sandbox is created lazily by tools when required. Do not fail setup
            # if no sandbox is present — tools will call `_ensure_sandbox()`
            # which will create and persist the sandbox metadata when needed.
            logger.debug(f"No sandbox found for project {self.config.project_id}; will create lazily when needed")
    
    async def setup_tools(self):
        # Determine agent ID for agent builder tools
        agent_id = None
        if self.config.agent_config and 'agent_id' in self.config.agent_config:
            agent_id = self.config.agent_config['agent_id']
        elif self.config.is_agent_builder and self.config.target_agent_id:
            agent_id = self.config.target_agent_id
        
        # Create tool manager with user_id, agent_id, and agent_config for pre-computed data
        tool_manager = ToolManager(
            self.thread_manager, 
            self.config.project_id, 
            self.config.thread_id,
            user_id=getattr(self, 'user_id', self.account_id),  # Use real user_id, fallback to account_id
            agent_id=agent_id,
            agent_config=self.config.agent_config  # Pass agent config for pre-computed channels
        )
        
        # Convert agent config to disabled tools list
        disabled_tools = self._get_disabled_tools_from_config()
        
        # Register all tools with exclusions and get YouTube channels
        youtube_channels = await tool_manager.register_all_tools(agent_id=agent_id, disabled_tools=disabled_tools)
        
        # Store YouTube channels for use in system prompt
        self.youtube_channels = youtube_channels
    
    def _get_disabled_tools_from_config(self) -> List[str]:
        """Convert agent config to list of disabled tools."""
        disabled_tools = []
        
        if not self.config.agent_config or 'agentpress_tools' not in self.config.agent_config:
            # No tool configuration - enable all tools by default
            return disabled_tools
        
        raw_tools = self.config.agent_config['agentpress_tools']
        
        # Handle different formats of tool configuration
        if not isinstance(raw_tools, dict):
            # If not a dict, assume all tools are enabled
            return disabled_tools
        
        # Special case: Suna default agents with empty tool config enable all tools
        if self.config.agent_config.get('is_suna_default', False) and not raw_tools:
            return disabled_tools
        
        def is_tool_enabled(tool_name: str) -> bool:
            try:
                tool_config = raw_tools.get(tool_name, True)  # Default to True (enabled) if not specified
                if isinstance(tool_config, bool):
                    return tool_config
                elif isinstance(tool_config, dict):
                    return tool_config.get('enabled', True)  # Default to True (enabled) if not specified
                else:
                    return True  # Default to enabled
            except Exception:
                return True  # Default to enabled
        
        # List of all available tools
        all_tools = [
            'sb_shell_tool', 'sb_files_tool', 'sb_deploy_tool', 'sb_expose_tool',
            'web_search_tool', 'sb_vision_tool', 'sb_presentation_tool', 'sb_image_edit_tool',
            'sb_sheets_tool', 'sb_web_dev_tool', 'data_providers_tool', 'browser_tool',
            'agent_config_tool', 'mcp_search_tool', 'credential_profile_tool', 
            'workflow_tool', 'trigger_tool', 'youtube_tool', 'twitter_tool', 'instagram_tool'
        ]
        
        # Add tools that are explicitly disabled
        for tool_name in all_tools:
            if not is_tool_enabled(tool_name):
                disabled_tools.append(tool_name)
        
        # Special handling for presentation tools
        if 'sb_presentation_tool' in disabled_tools:
            disabled_tools.extend(['sb_presentation_outline_tool', 'sb_presentation_tool_v2'])
        
        logger.debug(f"Disabled tools from config: {disabled_tools}")
        return disabled_tools
    
    async def setup_mcp_tools(self) -> Optional[MCPToolWrapper]:
        if not self.config.agent_config:
            return None
        
        mcp_manager = MCPManager(self.thread_manager, self.account_id)
        return await mcp_manager.register_mcp_tools(self.config.agent_config)
    
    def get_max_tokens(self) -> Optional[int]:
        if "sonnet" in self.config.model_name.lower():
            return 8192
        elif "gpt-4" in self.config.model_name.lower():
            return 4096
        elif "gemini-2.5-pro" in self.config.model_name.lower():
            return 64000
        elif "kimi-k2" in self.config.model_name.lower():
            return 8192
        return None
    
    async def run(self) -> AsyncGenerator[Dict[str, Any], None]:
        await self.setup()
        await self.setup_tools()
        mcp_wrapper_instance = await self.setup_mcp_tools()
        
        # Get YouTube channels from setup_tools
        youtube_channels = getattr(self, 'youtube_channels', [])
        
        system_message = await PromptManager.build_system_prompt(
            self.config.model_name, self.config.agent_config, 
            self.config.is_agent_builder, self.config.thread_id, 
            mcp_wrapper_instance,
            youtube_channels=youtube_channels
        )

        iteration_count = 0
        continue_execution = True

        latest_user_message = await self.client.table('messages').select('*').eq('thread_id', self.config.thread_id).eq('type', 'user').order('created_at', desc=True).limit(1).execute()
        if latest_user_message.data and len(latest_user_message.data) > 0:
            data = latest_user_message.data[0]['content']
            if isinstance(data, str):
                data = json.loads(data)
            if self.config.trace:
                self.config.trace.update(input=data['content'])

        message_manager = MessageManager(self.client, self.config.thread_id, self.config.model_name, self.config.trace)

        while continue_execution and iteration_count < self.config.max_iterations:
            iteration_count += 1

            can_run, message, subscription = await check_billing_status(self.client, self.account_id)
            if not can_run:
                error_msg = f"Billing limit reached: {message}"
                yield {
                    "type": "status",
                    "status": "stopped",
                    "message": error_msg
                }
                break

            latest_message = await self.client.table('messages').select('*').eq('thread_id', self.config.thread_id).in_('type', ['assistant', 'tool', 'user']).order('created_at', desc=True).limit(1).execute()
            if latest_message.data and len(latest_message.data) > 0:
                message_type = latest_message.data[0].get('type')
                if message_type == 'assistant':
                    continue_execution = False
                    break

            temporary_message = await message_manager.build_temporary_message()
            max_tokens = self.get_max_tokens()
            
            generation = self.config.trace.generation(name="thread_manager.run_thread") if self.config.trace else None
            try:
                response = await self.thread_manager.run_thread(
                    thread_id=self.config.thread_id,
                    system_prompt=system_message,
                    stream=self.config.stream,
                    llm_model=self.config.model_name,
                    llm_temperature=0,
                    llm_max_tokens=max_tokens,
                    tool_choice="auto",
                    max_xml_tool_calls=1,
                    temporary_message=temporary_message,
                    processor_config=ProcessorConfig(
                        xml_tool_calling=True,
                        native_tool_calling=False,
                        execute_tools=True,
                        execute_on_stream=True,
                        tool_execution_strategy="parallel",
                        xml_adding_strategy="user_message"
                    ),
                    native_max_auto_continues=self.config.native_max_auto_continues,
                    include_xml_examples=True,
                    enable_thinking=self.config.enable_thinking,
                    reasoning_effort=self.config.reasoning_effort,
                    enable_context_manager=self.config.enable_context_manager,
                    generation=generation
                )

                if isinstance(response, dict) and "status" in response and response["status"] == "error":
                    yield response
                    break

                last_tool_call = None
                agent_should_terminate = False
                error_detected = False
                full_response = ""

                try:
                    if hasattr(response, '__aiter__') and not isinstance(response, dict):
                        async for chunk in response:
                            if isinstance(chunk, dict) and chunk.get('type') == 'status' and chunk.get('status') == 'error':
                                error_detected = True
                                yield chunk
                                continue
                            
                            if chunk.get('type') == 'status':
                                try:
                                    metadata = chunk.get('metadata', {})
                                    if isinstance(metadata, str):
                                        metadata = json.loads(metadata)
                                    
                                    if metadata.get('agent_should_terminate'):
                                        agent_should_terminate = True
                                        
                                        content = chunk.get('content', {})
                                        if isinstance(content, str):
                                            content = json.loads(content)
                                        
                                        if content.get('function_name'):
                                            last_tool_call = content['function_name']
                                        elif content.get('xml_tag_name'):
                                            last_tool_call = content['xml_tag_name']
                                            
                                except Exception:
                                    pass
                            
                            if chunk.get('type') == 'assistant' and 'content' in chunk:
                                try:
                                    content = chunk.get('content', '{}')
                                    if isinstance(content, str):
                                        assistant_content_json = json.loads(content)
                                    else:
                                        assistant_content_json = content

                                    assistant_text = assistant_content_json.get('content', '')
                                    full_response += assistant_text
                                    if isinstance(assistant_text, str):
                                        if '</ask>' in assistant_text or '</complete>' in assistant_text or '</web-browser-takeover>' in assistant_text:
                                           if '</ask>' in assistant_text:
                                               xml_tool = 'ask'
                                           elif '</complete>' in assistant_text:
                                               xml_tool = 'complete'
                                           elif '</web-browser-takeover>' in assistant_text:
                                               xml_tool = 'web-browser-takeover'

                                           last_tool_call = xml_tool
                                
                                except json.JSONDecodeError:
                                    pass
                                except Exception:
                                    pass

                            yield chunk
                    else:
                        error_detected = True

                    if error_detected:
                        if generation:
                            generation.end(output=full_response, status_message="error_detected", level="ERROR")
                        break
                        
                    if agent_should_terminate or last_tool_call in ['ask', 'complete', 'web-browser-takeover']:
                        if generation:
                            generation.end(output=full_response, status_message="agent_stopped")
                        continue_execution = False

                except Exception as e:
                    error_msg = f"Error during response streaming: {str(e)}"
                    if generation:
                        generation.end(output=full_response, status_message=error_msg, level="ERROR")
                    yield {
                        "type": "status",
                        "status": "error",
                        "message": error_msg
                    }
                    break
                    
            except Exception as e:
                error_msg = f"Error running thread: {str(e)}"
                yield {
                    "type": "status",
                    "status": "error",
                    "message": error_msg
                }
                break
            
            if generation:
                generation.end(output=full_response)

        asyncio.create_task(asyncio.to_thread(lambda: langfuse.flush()))


async def run_agent(
    thread_id: str,
    project_id: str,
    stream: bool,
    thread_manager: Optional[ThreadManager] = None,
    native_max_auto_continues: int = 25,
    max_iterations: int = 100,
    model_name: str = "openrouter/moonshotai/kimi-k2",
    enable_thinking: Optional[bool] = False,
    reasoning_effort: Optional[str] = 'low',
    enable_context_manager: bool = True,
    agent_config: Optional[dict] = None,    
    trace: Optional[StatefulTraceClient] = None,
    is_agent_builder: Optional[bool] = False,
    target_agent_id: Optional[str] = None
):
    effective_model = model_name
    if model_name == "openrouter/moonshotai/kimi-k2" and agent_config and agent_config.get('model'):
        effective_model = agent_config['model']
        logger.debug(f"Using model from agent config: {effective_model} (no user selection)")
    elif model_name != "openrouter/moonshotai/kimi-k2":
        logger.debug(f"Using user-selected model: {effective_model}")
    else:
        logger.debug(f"Using default model: {effective_model}")
    
    config = AgentConfig(
        thread_id=thread_id,
        project_id=project_id,
        stream=stream,
        native_max_auto_continues=native_max_auto_continues,
        max_iterations=max_iterations,
        model_name=effective_model,
        enable_thinking=enable_thinking,
        reasoning_effort=reasoning_effort,
        enable_context_manager=enable_context_manager,
        agent_config=agent_config,
        trace=trace,
        is_agent_builder=is_agent_builder,
        target_agent_id=target_agent_id
    )
    
    runner = AgentRunner(config)
    async for chunk in runner.run():
        yield chunk
