-- Migration: Clean up inconsistent user_input_ timestamp keys
-- Purpose: Remove timestamp-based keys and standardize memory key format

-- First, let's see what user_input_ keys exist
-- SELECT key, category, value, created_at 
-- FROM memory 
-- WHERE key LIKE 'user_input_%' 
-- ORDER BY created_at DESC 
-- LIMIT 10;

-- Delete all memory entries with user_input_ timestamp keys
-- These are inconsistent with the standardized key format
DELETE FROM memory 
WHERE key LIKE 'user_input_%';

-- Add comment to document the cleanup
COMMENT ON TABLE memory IS 'User memory storage with standardized English keys (snake_case) - timestamp-based keys removed for consistency';

-- Verify cleanup (uncomment to run)
-- SELECT COUNT(*) as remaining_user_input_keys 
-- FROM memory 
-- WHERE key LIKE 'user_input_%';
