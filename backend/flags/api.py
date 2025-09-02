from fastapi import APIRouter
from utils.logger import logger
from .flags import list_flags, is_enabled, get_flag_details, set_flag

router = APIRouter()


@router.get("/feature-flags")
async def get_feature_flags():
    try:
        flags = await list_flags()
        return {"flags": flags}
    except Exception as e:
        logger.error(f"Error fetching feature flags: {str(e)}")
        return {"flags": {}}

@router.get("/feature-flags/{flag_name}")
async def get_feature_flag(flag_name: str):
    try:
        enabled = await is_enabled(flag_name)
        details = await get_flag_details(flag_name)
        return {
            "flag_name": flag_name,
            "enabled": enabled,
            "details": details
        }
    except Exception as e:
        logger.error(f"Error fetching feature flag {flag_name}: {str(e)}")
        return {
            "flag_name": flag_name,
            "enabled": False,
            "details": None
        }

@router.post("/feature-flags/enable-agents-temp")
async def enable_agents_temporarily():
    """Temporarily enable agents for cleanup"""
    try:
        await set_flag("custom_agents", True, "Temporarily enabled for cleanup")
        await set_flag("default_agent", True, "Willow default agent")
        await set_flag("hide_agent_creation", False, "Show agents menu for cleanup")
        await set_flag("agent_marketplace", True, "Agent marketplace features")
        
        flags = await list_flags()
        logger.info(f"Enabled agents temporarily. Current flags: {flags}")
        
        return {
            "success": True,
            "message": "Agents enabled temporarily for cleanup",
            "flags": flags
        }
    except Exception as e:
        logger.error(f"Error enabling agents temporarily: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }