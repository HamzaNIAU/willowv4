#!/usr/bin/env python3
"""
Verification script for Veo3 MCP service.

This script tests the Veo3 MCP implementation to ensure it's working correctly,
matching the Go implementation's verify functionality.
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from veo3_mcp.config import Config, get_config, list_available_models
from veo3_mcp.veo3_service import Veo3Service
from veo3_mcp.models import (
    TextToVideoRequest, ImageToVideoRequest,
    Veo3ModelName, AspectRatio, ImageMimeType
)
from veo3_mcp.mcp_server import MCPServer
from veo3_mcp.otel import init_telemetry, shutdown_telemetry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Veo3Verifier:
    """Verifier for Veo3 MCP service."""
    
    def __init__(self):
        """Initialize verifier."""
        self.config = None
        self.service = None
        self.telemetry = None
        self.results = {
            "passed": [],
            "failed": [],
            "skipped": []
        }
    
    async def setup(self):
        """Setup verification environment."""
        logger.info("Setting up Veo3 verification...")
        
        # Initialize configuration
        try:
            self.config = get_config()
            logger.info(f"✓ Configuration loaded (Project: {self.config.PROJECT_ID})")
            self.results["passed"].append("Configuration loading")
        except Exception as e:
            logger.error(f"✗ Failed to load configuration: {e}")
            self.results["failed"].append(f"Configuration loading: {e}")
            return False
        
        # Initialize telemetry
        try:
            self.telemetry = init_telemetry(
                service_name="veo3-mcp-verify",
                service_version="1.0.0",
                enabled=self.config.OTEL_ENABLED
            )
            logger.info("✓ OpenTelemetry initialized")
            self.results["passed"].append("OpenTelemetry initialization")
        except Exception as e:
            logger.warning(f"⚠ OpenTelemetry initialization failed (non-critical): {e}")
            self.results["skipped"].append(f"OpenTelemetry: {e}")
        
        # Initialize service
        try:
            self.service = Veo3Service(self.config)
            logger.info("✓ Veo3 service initialized")
            self.results["passed"].append("Service initialization")
        except Exception as e:
            logger.error(f"✗ Failed to initialize service: {e}")
            self.results["failed"].append(f"Service initialization: {e}")
            return False
        
        return True
    
    async def verify_models(self):
        """Verify model definitions."""
        logger.info("\nVerifying model definitions...")
        
        try:
            models = list_available_models()
            logger.info(f"✓ Found {len(models)} models:")
            for model in models:
                logger.info(f"  - {model.display_name} ({model.name.value})")
                logger.info(f"    Duration: {model.min_duration}-{model.max_duration}s")
                logger.info(f"    Max videos: {model.max_videos}")
                logger.info(f"    Aspect ratios: {[r.value for r in model.supported_aspect_ratios]}")
            
            self.results["passed"].append(f"Model definitions ({len(models)} models)")
            return True
        except Exception as e:
            logger.error(f"✗ Model verification failed: {e}")
            self.results["failed"].append(f"Model verification: {e}")
            return False
    
    async def verify_mcp_tools(self):
        """Verify MCP tool registration."""
        logger.info("\nVerifying MCP tools...")
        
        try:
            server = MCPServer()
            
            # Check tools
            tools = server.list_tools()
            expected_tools = ["veo_t2v", "veo_i2v"]
            
            logger.info(f"✓ Found {len(tools)} tools:")
            for tool in tools:
                logger.info(f"  - {tool['name']}: {tool.get('description', 'No description')}")
            
            # Verify expected tools are present
            tool_names = [t['name'] for t in tools]
            for expected in expected_tools:
                if expected in tool_names:
                    logger.info(f"✓ Tool '{expected}' registered")
                    self.results["passed"].append(f"Tool registration: {expected}")
                else:
                    logger.error(f"✗ Tool '{expected}' not found")
                    self.results["failed"].append(f"Tool registration: {expected}")
            
            # Check prompts
            prompts = server.list_prompts()
            logger.info(f"\n✓ Found {len(prompts)} prompts:")
            for prompt in prompts:
                logger.info(f"  - {prompt['name']}: {prompt.get('description', 'No description')}")
            
            self.results["passed"].append(f"MCP registration ({len(tools)} tools, {len(prompts)} prompts)")
            return True
            
        except Exception as e:
            logger.error(f"✗ MCP verification failed: {e}")
            self.results["failed"].append(f"MCP verification: {e}")
            return False
    
    async def verify_text_to_video(self):
        """Verify text-to-video generation (dry run)."""
        logger.info("\nVerifying text-to-video generation (dry run)...")
        
        if not self.service:
            logger.warning("⚠ Service not initialized, skipping")
            self.results["skipped"].append("Text-to-video verification")
            return False
        
        try:
            # Create a test request
            request = TextToVideoRequest(
                prompt="A beautiful sunset over mountains",
                model=Veo3ModelName.VEO_2_GENERATE,
                num_videos=1,
                duration=5,
                aspect_ratio=AspectRatio.RATIO_16_9
            )
            
            logger.info(f"  Request: {request.model.value}, {request.duration}s, {request.aspect_ratio.value}")
            
            # Note: We're not actually calling the API to avoid costs
            # Just validating the request structure
            logger.info("✓ Text-to-video request structure valid")
            self.results["passed"].append("Text-to-video request validation")
            
            # Test parameter validation
            from veo3_mcp.config import validate_generation_params
            num_videos, duration, aspect_ratio = validate_generation_params(
                request.model,
                request.num_videos,
                request.duration,
                request.aspect_ratio
            )
            
            logger.info(f"✓ Parameters validated: {num_videos} videos, {duration}s, {aspect_ratio.value}")
            self.results["passed"].append("Parameter validation")
            
            return True
            
        except Exception as e:
            logger.error(f"✗ Text-to-video verification failed: {e}")
            self.results["failed"].append(f"Text-to-video verification: {e}")
            return False
    
    async def verify_image_to_video(self):
        """Verify image-to-video generation (dry run)."""
        logger.info("\nVerifying image-to-video generation (dry run)...")
        
        if not self.service:
            logger.warning("⚠ Service not initialized, skipping")
            self.results["skipped"].append("Image-to-video verification")
            return False
        
        try:
            # Create a test request
            request = ImageToVideoRequest(
                image_uri="gs://test-bucket/test-image.jpg",
                prompt="Make the clouds move gently",
                model=Veo3ModelName.VEO_3_GENERATE_PREVIEW,
                num_videos=1,
                duration=8,
                aspect_ratio=AspectRatio.RATIO_16_9,
                mime_type=ImageMimeType.JPEG
            )
            
            logger.info(f"  Request: {request.model.value}, {request.duration}s, {request.aspect_ratio.value}")
            logger.info(f"  Image: {request.image_uri} ({request.mime_type.value})")
            
            # Note: We're not actually calling the API to avoid costs
            # Just validating the request structure
            logger.info("✓ Image-to-video request structure valid")
            self.results["passed"].append("Image-to-video request validation")
            
            return True
            
        except Exception as e:
            logger.error(f"✗ Image-to-video verification failed: {e}")
            self.results["failed"].append(f"Image-to-video verification: {e}")
            return False
    
    async def verify_gcs_integration(self):
        """Verify GCS integration."""
        logger.info("\nVerifying GCS integration...")
        
        try:
            from google.cloud import storage
            
            # Check if we can create a storage client
            client = storage.Client(project=self.config.PROJECT_ID)
            logger.info(f"✓ GCS client created for project: {self.config.PROJECT_ID}")
            
            # Check if GENMEDIA_BUCKET is configured
            if self.config.GENMEDIA_BUCKET:
                logger.info(f"✓ GENMEDIA_BUCKET configured: {self.config.GENMEDIA_BUCKET}")
                
                # Parse bucket name
                from veo3_mcp.utils import parse_gcs_uri, ensure_gcs_path_prefix
                
                bucket_uri = ensure_gcs_path_prefix(self.config.GENMEDIA_BUCKET)
                bucket_name, _ = parse_gcs_uri(bucket_uri)
                
                # Try to access bucket (will fail if no permissions)
                try:
                    bucket = client.bucket(bucket_name)
                    bucket.exists()  # This will raise an exception if no access
                    logger.info(f"✓ Bucket '{bucket_name}' is accessible")
                    self.results["passed"].append(f"GCS bucket access: {bucket_name}")
                except Exception as e:
                    logger.warning(f"⚠ Cannot access bucket '{bucket_name}': {e}")
                    self.results["skipped"].append(f"GCS bucket access: {e}")
            else:
                logger.warning("⚠ GENMEDIA_BUCKET not configured")
                self.results["skipped"].append("GENMEDIA_BUCKET configuration")
            
            self.results["passed"].append("GCS client initialization")
            return True
            
        except Exception as e:
            logger.error(f"✗ GCS integration verification failed: {e}")
            self.results["failed"].append(f"GCS integration: {e}")
            return False
    
    async def cleanup(self):
        """Cleanup verification resources."""
        logger.info("\nCleaning up...")
        
        if self.telemetry:
            shutdown_telemetry()
            logger.info("✓ Telemetry shutdown")
    
    async def run(self):
        """Run all verifications."""
        logger.info("=" * 60)
        logger.info("Veo3 MCP Service Verification")
        logger.info("=" * 60)
        
        # Setup
        if not await self.setup():
            logger.error("Setup failed, aborting verification")
            return False
        
        # Run verifications
        await self.verify_models()
        await self.verify_mcp_tools()
        await self.verify_text_to_video()
        await self.verify_image_to_video()
        await self.verify_gcs_integration()
        
        # Cleanup
        await self.cleanup()
        
        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("Verification Summary")
        logger.info("=" * 60)
        
        logger.info(f"\n✓ Passed: {len(self.results['passed'])}")
        for item in self.results["passed"]:
            logger.info(f"  - {item}")
        
        if self.results["failed"]:
            logger.info(f"\n✗ Failed: {len(self.results['failed'])}")
            for item in self.results["failed"]:
                logger.info(f"  - {item}")
        
        if self.results["skipped"]:
            logger.info(f"\n⚠ Skipped: {len(self.results['skipped'])}")
            for item in self.results["skipped"]:
                logger.info(f"  - {item}")
        
        # Overall result
        logger.info("\n" + "=" * 60)
        if not self.results["failed"]:
            logger.info("✓ All critical verifications passed!")
            return True
        else:
            logger.error("✗ Some verifications failed!")
            return False


async def main():
    """Main entry point."""
    verifier = Veo3Verifier()
    success = await verifier.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())