# Quick Test: Name Retrieval Verification

## Purpose
Test if name is correctly retrieved when already stored in:
1. **memory table** (as a FACT)
2. **user_profile table**

## Prerequisites

1. **You need a user_id** that already has data in your database
2. **Supabase credentials** must be configured in your environment

## How to Get Your User ID

### Option 1: From Recent Logs
Look at your agent logs for lines like:
```
[SESSION] User ID set to: abc12345-1234-1234-1234-123456789abc
```

### Option 2: Query Supabase Directly
Run this SQL in Supabase dashboard:
```sql
-- Get all users with memories
SELECT DISTINCT user_id, COUNT(*) as memory_count 
FROM memory 
GROUP BY user_id
ORDER BY memory_count DESC;
```

### Option 3: From Frontend
Check your frontend code where you create the LiveKit connection - the user_id should be passed there.

## Running the Test

### Step 1: Run the test script

```bash
cd /Users/romman/Downloads/Companion
python test_memory_retrieval.py YOUR_USER_ID
```

**Example:**
```bash
python test_memory_retrieval.py abc12345-1234-1234-1234-123456789abc
```

### Step 2: Review the Output

The test will run 6 comprehensive checks:

#### ✅ Expected Output (All Working)
```
=================================================================
  TEST: Memory Retrieval for Name
=================================================================
User ID: abc12345-1234-1234-1234-123456789abc

[SETUP] Connecting to Supabase...
✅ Supabase connected
✅ Set current user_id: abc12345...

=================================================================
  TEST 1: Memory Table Query
=================================================================
📊 Total memories in database: 127

📝 Sample memories:
  1. [FACT] name: Sarah
  2. [INTEREST] hobbies: I love photography
  3. [GOAL] career: Want to become a software architect

🔍 Found 1 potential name-related memories:
   - [FACT] name: Sarah

=================================================================
  TEST 2: User Profile Table Query
=================================================================
✅ Profile found: 245 chars

📄 Profile content:
   Sarah is a 25-year-old software engineer based in San Francisco. She's passionate about photography...

✅ Profile appears to contain name information

=================================================================
  TEST 3: Memory Service Name Retrieval
=================================================================
✅ Found name with key 'name': Sarah

=================================================================
  TEST 4: Profile Service Retrieval
=================================================================
✅ Profile retrieved: 245 chars
📄 Content: Sarah is a 25-year-old software engineer...

=================================================================
  TEST 5: RAG System Memory Loading
=================================================================
[RAG] Creating RAG system...
[DEBUG][RAG] get_or_create_rag called for user abc12345
[RAG] Loading memories from database...
[DEBUG][DB] Querying memory table for user_id: abc12345, limit: 100
[DEBUG][DB] ✅ Query returned 127 memories from database
[DEBUG][DB] Sample memories retrieved:
[DEBUG][DB]   #1: [FACT] Sarah
[DEBUG][DB]   #2: [INTEREST] I love photography
[DEBUG][DB] Creating embeddings for 127 memories...
[DEBUG][DB] Successful: 127, Failed: 0
✅ RAG loaded 127 memories
   FAISS index size: 127

📝 Sample RAG memories:
  1. [FACT] Sarah
  2. [INTEREST] I love photography
  3. [GOAL] Want to become a software architect

[RAG] Searching for 'name'...
✅ Found 3 relevant memories:
  1. Sarah (score: 0.856)
  2. My name is Sarah (score: 0.823)
  3. I'm Sarah, a software engineer (score: 0.791)

=================================================================
  TEST 6: ConversationContextService Name Retrieval
=================================================================
✅ Name found in context: 'Sarah'

📊 Full context keys: ['user_profile', 'conversation_state', 'recent_memories', 'onboarding_data', 'last_conversation', 'user_name', 'fetched_at']

=================================================================
  TEST SUMMARY
=================================================================

📊 Results:
  ✅ Memory table has data
  ✅ Name in memory table
  ✅ Profile exists
  ✅ RAG loaded memories
  ✅ RAG can search
  ✅ Context has name

🎉 ALL TESTS PASSED - Name retrieval working correctly!
```

#### ❌ Problem Output (Issues Found)

**Example 1: No memories in database**
```
=================================================================
  TEST 1: Memory Table Query
=================================================================
📊 Total memories in database: 0
⚠️  No memories found in database for this user

...

=================================================================
  TEST SUMMARY
=================================================================
📊 Results:
  ❌ Memory table has data
  ❌ Name in memory table
  ❌ Profile exists
  ❌ RAG loaded memories
  ❌ RAG can search
  ❌ Context has name

⚠️  SOME TESTS FAILED - Check results above
```

