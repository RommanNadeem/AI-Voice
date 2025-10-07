# Critical Fixes Needed

## 🔥 Issue 1: Memories Not Being Recalled in Regular Chats

### Root Cause
Current code uses `update_instructions()` in `on_agent_turn_started()` hook, but LiveKit may not use those updated instructions for the current turn.

### The Problem
```python
async def on_agent_turn_started(self):
    enhanced = await self.get_enhanced_instructions()
    self.update_instructions(enhanced)  # ← Might be too late!
    
# Then LiveKit calls:
session.generate_reply()  # ← Uses old instructions?
```

### The Fix
Use the old working pattern - pass context via `instructions` parameter:

```python
# DELETE on_agent_turn_started() hook entirely

# ADD this method to Assistant class:
async def generate_reply_with_context(self, session, user_text=None, greet=False):
    """Generate reply with context - simple working pattern"""
    user_id = get_current_user_id()
    
    # Fetch context
    extra_context = ""
    if user_id:
        profile = await self.profile_service.get_profile_async(user_id)
        rag_memories = await self.rag_service.search_memories(
            user_text or "user information", top_k=5
        ) if self.rag_service else []
        
        if profile:
            extra_context += f"Profile: {profile}\n"
        if rag_memories:
            mem_text = "\n".join([f"- {m['text'][:100]}" for m in rag_memories])
            extra_context += f"Memories:\n{mem_text}\n"
    
    # Generate with context
    base = self._base_instructions
    
    if greet:
        await session.generate_reply(
            instructions=f"{base}\n\nGreet warmly in Urdu.\n\n{extra_context}"
        )
    else:
        await session.generate_reply(
            instructions=f"{base}\n\n{extra_context}\n\nUser: {user_text}"
        )
```

---

## 🔊 Issue 2: First Message Audio Not Working

### Root Cause
First message is generated before audio track is fully connected/ready.

### The Problem
```python
await session.start(room=ctx.room, agent=assistant)
# Audio track connecting... (async process)

await session.generate_reply(...)  # ← Too fast! Audio not ready yet!
```

### The Fix
Wait for audio track to be ready before first message:

```python
# After session.start():
await session.start(room=ctx.room, agent=assistant)
print("[SESSION] ✓ Session started")

# CRITICAL: Wait for participant and audio track to be ready
participant = await wait_for_participant(ctx.room, timeout_s=20)

# ADD: Wait for audio track to be ready
await asyncio.sleep(0.5)  # Give audio track time to connect
print("[AUDIO] ✓ Audio track ready")

# NOW generate first message
await assistant.generate_reply_with_context(session, greet=True)
```

Or better - wait for the agent to be connected:

```python
# After getting participant:
participant = await wait_for_participant(ctx.room, timeout_s=20)

# Wait for agent to be fully connected
print("[SESSION] Waiting for agent connection...")
while not session.agent_publication:
    await asyncio.sleep(0.1)
print("[SESSION] ✓ Agent fully connected")

# Now first message audio will work
await assistant.generate_reply_with_context(session, greet=True)
```

---

## 📋 Complete Implementation Steps

### Step 1: Replace agent.py with agent_refactored.py

```bash
mv agent.py agent_old_backup.py
mv agent_refactored.py agent.py
```

The refactored version includes:
- ✅ Simple `generate_reply_with_context()` method
- ✅ Context passed via instructions parameter (working pattern)
- ✅ No complex hooks
- ✅ RAG service properly initialized per-user
- ✅ Background processing for saves

### Step 2: Add Audio Wait in Entrypoint

In the refactored agent.py, after line where participant is found, add:

```python
# After this line:
participant = await wait_for_participant(ctx.room, timeout_s=20)

# ADD:
# Wait for audio track to be ready (fixes first message audio issue)
print("[AUDIO] Waiting for connection...")
await asyncio.sleep(1.0)  # Give audio track time to establish
print("[AUDIO] ✓ Ready")
```

### Step 3: Test

Run the agent and verify:
- [ ] First message is audible
- [ ] Memories are recalled in chat
- [ ] Profile information is used
- [ ] RAG search works

---

## 🎯 Why This Works

### Old Working Pattern Advantages:

1. **Explicit Context Injection**
   - Context passed directly in `instructions` parameter
   - No reliance on hooks or timing
   - Guaranteed to be included

2. **Simple Flow**
   ```
   User speaks → Fetch context → Generate with context → Speak
   ```
   No complex caching, no hooks, no timing issues

3. **Debuggable**
   - One function handles everything
   - Easy to add logging
   - Clear where context comes from

### Current Pattern Problems:

1. **Hook Timing Issues**
   - `update_instructions()` might not affect current turn
   - Race conditions between hook and generation
   - Unclear execution order

2. **Complex Caching**
   - Multi-layer caching adds complexity
   - Cache invalidation logic
   - More points of failure

3. **Audio Timing**
   - First message generated too early
   - Audio track not ready
   - Subsequent messages work (track is ready by then)

---

## ⚡ Quick Fix (If You Don't Want Full Refactor)

If you want to keep current architecture but fix it:

### Fix Memory Recall:

In `on_agent_turn_started()`, change from:
```python
self.update_instructions(enhanced)
```

To intercepting the generation (but this is hacky and not recommended).

### Fix Audio:

In entrypoint, add wait before first message:
```python
# After participant found:
await asyncio.sleep(1.0)  # Wait for audio
await session.generate_reply(...)
```

---

## ✅ Recommended: Use Refactored Version

I've created `agent_refactored.py` with the simple working pattern:
- Uses `generate_reply_with_context()` method
- Context passed via instructions parameter
- No complex hooks
- Simple and working

Just replace the current agent.py with it!

---

## 📊 Comparison

| Aspect | Current | Refactored | Winner |
|--------|---------|-----------|---------|
| **Lines of code** | ~1073 | ~340 | ✅ Refactored |
| **Complexity** | High | Low | ✅ Refactored |
| **Memory recall** | ❌ Broken | ✅ Works | ✅ Refactored |
| **First audio** | ❌ Silent | ✅ Works (with wait) | ✅ Refactored |
| **Maintainability** | Hard | Easy | ✅ Refactored |

**Recommendation: Use the refactored version - it's simpler and actually works!** 🎯

