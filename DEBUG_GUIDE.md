# Memory Retrieval Debug Guide

## Overview
This guide helps diagnose why memories work during active sessions but not in new sessions.

## Debug Statements Added

### 1. Database Query Tracking (`rag_system.py`)
**What it tracks:**
- Whether memories are being queried from Supabase correctly
- How many memories are returned per user
- Sample of what memories look like
- Success/failure of embedding creation

**Key logs to watch:**
```
[DEBUG][DB] Querying memory table for user_id: abc12345, limit: 50
[DEBUG][DB] ✅ Query returned 127 memories from database
[DEBUG][DB] Sample memories retrieved:
[DEBUG][DB]   #1: [FACT] My name is Sarah...
[DEBUG][DB]   #2: [INTEREST] I love photography...
```

**Red flags:**
- `[DEBUG][DB] ⚠️  No memories found in database for user abc12345` - Database is empty
- `[DEBUG][DB] ❌ Error loading from Supabase` - Query failed
- `Query returned 0 memories` when you expect some - Wrong user_id or data issue

### 2. RAG Persistence Tracking (`rag_system.py` + `agent.py`)
**What it tracks:**
- Whether RAG instance is reused or created fresh each session
- Memory count before/after loading
- FAISS index size

**Key logs to watch:**
```
[DEBUG][RAG] get_or_create_rag called for user abc12345
[DEBUG][RAG] Current user_rag_systems keys: ['abc12345']
[DEBUG][RAG] ♻️  Returning EXISTING RAG for abc12345
[DEBUG][RAG]    Existing RAG has 127 memories
```

**Red flags:**
- `[DEBUG][RAG] 🆕 Creating NEW RAG instance` every session - RAG not persisted!
- `[DEBUG][RAG] ✅ RAG now has 0 memories` - Loading failed
- `FAISS index size: 0` - Index is empty

### 3. User ID Collision Tracking (`core/validators.py`)
**What it tracks:**
- When user_id changes in global state
- If multiple users overwrite each other's sessions

**Key logs to watch:**
```
[DEBUG][USER_ID] ✅ Global _current_user_id = abc12345
[DEBUG][USER_ID] Retrieved user_id: abc12345
```

**Red flags:**
- `[DEBUG][USER_ID] ⚠️  USER_ID COLLISION DETECTED!` - Multiple users active!
- `[DEBUG][USER_ID] ⚠️  Retrieved user_id: NONE` - Lost user context

### 4. Context Building Tracking (`agent.py`)
**What it tracks:**
- What data is fetched for each reply
- Whether RAG memories are retrieved
- User name availability

**Key logs to watch:**
```
[DEBUG][CONTEXT] RAG service attached: True
[DEBUG][CONTEXT] RAG stats: 127 memories
[DEBUG][CONTEXT] RAG memories: 5 items
[DEBUG][CONTEXT] User name from context: 'Sarah'
```

**Red flags:**
- `[DEBUG][CONTEXT] ⚠️  No RAG memories retrieved!` - Search returned nothing
- `[DEBUG][CONTEXT] User name from context: 'None'` - Name not stored/retrieved
- `RAG service attached: False` - RAG not initialized

## Test Scenarios

### Test 1: Single User, Two Sessions (RAG Persistence)

**Session 1:**
```bash
# User says: "My name is Sarah, I'm a software engineer"

# Expected logs:
[DEBUG][DB] Query returned 1 memories from database  # (if first time)
[DEBUG][RAG] 🆕 Creating NEW RAG instance for abc12345  # First time OK
[DEBUG][RAG] ✅ RAG now has 1 memories
[DEBUG][DB] ✅ Added 1 memories to FAISS index
```

**Close session, start new one**

**Session 2:**
```bash
# User says: "Hi" (don't mention name)

# HEALTHY SYSTEM:
[DEBUG][RAG] ♻️  Returning EXISTING RAG for abc12345  # ✅ Reusing!
[DEBUG][RAG]    Existing RAG has 1 memories  # ✅ Persisted!
[DEBUG][DB] Query returned 1 memories from database
[DEBUG][CONTEXT] User name from context: 'Sarah'  # ✅ Name remembered!

# BROKEN SYSTEM (RAG not persisted):
[DEBUG][RAG] 🆕 Creating NEW RAG instance for abc12345  # ❌ Should be EXISTING!
[DEBUG][RAG]    Existing RAG has 0 memories  # ❌ Lost memories!
[DEBUG][CONTEXT] ⚠️  No RAG memories retrieved!  # ❌ Nothing to search!
```

