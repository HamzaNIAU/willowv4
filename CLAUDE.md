# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kortix is an open-source platform for building, managing, and training AI agents. The platform includes Suna, a flagship generalist AI worker agent, and provides infrastructure for creating custom specialized agents.

## Tech Stack

### Backend
- **Python 3.11+** with uv package manager
- **FastAPI** for REST API endpoints
- **Dramatiq** for background job processing
- **Redis** for caching and session management
- **Supabase** for database, authentication, and storage
- **LiteLLM** for LLM provider abstraction (Anthropic, OpenAI, OpenRouter, Gemini)
- **Docker** for containerized deployment
- **MCP (Model Context Protocol)** for tool integrations

### Frontend
- **Next.js 15** with App Router and TurboPack
- **TypeScript** for type safety
- **React 18** with React Query for data fetching
- **Tailwind CSS v4** for styling
- **Supabase** client for auth and realtime subscriptions
- **Radix UI** for component primitives
- **Zustand** for state management

## Common Development Commands

### Backend

```bash
# Install dependencies (uses uv)
cd backend
uv sync

# Run API server locally
uv run api.py

# Run background worker
uv run dramatiq --processes 4 --threads 4 run_agent_background

# Run with Docker
docker compose down && docker compose up --build

# Run only Redis (for local development)
docker compose up redis

# When running API locally with Redis in Docker, update .env:
# REDIS_HOST=localhost (instead of 'redis')
```

### Frontend

```bash
# Install dependencies
cd frontend
npm install

# Development server with TurboPack
npm run dev

# Build for production
npm run build

# Start production server
npm run start

# Linting and formatting
npm run lint
npm run format
```

### Testing

```bash
# Backend tests
cd backend
uv run pytest

# No frontend test command configured yet
```

## Architecture & Key Components

### Backend Architecture

1. **API Layer** (`backend/api.py`)
   - FastAPI application serving REST endpoints
   - Authentication via Supabase JWT tokens
   - WebSocket support for real-time agent communication

2. **Agent System** (`backend/agent/`)
   - `run.py`: Core agent execution logic
   - `api.py`: Agent-specific API endpoints
   - `prompt.py`: System prompts for agent behavior
   - `agent_builder_prompt.py`: Prompts for agent creation
   - Tool system for extensible agent capabilities

3. **Background Processing** (`backend/run_agent_background.py`)
   - Dramatiq workers for async agent execution
   - Redis-backed job queue
   - Handles long-running agent tasks

4. **Services** (`backend/services/`)
   - MCP integration for external tools
   - YouTube integration service
   - Feature flag system via Redis
   - File handling and storage

5. **Database** (Supabase)
   - User authentication and profiles
   - Agent configurations and templates
   - Thread/conversation history
   - File storage and metadata

### Frontend Architecture

1. **App Router Structure** (`frontend/src/app/`)
   - `(dashboard)`: Main authenticated app interface
   - `(home)`: Public landing pages
   - `auth`: Authentication flows
   - `share`: Public thread sharing

2. **Core Components** (`frontend/src/components/`)
   - `thread/`: Chat interface and message components
   - `agents/`: Agent configuration and management
   - `sidebar/`: Navigation components
   - `settings/`: User and team settings

3. **State Management**
   - React Query for server state
   - Zustand for client state
   - Context providers for subscriptions and auth

4. **API Integration**
   - Backend API client with type safety
   - Supabase client for auth and realtime
   - WebSocket handling for agent streaming

## Environment Variables

### Backend (.env)
```bash
ENV_MODE=local
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
REDIS_HOST=redis  # or localhost for local dev
REDIS_PORT=6379
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
MODEL_TO_USE=
TAVILY_API_KEY=
FIRECRAWL_API_KEY=
DAYTONA_API_KEY=
DAYTONA_SERVER_URL=
WEBHOOK_BASE_URL=
MCP_CREDENTIAL_ENCRYPTION_KEY=
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000/api
NEXT_PUBLIC_URL=http://localhost:3000
NEXT_PUBLIC_ENV_MODE=LOCAL
```

## Database Migrations

Migrations are stored in `backend/supabase/migrations/` and applied via Supabase CLI or dashboard.

## Feature Flags

Managed via Redis, controlled through CLI:
```bash
cd backend/flags
python setup.py enable <flag_name> "description"
python setup.py disable <flag_name>
python setup.py list
```

Current flags:
- `custom_agents`: Custom agent creation
- `agent_marketplace`: Agent marketplace functionality

## MCP (Model Context Protocol) Integration

The platform supports MCP servers for tool extensions. YouTube MCP server is included at `backend/youtube_mcp/`.

## Docker Development

- Main services defined in `docker-compose.yaml`
- Production overrides in `docker-compose.prod.yml`
- Redis configured with persistence
- Worker processes handle background agent execution

## Key Workflows

1. **Agent Execution Flow**
   - User sends message → API endpoint
   - Job queued to Dramatiq via Redis
   - Worker processes agent logic
   - Results streamed back via WebSocket/API

2. **Agent Builder**
   - Visual configuration interface
   - Tool selection and configuration
   - Workflow builder for multi-step processes
   - Template system for reusable agents

3. **Authentication Flow**
   - Supabase handles user auth
   - JWT tokens for API authentication
   - Team/organization support
   - Role-based access control