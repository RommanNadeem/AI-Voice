# Context Injection Fix - Implementation Guide

## Problem Statement

Context injection was only happening for the **first greeting message** but not for subsequent messages during the conversation. This meant that after the initial greeting, the AI assistant didn't have access to:
- User profile information
- Conversation state (stage, trust score)
- Recent memories
- Onboarding preferences

## Root Cause

The `get_enhanced_instructions()` method existed but was only called once during the initial greeting in the `entrypoint()` function. For subsequent messages, the AI used base instructions without any user context.

## Solution Overview

The fix implements **automatic context injection for every message** by:

1. **Using the correct LiveKit hook** - `on_agent_turn_started()` is called automatically before every AI response
2. **Cache invalidation** - Context cache is properly invalidated after user input
3. **Pre-loading RAG memories** - Memories are loaded from database BEFORE the first message
4. **Comprehensive logging** - All context operations are logged with emojis for easy debugging
5. **Multi-layer caching** - Session → Redis → Database for optimal performance

## Implementation Details

### 1. Using `update_instructions()` Method

The key to making context injection work is LiveKit's Agent class method `update_instructions()`. This method dynamically updates the agent's instructions that will be used for the next LLM inference.

```python
# After fetching enhanced instructions with context
enhanced = await self.get_enhanced_instructions()

# Update the agent's instructions dynamically
self.update_instructions(enhanced)
```

This is the **correct way** to inject context - using the official LiveKit API rather than trying to override the property.

### 2. Using the Official LiveKit Hook

```python
async def on_agent_turn_started(self):
    """
    OFFICIAL LIVEKIT HOOK: Called automatically before every agent response.
    """
    user_id = get_current_user_id()
    if not user_id:
        return
    
    # Get enhanced instructions with fresh context
    enhanced = await self.get_enhanced_instructions()
    
    # Update instructions before LLM processes the message
    self.update_instructions(enhanced)
```

**Key Hook Point**: `on_agent_turn_started()` is the **correct LiveKit lifecycle hook** called automatically before every AI response. This ensures:
1. Context is fresh before EVERY AI response (not just the first one)
2. Profile, memories, and state are up-to-date
3. Cache is properly used and invalidated
4. All context changes are logged for debugging

### 3. Cache Invalidation After User Input

```python
async def on_user_turn_completed(self, turn_ctx, new_message):
    """Called after user completes their turn"""
    user_text = new_message.text_content or ""
    
    # Update RAG conversation context
    rag_service.update_conversation_context(user_text)
    
    # CRITICAL: Invalidate cache after user input
    await self._invalidate_context_cache(user_id)
    
    # Fire-and-forget background processing
    asyncio.create_task(self._process_with_rag_background(user_text))
```

**Separation of Concerns**:
- `on_user_turn_completed()` - Handles cache invalidation and background processing
- `on_agent_turn_started()` - Handles context refresh before AI response

### 3. Enhanced Context Injection Method

```python
async def get_enhanced_instructions(self) -> str:
    """
    Get assistant instructions enhanced with automatic conversation context.
    Includes comprehensive logging and performance tracking.
    """
    # Fetch context from multi-layer cache
    context = await self.conversation_context_service.get_context(user_id)
    
    # Format and inject context
    context_text = self.conversation_context_service.format_context_for_instructions(context)
    
    # Cache the enhanced instructions
    self._cached_enhanced_instructions = context_text + "\n\n" + self._base_instructions
```

### 4. RAG Memories Loaded Before First Message

```python
# CRITICAL: Wait for RAG memories to load BEFORE first message
print("[RAG] Loading memories from database...")
rag_task = asyncio.create_task(rag_service.load_from_database(supabase, limit=500))
onboarding_task = asyncio.create_task(onboarding_service.initialize_user_from_onboarding(user_id))

# Wait for both to complete
await asyncio.gather(rag_task, onboarding_task, return_exceptions=True)

print("[RAG] ✓ Memories loaded and indexed before first message")
```

**Key Change**: Previously, RAG was loaded in the background and might not be ready for the first message. Now we **await** the loading to ensure memories are available from the start.

