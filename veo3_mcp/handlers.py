"""
Handler functions for Veo3 MCP tools.

This module implements the handler functions for text-to-video and 
image-to-video generation, matching the Go implementation's handlers.go.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, Callable, Tuple
from datetime import datetime, timezone

from .config import get_config, get_model_info, resolve_model_name
from .models import (
    TextToVideoRequest, ImageToVideoRequest,
    Veo3ModelName, AspectRatio, ImageMimeType,
    VideoGenerationResponse, OperationState
)
from .veo3_service import Veo3Service
from .utils import ensure_gcs_path_prefix, infer_mime_type_from_uri
from .otel import get_telemetry

logger = logging.getLogger(__name__)


def parse_common_video_params(args: Dict[str, Any]) -> Tuple[str, str, Veo3ModelName, AspectRatio, int, int]:
    """
    Parse and validate common video generation parameters.
    Matches Go's parseCommonVideoParams function.
    
    Args:
        args: Request arguments
    
    Returns:
        Tuple of (gcs_bucket, output_dir, model, aspect_ratio, num_videos, duration)
    
    Raises:
        ValueError: If parameters are invalid
    """
    # Model
    model_input = args.get("model", "veo-2.0-generate-001")
    if not model_input:
        model_input = "veo-2.0-generate-001"
    
    # Resolve model name
    canonical_name = resolve_model_name(model_input)
    if not canonical_name:
        raise ValueError(f"model '{model_input}' is not a valid or supported model name")
    
    model = canonical_name
    model_details = get_model_info(model)
    
    # GCS Bucket
    gcs_bucket = args.get("bucket", "")
    if gcs_bucket:
        gcs_bucket = ensure_gcs_path_prefix(gcs_bucket)
    
    # Output Directory
    output_dir = args.get("output_directory", "")
    
    # Number of Videos
    num_videos = int(args.get("num_videos", 1))
    if num_videos < 1:
        num_videos = 1
    if num_videos > model_details.max_videos:
        logger.warning(
            f"Requested {num_videos} videos, but model {model} only supports "
            f"up to {model_details.max_videos}. Adjusting to max."
        )
        num_videos = model_details.max_videos
    
    # Duration
    duration = int(args.get("duration", model_details.default_duration))
    if duration < model_details.min_duration:
        logger.warning(
            f"Requested duration {duration}s is less than the minimum of "
            f"{model_details.min_duration}s for model {model}. Adjusting to minimum."
        )
        duration = model_details.min_duration
    if duration > model_details.max_duration:
        logger.warning(
            f"Requested duration {duration}s is greater than the maximum of "
            f"{model_details.max_duration}s for model {model}. Adjusting to maximum."
        )
        duration = model_details.max_duration
    
    # Aspect Ratio
    aspect_ratio_str = args.get("aspect_ratio", "16:9")
    if not aspect_ratio_str:
        aspect_ratio_str = "16:9"
    
    # Convert string to AspectRatio enum
    aspect_ratio_map = {
        "16:9": AspectRatio.RATIO_16_9,
        "9:16": AspectRatio.RATIO_9_16,
        "1:1": AspectRatio.RATIO_1_1,
        "4:3": AspectRatio.RATIO_4_3
    }
    
    aspect_ratio = aspect_ratio_map.get(aspect_ratio_str)
    if not aspect_ratio:
        raise ValueError(f"aspect ratio '{aspect_ratio_str}' is not supported")
    
    # Validate aspect ratio for model
    if aspect_ratio not in model_details.supported_aspect_ratios:
        raise ValueError(
            f"aspect ratio '{aspect_ratio_str}' is not supported by model {model}"
        )
    
    return gcs_bucket, output_dir, model, aspect_ratio, num_videos, duration


async def veo_text_to_video_handler(
    service: Veo3Service,
    request_args: Dict[str, Any],
    progress_callback: Optional[Callable] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Handler for text-to-video generation.
    Matches Go's veoTextToVideoHandler function.
    
    Args:
        service: Veo3Service instance
        request_args: Request arguments
        progress_callback: Optional progress callback
        context: Request context with cancellation info
    
    Returns:
        Tool result dictionary
    """
    # Check if context is already cancelled (matching Go implementation)
    if context and context.get("cancelled"):
        logger.info(f"Incoming t2v context was already cancelled")
        return {
            "isError": True,
            "content": [{"type": "text", "text": "request processing canceled early"}]
        }
    
    telemetry = get_telemetry()
    
    # Extract progress token if available
    progress_token = None
    if context and "meta" in context:
        progress_token = context["meta"].get("progressToken")
    
    # Log the request (matching Go implementation)
    prompt = request_args.get("prompt", "").strip()
    gcs_bucket = request_args.get("bucket", "")
    output_dir = request_args.get("output_directory", "")
    model = request_args.get("model", "veo-2.0-generate-001")
    
    logger.info(f"Handling Veo t2v request: Prompt=\"{prompt[:50]}...\", GCSBucket={gcs_bucket}, OutputDir='{output_dir}', Model={model}")
    
    # Start tracing span if telemetry is enabled
    span_attrs = {"tool": "veo_t2v", "prompt": prompt, "model": model}
    if telemetry:
        async with telemetry.async_span("veo_t2v", attributes=span_attrs):
            return await _handle_text_to_video(service, request_args, progress_callback, progress_token)
    else:
        return await _handle_text_to_video(service, request_args, progress_callback, progress_token)


