-- Verify and Fix Profiles Schema for UUID Standardization
-- Safe to run - won't drop or recreate existing tables
-- ============================================================================

-- Step 1: Verify profiles table structure
-- Run this to check if user_id column exists
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'profiles'
ORDER BY ordinal_position;

-- Step 2: Check if user_id column exists (if not, add it)
DO $$
BEGIN
    -- Check if user_id column exists
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'profiles'
          AND column_name = 'user_id'
    ) THEN
        -- Add user_id column if it doesn't exist
        ALTER TABLE profiles ADD COLUMN user_id UUID UNIQUE;
        RAISE NOTICE 'Added user_id column to profiles table';
    ELSE
        RAISE NOTICE 'user_id column already exists in profiles table';
    END IF;
END $$;

-- Step 3: Ensure user_id has proper constraints
-- Add UNIQUE constraint if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'profiles_user_id_key'
          AND conrelid = 'profiles'::regclass
    ) THEN
        ALTER TABLE profiles ADD CONSTRAINT profiles_user_id_key UNIQUE (user_id);
        RAISE NOTICE 'Added UNIQUE constraint to user_id column';
    ELSE
        RAISE NOTICE 'UNIQUE constraint already exists on user_id';
    END IF;
EXCEPTION
    WHEN duplicate_table THEN
        RAISE NOTICE 'Constraint already exists';
END $$;

-- Step 4: Verify memory table FK references profiles.user_id
SELECT
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_name IN ('memory', 'user_profiles')
  AND tc.table_schema = 'public';

-- Step 5: Apply RLS fixes (same as fix_profiles_rls_for_service_role.sql)
-- ============================================================================

-- PROFILES TABLE - Allow SERVICE_ROLE full access
DROP POLICY IF EXISTS "Service role full access to profiles" ON profiles;
CREATE POLICY "Service role full access to profiles"
ON profiles
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- MEMORY TABLE - Allow SERVICE_ROLE full access
DROP POLICY IF EXISTS "Service role full access to memory" ON memory;
CREATE POLICY "Service role full access to memory"
ON memory
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- USER_PROFILES TABLE - Allow SERVICE_ROLE full access
DROP POLICY IF EXISTS "Service role full access to user_profiles" ON user_profiles;
CREATE POLICY "Service role full access to user_profiles"
ON user_profiles
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- ============================================================================
-- VERIFICATION - Run this to confirm everything is set up correctly
-- ============================================================================

SELECT 
    'profiles' as table_name,
    EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'profiles' 
          AND column_name = 'user_id'
          AND data_type = 'uuid'
    ) as has_user_id_column,
    EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'profiles_user_id_key'
          AND conrelid = 'profiles'::regclass
    ) as has_unique_constraint;

-- Show current RLS policies
SELECT 
    schemaname, 
    tablename, 
    policyname, 
    roles::text, 
    cmd
FROM pg_policies
WHERE tablename IN ('profiles', 'memory', 'user_profiles')
ORDER BY tablename, policyname;

-- ============================================================================
-- SUCCESS CRITERIA
-- ============================================================================
-- ✅ profiles.user_id column exists and is UUID type
-- ✅ profiles.user_id has UNIQUE constraint
-- ✅ Service role has full access policies on all tables
-- ✅ FK constraints reference profiles.user_id
-- ============================================================================

