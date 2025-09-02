"""
Veo3 MCP (Model Context Protocol) Module

A Python implementation of the Veo3 video generation service following
the MCP protocol pattern, providing REST API endpoints and agent tool
integration for Google Cloud Vertex AI Veo3 models.
"""

from .api import router as veo3_router
from .server import Veo3MCPServer
from .veo3_service import Veo3Service
from .prompts import Veo3Prompts, VIDEO_PROMPT_TEMPLATES
from .handlers import veo_text_to_video_handler, veo_image_to_video_handler
from .mcp_server import create_mcp_server, run_mcp_server, MCPServer
from .config import get_config, list_available_models

__version__ = "1.0.0"
__all__ = [
    "veo3_router",
    "Veo3MCPServer", 
    "Veo3Service",
    "Veo3Prompts",
    "VIDEO_PROMPT_TEMPLATES",
    "veo_text_to_video_handler",
    "veo_image_to_video_handler",
    "create_mcp_server",
    "run_mcp_server",
    "MCPServer",
    "get_config",
    "list_available_models"
]