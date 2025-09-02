#!/bin/bash

# Veo3 MCP Run Script
# This script runs the Veo3 MCP service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
TRANSPORT="${TRANSPORT:-stdio}"
PORT="${PORT:-8080}"
OTEL_ENABLED="${OTEL_ENABLED:-true}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================"
echo "Veo3 MCP Service Runner"
echo "================================================"

# Check for required environment variables
check_env_var() {
    if [ -z "${!1}" ]; then
        echo -e "${RED}Error: $1 is not set${NC}"
        echo "Please set $1 environment variable"
        return 1
    fi
    echo -e "${GREEN}✓${NC} $1 is set"
    return 0
}

echo "Checking environment variables..."
check_env_var "PROJECT_ID" || exit 1
check_env_var "JWT_SECRET_KEY" || exit 1

# Optional environment variables
if [ -z "$GENMEDIA_BUCKET" ]; then
    echo -e "${YELLOW}Warning: GENMEDIA_BUCKET is not set${NC}"
    echo "  Video generation will require explicit bucket parameter"
fi

if [ -z "$VERTEX_API_ENDPOINT" ]; then
    echo "Using default Vertex AI endpoint"
else
    echo "Using custom Vertex AI endpoint: $VERTEX_API_ENDPOINT"
fi

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--transport)
            TRANSPORT="$2"
            shift 2
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        --no-otel)
            OTEL_ENABLED="false"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -t, --transport <type>  Transport type: stdio, http, sse (default: stdio)"
            echo "  -p, --port <port>       Port for HTTP/SSE transport (default: 8080)"
            echo "  --no-otel              Disable OpenTelemetry"
            echo "  -h, --help             Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run '$0 --help' for usage information"
            exit 1
            ;;
    esac
done

# Export configuration
export TRANSPORT="$TRANSPORT"
export PORT="$PORT"
export OTEL_ENABLED="$OTEL_ENABLED"

echo ""
echo "Configuration:"
echo "  Transport: $TRANSPORT"
if [ "$TRANSPORT" != "stdio" ]; then
    echo "  Port: $PORT"
fi
echo "  OpenTelemetry: $OTEL_ENABLED"
echo "  Project ID: $PROJECT_ID"
echo "  Location: ${LOCATION:-us-central1}"
echo ""

# Activate virtual environment if it exists
if [ -d "$SCRIPT_DIR/venv" ]; then
    echo "Activating virtual environment..."
    source "$SCRIPT_DIR/venv/bin/activate"
elif [ -d "$PROJECT_ROOT/venv" ]; then
    echo "Activating project virtual environment..."
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# Check if main.py exists
if [ ! -f "$SCRIPT_DIR/main.py" ]; then
    echo -e "${RED}Error: main.py not found${NC}"
    echo "Creating main.py..."
    
    cat > "$SCRIPT_DIR/main.py" << 'EOF'
#!/usr/bin/env python3
"""
Main entry point for Veo3 MCP service.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from veo3_mcp.mcp_server import run_mcp_server
from veo3_mcp.api import create_app, run_api_server
from veo3_mcp.config import get_config
from veo3_mcp.otel import init_telemetry, shutdown_telemetry

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point."""
    transport = os.getenv("TRANSPORT", "stdio")
    port = int(os.getenv("PORT", "8080"))
    
    # Initialize configuration
    config = get_config()
    
    # Initialize telemetry
    telemetry = init_telemetry(
        service_name="veo3-mcp",
        service_version="1.0.0",
        enabled=config.OTEL_ENABLED
    )
    
    try:
        if transport == "http":
            # Run as HTTP API server
            logger.info(f"Starting Veo3 MCP HTTP server on port {port}")
            app = create_app()
            await run_api_server(app, port=port)
        else:
            # Run as MCP server (stdio or sse)
            logger.info(f"Starting Veo3 MCP server with transport: {transport}")
            await run_mcp_server(transport=transport, port=port)
    finally:
        shutdown_telemetry()


if __name__ == "__main__":
    asyncio.run(main())
EOF
fi

# Run the service
echo "Starting Veo3 MCP service..."
echo "================================================"
echo ""

if [ "$TRANSPORT" == "stdio" ]; then
    echo "Running in STDIO mode. Ready to receive MCP messages..."
    echo "Press Ctrl+C to stop"
    python3 "$SCRIPT_DIR/main.py"
elif [ "$TRANSPORT" == "http" ]; then
    echo "Running in HTTP mode on port $PORT"
    echo "API will be available at: http://localhost:$PORT"
    echo "MCP endpoint: http://localhost:$PORT/mcp"
    echo "Press Ctrl+C to stop"
    python3 "$SCRIPT_DIR/main.py"
elif [ "$TRANSPORT" == "sse" ]; then
    echo "Running in SSE mode on port $PORT"
    echo "SSE endpoint: http://localhost:$PORT/sse"
    echo "Press Ctrl+C to stop"
    python3 "$SCRIPT_DIR/main.py"
else
    echo -e "${RED}Error: Unknown transport type: $TRANSPORT${NC}"
    echo "Valid options are: stdio, http, sse"
    exit 1
fi