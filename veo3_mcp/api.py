"""
FastAPI router for Veo3 MCP service.

This module provides REST API endpoints for video generation,
operation status checking, and model management.
"""

import logging
from typing import List, Optional, Dict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse

from .auth import verify_token, verify_agent_permission, permission_manager
from .config import get_config, list_available_models, get_mcp_id_for_model
from .models import (
    TextToVideoRequest, ImageToVideoRequest, VideoGenerationResponse,
    OperationStatusRequest, ListModelsResponse, ProgressUpdate,
    JWTPayload, Veo3ModelName
)
from .veo3_service import Veo3Service
from .utils import cache_result


logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/veo3",
    tags=["veo3"],
    responses={404: {"description": "Not found"}},
)

# Initialize service
veo3_service = Veo3Service()

# WebSocket connections for progress updates
websocket_connections: Dict[str, WebSocket] = {}


@router.post("/generate/text-to-video", response_model=VideoGenerationResponse)
async def generate_text_to_video(
    request: TextToVideoRequest,
    payload: JWTPayload = Depends(verify_token)
) -> VideoGenerationResponse:
    """
    Generate video from text prompt.
    
    This endpoint initiates a text-to-video generation operation using
    the specified Veo3 model. The operation runs asynchronously and
    returns an operation ID for tracking progress.
    
    Args:
        request: Text-to-video generation parameters
        payload: JWT payload with user information
    
    Returns:
        Video generation response with operation ID
    
    Raises:
        HTTPException: If generation fails or permission denied
    """
    # Check model permission
    mcp_id = get_mcp_id_for_model(request.model)
    if payload.agent_id:
        has_permission = await permission_manager.check_permission(
            payload.agent_id,
            mcp_id
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Agent does not have permission for model {request.model.value}"
            )
    
    try:
        # Add project ID from token
        if not request.bucket and payload.project_id:
            request.bucket = f"{payload.project_id}-veo3-outputs"
        
        # Generate video
        response = await veo3_service.generate_video_from_text(
            request,
            progress_callback=lambda update: send_progress_update(
                update,
                payload.user_id
            )
        )
        
        logger.info(
            f"Started text-to-video generation for user {payload.user_id}: "
            f"operation_id={response.operation_id}"
        )
        
        return response
    
    except Exception as e:
        logger.error(f"Text-to-video generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video generation failed: {str(e)}"
        )


@router.post("/generate/image-to-video", response_model=VideoGenerationResponse)
async def generate_image_to_video(
    request: ImageToVideoRequest,
    payload: JWTPayload = Depends(verify_token)
) -> VideoGenerationResponse:
    """
    Generate video from image with optional prompt.
    
    This endpoint initiates an image-to-video generation operation using
    the specified Veo3 model. The input image must be stored in GCS.
    
    Args:
        request: Image-to-video generation parameters
        payload: JWT payload with user information
    
    Returns:
        Video generation response with operation ID
    
    Raises:
        HTTPException: If generation fails or permission denied
    """
    # Check model permission
    mcp_id = get_mcp_id_for_model(request.model)
    if payload.agent_id:
        has_permission = await permission_manager.check_permission(
            payload.agent_id,
            mcp_id
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Agent does not have permission for model {request.model.value}"
            )
    
    try:
        # Add project ID from token
        if not request.bucket and payload.project_id:
            request.bucket = f"{payload.project_id}-veo3-outputs"
        
        # Generate video
        response = await veo3_service.generate_video_from_image(
            request,
            progress_callback=lambda update: send_progress_update(
                update,
                payload.user_id
            )
        )
        
        logger.info(
            f"Started image-to-video generation for user {payload.user_id}: "
            f"operation_id={response.operation_id}"
        )
        
        return response
    
    except Exception as e:
        logger.error(f"Image-to-video generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video generation failed: {str(e)}"
        )


@router.get("/operations/{operation_id}", response_model=VideoGenerationResponse)
async def get_operation_status(
    operation_id: str,
    payload: JWTPayload = Depends(verify_token)
) -> VideoGenerationResponse:
    """
    Get the status of a video generation operation.
    
    Args:
        operation_id: ID of the operation to check
        payload: JWT payload with user information
    
    Returns:
        Current operation status and results
    
    Raises:
        HTTPException: If operation not found
    """
    response = await veo3_service.get_operation_status(operation_id)
    
    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operation {operation_id} not found"
        )
    
    # Verify user owns this operation (in production, check database)
    # For now, we'll allow any authenticated user to check status
    
    return response


