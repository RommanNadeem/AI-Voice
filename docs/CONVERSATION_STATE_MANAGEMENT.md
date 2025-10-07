# Conversation State Management

## Overview

The Conversation State Management system implements **Social Penetration Theory** to guide natural conversation depth and breadth. It tracks two key metrics:

1. **Stage** - Current conversation depth (ORIENTATION → ENGAGEMENT → GUIDANCE → REFLECTION → INTEGRATION)
2. **Trust Score** - Trust level from 0-10 that influences readiness for deeper conversation

## Architecture

### Service: `ConversationStateService`

Located in `services/conversation_state_service.py`

**Responsibilities:**
- Track conversation stage and trust score
- Analyze user readiness for stage transitions
- Provide stage-specific conversation guidance
- Automatically update state based on interactions

### Database Table: `conversation_state`

```sql
CREATE TABLE conversation_state (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL UNIQUE,
    stage TEXT NOT NULL DEFAULT 'ORIENTATION',
    trust_score DECIMAL(3, 1) NOT NULL DEFAULT 2.0,
    metadata JSONB DEFAULT '{}',
    stage_history JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Migration**: See `migrations/create_conversation_state_table.sql`

---

## Conversation Stages

### 1. ORIENTATION (Default)
**Goal**: Build safety and comfort

**Trust Range**: 0-3  
**Duration**: First 3-5 interactions

**Characteristics:**
- Light, friendly conversation
- Non-intrusive questions
- Building rapport
- Offering small wins (<5 min tasks)

**Topics:**
- General interests
- Daily activities
- Light topics
- Weather, simple preferences

**Progression Signals:**
- User shares without prompting
- Responds with detail
- Asks personal questions back
- Shows comfort

---

### 2. ENGAGEMENT
**Goal**: Explore breadth across life domains

**Trust Range**: 3-5  
**Duration**: 5-15 interactions

**Characteristics:**
- Explore multiple life areas
- Open-ended questions
- Identify energetic domains
- Remember previous conversations

**Topics:**
- Work/Career
- Family & Relationships
- Health & Wellness
- Hobbies & Interests
- Learning & Growth
- Finances (surface level)

**Progression Signals:**
- Discusses multiple life areas
- Shows enthusiasm about topics
- Asks for more depth
- Trust score > 5

---

### 3. GUIDANCE
**Goal**: Go deeper with consent

**Trust Range**: 5-7  
**Duration**: Ongoing

**Characteristics:**
- **Ask consent** before going deeper
- Discuss feelings and needs
- Offer actionable guidance
- Validate emotions

**Topics:**
- Emotions and feelings
- Underlying needs
- Patterns and triggers
- Gentle challenges
- Reframing techniques

**Consent Examples:**
- "Would you like to explore this more deeply?"
- "Shall we talk about what's behind that feeling?"
- "Are you comfortable discussing this?"

**Progression Signals:**
- Accepts guidance willingly
- Implements suggestions
- Shares vulnerabilities
- Requests deeper conversation

---

### 4. REFLECTION
**Goal**: Reflect on progress and build routines

**Trust Range**: 7-9  
**Duration**: Ongoing

**Characteristics:**
- Review progress on actions
- Set sustainable routines
- Address obstacles
- Celebrate wins

**Topics:**
- Progress review
- Habit formation
- Obstacle handling
- Accountability
- Next steps

**Progression Signals:**
- Shows consistent progress
- Implements routines
- Reflects independently
- Discusses identity changes

---

### 5. INTEGRATION
**Goal**: Identity-level insights

**Trust Range**: 9-10  
**Duration**: Sustained

**Characteristics:**
- Identity-level reflection
- Celebrate transformation
- Choose next growth area
- Deep authenticity

**Topics:**
- Identity and values
- Life purpose
- Long-term vision
- Who they're becoming
- Next chapter

**Progression Signals:**
- Sustained growth
- Identity shift
- Self-directed growth
- Mentor-like relationship

---

## Trust Score System

### Scale: 0-10

| Range | Description | Stage Access |
|-------|-------------|--------------|
| 0-2 | Low trust, cautious | ORIENTATION only |
| 3-4 | Building trust | ORIENTATION, ENGAGEMENT |
| 5-6 | Established trust | Up to GUIDANCE |
| 7-8 | Strong trust | Up to REFLECTION |
| 9-10 | Deep trust | All stages including INTEGRATION |

### Trust Adjustment Triggers

**Increase Trust (+0.5 to +2.0):**
- User shares personal information voluntarily
- User implements suggestions
- User asks for deeper guidance
- User shows vulnerability
- User returns consistently

**Decrease Trust (-0.5 to -2.0):**
- User deflects questions
- Gives very short responses
- Changes topic abruptly
- Shows discomfort
- Long absence without explanation

### Automatic Trust Adjustment

The system automatically adjusts trust based on AI analysis of interactions:

```python
# Example trust adjustments
"Self-disclosure" → +1.0
"Accepts guidance" → +1.5
"Requests depth" → +2.0
"Deflection" → -0.5
"Discomfort signals" → -1.0
```

---

## API Reference

### Get Current State

```python
state_service = ConversationStateService(supabase)
state = await state_service.get_state(user_id)

