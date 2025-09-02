"""
MCP server integration module.

This module provides functions to create and run the MCP server
with different transport modes, matching the Go implementation structure.
"""

import os
import sys
import json
import asyncio
import logging
from typing import Optional, Dict, Any, List

from .server import Veo3MCPServer
from .config import get_config
from .handlers import veo_text_to_video_handler, veo_image_to_video_handler
from .veo3_service import Veo3Service

logger = logging.getLogger(__name__)


def create_mcp_server() -> Dict[str, Any]:
    """
    Create an MCP server instance with registered tools and prompts.
    
    Returns:
        Dictionary containing server configuration
    """
    config = get_config()
    service = Veo3Service(config)
    
    # Define tools matching Go implementation
    tools = [
        {
            "name": "veo_t2v",
            "description": "Generate a video from a text prompt using Veo. Video is saved to GCS and optionally downloaded locally.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Text prompt for video generation"
                    },
                    "bucket": {
                        "type": "string",
                        "description": "Google Cloud Storage bucket where the API will save the generated video(s)"
                    },
                    "output_directory": {
                        "type": "string",
                        "description": "Optional. If provided, specifies a local directory to download the generated video(s) to"
                    },
                    "model": {
                        "type": "string",
                        "default": "veo-2.0-generate-001",
                        "description": "Model for video generation"
                    },
                    "num_videos": {
                        "type": "number",
                        "default": 1,
                        "description": "Number of videos to generate"
                    },
                    "aspect_ratio": {
                        "type": "string",
                        "default": "16:9",
                        "description": "Aspect ratio of the generated videos"
                    },
                    "duration": {
                        "type": "number",
                        "default": 5,
                        "description": "Duration of the generated video in seconds"
                    }
                },
                "required": ["prompt"]
            }
        },
        {
            "name": "veo_i2v",
            "description": "Generate a video from an input image (and optional prompt) using Veo. Video is saved to GCS and optionally downloaded locally. Supported image MIME types: image/jpeg, image/png.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "image_uri": {
                        "type": "string",
                        "description": "GCS URI of the input image for video generation"
                    },
                    "mime_type": {
                        "type": "string",
                        "description": "MIME type of the input image"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Optional text prompt to guide video generation from the image"
                    },
                    "bucket": {
                        "type": "string",
                        "description": "Google Cloud Storage bucket where the API will save the generated video(s)"
                    },
                    "output_directory": {
                        "type": "string",
                        "description": "Optional. If provided, specifies a local directory to download the generated video(s) to"
                    },
                    "model": {
                        "type": "string",
                        "default": "veo-2.0-generate-001",
                        "description": "Model for video generation"
                    },
                    "num_videos": {
                        "type": "number",
                        "default": 1,
                        "description": "Number of videos to generate"
                    },
                    "aspect_ratio": {
                        "type": "string",
                        "default": "16:9",
                        "description": "Aspect ratio of the generated videos"
                    },
                    "duration": {
                        "type": "number",
                        "default": 5,
                        "description": "Duration of the generated video in seconds"
                    }
                },
                "required": ["image_uri"]
            }
        }
    ]
    
    # Define prompts matching Go implementation
    prompts = [
        {
            "name": "generate-video",
            "description": "Generates a video from a text prompt.",
            "arguments": [
                {
                    "name": "prompt",
                    "description": "The text prompt to generate a video from",
                    "required": True
                },
                {
                    "name": "duration",
                    "description": "The duration of the video in seconds",
                    "required": False
                },
                {
                    "name": "aspect_ratio",
                    "description": "The aspect ratio of the generated video",
                    "required": False
                },
                {
                    "name": "model",
                    "description": "The model to use for generation",
                    "required": False
                }
            ]
        }
    ]
    
    return {
        "name": "Veo",
        "version": config.VERSION,
        "tools": tools,
        "prompts": prompts,
        "service": service
    }


def list_tools() -> List[Dict[str, Any]]:
    """
    List all available MCP tools.
    
    Returns:
        List of tool definitions
    """
    server_config = create_mcp_server()
    return server_config["tools"]


def list_prompts() -> List[Dict[str, Any]]:
    """
    List all available MCP prompts.
    
    Returns:
        List of prompt definitions
    """
    server_config = create_mcp_server()
    return server_config["prompts"]


async def run_mcp_server(transport: str = "stdio", port: int = 8080):
    """
    Run the MCP server with the specified transport.
    
    Args:
        transport: Transport type (stdio, http, sse)
        port: Port for HTTP/SSE transport
    """
    config = get_config()
    
    logger.info(f"Starting Veo MCP Server (Version: {config.VERSION}, Transport: {transport})")
    
    if transport == "stdio":
        server = Veo3MCPServer(transport="stdio")
        logger.info("Veo MCP Server listening on STDIO with t2v and i2v tools")
        await server.run_stdio()
    
    elif transport == "http":
        # Import FastAPI components
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        import uvicorn
        
        app = FastAPI(
            title="Veo MCP Server",
            version=config.VERSION
        )
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["Link"],
            max_age=300
        )
        
        # Add MCP endpoints
        server = Veo3MCPServer(transport="http")
        
        @app.post("/mcp")
        async def mcp_endpoint(request: Dict[str, Any]):
            """MCP HTTP endpoint."""
            return await server.handle_request(request)
        
        @app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "service": "veo3-mcp", "version": config.VERSION}
        
        # Run server
        logger.info(f"Veo MCP Server listening on HTTP at :{port}/mcp with t2v and i2v tools and CORS enabled")
        
        uvconfig = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=port,
            log_level="info"
        )
        uvserver = uvicorn.Server(uvconfig)
        await uvserver.serve()
    
    elif transport == "sse":
        # SSE implementation
        logger.info(f"Veo MCP Server listening on SSE at :{port} with t2v and i2v tools")
        # SSE would be implemented as part of HTTP with SSE endpoints
        await run_mcp_server("http", port)
    
    else:
        raise ValueError(f"Unsupported transport type: {transport}")
    
    logger.info("Veo Server has stopped.")


# Convenience functions for the server
class MCPServer:
    """MCP Server wrapper for compatibility."""
    
    def __init__(self):
        """Initialize MCP server."""
        self.config = create_mcp_server()
        self.service = self.config["service"]
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        return self.config["tools"]
    
    def list_prompts(self) -> List[Dict[str, Any]]:
        """List available prompts."""
        return self.config["prompts"]
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Call a tool by name.
        
        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            context: Request context with meta info
        
        Returns:
            Tool result
        """
        # Extract progress callback if context has progress token
        progress_callback = None
        if context and "meta" in context and "progressToken" in context["meta"]:
            progress_token = context["meta"]["progressToken"]
            # Create a callback that sends progress notifications
            progress_callback = lambda update: self._send_progress_notification(progress_token, update)
        
        if tool_name == "veo_t2v":
            return await veo_text_to_video_handler(self.service, arguments, progress_callback, context)
        elif tool_name == "veo_i2v":
            return await veo_image_to_video_handler(self.service, arguments, progress_callback, context)
        else:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}]
            }
    
    def _send_progress_notification(self, progress_token: str, update: Any):
        """Send progress notification (placeholder for actual implementation)."""
        # This would integrate with the actual MCP server's notification system
        pass