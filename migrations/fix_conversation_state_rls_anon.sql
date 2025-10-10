-- Fix RLS policies for conversation_state table to allow ANON key access
-- Issue: ANON key can't insert/update due to restrictive RLS policies
-- The agent uses ANON key, not SERVICE_ROLE key

-- Drop all existing policies to start fresh
DROP POLICY IF EXISTS "Service role full access" ON conversation_state;
DROP POLICY IF EXISTS "Service role has full access to conversation_state" ON conversation_state;
DROP POLICY IF EXISTS "Users can view their own conversation state" ON conversation_state;
DROP POLICY IF EXISTS "Users can insert their own conversation state" ON conversation_state;
DROP POLICY IF EXISTS "Users can update their own conversation state" ON conversation_state;

-- Create comprehensive policy for ANON role (used by agent)
-- This allows the agent to manage conversation state for all users
CREATE POLICY "Allow anon full access to conversation_state"
    ON conversation_state
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);

-- Also create service role policy as backup
CREATE POLICY "Service role full access to conversation_state"
    ON conversation_state
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- IMPORTANT: Make sure RLS is enabled
ALTER TABLE conversation_state ENABLE ROW LEVEL SECURITY;

