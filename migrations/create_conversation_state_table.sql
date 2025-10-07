-- Migration: Create conversation_state table
-- Purpose: Track conversation stages and trust scores for Social Penetration Theory

CREATE TABLE IF NOT EXISTS conversation_state (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    stage TEXT NOT NULL DEFAULT 'ORIENTATION',
    trust_score DECIMAL(3, 1) NOT NULL DEFAULT 2.0 CHECK (trust_score >= 0 AND trust_score <= 10),
    metadata JSONB DEFAULT '{}',
    stage_history JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Unique constraint: one state per user
    UNIQUE(user_id)
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_conversation_state_user_id ON conversation_state(user_id);

-- Index for stage queries
CREATE INDEX IF NOT EXISTS idx_conversation_state_stage ON conversation_state(stage);

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_conversation_state_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_conversation_state_updated_at
    BEFORE UPDATE ON conversation_state
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_state_updated_at();

-- RLS (Row Level Security) policies
ALTER TABLE conversation_state ENABLE ROW LEVEL SECURITY;

-- Users can read their own conversation state
CREATE POLICY "Users can view their own conversation state"
    ON conversation_state FOR SELECT
    USING (auth.uid() = user_id);

-- Users can insert their own conversation state
CREATE POLICY "Users can insert their own conversation state"
    ON conversation_state FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Users can update their own conversation state
CREATE POLICY "Users can update their own conversation state"
    ON conversation_state FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Service role bypass (for backend operations)
CREATE POLICY "Service role has full access to conversation_state"
    ON conversation_state
    USING (auth.role() = 'service_role');

-- Add comment to table
COMMENT ON TABLE conversation_state IS 'Tracks conversation stages and trust scores based on Social Penetration Theory';
COMMENT ON COLUMN conversation_state.stage IS 'Current conversation stage: ORIENTATION, ENGAGEMENT, GUIDANCE, REFLECTION, INTEGRATION';
COMMENT ON COLUMN conversation_state.trust_score IS 'Trust level from 0-10, influences conversation depth';
COMMENT ON COLUMN conversation_state.metadata IS 'Additional metadata like last trust adjustment reason';
COMMENT ON COLUMN conversation_state.stage_history IS 'History of stage transitions with timestamps';