**Example 2: Name not stored properly**
```
=================================================================
  TEST 3: Memory Service Name Retrieval
=================================================================
⚠️  No name found using standard keys: ['name', 'user_name', 'full_name', 'first_name']

...

📊 Results:
  ✅ Memory table has data
  ❌ Name in memory table  ← Problem here!
  ✅ Profile exists
  ✅ RAG loaded memories
  ❌ RAG can search
  ❌ Context has name
```

## Troubleshooting

### Issue 1: "No memories found in database"

**Cause:** Database is empty for this user

**Check:**
```sql
-- Verify memories exist
SELECT * FROM memory WHERE user_id = 'YOUR_USER_ID' LIMIT 10;
```

**Fix:** Have a conversation with the agent first, then run the test again.

### Issue 2: "No name found using standard keys"

**Cause:** Name was saved with a different key (like `user_input_1234567890`)

**Check database:**
```sql
-- Find all memories for user
SELECT key, value FROM memory 
WHERE user_id = 'YOUR_USER_ID' 
AND value ILIKE '%name%'
ORDER BY created_at DESC;
```

**Fix:** The agent should save name as key="name", not as user_input. Check `categorize_user_input` function.

### Issue 3: "Profile exists but name not in context"

**Cause:** ConversationContextService not fetching name properly

**Debug:** Look at the test output for TEST 6 to see what keys are in context.

**Fix:** Check `conversation_context_service.py` `_fetch_user_name()` method.

### Issue 4: "RAG loaded 0 memories"

**Cause:** Database query returned data but RAG couldn't load it

**Check test output for:**
- `[DEBUG][DB] Query returned X memories` - Should be > 0
- `[DEBUG][DB] Creating embeddings...` - Should process memories
- Error messages in RAG section

**Fix:** Check OpenAI API key is valid (needed for embeddings).

## Quick Verification Without Script

If you can't run the script, verify manually in Supabase:

### 1. Check Memory Table
```sql
SELECT * FROM memory 
WHERE user_id = 'YOUR_USER_ID' 
AND (key = 'name' OR value ILIKE '%name is%')
ORDER BY created_at DESC
LIMIT 5;
```

**Expected:** At least 1 row with name information

### 2. Check Profile Table
```sql
SELECT profile_text FROM user_profiles 
WHERE user_id = 'YOUR_USER_ID';
```

**Expected:** Profile text containing name

### 3. Check Total Memory Count
```sql
SELECT COUNT(*) as total_memories 
FROM memory 
WHERE user_id = 'YOUR_USER_ID';
```

**Expected:** > 0 memories

## What This Test Validates

| Test | What It Checks | Why It Matters |
|------|----------------|----------------|
| **TEST 1** | Raw database query | Verifies data exists in Supabase |
| **TEST 2** | Profile table | Checks if user profile has name |
| **TEST 3** | MemoryService | Tests direct memory retrieval by key |
| **TEST 4** | ProfileService | Tests profile service retrieval |
| **TEST 5** | RAG System | Validates embeddings and semantic search |
| **TEST 6** | ConversationContext | Tests automatic context injection |

## Success Criteria

For the test to pass, you should see:

✅ All 6 tests showing checkmarks  
✅ Name retrieved in at least 2 different ways  
✅ RAG system loaded with memories  
✅ Semantic search returning results  
✅ Context service finding the name

## Next Steps After Test

### If Test Passes ✅
Your memory retrieval is working! The issue is likely:
- **RAG not persisted between sessions** (see DEBUG_GUIDE.md)
- **User ID collision** in multi-user scenarios

### If Test Fails ❌
Fix the failing component first:
- **Memory table empty** → Check if agent is saving memories
- **Name not found** → Check key storage format
- **RAG can't search** → Check OpenAI API key
- **Context missing name** → Check ConversationContextService

## Example: Setting Up Test Data

If you need to create test data:

```python
# Quick script to add test memory
from supabase import create_client
import uuid

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

user_id = "YOUR_USER_ID"  # Your test user ID

# Add name memory
supabase.table("memory").insert({
    "user_id": user_id,
    "category": "FACT",
    "key": "name",
    "value": "Sarah"
}).execute()

# Add profile
supabase.table("user_profiles").upsert({
    "user_id": user_id,
    "profile_text": "Sarah is a 25-year-old software engineer who loves photography."
}).execute()

print("✅ Test data created!")
```

Then run: `python test_memory_retrieval.py YOUR_USER_ID`