@router.delete("/operations/{operation_id}")
async def cancel_operation(
    operation_id: str,
    payload: JWTPayload = Depends(verify_token)
) -> JSONResponse:
    """
    Cancel a running video generation operation.
    
    Args:
        operation_id: ID of the operation to cancel
        payload: JWT payload with user information
    
    Returns:
        Success response if cancelled
    
    Raises:
        HTTPException: If operation not found or cannot be cancelled
    """
    cancelled = await veo3_service.cancel_operation(operation_id)
    
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operation {operation_id} not found or already completed"
        )
    
    logger.info(f"Cancelled operation {operation_id} for user {payload.user_id}")
    
    return JSONResponse(
        content={"message": f"Operation {operation_id} cancelled successfully"}
    )


@router.get("/models", response_model=ListModelsResponse)
@cache_result(ttl_seconds=300)  # Cache for 5 minutes
async def list_models(
    payload: JWTPayload = Depends(verify_token)
) -> ListModelsResponse:
    """
    List available Veo3 models.
    
    Returns models that the authenticated user/agent has permission to use.
    
    Args:
        payload: JWT payload with user information
    
    Returns:
        List of available models with their specifications
    """
    all_models = list_available_models()
    
    # Filter models based on agent permissions
    if payload.agent_id:
        permitted_models = []
        for model in all_models:
            mcp_id = get_mcp_id_for_model(model.name)
            has_permission = await permission_manager.check_permission(
                payload.agent_id,
                mcp_id
            )
            if has_permission:
                permitted_models.append(model)
        
        models = permitted_models
    else:
        # User has access to all models
        models = all_models
    
    return ListModelsResponse(
        models=models,
        default_model=Veo3ModelName.VEO_2_GENERATE
    )


@router.websocket("/progress")
async def websocket_progress(
    websocket: WebSocket,
    token: str
):
    """
    WebSocket endpoint for real-time progress updates.
    
    Clients can connect to this endpoint to receive real-time progress
    updates for their video generation operations.
    
    Args:
        websocket: WebSocket connection
        token: JWT token for authentication
    """
    try:
        # Verify token
        from .auth import token_manager
        payload = token_manager.decode_jwt(token)
        
        await websocket.accept()
        
        # Store connection
        user_id = payload.user_id
        websocket_connections[user_id] = websocket
        
        logger.info(f"WebSocket connected for user {user_id}")
        
        # Keep connection alive
        while True:
            # Wait for messages (ping/pong or close)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {payload.user_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Remove connection
        websocket_connections.pop(payload.user_id, None)


async def send_progress_update(update: ProgressUpdate, user_id: str):
    """
    Send progress update to connected WebSocket client.
    
    Args:
        update: Progress update to send
        user_id: User ID to send update to
    """
    websocket = websocket_connections.get(user_id)
    if websocket:
        try:
            await websocket.send_json(update.dict())
        except Exception as e:
            logger.error(f"Failed to send progress update: {e}")
            # Remove dead connection
            websocket_connections.pop(user_id, None)


# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "veo3-mcp",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# Permissions management endpoints
@router.post("/permissions/grant")
async def grant_permission(
    agent_id: str,
    mcp_id: str,
    payload: JWTPayload = Depends(verify_token)
) -> JSONResponse:
    """
    Grant MCP permission to an agent.
    
    Args:
        agent_id: Agent to grant permission to
        mcp_id: MCP permission ID to grant
        payload: JWT payload (must be admin)
    
    Returns:
        Success response
    """
    # In production, check if user is admin
    # For now, any authenticated user can grant permissions
    
    await permission_manager.grant_permission(agent_id, mcp_id)
    
    logger.info(f"Granted permission {mcp_id} to agent {agent_id}")
    
    return JSONResponse(
        content={"message": f"Permission {mcp_id} granted to agent {agent_id}"}
    )


@router.post("/permissions/revoke")
async def revoke_permission(
    agent_id: str,
    mcp_id: str,
    payload: JWTPayload = Depends(verify_token)
) -> JSONResponse:
    """
    Revoke MCP permission from an agent.
    
    Args:
        agent_id: Agent to revoke permission from
        mcp_id: MCP permission ID to revoke
        payload: JWT payload (must be admin)
    
    Returns:
        Success response
    """
    # In production, check if user is admin
    
    await permission_manager.revoke_permission(agent_id, mcp_id)
    
    logger.info(f"Revoked permission {mcp_id} from agent {agent_id}")
    
    return JSONResponse(
        content={"message": f"Permission {mcp_id} revoked from agent {agent_id}"}
    )


@router.get("/permissions/{agent_id}")
async def get_agent_permissions(
    agent_id: str,
    payload: JWTPayload = Depends(verify_token)
) -> List[str]:
    """
    Get all permissions for an agent.
    
    Args:
        agent_id: Agent ID to check
        payload: JWT payload
    
    Returns:
        List of MCP permission IDs
    """
    permissions = await permission_manager.get_agent_permissions(agent_id)
    return permissions