async def _handle_text_to_video(
    service: Veo3Service,
    request_args: Dict[str, Any],
    progress_callback: Optional[Callable],
    progress_token: Optional[str] = None
) -> Dict[str, Any]:
    """Internal text-to-video handler."""
    try:
        # Extract and validate prompt
        prompt = request_args.get("prompt", "").strip()
        if not prompt:
            return {
                "isError": True,
                "content": [{"type": "text", "text": "prompt must be a non-empty string and is required for text-to-video"}]
            }
        
        # Parse common parameters
        gcs_bucket, output_dir, model, aspect_ratio, num_videos, duration = parse_common_video_params(request_args)
        
        # Log the request
        logger.info(
            f"Text-to-video request: model={model.value}, duration={duration}s, "
            f"aspect_ratio={aspect_ratio.value}, num_videos={num_videos}"
        )
        
        # Create request object
        request = TextToVideoRequest(
            prompt=prompt,
            model=model,
            num_videos=num_videos,
            duration=duration,
            aspect_ratio=aspect_ratio,
            bucket=gcs_bucket,
            output_directory=output_dir
        )
        
        # Call service to start generation (non-blocking)
        # The service will handle the operation asynchronously
        response = await service.generate_video_from_text(request, progress_callback)
        
        # Return immediately with operation info (matching Go implementation)
        # The client will receive progress notifications or can poll for status
        result_text = f"Video generation started. Operation ID: {response.operation_id}\n"
        result_text += f"Model: {model}\n"
        result_text += f"Status: {response.state.value}\n"
        
        if progress_token:
            result_text += "Progress notifications will be sent.\n"
        
        return {
            "content": [{"type": "text", "text": result_text.strip()}]
        }
    
    except Exception as e:
        logger.error(f"Error in text-to-video handler: {e}")
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Error: {str(e)}"}]
        }


