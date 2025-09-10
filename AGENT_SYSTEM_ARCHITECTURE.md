# Kortix Agent System & AgentPress Framework Architecture

## Executive Summary

The Kortix platform (formerly Suna) implements a sophisticated autonomous agent system built on the custom AgentPress framework. This document provides a comprehensive technical analysis of the agent execution lifecycle, tool management, conversation handling, and the overall architecture that enables AI agents to perform complex tasks autonomously.

## Table of Contents

1. [System Overview](#system-overview)
2. [Agent Execution Lifecycle](#agent-execution-lifecycle)
3. [AgentPress Framework Architecture](#agentpress-framework-architecture)
4. [Tool System Architecture](#tool-system-architecture)
5. [Thread Management & Conversation Handling](#thread-management--conversation-handling)
6. [Agent Configuration & Versioning](#agent-configuration--versioning)
7. [Context Management & Compression](#context-management--compression)
8. [Response Processing & Tool Execution](#response-processing--tool-execution)
9. [Key Design Patterns](#key-design-patterns)
10. [Integration Points](#integration-points)

---

## 1. System Overview

### Core Components

The agent system consists of several interconnected layers:

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Runner Layer                       │
│  • AgentRunner (run.py) - Main orchestration                │
│  • AgentConfig - Configuration management                    │
│  • Execution control & iteration management                  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   AgentPress Framework                       │
│  • ThreadManager - Conversation management                   │
│  • ToolRegistry - Tool registration & discovery              │
│  • ResponseProcessor - LLM response & tool execution         │
│  • ContextManager - Token & context compression              │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Tool Layer                              │
│  • Core Tools (Message, TaskList, ExpandMessage)            │
│  • Sandbox Tools (Shell, Files, Deploy, etc.)               │
│  • Social Media Tools (YouTube, Twitter, etc.)              │
│  • MCP Tool Wrapper (External integrations)                 │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Persistence Layer                         │
│  • Supabase (PostgreSQL) - Data storage                     │
│  • Redis - Caching & session management                      │
│  • Version Control System - Agent versioning                │
└─────────────────────────────────────────────────────────────┘
```

### Key Technologies

- **Backend**: Python 3.11+, FastAPI, Dramatiq (async workers)
- **Framework**: Custom AgentPress for agent orchestration
- **LLM Integration**: LiteLLM for multi-provider support
- **Database**: Supabase (PostgreSQL) with Row-Level Security
- **Cache**: Redis for MCP schemas and session data
- **Tool Protocol**: OpenAPI schemas for function calling
- **Streaming**: Server-Sent Events (SSE) for real-time updates

---

## 2. Agent Execution Lifecycle

### 2.1 Initialization Phase

```python
# From backend/agent/run.py

class AgentRunner:
    async def setup(self):
        # 1. Initialize tracing for observability
        self.trace = langfuse.trace(...)
        
        # 2. Create ThreadManager with agent context
        self.thread_manager = ThreadManager(
            trace=self.trace,
            is_agent_builder=self.config.is_agent_builder,
            target_agent_id=self.config.target_agent_id,
            agent_config=self.config.agent_config
        )
        
        # 3. Resolve account and user IDs
        self.account_id = await get_account_id_from_thread(...)
        self.user_id = await _get_user_id_from_account_cached(...)
        
        # 4. Verify project exists and sandbox availability
        project = await self.client.table('projects').select('*')...
```

### 2.2 Tool Registration Phase

The system employs a sophisticated multi-stage tool registration process:

```python
class ToolManager:
    async def register_all_tools(self, agent_id, disabled_tools):
        # Stage 1: Core tools (always enabled)
        self._register_core_tools()  # Message, TaskList, ExpandMessage
        
        # Stage 2: Sandbox tools (configurable)
        self._register_sandbox_tools(disabled_tools)  # Shell, Files, Deploy, etc.
        
        # Stage 3: Utility tools with pre-computed data
        await self._register_utility_tools(disabled_tools)  # Social media, data providers
        
        # Stage 4: Agent builder tools (if applicable)
        if agent_id:
            self._register_agent_builder_tools(agent_id, disabled_tools)
        
        # Stage 5: Browser tool
        self._register_browser_tool(disabled_tools)
```

### 2.3 MCP Tool Registration

External MCP (Model Context Protocol) tools are registered dynamically:

```python
class MCPManager:
    async def register_mcp_tools(self, agent_config):
        # Combine configured and custom MCPs
        all_mcps = agent_config.get('configured_mcps', [])
        all_mcps.extend(agent_config.get('custom_mcps', []))
        
        # Initialize MCP wrapper with Redis caching
        mcp_wrapper = MCPToolWrapper(mcp_configs=all_mcps)
        await mcp_wrapper.initialize_and_register_tools()
        
        # Register schemas in tool registry
        for method_name, schema in mcp_wrapper.get_schemas().items():
            self.thread_manager.tool_registry.tools[method_name] = {
                "instance": mcp_wrapper,
                "schema": schema
            }
```

### 2.4 Execution Loop

The main execution loop handles iterations with billing checks and auto-continue logic:

```python
async def run(self) -> AsyncGenerator[Dict[str, Any], None]:
    iteration_count = 0
    continue_execution = True
    
    while continue_execution and iteration_count < self.config.max_iterations:
        # 1. Check billing status
        can_run, message, subscription = await check_billing_status(...)
        if not can_run:
            yield {"type": "status", "status": "stopped", "message": error_msg}
            break
        
        # 2. Check for terminal conditions
        latest_message = await self.client.table('messages').select('*')...
        if latest_message.type == 'assistant':
            continue_execution = False
            break
        
        # 3. Run thread with LLM
        response = await self.thread_manager.run_thread(...)
        
        # 4. Process streaming response
        async for chunk in response:
            # Handle tool calls, content, and termination signals
            if agent_should_terminate or last_tool_call in ['ask', 'complete']:
                continue_execution = False
            yield chunk
```

---

## 3. AgentPress Framework Architecture

### 3.1 Core Components

**ThreadManager** (`agentpress/thread_manager.py`):
- Manages conversation threads and message persistence
- Orchestrates LLM interactions with streaming support
- Handles tool registration and execution context
- Implements auto-continue logic for tool chains

**ToolRegistry** (`agentpress/tool_registry.py`):
- Central registry for all available tools
- Manages OpenAPI schemas for function calling
- Provides tool discovery and access methods
- Supports selective function registration

**ResponseProcessor** (`agentpress/response_processor.py`):
- Processes LLM responses (streaming and non-streaming)
- Detects and parses tool calls (XML and native formats)
- Orchestrates tool execution (sequential/parallel)
- Manages result formatting and message persistence

**ContextManager** (`agentpress/context_manager.py`):
- Token counting and context window management
- Message compression strategies
- Middle-out compression for long conversations
- Tool result and message truncation

### 3.2 Message Flow

```
User Input → ThreadManager → LLM API Call → ResponseProcessor
                ↓                               ↓
           Add to Thread                  Parse Tool Calls
                                               ↓
                                         Execute Tools
                                               ↓
                                         Format Results
                                               ↓
                                         Add to Thread
                                               ↓
                                         Stream to Client
```

---

## 4. Tool System Architecture

### 4.1 Tool Base Class

All tools inherit from the base `Tool` class:

```python
class Tool(ABC):
    def __init__(self):
        self._schemas: Dict[str, List[ToolSchema]] = {}
        self._register_schemas()
    
    def get_schemas(self) -> Dict[str, List[ToolSchema]]:
        return self._schemas
    
    def success_response(self, data) -> ToolResult:
        return ToolResult(success=True, output=data)
    
    def fail_response(self, msg) -> ToolResult:
        return ToolResult(success=False, output=msg)
```

### 4.2 Tool Categories

**Core Tools** (Always Enabled):
- `MessageTool`: User interaction (ask, complete, web_browser_takeover)
- `TaskListTool`: Task management and tracking
- `ExpandMessageTool`: Expand truncated messages

**Sandbox Tools** (Configurable):
- `SandboxShellTool`: Terminal command execution
- `SandboxFilesTool`: File system operations
- `SandboxDeployTool`: Application deployment
- `SandboxExposeTool`: Port exposure for web services
- `SandboxVisionTool`: Image processing and analysis
- `SandboxWebSearchTool`: Internet search capabilities

**Social Media Tools** (Native Implementation):
- `YouTubeTool`: Complete YouTube integration
- `TwitterTool`: Twitter/X posting and management
- `InstagramTool`: Instagram content posting
- `PinterestTool`: Pinterest pin creation
- `LinkedInTool`: Professional networking posts

**Agent Builder Tools**:
- `AgentConfigTool`: Update agent configuration
- `MCPSearchTool`: Discover MCP integrations
- `CredentialProfileTool`: Manage credentials
- `WorkflowTool`: Create automation workflows
- `TriggerTool`: Set up scheduled/event triggers

### 4.3 Tool Registration Pattern

Tools use decorators for schema definition:

```python
class ExampleTool(Tool):
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "example_function",
            "description": "Tool description",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {"type": "string"},
                    "param2": {"type": "integer"}
                },
                "required": ["param1"]
            }
        }
    })
    @usage_example('''
        <function_calls>
        <invoke name="example_function">
        <parameter name="param1">value</parameter>
        </invoke>
        </function_calls>
    ''')
    async def example_function(self, param1: str, param2: int = 0):
        # Implementation
        return self.success_response({"result": "success"})
```

---

## 5. Thread Management & Conversation Handling

### 5.1 Thread Creation and Persistence

```python
class ThreadManager:
    async def create_thread(self, account_id, project_id, is_public, metadata):
        # Create thread in database
        result = await client.table('threads').insert({
            'account_id': account_id,
            'project_id': project_id,
            'is_public': is_public,
            'metadata': metadata or {}
        }).execute()
        return thread_id
    
    async def add_message(self, thread_id, type, content, is_llm_message, metadata):
        # Add message with agent version tracking
        data = {
            'thread_id': thread_id,
            'type': type,  # user, assistant, tool, status
            'content': content,
            'is_llm_message': is_llm_message,
            'metadata': metadata,
            'agent_id': agent_id,
            'agent_version_id': version_id
        }
        result = await client.table('messages').insert(data).execute()
```

### 5.2 Message Types

The system supports various message types:
- **user**: User input messages
- **assistant**: LLM responses
- **tool**: Tool execution results
- **status**: System status updates
- **browser_state**: Browser interaction state
- **image_context**: Image processing context

### 5.3 Streaming Architecture

The system implements sophisticated streaming for real-time updates:

```python
async def run_thread(self, ...):
    # Create auto-continue wrapper for tool chains
    async def auto_continue_wrapper():
        while auto_continue and auto_continue_count < max_continues:
            response_gen = await _run_once()
            
            async for chunk in response_gen:
                # Check for tool_calls finish reason
                if chunk.get('finish_reason') == 'tool_calls':
                    auto_continue = True
                    auto_continue_count += 1
                    continue  # Don't yield, continue execution
                
                yield chunk  # Stream to client
```

---

## 6. Agent Configuration & Versioning

### 6.1 Configuration Structure

Agent configurations are versioned with Git-like semantics:

```python
@dataclass
class AgentVersion:
    version_id: str
    agent_id: str
    version_number: int
    version_name: str
    system_prompt: str
    model: Optional[str]
    configured_mcps: List[Dict[str, Any]]
    custom_mcps: List[Dict[str, Any]]
    agentpress_tools: Dict[str, Any]
    workflows: List[Dict[str, Any]]
    triggers: List[Dict[str, Any]]
    is_active: bool
    created_at: datetime
    created_by: str
    change_description: Optional[str]
    previous_version_id: Optional[str]
```

### 6.2 Version Management

The `VersionService` provides comprehensive version control:

```python
class VersionService:
    async def create_version(self, agent_id, user_id, system_prompt, ...):
        # Create new version with auto-incrementing number
        version_number = await self._get_next_version_number(agent_id)
        
        # Link to previous version for history
        previous_version_id = current_agent.get('current_version_id')
        
        # Store configuration snapshot
        version = AgentVersion(
            version_id=str(uuid4()),
            version_number=version_number,
            previous_version_id=previous_version_id,
            ...
        )
        
        # Update agent's current version pointer
        await self._update_agent_current_version(agent_id, version.version_id)
```

### 6.3 Configuration Extraction

The system distinguishes between Suna (default) and custom agents:

```python
async def extract_agent_config(agent_data, version_data):
    is_suna_default = agent_data.get('metadata', {}).get('is_suna_default')
    
    if is_suna_default:
        # Use central Suna config with user customizations
        return await _extract_suna_agent_config(agent_data, version_data)
    else:
        # Use versioned custom agent config
        return _extract_custom_agent_config(agent_data, version_data)
```

---

## 7. Context Management & Compression

### 7.1 Token Management Strategy

The `ContextManager` implements multi-tier compression:

```python
class ContextManager:
    def compress_messages(self, messages, llm_model, max_tokens):
        # 1. Calculate model-specific limits
        context_window = get_model_context_window(llm_model)
        effective_limit = context_window - safety_margin
        
        # 2. Remove metadata from messages
        messages = self.remove_meta_messages(messages)
        
        # 3. Compress tool results (except most recent)
        messages = self.compress_tool_result_messages(messages, ...)
        
        # 4. Compress user messages (except most recent)
        messages = self.compress_user_messages(messages, ...)
        
        # 5. Compress assistant messages (except most recent)
        messages = self.compress_assistant_messages(messages, ...)
        
        # 6. If still over limit, use middle-out compression
        if token_count > max_tokens:
            messages = self.middle_out_messages(messages)
        
        return messages
```

### 7.2 Compression Strategies

**Message Truncation**: 
- Preserves message structure while reducing content
- Adds expansion hints for truncated messages
- Maintains JSON structure for tool results

**Middle-Out Compression**:
- Keeps beginning and end of conversation
- Removes messages from the middle
- Preserves context continuity

**Safe Truncation**:
- Removes middle portion of very long messages
- Preserves start and end for context
- Adds truncation markers

---

## 8. Response Processing & Tool Execution

### 8.1 Tool Call Detection

The `ResponseProcessor` supports multiple tool calling formats:

```python
class ResponseProcessor:
    async def process_streaming_response(self, llm_response, config):
        # XML Tool Detection
        if config.xml_tool_calling:
            xml_chunks = self._extract_xml_chunks(content)
            for xml_chunk in xml_chunks:
                tool_call = self._parse_xml_tool_call(xml_chunk)
                if tool_call:
                    await self._execute_tool(tool_call)
        
        # Native Tool Detection (OpenAI format)
        if config.native_tool_calling:
            if delta.tool_calls:
                for tool_call_chunk in delta.tool_calls:
                    # Buffer and execute when complete
                    if self._is_complete_tool_call(tool_call_chunk):
                        await self._execute_tool(tool_call_chunk)
```

### 8.2 Tool Execution Patterns

**Sequential Execution**:
```python
for tool_call in tool_calls:
    result = await self._execute_tool(tool_call)
    yield self._format_tool_result(result)
```

**Parallel Execution**:
```python
tasks = [self._execute_tool(tc) for tc in tool_calls]
results = await asyncio.gather(*tasks)
for result in results:
    yield self._format_tool_result(result)
```

### 8.3 Result Processing

Tool results are formatted and persisted:

```python
async def _yield_and_save_tool_completed(self, context, thread_id):
    # Format tool result
    content = {
        "tool_execution": {
            "function_name": context.function_name,
            "result": context.result.to_dict(),
            "execution_time": execution_time
        }
    }
    
    # Save to database
    msg_obj = await self.add_message(
        thread_id=thread_id,
        type="tool",
        content=content,
        is_llm_message=True
    )
    
    # Yield for streaming
    return format_for_yield(msg_obj)
```

---

## 9. Key Design Patterns

### 9.1 Pre-computed Data Pattern

Social media integrations use pre-computed data to avoid database queries during execution:

```python
# At agent load time
agent_config['youtube_channels'] = await fetch_youtube_channels()
agent_config['twitter_accounts'] = await fetch_twitter_accounts()

# During execution - no DB queries needed
tool_manager = ToolManager(agent_config=agent_config)
youtube_channels = agent_config.get('youtube_channels', [])
```

### 9.2 Zero-Questions Protocol

Social media tools implement immediate action without user interaction:

```python
class YouTubeTool:
    async def youtube_authenticate(self):
        # Never ask which account - OAuth handles selection
        return self.success_response({
            "auth_url": oauth_url,
            "message": "Click to connect YouTube"
        })
    
    async def youtube_upload_video(self, video_ref):
        # Auto-generate all metadata
        title = self._generate_seo_title(video_content)
        description = self._generate_description(video_content)
        tags = self._generate_tags(video_content)
        
        # Upload with defaults (public, auto-thumbnail)
        return await self._upload(video_ref, title, description, tags)
```

### 9.3 Tool Registry Pattern

Dynamic tool registration with schema management:

```python
class ToolRegistry:
    def register_tool(self, tool_class, function_names=None):
        tool_instance = tool_class(**kwargs)
        schemas = tool_instance.get_schemas()
        
        for func_name, schema_list in schemas.items():
            if function_names is None or func_name in function_names:
                for schema in schema_list:
                    if schema.schema_type == SchemaType.OPENAPI:
                        self.tools[func_name] = {
                            "instance": tool_instance,
                            "schema": schema
                        }
```

### 9.4 Continuous State Management

Auto-continue maintains state across iterations:

```python
continuous_state = {
    'accumulated_content': '',  # Maintains assistant response
    'thread_run_id': None,      # Consistent run ID
    'sequence': 0               # Message sequencing
}

# State persists across auto-continue cycles
while auto_continue:
    response = await run_once(continuous_state)
    continuous_state['accumulated_content'] += response.content
```

---

## 10. Integration Points

### 10.1 LLM Providers

The system uses LiteLLM for multi-provider support:
- OpenAI (GPT-4, GPT-5)
- Anthropic (Claude Sonnet, Opus)
- Google (Gemini)
- OpenRouter (fallback and alternative models)

### 10.2 External Services

**MCP Servers**:
- Standard MCP servers (Gmail, Slack, GitHub)
- Composio integration (2700+ tools)
- Pipedream workflows
- Custom SSE/stdio servers

**Social Media APIs**:
- YouTube Data API v3
- Twitter API v2
- Instagram Graph API
- Pinterest API
- LinkedIn API

### 10.3 Database Schema

Key tables:
- `agents`: Agent definitions
- `agent_versions`: Configuration versions
- `threads`: Conversation threads
- `messages`: Thread messages
- `agent_workflows`: Automation workflows
- `agent_triggers`: Scheduled/event triggers
- `mcp_toggles`: Per-agent MCP control
- `credential_profiles`: Encrypted credentials

### 10.4 Caching Strategy

Redis caching for performance:
- MCP schemas (1 hour TTL)
- User configurations
- Session data
- Token counts

---

## Conclusion

The Kortix agent system represents a sophisticated implementation of autonomous AI agents with:

1. **Robust Execution Model**: Multi-stage initialization, dynamic tool registration, and intelligent execution loops
2. **Flexible Tool System**: Extensible architecture supporting native tools, social media integrations, and external MCP servers
3. **Advanced Conversation Management**: Streaming support, context compression, and message persistence
4. **Version Control**: Git-like versioning for agent configurations with rollback capabilities
5. **Performance Optimization**: Pre-computed data, Redis caching, and efficient token management
6. **User Experience Focus**: Zero-questions protocol, automatic metadata generation, and real-time streaming

The AgentPress framework provides a solid foundation for building sophisticated AI agents that can handle complex, multi-step tasks while maintaining conversation context and managing external integrations seamlessly.