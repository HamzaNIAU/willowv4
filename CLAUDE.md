# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kortix (previously Suna) is an open-source platform for building, managing, and training AI agents. The platform includes Suna, a flagship generalist AI worker agent, and provides the Agentpress framework for creating custom specialized agents.

## Tech Stack

### Backend
- **Python 3.11+** with uv package manager
- **FastAPI** for REST API endpoints
- **Dramatiq** for background job processing
- **Redis** for caching and session management (port 6380 external)
- **Supabase** for database, authentication, and storage
- **LiteLLM** for LLM provider abstraction
- **Agentpress** framework for agent orchestration
- **MCP (Model Context Protocol)** for tool integrations

### Frontend
- **Next.js 15** with App Router and TurboPack
- **TypeScript** for type safety
- **React 18** with React Query for data fetching
- **Tailwind CSS v4** for styling
- **shadcn/ui** for component library
- **Zustand** for state management

### SDK
- **Python SDK** (`sdk/kortix/`) for external integrations

## Essential Commands

### Quick Start
```bash
# Initial setup (14-step wizard with progress tracking)
python setup.py

# Start all services (Docker recommended)
python start.py
# Press Y to start, press Y again to stop
```

### Backend Development
```bash
cd backend

# Install dependencies
uv sync

# Run tests
uv run pytest
uv run pytest test_youtube_upload.py -v  # Specific test
uv run pytest --cov=.  # With coverage

# Run server locally
uv run api.py

# Run worker
uv run dramatiq --processes 4 --threads 4 run_agent_background

# Apply migrations
uv run apply_migration.py

# Enable feature flags
uv run enable_features.py  # All features
uv run enable_features_local.py  # Local dev

# Linting/formatting
uv run ruff check .
uv run ruff format .
```

### Frontend Development
```bash
cd frontend

# Install
npm install

# Development (uses TurboPack for fast HMR)
npm run dev

# Production
npm run build
npm run start

# Code quality
npm run lint
npm run format
npm run format:check
```

### Docker Operations
```bash
# IMPORTANT: Always use start.py for container management
python start.py  # Start/stop all services

# Rebuild after changes
docker compose down && docker compose up --build

# View logs
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f frontend

# Redis runs on port 6380 (mapped from 6379)
```

## Architecture Overview

### Core Agent System Architecture

#### **1. Agent Execution Pipeline - AgentRunner**
**Core Components**:
- **Location**: `backend/agent/run.py` - Main execution orchestrator
- **AgentRunner Class**: Comprehensive agent lifecycle management
- **Execution Flow**: `setup() → setup_tools() → setup_mcp_tools() → run()` in continuous loop
- **Auto-continue Logic**: Handles tool calls with configurable auto-continuation (default: 25 iterations)

**Setup Process**:
```python
class AgentRunner:
    async def setup(self):
        # 1. Initialize ThreadManager with agent config
        # 2. Get account_id and resolve user_id for integrations  
        # 3. Verify project access and sandbox info
        # 4. Set up langfuse tracing
    
    async def setup_tools(self):
        # 1. Determine agent_id for builder tools
        # 2. Create ToolManager with user context
        # 3. Register all tools based on agent config
        # 4. Pre-compute YouTube channels from cache
    
    async def run(self):
        # 1. Build system prompt with all context
        # 2. Continuous execution loop (max 100 iterations)
        # 3. Billing checks on each iteration
        # 4. ThreadManager.run_thread() execution
        # 5. Handle termination signals from tools
```

#### **2. AgentPress Framework - Core Engine**
**ThreadManager** (`backend/agentpress/thread_manager.py`):
- **Purpose**: Manages conversation threads with LLM integration
- **Key Features**:
  - Message persistence with full conversation history
  - Tool execution orchestration (sequential/parallel)
  - Context compression with 120k token threshold
  - Auto-continue support for multi-turn tool execution
  - Streaming and non-streaming response handling

**Tool Registry** (`backend/agentpress/tool_registry.py`):
- **Tool Registration**: Dynamic registration with function filtering
- **Schema Management**: OpenAPI schema extraction and validation
- **Function Mapping**: Maps tool names to callable functions
- **Usage Examples**: Stores tool usage examples for prompts

**Response Processor** (`backend/agentpress/response_processor.py`):
- **Dual Tool Parsing**: XML (`<function_calls><invoke>`) and native OpenAI format
- **Streaming Tool Execution**: Real-time tool execution during response streaming
- **Tool Result Formatting**: Structured tool results for both LLM and frontend
- **Auto-continue Logic**: Handles `finish_reason="tool_calls"` automatically

**Context Manager** (`backend/agentpress/context_manager.py`):
- **Token Counting**: Model-specific context window management
- **Message Compression**: Intelligent compression of tool results and user messages
- **Content Truncation**: Safe truncation with expand-message tool integration
- **Model-Specific Limits**: Handles Gemini (1M tokens), GPT-5 (400k), Claude (200k)

#### **3. Default Agent System (Suna)**
**Configuration** (`backend/agent/suna_config.py`):
- **Central Management**: Single source of truth for Suna behavior
- **Tool Defaults**: All AgentPress tools enabled by default
- **System Prompt**: 1500+ line comprehensive behavior definition
- **Zero-Questions Protocol**: Native YouTube integration without configuration
- **User Customization**: Redis-based per-user MCP configurations

**Key Behaviors**:
```python
# Tech Stack Priority (from prompt.py)
- User preferences OVERRIDE all defaults
- "Supabase" → Use Supabase, NOT generic databases
- "Prisma" → Use Prisma ORM, NOT raw SQL
- "Clerk" → Use Clerk auth, NOT NextAuth

# YouTube Zero-Questions Protocol
- User says "YouTube" → Use tools IMMEDIATELY
- NEVER ask account preferences or configuration
- OAuth handles ALL user interactions
- Tools work like "hardcoded brain functions"
```

#### **4. Custom Agent System**
**Agent Builder Mode**:
- **Activation**: `is_agent_builder=True` flag in ThreadManager
- **Builder Prompt**: `backend/agent/agent_builder_prompt.py` (500+ lines)
- **Builder Tools**: Complete agent configuration toolkit
- **Target Agent**: Can modify specific agent via `target_agent_id`

**Configuration Tools**:
```python
# Agent Builder Tools (backend/agent/tools/agent_builder_tools/)
- AgentConfigTool: update_agent() - Complete agent updates
- MCPSearchTool: search_mcp_servers() - Find integrations
- CredentialProfileTool: create_credential_profile() - Auth setup
- WorkflowTool: create_workflow() - Multi-step processes  
- TriggerTool: create_scheduled_trigger() - Automation
```

#### **5. Agent Versioning System**
**Version Service** (`backend/agent/versioning/version_service.py`):
- **Complete Versioning**: All agent configuration changes tracked
- **Rollback Support**: Restore to any previous version
- **Change Tracking**: Detailed diff analysis between versions
- **Access Control**: Owner/public permission system

**Version Structure**:
```python
@dataclass
class AgentVersion:
    version_id: str
    agent_id: str
    version_number: int
    system_prompt: str
    model: Optional[str]
    agentpress_tools: Dict[str, Any]
    configured_mcps: List[Dict[str, Any]]
    custom_mcps: List[Dict[str, Any]]
    workflows: List[Dict[str, Any]]
    triggers: List[Dict[str, Any]]
    # Change tracking
    change_description: Optional[str]
    previous_version_id: Optional[str]
```

#### **6. Configuration System**
**Config Helper** (`backend/agent/config_helper.py`):
- **Dual Path**: Suna agents vs Custom agents with different logic
- **Pre-computed Data**: YouTube channels cached during config extraction
- **Tool Configuration**: Converts agent config to disabled tools list
- **Runtime Format**: Converts config to execution-ready format

**Agent Config Flow**:
```python
async def extract_agent_config(agent_data, version_data):
    if is_suna_default:
        # Use central config + user customizations
        return await _extract_suna_agent_config(agent_data, version_data)
    else:
        # Use versioned custom agent config
        return _extract_custom_agent_config(agent_data, version_data)
```

### Tool Architecture Deep Dive

#### **7. Tool System Foundation**
**Base Classes** (`backend/agentpress/tool.py`):
```python
class Tool(ABC):
    # Base class for all tools with schema registration
    def __init__(self):
        self._schemas: Dict[str, List[ToolSchema]] = {}
        self._register_schemas()  # Auto-discovery of decorated methods
    
    def success_response(self, data) -> ToolResult
    def fail_response(self, msg: str) -> ToolResult
```

**Schema Decorators**:
```python
@openapi_schema({  # OpenAPI function calling format
    "type": "function",
    "function": {
        "name": "tool_name",
        "description": "Tool description",
        "parameters": {...}
    }
})
@usage_example("XML example for prompts")  # Tool usage examples
```

**Tool Registration Flow**:
```python
# ToolManager (backend/agent/run.py)
class ToolManager:
    async def register_all_tools(self):
        # 1. Core tools (always enabled)
        self._register_core_tools()  # MessageTool, ExpandMessageTool, TaskListTool
        
        # 2. Sandbox tools (configurable)
        self._register_sandbox_tools()  # Shell, Files, Browser, Vision, etc.
        
        # 3. Utility tools (optional)
        await self._register_utility_tools()  # YouTube, DataProviders, WebSearch
        
        # 4. Agent builder tools (if agent_id provided)
        if agent_id:
            self._register_agent_builder_tools()
```

#### **8. Tool Execution Pipeline**
**XML Tool Parser** (`backend/agentpress/xml_tool_parser.py`):
```python
# Supports <function_calls><invoke> format
class XMLToolParser:
    def parse_content(self, content: str) -> List[XMLToolCall]
    # Extracts: function_name, parameters, parsing_details
```

**Tool Execution Strategies**:
```python
# Sequential: Execute one after another (dependencies)
async def _execute_tools_sequentially(tool_calls):
    for tool_call in tool_calls:
        result = await self._execute_tool(tool_call)
        # Check for termination tools (ask, complete)
        if tool_name in ['ask', 'complete']:
            break  # Stop further execution

# Parallel: Execute simultaneously (independent)
async def _execute_tools_in_parallel(tool_calls):
    tasks = [self._execute_tool(tc) for tc in tool_calls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
```

**Tool Result Processing**:
```python
# Dual format for LLM and frontend
structured_result = {
    "tool_execution": {
        "function_name": tool_call["function_name"],
        "arguments": tool_call["arguments"],
        "result": {
            "success": result.success,
            "output": output,  # Rich for frontend, concise for LLM
        }
    }
}
```

#### **9. MCP (Model Context Protocol) Integration**
**MCP Tool Wrapper** (`backend/agent/tools/mcp_tool_wrapper.py`):
- **Dynamic Registration**: Discovers and registers external MCP tools
- **Redis Caching**: 1-hour TTL for MCP schemas to improve performance
- **Connection Manager**: Handles authentication and connection lifecycle
- **Tool Execution**: Seamless integration with native tool execution

**MCP Integration Flow**:
```python
class MCPManager:
    async def register_mcp_tools(self, agent_config):
        # 1. Process configured_mcps (standard integrations)
        # 2. Process custom_mcps (Composio, Pipedream, etc.)
        # 3. Initialize connections with credentials
        # 4. Register tools in ToolRegistry
        # 5. Cache schemas in Redis
```

**MCP Configuration Types**:
```python
# Standard MCP Server
{
    "name": "Gmail Integration",
    "qualifiedName": "gmail",
    "config": {"profile_id": "uuid"},
    "enabledTools": ["send_email", "read_email"]
}

# Composio Integration
{
    "type": "composio",
    "name": "Slack Bot",
    "toolkit_slug": "slack",
    "config": {"profile_id": "uuid"},
    "enabledTools": ["send_message"]
}

# Pipedream Integration  
{
    "type": "pipedream",
    "name": "Custom Webhook",
    "app_slug": "custom_app",
    "config": {"external_user_id": "user123"}
}
```

#### **10. AgentPress Core Tools** (Built-in Capabilities)
```python
CORE_TOOLS = {
    'sb_shell_tool': True,        # Terminal/command execution
    'sb_files_tool': True,        # File management & editing  
    'browser_tool': True,         # Web automation & scraping
    'web_search_tool': True,      # Internet search
    'sb_vision_tool': True,       # Image processing
    'sb_deploy_tool': True,       # Application deployment
    'sb_expose_tool': True,       # Port exposure for demos
    'data_providers_tool': True,  # API integrations (Zillow, Amazon, Yahoo Finance)
    'youtube_tool': True,         # Native YouTube integration
    'task_list_tool': True,       # Workflow management
    'message_tool': True,         # Communication
    'expand_msg_tool': True       # Message processing
}
```

#### **5. MCP (Model Context Protocol) Integration**
- **External Tools**: 2700+ available integrations
- **Connection Manager**: `MCPToolWrapper` handles tool registration
- **Credential Management**: Encrypted profiles with Fernet encryption
- **Discovery**: Search and configure external services
- **Tool Registration**: Dynamic registration based on agent configuration
- **Security**: Per-agent MCP toggles for fine-grained control

#### **6. YouTube Integration (CRITICAL - Native, Not MCP)**
- **Zero-Questions Protocol**: Never ask about account/channel preferences
- **OAuth Automation**: User handles all selections in OAuth flow
- **Native Tools**:
  ```python
  - youtube_authenticate()      # Shows OAuth button
  - youtube_channels()         # Lists connected channels  
  - youtube_upload_video()     # Smart upload with auto-metadata
  - youtube_list_captions()    # Caption management
  - youtube_download_caption() # Download captions
  - youtube_list_channel_videos() # Video browsing
  - youtube_list_playlists()   # Playlist management
  - youtube_manage_video()     # Full video management
  - youtube_smart_search()     # Multi-type search
  ```
- **File System**: Uses reference ID system, NOT workspace files
- **Channel Management**: Auto-detection and smart selection

### Automation Systems Deep Dive

#### **11. Workflow System Architecture**
**Workflow Structure** (`backend/supabase/migrations/*_agent_workflows.sql`):
```python
# Database Schema
{
    "id": "workflow-uuid",
    "agent_id": "agent-uuid",
    "name": "Research Playbook",
    "status": "active|draft|inactive",
    "is_default": False,
    "steps": [
        {
            "id": "start-node",
            "type": "instruction",  # instruction|tool|condition
            "name": "Research Phase",
            "children": [
                {
                    "type": "instruction", 
                    "name": "Execute Template",
                    "config": {
                        "playbook": {
                            "template": "Research {{company}} and update {{sheet_id}}",
                            "variables": [
                                {"key": "company", "label": "Company Name", "required": true},
                                {"key": "sheet_id", "label": "Sheet ID", "required": false}
                            ]
                        }
                    }
                }
            ]
        }
    ]
}
```

**Workflow Tools** (`backend/agent/tools/agent_builder_tools/workflow_tool.py`):
```python
# Available workflow operations
- create_workflow(name, steps, status="draft")
- get_workflows(agent_id) 
- update_workflow(workflow_id, name, steps, status)
- delete_workflow(workflow_id)
- activate_workflow(workflow_id, is_active)
```

**Workflow Types**:
1. **Playbooks**: Template-based with variable substitution (`{{variable}}`)
2. **Tool Workflows**: Structured tool execution with branching
3. **Conditional Workflows**: If/then logic based on results

#### **12. Trigger System Architecture**
**Scheduled Triggers** (Production):
```python
{
    "trigger_id": "uuid",
    "agent_id": "agent-uuid",
    "name": "Daily Report",
    "cron_expression": "0 9 * * *",  # 9 AM daily
    "execution_type": "workflow|agent",
    "workflow_id": "optional-workflow-id",
    "agent_prompt": "optional-direct-prompt"
}
```

**Event-based Triggers** (Non-Production via Composio):
- Real-time triggers from Gmail, Slack, GitHub, Calendar, etc.
- Webhook system: External Service → Composio → Suna webhook
- Complex trigger configurations with validation

#### **8. Workflow & Playbook System**
```json
{
  "id": "workflow-id",
  "name": "Research Playbook", 
  "status": "active|draft|inactive",
  "steps": [
    {
      "id": "start-node",
      "type": "instruction",
      "name": "Start",
      "children": [
        {
          "type": "instruction",
          "name": "Execute Workflow Template",
          "config": {
            "playbook": {
              "template": "Research {{company}} and update {{sheet_id}}",
              "variables": [
                {"key": "company", "label": "Company Name", "required": true},
                {"key": "sheet_id", "label": "Sheet ID", "required": false}
              ]
            }
          }
        }
      ]
    }
  ]
}
```

### Data Systems

#### **9. YouTube/Social Media Upload System**
- **Universal Endpoint**: `/youtube/universal-upload`
- **Reference ID System**: 32-char hex for file management
- **Chunked Upload**: 1MB chunks with progress tracking
- **Tables**: 
  - `video_file_references` (file data)
  - `upload_references` (metadata)
  - `youtube_channels` (connected channels)
- **Smart Detection**: Auto-routing to appropriate platforms

#### **10. Database Schema** (Key Tables)
```sql
-- Core agent management
agents: agent_id, name, description, avatar, current_version_id, account_id
agent_versions: version_id, agent_id, config, version_number, is_active
agent_workflows: id, agent_id, name, steps, status, is_default
agent_triggers: trigger_id, agent_id, provider_id, config, is_active

-- User & thread management  
threads: thread_id, project_id, account_id, metadata
messages: message_id, thread_id, type, content, role
projects: project_id, account_id, sandbox

-- Integration & credentials
credential_profiles: profile_id, account_id, app_slug, config
mcp_toggles: agent_id, user_id, mcp_id, is_enabled

-- File & social media
file_uploads: file_id, account_id, file_path, metadata
video_file_references: reference_id, user_id, file_data, metadata
youtube_channels: channel_id, user_id, name, subscriber_count
```

#### **11. Authentication & Security**
- **Supabase JWT tokens** (validated without signature)
- **Row-level security** on all user tables
- **Agent ownership** verification
- **Credential encryption** with Fernet
- **MCP toggles** for fine-grained integration control
- **Billing integration** with usage limits

### Key File Locations

#### **Agent System**
- **Agent Core**: `backend/agent/run.py` (AgentRunner, execution flow)
- **Default Prompt**: `backend/agent/prompt.py` (1500+ line Suna system prompt)
- **Agent Builder**: `backend/agent/agent_builder_prompt.py` (500+ line builder prompt)
- **Agent Config**: `backend/agent/config_helper.py` (configuration extraction)
- **Agent Versioning**: `backend/agent/versioning/version_service.py`

#### **Tools & Integrations**
- **Core Tools**: `backend/agent/tools/` (AgentPress built-in tools)
- **Agent Builder Tools**: `backend/agent/tools/agent_builder_tools/`
  - `agent_config_tool.py` (update_agent, get_current_agent_config)
  - `trigger_tool.py` (scheduled & event-based triggers)
  - `workflow_tool.py` (create/manage workflows)
  - `credential_profile_tool.py` (MCP credential management)
  - `mcp_search_tool.py` (search external integrations)
- **MCP Integration**: `backend/agent/tools/mcp_tool_wrapper.py`
- **YouTube Tools**: `backend/agent/tools/youtube_complete_mcp_tool.py`

#### **AgentPress Framework**
- **Thread Manager**: `backend/agentpress/thread_manager.py` (conversation management)
- **Tool Registry**: `backend/agentpress/tool_registry.py` (tool registration)
- **Tool Base**: `backend/agentpress/tool.py` (base tool classes)
- **Response Processor**: `backend/agentpress/response_processor.py`
- **Context Manager**: `backend/agentpress/context_manager.py`

#### **Backend Services**
- **API Endpoints**: `backend/api.py`, `backend/agent/api.py`
- **Services**: `backend/services/` (billing, LLM, supabase, etc.)
- **Triggers**: `backend/triggers/` (trigger execution system)
- **YouTube MCP**: `backend/youtube_mcp/` (native YouTube integration)
- **MCP Toggles**: `backend/services/mcp_toggles.py`

