# Critical Fixes Applied

## Issues Fixed

### 1. ✅ Session Termination Bug
**Problem**: `AgentSession.wait_for_completion()` doesn't exist in LiveKit SDK, causing premature session termination.

**Fix Applied**: Replaced with proper participant disconnect detection loop in `agent.py`.

**Before**:
```python
await session.wait_for_completion()  # This method doesn't exist!
```

**After**:
```python
while True:
    if participant not in room.remote_participants.values():
        break
    if room.connection_state == rtc.ConnectionState.CONN_DISCONNECTED:
        break
    await asyncio.sleep(1.0)
```

---

### 2. ⚠️ RLS Policy Violation (Requires DB Migration)
**Problem**: Conversation state updates fail with RLS policy error:
```
new row violates row-level security policy for table "conversation_state"
```

**Root Cause**: 
- Using ANON key instead of SERVICE_ROLE key
- Original RLS policy missing `WITH CHECK` clause for INSERT/UPDATE operations

**Fixes Required**:

#### A. Run SQL Migration
Execute `migrations/fix_conversation_state_rls.sql` in your Supabase SQL editor:

```sql
-- Drop old policy
DROP POLICY IF EXISTS "Service role has full access to conversation_state" ON conversation_state;

-- Create new policy with both USING and WITH CHECK
CREATE POLICY "Service role full access"
    ON conversation_state
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
```

#### B. Set SERVICE_ROLE Key
Add to your environment variables (Railway/Docker):

```bash
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here
```

**How to find your service role key**:
1. Go to Supabase Dashboard → Project Settings → API
2. Copy the `service_role` key (NOT the `anon` key)
3. Add it to your environment variables

**Why this matters**:
- ANON key: Limited access, subject to RLS policies checking `auth.uid()`
- SERVICE_ROLE key: Full database access, bypasses RLS when policies check `auth.role() = 'service_role'`

---

### 3. ✅ Gender Detection Timeout
**Problem**: Gender detection times out after 3 seconds.

**Status**: This is a warning, not a blocker. The system continues without gender detection.

**Optional Fix**: Increase timeout in profile service if needed, or remove gender detection if not critical.

---

## Deployment Steps

### Immediate (Code Changes Applied)
1. ✅ Fixed session termination loop in `agent.py`
2. ✅ Added better error handling in cleanup

### Required (Database + Config)
1. **Run SQL Migration**:
   ```bash
   # Copy contents of migrations/fix_conversation_state_rls.sql
   # Paste into Supabase SQL Editor
   # Execute
   ```

2. **Update Environment Variables**:
   ```bash
   # In Railway or your deployment platform
   SUPABASE_SERVICE_ROLE_KEY=your-actual-service-role-key
   ```

3. **Restart Application**:
   ```bash
   # Railway will auto-restart on env var change
   # Or manually restart your container
   ```

### Verification
After deploying, check logs for:
- ✅ `[SUPABASE] Connected using SERVICE_ROLE key (pooled)`
- ✅ `[STATE SERVICE] Updated state - Stage: X, Trust: Y`
- ✅ No more RLS policy violations

---

## Testing Checklist

- [ ] Logs show "SERVICE_ROLE key" (not "ANON key")
- [ ] Session stays alive during full conversation
- [ ] No RLS policy violation errors
- [ ] Conversation state updates successfully
- [ ] Agent responds normally in Urdu
- [ ] Session cleanup happens after disconnect

---

## Troubleshooting

### Still seeing RLS errors after migration?
1. Verify SERVICE_ROLE_KEY is set correctly
2. Check Supabase logs for policy evaluation
3. Temporarily disable RLS to test: `ALTER TABLE conversation_state DISABLE ROW LEVEL SECURITY;` (not recommended for production)

### Session still terminating early?
1. Check if there are any exceptions in the conversation loop
2. Verify participant disconnect detection is working
3. Add more logging around the session loop

### Gender detection timing out?
1. This is non-critical - system works without it
2. To fix: increase timeout or remove the feature
3. Check OpenAI API rate limits

---

## Architecture Notes

**Why SERVICE_ROLE key is needed**:
When your backend makes requests to Supabase, there's no authenticated user session (no JWT token). The RLS policies that check `auth.uid() = user_id` will fail because `auth.uid()` returns NULL. The SERVICE_ROLE key bypasses these checks when the policy checks `auth.role() = 'service_role'`.

**Security**:
- SERVICE_ROLE key should NEVER be exposed to clients
- Keep it in backend environment variables only
- It has full database access, so protect it carefully

**Alternative approach** (if you can't use SERVICE_ROLE):
You could restructure to use anon key with JWT auth, but this requires implementing user authentication flow, which is more complex.

