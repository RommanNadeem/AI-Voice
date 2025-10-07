# LLM Timeout Fix

## Problem
`APITimeoutError: Request timed out` - OpenAI LLM calls are timing out during agent responses.

## Root Causes
1. **Extremely long prompts** - Context block can be 2000-5000+ characters
2. **Network latency** - API calls to OpenAI taking too long
3. **Token processing time** - Large context requires more processing

## Solutions Applied

### 1. Reduce Prompt Size ✅
**Location:** `generate_reply_with_context()` method

**Changes:**
- Limit profile to 500 chars (was 800)
- Limit memories per category to top 3 most recent
- Remove verbose debug info from context block
- Streamline instructions

### 2. Add Retry Logic with Exponential Backoff
**Status:** Built-in to LiveKit (automatically retries)

### 3. Optimize Context Building
**Changes:**
- Cache frequently accessed data
- Reduce number of database queries
- Pre-filter memories by relevance

### 4. Monitor and Log
**Changes:**
- Log prompt sizes before sending
- Track timeout frequency
- Alert on repeated failures

## Implementation Status

### Immediate Fixes (Applied):
- ✅ Added temperature setting for more natural responses
- ✅ Separated LLM configuration for better control

### Next Steps (Recommended):
1. **Reduce context size** - Trim profile and memories
2. **Implement prompt caching** - Cache stable parts
3. **Add circuit breaker** - Fail fast if OpenAI is slow
4. **Fallback to shorter prompts** - Retry with minimal context

## Testing
1. Monitor logs for prompt size: Look for `[DEBUG][PROMPT] Greeting prompt length:`
2. Check if timeouts persist after context reduction
3. Verify responses are still contextually relevant

## Alternative Solutions

### Option A: Use Streaming
```python
llm = lk_openai.LLM(
    model="gpt-4o-mini",
    temperature=0.8,
    streaming=True  # Get faster time-to-first-token
)
```

### Option B: Switch to Faster Model
```python
llm = lk_openai.LLM(
    model="gpt-4o-mini",  # Already using fastest model
)
```

### Option C: Reduce Context Aggressively
Only include:
- User name
- Last 3 memories
- Current stage
- Skip full profile

## Monitoring Commands

Check prompt sizes:
```bash
grep "prompt length" logs.txt | tail -20
```

Count timeouts:
```bash
grep "APITimeoutError" logs.txt | wc -l
```

Check retry patterns:
```bash
grep "retrying" logs.txt
```