#### **Database & Migrations**
- **Migrations**: `backend/supabase/migrations/` (schema evolution)
- **Key Migrations**:
  - `20250524062639_agents_table.sql` (agent management)
  - `20250525000000_agent_versioning.sql` (version control)
  - `20250705161610_agent_workflows.sql` (workflow system)
  - `20250630070510_agent_triggers.sql` (trigger system)
  - `20250818000000_agent_mcp_toggles.sql` (MCP control)

#### **Frontend Components**
- **Thread Interface**: `frontend/src/components/thread/`
- **Agent Management**: `frontend/src/app/(dashboard)/agents/`
- **Social Media**: `frontend/src/components/social-media/`
- **MCP Integration**: `frontend/src/components/thread/chat-input/mcp-connections-dropdown.tsx`

## Tool & MCP System Architecture

### Core Tool System

#### **Tool Base Classes & Inheritance Hierarchy**
```python
# Base tool class for AgentPress framework
Tool (agentpress.tool)
├── AgentBuilderBaseTool  # For agent builder-specific tools
├── SandboxTool          # For sandbox-based execution tools
└── MCPToolWrapper       # For external MCP integrations
```

#### **Tool Registration & Schema System**
```python
# Tool schema definition using OpenAPI
@openapi_schema({
    "type": "function",
    "function": {
        "name": "tool_name",
        "description": "Clear tool purpose and usage",
        "parameters": {
            "type": "object",
            "properties": {
                "param": {"type": "string", "description": "Parameter description"}
            },
            "required": ["param"]
        }
    }
})
async def tool_method(self, param: str) -> ToolResult:
    return self.success_response(result=data)
```

### MCP (Model Context Protocol) Integration

#### **MCP System Architecture**
The MCP system enables external tool integrations through standardized protocols:

```python
# MCP Tool Wrapper - Core integration class
class MCPToolWrapper(Tool):
    - Connection management via MCPConnectionManager
    - Dynamic tool registration via DynamicToolBuilder
    - Tool execution via MCPToolExecutor
    - Redis caching via MCPSchemaRedisCache
    - Custom MCP handling via CustomMCPHandler
```

#### **MCP Connection Types & Transport Protocols**
```python
# Support for multiple MCP connection types:
1. Server-Sent Events (SSE): Real-time streaming connections
2. HTTP: Standard HTTP-based connections  
3. Stdio: Command-line process connections
4. Custom: Composio, Pipedream, and other specialized integrations

# Connection manager handles all transport protocols
class MCPConnectionManager:
    async def connect_sse_server(url, headers)
    async def connect_http_server(url) 
    async def connect_stdio_server(command, args, env)
```

#### **Dynamic Tool Registration System**
```python
class DynamicToolBuilder:
    def create_dynamic_methods(tools_info, custom_tools, execute_callback):
        # Creates runtime Python methods for MCP tools
        # Converts MCP schemas to AgentPress ToolSchema format
        # Handles tool name parsing and method generation
        
    def _parse_tool_name(tool_name) -> (method_name, clean_name, server_name):
        # Handles custom_ prefixes and server identification
        # Example: "custom_github_create_issue" -> "create_issue", "github"
```

#### **MCP Execution & Error Handling**
```python
class MCPToolExecutor:
    async def execute_tool(tool_name, arguments):
        if tool_name in custom_tools:
            return await self._execute_custom_tool(tool_name, arguments)
        else:
            return await self._execute_standard_tool(tool_name, arguments)
    
    # Specialized execution for different MCP types
    async def _execute_composio_tool()  # Composio integrations
    async def _execute_pipedream_tool() # Pipedream workflows
    async def _execute_sse_tool()       # SSE connections
    async def _execute_http_tool()      # HTTP connections
```

#### **Redis-Based MCP Caching System**
```python
class MCPSchemaRedisCache:
    # Caches MCP tool schemas for 1-hour TTL
    # Dramatically improves startup performance
    # Config-based cache keys with MD5 hashing
    
    async def get(config) -> Optional[Dict]
    async def set(config, data)
    async def clear_pattern(pattern=None)
```

### Credential Management & Security

#### **Encryption System**
```python
# Fernet-based encryption for credential storage
def encrypt_data(data: str) -> str:
    # Uses MCP_CREDENTIAL_ENCRYPTION_KEY environment variable
    # Base64 encoded encrypted strings for database storage

def decrypt_data(encrypted_data: str) -> str:
    # Secure decryption with error handling
```

#### **MCP Toggle System**
```python
class MCPToggleService:
    # Per-agent, per-user MCP control system
    async def get_toggles(agent_id, user_id) -> Dict[str, bool]
    async def set_toggle(agent_id, user_id, mcp_id, enabled)
    async def is_enabled(agent_id, user_id, mcp_id) -> bool
    
    # Special handling for social media MCPs:
    # - YouTube channels: Auto-enable connected channels
    # - Other social: Default to disabled for security
    # - Standard MCPs: Default to enabled
```

#### **Credential Profile Management**
```python
class CredentialProfileTool(AgentBuilderBaseTool):
    # Composio integration management
    async def create_credential_profile(toolkit_slug, profile_name)
    async def configure_profile_for_agent(profile_id, enabled_tools)
    async def delete_credential_profile(profile_id)
    
    # Returns authentication URLs for OAuth flows
    # Handles profile connection status tracking
```

### Agent Builder Tool System

#### **Agent Configuration Management**
```python
class AgentConfigTool(AgentBuilderBaseTool):
    async def update_agent(
        name, description, system_prompt, 
        agentpress_tools, configured_mcps, avatar
    ):
        # Version control integration
        # Suna protection for core identity
        # MCP configuration merging
        # Real-time tool registration
```

#### **MCP Search & Discovery**
```python
class MCPSearchTool(AgentBuilderBaseTool):
    async def search_mcp_servers(query, limit=10)
    async def get_popular_mcp_servers()
    async def get_mcp_server_tools(qualified_name)
    async def test_mcp_server_connection(qualified_name)
```

### Frontend Tool Rendering System

#### **Tool View Components**
```typescript
// Tool view component architecture
interface ToolViewProps {
    name: string;
    assistantContent?: string;
    toolContent?: any;
    assistantTimestamp?: string;
    toolTimestamp?: string;
    isSuccess?: boolean;
    isStreaming?: boolean;
}

// Specialized tool views:
- YouTubeToolView: Social media channel display
- YouTubeUploadProgressView: Real-time upload tracking  
- YouTubeUploadResultView: Completed upload display
- LoadingState: Universal loading component
```

#### **MCP Connection Dropdown**
```typescript
// Real-time MCP toggle interface
export const MCPConnectionsDropdown: React.FC = ({agentId, disabled}) => {
    // Social media platform grouping
    // Real-time toggle state management
    // OAuth authentication handling
    // Profile picture display for channels
}

// Features:
- Social media platform grouping (YouTube, Instagram, etc.)
- Live toggle switching with optimistic UI updates
- OAuth popup handling with success callbacks
- Search and filtering capabilities
```

#### **React Query Integration**
```typescript
// MCP toggle management hooks
export const useAgentMcpConfigurations = (agentId) => {
    // Combines multiple data sources:
    // - YouTube channels from /youtube/channels
    // - Composio profiles from credential system
    // - Agent MCP configurations from agent data
    // - Toggle states from /agents/{id}/mcp-toggles
}

export const useUpdateAgentMcpToggle = () => {
    // Real-time toggle updates with cache invalidation
    // Special handling for YouTube channel toggles
    // LocalStorage events for live UI updates
}
```

### YouTube Integration (Native, Not MCP)

#### **Zero-Questions Protocol Implementation**
```python
# YouTube tools never ask about account/channel preferences
# All user interactions happen in OAuth popup
# Channel selection is automatic based on connected accounts

class YouTubeCompleteMCPTool:
    async def youtube_authenticate() -> ToolResult:
        # Returns OAuth URL for popup authentication
        
    async def youtube_channels() -> ToolResult:
        # Auto-enabled connected channels via toggle system
        
    async def youtube_upload_video(file_reference_id, **kwargs) -> ToolResult:
        # Uses reference ID system, not workspace files
        # Smart metadata extraction and channel selection
```

#### **Channel Auto-Detection & Toggle Integration**
```python
# YouTube channels automatically enabled when connected
if mcp_id.startswith("social.youtube."):
    channel_id = mcp_id.replace("social.youtube.", "")
    # Check if channel exists and is active
    if channel_exists_and_active:
        await self.set_toggle(agent_id, user_id, mcp_id, True)
        return True
```

## Frontend Architecture Deep Dive

### Application Structure & Routing

#### **App Router Architecture (Next.js 15)**
```bash
frontend/src/app/
├── (dashboard)/                    # Dashboard group route
│   ├── layout.tsx                  # Dashboard layout wrapper
│   ├── dashboard/page.tsx          # Main dashboard page
│   ├── agents/                     # Agent management
│   │   ├── page.tsx                # Agents grid/marketplace
│   │   ├── [threadId]/page.tsx     # Agent chat interface
│   │   └── config/[agentId]/       # Agent configuration
│   ├── projects/[projectId]/thread/[threadId]/  # Project threads
│   ├── social-media/page.tsx       # Social media uploads
│   ├── settings/                   # User settings
│   └── (personalAccount)/          # Personal account routes
│       └── (teamAccount)/          # Team account routes
├── (home)/                         # Marketing pages
│   ├── layout.tsx                  # Home layout
│   └── page.tsx                    # Landing page
├── auth/                           # Authentication flow
├── api/                           # API routes & webhooks
│   ├── youtube/                    # YouTube API endpoints
│   ├── triggers/                   # Trigger webhooks
│   └── integrations/               # OAuth callbacks
├── share/[threadId]/              # Public thread sharing
└── layout.tsx                     # Root layout with providers
```

#### **Route Groups & Layout Hierarchy**
- **(dashboard)**: Protected dashboard routes with sidebar navigation
- **(home)**: Public marketing and landing pages
- **(personalAccount)** / **(teamAccount)**: Account-specific routes
- **Dynamic routes**: `[threadId]`, `[agentId]`, `[projectId]` for entity-specific pages

### Core Component Architecture

#### **1. Thread System (Conversation Interface)**
```bash
components/thread/
├── ThreadContent.tsx               # Main message rendering engine
├── chat-input/                     # Input system
│   ├── chat-input.tsx             # Main input component with file handling
│   ├── message-input.tsx          # Message textarea with voice
│   ├── file-upload-handler.tsx    # File upload processing
│   ├── smart-file-handler.tsx     # Social media auto-detection
│   ├── mcp-connections-dropdown.tsx # MCP integration selector
│   └── unified-config-menu.tsx    # Advanced agent configuration
├── tool-views/                     # Tool result renderers
│   ├── YouTubeToolView.tsx        # YouTube operations
│   ├── BrowserToolView.tsx        # Web browsing
│   ├── CompleteToolView.tsx       # Task completion
│   └── [50+ tool-specific views]  # Dynamic tool renderers
├── content/                        # Content rendering
│   ├── ShowToolStream.tsx         # Streaming tool execution
│   ├── ThreadSkeleton.tsx         # Loading states
│   └── agent-avatar.tsx           # Dynamic agent avatars
├── attachment-group.tsx            # File attachment grid
├── file-attachment.tsx             # Individual file renderer
└── file-browser.tsx                # Sandbox file explorer
```

**Key Features:**
- **Universal Message Rendering**: Handles text, markdown, XML tool calls, attachments
- **Real-time Streaming**: Live tool execution with progress indicators
- **File Attachment System**: Drag-drop, preview, workspace integration
- **Agent-aware UI**: Dynamic avatars, names, tool permissions
- **Tool Call Parsing**: XML → React components for 50+ tool types

#### **2. Agent Management System**
```bash
components/agents/
├── agents-grid.tsx                 # Agent listing with search/filter
├── agent-builder-chat.tsx          # Agent Builder conversation interface
├── config/                         # Agent configuration UI
│   ├── agent-header.tsx           # Agent profile editor
│   ├── configuration-tab.tsx      # System prompt, tools, model
│   ├── model-selector.tsx         # LLM model selection
│   └── version-alert.tsx          # Version management
├── mcp/                           # MCP Integration Management
│   ├── mcp-configuration-new.tsx  # MCP server setup
│   ├── configured-mcp-list.tsx    # Active integrations
│   ├── mcp-server-card.tsx        # Individual MCP server
│   └── tools-manager.tsx          # Tool enablement
├── triggers/                       # Automation System
│   ├── agent-triggers-configuration.tsx # Main triggers UI
│   ├── event-based-trigger-dialog.tsx   # Real-time triggers
│   ├── configured-triggers-list.tsx     # Active triggers
│   └── one-click-integrations.tsx       # Quick setup
├── workflows/                      # Workflow Builder
│   ├── agent-workflows-configuration.tsx # Main workflows UI
│   └── conditional-workflow-builder.tsx  # Visual workflow editor
├── composio/                       # Composio Integration (2700+ tools)
│   ├── composio-registry.tsx      # Tool marketplace
│   ├── composio-connector.tsx     # Authentication flow
│   └── composio-tools-manager.tsx # Tool configuration
├── new-agent-dialog.tsx           # Agent creation flow
├── agent-version-switcher.tsx     # Version management
└── marketplace-agent-preview-dialog.tsx # Public agent templates
```

**Key Features:**
- **Agent Builder Chat**: Interactive agent configuration through conversation
- **MCP Integration**: 2700+ external tools (Gmail, Slack, GitHub, etc.)
- **Version Control**: Full configuration versioning with rollback
- **Trigger System**: Scheduled and event-based automation
- **Workflow Builder**: Visual multi-step process creation
- **Tool Management**: Granular tool enablement and configuration

#### **3. Dashboard & Navigation**
```bash
components/dashboard/
├── layout-content.tsx              # Main dashboard wrapper with auth
├── custom-agents-section.tsx      # Agent overview
├── examples.tsx                    # Task examples
└── maintenance-banner.tsx         # System notifications

components/sidebar/
├── sidebar-left.tsx               # Main navigation sidebar
├── nav-agents.tsx                 # Agent navigation tree
├── nav-user-with-teams.tsx        # Account switcher
├── kortix-logo.tsx                # Branding
└── search-search.tsx              # Global search
```

**Key Features:**
- **Responsive Sidebar**: Collapsible with keyboard shortcuts (CMD+B)
- **Mobile Navigation**: Floating menu button with touch optimization
- **Account Management**: Personal/team account switching
- **Agent Organization**: Hierarchical agent navigation
- **Health Monitoring**: API status with fallback to maintenance page

#### **4. Social Media & File Management**
```bash
components/social-media/            # Social media upload interface
components/thread/chat-input/
├── youtube-upload-handler.tsx     # YouTube-specific logic
├── smart-file-handler.tsx         # Auto-platform detection
└── social-media-handler.ts        # Multi-platform routing

components/thread/tool-views/
├── YouTubeUploadProgressView.tsx  # Real-time upload tracking
├── YouTubeUploadResultView.tsx    # Upload completion
└── UniversalSocialMediaProgressView.tsx # Multi-platform progress
```

**Key Features:**
- **Universal Upload System**: Auto-detects target platform from context
- **Reference ID System**: 32-char hex IDs for seamless file management
- **Smart Detection**: Video files → YouTube, Images → multiple platforms
- **Progress Tracking**: Real-time upload progress with chunked uploads
- **Channel Management**: Auto-selection of connected YouTube channels

### State Management Architecture

#### **1. React Query (TanStack Query) - Server State**
```bash
hooks/react-query/
├── agents/                         # Agent-related queries
│   ├── use-agents.ts              # Agent listing and search
│   ├── use-agent-versions.ts      # Version management
│   ├── use-agent-mcp-toggle.ts    # MCP enablement
│   └── use-agent-workflows.ts     # Workflow queries
├── threads/                        # Thread and message management
│   ├── use-threads.ts             # Thread listing
│   ├── use-messages.ts            # Message history
│   ├── use-agent-run.ts           # Agent execution
│   └── use-billing-status.ts      # Usage limits
├── files/                          # File management
│   ├── use-file-queries.ts        # File content fetching
│   ├── use-file-mutations.ts      # File operations
│   └── use-sandbox-mutations.ts   # Sandbox file operations
├── composio/                       # External integrations
│   ├── use-composio.ts            # MCP server management
│   ├── use-composio-profiles.ts   # Credential profiles
│   └── use-composio-triggers.ts   # Event-based triggers
├── social-media/
│   └── use-social-accounts.ts     # Connected social accounts
└── subscriptions/
    ├── use-billing.ts             # Billing information
    └── use-subscriptions.ts       # Subscription status
```

**Query Patterns:**
```typescript
// Optimistic updates with rollback
const { mutate: toggleMCP } = useAgentMCPToggle({
  onMutate: async ({ agentId, mcpId, enabled }) => {
    // Optimistic update
    await queryClient.cancelQueries(['agents', agentId]);
    const previousAgent = queryClient.getQueryData(['agents', agentId]);
    queryClient.setQueryData(['agents', agentId], (old: any) => ({
      ...old,
      mcps: old.mcps.map(mcp => 
        mcp.id === mcpId ? { ...mcp, enabled } : mcp
      )
    }));
    return { previousAgent };
  },
  onError: (err, variables, context) => {
    // Rollback on error
    queryClient.setQueryData(['agents', variables.agentId], context.previousAgent);
  },
  onSettled: (data, error, variables) => {
    // Refetch to ensure consistency
    queryClient.invalidateQueries(['agents', variables.agentId]);
  }
});
```

#### **2. Zustand Stores - Client State**
```bash
lib/stores/
├── agent-selection-store.ts       # Selected agent persistence
├── agent-version-store.ts         # Version management
└── auth-tracking.ts               # Authentication state
```

**Agent Selection Store:**
```typescript
interface AgentSelectionState {
  selectedAgentId: string | undefined;
  hasInitialized: boolean;
  
  initializeFromAgents: (agents: Agent[], threadAgentId?: string) => void;
  autoSelectAgent: (agents: Agent[]) => void;
  setSelectedAgent: (agentId: string | undefined) => void;
  isSunaAgent: (agents: Agent[]) => boolean;
}

// Persistent with localStorage
export const useAgentSelectionStore = create<AgentSelectionState>()(
  persist((set, get) => ({
    selectedAgentId: undefined,
    hasInitialized: false,
    // ... implementation
  }), {
    name: 'agent-selection-storage',
    partialize: (state) => ({ selectedAgentId: state.selectedAgentId }),
  })
);
```

#### **3. Context Providers**
```bash
contexts/
├── SubscriptionContext.tsx        # Shared billing data
├── DeleteOperationContext.tsx     # Bulk operations
└── BillingContext.tsx             # Payment flow

app/providers.tsx                   # Root provider composition
```

**Context Pattern:**
```typescript
export function SubscriptionProvider({ children }: { children: ReactNode }) {
  const { data: subscriptionData, isLoading, error, refetch } = useSubscriptionQuery();
  
  return (
    <SubscriptionContext.Provider value={{ subscriptionData, isLoading, error, refetch }}>
      {children}
    </SubscriptionContext.Provider>
  );
}

// Convenience hook with fallback
export function useSharedSubscription() {
  const context = useContext(SubscriptionContext);
  const fallbackQuery = useSubscriptionQuery();
  
  // Use context if available, fallback to direct query
  return context || fallbackQuery;
}
```

#### **4. Tool Call State Management**
```typescript
// Global tool call context for thread communication
export const ToolCallsContext = createContext<{
  toolCalls: ParsedTag[];
  setToolCalls: React.Dispatch<React.SetStateAction<ParsedTag[]>>;
}>({
  toolCalls: [],
  setToolCalls: () => {},
});

// Tool call parsing and pairing
export interface ParsedTag {
  tagName: string;
  attributes: Record<string, string>;
  content: string;
  id: string;                       // Unique ID per call
  resultTag?: ParsedTag;           // Reference to result
  isToolCall?: boolean;            // vs result
  isPaired?: boolean;              // Completion status
  status?: 'running' | 'completed' | 'error';
  vncPreview?: string;             // VNC screenshot for browser tools
}
```

### File Upload & Attachment System

