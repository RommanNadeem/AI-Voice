# Console Output Example

## Complete Flow Example

Here's what you'll see in the console when everything is working correctly:

### 1. Agent Startup & Initialization
```
[ENTRYPOINT] Starting session for room: test-room
[ENTRYPOINT] ✓ Connection pool initialized
[ENTRYPOINT] ✓ Redis cache initialized
[ENTRYPOINT] ✓ Database batcher initialized
[SESSION INIT] Starting LiveKit session…
[SESSION INIT] ✓ Session started
[ENTRYPOINT] Participant: sid=PA_xxx, identity=12345678-1234-1234-1234-123456789abc

[INIT] 🔄 Starting parallel initialization (RAG + Onboarding)...
[RAG] Loading memories from database...
[RAG] ✓ Memories loaded and indexed before first message
[ONBOARDING] ✓ User initialization complete

[GREETING] 🎯 Generating intelligent first message...
[GREETING] Context will be auto-injected via on_agent_turn_started() hook
[STATE] Current: ORIENTATION (Trust: 5.0/10)
[GREETING] ✓ Greeting strategy prepared
[GREETING] 🚀 Generating response (context will be auto-injected)...

[ON_AGENT_TURN #1] 🔄 Refreshing context before AI response...
[CONTEXT INJECTION #1] 🔄 Fetching enhanced context for user 12345678...
[CONTEXT SERVICE] 🔍 Fetching user's first name for 12345678...
[CONTEXT SERVICE] ℹ️  User's name not found yet
[CONTEXT FORMAT] ℹ️  No user name available for context injection
[RAG] 🔍 Searching for relevant memories...
[RAG] ℹ️  No memories found yet
[CONTEXT INJECTION #1] ✅ Enhanced context injected in 120.5ms (cache hit rate: 0.0%)
[CONTEXT DETAILS] RAG memories: 0, Recent memories: 0, Profile: False
[CONTEXT SIZE] Base: 5000 chars, Enhanced: 5200 chars, Overhead: 200 chars
[ON_AGENT_TURN #1] ✓ Context refreshed in 122.1ms

[AI speaks greeting in Urdu]
```

### 2. User Shares Their Name
```
[USER INPUT] 💬 Mera naam Ahmed hai aur mujhe cricket pasand hai

[CONTEXT UPDATE] ✓ RAG context updated with user input
[CACHE INVALIDATION] ✓ Context cache invalidated after user input

[BACKGROUND] 🔄 Processing user input with RAG (optimized)...

[AUTO MEMORY] 💾 Saving: [INTEREST] user_input_1704567890123
[MEMORY SERVICE] 💾 Saving memory: [INTEREST] user_input_1704567890123
[MEMORY SERVICE]    Value: Mera naam Ahmed hai aur mujhe cricket pasand hai
[MEMORY SERVICE]    User: 12345678...
[MEMORY SERVICE] ✅ Saved successfully: [INTEREST] user_input_1704567890123
[AUTO MEMORY] ✅ Saved to Supabase

[RAG] ✅ Memory queued for indexing

[PROFILE SERVICE] ✅ Generated profile:
[PROFILE SERVICE]    Ahmed is passionate about cricket and enjoys playing the sport. He has shared his interest in the game...
[PROFILE SERVICE] 💾 Saving profile for user 12345678...
[PROFILE SERVICE]    Ahmed is passionate about cricket and enjoys playing the sport...
[PROFILE SERVICE] ✅ Profile saved successfully (cache invalidated)
[PROFILE SERVICE]    User: 12345678...
[AUTO PROFILE] ✅ Updated (cache invalidated)

[AUTO STATE] ℹ️  No state changes needed
[BACKGROUND] ✅ Completed in 0.85s (optimized with parallel processing)

[ON_AGENT_TURN #2] 🔄 Refreshing context before AI response...
[CONTEXT INJECTION #2] 🔄 Fetching enhanced context for user 12345678...

[PROFILE SERVICE] 🔍 Fetching profile (async) for user 12345678...
[PROFILE SERVICE] ℹ️  Cache miss - fetching from database...
[PROFILE SERVICE] ✅ Profile fetched from DB and cached
[PROFILE SERVICE]    Ahmed is passionate about cricket and enjoys playing the sport...

[CONTEXT SERVICE] 🔍 Fetching user's first name for 12345678...
[CONTEXT SERVICE] ✅ User's name found: 'Ahmed' (from key: user_input_1704567890123)
[CONTEXT FORMAT] 👤 Injecting user's name into context: 'Ahmed'

[RAG] 🔍 Searching for relevant memories...
[RAG] ✅ Retrieved 1 relevant memories
[RAG #1] INTEREST: Mera naam Ahmed hai aur mujhe cricket pas... (score: 0.892)

[CONTEXT INJECTION #2] ✅ Enhanced context injected in 85.3ms (cache hit rate: 50.0%)
[CONTEXT DETAILS] RAG memories: 1, Recent memories: 1, Profile: True
[CONTEXT SIZE] Base: 5000 chars, Enhanced: 7800 chars, Overhead: 2800 chars
[ON_AGENT_TURN #2] ✓ Context refreshed in 87.1ms

[AI responds using Ahmed's name and cricket interest]
```