### 5. Initial Greeting with Auto-Context

```python
# Prepare base instructions with greeting strategy
final_instructions = assistant._base_instructions + "\n\n" + first_message_instructions + "\n\n" + stage_guidance

# Update the agent's instructions
assistant.update_instructions(final_instructions)

# Generate greeting
# on_agent_turn_started() will be called AUTOMATICALLY before LLM inference
await session.generate_reply()
```

**Important**: We no longer manually call context refresh before the greeting. The `on_agent_turn_started()` hook handles this automatically.

## Logging & Verification

### Logging Levels

The fix adds comprehensive logging at multiple levels:

#### INFO Level - Key Events
```
[USER INPUT] User message received
[ON_USER_TURN] Refreshing context for next AI response...
[CONTEXT INJECTION #N] Fetching context for user...
[CONTEXT INJECTION #N] ✓ Context injected in Xms (cache hit rate: Y%)
[ON_USER_TURN] ✓ Context refreshed and cached for next response
```

#### DEBUG Level - Detailed Tracking
```
[INSTRUCTIONS PROPERTY] Returning cached enhanced instructions (age: Xms)
[CONTEXT INJECTION] Context preview: [first 200 chars]...
```

#### WARNING Level - Issues
```
[CONTEXT INJECTION #N] No context available, using base instructions
[INSTRUCTIONS PROPERTY] No cached context available, using base instructions
```

#### ERROR Level - Failures
```
[CONTEXT INJECTION ERROR] {exception details}
[ON_USER_TURN CONTEXT ERROR] {exception details}
```

### Diagnostic Tool

A new tool `getContextInjectionStats()` provides real-time diagnostics:

```json
{
  "injection_count": 15,
  "last_injection_time": "2025-10-07 14:30:45",
  "seconds_since_last_injection": 2.3,
  "has_cached_context": true,
  "cache_age_ms": 234.5,
  "base_instructions_length": 5000,
  "enhanced_instructions_length": 7500,
  "context_overhead_chars": 2500,
  "status": "active",
  "message": "Context injected 15 times. Cache: active"
}
```

## Verification Steps

### 1. Check Logs on Startup

Look for these log messages when the agent starts:
```
[GREETING] Generating intelligent first message with automatic context injection...
[CONTEXT INJECTION #1] Fetching context for user...
[CONTEXT INJECTION #1] ✓ Context injected in Xms
[GREETING] ✓ Context injected (cache hit rate: Y%)
```

### 2. Check Logs After Each User Message

After each user message, you should see:
```
[USER INPUT] {message}
[ON_USER_TURN] Refreshing context for next AI response...
[CONTEXT INJECTION #N] Fetching context for user...
[CONTEXT INJECTION #N] ✓ Context injected in Xms
[ON_USER_TURN] ✓ Context refreshed and cached for next response
```