#### **Universal File Handling**
```typescript
// Smart file routing based on context and content
const handleFiles = async (
  files: File[],
  sandboxId: string | undefined,
  setPendingFiles: React.Dispatch<React.SetStateAction<File[]>>,
  setUploadedFiles: React.Dispatch<React.SetStateAction<UploadedFile[]>>,
  setIsUploading: React.Dispatch<React.SetStateAction<boolean>>,
  messages: any[],
  queryClient?: any,
  userMessage?: string,          // Context for intent detection
  userId?: string,               // For reference system
) => {
  for (const file of files) {
    // Create base file info
    const fileInfo: UploadedFile = {
      name: normalizeFilenameToNFC(file.name),
      path: `/workspace/${normalizedName}`,
      size: file.size,
      type: file.type,
      localUrl: URL.createObjectURL(file)
    };
    
    // Social media detection
    const shouldCreateReference = shouldUseReferenceSystem(userMessage || '', file.type, file.name) ||
                                 (!userMessage && (file.type.startsWith('video/') || file.type.startsWith('image/')));
    
    if (shouldCreateReference && userId) {
      // Create reference ID for social media uploads
      const response = await fetch(`${API_URL}/youtube/prepare-upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${session.access_token}` },
        body: formData,
      });
      
      if (response.ok) {
        const data = await response.json();
        fileInfo.referenceId = data.reference_id;
        fileInfo.expiresAt = data.expires_at;
      }
    }
  }
};
```

#### **File Upload Patterns**
1. **Workspace Files**: Traditional sandbox file system (`/workspace/...`)
2. **Reference System**: Social media uploads with 32-char hex IDs
3. **Smart Detection**: Auto-routing based on file type and user intent
4. **Chunked Uploads**: 1MB chunks for large files with progress tracking
5. **Local Previews**: Blob URLs for immediate UI feedback

### Real-time Systems

#### **1. Supabase Real-time Integration**
```typescript
// Real-time YouTube account management
export function useRealtimeYouTubeAccounts(agentId?: string) {
  const [accounts, setAccounts] = useState<RealtimeYouTubeAccount[]>([]);
  
  useEffect(() => {
    const supabase = createClient();
    
    // Initial fetch
    const fetchAccounts = async () => {
      const { data } = await supabase
        .from('agent_social_accounts')
        .select('*')
        .eq('agent_id', agentId)
        .eq('platform', 'youtube');
      setAccounts(data || []);
    };
    
    fetchAccounts();
    
    // Real-time subscription
    const subscription = supabase
      .channel(`youtube_accounts_${agentId}`)
      .on('postgres_changes', {
        event: '*',
        schema: 'public',
        table: 'agent_social_accounts',
        filter: `agent_id=eq.${agentId} AND platform=eq.youtube`
      }, (payload) => {
        // Immediate UI updates based on database changes
        setAccounts(current => {
          if (payload.eventType === 'INSERT') {
            return [...current, payload.new as RealtimeYouTubeAccount];
          } else if (payload.eventType === 'UPDATE') {
            return current.map(acc => 
              acc.account_id === payload.new.account_id 
                ? payload.new as RealtimeYouTubeAccount 
                : acc
            );
          } else if (payload.eventType === 'DELETE') {
            return current.filter(acc => acc.account_id !== payload.old.account_id);
          }
          return current;
        });
      })
      .subscribe();
    
    return () => subscription.unsubscribe();
  }, [agentId]);
  
  return { accounts, enabledAccounts: accounts.filter(acc => acc.enabled) };
}
```

#### **2. WebSocket Message Streaming**
```typescript
// Agent message streaming via WebSocket
export function useAgentStream(threadId: string) {
  const [streamingContent, setStreamingContent] = useState('');
  const [toolCalls, setToolCalls] = useState<ParsedTag[]>([]);
  
  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/agent/${threadId}`);
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'text_chunk') {
        setStreamingContent(prev => prev + data.content);
      } else if (data.type === 'tool_call') {
        const toolCall = parseXmlToolCall(data.content);
        setToolCalls(prev => [...prev, toolCall]);
      } else if (data.type === 'tool_result') {
        setToolCalls(prev => prev.map(call => 
          call.id === data.tool_id 
            ? { ...call, resultTag: parseXmlResult(data.content), status: 'completed' }
            : call
        ));
      }
    };
    
    return () => ws.close();
  }, [threadId]);
  
  return { streamingContent, toolCalls };
}
```

#### **3. Real-time Upload Progress**
```typescript
// Chunked upload with progress tracking
export function useChunkedUpload(file: File, referenceId: string) {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<'idle' | 'uploading' | 'completed' | 'error'>('idle');
  
  const upload = useCallback(async () => {
    const chunkSize = 1024 * 1024; // 1MB chunks
    const totalChunks = Math.ceil(file.size / chunkSize);
    let uploadedChunks = 0;
    
    for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++) {
      const start = chunkIndex * chunkSize;
      const end = Math.min(start + chunkSize, file.size);
      const chunk = file.slice(start, end);
      
      const formData = new FormData();
      formData.append('chunk', chunk);
      formData.append('reference_id', referenceId);
      formData.append('chunk_index', chunkIndex.toString());
      formData.append('total_chunks', totalChunks.toString());
      
      await fetch('/api/youtube/upload-chunk', {
        method: 'POST',
        body: formData,
      });
      
      uploadedChunks++;
      setProgress((uploadedChunks / totalChunks) * 100);
    }
    
    setStatus('completed');
  }, [file, referenceId]);
  
  return { upload, progress, status };
}
```

### UI Component System

#### **shadcn/ui Foundation**
- **Base Components**: 40+ components based on Radix UI primitives
- **Consistent Styling**: Tailwind CSS with design system tokens
- **Accessibility**: WCAG compliance through Radix primitives
- **Theming**: Dark/light mode with CSS custom properties

#### **Custom Component Patterns**
```typescript
// Compound component pattern for complex UI
export const ChatInput = forwardRef<ChatInputHandles, ChatInputProps>(
  ({ onSubmit, placeholder, loading, ...props }, ref) => {
    return (
      <Card className="rounded-3xl">
        <CardContent className="p-1.5">
          <AttachmentGroup files={uploadedFiles} onRemove={removeFile} />
          <MessageInput 
            ref={textareaRef}
            onSubmit={handleSubmit}
            onTranscription={handleTranscription}
          />
          <FileUploadHandler 
            ref={fileInputRef}
            onUpload={handleFileUpload}
          />
        </CardContent>
      </Card>
    );
  }
);

// Tool view registry pattern
export const ToolViewRegistry = {
  'youtube-upload': YouTubeToolView,
  'browser-action': BrowserToolView,
  'file-edit': FileEditToolView,
  'web-search': WebSearchToolView,
  // 50+ tool views...
};

export function ToolViewWrapper({ toolName, content, ...props }) {
  const ToolComponent = ToolViewRegistry[toolName] || GenericToolView;
  return <ToolComponent content={content} {...props} />;
}
```

#### **Responsive Design Patterns**
```typescript
// Mobile-first responsive hooks
export function useIsMobile() {
  return useMediaQuery("(max-width: 767px)");
}

// Mobile navigation optimization
export function FloatingMobileMenuButton() {
  const { setOpenMobile, openMobile } = useSidebar();
  const isMobile = useIsMobile();

  if (!isMobile || openMobile) return null;

  return (
    <Button
      onClick={() => setOpenMobile(true)}
      className="fixed top-6 left-4 z-50 md:hidden h-12 w-12 rounded-full"
    >
      <Menu className="h-5 w-5" />
    </Button>
  );
}
```

### Performance Optimizations

#### **1. React Query Optimizations**
- **Prefetching**: File content preloading for attachments
- **Optimistic Updates**: Instant UI feedback with rollback
- **Background Refetching**: Stale-while-revalidate pattern
- **Query Deduplication**: Automatic request deduplication
- **Infinite Queries**: Paginated data loading

#### **2. Code Splitting & Lazy Loading**
```typescript
// Route-based code splitting
const AgentsPage = lazy(() => import('./agents/page'));
const ThreadPage = lazy(() => import('./thread/[threadId]/page'));

// Component-based lazy loading
const ToolViewWrapper = lazy(() => import('./tool-views/wrapper'));
```

#### **3. Image & Asset Optimization**
- **Next.js Image**: Automatic optimization and lazy loading
- **SVG Components**: Inline SVG for icons and illustrations
- **Blob URLs**: Client-side file preview optimization

### Key Frontend File Locations

#### **Core Application Structure**
- **Root Layout**: `frontend/src/app/layout.tsx` (providers, metadata, fonts)
- **Provider Composition**: `frontend/src/app/providers.tsx` (contexts, query client)
- **Dashboard Layout**: `frontend/src/components/dashboard/layout-content.tsx`
- **Sidebar Navigation**: `frontend/src/components/sidebar/sidebar-left.tsx`

#### **Thread & Messaging System**
- **Thread Content**: `frontend/src/components/thread/ThreadContent.tsx`
- **Chat Input**: `frontend/src/components/thread/chat-input/chat-input.tsx`
- **Message Rendering**: `frontend/src/components/thread/content/ShowToolStream.tsx`
- **File Uploads**: `frontend/src/components/thread/chat-input/file-upload-handler.tsx`

#### **Agent Management**
- **Agent Grid**: `frontend/src/components/agents/agents-grid.tsx`
- **Agent Builder**: `frontend/src/components/agents/agent-builder-chat.tsx`
- **MCP Configuration**: `frontend/src/components/agents/mcp/mcp-configuration-new.tsx`
- **Agent Config**: `frontend/src/components/agents/config/configuration-tab.tsx`

#### **State Management**
- **React Query Hooks**: `frontend/src/hooks/react-query/` (organized by domain)
- **Zustand Stores**: `frontend/src/lib/stores/` (client-side state)
- **Context Providers**: `frontend/src/contexts/` (shared application state)

#### **UI Components**
- **Base Components**: `frontend/src/components/ui/` (shadcn/ui foundation)
- **File Renderers**: `frontend/src/components/file-renderers/` (content display)
- **Tool Views**: `frontend/src/components/thread/tool-views/` (50+ tool renderers)

### Tool Development Pattern

```python
from agent.tools.agent_builder_tools.base_tool import AgentBuilderBaseTool
from agentpress.tool import openapi_schema, ToolResult

class CustomTool(AgentBuilderBaseTool):
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "action_name",
            "description": "Clear description",
            "parameters": {
                "type": "object",
                "properties": {
                    "param": {"type": "string", "description": "..."}
                },
                "required": ["param"]
            }
        }
    })
    async def action_name(self, param: str) -> ToolResult:
        try:
            result = await self.perform_action(param)
            return self.success_response(result=result)
        except Exception as e:
            return self.fail_response(str(e))
```

### Tool Execution Flow

#### **1. Tool Registration Pipeline**
```python
# During agent initialization (backend/agent/run.py):
1. Core tools (MessageTool, TaskListTool, ExpandMessageTool)
2. Sandbox tools (Shell, Files, Browser, Vision, etc.)  
3. Utility tools (DataProviders, WebSearch)
4. Agent builder tools (if agent_id provided)
5. YouTube tools (native integration)
6. MCP tools (external integrations via MCPToolWrapper)
```

#### **2. MCP Tool Initialization**
```python
# MCPToolWrapper initialization sequence:
await _initialize_servers()  # Connect to all configured MCPs
    - Standard MCPs via mcp_service.connect_server()
    - Custom MCPs via CustomMCPHandler
    - Redis cache check for schemas
    - Parallel connection establishment

await _create_dynamic_tools()  # Generate runtime methods
    - Convert MCP schemas to AgentPress format
    - Create async method wrappers
    - Register schemas in tool registry
```

#### **3. Runtime Tool Execution**
```python
# Tool execution through AgentRunner:
1. Schema validation against OpenAPI spec
2. Tool method invocation with arguments
3. MCP tool routing:
   - Standard tools -> mcp_service.execute_tool()
   - Custom tools -> MCPToolExecutor with transport-specific handling
4. Result formatting and return
```

### Performance Optimizations

#### **1. Redis Caching Strategy**
- MCP schemas cached for 1-hour TTL
- Config-based cache keys prevent stale data
- Parallel initialization with cache hits
- Cache stats monitoring via `get_stats()`

#### **2. Connection Pooling**
- Persistent MCP connections via ClientSession
- Connection reuse across tool calls
- Timeout handling with graceful fallbacks
- Background connection health checks

#### **3. Real-time Updates**
- LocalStorage events for UI synchronization
- React Query cache invalidation
- Optimistic UI updates for toggles
- WebSocket-style tool view refreshes

## Database Migration Pattern

```sql
-- backend/supabase/migrations/YYYYMMDD_description.sql
BEGIN;