### 3. User Asks About Their Information
```
[USER INPUT] 💬 Mujhe kaun se sports pasand hain?

[CONTEXT UPDATE] ✓ RAG context updated with user input
[CACHE INVALIDATION] ✓ Context cache invalidated after user input

[BACKGROUND] 🔄 Processing user input with RAG (optimized)...

[AUTO MEMORY] 💾 Saving: [FACT] user_input_1704567890456
[MEMORY SERVICE] 💾 Saving memory: [FACT] user_input_1704567890456
[MEMORY SERVICE]    Value: Mujhe kaun se sports pasand hain?
[MEMORY SERVICE]    User: 12345678...
[MEMORY SERVICE] ✅ Saved successfully: [FACT] user_input_1704567890456
[AUTO MEMORY] ✅ Saved to Supabase

[RAG] ✅ Memory queued for indexing

[PROFILE SERVICE] ℹ️  No meaningful profile info found in: Mujhe kaun se sports pasand hain?...
[AUTO PROFILE] ℹ️  No new info to extract

[AUTO STATE] ℹ️  No state changes needed
[BACKGROUND] ✅ Completed in 0.62s (optimized with parallel processing)

[ON_AGENT_TURN #3] 🔄 Refreshing context before AI response...
[CONTEXT INJECTION #3] 🔄 Fetching enhanced context for user 12345678...

[PROFILE SERVICE] 🔍 Fetching profile (async) for user 12345678...
[PROFILE SERVICE] ✅ Cache hit - profile found in Redis
[PROFILE SERVICE]    Ahmed is passionate about cricket and enjoys playing the sport...

[CONTEXT SERVICE] 🔍 Fetching user's first name for 12345678...
[CONTEXT SERVICE] ✅ User's name found: 'Ahmed' (from key: user_input_1704567890123)
[CONTEXT FORMAT] 👤 Injecting user's name into context: 'Ahmed'

[RAG] 🔍 Searching for relevant memories...
[RAG] ✅ Retrieved 2 relevant memories
[RAG #1] INTEREST: Mera naam Ahmed hai aur mujhe cricket pas... (score: 0.945)
[RAG #2] FACT: Mujhe kaun se sports pasand hain? (score: 0.823)

[CONTEXT INJECTION #3] ✅ Enhanced context injected in 45.2ms (cache hit rate: 66.7%)
[CONTEXT DETAILS] RAG memories: 2, Recent memories: 2, Profile: True
[CONTEXT SIZE] Base: 5000 chars, Enhanced: 8200 chars, Overhead: 3200 chars
[ON_AGENT_TURN #3] ✓ Context refreshed in 46.8ms

[AI responds with cricket information from memory]
```

