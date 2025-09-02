"""
Configuration and model definitions for Veo3 MCP service.

This module contains all configuration settings, model definitions,
and environment variable handling for the Veo3 MCP implementation.
"""

import os
from typing import Dict, List, Optional
from functools import lru_cache
from dotenv import load_dotenv

from .models import Veo3Model, Veo3ModelName, AspectRatio

# Load environment variables
load_dotenv()


class Config:
    """Configuration settings for Veo3 MCP service."""
    
    # Google Cloud settings
    PROJECT_ID: str = os.getenv("PROJECT_ID", "")
    LOCATION: str = os.getenv("LOCATION", "us-central1")
    GENMEDIA_BUCKET: str = os.getenv("GENMEDIA_BUCKET", "")
    API_ENDPOINT: Optional[str] = os.getenv("VERTEX_API_ENDPOINT")  # Match Go implementation
    
    # Service settings
    SERVICE_NAME: str = "veo3-mcp"
    VERSION: str = "1.0.0"
    PORT: int = int(os.getenv("PORT", "8080"))
    
    # Authentication settings
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # MCP settings
    MCP_TRANSPORT: str = os.getenv("MCP_TRANSPORT", "stdio")  # stdio, http, sse
    MCP_ENABLE_PROGRESS: bool = os.getenv("MCP_ENABLE_PROGRESS", "true").lower() == "true"
    
    # Operation settings
    OPERATION_TIMEOUT_MINUTES: int = 5
    POLLING_INTERVAL_SECONDS: int = 15
    MAX_POLLING_ATTEMPTS: int = 20
    
    # Cache settings
    CACHE_TTL_SECONDS: int = 300  # 5 minutes
    
    # Database settings (for MCP toggles)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///veo3_mcp.db")
    
    # OpenTelemetry settings
    OTEL_ENABLED: bool = os.getenv("OTEL_ENABLED", "true").lower() == "true"
    OTEL_SERVICE_NAME: str = "veo3-mcp"
    OTEL_EXPORTER_ENDPOINT: str = os.getenv("OTEL_EXPORTER_ENDPOINT", "http://localhost:4317")
    
    @classmethod
    def validate(cls) -> None:
        """Validate required configuration settings."""
        if not cls.PROJECT_ID:
            raise ValueError("PROJECT_ID environment variable is required")
        
        if not cls.JWT_SECRET_KEY or cls.JWT_SECRET_KEY == "your-secret-key-here":
            raise ValueError("JWT_SECRET_KEY must be set to a secure value")


# Veo3 model definitions
VEO3_MODELS: Dict[Veo3ModelName, Veo3Model] = {
    Veo3ModelName.VEO_2_GENERATE: Veo3Model(
        name=Veo3ModelName.VEO_2_GENERATE,
        display_name="Veo 2",
        aliases=["veo2", "veo-2"],
        min_duration=5,
        max_duration=8,
        default_duration=5,
        max_videos=4,
        supported_aspect_ratios=[AspectRatio.RATIO_16_9, AspectRatio.RATIO_9_16],
        supports_image_to_video=True,
        description="Veo 2.0 standard generation model with balanced quality and speed"
    ),
    Veo3ModelName.VEO_3_GENERATE_PREVIEW: Veo3Model(
        name=Veo3ModelName.VEO_3_GENERATE_PREVIEW,
        display_name="Veo 3",
        aliases=["veo3", "veo-3"],
        min_duration=8,
        max_duration=8,
        default_duration=8,
        max_videos=2,
        supported_aspect_ratios=[AspectRatio.RATIO_16_9],
        supports_image_to_video=True,
        description="Veo 3.0 preview model with enhanced quality and consistency"
    ),
    Veo3ModelName.VEO_3_FAST_GENERATE_PREVIEW: Veo3Model(
        name=Veo3ModelName.VEO_3_FAST_GENERATE_PREVIEW,
        display_name="Veo 3 Fast",
        aliases=["veo3-fast", "veo-3-fast"],
        min_duration=8,
        max_duration=8,
        default_duration=8,
        max_videos=2,
        supported_aspect_ratios=[AspectRatio.RATIO_16_9],
        supports_image_to_video=True,
        description="Veo 3.0 fast preview model optimized for speed"
    ),
}


# Model alias mapping for flexible model selection
MODEL_ALIASES: Dict[str, Veo3ModelName] = {}
for model_name, model_info in VEO3_MODELS.items():
    MODEL_ALIASES[model_name.value.lower()] = model_name
    MODEL_ALIASES[model_info.display_name.lower()] = model_name
    for alias in model_info.aliases:
        MODEL_ALIASES[alias.lower()] = model_name


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Get singleton configuration instance."""
    config = Config()
    config.validate()
    return config


def resolve_model_name(model_input: str) -> Optional[Veo3ModelName]:
    """
    Resolve a model name or alias to a canonical model name.
    
    Args:
        model_input: User-provided model name or alias
    
    Returns:
        Canonical model name or None if not found
    """
    return MODEL_ALIASES.get(model_input.lower())


def get_model_info(model_name: Veo3ModelName) -> Veo3Model:
    """
    Get detailed information about a specific model.
    
    Args:
        model_name: Canonical model name
    
    Returns:
        Model information
    
    Raises:
        ValueError: If model not found
    """
    if model_name not in VEO3_MODELS:
        raise ValueError(f"Model {model_name} not found")
    return VEO3_MODELS[model_name]


def list_available_models() -> List[Veo3Model]:
    """Get list of all available models."""
    return list(VEO3_MODELS.values())


def validate_generation_params(
    model_name: Veo3ModelName,
    num_videos: int,
    duration: int,
    aspect_ratio: AspectRatio
) -> tuple[int, int, AspectRatio]:
    """
    Validate and adjust generation parameters for a specific model.
    
    Args:
        model_name: Model to validate against
        num_videos: Requested number of videos
        duration: Requested duration in seconds
        aspect_ratio: Requested aspect ratio
    
    Returns:
        Tuple of (adjusted_num_videos, adjusted_duration, adjusted_aspect_ratio)
    """
    model = get_model_info(model_name)
    
    # Adjust number of videos
    if num_videos > model.max_videos:
        num_videos = model.max_videos
    elif num_videos < 1:
        num_videos = 1
    
    # Adjust duration
    if duration < model.min_duration:
        duration = model.min_duration
    elif duration > model.max_duration:
        duration = model.max_duration
    
    # Validate aspect ratio
    if aspect_ratio not in model.supported_aspect_ratios:
        aspect_ratio = model.supported_aspect_ratios[0]  # Use first supported ratio
    
    return num_videos, duration, aspect_ratio


# MCP permission prefixes
MCP_PERMISSION_PREFIXES = {
    "model": "veo3.model.",
    "feature": "veo3.feature.",
    "operation": "veo3.operation.",
}


def get_mcp_id_for_model(model_name: Veo3ModelName) -> str:
    """Generate MCP permission ID for a model."""
    return f"{MCP_PERMISSION_PREFIXES['model']}{model_name.value}"


def get_mcp_id_for_feature(feature: str) -> str:
    """Generate MCP permission ID for a feature."""
    return f"{MCP_PERMISSION_PREFIXES['feature']}{feature}"