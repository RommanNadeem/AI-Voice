# Debug Implementation Summary

## Changes Made

Comprehensive debug statements added to track two critical issues:
1. **RAG not persisted across sessions** (90% likely)
2. **Global user_id collision** (60% likely if multi-user)

## Files Modified

### 1. `agent.py`
**Lines modified:** 290-346, 348-435, 564-647

**Debug added:**
- ✅ Track user_id in `searchMemories` tool execution
- ✅ Check RAG state (memory count, FAISS index size, user_id match)
- ✅ Log exception details when memory search fails
- ✅ Track user_id during reply generation
- ✅ Log RAG service attachment status
- ✅ Show what context data is fetched (profile, memories, name)
- ✅ Warn when no RAG memories retrieved
- ✅ Verify user_id set correctly in entrypoint
- ✅ Check if RAG already exists (persistence check)
- ✅ Verify memories loaded after database query
- ✅ Show RAG stats before first greeting

**Key debug tags:**
- `[DEBUG][USER_ID]` - User ID tracking
- `[DEBUG][RAG]` - RAG system state
- `[DEBUG][CONTEXT]` - Context building
- `[DEBUG][GREETING]` - First message generation

### 2. `rag_system.py`
**Lines modified:** 478-559, 602-617

**Debug added:**
- ✅ Log database query parameters (user_id, limit)
- ✅ Show how many memories returned from database
- ✅ Display sample of retrieved memories (first 3)
- ✅ Warn when no memories found for user
- ✅ Track embedding creation (count, success/failure)
- ✅ Show how many memories added to FAISS
- ✅ Display final memory count and index size
- ✅ Log detailed error with traceback on failure
- ✅ Track RAG instance creation vs reuse
- ✅ Show existing RAG stats when reused

**Key debug tags:**
- `[DEBUG][DB]` - Database queries and loading
- `[DEBUG][RAG]` - RAG instance management

### 3. `core/validators.py`
**Lines modified:** 14-37

**Debug added:**
- ✅ Detect user_id collisions (when different user overwrites)
- ✅ Log old and new user_id on collision
- ✅ Confirm user_id set successfully
- ✅ Warn when user_id retrieval returns None

**Key debug tags:**
- `[DEBUG][USER_ID]` - User ID collision detection

### 4. `DEBUG_GUIDE.md` (NEW)
**Purpose:** Comprehensive guide for interpreting debug output

**Contents:**
- What each debug statement tracks
- Healthy system vs broken system log examples
- Test scenarios for both issues
- Quick diagnosis commands
- Common issues and solutions
- Success criteria

## How to Use

### Step 1: Run Your Test

**Single user test (RAG persistence):**
1. Session 1: Tell AI "My name is Sarah"
2. Close session
3. Session 2: Say "Hi" without mentioning name
4. Check if AI remembers the name

**Multi-user test (collision):**
1. Connect two users simultaneously
2. Check for collision warnings
3. Verify each user gets their own memories

### Step 2: Check Logs

Look for these patterns:

**✅ Healthy (memories working):**
```
[DEBUG][RAG] ♻️  Returning EXISTING RAG for abc12345
[DEBUG][RAG]    Existing RAG has 127 memories
[DEBUG][DB] Query returned 127 memories from database
[DEBUG][CONTEXT] User name from context: 'Sarah'
[DEBUG][CONTEXT] RAG memories added: 5 items
```

**❌ Issue #1: RAG not persisted:**
```
[DEBUG][RAG] 🆕 Creating NEW RAG instance for abc12345  ← Should be EXISTING!
[DEBUG][RAG] ✅ RAG now has 0 memories  ← Empty!
[DEBUG][CONTEXT] ⚠️  No RAG memories retrieved!
[DEBUG][CONTEXT] User name from context: 'None'
```

**❌ Issue #2: User ID collision:**
```
[DEBUG][USER_ID] ⚠️  USER_ID COLLISION DETECTED!
[DEBUG][USER_ID]    Previous: abc12345
[DEBUG][USER_ID]    New:      xyz67890
```

### Step 3: Diagnose with Commands

```bash
# Check RAG persistence
grep "Creating NEW RAG" logs.txt
# Should appear once per user, not every session

# Check user_id collisions
grep "USER_ID COLLISION" logs.txt
# Should be empty (0 lines)

# Check database queries
grep "\[DEBUG\]\[DB\]" logs.txt
# Verify correct user_id and memory counts

# Full debug output
grep "\[DEBUG\]" logs.txt | tail -100
```

### Step 4: Apply Fixes

Based on diagnosis results:

**If seeing "Creating NEW RAG every session":**
→ Implement RAG persistence to disk (see DEBUG_GUIDE.md Solution 1)

**If seeing "USER_ID COLLISION":**
→ Use thread-local storage (see DEBUG_GUIDE.md Solution 2)