### 4. User Shares More Information
```
[USER INPUT] 💬 Main software engineer hun aur machine learning seekhna chahta hun

[CONTEXT UPDATE] ✓ RAG context updated with user input
[CACHE INVALIDATION] ✓ Context cache invalidated after user input

[BACKGROUND] 🔄 Processing user input with RAG (optimized)...

[AUTO MEMORY] 💾 Saving: [GOAL] user_input_1704567890789
[MEMORY SERVICE] 💾 Saving memory: [GOAL] user_input_1704567890789
[MEMORY SERVICE]    Value: Main software engineer hun aur machine learning seekhna chahta hun
[MEMORY SERVICE]    User: 12345678...
[MEMORY SERVICE] ✅ Saved successfully: [GOAL] user_input_1704567890789
[AUTO MEMORY] ✅ Saved to Supabase

[RAG] ✅ Memory queued for indexing

[PROFILE SERVICE] ✅ Updated profile:
[PROFILE SERVICE]    Ahmed is passionate about cricket and enjoys playing the sport. He works as a software engineer and ha...
[PROFILE SERVICE] 💾 Saving profile for user 12345678...
[PROFILE SERVICE]    Ahmed is passionate about cricket and enjoys playing the sport. He works as a software engineer and ha...
[PROFILE SERVICE] ✅ Profile saved successfully (cache invalidated)
[AUTO PROFILE] ✅ Updated (cache invalidated)

[AUTO STATE] 📊 Trust adjusted: 5.0 → 6.2
[BACKGROUND] ✅ Completed in 0.94s (optimized with parallel processing)

[ON_AGENT_TURN #4] 🔄 Refreshing context before AI response...
[CONTEXT INJECTION #4] 🔄 Fetching enhanced context for user 12345678...

[PROFILE SERVICE] 🔍 Fetching profile (async) for user 12345678...
[PROFILE SERVICE] ℹ️  Cache miss - fetching from database...
[PROFILE SERVICE] ✅ Profile fetched from DB and cached
[PROFILE SERVICE]    Ahmed is passionate about cricket and enjoys playing the sport. He works as a software engineer...

[CONTEXT SERVICE] 🔍 Fetching user's first name for 12345678...
[CONTEXT SERVICE] ✅ User's name found: 'Ahmed' (from key: user_input_1704567890123)
[CONTEXT FORMAT] 👤 Injecting user's name into context: 'Ahmed'

[RAG] 🔍 Searching for relevant memories...
[RAG] ✅ Retrieved 3 relevant memories
[RAG #1] GOAL: Main software engineer hun aur machine learni... (score: 0.923)
[RAG #2] INTEREST: Mera naam Ahmed hai aur mujhe cricket pas... (score: 0.867)
[RAG #3] FACT: Mujhe kaun se sports pasand hain? (score: 0.745)

[CONTEXT INJECTION #4] ✅ Enhanced context injected in 120.8ms (cache hit rate: 75.0%)
[CONTEXT DETAILS] RAG memories: 3, Recent memories: 3, Profile: True
[CONTEXT SIZE] Base: 5000 chars, Enhanced: 9500 chars, Overhead: 4500 chars
[ON_AGENT_TURN #4] ✓ Context refreshed in 122.3ms

[AI responds acknowledging software engineer role and ML learning goal]
```

## Key Observations

### ✅ What You Should See:

1. **Context Injection Before Every Response**
   - `[ON_AGENT_TURN #N]` incrementing with each turn
   - `[CONTEXT INJECTION #N]` matching the turn number
   - Context refresh happening before AI speaks

2. **Memory Operations**
   - Every user message saved with `[MEMORY SERVICE] 💾 Saving memory`
   - Success confirmation with `[MEMORY SERVICE] ✅ Saved successfully`
   - Category automatically determined (INTEREST, GOAL, FACT, etc.)

3. **Profile Updates**
   - Profile generated when new information detected
   - Profile saved and cached
   - Profile fetched on subsequent turns (with cache hits)

4. **Name Tracking**
   - Name extracted from first mention
   - Name fetched on every context refresh
   - Name injected into context: `[CONTEXT FORMAT] 👤 Injecting user's name`

5. **RAG Integration**
   - Memories indexed in background
   - Relevant memories retrieved before each response
   - Semantic search with relevance scores

6. **Cache Performance**
   - Cache hit rate increasing over time
   - Cache invalidation after user input
   - Profile cache hits after first fetch

7. **Background Processing**
   - Completes in < 1s typically
   - Parallel execution of multiple tasks
   - Zero latency impact on responses

### ❌ What Indicates Problems:

1. **No context injection**
   ```
   Missing: [ON_AGENT_TURN #N] 🔄 Refreshing context
   ```

2. **Memory not saving**
   ```
   [MEMORY SERVICE] ❌ Save error: ...
   ```

3. **Profile not updating**
   ```
   [PROFILE SERVICE] ❌ Fetch error: ...
   ```

4. **Name not found**
   ```
   [CONTEXT SERVICE] ℹ️  User's name not found yet
   (persisting after user shared name)
   ```

5. **Low cache hit rate**
   ```
   (cache hit rate: 20.0%)
   (should increase to 70%+ after warmup)
   ```

## Quick Health Check

Run your agent and verify these patterns appear in the console:

```bash
# ✅ Context injection happening
grep "ON_AGENT_TURN" your_log.txt
# Should show: #1, #2, #3, #4... incrementing

# ✅ Memories being saved
grep "MEMORY SERVICE.*Saved successfully" your_log.txt
# Should show successful saves after each user message

# ✅ Profile being updated
grep "PROFILE SERVICE.*saved successfully" your_log.txt
# Should show updates when new info shared

# ✅ Name being tracked
grep "User's name found" your_log.txt
# Should show name after user introduces themselves

# ✅ No errors
grep "❌" your_log.txt
# Should be empty or minimal
```

If you see all these patterns, your system is working correctly! 🎉

