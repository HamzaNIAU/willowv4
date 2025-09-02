"""YouTube Sandbox Tool - Clean Implementation Following Proven Pattern"""

from typing import Dict, Any, Optional
from sandbox.tool_base import SandboxToolsBase
from agentpress.tool import ToolResult, openapi_schema
from agentpress.thread_manager import ThreadManager
from daytona_sdk import SessionExecuteRequest
from uuid import uuid4
import json
from utils.logger import logger


class YouTubeTool(SandboxToolsBase):
    """YouTube tool that follows exact same pattern as working sandbox tools"""
    
    def __init__(self, project_id: str, thread_manager: ThreadManager, user_id: str, agent_id: Optional[str] = None, jwt_token: Optional[str] = None, **kwargs):
        super().__init__(project_id, thread_manager)
        self.user_id = user_id
        self.agent_id = agent_id
        self.jwt_token = jwt_token
        # Use internal Docker network since we're in the same backend
        self.backend_url = "http://localhost:8000"
        
        logger.info(f"[YouTube Clean Tool] Initialized for user {user_id}, agent {agent_id}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_upload_video",
            "description": "Upload video to YouTube via Daytona sandbox - agent can monitor execution",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Video title"
                    },
                    "description": {
                        "type": "string", 
                        "description": "Video description (optional)"
                    },
                    "privacy": {
                        "type": "string",
                        "enum": ["public", "private", "unlisted"],
                        "description": "Privacy setting (default: public)"
                    }
                },
                "required": ["title"]
            }
        }
    })
    async def youtube_upload_video(
        self,
        title: str,
        description: str = "",
        privacy: str = "public"
    ) -> ToolResult:
        """Upload video to YouTube - EXACT same pattern as sb_shell_tool.py"""
        try:
            # STEP 1: Ensure sandbox (same as other tools)
            await self._ensure_sandbox()
            
            # STEP 2: Create session (same pattern as sb_shell_tool)
            session_id = f"youtube-upload-{str(uuid4())[:8]}"
            await self.sandbox.process.create_session(session_id)
            
            # STEP 3: Prepare command (simple curl to working backend)
            escaped_title = title.replace('"', '\\"')
            escaped_desc = description.replace('"', '\\"')
            
            # Add verbose curl output for debugging
            command = f'''curl -v -X POST {self.backend_url}/api/youtube/universal-upload \\
  -H "Authorization: Bearer {self.jwt_token}" \\
  -H "Content-Type: application/json" \\
  -d '{{"platform": "youtube", "account_id": "auto", "title": "{escaped_title}", "description": "{escaped_desc}", "privacy_status": "{privacy}", "auto_discover": true}}' '''
            
            # STEP 4: Execute (exact same as sb_shell_tool)
            req = SessionExecuteRequest(
                command=command,
                var_async=False,
                cwd="/workspace"
            )
            
            response = await self.sandbox.process.execute_session_command(
                session_id=session_id,
                req=req,
                timeout=15  # Much shorter timeout to get faster error feedback
            )
            
            logs = await self.sandbox.process.get_session_command_logs(
                session_id=session_id,
                command_id=response.cmd_id
            )
            
            logger.info(f"[YouTube Clean] Exit code: {response.exit_code}, Logs: {logs}")
            
            # STEP 5: Check database for final result if command succeeded
            if response.exit_code == 0:
                # Parse upload_id from curl response if available
                upload_id = None
                try:
                    if '{' in logs and 'upload_id' in logs:
                        # Try to parse JSON response from curl
                        for line in logs.strip().split('\\n'):
                            if line.strip().startswith('{'):
                                result_json = json.loads(line.strip())
                                upload_id = result_json.get('upload_id')
                                break
                except:
                    pass
                
                # Query database for upload status using sandbox
                if upload_id:
                    # Wait a moment for upload to process
                    wait_cmd = "sleep 5"
                    await self.sandbox.process.execute_session_command(session_id, SessionExecuteRequest(command=wait_cmd, cwd="/workspace"), timeout=10)
                    
                    # Query database via backend API to get final video status
                    status_cmd = f'''curl -s -H "Authorization: Bearer {self.jwt_token}" {self.backend_url}/api/youtube/upload-status/{upload_id}'''
                    
                    status_req = SessionExecuteRequest(command=status_cmd, var_async=False, cwd="/workspace")
                    status_response = await self.sandbox.process.execute_session_command(session_id, status_req, timeout=30)
                    status_logs = await self.sandbox.process.get_session_command_logs(session_id, status_response.cmd_id)
                    
                    # Parse final upload status
                    try:
                        if status_response.exit_code == 0:
                            status_data = json.loads(status_logs.strip())
                            video_id = status_data.get('video', {}).get('video_id')
                            
                            if video_id:
                                video_url = f"https://www.youtube.com/watch?v={video_id}"
                                return self.success_response(
                                    f"🎉 **YouTube Upload Successful!**\\n\\n"
                                    f"🎬 **Title**: {title}\\n"
                                    f"🆔 **Video ID**: {video_id}\\n"
                                    f"🔗 **YouTube URL**: {video_url}\\n\\n"
                                    f"⚡ **Sandbox Execution**: Complete\\n"
                                    f"📤 **Upload ID**: {upload_id}"
                                )
                            else:
                                return self.success_response(
                                    f"📤 **Upload Started Successfully**\\n\\n"
                                    f"🎬 **Title**: {title}\\n"
                                    f"📤 **Upload ID**: {upload_id}\\n\\n"
                                    f"Upload is processing... Video will be available shortly!"
                                )
                    except:
                        pass
                
                # Fallback success response
                return self.success_response(
                    f"✅ **YouTube Upload Command Executed**\\n\\n"
                    f"🎬 **Title**: {title}\\n"
                    f"⚡ **Sandbox Response**: {logs}\\n\\n"
                    f"Upload command completed successfully in Daytona sandbox!"
                )
            else:
                return self.fail_response(
                    f"❌ **Upload Command Failed**\\n\\n"
                    f"Exit code: {response.exit_code}\\n"
                    f"Error output: {logs}"
                )
                
        except Exception as e:
            logger.error(f"[YouTube Clean] Exception: {e}", exc_info=True)
            return self.fail_response(f"Sandbox execution error: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_check_recent_uploads",
            "description": "Check for recent successful YouTube uploads that may have been missed due to connection issues",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    })
    async def youtube_check_recent_uploads(self) -> ToolResult:
        """Check database for recent successful uploads"""
        try:
            await self._ensure_sandbox()
            
            session_id = f"youtube-check-{str(uuid4())[:8]}"
            await self.sandbox.process.create_session(session_id)
            
            # Query database via backend API for recent successful uploads
            check_cmd = f'''curl -s -H "Authorization: Bearer {self.jwt_token}" "{self.backend_url}/api/youtube/recent-uploads?limit=5"'''
            
            req = SessionExecuteRequest(command=check_cmd, var_async=False, cwd="/workspace")
            response = await self.sandbox.process.execute_session_command(session_id, req, timeout=30)
            logs = await self.sandbox.process.get_session_command_logs(session_id, response.cmd_id)
            
            if response.exit_code == 0:
                try:
                    uploads_data = json.loads(logs.strip())
                    if uploads_data.get('success') and uploads_data.get('uploads'):
                        uploads = uploads_data['uploads']
                        successful_uploads = [u for u in uploads if u.get('video_id')]
                        
                        if successful_uploads:
                            message = f"🎉 **Found {len(successful_uploads)} Recent Successful Upload(s):**\\n\\n"
                            for upload in successful_uploads:
                                video_id = upload['video_id']
                                title = upload['title']
                                video_url = f"https://www.youtube.com/watch?v={video_id}"
                                message += f"🎬 **{title}**\\n🔗 {video_url}\\n\\n"
                            
                            return self.success_response(message)
                        else:
                            return self.success_response("No recent successful uploads found.")
                    else:
                        return self.success_response("No recent uploads found.")
                except:
                    return self.success_response(f"Recent uploads query executed: {logs}")
            else:
                return self.fail_response(f"Failed to check recent uploads: {logs}")
                
        except Exception as e:
            return self.fail_response(f"Error checking uploads: {str(e)}")

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_channels",
            "description": "Get YouTube channels via sandbox execution",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    })
    async def youtube_channels(self) -> ToolResult:
        """Get YouTube channels - same pattern as other sandbox tools"""
        try:
            # Same pattern as upload method
            await self._ensure_sandbox()
            
            session_id = f"youtube-channels-{str(uuid4())[:8]}"
            await self.sandbox.process.create_session(session_id)
            
            command = f'curl -s -H "Authorization: Bearer {self.jwt_token}" {self.backend_url}/api/youtube/channels'
            
            req = SessionExecuteRequest(command=command, var_async=False, cwd="/workspace")
            response = await self.sandbox.process.execute_session_command(session_id, req, timeout=30)
            logs = await self.sandbox.process.get_session_command_logs(session_id, response.cmd_id)
            
            if response.exit_code == 0:
                return self.success_response(f"📺 **YouTube Channels**\\n\\nSandbox output: {logs}")
            else:
                return self.fail_response(f"Failed to get channels: {logs}")
                
        except Exception as e:
            logger.error(f"[YouTube Clean] Channels error: {e}")
            return self.fail_response(f"Error: {str(e)}")