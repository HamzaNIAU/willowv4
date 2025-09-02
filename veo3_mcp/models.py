"""
Pydantic models for Veo3 MCP service.

This module defines all request/response models and data structures
used throughout the Veo3 MCP implementation.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator


class Veo3ModelName(str, Enum):
    """Supported Veo3 model names."""
    VEO_2_GENERATE = "veo-2.0-generate-001"
    VEO_3_GENERATE_PREVIEW = "veo-3.0-generate-preview"
    VEO_3_FAST_GENERATE_PREVIEW = "veo-3.0-fast-generate-preview"


class AspectRatio(str, Enum):
    """Supported aspect ratios for video generation."""
    RATIO_16_9 = "16:9"
    RATIO_9_16 = "9:16"
    RATIO_1_1 = "1:1"
    RATIO_4_3 = "4:3"


class VideoGenerationMode(str, Enum):
    """Video generation modes."""
    TEXT_TO_VIDEO = "text_to_video"
    IMAGE_TO_VIDEO = "image_to_video"


class OperationState(str, Enum):
    """States of a long-running operation."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ImageMimeType(str, Enum):
    """Supported image MIME types."""
    JPEG = "image/jpeg"
    PNG = "image/png"


class TextToVideoRequest(BaseModel):
    """Request model for text-to-video generation."""
    prompt: str = Field(..., min_length=1, max_length=2000, description="Text prompt for video generation")
    model: Optional[Veo3ModelName] = Field(default=Veo3ModelName.VEO_2_GENERATE, description="Model to use for generation")
    num_videos: Optional[int] = Field(default=1, ge=1, le=4, description="Number of videos to generate")
    aspect_ratio: Optional[AspectRatio] = Field(default=AspectRatio.RATIO_16_9, description="Aspect ratio of the video")
    duration: Optional[int] = Field(default=5, ge=5, le=8, description="Duration in seconds")
    bucket: Optional[str] = Field(default=None, description="GCS bucket for output storage")
    output_directory: Optional[str] = Field(default=None, description="Local directory for downloads")
    
    @validator('prompt')
    def validate_prompt(cls, v):
        """Ensure prompt is not just whitespace."""
        if not v.strip():
            raise ValueError("Prompt cannot be empty or just whitespace")
        return v.strip()


class ImageToVideoRequest(BaseModel):
    """Request model for image-to-video generation."""
    image_uri: str = Field(..., description="GCS URI of the input image")
    mime_type: Optional[ImageMimeType] = Field(default=None, description="MIME type of the input image")
    prompt: Optional[str] = Field(default="", max_length=2000, description="Optional text prompt to guide generation")
    model: Optional[Veo3ModelName] = Field(default=Veo3ModelName.VEO_2_GENERATE, description="Model to use for generation")
    num_videos: Optional[int] = Field(default=1, ge=1, le=4, description="Number of videos to generate")
    aspect_ratio: Optional[AspectRatio] = Field(default=AspectRatio.RATIO_16_9, description="Aspect ratio of the video")
    duration: Optional[int] = Field(default=5, ge=5, le=8, description="Duration in seconds")
    bucket: Optional[str] = Field(default=None, description="GCS bucket for output storage")
    output_directory: Optional[str] = Field(default=None, description="Local directory for downloads")
    
    @validator('image_uri')
    def validate_gcs_uri(cls, v):
        """Ensure the image URI is a valid GCS path."""
        if not v.startswith('gs://'):
            raise ValueError("Image URI must be a GCS path starting with 'gs://'")
        return v


class ProgressUpdate(BaseModel):
    """Progress update for long-running operations."""
    operation_id: str
    state: OperationState
    progress_percent: Optional[int] = Field(default=None, ge=0, le=100)
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[Dict[str, Any]] = None


class VideoOutput(BaseModel):
    """Information about a generated video."""
    gcs_uri: str = Field(..., description="GCS URI of the generated video")
    local_path: Optional[str] = Field(default=None, description="Local file path if downloaded")
    duration_seconds: int
    aspect_ratio: str
    size_bytes: Optional[int] = None
    mime_type: str = "video/mp4"


class VideoGenerationResponse(BaseModel):
    """Response model for video generation requests."""
    operation_id: str
    state: OperationState
    videos: List[VideoOutput] = Field(default_factory=list)
    message: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class OperationStatusRequest(BaseModel):
    """Request model for checking operation status."""
    operation_id: str = Field(..., description="ID of the operation to check")


class Veo3Model(BaseModel):
    """Information about a Veo3 model."""
    name: Veo3ModelName
    display_name: str
    aliases: List[str] = Field(default_factory=list)
    min_duration: int
    max_duration: int
    default_duration: int
    max_videos: int
    supported_aspect_ratios: List[AspectRatio]
    supports_image_to_video: bool = True
    description: Optional[str] = None


class ListModelsResponse(BaseModel):
    """Response for listing available models."""
    models: List[Veo3Model]
    default_model: Veo3ModelName = Veo3ModelName.VEO_2_GENERATE


class MCPToolCall(BaseModel):
    """MCP tool call request."""
    tool: str
    arguments: Dict[str, Any]
    meta: Optional[Dict[str, Any]] = None


class MCPToolResult(BaseModel):
    """MCP tool call result."""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MCPProgressNotification(BaseModel):
    """MCP progress notification."""
    progress_token: Optional[str] = None
    message: str
    status: str
    progress: Optional[int] = None
    total: Optional[int] = None


class AgentPermission(BaseModel):
    """Agent permission model for MCP toggles."""
    agent_id: str
    mcp_id: str = Field(..., description="MCP ID like 'veo3.model.veo-3.0-generate-preview'")
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JWTPayload(BaseModel):
    """JWT token payload."""
    user_id: str
    agent_id: Optional[str] = None
    project_id: str
    permissions: List[str] = Field(default_factory=list)
    exp: datetime
    iat: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))