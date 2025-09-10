# Kortix Tool System Architecture - Comprehensive Analysis

## Executive Summary

The Kortix platform implements a sophisticated multi-layered tool system that seamlessly integrates native AgentPress tools with external MCP (Model Context Protocol) integrations. The architecture supports dynamic tool registration, parallel execution, rich result formatting, and intelligent caching for optimal performance.

## Core Architecture Components

### 1. Base Tool Framework (`backend/agentpress/tool.py`)

The foundation of the tool system is the abstract `Tool` base class that provides:

- **Schema Management**: Decorators for OpenAPI and usage example schemas
- **Result Standardization**: `ToolResult` dataclass for consistent output formatting
- **Response Helpers**: `success_response()` and `fail_response()` methods
- **Schema Registration**: Automatic discovery and registration of decorated methods

```python
class Tool(ABC):
    - _schemas: Dict[str, List[ToolSchema]]  # Schema registry
    - get_schemas() → Dict[str, List[ToolSchema]]
    - success_response(data) → ToolResult
    - fail_response(msg) → ToolResult
```

**Key Design Patterns:**
- Decorator-based schema definition (`@openapi_schema`, `@usage_example`)
- Automatic schema discovery via introspection
- Standardized result containers for error handling

### 2. Tool Registry System (`backend/agentpress/tool_registry.py`)

Centralized registry managing tool instances and schemas:

- **Selective Registration**: Can register specific functions from a tool class
- **Schema Collection**: Aggregates OpenAPI schemas for LLM function calling
- **Function Resolution**: Maps function names to executable methods

```python
class ToolRegistry:
    - tools: Dict[str, Dict[str, Any]]  # Tool instances and schemas
    - register_tool(tool_class, function_names=None)
    - get_available_functions() → Dict[str, Callable]
    - get_openapi_schemas() → List[Dict[str, Any]]
```

### 3. Tool Categories and Registration Order

Tools are registered in a specific order to ensure proper dependency resolution:

1. **Core Tools** (Always Enabled):
   - `MessageTool`: User interaction and questions
   - `TaskListTool`: Workflow tracking and management
   - `ExpandMessageTool`: Context expansion

2. **Sandbox Tools** (Configurable):
   - `SandboxShellTool`: Terminal execution
   - `SandboxFilesTool`: File management
   - `SandboxDeployTool`: Application deployment
   - `SandboxExposeTool`: Service exposure
   - `SandboxVisionTool`: Image processing
   - `SandboxWebSearchTool`: Internet search
   - Browser automation tools

3. **Utility Tools** (Configurable):
   - `DataProvidersTool`: External APIs (Zillow, Yahoo Finance)
   - Social Media Tools (YouTube, Twitter, Instagram, Pinterest, LinkedIn)
   - Web development and presentation tools

4. **Agent Builder Tools** (Context-Dependent):
   - `AgentConfigTool`: Agent configuration management
   - `WorkflowTool`: Workflow creation and management
   - `TriggerTool`: Scheduled and event triggers
   - `MCPSearchTool`: MCP discovery
   - `CredentialProfileTool`: Credential management

5. **MCP Tools** (Dynamic):
   - Standard MCP servers
   - Composio integrations (2700+ tools)
   - Pipedream workflows
   - Custom HTTP/SSE/JSON MCPs

### 4. MCP Tool Wrapper (`backend/agent/tools/mcp_tool_wrapper.py`)

Sophisticated wrapper for external MCP integrations:

**Key Features:**
- **Redis Caching**: 1-hour TTL for MCP schemas to reduce initialization time
- **Parallel Initialization**: Concurrent MCP server connections
- **Dynamic Method Generation**: Creates tool methods at runtime
- **Multiple MCP Types**: Supports standard, Composio, Pipedream, HTTP, SSE, JSON

```python
class MCPToolWrapper(Tool):
    - Redis cache for schemas (1hr TTL)
    - Parallel server initialization
    - Dynamic tool method creation
    - Custom MCP handler for non-standard integrations
```

