# Veo3 MCP Python Implementation Notes

## Overview
This is a complete Python implementation of the Veo3 MCP service, matching the Go implementation from `/experiments/mcp-genmedia/mcp-genmedia-go/mcp-veo-go/`.

## File Mapping

### Go Implementation → Python Implementation

| Go File | Python File | Purpose |
|---------|-------------|---------|
| `veo.go` | `mcp_main.py`, `mcp_server.py` | Main entry point and server initialization |
| `handlers.go` | `handlers.py` | Request handlers for veo_t2v and veo_i2v tools |
| `video_logic.go` | `veo3_service.py` | Core video generation logic |
| `utils.go` | `utils.py` | Utility functions |
| `../mcp-common/config.go` | `config.py` | Configuration management |
| `../mcp-common/models.go` | `models.py`, `config.py` | Model definitions |
| `../mcp-common/otel.go` | `otel.py` | OpenTelemetry instrumentation |
| `../mcp-common/gcs_utils.go` | `utils.py` | GCS operations |
| `../mcp-common/file_utils.go` | `utils.py` | File handling utilities |

### Additional Python Files

| Python File | Purpose |
|-------------|---------|
| `api.py` | FastAPI REST endpoints (YouTube MCP pattern) |
| `auth.py` | JWT authentication (YouTube MCP pattern) |
| `server.py` | MCP protocol server implementation |
| `prompts.py` | MCP prompts and templates |
| `verify.py` | Verification and testing script |
| `build.sh` | Build and packaging script |
| `run.sh` | Service runner script |
| `requirements.txt` | Python dependencies |
| `__init__.py` | Module initialization |

## Key Features Implemented

### 1. MCP Tools
- **veo_t2v**: Text-to-video generation (matches Go)
- **veo_i2v**: Image-to-video generation (matches Go)

### 2. Model Support
- Veo 2.0 (veo-2.0-generate-001)
- Veo 3.0 Preview (veo-3.0-generate-preview)
- Veo 3.0 Fast Preview (veo-3.0-fast-generate-preview)

### 3. Configuration
- Environment variables (PROJECT_ID, LOCATION, GENMEDIA_BUCKET, VERTEX_API_ENDPOINT)
- Model configurations with duration, aspect ratio, and video count limits
- JWT authentication settings

### 4. Transport Modes
- STDIO (default, matches Go)
- HTTP with CORS (matches Go)
- SSE (Server-Sent Events)

### 5. Observability
- OpenTelemetry tracing
- Metrics collection
- Structured logging

### 6. GCS Integration
- Upload to GCS buckets
- Download from GCS
- GENMEDIA_BUCKET with /veo_outputs suffix (matches Go)

### 7. Progress Tracking
- Long-running operation polling
- Progress notifications via MCP protocol
- Timeout handling (5 minutes default)

## API Compatibility

### MCP Protocol
The implementation follows the MCP (Model Context Protocol) specification:
- Tools discovery
- Prompts discovery
- Progress notifications
- Error handling

### Request/Response Format
Matches the Go implementation's request and response structures:
- Tool parameters (prompt, model, duration, aspect_ratio, etc.)
- Response format with GCS URIs and local paths
- Error responses with isError flag

## Environment Variables

Required:
- `PROJECT_ID`: Google Cloud project ID
- `JWT_SECRET_KEY`: Secret key for JWT authentication

Optional:
- `LOCATION`: Vertex AI location (default: us-central1)
- `GENMEDIA_BUCKET`: Default GCS bucket for outputs
- `VERTEX_API_ENDPOINT`: Custom Vertex AI endpoint
- `PORT`: HTTP server port (default: 8080)
- `OTEL_ENABLED`: Enable OpenTelemetry (default: true)
- `OTEL_EXPORTER_ENDPOINT`: OpenTelemetry exporter endpoint

## Running the Service

### STDIO Mode (default)
```bash
python mcp_main.py
# or
./run.sh
```

### HTTP Mode
```bash
python mcp_main.py --transport http
# or
./run.sh --transport http --port 8080
```

### SSE Mode
```bash
python mcp_main.py --transport sse
# or
./run.sh --transport sse --port 8081
```

## Verification

Run the verification script to test the implementation:
```bash
python verify.py
```

This will check:
- Configuration loading
- Model definitions
- MCP tool registration
- Request validation
- GCS integration
- OpenTelemetry setup

## Building and Distribution

Build the package:
```bash
./build.sh
```

This will:
- Run linting (black, ruff, mypy)
- Run tests (if available)
- Create wheel and source distributions
- Package for deployment

## Differences from Go Implementation

### Enhancements (YouTube MCP Pattern)
1. **JWT Authentication**: Added JWT-based authentication system
2. **REST API**: FastAPI endpoints for HTTP access
3. **Database Integration**: SQLAlchemy for MCP toggles
4. **Agent Integration**: Support for agent tool discovery

### Python-Specific Adaptations
1. **Async/Await**: Uses Python's asyncio for asynchronous operations
2. **Pydantic Models**: Type-safe request/response models
3. **FastAPI**: Modern web framework for HTTP transport
4. **Type Hints**: Full type annotations throughout

### Maintained Compatibility
1. **Tool Names**: veo_t2v and veo_i2v (exact match)
2. **Model Names**: Exact model IDs and aliases
3. **Parameters**: All parameters and defaults match
4. **Behavior**: Polling, timeouts, and error handling match

## Testing

The implementation has been designed to be testable with:
- Unit tests for individual components
- Integration tests for service operations
- Verification script for deployment validation

## Future Enhancements

Potential improvements while maintaining compatibility:
1. Add caching for frequently requested videos
2. Implement request queuing for rate limiting
3. Add metrics dashboard integration
4. Support for batch operations
5. WebSocket support for real-time updates