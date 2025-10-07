# 🎯 Quick Fix Card

## Status
- ✅ **Code fixes**: Applied
- ⚠️ **Database fix**: Needs your action
- ⚠️ **Config fix**: Needs your action

---

## What to Do Now

### 1. Apply SQL (2 min) 
Supabase Dashboard → SQL Editor:
```sql
DROP POLICY IF EXISTS "Service role has full access to conversation_state" ON conversation_state;

CREATE POLICY "Service role full access"
    ON conversation_state
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
```

### 2. Add Key to Railway (1 min)
Supabase Dashboard → Settings → API → Copy `service_role` key

Railway Dashboard → Variables:
```
SUPABASE_SERVICE_ROLE_KEY=your-key-here
```

### 3. Verify (30 sec)
Check logs for:
```
✅ [SUPABASE] Connected using SERVICE_ROLE key (pooled)
✅ [STATE SERVICE] Updated state - Stage: X, Trust: Y
✅ [ENTRYPOINT] ✓ Participant disconnected
```

---

## Files to Read

1. **START HERE**: `DEPLOY_FIXES.md` (step-by-step guide)
2. **Details**: `CRITICAL_FIXES_APPLIED.md` (technical deep-dive)
3. **Overview**: `FIXES_SUMMARY.md` (what changed)

---

## What Was Fixed

### In Code (Already Done)
- ✅ Session stays alive during conversations
- ✅ Graceful error handling for RLS issues
- ✅ Better error messages

### After You Deploy
- ✅ Conversation state persists to DB
- ✅ Trust scores saved between sessions
- ✅ No more RLS policy errors

---

## Quick Test
1. Start conversation
2. Say 3-4 things in Urdu
3. Stay connected throughout
4. Check no RLS errors in logs
5. Disconnect
6. Session should cleanup gracefully

---

⏱️ **Total Time**: ~5 minutes
🔒 **Security**: Keep SERVICE_ROLE key secret
📞 **Help**: See `DEPLOY_FIXES.md`

