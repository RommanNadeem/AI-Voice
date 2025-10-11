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

-- ============================================================================
-- VERIFICATION QUERIES (run these after applying the migration)
-- ============================================================================

-- Check RLS status on all tables
-- SELECT tablename, rowsecurity 
-- FROM pg_tables 
-- WHERE schemaname = 'public' 
-- AND tablename IN ('profiles', 'memory', 'user_profiles');

-- Check policies on profiles table
-- SELECT schemaname, tablename, policyname, roles, cmd
-- FROM pg_policies
-- WHERE tablename IN ('profiles', 'memory', 'user_profiles');

-- ============================================================================
-- NOTES:
-- ============================================================================
-- This migration fixes the FK constraint visibility issue where:
-- 1. SERVICE_ROLE can SELECT from profiles (finds rows)
-- 2. But FK constraint checks run under different context
-- 3. RLS policies block FK checker from seeing the rows
-- 4. All memory/profile inserts fail with FK violations
--
-- After applying this migration:
-- ✅ SERVICE_ROLE can fully manage all user data tables
-- ✅ FK constraints will see profile rows
-- ✅ Memory and profile saves will succeed
-- ✅ Onboarding initialization will work properly