**Diagnosis:**
If you see "Creating NEW RAG instance" every session:
- ✅ **Confirmed Issue**: RAG not persisted (Issue #1 - 90% likely)
- **Cause**: `user_rag_systems` dictionary cleared on process restart
- **Fix**: Implement RAG persistence to disk (see solution below)

### Test 2: Multi-User (User ID Collision)

**Setup:** Two users connect simultaneously or within minutes

**User A connects:**
```bash
[DEBUG][USER_ID] ✅ Global _current_user_id = aaaa1111
```

**User B connects (before A disconnects):**
```bash
# HEALTHY SYSTEM:
[DEBUG][USER_ID] ✅ Global _current_user_id = bbbb2222  # New user

# BROKEN SYSTEM:
[DEBUG][USER_ID] ⚠️  USER_ID COLLISION DETECTED!  # ❌ Collision!
[DEBUG][USER_ID]    Previous: aaaa1111
[DEBUG][USER_ID]    New:      bbbb2222
```

**User A sends message:**
```bash
# BROKEN SYSTEM:
[DEBUG][USER_ID] searchMemories - Current user_id: bbbb2222  # ❌ Wrong user!
[DEBUG][RAG] RAG user_id: bbbb2222  # ❌ User B's memories for User A!
```

**Diagnosis:**
If you see "USER_ID COLLISION DETECTED":
- ✅ **Confirmed Issue**: Global user_id collision (Issue #11 - 60% likely)
- **Cause**: Single global `_current_user_id` shared across sessions
- **Fix**: Use session-specific context (see solution below)

## Quick Diagnosis Commands

After running your test, check logs:

```bash
# 1. Check if RAG is persisted between sessions
grep "Creating NEW RAG" your_log.txt
# Expected: 1 per user ever
# Problem: Multiple times for same user = not persisted

# 2. Check for user_id collisions
grep "USER_ID COLLISION" your_log.txt
# Expected: 0 lines
# Problem: Any lines = multi-user bug

# 3. Check database query success
grep "Query returned.*memories from database" your_log.txt
# Expected: Increasing numbers over time
# Problem: "0 memories" or decreasing = database issue

# 4. Check memory loading success
grep "RAG now has.*memories" your_log.txt
# Expected: Matches query results
# Problem: "0 memories" when query returned data = loading issue

# 5. Check context retrieval
grep "No RAG memories retrieved" your_log.txt
# Expected: 0 lines
# Problem: Multiple occurrences = search failing

# 6. Get full debug summary
grep "\[DEBUG\]" your_log.txt | tail -100
```

## Common Issues & Solutions

### Issue 1: "No memories found in database"
**Symptoms:**
```
[DEBUG][DB] ⚠️  No memories found in database for user abc12345
```

**Causes:**
1. User ID mismatch (frontend sending different ID)
2. Memories not being saved to database
3. Wrong database/table

**Verify:**
```sql
-- Check if memories exist in Supabase
SELECT count(*), user_id 
FROM memory 
GROUP BY user_id;

-- Check specific user
SELECT * FROM memory 
WHERE user_id = 'abc12345-...' 
ORDER BY created_at DESC 
LIMIT 10;
```

### Issue 2: "Embeddings created: 0 total"
**Symptoms:**
```
[DEBUG][DB] Query returned 50 memories from database
[DEBUG][DB] Creating embeddings for 0 memories...
```

**Cause:** Memory values are empty or invalid

**Check:**
```
[DEBUG][DB] Sample memories retrieved:
[DEBUG][DB]   #1: [FACT] ...
```
If values are empty, check database integrity.

### Issue 3: "RAG service is None"
**Symptoms:**
```
[DEBUG][RAG] ❌ RAG service is None for user abc12345
```

**Cause:** RAG not initialized before tool call

**Check entrypoint logs:**
```
[DEBUG][RAG] ✅ RAG service attached to assistant
```
Should appear before first message.

## Solutions

### Solution 1: Persist RAG to Disk (Issue #1)

Add this to `agent.py` around line 580:

```python
# Initialize RAG for this user
print(f"[RAG] Initializing for user {user_id[:8]}...")
rag_service = RAGService(user_id)
assistant.rag_service = rag_service

# Try to load persisted index first
import os
index_path = f"/tmp/rag_index_{user_id}"
if os.path.exists(f"{index_path}.faiss"):
    print(f"[RAG] Loading persisted index from {index_path}")
    rag_service.load_index(index_path)
    print(f"[RAG] ✓ Loaded {len(rag_service.get_rag_system().memories)} memories from disk")
else:
    # Load from database and save
    await rag_service.load_from_database(supabase, limit=50)
    
    # Save for next session
    async def save_index_background():
        await rag_service.load_from_database(supabase, limit=500)
        rag_service.save_index(index_path)
        print(f"[RAG] ✓ Saved index to {index_path}")
    
    asyncio.create_task(save_index_background())
```

### Solution 2: Fix User ID Collision (Issue #11)

Use thread-local storage instead of global variable in `core/validators.py`:

```python
import threading

# Use thread-local storage instead of global
_thread_local = threading.local()

def set_current_user_id(user_id: str):
    """Set the current user ID for this thread/session"""
    _thread_local.user_id = user_id
    print(f"[SESSION] User ID set to: {user_id} (thread: {threading.current_thread().name})")

def get_current_user_id() -> Optional[str]:
    """Get the current user ID for this thread"""
    return getattr(_thread_local, 'user_id', None)
```

## Next Steps

1. **Run your test** with debug statements active
2. **Save logs** to a file for analysis
3. **Run diagnosis commands** above to identify issue
4. **Apply appropriate solution** based on findings
5. **Verify fix** with same test scenario

## Success Criteria

After implementing fixes, you should see:

✅ **Session 1:**
```
[DEBUG][RAG] 🆕 Creating NEW RAG instance  # First time
[DEBUG][DB] Query returned N memories
[DEBUG][RAG] ✅ RAG now has N memories
```

✅ **Session 2 (same user):**
```
[DEBUG][RAG] ♻️  Returning EXISTING RAG  # Reused!
[DEBUG][RAG]    Existing RAG has N memories  # Persisted!
[DEBUG][CONTEXT] User name from context: 'Sarah'  # Remembered!
[DEBUG][CONTEXT] RAG memories added: 5 items  # Retrieved!
```

✅ **Multi-user:**
```
User A: [DEBUG][USER_ID] ✅ Global _current_user_id = aaaa1111
User B: [DEBUG][USER_ID] ✅ Global _current_user_id = bbbb2222
# NO collision warnings
```