**Caching Strategy:**
- Cache key: MD5 hash of MCP configuration
- Stores tool schemas and metadata
- Instant startup for cached MCPs
- Automatic cache invalidation after 1 hour

### 5. Dynamic Tool Building (`backend/agent/tools/utils/dynamic_tool_builder.py`)

Converts MCP tool definitions to executable methods:

- **Name Parsing**: Extracts server name and clean tool name
- **Schema Generation**: Creates OpenAPI schemas dynamically
- **Method Creation**: Generates async methods with proper signatures
- **Metadata Preservation**: Maintains original tool information

```python
class DynamicToolBuilder:
    - create_dynamic_methods(tools_info, custom_tools, execute_callback)
    - _parse_tool_name(tool_name) → (method_name, clean_name, server_name)
    - _create_tool_schema(method_name, description, tool_info)
```

### 6. Tool Execution Pipeline

#### 6.1 Tool Discovery and Parsing

The system supports two XML formats for tool invocation:

**New Format (Preferred):**
```xml
<function_calls>
<invoke name="tool_name">
<parameter name="param1">value1</parameter>
<parameter name="param2">value2</parameter>
</invoke>
</function_calls>
```

**OpenAI Format:**
```json
{
  "tool_calls": [{
    "id": "call_123",
    "type": "function",
    "function": {
      "name": "tool_name",
      "arguments": "{\"param1\": \"value1\"}"
    }
  }]
}
```

#### 6.2 Execution Flow (`backend/agentpress/response_processor.py`)

1. **Parse Tool Calls**: Extract from LLM response (XML or JSON)
2. **Create Execution Context**: Tool metadata and parsing details
3. **Execute Tools**: Sequential or parallel execution strategies
4. **Format Results**: Structure for both LLM and frontend
5. **Save Messages**: Persist tool results with metadata

```python
async def _execute_tools(tool_calls, execution_strategy="sequential"):
    if execution_strategy == "parallel":
        # Execute all tools simultaneously with asyncio.gather
        tasks = [_execute_tool(tc) for tc in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    else:
        # Execute sequentially for dependent operations
        for tool_call in tool_calls:
            result = await _execute_tool(tool_call)
            if tool_name in ['ask', 'complete']:
                break  # Terminating tools
```

#### 6.3 Result Processing

Tool results are formatted differently for LLM context and frontend display:

**LLM Format (Concise):**
```json
{
  "tool_execution": {
    "function_name": "edit_file",
    "result": {
      "success": true,
      "output": "File updated successfully"
    }
  }
}
```

**Frontend Format (Rich):**
```json
{
  "tool_execution": {
    "function_name": "edit_file",
    "arguments": {...},
    "result": {
      "success": true,
      "output": {
        "original_content": "...",
        "updated_content": "...",
        "diff": "..."
      }
    }
  }
}
```

### 7. Native Social Media Tools Pattern

Social media tools (YouTube, Twitter, Instagram, etc.) follow a consistent pattern:

1. **Zero-Questions Protocol**: Never ask users about account preferences
2. **OAuth-First**: All authentication via OAuth popups
3. **Reference ID System**: 32-character hex IDs for file management
4. **Real-Time Permissions**: Direct database queries for enabled accounts
5. **Fallback Chains**: Multiple fallback strategies for account discovery

Example from `YouTubeTool`:
```python
async def _check_enabled_channels():
    # 1. Real-time database query (no cache)
    # 2. Check agent_social_accounts table
    # 3. Fallback to youtube_channels table
    # 4. Return OAuth initiation if no accounts
```

### 8. MCP Tool Execution (`backend/agent/tools/utils/mcp_tool_executor.py`)

Handles execution of different MCP types:

**Standard MCPs:**
- Direct execution via MCP manager
- Error handling and result formatting

**Composio MCPs:**
- Profile resolution for credentials
- Dynamic URL generation
- 2700+ integrated tools

