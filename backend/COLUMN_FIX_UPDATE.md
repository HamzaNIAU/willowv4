# Database Column Fix Update

## Issue Discovered
The agents table uses `account_id` to reference users, not `created_by` as initially assumed.

## Files Fixed

### 1. `backend/cleanup_mcp_toggles.py`
- Line 125: Changed `"created_by"` to `"account_id"` 
- Line 179: Changed `"created_by"` to `"account_id"`

### 2. `backend/services/mcp_toggles.py`
- Line 214: Changed `"created_by"` to `"account_id"` in `enable_channel_for_all_agents()`
- Line 251: Changed `"created_by"` to `"account_id"` in `disable_channel_for_all_agents()`

### 3. `backend/youtube_mcp/oauth.py`
- Line 247: Changed `"created_by"` to `"account_id"` in `_create_channel_toggles()`

### 4. `backend/supabase/migrations/20250820_cleanup_orphaned_mcp_toggles.sql`
- Line 46: Changed `a.created_by` to `a.account_id` in the PL/pgSQL function

## Verification
Successfully ran the cleanup script with the fixes:
- Removed 1 orphaned toggle entry
- Verified data consistency: 2 toggles exist as expected
- No errors encountered

## Impact
This fix ensures that:
- MCP toggles are correctly associated with agents
- The cleanup script properly identifies and manages toggle entries
- Database queries correctly reference the user-agent relationship