# Quick Deployment Guide - Critical Fixes

## ⚡ Immediate Action Required

Your agent is working but has **2 critical issues** that need fixing:

### Issue 1: Session Terminates Early ✅ FIXED IN CODE
**Status**: Code changes already applied to `agent.py`

### Issue 2: Database State Not Persisting ⚠️ REQUIRES YOUR ACTION
**Status**: Requires SQL migration + environment variable

---

## 🚀 Deploy in 3 Steps

### Step 1: Apply SQL Migration (2 minutes)

1. Open your Supabase Dashboard
2. Go to **SQL Editor**
3. Create new query
4. Paste this SQL:

```sql
-- Fix RLS policies for conversation_state table
DROP POLICY IF EXISTS "Service role has full access to conversation_state" ON conversation_state;

CREATE POLICY "Service role full access"
    ON conversation_state
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
```

5. Click **Run**
6. ✅ You should see "Success. No rows returned"

### Step 2: Add SERVICE_ROLE Key to Railway (3 minutes)

1. Go to **Supabase Dashboard** → **Project Settings** → **API**
2. Find the `service_role` key (NOT the `anon` key)
3. Copy the full key (starts with `eyJhbG...`)

4. Go to **Railway Dashboard** → Your Project → **Variables**
5. Add new variable:
   ```
   SUPABASE_SERVICE_ROLE_KEY=paste-your-service-role-key-here
   ```
6. Save

**⚠️ Important**: Keep this key secret! Never commit to git or expose to clients.

### Step 3: Restart & Verify (1 minute)

1. Railway will auto-restart after adding the env var
2. Wait ~30 seconds for deployment
3. Check logs for these indicators:

**✅ Success indicators:**
```
[SUPABASE] Connected using SERVICE_ROLE key (pooled)
[STATE SERVICE] Updated state - Stage: X, Trust: Y
```

**❌ If you still see:**
```
[SUPABASE] Connected using ANON key (pooled)
[STATE SERVICE] update_state failed: {'message': 'new row violates...
```
→ The SERVICE_ROLE_KEY wasn't set correctly. Double-check step 2.

---

## 🧪 Test Your Fixes

### Quick Test
1. Start a new conversation with your agent
2. Say something in Urdu
3. Stay connected for 2-3 exchanges
4. Check logs:
   - ✅ No RLS policy errors
   - ✅ `[STATE SERVICE] Updated state` messages appear
   - ✅ Session stays alive during conversation
   - ✅ Cleanup happens only after you disconnect

### Full Test
1. Have a 5-minute conversation
2. Disconnect and reconnect
3. Agent should remember context from previous session
4. Trust scores should persist between sessions

---

## 🐛 Troubleshooting

### "Still seeing ANON key in logs"
→ SERVICE_ROLE_KEY not set correctly in Railway
→ Check for typos, extra spaces, or incomplete key

### "RLS errors still appearing"
→ SQL migration not applied
→ Go back to Step 1 and rerun the SQL

### "Session still ending early"
→ Check for exceptions in logs around session loop
→ This should be fixed by code changes

### "Agent not responding in Urdu"
→ This is separate from these fixes
→ Check TTS configuration and OpenAI model settings

---

## 📊 What Changed

### Code Changes (Already Applied)
- ✅ `agent.py`: Fixed session lifecycle management
- ✅ `conversation_state_service.py`: Added graceful RLS error handling
- ✅ Created migration file: `migrations/fix_conversation_state_rls.sql`
- ✅ Created documentation: `CRITICAL_FIXES_APPLIED.md`

### What You Need to Do
- [ ] Run SQL migration in Supabase
- [ ] Add SERVICE_ROLE_KEY to Railway
- [ ] Verify fixes in logs

---

## 🔒 Security Note

The **SERVICE_ROLE key**:
- ✅ Should be in backend environment variables
- ✅ Should be kept secret
- ❌ Never commit to git
- ❌ Never expose to frontend/clients
- ❌ Never log the full key

It has **full database access**, so treat it like a root password.

---

## 📝 After Deployment

Once deployed successfully, you can:
1. Delete temporary files: `agent.py.backup`, `agent.py.before_fixes`
2. Commit the fixes to git (excluding `.env` files)
3. Monitor logs for any new issues

---

## 💬 Expected Behavior After Fixes

### Before Fixes
```
[SUPABASE] Connected using ANON key (pooled)
[ENTRYPOINT] Session ended with exception: 'AgentSession' object has no attribute 'wait_for_completion'
[STATE SERVICE] update_state failed: {'message': 'new row violates row-level security policy...
```

### After Fixes ✨
```
[SUPABASE] Connected using SERVICE_ROLE key (pooled)
[ENTRYPOINT] 🎧 Agent is now listening and ready for conversation...
[STATE SERVICE] Updated state - Stage: ORIENTATION, Trust: 2.0
[STATE SERVICE] Updated state - Stage: ORIENTATION, Trust: 1.0
[ENTRYPOINT] ✓ Participant disconnected
[ENTRYPOINT] ✓ Session completed normally
```

---

## Need Help?

If you're still seeing issues after following these steps:
1. Share the full logs from a test conversation
2. Verify the SQL migration was successful
3. Confirm SERVICE_ROLE_KEY is set in Railway (you can check by echoing first 10 chars)
4. Check Supabase logs in Dashboard → Logs for RLS evaluation errors

Good luck! 🚀