**Pipedream Workflows:**
- External user ID resolution
- Rate limiting headers
- Custom authentication

**HTTP/SSE/JSON MCPs:**
- Protocol-specific clients
- Timeout management (30s default)
- Content extraction from various formats

### 9. Tool Configuration Management

Tools are configured at multiple levels:

**Agent Level:**
```json
{
  "agentpress_tools": {
    "sb_shell_tool": true,
    "web_search_tool": false
  }
}
```

**MCP Toggle System:**
- Per-agent, per-user control
- Auto-enable for connected accounts
- Security defaults (social media disabled by default)

**Pre-computed Channels:**
- YouTube channels stored in agent config
- Avoids runtime database queries
- Fallback to real-time queries if needed

### 10. Performance Optimizations

**Caching Strategies:**
- Redis cache for MCP schemas (1hr TTL)
- Pre-computed social media accounts in agent config
- Connection pooling for database and HTTP

**Parallel Execution:**
- MCP server initialization in parallel
- Tool execution parallelization for independent operations
- Asyncio.gather with exception handling

**Lazy Loading:**
- Sandboxes created only when needed
- MCP connections established on first use
- Dynamic tool methods created on demand

## Tool Lifecycle

### 1. Registration Phase
```
AgentRunner.setup_tools()
  → ToolManager.register_all_tools()
    → Register core tools (always)
    → Register sandbox tools (if enabled)
    → Register utility tools (if enabled)
    → Register agent builder tools (if agent_id)
    → Register MCP tools (dynamic)
```

### 2. Execution Phase
```
LLM Response with tool calls
  → ResponseProcessor._parse_xml_tool_calls()
    → Create ToolExecutionContext
    → Save "tool_started" status
    → Execute tool (sequential/parallel)
    → Format result for LLM and frontend
    → Save "tool_completed" status
    → Add result to context
```

### 3. Result Phase
```
Tool execution result
  → Format for LLM (concise)
  → Format for frontend (rich)
  → Save to messages table
  → Update thread context
  → Check for terminating tools
```

## Security Considerations

1. **JWT Authentication**: All API calls use signed JWT tokens
2. **Row-Level Security**: Database enforces user access controls
3. **Encrypted Credentials**: Fernet encryption for MCP credentials
4. **Sandbox Isolation**: Each project has isolated sandbox environment
5. **Rate Limiting**: Progressive backoff for failed operations

## Error Handling Patterns

1. **Tool Not Found**: Graceful fallback with error message
2. **Execution Failures**: Structured error results
3. **Timeout Management**: 30-second default for external tools
4. **Network Failures**: Progressive backoff (1s, 5s, 15s)
5. **Authentication Errors**: Auto-refresh with 3 retries

## Best Practices

1. **Tool Development**:
   - Inherit from `Tool` base class
   - Use decorators for schema definition
   - Return `ToolResult` objects
   - Include comprehensive error messages

2. **MCP Integration**:
   - Leverage Redis caching for schemas
   - Initialize servers in parallel
   - Handle multiple MCP types gracefully
   - Implement proper timeout management

3. **Social Media Tools**:
   - Never ask users questions
   - Use OAuth for all authentication
   - Implement reference ID system
   - Query permissions in real-time

4. **Performance**:
   - Cache expensive operations
   - Use parallel execution when possible
   - Implement lazy loading
   - Pool database connections

## Future Enhancements

1. **Tool Versioning**: Git-like versioning for tool configurations
2. **Tool Marketplace**: Community-contributed tool packages
3. **Tool Analytics**: Usage metrics and performance monitoring
4. **Tool Composition**: Combine multiple tools into workflows
5. **Tool Testing**: Automated testing framework for tools

## Conclusion

The Kortix tool system provides a robust, extensible foundation for agent capabilities. Through careful layering of native tools, MCP integrations, and dynamic registration, the system achieves both flexibility and performance. The architecture supports everything from simple file operations to complex multi-step workflows involving external services, all while maintaining consistency, security, and excellent developer experience.