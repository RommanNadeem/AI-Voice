# Fix RLS Issue - Foreign Key Constraint Violations

## Problem
Your logs show:
```
insert or update on table "memory" violates foreign key constraint "memory_user_id_fkey"
Key (user_id)=(bb4a6f7c-1e1d-4db8-9fcd-f7095759aba2) is not present in table "profiles"
```

## Root Cause
**RLS (Row Level Security) is blocking FK constraint validation**:

1. ✅ Your SERVICE_ROLE can SELECT from `profiles` (so checks say "profile exists")
2. ❌ But PostgreSQL's FK constraint checker can't see the rows due to RLS policies
3. ❌ Result: All `memory` and `user_profiles` inserts fail

## Solution: Apply RLS Fix Migration

### Step 1: Go to Supabase Dashboard
1. Open https://app.supabase.com
2. Select your project
3. Go to **SQL Editor** (left sidebar)

### Step 2: Run the Migration
Copy and paste this SQL into the SQL Editor and click **Run**:

```sql
-- Fix RLS policies for profiles, memory, and user_profiles tables
-- This resolves FK constraint violations where SERVICE_ROLE can SELECT rows
-- but FK checks can't see them due to RLS policies

-- ============================================================================
-- PROFILES TABLE - Allow SERVICE_ROLE full access
-- ============================================================================

-- Drop existing restrictive policies if they exist
DROP POLICY IF EXISTS "Service role full access to profiles" ON profiles;

-- Create policy allowing service_role to bypass RLS completely
CREATE POLICY "Service role full access to profiles"
ON profiles
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- ============================================================================
-- MEMORY TABLE - Allow SERVICE_ROLE full access
-- ============================================================================

-- Drop existing restrictive policies if they exist
DROP POLICY IF EXISTS "Service role full access to memory" ON memory;

-- Create policy allowing service_role to bypass RLS
CREATE POLICY "Service role full access to memory"
ON memory
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- ============================================================================
-- USER_PROFILES TABLE - Allow SERVICE_ROLE full access
-- ============================================================================

-- Drop existing restrictive policies if they exist
DROP POLICY IF EXISTS "Service role full access to user_profiles" ON user_profiles;

-- Create policy allowing service_role to bypass RLS
CREATE POLICY "Service role full access to user_profiles"
ON user_profiles
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);
```

### Step 3: Verify the Fix
After running the migration, your memory saves should work. The logs should show:
```
[MEMORY SERVICE] ✅ Saved successfully: [INTEREST] hobby
```

Instead of:
```
[MEMORY SERVICE] ❌ Database error: foreign key constraint violation
```

## Alternative: Code-Level Fix

If you can't apply the migration immediately, you can also fix this by ensuring the `profiles` table entry exists BEFORE any memory operations:

```python
# In your onboarding service, ensure this order:
1. Create profiles table entry first
2. Then create memories
3. Then create user_profiles entry
```

The `UserService.ensure_profile_exists()` method should be called before any memory or profile operations.

## Why This Happens

Looking at your schema:
- `memory.user_id` → `auth.users.id` (FK constraint)
- `user_profiles.user_id` → `auth.users.id` (FK constraint)
- `profiles.user_id` → `auth.users.id` (FK constraint)

When you insert into `memory` or `user_profiles`, PostgreSQL validates the FK constraint by checking if the user exists in the referenced table. But RLS policies block this check from seeing the row, even though your application code can see it.

The migration fixes this by allowing SERVICE_ROLE to bypass RLS completely for these tables.
