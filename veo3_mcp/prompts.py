"""
MCP Prompts for Veo3 service.

This module defines interactive prompts that can be used by MCP clients
to generate videos through guided interactions, matching the Go implementation.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from .models import Veo3ModelName, AspectRatio


class Veo3Prompts:
    """Collection of MCP prompts for Veo3 video generation."""
    
    @staticmethod
    def get_all_prompts() -> Dict[str, Dict[str, Any]]:
        """
        Get all available MCP prompts.
        
        Returns:
            Dictionary of prompt definitions
        """
        return {
            "generate-video": {
                "description": "Generates a video from a text prompt.",
                "arguments": [
                    {
                        "name": "prompt",
                        "description": "The text prompt to generate a video from.",
                        "required": True
                    },
                    {
                        "name": "duration",
                        "description": "The duration of the video in seconds.",
                        "required": False
                    },
                    {
                        "name": "aspect_ratio",
                        "description": "The aspect ratio of the generated video.",
                        "required": False
                    },
                    {
                        "name": "model",
                        "description": "The model to use for generation.",
                        "required": False
                    }
                ]
            },
            "generate-video-advanced": {
                "description": "Generate a video with advanced options and customization.",
                "arguments": [
                    {
                        "name": "prompt",
                        "description": "The text prompt to generate a video from.",
                        "required": True
                    },
                    {
                        "name": "model",
                        "description": "The model to use (veo-2.0-generate-001, veo-3.0-generate-preview, veo-3.0-fast-generate-preview).",
                        "required": False
                    },
                    {
                        "name": "num_videos",
                        "description": "Number of videos to generate (1-4).",
                        "required": False
                    },
                    {
                        "name": "duration",
                        "description": "Duration in seconds (5-8).",
                        "required": False
                    },
                    {
                        "name": "aspect_ratio",
                        "description": "Aspect ratio (16:9, 9:16, 1:1, 4:3).",
                        "required": False
                    },
                    {
                        "name": "bucket",
                        "description": "GCS bucket for output storage.",
                        "required": False
                    }
                ]
            },
            "generate-video-from-image": {
                "description": "Generate a video from an image with optional text guidance.",
                "arguments": [
                    {
                        "name": "image_uri",
                        "description": "GCS URI of the input image (gs://bucket/path/to/image).",
                        "required": True
                    },
                    {
                        "name": "prompt",
                        "description": "Optional text prompt to guide video generation.",
                        "required": False
                    },
                    {
                        "name": "mime_type",
                        "description": "MIME type of the image (image/jpeg or image/png).",
                        "required": False
                    },
                    {
                        "name": "model",
                        "description": "The model to use for generation.",
                        "required": False
                    },
                    {
                        "name": "duration",
                        "description": "Duration in seconds.",
                        "required": False
                    },
                    {
                        "name": "aspect_ratio",
                        "description": "Aspect ratio of the video.",
                        "required": False
                    }
                ]
            },
            "list-veo-models": {
                "description": "List all available Veo3 models and their capabilities.",
                "arguments": []
            }
        }
    
    @staticmethod
    def handle_generate_video_prompt(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the generate-video prompt.
        
        Args:
            arguments: Prompt arguments
        
        Returns:
            Prompt result with messages
        """
        prompt = arguments.get("prompt", "").strip()
        
        if not prompt:
            return {
                "title": "Missing Prompt",
                "messages": [
                    {
                        "role": "assistant",
                        "content": "What video would you like me to generate?"
                    }
                ]
            }
        
        # Build a descriptive message about what will be generated
        duration = arguments.get("duration", 5)
        aspect_ratio = arguments.get("aspect_ratio", "16:9")
        model = arguments.get("model", "veo-2.0-generate-001")
        
        message = f"I'll generate a video with the following specifications:\n\n"
        message += f"**Prompt**: {prompt}\n"
        message += f"**Model**: {model}\n"
        message += f"**Duration**: {duration} seconds\n"
        message += f"**Aspect Ratio**: {aspect_ratio}\n\n"
        message += "The video generation will begin now. This typically takes 2-5 minutes to complete."
        
        return {
            "title": "Video Generation Request",
            "messages": [
                {
                    "role": "assistant",
                    "content": message
                }
            ],
            "metadata": {
                "action": "generate_video",
                "parameters": {
                    "prompt": prompt,
                    "model": model,
                    "duration": duration,
                    "aspect_ratio": aspect_ratio
                }
            }
        }
    
    @staticmethod
    def handle_generate_video_advanced_prompt(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the advanced video generation prompt with all options.
        
        Args:
            arguments: Prompt arguments
        
        Returns:
            Prompt result with messages
        """
        prompt = arguments.get("prompt", "").strip()
        
        if not prompt:
            return {
                "title": "Advanced Video Generation",
                "messages": [
                    {
                        "role": "assistant",
                        "content": (
                            "Welcome to advanced video generation! Please provide:\n\n"
                            "1. **Text prompt** (required): Describe the video you want\n"
                            "2. **Model** (optional): veo-2.0-generate-001, veo-3.0-generate-preview, or veo-3.0-fast-generate-preview\n"
                            "3. **Number of videos** (optional): 1-4 videos\n"
                            "4. **Duration** (optional): 5-8 seconds\n"
                            "5. **Aspect ratio** (optional): 16:9, 9:16, 1:1, or 4:3\n"
                            "6. **Output bucket** (optional): GCS bucket for storage\n\n"
                            "What video would you like to generate?"
                        )
                    }
                ]
            }
        
        # Parse all parameters
        model = arguments.get("model", "veo-2.0-generate-001")
        num_videos = arguments.get("num_videos", 1)
        duration = arguments.get("duration", 5)
        aspect_ratio = arguments.get("aspect_ratio", "16:9")
        bucket = arguments.get("bucket", "")
        
        message = f"Generating {num_videos} video(s) with advanced settings:\n\n"
        message += f"**Prompt**: {prompt}\n"
        message += f"**Model**: {model}\n"
        message += f"**Videos to generate**: {num_videos}\n"
        message += f"**Duration**: {duration} seconds each\n"
        message += f"**Aspect Ratio**: {aspect_ratio}\n"
        if bucket:
            message += f"**Output Location**: gs://{bucket}\n"
        message += "\nGeneration starting now..."
        
        return {
            "title": "Advanced Video Generation",
            "messages": [
                {
                    "role": "assistant",
                    "content": message
                }
            ],
            "metadata": {
                "action": "generate_video_advanced",
                "parameters": {
                    "prompt": prompt,
                    "model": model,
                    "num_videos": num_videos,
                    "duration": duration,
                    "aspect_ratio": aspect_ratio,
                    "bucket": bucket
                }
            }
        }
    
    @staticmethod
    def handle_generate_video_from_image_prompt(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the image-to-video generation prompt.
        
        Args:
            arguments: Prompt arguments
        
        Returns:
            Prompt result with messages
        """
        image_uri = arguments.get("image_uri", "").strip()
        
        if not image_uri:
            return {
                "title": "Image-to-Video Generation",
                "messages": [
                    {
                        "role": "assistant",
                        "content": (
                            "To generate a video from an image, I need:\n\n"
                            "1. **Image URI** (required): GCS path to your image (gs://bucket/path/image.jpg)\n"
                            "2. **Text prompt** (optional): Guide the animation/motion\n"
                            "3. **Duration** (optional): 5-8 seconds\n"
                            "4. **Aspect ratio** (optional): 16:9, 9:16, etc.\n\n"
                            "Please provide the GCS URI of your input image."
                        )
                    }
                ]
            }
        
        if not image_uri.startswith("gs://"):
            return {
                "title": "Invalid Image URI",
                "messages": [
                    {
                        "role": "assistant",
                        "content": f"The image URI must be a GCS path starting with 'gs://'. You provided: {image_uri}\n\nPlease provide a valid GCS URI like: gs://your-bucket/path/to/image.jpg"
                    }
                ]
            }
        
        prompt = arguments.get("prompt", "")
        mime_type = arguments.get("mime_type", "")
        model = arguments.get("model", "veo-2.0-generate-001")
        duration = arguments.get("duration", 5)
        aspect_ratio = arguments.get("aspect_ratio", "16:9")
        
        message = f"Generating video from image:\n\n"
        message += f"**Source Image**: {image_uri}\n"
        if prompt:
            message += f"**Animation Prompt**: {prompt}\n"
        message += f"**Model**: {model}\n"
        message += f"**Duration**: {duration} seconds\n"
        message += f"**Aspect Ratio**: {aspect_ratio}\n"
        if mime_type:
            message += f"**Image Type**: {mime_type}\n"
        message += "\nStarting image-to-video generation..."
        
        return {
            "title": "Image-to-Video Generation",
            "messages": [
                {
                    "role": "assistant",
                    "content": message
                }
            ],
            "metadata": {
                "action": "generate_video_from_image",
                "parameters": {
                    "image_uri": image_uri,
                    "prompt": prompt,
                    "mime_type": mime_type,
                    "model": model,
                    "duration": duration,
                    "aspect_ratio": aspect_ratio
                }
            }
        }
    
    @staticmethod
    def handle_list_models_prompt(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the list models prompt.
        
        Args:
            arguments: Prompt arguments (unused)
        
        Returns:
            Prompt result with model information
        """
        message = "**Available Veo3 Models:**\n\n"
        
        message += "**1. Veo 2.0** (`veo-2.0-generate-001`)\n"
        message += "   - Duration: 5-8 seconds\n"
        message += "   - Max videos: 4\n"
        message += "   - Aspect ratios: 16:9, 9:16\n"
        message += "   - Best for: Balanced quality and speed\n\n"
        
        message += "**2. Veo 3.0 Preview** (`veo-3.0-generate-preview`)\n"
        message += "   - Duration: 8 seconds (fixed)\n"
        message += "   - Max videos: 2\n"
        message += "   - Aspect ratios: 16:9\n"
        message += "   - Best for: Enhanced quality and consistency\n\n"
        
        message += "**3. Veo 3.0 Fast Preview** (`veo-3.0-fast-generate-preview`)\n"
        message += "   - Duration: 8 seconds (fixed)\n"
        message += "   - Max videos: 2\n"
        message += "   - Aspect ratios: 16:9\n"
        message += "   - Best for: Faster generation with good quality\n\n"
        
        message += "All models support both text-to-video and image-to-video generation."
        
        return {
            "title": "Available Veo3 Models",
            "messages": [
                {
                    "role": "assistant",
                    "content": message
                }
            ],
            "metadata": {
                "action": "list_models",
                "models": [
                    "veo-2.0-generate-001",
                    "veo-3.0-generate-preview",
                    "veo-3.0-fast-generate-preview"
                ]
            }
        }


# Example templates for common video generation scenarios
VIDEO_PROMPT_TEMPLATES = {
    "cinematic": {
        "description": "Cinematic style video generation",
        "template": "Cinematic shot: {description}, professional cinematography, dramatic lighting, high production value",
        "examples": [
            "Cinematic shot: A lone figure walking through a misty forest at dawn, professional cinematography, dramatic lighting, high production value",
            "Cinematic shot: City skyline at golden hour with slow camera movement, professional cinematography, dramatic lighting, high production value"
        ]
    },
    "nature": {
        "description": "Nature and landscape videos",
        "template": "Nature scene: {description}, pristine natural environment, vibrant colors, peaceful atmosphere",
        "examples": [
            "Nature scene: Waterfall cascading into a crystal clear pool, pristine natural environment, vibrant colors, peaceful atmosphere",
            "Nature scene: Wind blowing through a field of wildflowers, pristine natural environment, vibrant colors, peaceful atmosphere"
        ]
    },
    "animation": {
        "description": "Animated style videos",
        "template": "Animated scene: {description}, smooth animation, vibrant colors, stylized rendering",
        "examples": [
            "Animated scene: A cheerful robot dancing in a futuristic city, smooth animation, vibrant colors, stylized rendering",
            "Animated scene: Magical forest with glowing creatures, smooth animation, vibrant colors, stylized rendering"
        ]
    },
    "realistic": {
        "description": "Photorealistic videos",
        "template": "Photorealistic: {description}, ultra-realistic rendering, natural lighting, high detail",
        "examples": [
            "Photorealistic: Person walking down a busy street, ultra-realistic rendering, natural lighting, high detail",
            "Photorealistic: Ocean waves crashing on a sandy beach, ultra-realistic rendering, natural lighting, high detail"
        ]
    },
    "abstract": {
        "description": "Abstract and artistic videos",
        "template": "Abstract art: {description}, flowing shapes, vibrant colors, artistic composition",
        "examples": [
            "Abstract art: Swirling colors morphing into geometric patterns, flowing shapes, vibrant colors, artistic composition",
            "Abstract art: Liquid metal transforming into crystalline structures, flowing shapes, vibrant colors, artistic composition"
        ]
    }
}


def get_prompt_template(style: str, description: str) -> str:
    """
    Get a formatted prompt using a template style.
    
    Args:
        style: Style name from VIDEO_PROMPT_TEMPLATES
        description: User's description to insert into template
    
    Returns:
        Formatted prompt string
    """
    if style in VIDEO_PROMPT_TEMPLATES:
        template = VIDEO_PROMPT_TEMPLATES[style]["template"]
        return template.format(description=description)
    return description