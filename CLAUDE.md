# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Quick reference guide for Kortix (formerly Suna) platform development - an open-source AI agent platform with Agentpress framework.

## Project Overview

**Kortix** (previously Suna) - Open-source AI agent platform featuring Suna generalist agent + Agentpress framework.

**Tech Stack:**
- Backend: Python 3.11+/FastAPI/Dramatiq/Redis/Supabase/LiteLLM/Agentpress/MCP
- Frontend: Next.js 15/TypeScript/React 18/TailwindCSS v4/shadcn-ui/Zustand
- SDK: Python (`sdk/kortix/`)

## Essential Commands

| Category | Command | Description |
|----------|---------|-------------|
| **Setup** | `python setup.py` | 14-step wizard |
| | `python start.py` | Start/stop all services |
| **Backend** | `cd backend && uv sync` | Install dependencies |
| | `uv run api.py` | Run API server |
| | `uv run dramatiq --processes 4 --threads 4 run_agent_background` | Run worker |
| | `uv run pytest` | Run all tests |
| | `uv run pytest test_file.py::test_function` | Run single test |
| | `uv run apply_migration.py` | Apply migrations |
| | `uv run ruff check . && uv run ruff format .` | Lint/format |
| **Frontend** | `cd frontend && npm install` | Install dependencies |
| | `npm run dev` | Development with TurboPack |
| | `npm run build && npm run start` | Production |
| | `npm run lint && npm run format` | Code quality |
| **Docker** | `python start.py` | **ALWAYS use for containers** |
| | `docker compose logs -f backend` | View logs |

## Architecture Reference

### Agent System
- **Core**: `backend/agent/run.py` - AgentRunner orchestration
- **Framework**: `backend/agentpress/` - Tool management & thread handling
- **Default Agent**: `backend/agent/prompt.py` - Suna system prompt (1500+ lines)
- **Agent Builder**: `backend/agent/agent_builder_prompt.py` - Builder prompt (500+ lines)
- **Config Flow**: `backend/agent/config_helper.py` - Configuration extraction
- **Versioning**: `backend/agent/versioning/version_service.py` - Git-like versioning

### Tool System
- **Base**: `backend/agentpress/tool.py` - Tool base classes
- **Core Tools**: `backend/agent/tools/` - AgentPress built-in tools
- **Builder Tools**: `backend/agent/tools/agent_builder_tools/` - Agent configuration
- **MCP Wrapper**: `backend/agent/tools/mcp_tool_wrapper.py` - External integrations
- **Social Media Tools**: Native implementations for YouTube, Twitter, Instagram, Pinterest, LinkedIn

### MCP Integration
- **Types**: Standard servers, Composio (2700+ tools), Pipedream workflows
- **Management**: `backend/services/mcp_toggles.py` - Per-agent toggles
- **Credentials**: `backend/services/credential_profiles.py` - Encrypted storage
- **Discovery**: Search via `MCPSearchTool` in agent builder

### Social Media System (NATIVE - NOT MCP)
- **YouTube**: `backend/youtube_mcp/` - OAuth, upload, management
- **Twitter**: `backend/twitter_mcp/` - Tweet, media upload
- **Instagram**: `backend/instagram_mcp/` - Post, story upload
- **Pinterest**: `backend/pinterest_mcp/` - Pin creation
- **LinkedIn**: `backend/linkedin_mcp/` - Professional posting
- **Reference System**: `backend/services/youtube_file_service.py` - 32-char hex IDs

### Frontend Components
- **Thread UI**: `frontend/src/components/thread/` - Chat interface
- **Agent Management**: `frontend/src/components/agents/` - Configuration UI
- **Tool Views**: `frontend/src/components/thread/tool-views/` - Result rendering
- **MCP UI**: `frontend/src/components/thread/chat-input/mcp-connections-dropdown.tsx`

## Critical Patterns

### Social Media Zero-Questions Protocol
- **NEVER** ask about account/channel preferences for any social platform
- **ALWAYS** use tools immediately when social media mentioned
- **OAuth popup** handles ALL user interactions
- **Reference IDs** (32-char hex) for file management, NOT workspace paths
- **Auto-discovery** finds latest uploaded files automatically
- **Channel/Account selection** automatic for single-account users

### Agent Configuration Structure
```json
{
  "name": "Agent Name",
  "system_prompt": "Instructions...",
  "model": "openrouter/moonshotai/kimi-k2",
  "agentpress_tools": {"tool_name": true/false},
  "configured_mcps": [{"name": "Gmail", "qualifiedName": "gmail", "enabledTools": ["send"]}],
  "custom_mcps": [{"type": "composio", "toolkit_slug": "slack"}],
  "youtube_channels": [{"id": "UC...", "name": "Channel"}],  // Pre-computed
  "social_accounts": {
    "twitter": [{"id": "123", "username": "@user"}],
    "instagram": [{"id": "456", "username": "user"}]
  }
}
```

