# Deployment Checklist

## Pre-Deployment ✅

- [x] Code changes applied to `agent.py`
- [x] Code changes applied to `conversation_state_service.py`
- [x] SQL migration created
- [x] Documentation created

## Your Action Items

### Database Migration
- [ ] Open Supabase Dashboard
- [ ] Go to SQL Editor
- [ ] Run `migrations/fix_conversation_state_rls.sql`
- [ ] Verify "Success. No rows returned" message

### Environment Configuration
- [ ] Get SERVICE_ROLE key from Supabase → Settings → API
- [ ] Add to Railway Variables: `SUPABASE_SERVICE_ROLE_KEY`
- [ ] Save and wait for auto-restart (~30 seconds)

### Verification
- [ ] Check logs show `SERVICE_ROLE key` (not `ANON key`)
- [ ] Verify no RLS policy errors in logs
- [ ] Test: Have a conversation in Urdu
- [ ] Confirm: Session stays alive during conversation
- [ ] Confirm: Session ends only when you disconnect

## Post-Deployment

### Cleanup (Optional)
- [ ] Delete `agent.py.backup` if everything works
- [ ] Delete `agent.py.before_fixes` if everything works
- [ ] Delete `fixes_to_apply.py` if no longer needed
- [ ] Commit working changes to git
- [ ] Add `.env` to `.gitignore` (if not already)

### Documentation
- [ ] Keep `DEPLOY_FIXES.md` for reference
- [ ] Keep `CRITICAL_FIXES_APPLIED.md` for technical details
- [ ] Archive `QUICK_FIX_CARD.md` once done

### Testing Checklist
- [ ] Start new conversation
- [ ] Agent greets in Urdu
- [ ] Agent responds to multiple messages
- [ ] Session persists for 5+ minutes
- [ ] No errors in logs
- [ ] Clean disconnect and cleanup
- [ ] Reconnect - agent remembers context
- [ ] Trust scores persist between sessions

## Common Issues

### ❌ Still seeing "ANON key" in logs
**Fix**: SERVICE_ROLE_KEY not set correctly
- Check Railway → Variables
- Ensure no extra spaces or typos
- Ensure complete key copied (starts with `eyJhbG...`)

### ❌ Still seeing RLS errors
**Fix**: SQL migration not applied
- Go to Supabase SQL Editor
- Rerun the migration
- Check for any SQL errors

### ❌ Session ending too early
**Fix**: Check for exceptions
- Look for error messages in logs
- Check if participant actually disconnected
- Verify no crashes in background tasks

### ❌ Agent not responding in Urdu
**Note**: This is a separate issue
- Check TTS configuration
- Verify OpenAI model settings
- Check language settings in STT

## Success Criteria

All of these should be true:
- ✅ Logs show `SERVICE_ROLE key` connection
- ✅ No RLS policy violation errors
- ✅ `[STATE SERVICE] Updated state` messages appear
- ✅ Session stays alive during full conversation
- ✅ `[ENTRYPOINT] ✓ Participant disconnected` on exit
- ✅ `[ENTRYPOINT] ✓ Session completed normally` on exit
- ✅ Agent responds correctly in Urdu
- ✅ Context persists between sessions

## Estimated Time
- SQL Migration: 2 minutes
- Environment Setup: 1 minute
- Deployment: 30 seconds (auto)
- Testing: 5 minutes
- **Total: ~10 minutes**

## Support
If issues persist after checklist:
1. Share logs from a test conversation
2. Verify SQL migration success in Supabase logs
3. Confirm env var set correctly (echo first 10 chars)
4. Check Supabase Dashboard → Logs for RLS details

---

**Date Applied**: October 7, 2025
**Files Modified**: 2
**Files Created**: 6
**Breaking Changes**: None
**Rollback**: Restore from git if needed