async def veo_image_to_video_handler(
    service: Veo3Service,
    request_args: Dict[str, Any],
    progress_callback: Optional[Callable] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Handler for image-to-video generation.
    Matches Go's veoImageToVideoHandler function.
    
    Args:
        service: Veo3Service instance
        request_args: Request arguments
        progress_callback: Optional progress callback
        context: Request context with cancellation info
    
    Returns:
        Tool result dictionary
    """
    # Check if context is already cancelled (matching Go implementation)
    if context and context.get("cancelled"):
        logger.info(f"Incoming i2v context was already cancelled")
        return {
            "isError": True,
            "content": [{"type": "text", "text": "request processing canceled early"}]
        }
    
    telemetry = get_telemetry()
    
    # Extract progress token if available
    progress_token = None
    if context and "meta" in context:
        progress_token = context["meta"].get("progressToken")
    
    # Log the request (matching Go implementation)
    image_uri = request_args.get("image_uri", "")
    gcs_bucket = request_args.get("bucket", "")
    output_dir = request_args.get("output_directory", "")
    model = request_args.get("model", "veo-2.0-generate-001")
    
    logger.info(f"Handling Veo i2v request: ImageURI=\"{image_uri}\", GCSBucket={gcs_bucket}, OutputDir='{output_dir}', Model={model}")
    
    # Start tracing span if telemetry is enabled
    span_attrs = {"tool": "veo_i2v", "image_uri": image_uri, "model": model}
    if telemetry:
        async with telemetry.async_span("veo_i2v", attributes=span_attrs):
            return await _handle_image_to_video(service, request_args, progress_callback, progress_token)
    else:
        return await _handle_image_to_video(service, request_args, progress_callback, progress_token)


async def _handle_image_to_video(
    service: Veo3Service,
    request_args: Dict[str, Any],
    progress_callback: Optional[Callable],
    progress_token: Optional[str] = None
) -> Dict[str, Any]:
    """Internal image-to-video handler."""
    try:
        # Extract and validate image URI
        image_uri = request_args.get("image_uri", "").strip()
        if not image_uri:
            return {
                "isError": True,
                "content": [{"type": "text", "text": "image_uri must be a non-empty string (GCS URI) and is required for image-to-video"}]
            }
        
        # Ensure GCS prefix
        if not image_uri.startswith("gs://"):
            return {
                "isError": True,
                "content": [{"type": "text", "text": "image_uri must be a GCS URI (starting with gs://)"}]
            }
        
        # Get optional prompt
        prompt = request_args.get("prompt", "").strip()
        
        # Get MIME type or infer it
        mime_type_str = request_args.get("mime_type", "")
        if not mime_type_str:
            mime_type_str = infer_mime_type_from_uri(image_uri)
            if not mime_type_str:
                mime_type_str = "image/jpeg"  # Default
        
        # Convert to enum
        mime_type_map = {
            "image/jpeg": ImageMimeType.JPEG,
            "image/png": ImageMimeType.PNG
        }
        mime_type = mime_type_map.get(mime_type_str, ImageMimeType.JPEG)
        
        # Parse common parameters
        gcs_bucket, output_dir, model, aspect_ratio, num_videos, duration = parse_common_video_params(request_args)
        
        # Log the request
        logger.info(
            f"Image-to-video request: model={model.value}, duration={duration}s, "
            f"aspect_ratio={aspect_ratio.value}, num_videos={num_videos}, "
            f"image_uri={image_uri}, mime_type={mime_type.value}"
        )
        
        # Create request object
        request = ImageToVideoRequest(
            image_uri=image_uri,
            prompt=prompt,
            mime_type=mime_type,
            model=model,
            num_videos=num_videos,
            duration=duration,
            aspect_ratio=aspect_ratio,
            bucket=gcs_bucket,
            output_directory=output_dir
        )
        
        # Call service to start generation (non-blocking)
        # The service will handle the operation asynchronously
        response = await service.generate_video_from_image(request, progress_callback)
        
        # Return immediately with operation info (matching Go implementation)
        # The client will receive progress notifications or can poll for status
        result_text = f"Video generation from image started. Operation ID: {response.operation_id}\n"
        result_text += f"Model: {model}\n"
        result_text += f"Status: {response.state.value}\n"
        result_text += f"Image URI: {image_uri}\n"
        
        if progress_token:
            result_text += "Progress notifications will be sent.\n"
        
        return {
            "content": [{"type": "text", "text": result_text.strip()}]
        }
    
    except Exception as e:
        logger.error(f"Error in image-to-video handler: {e}")
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Error: {str(e)}"}]
        }