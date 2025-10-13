-- Migration: Create conversation_summaries table
-- Purpose: Store progressive conversation summaries for context continuity
-- Date: 2025-10-14

-- Create conversation summaries table
CREATE TABLE IF NOT EXISTS conversation_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(user_id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    
    -- Summary content
    summary_text TEXT NOT NULL,
    key_topics TEXT[] DEFAULT '{}',
    important_facts TEXT[] DEFAULT '{}',
    emotional_tone TEXT DEFAULT 'neutral',
    
    -- Metadata
    turn_count INTEGER NOT NULL DEFAULT 0,
    start_time TIMESTAMPTZ DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    is_final BOOLEAN DEFAULT FALSE,
    
    -- Linkage (for incremental summaries)
    previous_summary_id UUID REFERENCES conversation_summaries(id) ON DELETE SET NULL,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_conv_summaries_user_time 
    ON conversation_summaries(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_conv_summaries_session 
    ON conversation_summaries(session_id);

CREATE INDEX IF NOT EXISTS idx_conv_summaries_final 
    ON conversation_summaries(user_id, is_final) 
    WHERE is_final = TRUE;

-- RLS Policies
ALTER TABLE conversation_summaries ENABLE ROW LEVEL SECURITY;

-- Policy: Users can read their own summaries
CREATE POLICY "Users can read own summaries"
    ON conversation_summaries
    FOR SELECT
    USING (
        auth.uid() = user_id
        OR 
        auth.jwt() ->> 'role' = 'service_role'
    );

-- Policy: Service role can insert summaries
CREATE POLICY "Service role can insert summaries"
    ON conversation_summaries
    FOR INSERT
    WITH CHECK (
        auth.jwt() ->> 'role' = 'service_role'
    );

-- Policy: Service role can update summaries
CREATE POLICY "Service role can update summaries"
    ON conversation_summaries
    FOR UPDATE
    USING (
        auth.jwt() ->> 'role' = 'service_role'
    );

-- Policy: Service role can delete summaries
CREATE POLICY "Service role can delete summaries"
    ON conversation_summaries
    FOR DELETE
    USING (
        auth.jwt() ->> 'role' = 'service_role'
    );

-- Function to auto-update updated_at
CREATE OR REPLACE FUNCTION update_conversation_summaries_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for auto-updating updated_at
DROP TRIGGER IF EXISTS update_conversation_summaries_timestamp ON conversation_summaries;
CREATE TRIGGER update_conversation_summaries_timestamp
    BEFORE UPDATE ON conversation_summaries
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_summaries_updated_at();

-- Comments
COMMENT ON TABLE conversation_summaries IS 'Stores progressive conversation summaries for context continuity across sessions';
COMMENT ON COLUMN conversation_summaries.summary_text IS 'LLM-generated summary of conversation segment';
COMMENT ON COLUMN conversation_summaries.key_topics IS 'Main topics discussed (for quick scanning)';
COMMENT ON COLUMN conversation_summaries.important_facts IS 'Key facts shared by user in this session';
COMMENT ON COLUMN conversation_summaries.emotional_tone IS 'Overall mood/tone of conversation';
COMMENT ON COLUMN conversation_summaries.is_final IS 'True if this is the final session summary (vs incremental)';
COMMENT ON COLUMN conversation_summaries.previous_summary_id IS 'Links incremental summaries together';

-- Verification query
SELECT 
    COUNT(*) as total_summaries,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(*) FILTER (WHERE is_final = TRUE) as final_summaries,
    AVG(turn_count) as avg_turns_per_summary
FROM conversation_summaries;