# Returns:
{
    "stage": "ENGAGEMENT",
    "trust_score": 5.5,
    "last_updated": "2024-10-07T12:00:00Z",
    "metadata": {...},
    "stage_history": [...]
}
```

### Update State

```python
success = await state_service.update_state(
    stage="GUIDANCE",
    trust_score=6.0,
    metadata={"reason": "User requested deeper conversation"},
    user_id=user_id
)
```

### Adjust Trust

```python
new_trust = await state_service.adjust_trust(
    delta=1.5,
    reason="User shared vulnerability",
    user_id=user_id
)
# Returns: 7.0 (new trust score)
```

### Suggest Stage Transition (AI-Powered)

```python
suggestion = await state_service.suggest_stage_transition(
    user_input="I've been struggling with my anxiety lately...",
    user_profile="User interested in mental health",
    user_id=user_id
)

# Returns:
{
    "current_stage": "ENGAGEMENT",
    "suggested_stage": "GUIDANCE",
    "should_transition": True,
    "confidence": 0.85,
    "reason": "User showing readiness for deeper conversation",
    "trust_adjustment": +1.0,
    "detected_signals": ["vulnerability", "emotional_topic"]
}
```

### Auto-Update from Interaction

```python
result = await state_service.auto_update_from_interaction(
    user_input="I tried the meditation you suggested, it really helped!",
    user_profile="User working on mindfulness",
    user_id=user_id
)

# Returns:
{
    "action_taken": "trust_adjustment",  # or "stage_transition" or "none"
    "old_state": {"stage": "GUIDANCE", "trust_score": 6.0},
    "new_state": {"stage": "GUIDANCE", "trust_score": 7.5},
    "suggestion": {...}
}
```

### Get Stage Guidance

```python
guidance = state_service.get_stage_guidance("ENGAGEMENT")
# Returns markdown text with stage-specific instructions
```

---

## Tool Functions (Agent Access)

### `getUserState()`

Get current conversation state.

**Returns:**
```json
{
    "stage": "ENGAGEMENT",
    "trust_score": 5.5,
    "stage_description": "Exploring interests and life domains",
    "message": "Current stage: ENGAGEMENT (Trust: 5.5/10)"
}
```

### `updateUserState(stage, trust_score)`

Manually update conversation state (use sparingly).

**Parameters:**
- `stage` (optional): New stage
- `trust_score` (optional): New trust score (0-10)

**Returns:**
```json
{
    "success": true,
    "stage": "GUIDANCE",
    "trust_score": 6.0,
    "message": "Updated to GUIDANCE (Trust: 6.0/10)"
}
```

### `runDirectiveAnalysis(user_input)`

Analyze user input for stage transition readiness.

**Parameters:**
- `user_input`: Recent user message

**Returns:**
```json
{
    "current_stage": "ENGAGEMENT",
    "suggested_stage": "GUIDANCE",
    "should_transition": true,
    "confidence": 0.85,
    "reason": "User showing readiness for deeper conversation",
    "trust_adjustment": +1.0,
    "detected_signals": ["vulnerability", "emotional_topic"],
    "message": "Suggest transition to GUIDANCE (confidence: 85%)"
}
```

---

## Integration with Agent

### Automatic State Updates

State is automatically updated in background processing after each user turn:

```python
# In Agent.on_user_turn_completed()
async def on_user_turn_completed(self, turn_ctx, new_message):
    # ... save memory, update profile ...
    
    # Automatic state update
    state_update = await self.conversation_state_service.auto_update_from_interaction(
        user_input=user_text,
        user_profile=user_profile,
        user_id=user_id
    )
    
    if state_update.get("action_taken") == "stage_transition":
        print(f"Transitioned: {old_stage} → {new_stage}")
```

### State-Aware Greetings

First message includes stage-specific guidance:

```python
# In entrypoint()
state = await conversation_state_service.get_state(user_id)
stage_guidance = conversation_state_service.get_stage_guidance(state["stage"])

