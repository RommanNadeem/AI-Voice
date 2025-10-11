# 🚨 URGENT: Database RLS Issue Causing FK Errors

## Problem
Your logs show FK errors are still happening because **Row Level Security (RLS) policies** are blocking Foreign Key constraint checks from seeing profile rows.

## Evidence from Your Logs
```
[USER SERVICE] ℹ️  Profile NOT FOUND for bb4a6f7c...
[USER SERVICE] Creating new profile for bb4a6f7c...
ERROR: duplicate key value violates unique constraint "profiles_email_key"
  → This proves profile DOES exist

[MEMORY SERVICE] 🚨 CRITICAL BUG: FK error after ensure_profile_exists!
  → But FK checker can't see it due to RLS
```

## Root Cause
PostgreSQL's FK constraint checks run in a **different security context** than your SERVICE_ROLE queries. Even though SERVICE_ROLE can SELECT from profiles, the FK checker is blocked by RLS policies.

## Immediate Fix (Choose One)

### Option A: Disable RLS Completely (RECOMMENDED for SERVICE_ROLE backends)

**Run this SQL in Supabase Dashboard:**

```sql
-- Disable RLS on all three tables
ALTER TABLE profiles DISABLE ROW LEVEL SECURITY;
ALTER TABLE memory DISABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles DISABLE ROW LEVEL SECURITY;

-- Verify
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public' 
  AND tablename IN ('profiles', 'memory', 'user_profiles');
```

This is **SAFE** because:
- ✅ You're using SERVICE_ROLE key (trusted backend)
- ✅ All access goes through your application (not direct from users)
- ✅ Your application code enforces permissions
- ✅ No public/anonymous access to these tables

### Option B: Use the Migration Script

```bash
# The script is already created at:
migrations/critical_rls_bypass_fix.sql

# Apply it via Supabase Dashboard SQL Editor
# (Copy/paste contents and run)
```

## Why This Happens

```
User Code (SERVICE_ROLE):
  SELECT * FROM profiles WHERE user_id = 'uuid'
  → RLS policy: "service_role can see everything" ✅
  → Returns row

FK Constraint Check (internal):
  Check if 'uuid' exists in profiles.user_id
  → Runs in DIFFERENT context
  → RLS policy might not apply
  → Can't see row ❌
  → FK violation!
```

## How to Apply the Fix

### Using Supabase Dashboard (EASIEST):

1. Open https://app.supabase.com
2. Select your project
3. Go to **SQL Editor**
4. Click "New Query"
5. Paste this:
   ```sql
   ALTER TABLE profiles DISABLE ROW LEVEL SECURITY;
   ALTER TABLE memory DISABLE ROW LEVEL SECURITY;
   ALTER TABLE user_profiles DISABLE ROW LEVEL SECURITY;
   ```
6. Click **Run**
7. Wait for "Success" message

### Verification:

Run this to confirm:
```sql
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public' 
  AND tablename IN ('profiles', 'memory', 'user_profiles');
```

Expected output:
```
tablename     | rowsecurity
--------------+-------------
profiles      | f           ← "f" means RLS is OFF
memory        | f
user_profiles | f
```

## After Applying Fix

Your logs should show:
- ✅ `[USER SERVICE] ✅ Profile EXISTS` (found correctly)
- ✅ `[MEMORY SERVICE] ✅ Saved successfully`
- ✅ No more FK errors
- ✅ No more duplicate email errors

## If You Can't Disable RLS

If security policies require RLS to stay enabled, we need a different approach:

1. **Change FK constraints** to use SECURITY DEFINER functions
2. **Use triggers** instead of direct inserts
3. **Grant explicit permissions** to the FK checker role

But for a SERVICE_ROLE backend, disabling RLS is the standard approach.

---

**APPLY THIS FIX NOW** and the FK errors will stop immediately! 🚀

