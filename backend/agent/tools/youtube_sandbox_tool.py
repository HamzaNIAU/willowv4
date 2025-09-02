"""YouTube Sandbox Tool - Runs in Daytona for Agent Visibility"""

from typing import Dict, Any, Optional, List
from sandbox.tool_base import SandboxToolsBase
from agentpress.tool import ToolResult, openapi_schema
from agentpress.thread_manager import ThreadManager
from daytona_sdk import SessionExecuteRequest
import json
import time
from datetime import datetime, timezone
from utils.logger import logger


class YouTubeSandboxTool(SandboxToolsBase):
    """YouTube integration tool that runs in Daytona sandbox for full agent visibility"""
    
    def __init__(self, project_id: str, thread_manager: ThreadManager, user_id: str, agent_id: Optional[str] = None, jwt_token: Optional[str] = None):
        super().__init__(project_id, thread_manager)
        self.user_id = user_id
        self.agent_id = agent_id
        self.jwt_token = jwt_token
        self.backend_url = "http://backend:8000"  # Docker internal network
        
        logger.info(f"[YouTube Sandbox Tool] Initialized for user {user_id}, agent {agent_id}")
    
    async def _setup_sandbox_environment(self):
        """Set up the sandbox environment with YouTube capabilities - optimized for speed"""
        await self._ensure_sandbox()
        
        # Quick environment setup without heavy package installation
        quick_setup = f"""
mkdir -p /workspace/youtube_scripts
cat > /workspace/.youtube_env << 'EOF'
export BACKEND_URL="{self.backend_url}"
export USER_ID="{self.user_id}"
export AGENT_ID="{self.agent_id}"  
export JWT_TOKEN="{self.jwt_token}"
EOF
"""
        
        setup_result = await self._execute_command(quick_setup, timeout=10)
        if not setup_result["success"]:
            logger.error(f"Failed quick setup: {setup_result['output']}")
            return False
        
        logger.info("[YouTube Sandbox Tool] Quick environment setup completed")
        return True
    
    async def _execute_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute command in sandbox and return structured result"""
        session_id = f"youtube-{int(time.time())}"
        
        try:
            # Create session
            await self.sandbox.process.create_session(session_id)
            
            # Execute command
            req = SessionExecuteRequest(
                command=f"source /workspace/.youtube_env 2>/dev/null; {command}",
                var_async=False,
                cwd="/workspace"
            )
            
            response = await self.sandbox.process.execute_session_command(
                session_id=session_id,
                req=req,
                timeout=timeout
            )
            
            # Get logs
            logs = await self.sandbox.process.get_session_command_logs(
                session_id=session_id,
                command_id=response.cmd_id
            )
            
            return {
                "success": response.exit_code == 0,
                "output": logs.strip(),
                "exit_code": response.exit_code
            }
            
        except Exception as e:
            logger.error(f"[YouTube Sandbox] Command execution failed: {e}")
            return {
                "success": False,
                "output": str(e),
                "exit_code": -1
            }
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_upload_video",
            "description": "Upload video to YouTube with agent visibility via Daytona sandbox execution",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "YouTube channel ID to upload to"
                    },
                    "title": {
                        "type": "string", 
                        "description": "Video title"
                    },
                    "description": {
                        "type": "string",
                        "description": "Video description"
                    },
                    "privacy": {
                        "type": "string",
                        "enum": ["public", "private", "unlisted"],
                        "description": "Privacy setting (default: public)"
                    },
                    "video_reference_id": {
                        "type": "string",
                        "description": "Reference ID of video file"
                    }
                },
                "required": ["title"]
            }
        }
    })
    async def youtube_upload_video(
        self,
        title: str,
        channel_id: Optional[str] = None,
        description: str = "",
        privacy: str = "public",
        video_reference_id: Optional[str] = None
    ) -> ToolResult:
        """Upload video to YouTube via sandbox execution"""
        try:
            logger.info(f"[YouTube Sandbox Upload] Starting upload: {title}")
            
            # Setup sandbox environment
            if not await self._setup_sandbox_environment():
                return self.fail_response("Failed to setup sandbox environment")
            
            # Create upload command for sandbox execution
            upload_params = {
                "title": title,
                "description": description,
                "privacy": privacy,
                "channel_id": channel_id,
                "video_reference_id": video_reference_id
            }
            
            # Simple curl-based upload to existing backend API (much faster)
            upload_command = f"""
