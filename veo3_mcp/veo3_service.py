"""
Core Veo3 service for video generation using Google Cloud Vertex AI.

This module handles all interactions with the Vertex AI Veo3 API,
including video generation, operation polling, and progress tracking.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path

from google.cloud import aiplatform
from google.cloud import storage
from google.api_core import exceptions as gcp_exceptions
import google.generativeai as genai

from .config import Config, get_config, get_model_info, validate_generation_params
from .models import (
    TextToVideoRequest, ImageToVideoRequest, VideoGenerationResponse,
    VideoOutput, OperationState, ProgressUpdate, Veo3ModelName
)
from .utils import (
    download_from_gcs, generate_operation_id, generate_filename,
    parse_gcs_uri, ensure_gcs_path_prefix, format_duration
)


logger = logging.getLogger(__name__)


class Veo3Service:
    """Service for interacting with Vertex AI Veo3 models."""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize Veo3 service.
        
        Args:
            config: Optional configuration object
        """
        self.config = config or get_config()
        self.storage_client = storage.Client(project=self.config.PROJECT_ID)
        self.operations: Dict[str, VideoGenerationResponse] = {}
        self.progress_callbacks: Dict[str, Callable] = {}
        
        # Initialize Vertex AI
        aiplatform.init(
            project=self.config.PROJECT_ID,
            location=self.config.LOCATION
        )
        
        # Initialize GenAI client for Veo3
        self._init_genai_client()
    
    def _init_genai_client(self):
        """Initialize Google GenAI client for Veo3."""
        # Initialize using the same pattern as Go implementation
        client_config = genai.ClientConfig(
            backend=genai.BackendVertexAI,
            project=self.config.PROJECT_ID,
            location=self.config.LOCATION
        )
        
        if self.config.API_ENDPOINT:
            client_config.http_options = {"base_url": self.config.API_ENDPOINT}
        
        self.genai_client = genai.Client(client_config)
    
    async def generate_video_from_text(
        self,
        request: TextToVideoRequest,
        progress_callback: Optional[Callable] = None
    ) -> VideoGenerationResponse:
        """
        Generate video from text prompt.
        
        Args:
            request: Text-to-video generation request
            progress_callback: Optional callback for progress updates
        
        Returns:
            Video generation response with operation details
        """
        operation_id = generate_operation_id("t2v")
        
        # Validate and adjust parameters
        num_videos, duration, aspect_ratio = validate_generation_params(
            request.model,
            request.num_videos,
            request.duration,
            request.aspect_ratio
        )
        
        # Prepare GCS output path (matching Go implementation)
        gcs_bucket = request.bucket
        if not gcs_bucket and self.config.GENMEDIA_BUCKET:
            # If no bucket provided but GENMEDIA_BUCKET is set, use it with veo_outputs suffix
            gcs_bucket = f"{self.config.GENMEDIA_BUCKET}/veo_outputs"
        gcs_bucket = ensure_gcs_path_prefix(gcs_bucket) if gcs_bucket else ""
        
        # Create initial response
        response = VideoGenerationResponse(
            operation_id=operation_id,
            state=OperationState.PENDING,
            message=f"Starting text-to-video generation with model {request.model.value}",
            metadata={
                "mode": "text_to_video",
                "model": request.model.value,
                "prompt": request.prompt[:100] + "..." if len(request.prompt) > 100 else request.prompt
            }
        )
        
        self.operations[operation_id] = response
        if progress_callback:
            self.progress_callbacks[operation_id] = progress_callback
        
        # Start generation in background
        asyncio.create_task(self._generate_video_async(
            operation_id=operation_id,
            model_name=request.model.value,
            prompt=request.prompt,
            image_uri=None,
            num_videos=num_videos,
            duration=duration,
            aspect_ratio=aspect_ratio.value,
            gcs_bucket=gcs_bucket,
            output_directory=request.output_directory
        ))
        
        return response
    
    async def generate_video_from_image(
        self,
        request: ImageToVideoRequest,
        progress_callback: Optional[Callable] = None
    ) -> VideoGenerationResponse:
        """
        Generate video from image with optional prompt.
        
        Args:
            request: Image-to-video generation request
            progress_callback: Optional callback for progress updates
        
        Returns:
            Video generation response with operation details
        """
        operation_id = generate_operation_id("i2v")
        
        # Validate and adjust parameters
        num_videos, duration, aspect_ratio = validate_generation_params(
            request.model,
            request.num_videos,
            request.duration,
            request.aspect_ratio
        )
        
        # Prepare GCS output path (matching Go implementation)
        gcs_bucket = request.bucket
        if not gcs_bucket and self.config.GENMEDIA_BUCKET:
            # If no bucket provided but GENMEDIA_BUCKET is set, use it with veo_outputs suffix
            gcs_bucket = f"{self.config.GENMEDIA_BUCKET}/veo_outputs"
        gcs_bucket = ensure_gcs_path_prefix(gcs_bucket) if gcs_bucket else ""
        
        # Create initial response
        response = VideoGenerationResponse(
            operation_id=operation_id,
            state=OperationState.PENDING,
            message=f"Starting image-to-video generation with model {request.model.value}",
            metadata={
                "mode": "image_to_video",
                "model": request.model.value,
                "image_uri": request.image_uri,
                "has_prompt": bool(request.prompt)
            }
        )
        
        self.operations[operation_id] = response
        if progress_callback:
            self.progress_callbacks[operation_id] = progress_callback
        
        # Start generation in background
        asyncio.create_task(self._generate_video_async(
            operation_id=operation_id,
            model_name=request.model.value,
            prompt=request.prompt or "",
            image_uri=request.image_uri,
            num_videos=num_videos,
            duration=duration,
            aspect_ratio=aspect_ratio.value,
            gcs_bucket=gcs_bucket,
            output_directory=request.output_directory,
            image_mime_type=request.mime_type.value if request.mime_type else None
        ))
        
        return response
    
    async def _generate_video_async(
        self,
        operation_id: str,
        model_name: str,
        prompt: str,
        image_uri: Optional[str],
        num_videos: int,
        duration: int,
        aspect_ratio: str,
        gcs_bucket: str,
        output_directory: Optional[str],
        image_mime_type: Optional[str] = None
    ):
        """
        Internal async method to handle video generation.
        
        This method runs the actual video generation operation and
        handles polling, progress updates, and result processing.
        """
        response = self.operations[operation_id]
        progress_callback = self.progress_callbacks.get(operation_id)
        
        try:
            # Update state to running
            response.state = OperationState.RUNNING
            await self._send_progress(
                operation_id,
                "Video generation (t2v) initiated. Polling for completion...",
                0,
                status="initiated"  # Match Go's status value
            )
            
            # Prepare generation config matching Go implementation
            generation_config = genai.GenerateVideosConfig(
                number_of_videos=num_videos,
                aspect_ratio=aspect_ratio,
                output_gcs_uri=gcs_bucket,
                duration_seconds=duration
            )
            
            # Create the generation request matching Go implementation
            if image_uri:
                # Image-to-video generation
                image = genai.Image(
                    gcs_uri=image_uri,
                    mime_type=image_mime_type or "image/jpeg"
                )
                operation = await self._call_genai_async(
                    self.genai_client.models.generate_videos,
                    model_name,
                    prompt,
                    image,
                    generation_config
                )
            else:
                # Text-to-video generation
                operation = await self._call_genai_async(
                    self.genai_client.models.generate_videos,
                    model_name,
                    prompt,
                    None,
                    generation_config
                )
            
            logger.info(f"Started Veo3 operation: {operation.name}")
            await self._send_progress(
                operation_id,
                "Video generation started, polling for completion...",
                10,
                status="polling"  # Match Go's status value
            )
            
            # Poll for operation completion
            result = await self._poll_operation(
                operation_id,
                operation,
                timeout_minutes=self.config.OPERATION_TIMEOUT_MINUTES
            )
            
            # Process results matching Go implementation structure
            if result and hasattr(result, 'generated_videos'):
                videos = []
                for idx, generated_video in enumerate(result.generated_videos):
                    video_gcs_uri = ""
                    if hasattr(generated_video, 'video') and generated_video.video:
                        if hasattr(generated_video.video, 'uri'):
                            video_gcs_uri = generated_video.video.uri
                    
                    if not video_gcs_uri:
                        logger.warning(f"Generated video {idx} had no retrievable GCS URI")
                        continue
                    
                    # Download locally if requested
                    local_path = None
                    if output_directory:
                        filename = generate_filename(
                            model_name, "video", idx, "mp4"
                        )
                        local_path = str(Path(output_directory) / filename)
                        
                        try:
                            await download_from_gcs(
                                video_gcs_uri,
                                local_path,
                                self.storage_client
                            )
                            logger.info(f"Downloaded video to {local_path}")
                        except Exception as e:
                            logger.error(f"Failed to download video: {e}")
                            local_path = None
                    
                    videos.append(VideoOutput(
                        gcs_uri=video_gcs_uri,
                        local_path=local_path,
                        duration_seconds=duration,
                        aspect_ratio=aspect_ratio
                    ))
                
                # Update response
                response.videos = videos
                response.state = OperationState.SUCCEEDED
                response.completed_at = datetime.now(timezone.utc)
                response.message = f"Successfully generated {len(videos)} video(s)"
                
                await self._send_progress(
                    operation_id,
                    f"Video generation completed! Generated {len(videos)} video(s)",
                    100,
                    status="completed"  # Match Go's status value
                )
            else:
                raise Exception("No videos generated in the operation result")
        
        except asyncio.TimeoutError:
            response.state = OperationState.FAILED
            response.error = "Operation timed out"
            response.message = "Video generation timed out after 5 minutes"
            response.completed_at = datetime.utcnow()
            
            await self._send_progress(
                operation_id,
                "Video generation timed out",
                -1,
                status="completed_with_error"  # Match Go's status value
            )
        
        except Exception as e:
            logger.error(f"Video generation failed: {e}")
            response.state = OperationState.FAILED
            response.error = str(e)
            response.message = f"Video generation failed: {str(e)}"
            response.completed_at = datetime.utcnow()
            
            await self._send_progress(
                operation_id,
                f"Video generation failed: {str(e)}",
                -1,
                status="completed_with_error"  # Match Go's status value
            )
    
    async def _call_genai_async(self, func, **kwargs):
        """Wrapper to call GenAI functions asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, **kwargs)
    
    async def _poll_operation(
        self,
        operation_id: str,
        operation: Any,
        timeout_minutes: int = 5
    ) -> Any:
        """
        Poll a long-running operation until completion.
        
        Args:
            operation_id: Our operation ID
            operation: GenAI operation object
            timeout_minutes: Timeout in minutes
        
        Returns:
            Operation result
        
        Raises:
            TimeoutError: If operation times out
        """
        start_time = datetime.now(timezone.utc)
        timeout = timedelta(minutes=timeout_minutes)
        polling_interval = self.config.POLLING_INTERVAL_SECONDS
        attempt = 0
        
        while not operation.done:
            # Check timeout
            if datetime.now(timezone.utc) - start_time > timeout:
                raise asyncio.TimeoutError(
                    f"Operation timed out after {timeout_minutes} minutes"
                )
            
            attempt += 1
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            # Send progress update matching Go implementation
            # Send heartbeat notification before polling
            await self._send_progress(
                operation_id,
                f"Checking video status (polling attempt {attempt})...",
                None  # Progress unknown during polling
            )
            
            # Wait before next poll
            await asyncio.sleep(polling_interval)
            
            # Update operation status matching Go implementation
            try:
                get_op_config = genai.GetOperationConfig()
                operation = await self._call_genai_async(
                    self.genai_client.operations.get_videos_operation,
                    operation,
                    get_op_config
                )
            except Exception as e:
                logger.warning(f"Error polling operation: {e}")
                # Send polling issue notification like Go implementation
                await self._send_progress(
                    operation_id,
                    f"Polling attempt {attempt} encountered an issue. Retrying...",
                    None
                )
                continue
            
            # Update progress based on operation metadata (matching Go)
            if hasattr(operation, 'metadata') and operation.metadata:
                progress_message = f"Video generation in progress. Polling attempt {attempt}."
                progress_percent = None
                
                if 'state' in operation.metadata:
                    state = operation.metadata['state']
                    progress_message = f"Video generation state: {state}. Polling attempt {attempt}."
                
                if 'progress_percent' in operation.metadata:
                    progress_percent = int(operation.metadata['progress_percent'])
                    progress_message = f"Video generation is {progress_percent}% complete. Polling attempt {attempt}."
                elif 'progressPercent' in operation.metadata:  # Alternative casing
                    progress_percent = int(operation.metadata['progressPercent'])
                    progress_message = f"Video generation is {progress_percent}% complete. Polling attempt {attempt}."
                
                await self._send_progress(
                    operation_id,
                    progress_message,
                    progress_percent
                )
        
        # Check for errors
        if operation.error:
            error_msg = getattr(operation.error, 'message', str(operation.error))
            raise Exception(f"Operation failed: {error_msg}")
        
        return operation.response
    
    async def _send_progress(
        self,
        operation_id: str,
        message: str,
        progress_percent: int,
        status: Optional[str] = None
    ):
        """Send progress update for an operation."""
        if operation_id in self.operations:
            response = self.operations[operation_id]
            
            # Use provided status or derive from state (matching Go implementation)
            if status is None:
                status = response.state.value
            
            # Create progress update with custom status
            update = ProgressUpdate(
                operation_id=operation_id,
                state=response.state,
                progress_percent=progress_percent if progress_percent >= 0 else None,
                message=message
            )
            # Override the status for MCP protocol
            update.status = status
            
            # Call progress callback if registered
            callback = self.progress_callbacks.get(operation_id)
            if callback:
                try:
                    await callback(update)
                except Exception as e:
                    logger.error(f"Error calling progress callback: {e}")
    
    async def get_operation_status(
        self,
        operation_id: str
    ) -> Optional[VideoGenerationResponse]:
        """
        Get the status of a video generation operation.
        
        Args:
            operation_id: Operation identifier
        
        Returns:
            Operation response or None if not found
        """
        return self.operations.get(operation_id)
    
    async def cancel_operation(
        self,
        operation_id: str
    ) -> bool:
        """
        Cancel a running operation.
        
        Args:
            operation_id: Operation identifier
        
        Returns:
            True if cancelled, False if not found or already completed
        """
        if operation_id in self.operations:
            response = self.operations[operation_id]
            if response.state in [OperationState.PENDING, OperationState.RUNNING]:
                response.state = OperationState.CANCELLED
                response.completed_at = datetime.now(timezone.utc)
                response.message = "Operation cancelled by user"
                
                await self._send_progress(
                    operation_id,
                    "Operation cancelled",
                    -1
                )
                return True
        
        return False
    
    def cleanup_old_operations(self, hours: int = 24):
        """
        Clean up old operations from memory.
        
        Args:
            hours: Remove operations older than this many hours
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        to_remove = []
        for op_id, response in self.operations.items():
            if response.created_at < cutoff:
                to_remove.append(op_id)
        
        for op_id in to_remove:
            del self.operations[op_id]
            self.progress_callbacks.pop(op_id, None)
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old operations")