"""
MCP (Model Context Protocol) server implementation for Veo3 service.

This module implements the MCP protocol server that allows AI agents
to discover and use Veo3 video generation capabilities.
"""

import sys
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from .config import get_config, list_available_models
from .models import (
    TextToVideoRequest, ImageToVideoRequest, Veo3ModelName
)
from .veo3_service import Veo3Service
from .prompts import Veo3Prompts, VIDEO_PROMPT_TEMPLATES
from .handlers import veo_text_to_video_handler, veo_image_to_video_handler


logger = logging.getLogger(__name__)


class Veo3MCPServer:
    """MCP server for Veo3 video generation service."""
    
    def __init__(self, transport: str = "stdio"):
        """
        Initialize MCP server.
        
        Args:
            transport: Transport type (stdio, http, sse)
        """
        self.config = get_config()
        self.transport = transport
        self.veo3_service = Veo3Service()
        self.tools = self._register_tools()
        self.prompts = self._register_prompts()
        self.running = False
    
    def _register_tools(self) -> Dict[str, Dict[str, Any]]:
        """Register available MCP tools."""
        return {
            "veo_t2v": {
                "description": "Generate a video from a text prompt using Veo3. Video is saved to GCS and optionally downloaded locally.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Text prompt for video generation",
                            "minLength": 1,
                            "maxLength": 2000
                        },
                        "model": {
                            "type": "string",
                            "description": "Model to use for generation",
                            "enum": [m.value for m in Veo3ModelName],
                            "default": "veo-2.0-generate-001"
                        },
                        "num_videos": {
                            "type": "integer",
                            "description": "Number of videos to generate",
                            "minimum": 1,
                            "maximum": 4,
                            "default": 1
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "description": "Aspect ratio of the video",
                            "enum": ["16:9", "9:16", "1:1", "4:3"],
                            "default": "16:9"
                        },
                        "duration": {
                            "type": "integer",
                            "description": "Duration in seconds",
                            "minimum": 5,
                            "maximum": 8,
                            "default": 5
                        },
                        "bucket": {
                            "type": "string",
                            "description": "GCS bucket for output storage"
                        },
                        "output_directory": {
                            "type": "string",
                            "description": "Local directory for downloads"
                        }
                    },
                    "required": ["prompt"]
                },
                "handler": lambda args, cb: veo_text_to_video_handler(
                    self.veo3_service, args, cb, None
                )
            },
            "veo_i2v": {
                "description": "Generate a video from an input image (and optional prompt) using Veo3. Supported image MIME types: image/jpeg, image/png.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_uri": {
                            "type": "string",
                            "description": "GCS URI of the input image"
                        },
                        "mime_type": {
                            "type": "string",
                            "description": "MIME type of the input image",
                            "enum": ["image/jpeg", "image/png"]
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Optional text prompt to guide generation",
                            "maxLength": 2000
                        },
                        "model": {
                            "type": "string",
                            "description": "Model to use for generation",
                            "enum": [m.value for m in Veo3ModelName],
                            "default": "veo-2.0-generate-001"
                        },
                        "num_videos": {
                            "type": "integer",
                            "description": "Number of videos to generate",
                            "minimum": 1,
                            "maximum": 4,
                            "default": 1
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "description": "Aspect ratio of the video",
                            "enum": ["16:9", "9:16", "1:1", "4:3"],
                            "default": "16:9"
                        },
                        "duration": {
                            "type": "integer",
                            "description": "Duration in seconds",
                            "minimum": 5,
                            "maximum": 8,
                            "default": 5
                        },
                        "bucket": {
                            "type": "string",
                            "description": "GCS bucket for output storage"
                        },
                        "output_directory": {
                            "type": "string",
                            "description": "Local directory for downloads"
                        }
                    },
                    "required": ["image_uri"]
                },
                "handler": lambda args, cb: veo_image_to_video_handler(
                    self.veo3_service, args, cb, None
                )
            },
            "veo3_list_models": {
                "description": "List available Veo3 models with their specifications",
                "parameters": {
                    "type": "object",
                    "properties": {}
                },
                "handler": self._handle_list_models
            }
        }
    
    def _register_prompts(self) -> Dict[str, Dict[str, Any]]:
        """Register available MCP prompts."""
        all_prompts = Veo3Prompts.get_all_prompts()
        
        # Map prompt handlers
        prompt_handlers = {
            "generate-video": Veo3Prompts.handle_generate_video_prompt,
            "generate-video-advanced": Veo3Prompts.handle_generate_video_advanced_prompt,
            "generate-video-from-image": Veo3Prompts.handle_generate_video_from_image_prompt,
            "list-veo-models": Veo3Prompts.handle_list_models_prompt
        }
        
        # Build prompts with handlers
        registered_prompts = {}
        for prompt_name, prompt_def in all_prompts.items():
            registered_prompts[prompt_name] = {
                "description": prompt_def["description"],
                "arguments": prompt_def["arguments"],
                "handler": prompt_handlers.get(prompt_name, self._handle_generic_prompt)
            }
        
        return registered_prompts
    
    
    async def _handle_list_models(
        self,
        arguments: Dict[str, Any],
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Handle list models tool call."""
        try:
            models = list_available_models()
            
            result_text = "Available Veo3 models:\n"
            for model in models:
                result_text += f"\n• {model.display_name} ({model.name.value})\n"
                result_text += f"  - Duration: {model.min_duration}-{model.max_duration}s\n"
                result_text += f"  - Max videos: {model.max_videos}\n"
                result_text += f"  - Aspect ratios: {', '.join([r.value for r in model.supported_aspect_ratios])}\n"
                if model.description:
                    result_text += f"  - {model.description}\n"
            
            return {
                "content": [{"type": "text", "text": result_text}]
            }
        
        except Exception as e:
            logger.error(f"List models failed: {e}")
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Error: {str(e)}"}]
            }
    
    async def _handle_generic_prompt(
        self,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle generic prompt that doesn't have a specific handler."""
        return {
            "title": "Prompt Handler",
            "messages": [{
                "role": "assistant",
                "content": "This prompt is registered but needs implementation."
            }]
        }
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming MCP request.
        
        Args:
            request: MCP request object
        
        Returns:
            MCP response object
        """
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        try:
            if method == "initialize":
                return self._handle_initialize(request_id, params)
            
            elif method == "tools/list":
                return self._handle_tools_list(request_id)
            
            elif method == "tools/call":
                return await self._handle_tool_call(request_id, params)
            
            elif method == "prompts/list":
                return self._handle_prompts_list(request_id)
            
            elif method == "prompts/get":
                return await self._handle_prompt_get(request_id, params)
            
            else:
                return self._error_response(
                    request_id,
                    f"Unknown method: {method}"
                )
        
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            return self._error_response(request_id, str(e))
    
    def _handle_initialize(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "prompts": {}
                },
                "serverInfo": {
                    "name": "veo3-mcp",
                    "version": self.config.VERSION
                }
            }
        }
    
    def _handle_tools_list(self, request_id: Any) -> Dict[str, Any]:
        """Handle tools/list request."""
        tools_list = []
        for tool_name, tool_info in self.tools.items():
            tools_list.append({
                "name": tool_name,
                "description": tool_info["description"],
                "inputSchema": tool_info["parameters"]
            })
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": tools_list
            }
        }
    
    async def _handle_tool_call(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if tool_name not in self.tools:
            return self._error_response(
                request_id,
                f"Unknown tool: {tool_name}"
            )
        
        # Get progress token if provided
        progress_token = None
        context = {}
        if params.get("meta"):
            progress_token = params["meta"].get("progressToken")
            context["meta"] = {"progressToken": progress_token}
        
        # Create progress callback if token provided
        progress_callback = None
        if progress_token:
            progress_callback = lambda update: self._send_progress(
                progress_token,
                update
            )
        
        # Call tool handler
        tool_handler = self.tools[tool_name]["handler"]
        
        # Handle different tools differently
        if tool_name in ["veo_t2v", "veo_i2v"]:
            # These handlers need service, args, callback, and context
            result = await veo_text_to_video_handler(
                self.veo3_service, arguments, progress_callback, context
            ) if tool_name == "veo_t2v" else await veo_image_to_video_handler(
                self.veo3_service, arguments, progress_callback, context
            )
        else:
            # Other handlers (like list_models)
            result = await tool_handler(arguments, progress_callback)
        
        # Check if result is an error
        if isinstance(result, dict) and result.get("isError"):
            # Extract error message from content
            error_msg = "Unknown error"
            if result.get("content") and len(result["content"]) > 0:
                error_msg = result["content"][0].get("text", error_msg)
            return self._error_response(request_id, error_msg)
        
        # Return success result
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
    
    def _handle_prompts_list(self, request_id: Any) -> Dict[str, Any]:
        """Handle prompts/list request."""
        prompts_list = []
        for prompt_name, prompt_info in self.prompts.items():
            prompts_list.append({
                "name": prompt_name,
                "description": prompt_info["description"],
                "arguments": [
                    {
                        "name": arg_name,
                        "description": arg_info["description"],
                        "required": arg_info["required"]
                    }
                    for arg_name, arg_info in prompt_info["arguments"].items()
                ]
            })
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "prompts": prompts_list
            }
        }
    
    async def _handle_prompt_get(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/get request."""
        prompt_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if prompt_name not in self.prompts:
            return self._error_response(
                request_id,
                f"Unknown prompt: {prompt_name}"
            )
        
        prompt_handler = self.prompts[prompt_name]["handler"]
        
        # Check if this is the generate-video prompt that needs special handling
        if prompt_name == "generate-video" and arguments.get("prompt"):
            # Call the actual video generation for the generate-video prompt
            # This matches the Go implementation behavior
            try:
                tool_result = await veo_text_to_video_handler(
                    self.veo3_service, arguments, None, None
                )
                
                # Extract text from result
                if tool_result.get("isError"):
                    result_text = f"Error: {tool_result['content'][0]['text']}"
                else:
                    result_text = tool_result['content'][0]['text']
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "title": "Video Generation Result",
                        "messages": [
                            {
                                "role": "assistant",
                                "content": result_text
                            }
                        ]
                    }
                }
            except Exception as e:
                return self._error_response(request_id, str(e))
        else:
            # Use the prompt handler for other prompts
            result = prompt_handler(arguments)
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }
    
    def _error_response(self, request_id: Any, error_message: str) -> Dict[str, Any]:
        """Create error response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32603,
                "message": error_message
            }
        }
    
    def _send_progress(self, progress_token: str, update: Any):
        """Send progress notification."""
        # Use camelCase for MCP protocol compatibility (matching Go)
        # Use custom status if available, otherwise use state value
        status = getattr(update, 'status', None) or update.state.value
        
        notification_params = {
            "progressToken": progress_token,  # Changed from progress_token
            "message": update.message,
            "status": status,  # Use custom status from update
            "progress": update.progress_percent,
            "total": 100 if update.progress_percent is not None else None
        }
        
        # In stdio mode, write to stdout
        if self.transport == "stdio":
            message = {
                "jsonrpc": "2.0",
                "method": "notifications/progress",
                "params": notification_params
            }
            sys.stdout.write(json.dumps(message) + "\n")
            sys.stdout.flush()
    
    async def run_stdio(self):
        """Run MCP server in stdio mode."""
        self.running = True
        logger.info("Starting Veo3 MCP server in stdio mode")
        
        while self.running:
            try:
                # Read from stdin
                line = await asyncio.get_event_loop().run_in_executor(
                    None,
                    sys.stdin.readline
                )
                
                if not line:
                    break
                
                # Parse request
                request = json.loads(line.strip())
                
                # Handle request
                response = await self.handle_request(request)
                
                # Write response
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error in stdio loop: {e}")
        
        logger.info("Veo3 MCP server stopped")
    
    def stop(self):
        """Stop the MCP server."""
        self.running = False