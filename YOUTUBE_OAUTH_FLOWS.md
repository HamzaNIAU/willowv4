# YouTube OAuth Authentication Flows

## Overview
The YouTube integration supports **two OAuth authentication methods** to connect YouTube channels:

### 1. Agent Chat Authentication (`youtube_authenticate`)
- **Location**: Directly within the agent chat interface
- **Trigger**: Agent uses `youtube_authenticate()` tool
- **Flow**:
  1. Agent calls `youtube_authenticate()` tool
  2. Backend generates OAuth URL via `/api/youtube/auth/initiate`
  3. User sees OAuth button in chat
  4. User clicks button → OAuth popup opens
  5. User authorizes YouTube access
  6. Callback to `/api/youtube/auth/callback`
  7. Success page with channel info
  8. Window closes, chat updates

### 2. Social Media Page Authentication
- **Location**: Dashboard → Social Media page
- **URL**: `/social-media`
- **Flow**:
  1. User navigates to Social Media page
  2. Clicks "Add Account" button for YouTube
  3. Same OAuth endpoint (`/api/youtube/auth/initiate`)
  4. OAuth popup opens
  5. User authorizes YouTube access
  6. Callback to `/api/youtube/auth/callback`
  7. Success page with channel info
  8. Window closes, page refreshes with new channel

## Shared Backend Infrastructure

Both methods use the **same backend endpoints**:

### `/api/youtube/auth/initiate` (POST)
```python
# backend/youtube_mcp/api.py
@router.post("/auth/initiate")
async def initiate_auth(user_id: str) -> Dict[str, Any]:
    """Start YouTube OAuth flow"""
    oauth_handler = YouTubeOAuthHandler(db)
    auth_url = oauth_handler.get_auth_url(state=user_id)
    return {"success": True, "auth_url": auth_url}
```

### `/api/youtube/auth/callback` (GET)
```python
# backend/youtube_mcp/api.py
@router.get("/auth/callback")
async def auth_callback(code: str, state: str):
    """Handle OAuth callback"""
    # Exchange code for tokens
    # Get channel info
    # Save to database
    # Return success HTML
```

## Configuration Requirements

### Environment Variables
```bash
# YouTube OAuth Application (from Google Cloud Console)
YOUTUBE_CLIENT_ID=your_client_id.apps.googleusercontent.com
YOUTUBE_CLIENT_SECRET=your_client_secret
YOUTUBE_REDIRECT_URI=http://localhost:8000/api/youtube/auth/callback

# Token Encryption
MCP_CREDENTIAL_ENCRYPTION_KEY=your_base64_encryption_key
```

### Google Cloud Console Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable YouTube Data API v3
4. Create OAuth 2.0 credentials:
   - Application type: Web application
   - Authorized redirect URIs:
     - Development: `http://localhost:8000/api/youtube/auth/callback`
     - Production: `https://yourdomain.com/api/youtube/auth/callback`

### Required Scopes
```python
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
```

## Enhanced Agent Tool Features

The `youtube_authenticate` tool now includes:

### Smart Existing Channel Detection
```python
youtube_authenticate(check_existing=True)  # Default behavior
```
- Checks if channels are already connected
- Shows connected channels with stats
- Still provides "Add Another Channel" button

### Improved User Experience
- Clear messaging about both authentication methods
- Instructions for MCP toggle management
- Tips for using connected channels

### Response Types
```json
{
  "message": "Connection instructions and status",
  "auth_url": "OAuth URL for authentication",
  "type": "oauth_button",
  "button_text": "Connect YouTube Channel" | "Add Another Channel",
  "existing_channels": [...] // If channels already connected
}
```

## Security Features

### Token Encryption
- Access and refresh tokens are encrypted using Fernet
- Encryption key stored in environment variable
- Tokens never exposed in plaintext

### State Parameter
- User ID passed as state parameter
- Validates user identity during callback
- Prevents CSRF attacks

### Token Refresh
- Automatic token refresh when expired
- Refresh tokens stored securely
- Seamless re-authentication

## Testing Both Flows

### Test Agent Authentication
1. Start a conversation with an agent
2. Ask: "Connect my YouTube channel"
3. Agent will use `youtube_authenticate()` tool
4. OAuth button appears in chat
5. Complete OAuth flow
6. Verify channel appears in MCP dropdown

### Test Social Media Page
1. Navigate to `/social-media` in dashboard
2. Find YouTube in the platforms list
3. Click "Add Account"
4. Complete OAuth flow
5. Verify channel appears in the table
6. Check same channel in agent MCP dropdown

## Troubleshooting

### Common Issues

1. **"No authentication URL received"**
   - Check YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET
   - Verify backend is running

2. **OAuth callback fails**
   - Ensure YOUTUBE_REDIRECT_URI matches Google Console
   - Check network/firewall settings

3. **Channels not appearing in MCP dropdown**
   - Verify database write succeeded
   - Check agent_mcp_toggles table
   - Ensure toggle service is initialized

4. **Token refresh failures**
   - Verify refresh token was saved
   - Check token encryption key consistency
   - Ensure Google API access not revoked

## Best Practices

1. **Always use HTTPS in production** for OAuth callbacks
2. **Rotate encryption keys** periodically
3. **Monitor token expiration** and refresh proactively
4. **Log OAuth events** for debugging
5. **Handle edge cases** like revoked access gracefully