source /workspace/.youtube_env
curl -X POST ${{BACKEND_URL}}/api/youtube/universal-upload \\
  -H "Authorization: Bearer ${{JWT_TOKEN}}" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "platform": "youtube",
    "account_id": "{channel_id or 'auto'}",
    "title": "{title}",
    "description": "{description}",
    "tags": {json.dumps(tags)},
    "privacy_status": "{privacy}",
    "video_reference_id": "{video_reference_id or 'auto'}",
    "auto_discover": true
  }}'
"""
            
            # Execute in sandbox
            logger.info("[YouTube Sandbox Upload] Executing upload in Daytona sandbox...")
            result = await self._execute_command(upload_command, timeout=300)
            
            # Parse result
            if result["success"]:
                try:
                    # Parse JSON output from sandbox
                    output_lines = result["output"].strip().split('\n')
                    last_line = output_lines[-1]
                    upload_result = json.loads(last_line)
                    
                    if upload_result.get("success"):
                        return self.success_response({
                            "message": f"✅ **Sandbox Upload Success!**\n\n{upload_result.get('message', '')}",
                            "sandbox_executed": True,
                            "result": upload_result
                        })
                    else:
                        return self.fail_response(f"Upload failed: {upload_result.get('error', 'Unknown error')}")
                        
                except json.JSONDecodeError:
                    return self.success_response({
                        "message": f"Upload command executed in sandbox",
                        "output": result["output"],
                        "sandbox_executed": True
                    })
            else:
                return self.fail_response(f"Sandbox execution failed: {result['output']}")
                
        except Exception as e:
            logger.error(f"[YouTube Sandbox Upload] Error: {e}", exc_info=True)
            return self.fail_response(f"Upload failed: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_channels",
            "description": "Get connected YouTube channels via sandbox execution",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    })
    async def youtube_channels(self) -> ToolResult:
        """Get YouTube channels via sandbox execution"""
        try:
            logger.info("[YouTube Sandbox] Getting channels...")
            
            # Setup sandbox environment
            if not await self._setup_sandbox_environment():
                return self.fail_response("Failed to setup sandbox environment")
            
            # Execute channel fetch in sandbox
            channel_command = f"python -c \"\n\
import json, requests, os\n\
backend_url = os.getenv('BACKEND_URL', 'http://backend:8000')\n\
jwt_token = os.getenv('JWT_TOKEN')\n\
agent_id = os.getenv('AGENT_ID')\n\
\n\
r = requests.get(f'{{backend_url}}/api/youtube/sandbox/channels/enabled/{{agent_id}}', headers={{'Authorization': f'Bearer {{jwt_token}}'}}))\n\
if r.status_code == 200:\n\
    result = r.json()\n\
    channels = result.get('channels', [])\n\
    print(json.dumps({{'success': True, 'channels': channels, 'count': len(channels)}}))\n\
else:\n\
    print(json.dumps({{'success': False, 'error': f'API error: {{r.status_code}}'}}))\n\
\""
            
            result = await self._execute_command(channel_command)
            
            if result["success"]:
                try:
                    output_lines = result["output"].strip().split('\n')
                    last_line = output_lines[-1]
                    channel_result = json.loads(last_line)
                    
                    if channel_result.get("success"):
                        channels = channel_result.get("channels", [])
                        return self.success_response({
                            "message": f"Found {len(channels)} YouTube channels",
                            "channels": channels,
                            "count": len(channels),
                            "has_channels": len(channels) > 0,
                            "sandbox_executed": True
                        })
                    else:
                        return self.fail_response(channel_result.get("error", "Failed to get channels"))
                        
                except json.JSONDecodeError:
                    return self.success_response({
                        "message": "Channel command executed",
                        "output": result["output"],
                        "sandbox_executed": True
                    })
            else:
                return self.fail_response(f"Sandbox execution failed: {result['output']}")
                
        except Exception as e:
            logger.error(f"[YouTube Sandbox] Error getting channels: {e}")
            return self.fail_response(f"Failed to get channels: {str(e)}")