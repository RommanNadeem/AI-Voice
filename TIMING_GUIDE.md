# ⏱️ Agent Startup Timing Guide

## Overview

The agent now includes detailed timing measurements to track performance from startup to first greeting.

---

## Timestamps Added

### Startup Sequence Timers:

1. **Start (0.00s)**
   - Job received, room initialization begins

2. **Infrastructure Ready**
   - Connection pool, Redis, database batcher initialized

3. **Room Connected**
   - Successfully connected to LiveKit room

4. **Participant Joined**
   - User joined the room, identity extracted

5. **User Data Loaded**
   - Onboarding data fetched (name, gender)

6. **Context Loaded**
   - Profile + memories loaded from database

7. **Agent Created**
   - Assistant instance created with context

8. **Session Ready**
   - AgentSession started and initialized

9. **Starting Greeting**
   - About to generate greeting

10. **🎉 FIRST GREETING COMPLETE**
    - Greeting sent to user (total time from start)

### Background Timers:

- **RAG Loading** - Time to load and index memories (parallel)

---

## Expected Timing (After Optimizations)

### First Run (New User):
```
[TIMER] ⏱️  Start time: 0.00s
[TIMER] ⏱️  Infrastructure ready: ~1.5s
[TIMER] ⏱️  Room connected: ~1.7s
[TIMER] ⏱️  Participant joined: ~1.8s
[TIMER] ⏱️  User data loaded: ~4.0s
[TIMER] ⏱️  Context loaded: ~6.0s
[TIMER] ⏱️  Agent created: ~6.5s
[TIMER] ⏱️  Session ready: ~7.0s
[TIMER] ⏱️  Starting greeting: ~7.3s
[TIMER] 🎉 FIRST GREETING COMPLETE: ~7.5s
```

### Subsequent Runs (Existing User - Cached):
```
[TIMER] ⏱️  Start time: 0.00s
[TIMER] ⏱️  Infrastructure ready: ~1.5s
[TIMER] ⏱️  Room connected: ~1.7s
[TIMER] ⏱️  Participant joined: ~1.8s
[TIMER] ⏱️  User data loaded: ~2.0s  ⚡ (cached init check)
[TIMER] ⏱️  Context loaded: ~4.0s
[TIMER] ⏱️  Agent created: ~4.5s
[TIMER] ⏱️  Session ready: ~5.0s
[TIMER] ⏱️  Starting greeting: ~5.3s
[TIMER] 🎉 FIRST GREETING COMPLETE: ~5.5s
```

---

## How to Read the Logs

### Example Output:
```bash
================================================================================
[ENTRYPOINT] 🚀 NEW JOB RECEIVED
[ENTRYPOINT] Room: mock_room
[ENTRYPOINT] Job ID: simulated-job-abc123
================================================================================
[TIMER] ⏱️  Start time: 0.00s
[POOL] Initializing connection pool...
[POOL] ✓ OpenAI clients initialized with connection pooling
[POOL] ✓ Connection pool initialized with health monitoring
[ENTRYPOINT] ✓ Connection pool initialized
[REDIS] Connecting to redis://localhost:6379/0...
[REDIS] Warning: Connection failed
[REDIS] Continuing without Redis caching
[BATCH] Database batcher initialized
[ENTRYPOINT] ✓ Database batcher initialized
[TIMER] ⏱️  Infrastructure ready: 1.52s
[ENTRYPOINT] Connecting to LiveKit room...
[ENTRYPOINT] ✓ Connected to room
[TIMER] ⏱️  Room connected: 1.68s
...
[TIMER] 🎉 FIRST GREETING COMPLETE: 5.42s
================================================================================
```

### Phase Breakdown:

