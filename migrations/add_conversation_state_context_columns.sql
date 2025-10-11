-- Migration: Add context columns to conversation_state
-- Adds columns used by code: last_summary, last_topics, last_user_message,
-- last_assistant_message, last_conversation_at.

ALTER TABLE conversation_state
    ADD COLUMN IF NOT EXISTS last_summary TEXT,
    ADD COLUMN IF NOT EXISTS last_topics JSONB DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS last_user_message TEXT,
    ADD COLUMN IF NOT EXISTS last_assistant_message TEXT,
    ADD COLUMN IF NOT EXISTS last_conversation_at TIMESTAMPTZ;

-- Optional: comment for clarity
COMMENT ON COLUMN conversation_state.last_summary IS 'Brief summary of last exchange';
COMMENT ON COLUMN conversation_state.last_topics IS 'Array of key topics from last exchange';
COMMENT ON COLUMN conversation_state.last_user_message IS 'Most recent user message';
COMMENT ON COLUMN conversation_state.last_assistant_message IS 'Most recent assistant message';
COMMENT ON COLUMN conversation_state.last_conversation_at IS 'Timestamp of last conversation exchange';