### Tool Registration Order
1. Core tools (always enabled): Message, TaskList, ExpandMessage
2. Sandbox tools (configurable): Shell, Files, Browser, Vision, Deploy, Expose
3. Utility tools: Social Media (YouTube, Twitter, etc.), DataProviders, WebSearch
4. Agent builder tools (if agent_id): AgentConfig, Workflow, Trigger, MCP tools
5. MCP tools (external): Dynamic registration from configured_mcps

### Workflow & Trigger Patterns
- **Workflows**: Playbooks with `{{variables}}`, tool sequences, conditional logic
- **Scheduled Triggers**: Cron expressions for time-based automation
- **Event Triggers** (non-prod): Real-time from Gmail, Slack, GitHub via Composio
- **Execution Types**: Direct agent prompt OR workflow execution

### MCP Toggle System
- Per-agent, per-user control: `agent_id + user_id + mcp_id`
- Social media accounts auto-enabled when connected
- Social media MCPs default disabled for security
- Standard MCPs default enabled

## Quick Reference Tables

### Key File Locations

| System | Key Files |
|--------|-----------|
| **Agent Core** | `backend/agent/run.py`, `backend/agent/prompt.py`, `backend/agent/config_helper.py` |
| **AgentPress** | `backend/agentpress/thread_manager.py`, `backend/agentpress/tool_registry.py` |
| **Tools** | `backend/agent/tools/`, `backend/agent/tools/agent_builder_tools/` |
| **Social Media** | `backend/youtube_mcp/`, `backend/twitter_mcp/`, `backend/instagram_mcp/`, `backend/pinterest_mcp/`, `backend/linkedin_mcp/` |
| **Frontend** | `frontend/src/app/`, `frontend/src/components/thread/`, `frontend/src/hooks/` |
| **Database** | `backend/supabase/migrations/` |
| **Services** | `backend/services/`, `backend/credentials/`, `backend/composio_integration/` |

### Database Tables

| Table | Purpose |
|-------|---------|
| **agents** | Agent definitions with current_version_id |
| **agent_versions** | Configuration versioning |
| **agent_workflows** | Workflow definitions |
| **agent_triggers** | Scheduled/event triggers |
| **threads** | Conversation threads |
| **messages** | Thread messages |
| **credential_profiles** | Encrypted MCP credentials |
| **mcp_toggles** | Per-agent MCP control |
| **youtube_channels** | Connected YouTube accounts |
| **video_file_references** | 32-char reference IDs for uploads |
| **youtube_uploads** | Upload progress tracking |
| **unified_accounts** | Cross-platform social media accounts |

### Environment Variables

```bash
# Backend (.env)
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
REDIS_HOST=redis  # 'localhost' for local
REDIS_PORT=6380  # External port
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
MCP_CREDENTIAL_ENCRYPTION_KEY=
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=
YOUTUBE_REDIRECT_URI=
TWITTER_CLIENT_ID=
TWITTER_CLIENT_SECRET=
INSTAGRAM_CLIENT_ID=
INSTAGRAM_CLIENT_SECRET=

# Frontend (.env.local)
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000/api
```

### API Endpoints

| Endpoint | Purpose |
|----------|---------|
| **POST /api/agent-run** | Start agent execution |
| **GET /api/agent-run/{id}/stream** | SSE agent streaming |
| **POST /api/youtube/auth/initiate** | Start YouTube OAuth |
| **POST /api/twitter/auth/initiate** | Start Twitter OAuth |
| **POST /api/instagram/auth/initiate** | Start Instagram OAuth |
| **GET /api/youtube/channels** | List connected channels |
| **POST /api/youtube/universal-upload** | Upload to YouTube |
| **GET /api/agents/{id}/mcp-toggles** | MCP toggle states |

### AgentPress Core Tools

| Tool | Purpose | Status |
|------|---------|--------|
| **sb_shell_tool** | Terminal execution | Configurable |
| **sb_files_tool** | File management | Configurable |
| **browser_tool** | Web automation | Configurable |
| **web_search_tool** | Internet search | Configurable |
| **sb_vision_tool** | Image processing | Configurable |
| **sb_deploy_tool** | App deployment | Configurable |
| **data_providers_tool** | APIs (Zillow, Yahoo) | Configurable |
| **youtube_tool** | YouTube native | Configurable |
| **twitter_tool** | Twitter native | Configurable |
| **instagram_tool** | Instagram native | Configurable |
| **pinterest_tool** | Pinterest native | Configurable |
| **linkedin_tool** | LinkedIn native | Configurable |
| **message_tool** | Communication | Always enabled |
| **task_list_tool** | Workflow tracking | Always enabled |