# Combine with greeting
enhanced_instructions = greeting + "\n\n" + stage_guidance
await session.generate_reply(instructions=enhanced_instructions)
```

---

## Best Practices

### 1. Let Automatic Updates Handle Most Transitions

The AI-powered analysis handles transitions based on user signals. Manual updates should be rare.

### 2. Always Ask Consent for GUIDANCE

Before transitioning to GUIDANCE stage, explicitly ask:
- "Would you like to explore this more deeply?"
- "Shall we talk about what's behind that feeling?"

### 3. Step Back on Discomfort

If user shows discomfort at any stage, step back to previous stage:

```python
if user_shows_discomfort:
    await state_service.adjust_trust(delta=-1.0, reason="User discomfort")
    # Consider stepping back to previous stage
```

### 4. Monitor Trust Score

Trust score gates access to deeper stages:
- Don't push for GUIDANCE if trust < 5
- Don't attempt REFLECTION if trust < 7
- INTEGRATION requires trust > 9

### 5. Use Stage Guidance

Each stage has specific guidance for conversation approach. Reference this in your responses.

---

## Monitoring & Debugging

### View Current State

```python
state = await state_service.get_state(user_id)
print(f"Stage: {state['stage']}, Trust: {state['trust_score']}")
```

### View Stage History

```python
history = state["stage_history"]
for transition in history:
    print(f"{transition['from']} → {transition['to']} at {transition['timestamp']}")
```

### Check Trust Adjustments

```python
last_adjustment = state["metadata"].get("last_trust_adjustment")
print(f"Last adjustment: {last_adjustment['delta']} ({last_adjustment['reason']})")
```

---

## Database Migration

Run this SQL in your Supabase SQL editor:

```bash
# Apply migration
psql -U postgres -d your_database -f migrations/create_conversation_state_table.sql
```

Or in Supabase dashboard:
1. Go to SQL Editor
2. Paste contents of `migrations/create_conversation_state_table.sql`
3. Run

---

## Performance

### Caching
- States cached in Redis for 5 minutes
- Cache invalidated on updates
- Reduces database load

### Background Updates
- State analysis runs in background (zero latency)
- Does not block user responses
- Parallel processing with other operations

### Database Queries
- Single query to get state
- Single upsert to update
- Indexes on `user_id` for fast lookups

---

## Example Conversation Flow

```
User: "Hi!"
State: ORIENTATION (Trust: 2.0)
→ Warm greeting, light questions

User: "I love hiking and photography"
State: ORIENTATION → ENGAGEMENT (Trust: 3.5)
→ Explore hobbies, ask about other interests

User: "I've been feeling stressed at work lately..."
Analysis: Trust 5.5, signals: [emotional_topic, ready_for_depth]
State: ENGAGEMENT → GUIDANCE (Trust: 6.0)
→ "Would you like to talk about what's causing the stress?"

User: "Yes, I'd like some guidance"
State: GUIDANCE (Trust: 7.0)
→ Offer specific techniques, discuss feelings

User: "I tried your suggestion, it helped!"
State: GUIDANCE → REFLECTION (Trust: 8.0)
→ Reflect on progress, build on success
```

---

## Testing

```python
# Test state transitions
async def test_state_flow():
    service = ConversationStateService(supabase)
    
    # Start at ORIENTATION
    state = await service.get_state(user_id)
    assert state["stage"] == "ORIENTATION"
    assert state["trust_score"] == 2.0
    
    # Simulate progression
    await service.adjust_trust(delta=2.0, reason="Test")
    await service.update_state(stage="ENGAGEMENT", user_id=user_id)
    
    # Verify
    state = await service.get_state(user_id)
    assert state["stage"] == "ENGAGEMENT"
    assert state["trust_score"] == 4.0
```

---

## Future Enhancements

1. **Stage-specific prompts**: Automatically adjust system prompts based on stage
2. **Micro-win tracking**: Track completion of small tasks at each stage
3. **Domain energy mapping**: Track which life domains energize the user
4. **Regression detection**: Detect and handle stage regressions
5. **Multi-cycle support**: Support multiple cycles through stages for different domains

---

## References

- **Social Penetration Theory**: Altman & Taylor (1973)
- **Trust Development**: Mayer, Davis & Schoorman (1995)
- **Conversation Depth**: Aron et al. (1997) - 36 Questions study

---

**Last Updated**: October 7, 2024  
**Version**: 1.0  
**Status**: Production Ready

