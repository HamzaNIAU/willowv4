# YouTube Toggle System Test Guide

## Test Scenarios to Verify the New Toggle System

### 1. Connect YouTube Channel Test
**What to say to the agent:**
```
"Upload my latest video to YouTube with the title 'Test Upload' and description 'Testing the new system'"
```

**Expected behavior:**
- Agent should respond that no YouTube channels are connected
- Should NOT see any channels even if you have them in Social Hub
- This confirms channels default to disabled

### 2. Enable Channel for Agent Test
**Steps:**
1. First, go to Social Hub and connect a YouTube channel (if not already connected)
2. Go to your agent's chat
3. Click the social media dropdown (plug icon) in the chat input
4. You should see your YouTube channel with a toggle - it should be OFF by default
5. Turn the toggle ON for this specific agent
6. Now say to the agent:
```
"List my connected YouTube channels"
```

**Expected behavior:**
- Agent should now see and list the YouTube channel you enabled
- Only the channels you toggled ON should be visible

### 3. Multi-Agent Isolation Test
**Steps:**
1. Create or use two different agents
2. Enable YouTube for Agent A but not Agent B
3. Test with Agent A:
```
"Show me my YouTube channels"
```
4. Test with Agent B:
```
"Show me my YouTube channels"
```

**Expected behavior:**
- Agent A sees the channel
- Agent B sees no channels
- This confirms agent-specific toggle isolation

### 4. Upload Test with Enabled Channel
**After enabling a channel for an agent, say:**
```
"Upload a video to YouTube with:
- Title: Test Video Upload
- Description: Testing the new toggle system
- File: [attach a small test video file]"
```

**Expected behavior:**
- Agent should successfully initiate the upload
- Should use only the enabled channel

### 5. Toggle Off Test
**Steps:**
1. With a channel previously enabled, toggle it OFF in the dropdown
2. Say to the agent:
```
"List my YouTube channels"
```

**Expected behavior:**
- Agent should no longer see any channels
- Confirms real-time toggle updates

### 6. Disconnect and Reconnect Test
**Steps:**
1. Go to Social Hub
2. Disconnect your YouTube channel
3. Check the agent chat - channel should disappear from dropdown
4. Reconnect the YouTube channel in Social Hub
5. Check the agent chat - channel should reappear (but OFF by default)

**Expected behavior:**
- Clean removal and re-addition
- No orphaned entries
- New connections default to disabled

### 7. Channel Details Test
**With channel enabled, say:**
```
"Show me details about my YouTube channel including subscriber count"
```

**Expected behavior:**
- Agent fetches and displays channel statistics
- Only works when channel is enabled

### 8. Multiple Channels Test
**If you have multiple YouTube channels:**
1. Connect 2+ channels in Social Hub
2. Enable only one for the agent
3. Say:
```
"Which YouTube channels can I upload to?"
```

**Expected behavior:**
- Agent only sees the enabled channel(s)
- Disabled channels remain hidden

## Quick Test Commands

### Basic Commands to Test:
1. `"Do I have any YouTube channels connected?"` - Tests visibility
2. `"Upload a test video to YouTube"` - Tests upload access
3. `"Get my YouTube channel statistics"` - Tests API access
4. `"List all my social media connections"` - Tests filtering

## Verification Checklist

- [ ] Channels default to OFF when connected ✅
- [ ] Only enabled channels visible to agents ✅
- [ ] Toggle changes take effect immediately ✅
- [ ] Each agent has independent toggle states ✅
- [ ] Disconnecting removes all toggles cleanly ✅
- [ ] Reconnecting creates new toggles (OFF by default) ✅
- [ ] Upload only works with enabled channels ✅
- [ ] Channel info only accessible when enabled ✅

## Troubleshooting

### If agent sees channels that should be disabled:
1. Check the toggle state in the dropdown
2. Refresh the page and check again
3. The agent should only see channels with green/enabled toggles

### If toggles don't appear in dropdown:
1. Make sure you've connected a channel in Social Hub first
2. Refresh the agent chat page
3. Look for the plug icon in the chat input area

### If uploads fail even with enabled channel:
1. Verify the channel is properly connected in Social Hub
2. Check that the toggle is ON for this specific agent
3. Try disconnecting and reconnecting the channel

## Security Benefits Demonstrated

1. **No Accidental Exposure**: New channels don't automatically become available to all agents
2. **Granular Control**: Each agent can have different channel access
3. **Explicit Permission**: Users must intentionally enable each channel per agent
4. **Clean State Management**: No leftover permissions after disconnect

## Expected Log Messages

When testing, you might see these in the Docker logs:
- `"No toggle found for social MCP social.youtube.XXX, defaulting to disabled"`
- `"Created MCP toggle for agent XXX, channel YYY (disabled by default)"`
- `"Filtering out disabled YouTube channel: XXX"`

These confirm the security-first approach is working correctly.