**If seeing "No memories found in database":**
→ Check database queries and user_id consistency

## Expected Output Flow

### On Session Start (New User)
```
[DEBUG][USER_ID] ✅ Global _current_user_id = abc12345
[DEBUG][RAG] get_or_create_rag called for user abc12345
[DEBUG][RAG] Current user_rag_systems keys: []
[DEBUG][RAG] 🆕 Creating NEW RAG instance for abc12345  ← First time OK
[DEBUG][DB] Querying memory table for user_id: abc12345, limit: 50
[DEBUG][DB] ✅ Query returned 0 memories from database  ← New user
[DEBUG][RAG] ✅ RAG now has 0 memories
```

### After User Shares Information
```
[DEBUG][DB] Query returned 5 memories from database
[DEBUG][DB] Sample memories retrieved:
[DEBUG][DB]   #1: [FACT] My name is Sarah
[DEBUG][DB]   #2: [INTEREST] I love photography
[DEBUG][DB] Creating embeddings for 5 memories...
[DEBUG][DB] Successful: 5, Failed: 0
[DEBUG][DB] ✅ Added 5 memories to FAISS index
[DEBUG][RAG] ✅ RAG now has 5 memories
[DEBUG][RAG] FAISS index size: 5
```

### On Reply Generation
```
[DEBUG][USER_ID] generate_reply_with_context - user_id: abc12345
[DEBUG][RAG] RAG service attached: True
[DEBUG][RAG] RAG stats: 5 memories
[DEBUG][CONTEXT] Profile fetched: 150 chars
[DEBUG][CONTEXT] RAG memories: 3 items
[DEBUG][CONTEXT] User name from context: 'Sarah'
[DEBUG][CONTEXT] RAG memories added: 3 items
[DEBUG][CONTEXT] Total context length: 450 chars
```

### On searchMemories Tool Call
```
[TOOL] 🔍 searchMemories called: query='user name', limit=5
[DEBUG][USER_ID] searchMemories - Current user_id: abc12345
[DEBUG][RAG] RAG system exists: True
[DEBUG][RAG] Current RAG has 5 memories loaded
[DEBUG][RAG] RAG user_id: abc12345
[DEBUG][RAG] FAISS index total: 5
[TOOL] ✅ Found 2 memories
[TOOL]    #1: My name is Sarah
[TOOL]    #2: Sarah loves photography
```

### On New Session (Same User) - CRITICAL TEST
```
[DEBUG][RAG] get_or_create_rag called for user abc12345
[DEBUG][RAG] Current user_rag_systems keys: ['abc12345']  ← User exists!
[DEBUG][RAG] ♻️  Returning EXISTING RAG for abc12345  ← ✅ REUSING!
[DEBUG][RAG]    Existing RAG has 5 memories  ← ✅ PERSISTED!
[DEBUG][DB] Query returned 5 memories from database
[DEBUG][CONTEXT] User name from context: 'Sarah'  ← ✅ REMEMBERED!
```

**If you see this instead:**
```
[DEBUG][RAG] Current user_rag_systems keys: []  ← ❌ Empty!
[DEBUG][RAG] 🆕 Creating NEW RAG instance  ← ❌ Should be EXISTING!
```
→ **Confirmed: RAG not persisted (Issue #1)**

## Debug Statement Statistics

- **Total debug statements added:** ~40
- **Critical checkpoints:** 8
  - User ID set/get
  - RAG instance creation/reuse  
  - Database query success
  - Memory loading success
  - Embedding creation
  - Context retrieval
  - First greeting generation
  - Tool execution

- **Debug tags used:** 5
  - `[DEBUG][USER_ID]` - User context tracking
  - `[DEBUG][RAG]` - RAG system state
  - `[DEBUG][DB]` - Database operations
  - `[DEBUG][CONTEXT]` - Context building
  - `[DEBUG][GREETING]` - First message

## Performance Impact

- **Minimal:** Debug print statements are negligible overhead
- **Can be disabled:** Comment out debug sections if needed
- **Recommended:** Keep enabled in development, disable in production

## Next Steps

1. ✅ **Debug statements implemented**
2. ⏭️ **Run test scenario** (single user, two sessions)
3. ⏭️ **Analyze logs** using DEBUG_GUIDE.md
4. ⏭️ **Identify root cause** (RAG persistence vs user_id collision)
5. ⏭️ **Implement fix** from DEBUG_GUIDE.md solutions
6. ⏭️ **Verify fix** with same test
7. ⏭️ **Optional:** Remove/reduce debug statements after fix confirmed

## Files to Review

- `DEBUG_GUIDE.md` - Comprehensive diagnosis guide
- `agent.py` - Main debug logic
- `rag_system.py` - Database and RAG tracking
- `core/validators.py` - User ID collision detection

