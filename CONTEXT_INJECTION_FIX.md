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

1. **Making instructions dynamic** - Converting the `instructions` property from static to dynamic
2. **Hook into message flow** - Using `on_user_turn_completed()` to refresh context before each AI response
3. **Caching for performance** - Caching enhanced instructions to avoid repeated database queries
4. **Comprehensive logging** - Adding detailed logging to track when context is injected

## Implementation Details

### 1. Dynamic Instructions Property

```python
@property
def instructions(self) -> str:
    """
    Dynamic instructions property that automatically injects context before each LLM inference.
    Returns cached enhanced instructions that were prepared in on_user_turn_completed.
    """
    # Returns cached enhanced instructions with user context
```

The `instructions` property is now dynamic and returns cached enhanced instructions that include user context.

### 2. Context Refresh on Every User Turn

```python
async def on_user_turn_completed(self, turn_ctx, new_message):
    """Called after each user message"""
    # ... existing background processing ...
    
    # CRITICAL: Refresh context for next AI response
    await self.get_enhanced_instructions()
```

**Key Hook Point**: `on_user_turn_completed()` is called by LiveKit after each user message. We use this to refresh the context cache before the AI generates its response.

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

### 4. Optional: before_llm_inference Hook

```python
async def before_llm_inference(self, chat_ctx) -> None:
    """
    Hook called by AgentSession before each LLM inference.
    This provides an additional hook point for context refresh.
    """
    await self.get_enhanced_instructions()
```

This is an **optional safety hook** - if LiveKit's AgentSession supports this method, it will be called automatically before each LLM inference.

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

1. **agent.py Line 170-282**: Store base instructions separately, initialize with dynamic property
2. **agent.py Line 297-336**: Dynamic `instructions` property with caching
3. **agent.py Line 664-737**: Enhanced `get_enhanced_instructions()` with logging and metrics
4. **agent.py Line 739-776**: Updated `on_user_turn_completed()` to refresh context
5. **agent.py Line 555-586**: New `getContextInjectionStats()` diagnostic tool
6. **agent.py Line 1009-1022**: Updated entrypoint to use new pattern

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