| Phase | Time Range | What's Happening |
|-------|------------|------------------|
| **Infrastructure** | 0.0s - 1.5s | Connection pools, Redis, DB batcher |
| **Room Setup** | 1.5s - 1.8s | LiveKit room connection, participant wait |
| **User Data** | 1.8s - 4.0s | Onboarding init, name/gender fetch |
| **Context** | 4.0s - 6.0s | Profile + memories loading |
| **Agent Setup** | 6.0s - 7.0s | Assistant creation, session start |
| **Greeting** | 7.0s - 7.5s | Hardcoded greeting generation + TTS |

---

## Identifying Bottlenecks

### If Infrastructure is Slow (>2s):
- Check network connection
- Check Redis connectivity (should fail fast at ~1s)
- Check Supabase connection speed

### If User Data is Slow (>2s after participant join):
- First run: Normal (~2s for initialization checks)
- Subsequent runs: Should be <0.5s (cached)
- If slow on subsequent runs: Check session cache

### If Context is Slow (>2s):
- Check database query performance
- Profile fetch: Should be ~1.8s
- Memories batch fetch: Should be ~0.3s

### If Greeting is Slow (>1s):
- Should be nearly instant (<0.1s)
- If slow: Check if name was passed correctly
- TTS synthesis happens during playback (doesn't block)

---

## Monitoring Performance

### Good Performance Indicators:
✅ Infrastructure: <2s  
✅ User Data (cached): <0.5s  
✅ Context Load: <2.5s  
✅ Greeting Gen: <0.2s  
✅ **Total First Greeting: <6s**

### Warning Signs:
⚠️ Infrastructure: >3s - Network issues  
⚠️ User Data (cached): >1s - Cache not working  
⚠️ Context Load: >3s - Database slow  
⚠️ Greeting Gen: >0.5s - Not using hardcoded greeting  
⚠️ **Total First Greeting: >8s - Multiple issues**

---

## Debug Commands

### View Just Timing Info:
```bash
python agent.py | grep TIMER
```

### View Phase Summary:
```bash
python agent.py | grep -E "(TIMER|✅.*complete)"
```

### View Complete Flow:
```bash
python agent.py | grep -E "(TIMER|ENTRYPOINT|GREETING)"
```

---

## Optimization History

### Before Optimizations (~20s):
- Infrastructure: ~2s
- User Data: ~4s (duplicate checks)
- Context: ~2s
- Greeting: ~9s (LLM call)
- RAG: ~3s (46 individual API calls)

### After Optimizations (~5-7s):
- Infrastructure: ~1.5s (faster Redis timeout)
- User Data: ~2s first run, ~0.1s cached
- Context: ~2s (batch optimized)
- Greeting: ~0.1s (hardcoded + direct TTS)
- RAG: ~0.5s (batch API call, background)

### Total Improvement: **65-75% faster**

---

## Background Tasks

These run in parallel (don't block greeting):

### RAG Loading:
```
[RAG_BG] Loading memories in background...
[RAG_BG] ✅ Loaded 46 memories in 0.48s
```

### Prefetch:
```
[BATCH_BG] ✅ Prefetched 46 memories in background
```

**Note:** These complete after the greeting is sent, ensuring instant first response.

---

## Comparing Runs

### Track Performance Over Time:
```bash
# Save timing data
python agent.py 2>&1 | grep "FIRST GREETING COMPLETE" >> timing_log.txt

# View history
cat timing_log.txt
```

### Expected Output:
```
[TIMER] 🎉 FIRST GREETING COMPLETE: 5.42s
[TIMER] 🎉 FIRST GREETING COMPLETE: 4.98s  ⬅️ Cached (faster)
[TIMER] 🎉 FIRST GREETING COMPLETE: 5.15s
```

---

## Next Steps

If performance is still not satisfactory:

1. **Enable Redis** - Cache context data (save ~2s)
2. **Parallel Context Loading** - Load profile + memories simultaneously
3. **Persistent RAG Index** - Save embeddings to disk (save ~0.5s)
4. **Preload TTS** - Keep WebSocket connection warm

---

**Happy Optimizing! ⚡**

