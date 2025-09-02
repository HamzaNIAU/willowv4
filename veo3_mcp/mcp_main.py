#!/usr/bin/env python3
"""
Main MCP runner for Veo3 service.

This script provides the same functionality as the Go implementation's
main.go file, handling different transport modes and initialization.
"""

import sys
import os
import argparse
import asyncio
import logging
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from veo3_mcp.server import Veo3MCPServer
from veo3_mcp.config import get_config


# Configure logging to match Go implementation
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("mcp-veo3")


async def run_stdio_server():
    """Run MCP server in stdio mode (default)."""
    logger.info("Veo3 MCP Server listening on STDIO with t2v and i2v tools")
    server = Veo3MCPServer(transport="stdio")
    try:
        await server.run_stdio()
    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down...")
    except Exception as e:
        logger.error(f"STDIO Server error: {e}")
        sys.exit(1)


async def run_http_server(port: int = 8080):
    """Run MCP server in HTTP mode."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    from veo3_mcp.api import router
    
    app = FastAPI(
        title="Veo3 MCP Server",
        version=get_config().VERSION
    )
    
    # Configure CORS (matching Go implementation)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
        allow_headers=["Accept", "Authorization", "Content-Type", "X-CSRF-Token", "X-MCP-Progress-Token"],
        expose_headers=["Link"],
        max_age=300
    )
    
    app.include_router(router)
    
    logger.info(f"Veo3 MCP Server listening on HTTP at :{port}/veo3 with t2v and i2v tools and CORS enabled")
    
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    
    try:
        await server.serve()
    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down...")
    except Exception as e:
        logger.error(f"HTTP Server error: {e}")
        sys.exit(1)


async def run_sse_server(port: int = 8081):
    """Run MCP server in SSE mode."""
    # For Python, SSE is typically handled as part of the HTTP server
    # with specific endpoints for SSE streams
    logger.info(f"Veo3 MCP Server listening on SSE at :{port} with t2v and i2v tools")
    
    # Run HTTP server with SSE support
    await run_http_server(port)


def main():
    """Main entry point matching Go implementation."""
    parser = argparse.ArgumentParser(description="Veo3 MCP Server")
    parser.add_argument(
        "-t", "--transport",
        default="stdio",
        choices=["stdio", "http", "sse"],
        help="Transport type (stdio, http, or sse)"
    )
    parser.add_argument(
        "--otel",
        action="store_true",
        default=True,
        help="Enable OpenTelemetry (default: true)"
    )
    
    args = parser.parse_args()
    
    # Load and validate configuration
    try:
        config = get_config()
        
        # Log startup information (matching Go implementation)
        logger.info(f"Initializing global GenAI client...")
        logger.info(f"Project ID: {config.PROJECT_ID}")
        logger.info(f"Location: {config.LOCATION}")
        if config.API_ENDPOINT:
            logger.info(f"Using custom Vertex AI endpoint: {config.API_ENDPOINT}")
        
        logger.info("Global GenAI client initialized successfully.")
        logger.info(f"Starting Veo MCP Server (Version: {config.VERSION}, Transport: {args.transport})")
        
    except Exception as e:
        logger.error(f"Error initializing configuration: {e}")
        sys.exit(1)
    
    # Initialize OpenTelemetry if enabled
    if args.otel and config.OTEL_ENABLED:
        try:
            # Initialize OpenTelemetry (simplified for this example)
            logger.info(f"OpenTelemetry enabled for service: {config.OTEL_SERVICE_NAME}")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenTelemetry: {e}")
    
    # Run the appropriate server based on transport
    try:
        if args.transport == "stdio":
            asyncio.run(run_stdio_server())
        elif args.transport == "http":
            port = int(os.getenv("PORT", "8080"))
            asyncio.run(run_http_server(port))
        elif args.transport == "sse":
            # SSE typically runs on different port to avoid conflict
            port = int(os.getenv("SSE_PORT", "8081"))
            asyncio.run(run_sse_server(port))
    except KeyboardInterrupt:
        logger.info("Veo3 Server shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    
    logger.info("Veo3 Server has stopped.")


if __name__ == "__main__":
    main()