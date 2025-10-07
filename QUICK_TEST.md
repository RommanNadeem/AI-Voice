# Quick Test for Name Retrieval

## 🚀 Fast Setup (30 seconds)

### Step 1: Get Your User ID

**Option A - From Logs:**
```bash
# Find user_id in your recent logs
grep "User ID set to:" logs.txt | tail -1
```

**Option B - From Supabase Dashboard:**
1. Go to Supabase SQL Editor
2. Run: `SELECT DISTINCT user_id FROM memory LIMIT 5;`
3. Copy any user_id

### Step 2: Run Test
```bash
python test_memory_retrieval.py YOUR_USER_ID_HERE
```

**Example:**
```bash
python test_memory_retrieval.py abc12345-1234-1234-1234-123456789abc
```

## ✅ Expected Output (Working)

```
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

## ❌ Problem Output (Not Working)

```
📊 Results:
  ❌ Memory table has data        ← Database empty
  ❌ Name in memory table         ← Name not saved
  ❌ RAG loaded memories          ← RAG couldn't load
  ❌ Context has name             ← Context service failed
```

## 🔍 What Gets Tested

| # | Test | Checks |
|---|------|--------|
| 1 | Memory Table | Raw database has data |
| 2 | Profile Table | User profile exists |
| 3 | Memory Service | Can retrieve by key |
| 4 | Profile Service | Profile service works |
| 5 | RAG System | Embeddings & search work |
| 6 | Context Service | Auto context injection |

## 📊 Interpreting Results

### Scenario 1: All Tests Pass ✅
**Meaning:** Data storage and retrieval working perfectly!  
**Issue:** Problem is RAG not persisting between sessions  
**Next:** See `DEBUG_GUIDE.md` for RAG persistence fix

### Scenario 2: "Memory table has data" fails ❌
**Meaning:** Database is empty for this user  
**Issue:** Memories not being saved  
**Next:** Have a conversation first, then retest

### Scenario 3: "Name in memory table" fails ❌
**Meaning:** Name exists but not with correct key  
**Issue:** Name saved as `user_input_123` instead of `name`  
**Next:** Check how name is being categorized

### Scenario 4: "RAG loaded memories" fails ❌
**Meaning:** Database has data but RAG can't load it  
**Issue:** Embedding creation failing (OpenAI API issue)  
**Next:** Check OpenAI API key

### Scenario 5: "Context has name" fails ❌
**Meaning:** ConversationContextService not finding name  
**Issue:** `_fetch_user_name()` method not searching correctly  
**Next:** Check `conversation_context_service.py`

## 🐛 Quick Fixes

### If no data in database:
```bash
# Have a conversation first
# Tell agent: "My name is Sarah"
# Wait 5 seconds for background save
# Then run test again
```

### If name not found:
```sql
-- Check what keys are used
SELECT key, value FROM memory 
WHERE user_id = 'YOUR_USER_ID' 
AND value ILIKE '%name%';

-- Manually add name if needed
INSERT INTO memory (user_id, category, key, value)
VALUES ('YOUR_USER_ID', 'FACT', 'name', 'Sarah');
```

### If RAG fails:
```bash
# Check OpenAI API key
echo $OPENAI_API_KEY

# Or check .env file
grep OPENAI_API_KEY .env
```

## 📝 Full Documentation

- **Complete Guide:** `MEMORY_TEST_INSTRUCTIONS.md`
- **Debug Guide:** `DEBUG_GUIDE.md`
- **Implementation Details:** `DEBUG_IMPLEMENTATION_SUMMARY.md`

## 🎯 Success = All Green Checkmarks

When you see:
```
🎉 ALL TESTS PASSED - Name retrieval working correctly!
```

Your memory system is healthy! Any issues you're experiencing are likely:
1. RAG not persisting between sessions → Need to implement disk persistence
2. User ID collisions in multi-user setup → Need session-specific context

Both solutions provided in `DEBUG_GUIDE.md`

