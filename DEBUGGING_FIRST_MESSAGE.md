# Debugging: AI Not Starting Conversation

## 🔍 Issue
AI is not starting the conversation when user joins the room.

## 🛠️ Debugging Changes Added

### 1. Removed `RoomInputOptions()`
**Before:**
```python
await session.start(room=ctx.room, agent=assistant, room_input_options=RoomInputOptions())
```

**After:**
```python
await session.start(room=ctx.room, agent=assistant)
```

**Reason:** Default RoomInputOptions might interfere with agent-initiated messages

### 2. Added Comprehensive Logging

#### In Entrypoint (Greeting Generation)
- Logs instructions length before generating
- Catches and logs any exceptions during `generate_reply()`
- Shows exactly where failure occurs

#### In `on_agent_turn_started` Hook
- Logs when hook is called
- Shows `_is_first_message` flag status
- Logs instructions length when skipping
- Shows enhanced instructions process for subsequent messages
- Full exception stack traces

## 🔍 What to Check in Logs

### Expected Flow (Success)
```
[GREETING] 🚀 Generating FAST first message (simple greeting)...
[GREETING] Instructions length: 5000+ chars
[HOOK] on_agent_turn_started called, first_message=True
[HOOK] ⚡ Skipping context injection for first message (speed mode)
[HOOK] Instructions already set in entrypoint, length: 5000+
[GREETING] ✓ First message sent!
```

### Failure Patterns

#### Pattern 1: No Hook Called
```
[GREETING] 🚀 Generating FAST first message...
[GREETING] Instructions length: XXXX
(no [HOOK] logs)
[GREETING] ❌ FAILED to generate first message: ...
```
**Problem:** Hook not being triggered → LiveKit session issue

#### Pattern 2: Hook Called But No User ID
```
[HOOK] on_agent_turn_started called, first_message=True
[HOOK] No user_id, skipping
```
**Problem:** User ID not set → Check participant identity parsing

#### Pattern 3: Instructions Empty/Short
```
[GREETING] Instructions length: 100 chars
```
**Problem:** Base instructions or greeting instructions not loaded

#### Pattern 4: Exception in generate_reply()
```
[GREETING] ❌ FAILED to generate first message: [error details]
```
**Problem:** Check error message for specific issue

## 🎯 Potential Root Causes

### 1. Session Not Ready
- Session.start() completed but session not in ready state
- Solution: Check LiveKit session lifecycle

### 2. User ID Not Set
- `get_current_user_id()` returns None in hook
- Instructions can't be updated
- Solution: Ensure `set_current_user_id()` called before generate_reply()

### 3. Instructions Not Persisting
- Instructions set in entrypoint but cleared before hook
- Solution: Check if something clears instructions between set and generate

### 4. TTS/STT/LLM Failure
- OpenAI API error
- TTS service error
- Solution: Check exception details in logs

### 5. Timeout in Greeting Preparation
- `get_simple_greeting_instructions()` times out
- Falls back to hardcoded greeting
- Should still work, but check if fallback is correct

## 📋 Debugging Checklist

Run the agent and check:

- [ ] `[SESSION INIT] ✓ Session started` appears
- [ ] `[ENTRYPOINT] Participant: sid=...` appears
- [ ] `[GREETING] 🚀 Generating FAST first message` appears
- [ ] `[GREETING] Instructions length: XXXX` shows >5000 chars
- [ ] `[HOOK] on_agent_turn_started called` appears
- [ ] `[HOOK] Instructions already set in entrypoint` appears
- [ ] `[GREETING] ✓ First message sent!` appears
- [ ] No error logs (`❌` or `ERROR`)

## 🔧 Quick Fixes

### If Instructions Are Empty
```python
# Check base_instructions are loaded
print(f"Base instructions: {len(assistant._base_instructions)}")
```

### If Hook Not Called
```python
# Check session state
print(f"Session state: {session._state}")
```

### If User ID Missing
```python
# Check participant identity
print(f"Participant identity: {participant.identity}")
print(f"Extracted user_id: {user_id}")
```

### If TTS/LLM Error
```python
# Check API keys
print(f"OpenAI key configured: {bool(Config.OPENAI_API_KEY)}")
print(f"TTS configured: {tts.voice_id}")
```

## 📊 Expected Timing

```
Session start:         0ms
Wait for participant:  0-20,000ms
Prefetch:             40-80ms
RAG loading:          200-500ms
Greeting prep:        100-1500ms
Generate reply:       1000-3000ms
─────────────────────────────────
Total to first msg:   1500-5000ms
```

## 🚀 Next Steps

1. **Run the agent with debugging enabled**
2. **Check logs for the patterns above**
3. **Identify which step fails**
4. **Apply appropriate fix**
5. **Report findings** with log excerpts

## 📝 Common Issues & Solutions

| Issue | Log Pattern | Solution |
|-------|-------------|----------|
| **Session not starting** | No `[SESSION INIT] ✓` | Check LiveKit connection |
| **No participant** | `No participant joined within timeout` | Check client connection |
| **Bad identity** | `identity could not be parsed as UUID` | Fix participant identity format |
| **Hook not called** | No `[HOOK]` logs | Check LiveKit version/compatibility |
| **Empty instructions** | `Instructions length: 0` | Check base_instructions initialization |
| **LLM error** | Exception in generate_reply | Check OpenAI API key/quota |
| **TTS error** | TTS-related exception | Check Uplift TTS service |

---

**With these debugging logs, you should be able to identify exactly where and why the first message is failing.**

Run the agent and share the logs - we'll find the issue! 🔍