CREATE TABLE IF NOT EXISTS table_name (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_table_user_id ON table_name(user_id);

ALTER TABLE table_name ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own records" 
    ON table_name FOR ALL USING (auth.uid() = user_id);

COMMIT;
```

## Environment Variables

### Backend (.env)
```bash
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
REDIS_HOST=redis  # 'localhost' for local dev
REDIS_PORT=6380  # External port
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
MCP_CREDENTIAL_ENCRYPTION_KEY=
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000/api
```

## Critical Notes

- **Container Management**: Always use `python start.py`, never raw docker-compose commands
- **Redis Port**: External 6380, internal 6379
- **YouTube Uploads**: Use universal upload system with reference IDs
- **File Storage**: `video_file_references` (data) + `upload_references` (metadata)
- **Authentication**: JWT validation without signature (Supabase pattern)
- **Testing**: Run tests before commits, check coverage
- **Migrations**: Always include RLS policies and indexes

## Recent Changes (2025)

- Universal social media upload system with smart detection
- Reference ID system for seamless file management
- Chunked upload with real-time progress tracking
- YouTube channel auto-detection and selection
- Setup wizard with 14-step guided configuration
- Python SDK for external integrations
- Custom agents feature disabled (only Suna default agent active)
- Agent UUID validation system to prevent 404 errors

## Agent System Deep Dive

### Agent Execution Pipeline

#### **Runtime Configuration Assembly**
```python
# Agent config extracted from multiple sources
agent_config = extract_agent_config(agent_data, version_data)
{
    "agent_id": "uuid",
    "system_prompt": "Custom or default prompt",
    "agentpress_tools": {"tool_name": True/False},
    "configured_mcps": [{"name": "gmail", "enabledTools": ["send"]}],
    "custom_mcps": [{"type": "composio", "config": {...}}],
    "youtube_channels": [{"id": "UCxxx", "name": "Channel"}],  # Pre-computed
    "model": "openrouter/moonshotai/kimi-k2",
    "is_suna_default": False
}
```

#### **Agent Execution Flow (backend/agent/run.py)**
```python
class AgentRunner:
    # 1. Initialization
    def __init__(self, agent_config, thread_manager, tool_manager):
        self.agent_config = agent_config
        self.thread_manager = thread_manager  
        self.tool_manager = tool_manager
    
    # 2. Tool Registration (Order Matters!)
    async def setup_tools(self):
        # Core tools (always enabled)
        self.register_core_tools()
        # Sandbox tools (configurable)
        self.register_sandbox_tools()
        # Utility tools (YouTube, data providers)
        self.register_utility_tools()
        # Agent builder tools (if agent_id provided)
        self.register_agent_builder_tools()
        # MCP tools (external integrations)
        await self.register_mcp_tools()
    
    # 3. Main execution loop
    async def run(self):
        system_prompt = self.build_system_prompt()
        while True:
            response = await self.llm.generate(system_prompt + conversation)
            tool_calls = self.parse_tool_calls(response)
            if tool_calls:
                results = await self.execute_tools(tool_calls)
                conversation.append(tool_results)
            else:
                break
```

#### **Tool Registration Process**
```python
# ToolManager in backend/agent/run.py:70-110
async def _register_all_tools(self):
    # 1. Core tools (always enabled)
    self.register_tool(MessageTool())
    self.register_tool(TaskListTool()) 
    self.register_tool(ExpandMessageTool())
    
    # 2. Sandbox tools (configurable via agentpress_tools)
    if self.agent_config.get('agentpress_tools', {}).get('sb_shell_tool'):
        self.register_tool(ShellTool())
    if self.agent_config.get('agentpress_tools', {}).get('sb_files_tool'):
        self.register_tool(FilesTool())
    
    # 3. Utility tools
    if self.agent_config.get('agentpress_tools', {}).get('youtube_tool'):
        youtube_tool = YouTubeTool(
            self.user_id, 
            self.agent_config.get('youtube_channels', [])
        )
        self.register_tool(youtube_tool)
    
    # 4. Agent builder tools (if agent_id provided)
    if self.agent_config.get('agent_id'):
        self.register_tool(AgentConfigTool())
        self.register_tool(WorkflowTool())
        self.register_tool(TriggerTool())
    
    # 5. MCP tools (external integrations)
    await self._register_mcp_tools()
```

## YouTube Integration Deep Dive

### **CRITICAL UNDERSTANDING: YouTube is NATIVE, not MCP**

YouTube integration represents the gold standard for native tool implementation with these key principles:

#### **Zero-Questions Protocol Implementation**
```python
# System prompt enforces immediate action (backend/agent/prompt.py)
"User says 'YouTube' → Use tools IMMEDIATELY (no questions)"
"User says 'connect YouTube' → Use youtube_authenticate() NOW"
"User says 'add channel' → Use youtube_authenticate() INSTANTLY"

# Tool behavior follows this protocol
@openapi_schema({
    "name": "youtube_upload_video",
    "description": "Upload video with auto-discovery - NO QUESTIONS NEEDED"
})
async def youtube_upload_video(self, auto_discover: bool = True, **params):
    if auto_discover:
        # Find latest uploaded files automatically
        uploads = await self.file_service.get_latest_pending_uploads(user_id)
        video_id = uploads["video"]["reference_id"]
        # NO user prompting - just use the file
```

#### **Reference ID File System (CRITICAL INNOVATION)**
```python
# 32-character hex reference system replaces file paths
class YouTubeFileService:
    async def create_reference(self, user_id: str, file_data: bytes) -> str:
        reference_id = secrets.token_hex(16)  # 32 chars
        
        # Store in database with TTL
        await db.execute("""
            INSERT INTO video_file_references 
            (id, user_id, file_data, expires_at)
            VALUES ($1, $2, $3, $4)
        """, reference_id, user_id, file_data, expires_at)
        
        return reference_id
    
    async def auto_discover_uploads(self, user_id: str):
        # Smart pairing of video + thumbnail files
        video_refs = await self.get_pending_by_type(user_id, 'video')
        thumb_refs = await self.get_pending_by_type(user_id, 'thumbnail')
        
        return {
            "video": video_refs[0] if video_refs else None,
            "thumbnail": thumb_refs[0] if thumb_refs else None
        }
```

#### **YouTube Database Schema Details**
```sql
-- Channel management with encrypted tokens
youtube_channels (
    id VARCHAR PRIMARY KEY,              -- YouTube channel ID (UC...)
    user_id UUID REFERENCES auth.users(id),
    name VARCHAR NOT NULL,               -- Channel display name
    username VARCHAR,                    -- @handle
    profile_picture VARCHAR,             -- Avatar URL
    subscriber_count BIGINT,             -- Statistics
    access_token TEXT,                   -- Encrypted OAuth token
    refresh_token TEXT,                  -- Encrypted refresh token
    token_expires_at TIMESTAMPTZ,        -- Token expiration
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- File reference system (32-char hex IDs)
video_file_references (
    id VARCHAR(32) PRIMARY KEY,          -- Reference ID
    user_id UUID REFERENCES auth.users(id),
    file_name VARCHAR NOT NULL,
    file_data BYTEA,                     -- Binary file storage
    file_size BIGINT,
    mime_type VARCHAR,
    transcription JSONB,                 -- AI transcription
    generated_metadata JSONB,            -- AI-generated titles/descriptions  
    is_used BOOLEAN DEFAULT false,       -- Prevents reuse
    expires_at TIMESTAMPTZ,              -- TTL cleanup
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Upload progress tracking
youtube_uploads (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id),
    channel_id VARCHAR REFERENCES youtube_channels(id),
    video_id VARCHAR,                    -- YouTube video ID when complete
    title VARCHAR NOT NULL,
    description TEXT,
    upload_status VARCHAR DEFAULT 'pending', -- pending|uploading|processing|completed|failed
    upload_progress FLOAT DEFAULT 0.0,   -- Progress percentage
    bytes_uploaded BIGINT DEFAULT 0,     -- Progress tracking
    total_bytes BIGINT DEFAULT 0,
    video_reference_id VARCHAR(32),      -- Links to video_file_references
    thumbnail_reference_id VARCHAR(32),  -- Links to thumbnail
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### **YouTube OAuth Flow Details**
```python
# OAuth handler (backend/youtube_mcp/oauth.py)
class YouTubeOAuthHandler:
    SCOPES = [
        'https://www.googleapis.com/auth/youtube.upload',
        'https://www.googleapis.com/auth/youtube',
        'https://www.googleapis.com/auth/youtube.readonly'
    ]
    
    async def initiate_oauth(self, user_id: str):
        # 1. Generate OAuth URL with PKCE
        auth_url = self.build_authorization_url()
        
        # 2. Return OAuth button for frontend
        return {"oauth_url": auth_url, "state": state_token}
    
    async def handle_callback(self, code: str, state: str):
        # 3. Exchange code for tokens
        tokens = await self.exchange_code_for_tokens(code)
        
        # 4. Fetch user's channels
        channels = await self.fetch_user_channels(tokens['access_token'])
        
        # 5. Store all channels with encrypted tokens
        for channel in channels:
            await self.store_channel(user_id, channel, tokens)
        
        # 6. Auto-enable MCP toggles for all user agents
        await self.enable_channels_for_agents(user_id, channels)
```

## Background Processing Architecture

### **Dramatiq Worker System (backend/run_agent_background.py)**
```python
@dramatiq.actor
async def run_agent_background(
    agent_run_id: str,
    thread_id: str, 
    instance_id: str,
    project_id: str,
    model_name: str,
    enable_thinking: bool,
    reasoning_effort: str,
    stream: bool,
    enable_context_manager: bool,
    agent_config: dict = None,
    is_agent_builder: bool = False,
    target_agent_id: str = None,
    request_id: str = None
):
    # Redis-based coordination prevents duplicate runs
    lock_key = f"agent_run_lock:{agent_run_id}"
    acquired = await redis_client.set(lock_key, instance_id, nx=True, ex=30)
    
    if not acquired:
        return {"status": "skipped", "reason": "already_running"}
    
    try:
        # Execute agent with full configuration
        runner = AgentRunner(agent_config)
        await runner.run()
    finally:
        # Always cleanup lock
        await redis_client.delete(lock_key)
```

### **Redis Coordination (backend/services/redis.py)**
```python
# Production-optimized Redis configuration
class RedisManager:
    def __init__(self):
        self.pool = redis.ConnectionPool(
            host=REDIS_HOST,
            port=int(REDIS_PORT),
            max_connections=512,        # High concurrency support
            socket_timeout=30.0,        # Long operations
            socket_connect_timeout=15.0,
            health_check_interval=30,   # Health monitoring
            retry_on_timeout=True
        )
    
    # Multi-purpose usage patterns:
    # - Feature flags: feature_flag:{key}
    # - Agent locks: agent_run_lock:{run_id}
    # - Cache: youtube_channels:{user_id}
    # - Pub/sub: agent_events:{thread_id}
```

## Tool System Architecture Details

### **MCP Integration (backend/agent/tools/mcp_tool_wrapper.py)**
```python
class MCPToolWrapper(Tool):
    async def register_mcp_tools(self, mcp_configs: List[Dict]):
        for config in mcp_configs:
            if config['type'] == 'composio':
                # Composio toolkit integration
                await self.register_composio_toolkit(config)
            else:
                # Standard MCP server
                await self.register_mcp_server(config)
    
    async def execute_mcp_tool(self, tool_name: str, parameters: dict):
        # Schema caching for performance
        cache_key = f"mcp_schema:{hash(config)}"
        schema = await redis.get(cache_key)
        
        if not schema:
            schema = await self.fetch_mcp_schema(config)
            await redis.setex(cache_key, 3600, schema)  # 1-hour cache
        
        # Execute via MCP protocol
        return await self.mcp_client.call_tool(tool_name, parameters)
```

### **YouTube Tool Implementation Patterns**
```python
# Native tool following MCP schema patterns
class YouTubeCompleteMCPTool(Tool):
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_upload_video", 
            "description": "Upload video to YouTube with intelligent auto-discovery",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Video title"},
                    "channel_id": {"type": "string", "description": "Target channel"},
                    "auto_discover": {"type": "boolean", "default": True}
                }
            }
        }
    })
    async def youtube_upload_video(self, **params) -> ToolResult:
        # Zero-questions implementation
        if params.get('auto_discover', True):
            # Find files automatically via reference system
            uploads = await self.file_service.get_latest_pending_uploads(self.user_id)
            
        # Pre-computed channel validation
        channel = self.validate_channel(params.get('channel_id'))
        
        # Background upload with progress tracking
        upload_id = await self.upload_service.initiate_upload(...)
        
        return self.success_response({
            "upload_id": upload_id,
            "status": "uploading",
            "message": "Video upload started - progress will be tracked automatically"
        })
```

## Frontend Architecture Patterns

### **React Query Cache Management**
```typescript
// Strategic cache invalidation (frontend/src/hooks/react-query/agents/use-agent-mcp-toggle.ts)
const updateMCPToggle = useMutation({
  onSuccess: (data, variables) => {
    // Hierarchical invalidation
    queryClient.invalidateQueries({ queryKey: ['agent', variables.agentId] });
    queryClient.invalidateQueries({ queryKey: ['agent-mcp-toggles'] });
    
    // YouTube-specific real-time sync
    if (variables.mcpId.startsWith('social.youtube.')) {
      // Trigger immediate UI updates via localStorage events
      localStorage.setItem('youtube_toggle_changed', Date.now().toString());
      localStorage.removeItem('youtube_toggle_changed');
    }
    
    // Cross-tab synchronization
    window.dispatchEvent(new CustomEvent('mcp-toggle-updated', {
      detail: { agentId: variables.agentId, mcpId: variables.mcpId }
    }));
  }
});
```

### **Agent State Management**
```typescript
// Agent selection store with persistence (frontend/src/lib/stores/agent-selection-store.ts)
const useAgentSelectionStore = create<AgentSelectionState>()(
  persist(
    (set, get) => ({
      selectedAgentId: undefined,
      hasInitialized: false,
      
      initializeFromAgents: (agents, threadAgentId, onAgentSelect) => {
        // Multi-source priority resolution
        let selectedId: string | undefined;
        
        // 1. Thread agent (highest priority)
        if (threadAgentId && agents.some(a => a.agent_id === threadAgentId)) {
          selectedId = threadAgentId;
        }
        // 2. URL parameter
        else if (typeof window !== 'undefined') {
          const urlAgentId = new URLSearchParams(window.location.search).get('agent_id');
          if (urlAgentId && agents.some(a => a.agent_id === agentAgentId)) {
            selectedId = urlAgentId;
          }
        }
        // 3. Persisted selection
        else {
          const current = get().selectedAgentId;
          if (current && agents.some(a => a.agent_id === current)) {
            selectedId = current;
          }
        }
        // 4. Default fallback
        if (!selectedId && agents.length > 0) {
          const defaultSuna = agents.find(agent => agent.metadata?.is_suna_default);
          selectedId = defaultSuna ? defaultSuna.agent_id : agents[0].agent_id;
        }
        
        set({ selectedAgentId: selectedId, hasInitialized: true });
      }
    }),
    { name: 'agent-selection-storage' }
  )
);
```

### **File Upload Integration**
```typescript
// File upload handler with reference ID system
class FileUploadHandler {
  async handleYouTubeFiles(files: File[]): Promise<string[]> {
    const referenceIds: string[] = [];
    
    for (const file of files) {
      // Auto-detect file type
      const fileType = this.detectFileType(file);
      
      // Create reference
      const formData = new FormData();
      formData.append('file', file);
      formData.append('file_type', fileType);
      
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData
      });
      
      const result = await response.json();
      referenceIds.push(result.reference_id);
    }
    
    return referenceIds;
  }
}
```

## Production Architecture Insights

### **Multi-Instance Coordination**
```python
# Backend instance coordination via Redis
class InstanceManager:
    def __init__(self):
        self.instance_id = str(uuid.uuid4())
        self.heartbeat_interval = 30
    
    async def register_instance(self):
        # Register this backend instance
        await redis.setex(f"instance:{self.instance_id}", 60, {
          "started_at": datetime.utcnow().isoformat(),
          "worker_count": 4,
          "status": "healthy"
        })
    
    async def coordinate_agent_runs(self, agent_run_id: str):
        # Prevent duplicate agent runs across instances
        lock_acquired = await redis.set(
            f"agent_run_lock:{agent_run_id}", 
            self.instance_id, 
            nx=True, 
            ex=30
        )
        return lock_acquired
```

### **Error Handling and Recovery**
```python
# Comprehensive error handling patterns
class AgentExecutionError(Exception):
    def __init__(self, error_type: str, details: dict):
        self.error_type = error_type  # billing, authentication, tool_error, etc.
        self.details = details
        super().__init__(f"{error_type}: {details}")

# Graceful degradation strategies
try:
    result = await youtube_tool.upload_video(**params)
except BillingError as e:
    # Billing limit reached - show upgrade prompt
    return ToolResult(error=True, billing_error=True, details=e.details)
except AuthenticationError as e:
    # OAuth expired - trigger re-authentication
    return ToolResult(error=True, auth_required=True, oauth_url=e.oauth_url)
except Exception as e:
    # Generic error - log and continue
    logger.error("Tool execution failed", error=str(e), tool="youtube_upload_video")
    return ToolResult(error=True, message=f"Upload failed: {str(e)}")
```

### **Security Model Implementation**
```sql
-- Row Level Security (RLS) patterns used throughout
CREATE POLICY "Users manage own agents" 
    ON agents FOR ALL USING (
        EXISTS (
            SELECT 1 FROM accounts 
            WHERE accounts.id = agents.account_id 
            AND accounts.user_id = auth.uid()
        )
    );

CREATE POLICY "Users access own YouTube channels"
    ON youtube_channels FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users manage own file references"
    ON video_file_references FOR ALL USING (auth.uid() = user_id);
```

## Critical Implementation Guidelines

### **YouTube Development Patterns**
1. **Always use reference IDs** - Never direct file paths for social media files
2. **Follow zero-questions protocol** - Auto-discover, don't ask for file selection
3. **Pre-compute channel data** - Pass channels in agent config for performance
4. **Handle OAuth gracefully** - Provide clear OAuth buttons, handle token refresh
5. **Track upload progress** - Use background jobs with real-time updates
6. **Validate MCP toggles** - Check channel enablement before tool execution

### **Agent Development Best Practices**
1. **Tool Registration Order**: Core → Sandbox → Utility → Builder → MCP
2. **Configuration Validation**: Extract and validate all config sources
3. **Version Control**: Use agent versioning for all configuration changes
4. **MCP Integration**: Test connections before adding to agent configuration
5. **Error Recovery**: Provide context-aware guidance without re-prompting
6. **Performance**: Cache schemas, pre-compute data, use Redis coordination

This represents a production-grade AI agent platform with sophisticated integration patterns, real-time capabilities, and enterprise-level security and billing systems.

## COMPLETE YOUTUBE SYSTEM TECHNICAL SPECIFICATION

### **System Overview**
YouTube integration is a **NATIVE** (non-MCP) system providing seamless video upload, channel management, and OAuth authentication with zero-questions protocol.

### **Backend Architecture - Complete File Analysis**

#### **Core YouTube Service Files**

**1. YouTube MCP API (`backend/youtube_mcp/api.py`) - 1,369 lines**
```python
# Main API endpoints and routing
@app.post("/auth/initiate")           # Start OAuth flow
@app.get("/auth/callback")            # Handle OAuth callback  
@app.get("/channels")                 # List connected channels
@app.post("/upload")                  # Video upload to YouTube
@app.get("/upload-status/{upload_id}") # Track upload progress
@app.post("/prepare-upload")          # File upload to reference system
@app.get("/pending-uploads")          # Get latest pending files
@app.delete("/channels/{channel_id}") # Remove channel connection
@app.post("/universal-upload")        # Universal social media upload
```

**2. YouTube OAuth Handler (`backend/youtube_mcp/oauth.py`) - 440 lines**
```python
class YouTubeOAuthHandler:
    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/yt-analytics.readonly",
        "https://www.googleapis.com/auth/youtube.force-ssl"
    ]
    
    async def initiate_oauth(self, user_id: str) -> Dict[str, str]:
        # PKCE (Proof Key for Code Exchange) implementation
        code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        
        state = secrets.token_urlsafe(32)
        
        # Store OAuth session for security
        await self.store_oauth_session(state, code_verifier, user_id)
        
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={YOUTUBE_CLIENT_ID}&"
            f"redirect_uri={YOUTUBE_REDIRECT_URI}&"
            f"scope={'+'.join(self.SCOPES)}&"
            f"response_type=code&"
            f"state={state}&"
            f"code_challenge={code_challenge}&"
            f"code_challenge_method=S256&"
            f"access_type=offline&"
            f"prompt=consent"
        )
        
        return {"auth_url": auth_url, "state": state}
    
    async def handle_callback(self, code: str, state: str) -> Dict[str, Any]:
        # Exchange authorization code for tokens
        tokens = await self.exchange_code_for_tokens(code, state)
        
        # Fetch all user's channels
        channels_data = await self.youtube_service.fetch_user_channels(tokens['access_token'])
        
        # Store each channel with encrypted tokens
        stored_channels = []
        for channel_data in channels_data['items']:
            channel_info = await self.store_channel_with_tokens(
                user_id, channel_data, tokens
            )
            stored_channels.append(channel_info)
        
        return {"channels": stored_channels, "count": len(stored_channels)}
```

**3. YouTube Service (`backend/youtube_mcp/youtube_service.py`) - 611 lines**
```python
class YouTubeService:
    def __init__(self):
        self.base_url = "https://www.googleapis.com/youtube/v3"
        
    async def upload_video(self, user_id: str, channel_id: str, 
                          video_data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Upload video with progress tracking"""
        # Get valid access token with automatic refresh
        access_token = await self.oauth_handler.get_valid_token(user_id, channel_id)
        
        # Multipart upload for progress tracking
        upload_url = f"{self.base_url}/videos?uploadType=multipart&part=snippet,status"
        
        # Build metadata
        video_metadata = {
            "snippet": {
                "title": metadata.get("title", ""),
                "description": metadata.get("description", ""),
                "tags": metadata.get("tags", []),
                "categoryId": metadata.get("categoryId", "22")  # People & Blogs
            },
            "status": {
                "privacyStatus": metadata.get("privacy", "private"),
                "selfDeclaredMadeForKids": False
            }
        }
        
        # Chunked upload with progress tracking
        chunk_size = 1024 * 1024  # 1MB chunks
        total_size = len(video_data)
        uploaded = 0
        
        while uploaded < total_size:
            chunk = video_data[uploaded:uploaded + chunk_size]
            
            # Update progress in database
            await self.update_upload_progress(upload_id, uploaded, total_size)
            
            # Send chunk
            response = await self.send_chunk(chunk, uploaded, total_size, headers)
            uploaded += len(chunk)
        
        return await response.json()
```

**4. YouTube Channels Service (`backend/youtube_mcp/channels.py`) - 128 lines**
```python
class YouTubeChannelsService:
    async def get_channels_for_agent(self, user_id: str, agent_id: str) -> List[Dict[str, Any]]:
        """Get enabled channels for specific agent with MCP toggle filtering"""
        
        # Query with MCP toggle filtering
        channels = await self.db.fetch("""
            SELECT yc.*, asa.enabled
            FROM youtube_channels yc
            LEFT JOIN agent_social_accounts asa ON (
                asa.platform = 'youtube' AND
                asa.account_id = yc.id AND
                asa.agent_id = $2 AND
                asa.user_id = $1
            )
            WHERE yc.user_id = $1 
            AND yc.is_active = true
            AND (asa.enabled IS NULL OR asa.enabled = true)
            ORDER BY yc.name
        """, user_id, agent_id)
        
        return [self._format_channel_data(channel) for channel in channels]
    
    async def refresh_channel_info(self, user_id: str, channel_id: str) -> Dict[str, Any]:
        """Update channel metadata from YouTube API"""
        token = await self.oauth_handler.get_valid_token(user_id, channel_id)
        
        channel_data = await self.youtube_service.get_channel_info(channel_id, token)
        
        # Update database with fresh data
        await self.db.execute("""
            UPDATE youtube_channels 
            SET name = $3, username = $4, subscriber_count = $5, 
                profile_picture = $6, updated_at = NOW()
            WHERE user_id = $1 AND id = $2
        """, user_id, channel_id, 
            channel_data['snippet']['title'],
            channel_data['snippet'].get('customUrl', ''),
            int(channel_data['statistics']['subscriberCount']),
            channel_data['snippet']['thumbnails']['default']['url']
        )
        
        return self._format_channel_data(channel_data)
```

**5. YouTube Upload Service (`backend/youtube_mcp/upload.py`) - 479 lines**
```python
class YouTubeUploadService:
    async def upload_video_with_progress(self, user_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Complete video upload with progress tracking"""
        
        # Auto-discovery of pending files
        if params.get('auto_discover', True):
            uploads = await self.file_service.get_latest_pending_uploads(user_id)
            video_reference_id = uploads["video"]["reference_id"]
            thumbnail_reference_id = uploads.get("thumbnail", {}).get("reference_id")
        
        # Create upload tracking record
        upload_id = str(uuid.uuid4())
        upload_data = {
            "id": upload_id,
            "user_id": user_id,
            "channel_id": params["channel_id"],
            "title": params["title"],
            "description": params.get("description", ""),
            "upload_status": "pending",
            "video_reference_id": video_reference_id,
            "thumbnail_reference_id": thumbnail_reference_id,
        }
        
        await self.db.execute("""
            INSERT INTO youtube_uploads (id, user_id, channel_id, title, description, 
                                       upload_status, video_reference_id, thumbnail_reference_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, *upload_data.values())
        
        # Start background upload task
        asyncio.create_task(self._perform_upload_background(upload_id, params))
        
        return {
            "upload_id": upload_id,
            "status": "uploading",
            "message": "Video upload started. Progress will be tracked automatically."
        }
    
    async def _perform_upload_background(self, upload_id: str, params: Dict[str, Any]):
        """Background upload with progress tracking"""
        try:
            # Update status to uploading
            await self.update_upload_status(upload_id, "uploading")
            
            # Get file data
            video_data = await self.file_service.get_file_data(video_reference_id)
            
            # Upload with progress callbacks
            result = await self.youtube_service.upload_video_chunked(
                video_data, metadata, progress_callback=lambda progress: 
                self.update_upload_progress(upload_id, progress)
            )
            
            # Mark as completed
            await self.complete_upload(upload_id, result['id'], result)
            
        except Exception as e:
            # Mark as failed with error details
            await self.fail_upload(upload_id, str(e))
```

**6. YouTube File Service (`backend/services/youtube_file_service.py`) - 1,154 lines**
```python
class YouTubeFileService:
    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    MAX_VIDEO_SIZE = 128 * 1024 * 1024 * 1024  # 128GB YouTube limit
    MAX_THUMBNAIL_SIZE = 2 * 1024 * 1024        # 2MB thumbnail limit
    
    async def create_video_reference(self, user_id: str, file_data: bytes, 
                                   file_name: str, mime_type: str) -> str:
        """Create 32-char reference ID for file"""
        reference_id = secrets.token_hex(16)  # 32 characters
        
        # Detect file type
        file_type = self._detect_file_type(file_name, mime_type)
        
        # Set expiration (30 min quick upload, 24h prepared upload)
        expires_at = datetime.utcnow() + (
            timedelta(minutes=30) if file_type == 'video' else timedelta(hours=24)
        )
        
        # Store in database
        await self.db.execute("""
            INSERT INTO video_file_references 
            (id, user_id, file_name, file_data, file_size, mime_type, 
             file_type, expires_at, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
        """, reference_id, user_id, file_name, base64.b64encode(file_data).decode(),
            len(file_data), mime_type, file_type, expires_at)
        
        return reference_id
    
    async def get_latest_pending_uploads(self, user_id: str) -> Dict[str, Any]:
        """Auto-discovery: Find latest uploaded video and thumbnail"""
        
        # Get latest video file
        video_ref = await self.db.fetchrow("""
            SELECT * FROM video_file_references 
            WHERE user_id = $1 AND file_type = 'video' 
            AND is_used = false AND expires_at > NOW()
            ORDER BY created_at DESC LIMIT 1
        """, user_id)
        
        # Get latest thumbnail file
        thumbnail_ref = await self.db.fetchrow("""
            SELECT * FROM video_file_references 
            WHERE user_id = $1 AND file_type = 'thumbnail'
            AND is_used = false AND expires_at > NOW()
            ORDER BY created_at DESC LIMIT 1
        """, user_id)
        
        return {
            "video": {
                "reference_id": video_ref['id'],
                "file_name": video_ref['file_name'],
                "file_size": video_ref['file_size']
            } if video_ref else None,
            "thumbnail": {
                "reference_id": thumbnail_ref['id'],
                "file_name": thumbnail_ref['file_name'], 
                "file_size": thumbnail_ref['file_size']
            } if thumbnail_ref else None
        }
    
    async def cleanup_expired_references(self):
        """Automatic cleanup of expired file references"""
        await self.db.execute("""
            DELETE FROM video_file_references 
            WHERE expires_at < NOW() OR 
                  (is_used = true AND created_at < NOW() - INTERVAL '1 day')
        """)
```

#### **YouTube Agent Tool (`backend/agent/tools/youtube_complete_mcp_tool.py`) - 641 lines**
```python
class YouTubeCompleteMCPTool(Tool):
    def __init__(self, user_id: str, youtube_channels: List[Dict[str, Any]] = None):
        self.user_id = user_id
        self.youtube_channels = youtube_channels or []
        self.file_service = YouTubeFileService()
        self.upload_service = YouTubeUploadService()
        self.channels_service = YouTubeChannelsService()
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_authenticate",
            "description": "Connect your YouTube channel - shows OAuth button to authorize",
            "parameters": {"type": "object", "properties": {}}
        }
    })
    async def youtube_authenticate(self) -> ToolResult:
        """Zero-questions OAuth initiation"""
        
        # Check if already connected
        existing_channels = await self.channels_service.get_channels_for_agent(
            self.user_id, self.agent_id
        )
        
        if existing_channels:
            return self.success_response({
                "message": f"Already connected to {len(existing_channels)} YouTube channel(s)",
                "channels": existing_channels,
                "status": "already_connected"
            })
        
        # Initiate OAuth flow
        oauth_result = await self.oauth_handler.initiate_oauth(self.user_id)
        
        return self.success_response({
            "message": "Click the button below to connect your YouTube channel",
            "oauth_url": oauth_result["auth_url"],
            "auth_required": True,
            "provider": "youtube"
        })
    
    @openapi_schema({
        "type": "function", 
        "function": {
            "name": "youtube_upload_video",
            "description": "Upload video to YouTube with intelligent auto-discovery",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Video title"},
                    "description": {"type": "string", "description": "Video description"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "privacy": {"type": "string", "enum": ["private", "unlisted", "public"]},
                    "channel_id": {"type": "string", "description": "Target channel ID"},
                    "auto_discover": {"type": "boolean", "default": True}
                },
                "required": ["title"]
            }
        }
    })
    async def youtube_upload_video(self, title: str, description: str = "", 
                                 tags: List[str] = None, privacy: str = "private",
                                 channel_id: str = None, auto_discover: bool = True) -> ToolResult:
        """Zero-questions video upload with auto-discovery"""
        
        # Auto-discover files if not specified
        if auto_discover and not channel_id:
            uploads = await self.file_service.get_latest_pending_uploads(self.user_id)
            if not uploads.get("video"):
                return self.fail_response("No video file found. Please attach a video file first.")
        
        # Smart channel selection
        if not channel_id:
            available_channels = await self.get_available_channels()
            if len(available_channels) == 1:
                channel_id = available_channels[0]["id"]
            elif len(available_channels) > 1:
                return self.fail_response(
                    f"Multiple channels available: {', '.join(c['name'] for c in available_channels)}. "
                    "Please specify channel_id parameter."
                )
            else:
                return self.fail_response("No YouTube channels connected. Use youtube_authenticate() first.")
        
        # Initiate upload
        upload_result = await self.upload_service.upload_video_with_progress(
            self.user_id, {
                "title": title,
                "description": description,
                "tags": tags or [],
                "privacy": privacy,
                "channel_id": channel_id,
                "auto_discover": auto_discover
            }
        )
        
        return self.success_response({
            "upload_id": upload_result["upload_id"],
            "status": upload_result["status"],
            "message": f"Video '{title}' upload started to {channel_id}",
            "progress_tracking": True
        })
```

### **Frontend Architecture - Complete Component Analysis**

#### **YouTube Tool View (`frontend/src/components/thread/tool-views/YouTubeToolView.tsx`) - 635 lines**
```typescript
export const YouTubeToolView: React.FC<YouTubeToolViewProps> = ({ 
  data, request, agentId, userId 
}) => {
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  // Real-time channel subscription
  const { 
    channels: realtimeChannels, 
    loading: realtimeLoading 
  } = useRealtimeYouTubeAccounts(userId, agentId);
  
  const handleRefreshChannels = async () => {
    setIsRefreshing(true);
    try {
      // Refresh all channel metadata from YouTube API
      const promises = channels.map(channel =>
        fetch(`/api/youtube/channels/${channel.id}/refresh`, { method: 'POST' })
      );
      await Promise.all(promises);
      
      // Invalidate React Query cache
      queryClient.invalidateQueries(['youtube', 'channels']);
      
    } finally {
      setIsRefreshing(false);
    }
  };
  
  // Render OAuth button for authentication
  if (data.auth_required) {
    return (
      <div className="youtube-auth-container">
        <Button 
          onClick={() => window.open(data.oauth_url, 'youtube-auth', 'width=600,height=700')}
          className="oauth-button"
        >
          <Youtube className="w-4 h-4 mr-2" />
          Connect YouTube Channel
        </Button>
      </div>
    );
  }
  
  // Render channel list with statistics
  return (
    <div className="youtube-channels-grid">
      {channels.map(channel => (
        <ChannelCard 
          key={channel.id}
          channel={channel}
          onToggle={(enabled) => handleToggleChannel(channel.id, enabled)}
          onRefresh={() => handleRefreshChannel(channel.id)}
        />
      ))}
    </div>
  );
};
```

#### **YouTube Upload Progress View (`frontend/src/components/thread/tool-views/YouTubeUploadProgressView.tsx`) - 458 lines**
```typescript
export const YouTubeUploadProgressView: React.FC<YouTubeUploadProgressViewProps> = ({ 
  uploadId, onComplete 
}) => {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<'uploading' | 'processing' | 'completed' | 'failed'>('uploading');
  const [bytesUploaded, setBytesUploaded] = useState(0);
  const [totalBytes, setTotalBytes] = useState(0);
  
  // Hybrid progress tracking: real-time + polling fallback
  useEffect(() => {
    let interval: NodeJS.Timeout;
    let subscription: any;
    
    // Try real-time subscription first
    const supabase = createClient();
    subscription = supabase
      .channel(`upload_progress_${uploadId}`)
      .on('postgres_changes', {
        event: 'UPDATE',
        schema: 'public',
        table: 'youtube_uploads',
        filter: `id=eq.${uploadId}`
      }, (payload) => {
        const upload = payload.new;
        setProgress(upload.upload_progress);
        setStatus(upload.upload_status);
        setBytesUploaded(upload.bytes_uploaded);
        setTotalBytes(upload.total_bytes);
        
        if (upload.upload_status === 'completed') {
          onComplete?.(upload);
        }
      })
      .subscribe();
    
    // Fallback polling if real-time fails
    interval = setInterval(async () => {
      try {
        const response = await fetch(`/api/youtube/upload-status/${uploadId}`);
        const data = await response.json();
        
        setProgress(data.upload_progress);
        setStatus(data.upload_status);
        setBytesUploaded(data.bytes_uploaded);
        setTotalBytes(data.total_bytes);
        
        if (data.upload_status === 'completed' || data.upload_status === 'failed') {
          clearInterval(interval);
          onComplete?.(data);
        }
      } catch (error) {
        console.error('Progress polling failed:', error);
      }
    }, 2000);
    
    return () => {
      clearInterval(interval);
      subscription?.unsubscribe();
    };
  }, [uploadId]);
  
  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };
  
  return (
    <div className="upload-progress-container">
      <div className="progress-header">
        <Youtube className="w-5 h-5 text-red-500" />
        <span>YouTube Upload Progress</span>
      </div>
      
      <div className="progress-bar-container">
        <Progress value={progress} className="w-full" />
        <div className="progress-details">
          <span>{Math.round(progress)}%</span>
          <span>{formatBytes(bytesUploaded)} / {formatBytes(totalBytes)}</span>
        </div>
      </div>
      
      <div className="status-indicator">
        Status: <Badge variant={status === 'completed' ? 'success' : 'secondary'}>
          {status}
        </Badge>
      </div>
    </div>
  );
};
```

#### **Real-time YouTube Accounts Hook (`frontend/src/hooks/use-realtime-youtube-accounts.ts`) - 173 lines**
```typescript
export const useRealtimeYouTubeAccounts = (userId: string, agentId: string) => {
  const [channels, setChannels] = useState<YouTubeChannel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    if (!userId || !agentId) return;
    
    const supabase = createClient();
    
    // Initial data fetch
    const fetchChannels = async () => {
      try {
        const { data, error } = await supabase
          .from('youtube_channels')
          .select(`
            *,
            agent_social_accounts!inner(enabled)
          `)
          .eq('user_id', userId)
          .eq('agent_social_accounts.agent_id', agentId)
          .eq('agent_social_accounts.platform', 'youtube')
          .eq('is_active', true)
          .order('name');
        
        if (error) throw error;
        
        setChannels(data || []);
        setLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch channels');
        setLoading(false);
      }
    };
    
    fetchChannels();
    
    // Real-time subscription for changes
    const channelSubscription = supabase
      .channel(`youtube_channels_${agentId}`)
      .on('postgres_changes', {
        event: '*',
        schema: 'public',
        table: 'youtube_channels',
        filter: `user_id=eq.${userId}`
      }, (payload) => {
        console.log('Channel change detected:', payload);
        fetchChannels(); // Refetch on any change
      })
      .on('postgres_changes', {
        event: '*',
        schema: 'public', 
        table: 'agent_social_accounts',
        filter: `user_id=eq.${userId}`
      }, (payload) => {
        console.log('Social account change detected:', payload);
        fetchChannels(); // Refetch on toggle changes
      })
      .subscribe();
    
    return () => {
      channelSubscription.unsubscribe();
    };
  }, [userId, agentId]);
  
  return { channels, loading, error };
};
```

### **Database Schema - Complete Analysis**

#### **YouTube Tables (backend/supabase/migrations/)**

**Channel Management:**
```sql
-- 20250809100000_youtube_integration.sql
CREATE TABLE youtube_channels (
    id VARCHAR PRIMARY KEY,                    -- YouTube channel ID (UC...)
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,               -- Channel display name
    username VARCHAR(255),                    -- @handle
    custom_url VARCHAR(255),                  -- Custom channel URL
    profile_picture VARCHAR(500),             -- Default thumbnail
    profile_picture_medium VARCHAR(500),      -- Medium thumbnail
    profile_picture_small VARCHAR(500),       -- Small thumbnail
    subscriber_count BIGINT DEFAULT 0,        -- Subscriber statistics
    view_count BIGINT DEFAULT 0,              -- Total view count
    video_count BIGINT DEFAULT 0,             -- Total video count
    access_token TEXT,                        -- Encrypted OAuth token
    refresh_token TEXT,                       -- Encrypted refresh token
    token_expires_at TIMESTAMPTZ,             -- Token expiration
    token_scopes TEXT[],                      -- OAuth scopes granted
    is_active BOOLEAN DEFAULT true,           -- Soft delete flag
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_youtube_channels_user_id ON youtube_channels(user_id);
CREATE INDEX idx_youtube_channels_active ON youtube_channels(user_id, is_active);
```

**File Reference System:**
```sql
-- 20250824_video_file_references.sql  
CREATE TABLE video_file_references (
    id VARCHAR(32) PRIMARY KEY,              -- 32-char hex reference ID
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,         -- Original filename
    file_path VARCHAR(500),                  -- Temporary storage path
    file_data TEXT,                          -- Base64 encoded file content
    file_size BIGINT NOT NULL,               -- File size in bytes
    mime_type VARCHAR(100),                  -- MIME type
    file_type VARCHAR(20),                   -- 'video' or 'thumbnail'
    metadata JSONB,                          -- Additional file metadata
    transcription JSONB,                     -- AI transcription results
    generated_metadata JSONB,                -- AI-generated titles/descriptions
    is_used BOOLEAN DEFAULT false,           -- Prevents reuse
    expires_at TIMESTAMPTZ NOT NULL,         -- TTL for cleanup
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_video_file_references_user_id ON video_file_references(user_id);
CREATE INDEX idx_video_file_references_expires ON video_file_references(expires_at);
CREATE INDEX idx_video_file_references_type ON video_file_references(user_id, file_type, is_used);
```

**Upload Tracking:**
```sql
-- 20250825_add_youtube_upload_progress_tracking.sql
CREATE TABLE youtube_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    channel_id VARCHAR REFERENCES youtube_channels(id),
    video_id VARCHAR,                        -- YouTube video ID when complete
    title VARCHAR(255) NOT NULL,
    description TEXT,
    tags TEXT[],                            -- Video tags array
    privacy_status VARCHAR(20) DEFAULT 'private', -- private, unlisted, public
    upload_status VARCHAR(20) DEFAULT 'pending',  -- pending, uploading, processing, completed, failed
    upload_progress FLOAT DEFAULT 0.0,      -- Progress percentage (0-100)
    bytes_uploaded BIGINT DEFAULT 0,        -- Bytes uploaded so far
    total_bytes BIGINT DEFAULT 0,           -- Total file size
    video_reference_id VARCHAR(32),         -- Links to video_file_references
    thumbnail_reference_id VARCHAR(32),     -- Links to thumbnail file
    error_message TEXT,                      -- Error details if failed
    video_url VARCHAR(500),                  -- Final YouTube URL
    thumbnail_url VARCHAR(500),              -- YouTube thumbnail URL
    duration_seconds INTEGER,                -- Video duration
    view_count BIGINT DEFAULT 0,             -- View statistics
    like_count BIGINT DEFAULT 0,             -- Like statistics
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ                 -- Upload completion time
);

CREATE INDEX idx_youtube_uploads_user_id ON youtube_uploads(user_id);
CREATE INDEX idx_youtube_uploads_status ON youtube_uploads(upload_status);
CREATE INDEX idx_youtube_uploads_progress ON youtube_uploads(user_id, upload_status, created_at);
```

**MCP Toggle Integration:**
```sql
-- 20250827_unified_social_accounts.sql
CREATE TABLE agent_social_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL,                  -- Can be virtual 'suna-default'
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,          -- 'youtube', 'twitter', etc.
    account_id VARCHAR(255) NOT NULL,       -- Platform account ID
    account_name VARCHAR(255),              -- Display name
    enabled BOOLEAN DEFAULT true,           -- Per-agent toggle
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (agent_id, user_id, platform, account_id),
    FOREIGN KEY (user_id, platform, account_id) REFERENCES youtube_channels(user_id, 'youtube', id)
);

CREATE INDEX idx_agent_social_accounts_lookup ON agent_social_accounts(agent_id, user_id, platform);
```

### **YouTube Configuration Requirements**

#### **Environment Variables**
```bash
# OAuth Configuration
YOUTUBE_CLIENT_ID=your_google_oauth_client_id
YOUTUBE_CLIENT_SECRET=your_google_oauth_client_secret  
YOUTUBE_REDIRECT_URI=http://localhost:8000/api/youtube/auth/callback

# Token Encryption
MCP_CREDENTIAL_ENCRYPTION_KEY=your_32_byte_fernet_key

# YouTube API Configuration  
YOUTUBE_API_KEY=your_youtube_data_api_key
YOUTUBE_UPLOAD_CHUNK_SIZE=1048576  # 1MB chunks
YOUTUBE_MAX_RETRIES=3

# File Storage Configuration
YOUTUBE_FILE_EXPIRY_MINUTES=30     # Quick upload expiry
YOUTUBE_PREPARED_EXPIRY_HOURS=24   # Prepared upload expiry
YOUTUBE_MAX_VIDEO_SIZE=137438953472 # 128GB YouTube limit
YOUTUBE_MAX_THUMBNAIL_SIZE=2097152  # 2MB thumbnail limit
```

#### **Google OAuth Setup Requirements**
```json
{
  "web": {
    "client_id": "your_client_id",
    "client_secret": "your_client_secret", 
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "redirect_uris": [
      "http://localhost:8000/api/youtube/auth/callback",
      "https://your-domain.com/api/youtube/auth/callback"
    ],
    "javascript_origins": [
      "http://localhost:3000",
      "https://your-domain.com"
    ]
  }
}
```

### **Complete YouTube API Tools Reference**

#### **Authentication Tools**
```python
youtube_authenticate() -> ToolResult:
    """Initiate OAuth flow - returns auth button"""
    # Behavior: Skips if channels connected, shows OAuth URL
    # Response: oauth_url, auth_required=True
```

#### **Channel Management Tools**  
```python
youtube_channels(include_analytics: bool = False) -> ToolResult:
    """List connected channels with statistics"""
    # Real-time database queries, no cache dependencies
    # Returns: channel list with names, subscribers, profile pics
    
youtube_refresh_channel(channel_id: str) -> ToolResult:
    """Refresh channel metadata from YouTube API"""
    # Updates subscriber count, profile pictures, statistics
```

#### **Upload Tools**
```python
youtube_upload_video(
    title: str,
    description: str = "",
    tags: List[str] = None,
    privacy: str = "private", 
    channel_id: str = None,
    auto_discover: bool = True
) -> ToolResult:
    """Upload video with zero-questions auto-discovery"""
    # Auto-finds latest video file if not specified
    # Smart channel selection for single-channel users
    # Returns upload_id for progress tracking

youtube_prepare_upload(file_content: bytes, file_name: str) -> ToolResult:
    """Upload file to reference system for later use"""
    # Creates 32-char reference ID
    # Automatic file type detection
    # TTL-based cleanup
```

#### **Content Management Tools**
```python
youtube_list_channel_videos(
    channel_id: str,
    max_results: int = 25,
    order: str = "date"
) -> ToolResult:
    """Browse channel videos with metadata"""
    
youtube_manage_video(
    video_id: str,
    action: str,  # 'update', 'delete'
    **kwargs
) -> ToolResult:
    """Update or delete YouTube video"""
    
youtube_list_captions(video_id: str) -> ToolResult:
    """List video captions/subtitles"""
    
youtube_download_caption(
    video_id: str,
    caption_id: str,
    format: str = "srt"
) -> ToolResult:
    """Download caption file"""
    
youtube_list_playlists(channel_id: str = None) -> ToolResult:
    """List user playlists"""
    
youtube_smart_search(
    query: str,
    search_type: str = "video",  # video, channel, playlist
    max_results: int = 10
) -> ToolResult:
    """Search YouTube content"""
```

### **YouTube Error Handling Patterns**

#### **Authentication Error Recovery**
```python
class YouTubeAuthError(Exception):
    def __init__(self, channel_id: str, error_type: str):
        self.channel_id = channel_id
        self.error_type = error_type  # token_expired, invalid_grant, etc.
        
async def handle_auth_error(self, error: YouTubeAuthError) -> ToolResult:
    if error.error_type == "token_expired":
        # Attempt automatic refresh
        try:
            await self.oauth_handler.refresh_token(user_id, error.channel_id)
            return self.success_response({"message": "Token refreshed, please retry"})
        except:
            # Refresh failed - require re-authentication
            oauth_url = await self.oauth_handler.initiate_oauth(user_id)
            return self.fail_response(
                "YouTube authentication expired. Please re-connect your channel.",
                auth_required=True,
                oauth_url=oauth_url["auth_url"]
            )
```

#### **Upload Error Recovery** 
```python
async def handle_upload_error(self, upload_id: str, error: Exception):
    if "quotaExceeded" in str(error):
        await self.update_upload_status(upload_id, "failed", 
            "Daily YouTube upload quota exceeded. Try again tomorrow.")
    elif "fileTooBig" in str(error):
        await self.update_upload_status(upload_id, "failed",
            "File exceeds YouTube's 128GB limit.")
    elif "invalidVideoFormat" in str(error):
        await self.update_upload_status(upload_id, "failed",
            "Invalid video format. Please use MP4, AVI, MOV, or WebM.")
    else:
        # Generic error with retry suggestion
        await self.update_upload_status(upload_id, "failed",
            f"Upload failed: {str(error)}. Please try again.")
```

### **Performance Optimizations**

#### **Token Caching Strategy**
```python
# 5-minute buffer for token refresh
async def get_valid_token(self, user_id: str, channel_id: str) -> str:
    channel = await self.get_channel(user_id, channel_id)
    
    # Check if token expires within 5 minutes
    if channel['token_expires_at'] <= datetime.utcnow() + timedelta(minutes=5):
        await self.refresh_token(user_id, channel_id)
        
    return self.decrypt_token(channel['access_token'])
```

#### **Channel Data Pre-computation**
```python
# Agent config includes pre-computed channel data
async def get_agent_config(agent_id: str, user_id: str) -> Dict[str, Any]:
    config = await self.load_base_config(agent_id)
    
    # Pre-compute YouTube channels for performance
    channels = await self.channels_service.get_channels_for_agent(user_id, agent_id)
    config['youtube_channels'] = [
        {
            "id": channel["id"],
            "name": channel["name"],
            "username": channel["username"],
            "subscriber_count": channel["subscriber_count"],
            "profile_picture": channel["profile_picture"]
        } for channel in channels
    ]
    
    return config
```

#### **Chunked Upload Strategy**
```python
# 1MB chunks for progress tracking and resumability
CHUNK_SIZE = 1024 * 1024  # 1MB

async def upload_video_chunked(self, video_data: bytes, metadata: Dict) -> Dict:
    total_size = len(video_data)
    uploaded = 0
    
    # Initialize resumable upload
    upload_url = await self.initialize_resumable_upload(metadata)
    
    while uploaded < total_size:
        chunk = video_data[uploaded:uploaded + CHUNK_SIZE]
        chunk_size = len(chunk)
        
        # Upload chunk with progress update
        response = await self.upload_chunk(
            upload_url, chunk, uploaded, uploaded + chunk_size - 1, total_size
        )
        
        uploaded += chunk_size
        
        # Update progress in database
        await self.update_upload_progress(upload_id, uploaded, total_size)
        
        # Yield control for other operations
        await asyncio.sleep(0.01)
    
    return await self.finalize_upload(upload_url)
```

### **YouTube Development Guidelines**

#### **Zero-Questions Protocol Rules**
1. **Never ask file location** - Use auto_discover=True by default
2. **Never ask channel preference** - Auto-select single channel, list multiple
3. **Never ask metadata confirmation** - Use provided or generate intelligently
4. **Never ask upload timing** - Execute immediately when requested
5. **Never ask privacy settings** - Default to private, allow override

#### **File Management Best Practices**
1. **Always use reference IDs** - Never direct file paths for YouTube content
2. **Validate file types** - Check video/thumbnail before processing
3. **Handle large files** - Use chunked upload for videos >10MB
4. **Implement cleanup** - Mark references as used, respect TTL
5. **Optimize thumbnails** - Resize to 1280x720, maintain aspect ratio

#### **Error Recovery Patterns**
1. **Token Refresh**: Automatic with 3-attempt retry
2. **Network Failures**: Progressive backoff (1s, 5s, 15s)  
3. **Quota Limits**: Clear messaging with retry timing
4. **File Errors**: Specific guidance for resolution
5. **OAuth Errors**: Seamless re-authentication flow

### **Integration Testing Patterns**

#### **OAuth Flow Testing**
```python
async def test_youtube_oauth_flow():
    # 1. Initiate OAuth
    oauth_result = await youtube_tool.youtube_authenticate()
    assert oauth_result.success
    assert "oauth_url" in oauth_result.data
    
    # 2. Simulate callback (requires manual step)
    # User completes OAuth in browser
    
    # 3. Verify channel storage
    channels = await youtube_tool.youtube_channels()
    assert len(channels.data["channels"]) > 0
    
    # 4. Test token validity
    first_channel = channels.data["channels"][0]
    token = await oauth_handler.get_valid_token(user_id, first_channel["id"])
    assert token is not None
```

#### **Upload Flow Testing**
```python
async def test_youtube_upload_flow():
    # 1. Prepare test video file
    video_data = create_test_video()  # Generate test MP4
    ref_id = await file_service.create_video_reference(user_id, video_data, "test.mp4")
    
    # 2. Test upload
    result = await youtube_tool.youtube_upload_video(
        title="Test Upload",
        description="Test video upload",
        auto_discover=True
    )
    assert result.success
    upload_id = result.data["upload_id"]
    
    # 3. Monitor progress
    while True:
        status = await get_upload_status(upload_id)
        if status["upload_status"] in ["completed", "failed"]:
            break
        await asyncio.sleep(1)
    
    assert status["upload_status"] == "completed"
    assert status["video_id"] is not None
```

This complete YouTube system specification provides everything needed to understand, maintain, and extend the sophisticated YouTube integration within the Kortix platform.

## COMPLETE TOOL SYSTEM TECHNICAL SPECIFICATION

### **Tool Architecture Overview**

The Kortix platform implements a sophisticated tool system with multiple integration patterns:

#### **Tool Base Classes & Inheritance**
```python
# Base tool hierarchy (backend/agentpress/tool.py)
class Tool:
    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__
        self.schema = None
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass
    
    def success_response(self, result: Any = None, **kwargs) -> ToolResult:
        return ToolResult(success=True, result=result, **kwargs)
    
    def fail_response(self, message: str, **kwargs) -> ToolResult:
        return ToolResult(success=False, error=message, **kwargs)

# Specialized base classes
class AgentBuilderBaseTool(Tool):
    """Base for agent configuration tools"""
    
class SandboxTool(Tool):
    """Base for sandbox environment tools"""
    
class MCPToolWrapper(Tool):
    """Wrapper for external MCP integrations"""
```

#### **Tool Registration System**
```python
# ToolManager registration flow (backend/agent/run.py)
class ToolManager:
    async def _register_all_tools(self):
        # 1. Core tools (always enabled)
        self.register_tool(MessageTool())           # Agent communication
        self.register_tool(TaskListTool())          # Workflow management
        self.register_tool(ExpandMessageTool())     # Context expansion
        
        # 2. Sandbox tools (configurable via agentpress_tools)
        if self.config.get('sb_shell_tool'):
            self.register_tool(ShellTool())         # Terminal execution
        if self.config.get('sb_files_tool'):
            self.register_tool(FilesTool())         # File management
        if self.config.get('browser_tool'):
            self.register_tool(BrowserTool())       # Web automation
        if self.config.get('sb_vision_tool'):
            self.register_tool(VisionTool())        # Image processing
        if self.config.get('sb_deploy_tool'):
            self.register_tool(DeployTool())        # App deployment
        if self.config.get('sb_expose_tool'):
            self.register_tool(ExposeTool())        # Port exposure
        
        # 3. Utility tools
        if self.config.get('web_search_tool'):
            self.register_tool(WebSearchTool())     # Internet search
        if self.config.get('data_providers_tool'):
            self.register_tool(DataProvidersTool()) # API integrations
        if self.config.get('youtube_tool'):
            youtube_tool = YouTubeCompleteMCPTool(
                self.user_id, 
                self.agent_config.get('youtube_channels', [])
            )
            self.register_tool(youtube_tool)        # Native YouTube
        
        # 4. Agent builder tools (if agent_id provided)
        if self.agent_config.get('agent_id'):
            self.register_tool(AgentConfigTool())   # Agent configuration
            self.register_tool(WorkflowTool())      # Workflow management
            self.register_tool(TriggerTool())       # Trigger management
            self.register_tool(CredentialProfileTool()) # MCP credentials
            self.register_tool(MCPSearchTool())     # MCP discovery
        
        # 5. MCP tools (external integrations via wrapper)
        await self._register_mcp_tools()
```

### **AgentPress Core Tools**

#### **Message Tool (`backend/agent/tools/message_tool.py`)**
```python
class MessageTool(Tool):
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "message",
            "description": "Send message to user with optional image, audio or video",
            "parameters": {
                "type": "object", 
                "properties": {
                    "content": {"type": "string", "description": "Message content"},
                    "image_path": {"type": "string", "description": "Optional image path"},
                    "audio_path": {"type": "string", "description": "Optional audio path"},
                    "video_path": {"type": "string", "description": "Optional video path"}
                },
                "required": ["content"]
            }
        }
    })
    async def message(self, content: str, image_path: str = None, 
                     audio_path: str = None, video_path: str = None) -> ToolResult:
        # Stream message to user with optional media attachments
        return self.success_response({
            "content": content,
            "attachments": {
                "image": image_path,
                "audio": audio_path, 
                "video": video_path
            }
        })
```

#### **Task List Tool (`backend/agent/tools/task_list_tool.py`)**
```python
class TaskListTool(Tool):
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "task_list",
            "description": "Manage task list for workflow tracking",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["create", "update", "complete", "list"]},
                    "tasks": {"type": "array", "items": {"type": "string"}},
                    "task_id": {"type": "string"}
                },
                "required": ["action"]
            }
        }
    })
    async def task_list(self, action: str, tasks: List[str] = None, 
                       task_id: str = None) -> ToolResult:
        # Workflow management with task tracking
        if action == "create":
            task_list = [{"id": str(uuid.uuid4()), "content": task, "status": "pending"} 
                        for task in tasks]
            return self.success_response({"tasks": task_list})
        elif action == "update":
            # Update existing task status
            return self.success_response({"updated": task_id})
        elif action == "complete":
            # Mark task as completed
            return self.success_response({"completed": task_id})
        else:
            # List all tasks
            return self.success_response({"tasks": []})
```

#### **Shell Tool (`backend/agent/tools/shell_tool.py`)**
```python
class ShellTool(SandboxTool):
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "shell",
            "description": "Execute shell commands in sandbox environment",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "timeout": {"type": "integer", "default": 30}
                },
                "required": ["command"]
            }
        }
    })
    async def shell(self, command: str, timeout: int = 30) -> ToolResult:
        # Secure sandbox execution with timeout
        try:
            result = await self.sandbox_client.execute_command(
                command, timeout=timeout, user_id=self.user_id
            )
            return self.success_response({
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
                "execution_time": result.execution_time
            })
        except TimeoutError:
            return self.fail_response(f"Command timed out after {timeout} seconds")
        except Exception as e:
            return self.fail_response(f"Command execution failed: {str(e)}")
```

#### **Browser Tool (`backend/agent/tools/browser_tool.py`)**
```python
class BrowserTool(SandboxTool):
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "browser",
            "description": "Automate web browser interactions and scraping",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["navigate", "click", "type", "screenshot", "extract"]},
                    "url": {"type": "string", "description": "Target URL"},
                    "selector": {"type": "string", "description": "CSS selector for element"},
                    "text": {"type": "string", "description": "Text to type"},
                    "wait_for": {"type": "string", "description": "Element to wait for"}
                },
                "required": ["action"]
            }
        }
    })
    async def browser(self, action: str, url: str = None, selector: str = None,
                     text: str = None, wait_for: str = None) -> ToolResult:
        # Browser automation with screenshot capability
        browser_session = await self.get_browser_session()
        
        if action == "navigate":
            await browser_session.navigate(url)
            screenshot = await browser_session.screenshot()
            return self.success_response({
                "url": url,
                "screenshot": screenshot,
                "title": await browser_session.get_title()
            })
        elif action == "click":
            await browser_session.click(selector)
            return self.success_response({"clicked": selector})
        elif action == "type":
            await browser_session.type(selector, text)
            return self.success_response({"typed": text, "into": selector})
        elif action == "screenshot":
            screenshot = await browser_session.screenshot()
            return self.success_response({"screenshot": screenshot})
        elif action == "extract":
            content = await browser_session.extract_content(selector)
            return self.success_response({"content": content, "selector": selector})
```

### **MCP Integration System**

#### **MCP Tool Wrapper (`backend/agent/tools/mcp_tool_wrapper.py`)**
```python
class MCPToolWrapper(Tool):
    def __init__(self, mcp_configs: List[Dict[str, Any]]):
        self.connection_manager = MCPConnectionManager()
        self.custom_handler = CustomMCPHandler(self.connection_manager)
        self.tool_builder = DynamicToolBuilder()
        self.tool_executor = MCPToolExecutor()
        self.schema_cache = {}
    
    async def register_mcp_tools(self, mcp_configs: List[Dict]):
        """Register all MCP tools dynamically"""
        for config in mcp_configs:
            cache_key = f"mcp_schema:{hashlib.md5(str(config).encode()).hexdigest()}"
            
            # Try Redis cache first
            cached_schema = await redis_client.get(cache_key)
            if cached_schema:
                schema = json.loads(cached_schema)
            else:
                # Fetch fresh schema and cache
                schema = await self.fetch_mcp_schema(config)
                await redis_client.setex(cache_key, 3600, json.dumps(schema))  # 1-hour cache
            
            # Build dynamic tools from schema
            for tool_schema in schema.get('tools', []):
                dynamic_method = self.tool_builder.create_tool_method(tool_schema, config)
                setattr(self, tool_schema['name'], dynamic_method)
    
    async def execute_mcp_tool(self, tool_name: str, parameters: dict, config: dict) -> ToolResult:
        """Execute MCP tool with transport-specific handling"""
        try:
            if config['type'] == 'composio':
                # Composio toolkit integration
                result = await self.custom_handler.execute_composio_tool(
                    tool_name, parameters, config
                )
            elif config['type'] == 'sse':
                # Server-Sent Events transport
                result = await self.connection_manager.execute_sse_tool(
                    tool_name, parameters, config
                )
            elif config['type'] == 'http':
                # HTTP transport
                result = await self.connection_manager.execute_http_tool(
                    tool_name, parameters, config
                )
            else:
                # Standard MCP protocol
                result = await self.connection_manager.execute_standard_tool(
                    tool_name, parameters, config
                )
            
            return self.success_response(result)
            
        except Exception as e:
            return self.fail_response(f"MCP tool execution failed: {str(e)}")
```

#### **MCP Connection Manager (`backend/agent/tools/mcp_connection_manager.py`)**
```python
class MCPConnectionManager:
    def __init__(self):
        self.connections = {}
        self.connection_pool = {}
        
    async def get_or_create_connection(self, config: Dict[str, Any]) -> Any:
        """Maintain persistent connections for performance"""
        connection_key = self._generate_connection_key(config)
        
        if connection_key not in self.connections:
            if config['type'] == 'sse':
                connection = await self._create_sse_connection(config)
            elif config['type'] == 'http':
                connection = await self._create_http_connection(config)
            elif config['type'] == 'stdio':
                connection = await self._create_stdio_connection(config)
            else:
                connection = await self._create_standard_connection(config)
            
            self.connections[connection_key] = connection
        
        return self.connections[connection_key]
    
    async def execute_tool_with_retry(self, connection: Any, tool_name: str, 
                                    parameters: dict, max_retries: int = 3) -> Any:
        """Execute with automatic retry and connection recovery"""
        for attempt in range(max_retries):
            try:
                return await connection.call_tool(tool_name, parameters)
            except ConnectionError as e:
                if attempt < max_retries - 1:
                    # Reconnect and retry
                    await self._reconnect(connection)
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise e
```

### **Agent Builder Tool System**

#### **Agent Config Tool (`backend/agent/tools/agent_builder_tools/agent_config_tool.py`)**
```python
class AgentConfigTool(AgentBuilderBaseTool):
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "update_agent",
            "description": "Update agent configuration with new settings",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "system_prompt": {"type": "string"},
                    "model": {"type": "string"},
                    "agentpress_tools": {"type": "object"},
                    "configured_mcps": {"type": "array"},
                    "custom_mcps": {"type": "array"},
                    "avatar": {"type": "string"},
                    "avatar_color": {"type": "string"}
                }
            }
        }
    })
    async def update_agent(self, **config_updates) -> ToolResult:
        """Update agent configuration with version control"""
        
        # Validate Suna restrictions
        if self.is_suna_default_agent():
            restricted_fields = ['name', 'agentpress_tools']
            for field in restricted_fields:
                if field in config_updates:
                    return self.fail_response(f"Cannot modify {field} for Suna default agent")
        
        # Create new version
        try:
            new_version = await self.version_service.create_version(
                self.target_agent_id,
                config_updates,
                created_by=self.user_id,
                change_description=self._generate_change_description(config_updates)
            )
            
            # Activate new version
            await self.version_service.activate_version(
                self.target_agent_id, 
                new_version.version_id
            )
            
            return self.success_response({
                "message": "Agent configuration updated successfully",
                "version_id": new_version.version_id,
                "version_number": new_version.version_number,
                "changes": config_updates
            })
            
        except Exception as e:
            return self.fail_response(f"Failed to update agent: {str(e)}")
```

#### **MCP Search Tool (`backend/agent/tools/agent_builder_tools/mcp_search_tool.py`)**
```python
class MCPSearchTool(AgentBuilderBaseTool):
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "search_mcp_servers",
            "description": "Search available MCP servers and integrations",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "category": {"type": "string", "description": "Category filter"},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": ["query"]
            }
        }
    })
    async def search_mcp_servers(self, query: str, category: str = None, limit: int = 10) -> ToolResult:
        """Search 2700+ available MCP integrations"""
        try:
            # Search local MCP registry
            servers = await self.mcp_registry.search(
                query=query,
                category=category,
                limit=limit,
                sort_by="popularity"
            )
            
            # Format results with connection instructions
            formatted_servers = []
            for server in servers:
                formatted_servers.append({
                    "name": server["name"],
                    "qualified_name": server["qualified_name"],
                    "description": server["description"],
                    "category": server["category"],
                    "popularity_score": server["popularity_score"],
                    "connection_type": server["connection_type"],
                    "setup_required": server.get("requires_auth", False),
                    "available_tools": server.get("tool_count", 0)
                })
            
            return self.success_response({
                "servers": formatted_servers,
                "total_found": len(formatted_servers),
                "message": f"Found {len(formatted_servers)} MCP servers matching '{query}'"
            })
            
        except Exception as e:
            return self.fail_response(f"MCP search failed: {str(e)}")
```

### **Data Provider Tools**

#### **Data Providers Tool (`backend/agent/tools/data_providers_tool.py`)**
```python
class DataProvidersTool(Tool):
    """Unified access to multiple data APIs"""
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "search_zillow",
            "description": "Search real estate listings on Zillow",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City, state or ZIP code"},
                    "property_type": {"type": "string", "enum": ["house", "condo", "townhouse", "apartment"]},
                    "min_price": {"type": "integer"},
                    "max_price": {"type": "integer"},
                    "bedrooms": {"type": "integer"},
                    "bathrooms": {"type": "integer"}
                },
                "required": ["location"]
            }
        }
    })
    async def search_zillow(self, location: str, **filters) -> ToolResult:
        """Search Zillow real estate listings"""
        try:
            # Use RapidAPI Zillow integration
            results = await self.zillow_client.search_properties(
                location=location,
                filters=filters
            )
            
            formatted_results = []
            for property in results.get('props', []):
                formatted_results.append({
                    "address": property.get('address', ''),
                    "price": property.get('price', 0),
                    "bedrooms": property.get('bedrooms', 0),
                    "bathrooms": property.get('bathrooms', 0),
                    "square_feet": property.get('livingArea', 0),
                    "property_type": property.get('propertyType', ''),
                    "listing_url": property.get('detailUrl', ''),
                    "image_url": property.get('imgSrc', '')
                })
            
            return self.success_response({
                "listings": formatted_results,
                "total_found": len(formatted_results),
                "location": location
            })
            
        except Exception as e:
            return self.fail_response(f"Zillow search failed: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "get_stock_data",
            "description": "Get stock market data and financial information",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock ticker symbol"},
                    "period": {"type": "string", "enum": ["1d", "1w", "1m", "3m", "1y"], "default": "1d"}
                },
                "required": ["symbol"]
            }
        }
    })
    async def get_stock_data(self, symbol: str, period: str = "1d") -> ToolResult:
        """Get stock market data via Yahoo Finance"""
        try:
            stock_data = await self.yahoo_finance_client.get_stock_info(
                symbol=symbol.upper(),
                period=period
            )
            
            return self.success_response({
                "symbol": symbol.upper(),
                "current_price": stock_data.get('regularMarketPrice', 0),
                "previous_close": stock_data.get('previousClose', 0),
                "day_change": stock_data.get('regularMarketChange', 0),
                "day_change_percent": stock_data.get('regularMarketChangePercent', 0),
                "volume": stock_data.get('regularMarketVolume', 0),
                "market_cap": stock_data.get('marketCap', 0),
                "pe_ratio": stock_data.get('trailingPE', 0),
                "52_week_high": stock_data.get('fiftyTwoWeekHigh', 0),
                "52_week_low": stock_data.get('fiftyTwoWeekLow', 0)
            })
            
        except Exception as e:
            return self.fail_response(f"Stock data retrieval failed: {str(e)}")
```

## COMPLETE MCP INTEGRATION SPECIFICATION

### **MCP System Architecture**

#### **Credential Profile System (`backend/agent/tools/agent_builder_tools/credential_profile_tool.py`)**
```python
class CredentialProfileTool(AgentBuilderBaseTool):
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "create_credential_profile",
            "description": "Create encrypted credential profile for MCP integration",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_slug": {"type": "string", "description": "MCP app identifier"},
                    "profile_name": {"type": "string", "description": "Profile display name"},
                    "config": {"type": "object", "description": "Configuration parameters"}
                },
                "required": ["app_slug", "profile_name"]
            }
        }
    })
    async def create_credential_profile(self, app_slug: str, profile_name: str, 
                                      config: Dict[str, Any] = None) -> ToolResult:
        """Create encrypted credential profile for external service"""
        try:
            # Generate OAuth URL for user authentication
            oauth_url = await self.composio_client.get_oauth_url(
                app_slug=app_slug,
                user_id=self.user_id
            )
            
            # Create profile record
            profile_id = str(uuid.uuid4())
            encrypted_config = self.encryption_service.encrypt(json.dumps(config or {}))
            
            await self.db.execute("""
                INSERT INTO credential_profiles 
                (id, user_id, app_slug, profile_name, config, status, created_at)
                VALUES ($1, $2, $3, $4, $5, 'pending', NOW())
            """, profile_id, self.user_id, app_slug, profile_name, encrypted_config)
            
            return self.success_response({
                "profile_id": profile_id,
                "connection_link": oauth_url,
                "message": f"Credential profile '{profile_name}' created. Complete authentication via the provided link.",
                "status": "pending_auth"
            })
            
        except Exception as e:
            return self.fail_response(f"Failed to create credential profile: {str(e)}")
```

#### **MCP Toggle Service (`backend/services/mcp_toggles.py`)**
```python
class MCPToggleService:
    async def set_toggle(self, agent_id: str, user_id: str, mcp_id: str, enabled: bool) -> bool:
        """Set MCP toggle state for specific agent/user/service"""
        
        # Handle virtual suna-default agent
        if agent_id == 'suna-default':
            # Store with special virtual agent handling
            await self.db.execute("""
                INSERT INTO mcp_toggles (agent_id, user_id, mcp_id, is_enabled, created_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (agent_id, user_id, mcp_id) 
                DO UPDATE SET is_enabled = $4, updated_at = NOW()
            """, 'suna-default', user_id, mcp_id, enabled)
        else:
            # Standard agent toggle
            await self.db.execute("""
                INSERT INTO mcp_toggles (agent_id, user_id, mcp_id, is_enabled, created_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (agent_id, user_id, mcp_id)
                DO UPDATE SET is_enabled = $4, updated_at = NOW()
            """, agent_id, user_id, mcp_id, enabled)
        
        # Invalidate cache for immediate effect
        cache_key = f"mcp_toggles:{agent_id}:{user_id}"
        await redis_client.delete(cache_key)
        
        return True
    
    async def get_enabled_mcps(self, agent_id: str, user_id: str) -> List[str]:
        """Get list of enabled MCP IDs for agent/user combination"""
        
        # Check cache first
        cache_key = f"mcp_toggles:{agent_id}:{user_id}"
        cached_toggles = await redis_client.get(cache_key)
        
        if cached_toggles:
            return json.loads(cached_toggles)
        
        # Query database
        toggles = await self.db.fetch("""
            SELECT mcp_id FROM mcp_toggles 
            WHERE agent_id = $1 AND user_id = $2 AND is_enabled = true
        """, agent_id, user_id)
        
        enabled_mcps = [toggle['mcp_id'] for toggle in toggles]
        
        # Cache for 5 minutes
        await redis_client.setex(cache_key, 300, json.dumps(enabled_mcps))
        
        return enabled_mcps
```

### **Composio Integration System**

#### **Composio Handler (`backend/agent/tools/composio_handler.py`)**
```python
class ComposioHandler:
    async def execute_composio_tool(self, tool_name: str, parameters: dict, config: dict) -> Any:
        """Execute Composio toolkit action"""
        
        # Get profile credentials
        profile_id = config.get('profile_id')
        if not profile_id:
            raise ValueError("Composio tools require credential profile")
        
        credentials = await self.get_profile_credentials(profile_id)
        
        # Execute via Composio API
        response = await self.composio_client.execute_action(
            toolkit_slug=config['toolkit_slug'],
            action_name=tool_name,
            parameters=parameters,
            credentials=credentials
        )
        
        return response
    
    async def get_composio_toolkits(self, category: str = None) -> List[Dict[str, Any]]:
        """Get available Composio toolkits"""
        toolkits = await self.composio_client.get_toolkits(category=category)
        
        return [
            {
                "name": toolkit["name"],
                "slug": toolkit["slug"],
                "description": toolkit["description"],
                "category": toolkit["category"],
                "logo": toolkit["logo"],
                "auth_required": toolkit["auth_required"],
                "available_actions": len(toolkit["actions"])
            }
            for toolkit in toolkits
        ]
```

## AGENTPRESS FRAMEWORK DEEP DIVE

### **Thread Manager (`backend/agentpress/thread_manager.py`)**
```python
class ThreadManager:
    def __init__(self, thread_id: str, user_id: str, model_config: Dict[str, Any]):
        self.thread_id = thread_id
        self.user_id = user_id
        self.model_config = model_config
        self.conversation_history = []
        self.tool_registry = ToolRegistry()
        
    async def process_user_message(self, content: str, attachments: List[Dict] = None) -> AsyncGenerator[str, None]:
        """Process user message with streaming response"""
        
        # Add user message to conversation
        user_message = {
            "role": "user",
            "content": content,
            "attachments": attachments or [],
            "timestamp": datetime.utcnow().isoformat()
        }
        self.conversation_history.append(user_message)
        
        # Build system prompt with tool schemas
        system_prompt = await self.build_system_prompt()
        
        # Stream LLM response with tool execution
        async for chunk in self.stream_llm_response(system_prompt):
            yield chunk
            
            # Parse and execute any tool calls
            if self.has_tool_calls(chunk):
                tool_results = await self.execute_tool_calls(chunk)
                
                # Add tool results to conversation
                self.conversation_history.append({
                    "role": "assistant",
                    "content": chunk,
                    "tool_calls": tool_results,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                # Continue conversation with tool results
                async for follow_up in self.continue_with_tool_results(tool_results):
                    yield follow_up
    
    async def build_system_prompt(self) -> str:
        """Build comprehensive system prompt with context"""
        prompt_parts = []
        
        # Base agent prompt
        if self.agent_config.get('system_prompt'):
            prompt_parts.append(self.agent_config['system_prompt'])
        else:
            # Default Suna prompt
            from agent.prompt import get_default_prompt
            prompt_parts.append(get_default_prompt())
        
        # Tool schemas
        tool_schemas = await self.tool_registry.get_all_schemas()
        prompt_parts.append(f"Available tools: {json.dumps(tool_schemas, indent=2)}")
        
        # YouTube channels (if any)
        if self.agent_config.get('youtube_channels'):
            channels_info = "Connected YouTube channels:\n"
            for channel in self.agent_config['youtube_channels']:
                channels_info += f"- {channel['name']} (@{channel['username']}) - {channel['subscriber_count']} subscribers\n"
            prompt_parts.append(channels_info)
        
        # Current date/time
        prompt_parts.append(f"Current date and time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        return "\n\n".join(prompt_parts)
```

### **Tool Registry (`backend/agentpress/tool_registry.py`)**
```python
class ToolRegistry:
    def __init__(self):
        self.tools = {}
        self.schemas = {}
        
    def register_tool(self, tool: Tool):
        """Register tool with schema validation"""
        tool_name = tool.name
        self.tools[tool_name] = tool
        
        # Extract OpenAPI schema from decorator
        if hasattr(tool, '__openapi_schema__'):
            self.schemas[tool_name] = tool.__openapi_schema__
        
    async def execute_tool(self, tool_name: str, parameters: dict) -> ToolResult:
        """Execute tool with error handling"""
        if tool_name not in self.tools:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found",
                available_tools=list(self.tools.keys())
            )
        
        tool = self.tools[tool_name]
        
        try:
            # Validate parameters against schema
            self._validate_parameters(tool_name, parameters)
            
            # Execute tool
            result = await tool.execute(**parameters)
            
            # Log execution for debugging
            logger.info(f"Tool executed successfully", 
                       tool=tool_name, 
                       user_id=tool.user_id if hasattr(tool, 'user_id') else None)
            
            return result
            
        except Exception as e:
            logger.error(f"Tool execution failed", 
                        tool=tool_name, 
                        error=str(e),
                        parameters=parameters)
            
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}",
                tool_name=tool_name
            )
    
    def get_all_schemas(self) -> Dict[str, Any]:
        """Get all tool schemas for LLM context"""
        return {
            "tools": [
                {
                    "name": tool_name,
                    "schema": schema
                }
                for tool_name, schema in self.schemas.items()
            ]
        }
```

### **Response Processor (`backend/agentpress/response_processor.py`)**
```python
class ResponseProcessor:
    """Handles dual tool call parsing: XML and OpenAI formats"""
    
    async def process_llm_response(self, response: str, tool_registry: ToolRegistry) -> Dict[str, Any]:
        """Process LLM response with tool call detection and execution"""
        
        # Try XML format first (Claude-style)
        xml_tool_calls = self._parse_xml_tool_calls(response)
        if xml_tool_calls:
            results = await self._execute_xml_tools(xml_tool_calls, tool_registry)
            return {
                "format": "xml",
                "tool_calls": xml_tool_calls,
                "tool_results": results,
                "response_text": self._extract_text_from_xml_response(response)
            }
        
        # Try OpenAI function call format
        openai_tool_calls = self._parse_openai_tool_calls(response)
        if openai_tool_calls:
            results = await self._execute_openai_tools(openai_tool_calls, tool_registry)
            return {
                "format": "openai",
                "tool_calls": openai_tool_calls,
                "tool_results": results,
                "response_text": response
            }
        
        # No tool calls - regular text response
        return {
            "format": "text",
            "tool_calls": [],
            "tool_results": [],
            "response_text": response
        }
    
    def _parse_xml_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """Parse Claude-style XML tool calls"""
        import re
        import xml.etree.ElementTree as ET
        
        # Extract <function_calls> blocks
        function_blocks = re.findall(
            r'<function_calls>(.*?)</function_calls>', 
            response, 
            re.DOTALL
        )
        
        tool_calls = []
        for block in function_blocks:
            # Parse <invoke> elements
            invokes = re.findall(
                r'<invoke name="([^"]+)">(.*?)</invoke>',
                block,
                re.DOTALL
            )
            
            for tool_name, params_xml in invokes:
                # Parse parameter XML
                parameters = {}
                param_matches = re.findall(
                    r'<parameter name="([^"]+)">([^<]*)</parameter>',
                    params_xml
                )
                for param_name, param_value in param_matches:
                    parameters[param_name] = param_value
                
                tool_calls.append({
                    "name": tool_name,
                    "parameters": parameters
                })
        
        return tool_calls
```

### **Context Manager (`backend/agentpress/context_manager.py`)**
```python
class ContextManager:
    """Intelligent context and token management"""
    
    def __init__(self, model_config: Dict[str, Any]):
        self.model_config = model_config
        self.max_tokens = self._get_model_context_limit()
        self.compression_threshold = int(self.max_tokens * 0.8)  # 80% threshold
        
    async def manage_conversation_context(self, conversation: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Manage conversation context with intelligent compression"""
        
        # Calculate current token usage
        current_tokens = self._estimate_token_count(conversation)
        
        if current_tokens > self.compression_threshold:
            # Compress conversation while preserving recent context
            compressed = await self._compress_conversation(conversation)
            return compressed
        
        return conversation
    
    async def _compress_conversation(self, conversation: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Compress conversation using summarization"""
        
        # Keep system message and last N messages
        system_msg = conversation[0] if conversation[0]['role'] == 'system' else None
        recent_messages = conversation[-10:]  # Keep last 10 messages
        middle_messages = conversation[1:-10] if len(conversation) > 11 else []
        
        if middle_messages:
            # Summarize middle portion
            summary_prompt = "Summarize this conversation history concisely:\n"
            for msg in middle_messages:
                summary_prompt += f"{msg['role']}: {msg['content'][:200]}...\n"
            
            summary = await self._get_summary(summary_prompt)
            
            compressed = []
            if system_msg:
                compressed.append(system_msg)
            
            compressed.append({
                "role": "assistant",
                "content": f"[Conversation summary: {summary}]"
            })
            
            compressed.extend(recent_messages)
            return compressed
        
        return conversation
    
    def _get_model_context_limit(self) -> int:
        """Get context limit for current model"""
        model_limits = {
            "claude-sonnet-4": 200000,
            "gpt-4": 8192,
            "gpt-4-turbo": 128000,
            "claude-3-haiku": 200000,
            "claude-3-sonnet": 200000,
            "moonshotai/kimi-k2": 200000
        }
        
        return model_limits.get(self.model_config['name'], 8192)
```

This documentation provides comprehensive coverage of the complete tool, MCP, and agent systems, including implementation details, architectural patterns, and integration strategies.

#### **Agent Builder vs Regular Agent**
- **Regular Agent**: Uses system prompt from `backend/agent/prompt.py`
- **Agent Builder**: Uses builder prompt from `backend/agent/agent_builder_prompt.py`
- **Builder Mode**: Activated by `is_agent_builder=True` flag
- **Target Agent**: Builder can modify specific agent via `target_agent_id`

### Tool System Architecture

#### **Tool Base Classes**
```python
# Tool inheritance hierarchy
Tool (base)
├── AgentBuilderBaseTool  # For agent builder tools
├── SandboxTool          # For sandbox-based tools
└── MCPToolWrapper       # For external MCP integrations
```

#### **Tool Schema Patterns**
```python
@openapi_schema({
    "type": "function",
    "function": {
        "name": "tool_name",
        "description": "Clear tool purpose",
        "parameters": {
            "type": "object",
            "properties": {
                "param": {"type": "string", "description": "Parameter purpose"}
            },
            "required": ["param"]
        }
    }
})
```

#### **YouTube Tool Behavior (CRITICAL)**
- **Location**: `backend/agent/tools/youtube_complete_mcp_tool.py`
- **Zero-Questions Protocol**: Immediate tool usage without configuration questions
- **OAuth Handling**: All user interactions happen in OAuth popup
- **Channel Pre-computation**: YouTube channels loaded and cached in agent config
- **File System**: Uses reference ID system, not workspace files

### Custom Agent Creation Process

#### **Agent Builder Flow**
```python
# 1. Discovery Phase
get_current_agent_config()  # Check existing setup
# Ask about use case, tools needed, integrations desired

# 2. Tool Analysis Phase  
# Recommend required AgentPress tools
# Search for relevant MCP integrations
# Suggest workflow/trigger opportunities

# 3. Integration Setup Phase
search_mcp_servers(query="gmail")  # Find external services
create_credential_profile()        # Setup authenticated connections
configure_profile_for_agent()      # Add to agent config

# 4. Configuration Phase
update_agent(
    name="Custom Agent",
    system_prompt="Specialized instructions...",
    agentpress_tools={"web_search_tool": True},
    configured_mcps=[{"name": "gmail", "enabledTools": ["send_email"]}]
)

# 5. Automation Phase  
create_workflow()           # Multi-step processes
create_scheduled_trigger()  # Time-based automation
create_event_trigger()      # Real-time automation
```

#### **Agent Configuration Structure**
```python
# Complete agent configuration includes:
{
    # Identity
    "name": "Agent Name",
    "description": "What agent does",
    "avatar": "🤖", 
    "avatar_color": "#6B7280",
    
    # Behavior
    "system_prompt": "Custom instructions...",
    "model": "openrouter/moonshotai/kimi-k2",
    
    # Capabilities
    "agentpress_tools": {
        "sb_shell_tool": True,
        "browser_tool": False,
        "youtube_tool": True
    },
    
    # External integrations
    "configured_mcps": [
        {
            "name": "Gmail Integration",
            "qualifiedName": "gmail", 
            "config": {"profile_id": "profile-uuid"},
            "enabledTools": ["send_email", "read_email"]
        }
    ],
    
    # Custom integrations
    "custom_mcps": [
        {
            "name": "Slack Bot",
            "type": "composio",
            "toolkit_slug": "slack",
            "config": {"profile_id": "profile-uuid"},
            "enabledTools": ["send_message"]
        }
    ]
}
```

### Workflow System Details

#### **Workflow Types**
1. **Playbooks**: Template-based with variable substitution
2. **Tool Workflows**: Structured tool execution sequences  
3. **Conditional Workflows**: Branching logic based on results

#### **Workflow Execution**
- **Start Node**: Every workflow begins with start node
- **Step Types**: instruction, tool, condition
- **Variable Substitution**: `{{variable}}` tokens replaced at runtime
- **Tool Validation**: Only agent's enabled tools can be used
- **Status Management**: draft → active → execution

### Trigger System Implementation

#### **Scheduled Trigger Creation**
```python
# Via TriggerTool in agent builder
create_scheduled_trigger(
    name="Daily Report",
    cron_expression="0 9 * * *",     # 9 AM daily
    execution_type="workflow",       # or "agent"
    workflow_id="workflow-uuid",     # if workflow
    agent_prompt="Generate report"   # if direct agent
)
```

#### **Event Trigger Setup** (Non-Production)
```python
# 1. List available apps
list_event_trigger_apps()  # Gmail, Slack, GitHub, etc.

# 2. List triggers for specific app  
list_app_event_triggers(toolkit_slug="gmail")

# 3. List connected profiles
list_event_profiles(toolkit_slug="gmail")

# 4. Create trigger
create_event_trigger(
    slug="GMAIL_NEW_GMAIL_MESSAGE",
    profile_id="profile-uuid", 
    trigger_config={"labelIds": "INBOX"},
    route="agent",
    agent_prompt="Process this email"
)
```

### MCP Integration Architecture

#### **MCP Server Discovery**
```python
# Search for integrations
search_mcp_servers(query="gmail", limit=5)
get_popular_mcp_servers()
get_mcp_server_tools(qualified_name="gmail")

# Test connections
test_mcp_server_connection(qualified_name="gmail")
```

#### **Credential Profile Management**
```python
# Setup authenticated connections
get_credential_profiles(toolkit_slug="gmail")  # Check existing
create_credential_profile(app_slug="gmail", profile_name="Work Gmail")
# → Returns connection_link for user authentication

# After user authenticates
discover_user_mcp_servers()  # Get actual available tools
configure_profile_for_agent(profile_id, enabled_tools)
```

#### **MCP Tool Wrapper**
- **Location**: `backend/agent/tools/mcp_tool_wrapper.py`
- **Registration**: Dynamic tool registration based on MCP configs
- **Schema Handling**: Converts MCP schemas to AgentPress format
- **Execution**: Seamless integration with native tool execution

## Agent System Implementation Patterns

### **Thread-to-Agent Resolution Flow**
```python
# Complete flow from HTTP request to agent execution
1. API Request → backend/api.py
2. JWT Validation → get_account_id_from_thread()
3. Agent Resolution → Agent + Version lookup
4. Config Extraction → extract_agent_config()
5. Tool Registration → ToolManager.register_all_tools()
6. MCP Setup → MCPManager.register_mcp_tools()  
7. Execution → AgentRunner.run() → ThreadManager.run_thread()
```

### **Agent Builder Interaction Patterns**
```python
# Agent Builder Session Flow
1. User starts builder → is_agent_builder=True
2. Builder prompt loaded → agent_builder_prompt.py
3. Builder tools registered → agent_config_tool, mcp_search_tool, etc.
4. User interactions → update_agent(), search_mcp_servers()
5. Version created → VersionService.create_version()
6. Agent updated → current_version_id updated
```

### **MCP Integration Patterns**
```python
# MCP Tool Discovery & Integration
1. User requests → "I need Gmail integration"
2. Builder searches → search_mcp_servers(query="gmail")
3. Profile creation → create_credential_profile(app_slug="gmail")
4. User authentication → Connection link provided
5. Tool configuration → configure_profile_for_agent()
6. Agent update → configured_mcps added
7. Runtime registration → MCPToolWrapper registers tools
```

### **YouTube Native Integration Patterns**
```python
# YouTube Zero-Questions Flow
1. User mentions YouTube → Instant tool usage
2. youtube_authenticate() → OAuth button shown
3. User clicks → Google OAuth flow
4. Channel selection → User chooses in popup
5. Token storage → Encrypted in database
6. MCP toggles → Per-agent channel access
7. Tool execution → youtube_upload_video(), youtube_channels()

# Pre-computed Channel Data
- Channels loaded during config extraction
- Cached in agent_config['youtube_channels']
- Used in system prompt for context
- Reference ID system for file uploads
```

### **Tool Execution Context Flow**
```python
# XML Tool Execution Pipeline
1. LLM generates → <function_calls><invoke name="tool">
2. XML Parser → Extracts function_name + parameters
3. Tool Registry → Looks up registered function
4. Tool Execution → await tool_function(**parameters)
5. Result Processing → ToolResult + structured format
6. Message Persistence → Dual format (LLM + frontend)
7. Response Streaming → Real-time tool status updates
```

### **Agent Termination Patterns**
```python
# Termination Signal Handling
1. Tool execution → ask() or complete() tools
2. Termination signal → agent_should_terminate = True
3. Response processor → Detects termination metadata
4. Execution loop → continue_execution = False
5. Thread cleanup → Final status messages
6. Response end → No further iterations
```

### **Context Management Patterns**
```python
# Intelligent Context Compression
1. Token counting → litellm.token_counter()
2. Model limits → get_model_context_window()
3. Compression stages →
   - Tool result compression (except recent)
   - User message compression (except recent)  
   - Assistant message compression (except recent)
4. Fallback → Middle-out message removal
5. Expand tool → expand-message for truncated content
```

## Frontend Architecture Deep Dive

### **Core Application Structure**

#### **Next.js 15 App Router Architecture**
- **App Directory**: `frontend/src/app/` - New App Router structure
- **Route Groups**: Organized by feature (`(dashboard)`, `(home)`, `(auth)`)
- **Layout Nesting**: Shared layouts with proper TypeScript integration
- **API Routes**: Server actions and edge functions in `app/api/`
- **Metadata API**: Dynamic SEO with Next.js 15 metadata API

#### **TypeScript Configuration**
- **Strict Mode**: Full type safety with no `any` types
- **Path Mapping**: Clean imports with `@/` alias for `src/`
- **Component Props**: Comprehensive interface definitions
- **API Types**: Shared types between frontend and backend
- **Utility Types**: Custom type helpers for React patterns

### **State Management Architecture**

#### **React Query (TanStack Query) - Server State**
- **Location**: `frontend/src/hooks/react-query/`
- **Query Keys**: Hierarchical key factory pattern for cache management
- **Custom Hooks**: Abstracted API calls with optimistic updates
- **Cache Management**: Intelligent invalidation and prefetching
- **Background Updates**: Stale-while-revalidate patterns

```typescript
// Query Key Factory Pattern
export const agentKeys = {
  all: ['agents'] as const,
  lists: () => [...agentKeys.all, 'list'] as const,
  list: (params: AgentsParams) => [...agentKeys.lists(), params] as const,
  details: () => [...agentKeys.all, 'detail'] as const,
  detail: (id: string) => [...agentKeys.details(), id] as const,
  versions: (id: string) => [...agentKeys.detail(id), 'versions'] as const,
};

// Optimistic Updates with Rollback
export const useDeleteAgent = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: deleteAgent,
    onMutate: async (agentId) => {
      await queryClient.cancelQueries({ queryKey: agentKeys.lists() });
      const previousData = queryClient.getQueriesData({ queryKey: agentKeys.lists() });
      
      // Optimistic update
      queryClient.setQueriesData({ queryKey: agentKeys.lists() }, (old: any) => ({
        ...old,
        agents: old.agents.filter((agent: any) => agent.agent_id !== agentId)
      }));
      
      return { previousData };
    },
    onError: (err, variables, context) => {
      // Rollback on error
      if (context?.previousData) {
        context.previousData.forEach(([queryKey, data]) => {
          queryClient.setQueryData(queryKey, data);
        });
      }
    }
  });
};
```

#### **Zustand - Client State**
- **Location**: `frontend/src/lib/stores/`
- **Persistent State**: localStorage integration with selective persistence
- **Type Safety**: Full TypeScript integration with proper typing
- **Middleware**: Custom middleware for logging and persistence

```typescript
// Agent Selection Store with Persistence
export const useAgentSelectionStore = create<AgentSelectionState>()(
  persist(
    (set, get) => ({
      selectedAgentId: undefined,
      hasInitialized: false,
      
      initializeFromAgents: (agents, threadAgentId?, onAgentSelect?) => {
        // Complex initialization logic with URL params, localStorage, and defaults
        const selectedId = resolveAgentId(agents, threadAgentId);
        set({ selectedAgentId: selectedId, hasInitialized: true });
        onAgentSelect?.(selectedId);
      },
    }),
    {
      name: 'agent-selection-storage',
      partialize: (state) => ({ selectedAgentId: state.selectedAgentId })
    }
  )
);
```

### **Component Architecture**

#### **Thread Interface System** - Core Chat Experience
**Thread Content Rendering** (`frontend/src/components/thread/content/ThreadContent.tsx`):
- **Message Grouping**: Intelligent grouping of user/assistant message sequences
- **Streaming Support**: Real-time text and tool call streaming
- **Tool Integration**: Clickable tool buttons with side panel expansion
- **File Attachments**: Comprehensive file upload/preview system
- **Agent Avatar**: Dynamic agent avatars with fallbacks

```typescript
// Advanced Message Grouping Algorithm
const groupMessages = (messages: UnifiedMessage[]) => {
  const groups: MessageGroup[] = [];
  let currentGroup: MessageGroup | null = null;
  
  messages.forEach((message) => {
    if (message.type === 'user') {
      // Finalize assistant group, create user group
      if (currentGroup) groups.push(currentGroup);
      groups.push({ type: 'user', messages: [message], key: message.message_id });
      currentGroup = null;
    } else if (['assistant', 'tool', 'browser_state'].includes(message.type)) {
      // Group consecutive assistant-related messages
      const canAddToGroup = currentGroup?.type === 'assistant_group' && 
        sameAgentContext(currentGroup, message);
      
      if (canAddToGroup) {
        currentGroup.messages.push(message);
      } else {
        if (currentGroup) groups.push(currentGroup);
        currentGroup = { type: 'assistant_group', messages: [message], key: generateGroupKey() };
      }
    }
  });
  
  return groups;
};
```

**Chat Input System** (`frontend/src/components/thread/chat-input/`):
- **Multi-file Upload**: Drag-and-drop with progress tracking
- **Voice Recording**: WebRTC integration with transcription
- **Smart File Detection**: Automatic YouTube upload routing
- **Model Selection**: Dynamic model picker with subscription checks
- **Agent Selection**: Persistent agent selection with URL support

#### **Agent Management System** - Complete Agent Lifecycle
**Agent Configuration** (`frontend/src/components/agents/config/`):
- **Tabbed Interface**: Agent Builder vs Manual Configuration
- **Version Management**: Git-like versioning with branch switching
- **Live Preview**: Real-time configuration validation
- **Profile Management**: Avatar upload with image optimization

```typescript
// Agent Configuration with Real-time Validation
export function AgentConfigurationTab({ agentId, formData, onFormDataChange }: Props) {
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const debouncedFormData = useDebounce(formData, 500);
  
  // Real-time validation with debouncing
  useEffect(() => {
    validateAgentConfig(debouncedFormData)
      .then(errors => setValidationErrors(errors))
      .catch(console.error);
  }, [debouncedFormData]);
  
  return (
    <div className="space-y-6">
      <SystemPromptEditor
        value={formData.system_prompt}
        onChange={(value) => onFormDataChange('system_prompt', value)}
        errors={validationErrors.filter(e => e.field === 'system_prompt')}
      />
      <ToolConfiguration
        tools={formData.agentpress_tools}
        onChange={(tools) => onFormDataChange('agentpress_tools', tools)}
      />
    </div>
  );
}
```

**Agent Grid & Cards** (`frontend/src/components/agents/agents-grid.tsx`):
- **Masonry Layout**: Responsive grid with dynamic card sizing
- **Optimistic Updates**: Instant UI feedback with rollback support
- **Publishing System**: Template marketplace integration
- **Bulk Operations**: Multi-select with batch operations

#### **Tool Views System** - Rich Tool Result Display
**Tool View Registry** (`frontend/src/components/thread/tool-views/wrapper/`):
- **Dynamic Loading**: Lazy-loaded tool-specific renderers
- **Unified Interface**: Consistent tool result presentation
- **Status Management**: Loading, success, error state handling
- **Export Capabilities**: Tool result export functionality

```typescript
// Dynamic Tool View Loading
export const ToolViewRegistry: React.FC<ToolViewProps> = (props) => {
  const ToolComponent = useMemo(() => {
    // Dynamic import based on tool name
    const toolName = props.name.replace(/_/g, '-');
    
    switch (toolName) {
      case 'file-operation':
        return lazy(() => import('./file-operation/FileOperationToolView'));
      case 'web-search':
        return lazy(() => import('./web-search-tool/WebSearchToolView'));
      case 'youtube-upload':
        return lazy(() => import('./YouTubeUploadProgressView'));
      default:
        return lazy(() => import('./GenericToolView'));
    }
  }, [props.name]);
  
  return (
    <Suspense fallback={<ToolViewSkeleton />}>
      <ToolComponent {...props} />
    </Suspense>
  );
};
```

### **Real-time Systems**

#### **Agent Streaming** - Live Tool Execution
**useAgentStream Hook** (`frontend/src/hooks/useAgentStream.ts`):
- **EventSource Integration**: Server-sent events with automatic reconnection
- **Message Parsing**: Real-time JSON parsing with error recovery
- **Status Management**: Connection state tracking and error handling
- **Tool Call Streaming**: Live tool execution with progress updates

```typescript
export const useAgentStream = (callbacks: StreamCallbacks, threadId: string) => {
  const [status, setStatus] = useState<StreamStatus>('idle');
  const eventSourceRef = useRef<EventSource | null>(null);
  
  const startStreaming = useCallback((agentRunId: string) => {
    const eventSource = new EventSource(`/api/agent-run/${agentRunId}/stream`);
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // Handle different message types
        switch (data.type) {
          case 'text_delta':
            callbacks.onTextDelta?.(data.content);
            break;
          case 'tool_call':
            callbacks.onToolCall?.(data.tool_call);
            break;
          case 'message_complete':
            callbacks.onMessage?.(data.message);
            break;
          case 'status':
            setStatus(data.status);
            if (data.status === 'completed') {
              callbacks.onComplete?.();
              cleanup();
            }
            break;
        }
      } catch (error) {
        callbacks.onError?.(error);
      }
    };
    
    eventSourceRef.current = eventSource;
  }, [callbacks]);
  
  return { status, startStreaming, stopStreaming };
};
```

#### **File Upload System** - Universal File Handling
**Smart File Handler** (`frontend/src/components/thread/chat-input/smart-file-handler.tsx`):
- **Intent Detection**: Automatic routing based on message content
- **Progress Tracking**: Real-time upload progress with cancellation
- **Preview Generation**: Client-side preview generation
- **Reference System**: YouTube-compatible reference ID system

### **Social Media Integration**

#### **YouTube Integration** - Complete Video Workflow
**Upload Progress Views** (`frontend/src/components/thread/tool-views/`):
- **Real-time Progress**: WebSocket-based upload progress
- **Preview Generation**: Video thumbnail and metadata preview
- **Error Handling**: Detailed error reporting with retry logic
- **Channel Management**: Multi-channel support with auto-selection

```typescript
// YouTube Upload with Progress Tracking
export const YouTubeUploadProgressView: React.FC<Props> = ({ uploadData }) => {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<UploadStatus>('preparing');
  
  // WebSocket connection for real-time updates
  useEffect(() => {
    const ws = new WebSocket(`/ws/upload/${uploadData.reference_id}`);
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setProgress(data.progress);
      setStatus(data.status);
      
      if (data.status === 'completed') {
        onUploadComplete?.(data.video_data);
      }
    };
    
    return () => ws.close();
  }, [uploadData.reference_id]);
  
  return (
    <div className="upload-progress">
      <ProgressBar value={progress} status={status} />
      <VideoPreview data={uploadData} />
    </div>
  );
};
```

**Channel Management** (`frontend/src/app/(dashboard)/social-media/page.tsx`):
- **OAuth Flow**: Popup-based authentication with message passing
- **Multi-Platform**: Extensible architecture for multiple platforms
- **Statistics Display**: Real-time follower/view counts
- **Account Switching**: Seamless switching between connected accounts

### **UI Component System**

#### **shadcn/ui Integration** - Consistent Design Language
**Component Library** (`frontend/src/components/ui/`):
- **Radix Primitives**: Accessible, unstyled components as foundation
- **Tailwind Styling**: Utility-first CSS with design tokens
- **Dark Mode**: System-wide theme switching with persistence
- **Responsive Design**: Mobile-first responsive components

```typescript
// Custom Button Component with Variants
const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    
    return (
      <Comp
        className={cn(
          // Base styles
          "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
          // Variant styles
          {
            "bg-primary text-primary-foreground hover:bg-primary/90": variant === "default",
            "bg-destructive text-destructive-foreground hover:bg-destructive/90": variant === "destructive",
            "border border-input bg-background hover:bg-accent hover:text-accent-foreground": variant === "outline",
          },
          // Size styles
          {
            "h-10 px-4 py-2": size === "default",
            "h-9 rounded-md px-3": size === "sm",
            "h-11 rounded-md px-8": size === "lg",
          },
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
```

#### **Advanced UI Patterns** - Complex Interactions
**Data Tables** (`frontend/src/components/ui/data-table.tsx`):
- **Sorting & Filtering**: Built-in table controls
- **Pagination**: Efficient large dataset handling
- **Selection**: Multi-row selection with bulk actions
- **Export**: CSV/JSON export functionality

**Modal System** (`frontend/src/components/ui/dialog.tsx`):
- **Stacked Modals**: Multiple modal layers
- **Focus Management**: Proper accessibility handling
- **Animation**: Smooth open/close animations
- **Responsive**: Mobile-optimized modal behavior

### **Performance Optimizations**

#### **Code Splitting & Lazy Loading**
- **Route-based**: Automatic code splitting by route
- **Component-based**: Lazy loading of heavy components
- **Tool Views**: Dynamic tool view imports
- **Bundle Analysis**: Webpack bundle analyzer integration

#### **Caching Strategies**
- **React Query**: Intelligent server state caching
- **Image Optimization**: Next.js automatic image optimization
- **Static Assets**: Long-term caching with versioning
- **API Response**: Stale-while-revalidate patterns

### **Error Handling & Monitoring**

#### **Error Boundaries** - Comprehensive Error Catching
```typescript
export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }
  
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log to monitoring service
    console.error('Error caught by boundary:', error, errorInfo);
    
    // Send to error tracking
    if (typeof window !== 'undefined') {
      (window as any).posthog?.capture('frontend_error', {
        error: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
      });
    }
  }
  
  render() {
    if (this.state.hasError) {
      return this.props.fallback || <ErrorFallback error={this.state.error} />;
    }
    
    return this.props.children;
  }
}
```

#### **API Error Handling** - Structured Error Management
```typescript
// Centralized API Error Handler
export const handleApiError = (error: unknown, context?: ErrorContext) => {
  if (error instanceof BillingError) {
    // Handle billing-specific errors
    showBillingModal(error.detail);
    return;
  }
  
  if (error instanceof AgentRunLimitError) {
    // Handle agent limit errors
    showAgentLimitDialog(error.detail);
    return;
  }
  
  // Generic error handling
  const message = error instanceof Error ? error.message : 'An unknown error occurred';
  toast.error(message);
  
  // Log for monitoring
  console.error('API Error:', error, context);
};
```

### **Development Workflow**

#### **Hot Module Replacement** - Fast Development
- **TurboPack**: Next.js 15 fast bundler for instant updates
- **Component Hot Reload**: React components update without losing state
- **CSS Hot Reload**: Style changes apply instantly
- **API Route Updates**: Server-side updates with minimal restart

#### **Type Safety** - Comprehensive TypeScript
```typescript
// API Response Types with Backend Synchronization
export interface AgentResponse {
  agent_id: string;
  name: string;
  description?: string;
  system_prompt: string;
  agentpress_tools: Record<string, boolean>;
  configured_mcps: ConfiguredMCP[];
  metadata: AgentMetadata;
  current_version: {
    version_id: string;
    version_number: number;
    created_at: string;
  };
}

// React Component Props with Strict Typing
interface ChatInputProps {
  onSubmit: (message: string, options?: SubmitOptions) => void;
  loading?: boolean;
  disabled?: boolean;
  selectedAgentId?: string;
  onAgentSelect?: (agentId: string | undefined) => void;
  toolCalls?: ToolCallInput[];
  showScrollToBottomIndicator?: boolean;
  onScrollToBottom?: () => void;
}
```

## Development Best Practices

### Frontend Development
- **Component Architecture**: Use composition over inheritance with proper prop typing
- **State Management**: React Query for server state, Zustand for client state persistence
- **Error Boundaries**: Implement error boundaries for all major component trees
- **Performance**: Use React.memo, useMemo, and useCallback strategically
- **Accessibility**: Maintain ARIA compliance with shadcn/ui components
- **Testing**: Write unit tests for business logic, integration tests for user flows
- **Mobile First**: Design responsive layouts with mobile-first approach

### Agent Development
- **System Prompts**: Write comprehensive, behavior-defining prompts
- **Tool Selection**: Choose minimal required toolset for performance
- **Version Control**: Use agent versioning for configuration changes
- **YouTube Integration**: Never ask questions - use OAuth automation
- **MCP Setup**: Always authenticate users before tool configuration
- **Workflow Design**: Structure complex processes with clear variable definitions
- **Trigger Configuration**: Use appropriate trigger types (scheduled vs event-based)

### Code Standards
- **Type Safety**: Use strict TypeScript (no `any` types) and comprehensive Python type hints
- **UI Components**: Default to shadcn/ui components with Radix UI primitives
- **State Management**: Use React Query for server state, React hooks for local state
- **Error Handling**: Implement structured error responses with proper HTTP status codes
- **Logging**: Use structured logging with context throughout the application stack
- **Testing**: Write unit tests for business logic, integration tests for API endpoints
- **Security**: Always implement input validation, authentication checks, and encrypt sensitive data
- **Performance**: Use async/await patterns, connection pooling, and Redis caching
- **Database**: Include RLS policies and proper indexing in all migrations