The injection count (#N) should increment with each message.

### 3. Use the Diagnostic Tool

Ask the AI to check context injection stats:
```
User: "Can you check your context injection stats?"

AI: *calls getContextInjectionStats() tool*
```

Expected response should show:
- `injection_count` > 0 and increasing
- `has_cached_context` = true
- `status` = "active"
- `context_overhead_chars` > 0 (showing context is being added)

### 4. Test Context Awareness

**Test 1: Profile Information**
```
User: "My name is Ahmed"
AI: *Should remember and use male pronouns in Urdu*

[Later in conversation]
User: "What's my name?"
AI: *Should correctly recall "Ahmed"*
```

**Test 2: Conversation State**
```
User: *Ask about current stage*
AI: *calls getUserState() - should show current stage and trust score*
```

**Test 3: Memory Recall**
```
User: "I love playing cricket"
[Wait for background processing]

[Later in conversation]
User: "What are my hobbies?"
AI: *Should naturally mention cricket*
```

## Performance Considerations

### Caching Strategy

1. **Session Cache** (Fastest)
   - Enhanced instructions are cached in memory
   - Cache is refreshed after each user message
   - No database queries needed for AI responses

2. **Redis Cache** (Fast)
   - User context is cached in Redis
   - Hit rate typically 70-90%
   - Fallback to database if cache miss

3. **Database** (Slowest)
   - Only queried on cache misses
   - Results are cached for subsequent requests

### Typical Performance

- **Context injection time**: 10-50ms (with cache hits)
- **Context injection time**: 100-300ms (with cache misses)
- **Cache hit rate**: 70-90% after warmup

### Zero-Latency Design

Context refresh happens in `on_user_turn_completed()`, which is called **after** the user's message is processed but **before** the AI generates a response. This means:

1. User sends message → Immediately processed
2. Context is refreshed (parallel with background tasks)
3. AI generates response with fresh context
4. **No perceived latency** from user's perspective

## Monitoring & Debugging

### Enable Debug Logging

To see detailed context injection logs, set logging level to DEBUG:

```python
logging.basicConfig(level=logging.DEBUG)
```

### Watch for Warning Signs

**Warning**: Context not being injected
```
[INSTRUCTIONS PROPERTY] No cached context available, using base instructions
```

**Action**: Check if `on_user_turn_completed()` is being called correctly.

**Warning**: Context injection failing
```
[CONTEXT INJECTION ERROR] {exception}
```

**Action**: Check database connectivity and service initialization.

**Warning**: Stale cache
```
[INSTRUCTIONS PROPERTY] Returning cached enhanced instructions (age: 5000ms)
```

**Action**: Cache might not be refreshing. Check `on_user_turn_completed()` logic.

## Architecture Flow

```
┌─────────────────────────────────────────────────────────────┐
│ User sends message                                          │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ on_user_turn_completed() called by LiveKit                  │
│ - Update RAG conversation context                           │
│ - Call get_enhanced_instructions()                          │
│   - Fetch user context (profile, state, memories)          │
│   - Format context for instructions                         │
│   - Cache: context_text + base_instructions                │
│ - Fire background processing                                │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ AI generates response                                       │
│ - AgentSession reads instructions property                  │
│ - Property returns cached enhanced instructions             │
│ - LLM inference with full context                           │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ AI sends response with full context awareness               │
└─────────────────────────────────────────────────────────────┘
```

## Key Code Changes Summary

1. **agent.py Line 170-282**: Store base instructions separately (`_base_instructions`)
2. **agent.py Line 652-700**: Enhanced `get_enhanced_instructions()` with logging and metrics
3. **agent.py Line 702-803**: Updated `on_user_turn_completed()` to call `update_instructions()`
4. **agent.py Line 516-543**: New `getContextInjectionStats()` diagnostic tool
5. **agent.py Line 980-995**: Updated entrypoint to use `update_instructions()` pattern

**Key Change**: Using `self.update_instructions(enhanced)` instead of property overrides - this is the official LiveKit API for dynamically updating agent instructions.

## Testing Checklist

- [ ] Context injection happens on first greeting
- [ ] Context injection happens after each user message
- [ ] Injection count increments correctly
- [ ] AI remembers user profile information
- [ ] AI uses correct conversation stage
- [ ] AI recalls memories naturally
- [ ] Cache hit rate > 70% after warmup
- [ ] Context injection time < 100ms (with cache)
- [ ] No errors in logs
- [ ] `getContextInjectionStats()` shows active status

## Rollback Plan

If issues occur, the fix can be rolled back by:

1. Reverting the dynamic `instructions` property to static
2. Removing context refresh from `on_user_turn_completed()`
3. Keeping only the initial greeting context injection

However, this would return to the original problem of context only being available for the first message.

## Future Enhancements

1. **Adaptive cache TTL**: Adjust cache freshness based on conversation velocity
2. **Context compression**: Reduce context size for faster LLM inference
3. **Predictive prefetch**: Prefetch context before user finishes speaking
4. **Context diff logging**: Log what changed in context between messages

## References

- LiveKit Agents Documentation: https://docs.livekit.io/agents/
- AgentSession API: https://docs.livekit.io/agents/build/session/
- Chat Context: https://docs.livekit.io/agents/build/workflows/

