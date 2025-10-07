-- Fix RLS policies for conversation_state table
-- Issue: Service role needs full access for INSERT/UPDATE operations
-- The existing service role policy only covers SELECT (USING clause)

-- Drop existing service role policy
DROP POLICY IF EXISTS "Service role has full access to conversation_state" ON conversation_state;

-- Create comprehensive service role policy
-- This policy allows service_role to perform ALL operations (SELECT, INSERT, UPDATE, DELETE) on any row
-- USING clause: controls which rows can be read/updated/deleted
-- WITH CHECK clause: controls which rows can be inserted/updated
CREATE POLICY "Service role full access"
    ON conversation_state
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Note: User-specific policies remain unchanged for authenticated user access
-- When users authenticate directly, they can only access their own data