## Development Guidelines

### Security & Performance
- JWT validation without signature (Supabase pattern)
- Row-level security on all user tables
- Fernet encryption for credentials
- Redis caching with TTL (MCP schemas: 1hr)
- Connection pooling for database/HTTP
- Chunked uploads (1MB chunks)

### Error Handling
- Billing errors → Show upgrade modal
- OAuth expiry → Auto-refresh with 3 retries
- Tool failures → Structured ToolResult errors
- Network errors → Progressive backoff (1s, 5s, 15s)

### Best Practices
- **Container Management**: Always use `python start.py`
- **Redis Port**: External 6380, internal 6379
- **Social Media**: Use reference IDs, never ask questions
- **Migrations**: Include RLS policies and indexes
- **Testing**: Run tests before commits
- **Type Safety**: No `any` in TypeScript, type hints in Python
- **Components**: Default to shadcn/ui with Radix primitives
- **State**: React Query for server, Zustand for client

### Agent Development Flow
1. **Discovery**: User describes needs
2. **Tool Analysis**: Recommend AgentPress tools + MCP integrations
3. **Integration Setup**: Create credential profiles, authenticate
4. **Configuration**: update_agent() with system prompt, tools, MCPs
5. **Automation**: Create workflows and triggers
6. **Version Control**: All changes create new versions

### Critical Rules
- **Social Media Integration**: NEVER ask questions, use OAuth for ALL interactions
- **File References**: 32-char hex IDs for social media, workspace paths for code
- **Agent Builder**: Only modifies target_agent_id, protects Suna identity
- **MCP Toggles**: Per-agent control with auto-enable for connected accounts
- **Tool Execution**: XML format `<function_calls><invoke>` or OpenAI format
- **Context Compression**: 80% threshold triggers summarization
- **Billing Checks**: Every agent iteration validates usage limits

### Docker & Service Management
- **Always use `python start.py`** for container lifecycle management
- **Redis**: Runs on port 6380 externally, 6379 internally
- **Backend**: Port 8000, depends on Redis and worker
- **Frontend**: Port 3000, connects to backend internally via docker network
- **Worker**: Dramatiq background processor for async tasks
- **Health Checks**: Redis has built-in health monitoring
- **Volumes**: Config and source code mounted for development

### Rebuilding Docker Containers After Backend Changes
**IMPORTANT**: After making changes to backend code, you must rebuild and restart containers:
```bash
# 1. Rebuild the backend container
docker compose build --no-cache backend

# 2. Stop and remove existing containers
echo "y" | python start.py

# 3. Start fresh containers
echo "" | python start.py  # or just press Enter for default Yes
```
This ensures your backend changes are properly reflected in the running containers.

### Testing & Quality
- **Backend**: `uv run pytest` for Python tests
- **Frontend**: `npm run lint` and `npm run format` for code quality
- **Backend Linting**: `uv run ruff check . && uv run ruff format .`
- **Type Checking**: Enforced in both TypeScript and Python
- **Pre-commit**: Run linting before commits

## Recent Updates (2025)
- Universal social media upload with smart detection
- Reference ID system for file management across all platforms
- Agent UUID validation prevents 404s
- Python SDK for external integrations (`sdk/kortix/`)
- Custom agents temporarily disabled (Suna only)
- Expanded social media support (Twitter, Instagram, Pinterest, LinkedIn)
- Unified account management system

## Common Troubleshooting

### Backend Issues
- **Redis connection errors**: Ensure Redis is running on port 6380 (external) / 6379 (internal)
- **Migration failures**: Check Supabase connection and run `uv run apply_migration.py`
- **Worker not processing**: Restart with proper flags: `uv run dramatiq --processes 4 --threads 4 run_agent_background`

### Frontend Issues
- **Build errors**: Clear `.next` folder and run `npm run build` again
- **Type errors**: Run `npm run lint` to identify TypeScript issues
- **API connection**: Verify `NEXT_PUBLIC_BACKEND_URL` in `.env.local`

### Docker Issues
- **Container changes not reflecting**: Rebuild with `docker compose build --no-cache backend`
- **Service health**: Check logs with `docker compose logs -f [service-name]`
- **Port conflicts**: Ensure ports 3000, 8000, 6380 are available