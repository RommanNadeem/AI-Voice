# Profile & Memory Not Updating - Diagnosis & Fixes

## Problem
Users report that profiles and memories are not updating in the current build (commit `c969d78`).

## Root Causes Found

### 1. **`initialize_user_from_onboarding` never called** ❌
The onboarding initialization function exists but is **never invoked** in `agent.py`.

**Evidence:** 
- `services/onboarding_service.py` line 17: Function exists
- `agent.py` line 1270: Only calls `ensure_profile_exists` (creates `profiles` table row)
- `agent.py`: **No call to `initialize_user_from_onboarding` anywhere**

**Impact:**
- New users don't get `user_profiles` table rows created
- No initial memories created from onboarding data
- Gender/pronouns not stored
- RAG system not initialized with user data

### 2. **Bug in `onboarding_service.py`** 🐛
Line 69 calls non-existent function `detect_gender_from_name()`:

```python
gender_info = await profile_service.detect_gender_from_name(full_name, user_id)
```

This function **does not exist** in `profile_service.py`, causing initialization to fail.

### 3. **Missing `gender` field in query** 
Line 44 fetches onboarding data but doesn't include `gender`:

```python
result = self.supabase.table("onboarding_details").select("full_name, occupation, interests")...
```

Should be: `"full_name, gender, occupation, interests"`

### 4. **Silent failures** 
Print statements don't appear in console due to LiveKit CLI buffering, making debugging difficult.

---

## How Profile/Memory Updates SHOULD Work

### On User Signup/First Login:
1. `ensure_profile_exists()` creates row in `profiles` table ✅
2. **`initialize_user_from_onboarding()`** should create:
   - Row in `user_profiles` table with generated profile_text ❌ NOT CALLED
   - Memories in `memory` table for name, occupation, interests, etc. ❌ NOT CALLED
   - Gender/pronouns stored ❌ NOT CALLED
   - RAG system populated ❌ NOT CALLED

### During Conversations:
1. User speaks → `on_user_turn_completed()` called (line 1010)
2. Triggers `_process_background()` (line 1030) which:
   - Auto-saves durable memories to database (line 1102-1111) ✅
   - Indexes in RAG for semantic search (line 1113-1121) ✅
   - Generates and saves updated profile (line 1123-1136) ✅
   - Updates conversation state (line 1138-1162) ✅

**The conversation update flow EXISTS and should work**, BUT:
- If initial `user_profiles` row doesn't exist, profile updates will fail
- If initial memories don't exist, users start with empty knowledge

---

## Why This Breaks User Experience

### Scenario: New User Signs Up

1. ✅ User completes onboarding form (name, gender, occupation, interests)
2. ✅ `profiles` table gets a row (basic user record)
3. ❌ `user_profiles` table stays EMPTY (no profile_text created)
4. ❌ `memory` table stays EMPTY (no initial memories)
5. ❌ Agent has NO knowledge of user's name, occupation, interests
6. ❌ Gender/pronouns not stored, agent uses wrong pronouns

### During First Conversation:

1. User: "Tell me about my interests"
2. Agent: "I don't know anything about you yet" (no memories)
3. User shares info: "I like cricket and coding"
4. ✅ `_process_background` tries to save memory
5. ❌ But if `user_profiles` row missing, profile updates fail
6. ⚠️ Some memories may save, but profile generation fails

### Result:
- Agent appears to "forget" onboarding information
- User has to re-share everything they already provided
- Poor user experience

---

## The Code Flow (Current State)

### agent.py entrypoint (line 1265-1271):
```python
# Ensure user profile exists
user_service = UserService(supabase)
await asyncio.to_thread(user_service.ensure_profile_exists, user_id)
print("[PROFILE] ✓ User profile ensured")
```

**What it does:** Creates row in `profiles` table
**What it DOESN'T do:** Create `user_profiles` row or memories

### services/onboarding_service.py (line 17-130):
```python
async def initialize_user_from_onboarding(self, user_id: str):
    """Initialize new user profile and memories from onboarding_details table."""
    # Lines 32-41: Check if already initialized
    # Lines 44-55: Fetch onboarding data
    # Line 69: ❌ BUG: Calls non-existent detect_gender_from_name()
    # Lines 75-81: Create profile_text
    # Lines 84-125: Create memories and populate RAG
```

**Status:** Function exists BUT:
- ❌ Never called from `agent.py`
- 🐛 Has bug on line 69
- ⚠️ Missing `gender` in query (line 44)

---

## Fixes Needed

### Fix 1: Call `initialize_user_from_onboarding` in agent.py

**Location:** `agent.py` around line 1270

**Change from:**
```python
# Ensure user profile exists
user_service = UserService(supabase)
await asyncio.to_thread(user_service.ensure_profile_exists, user_id)
print("[PROFILE] ✓ User profile ensured")
```

**Change to:**
```python
# Ensure user profile exists (parent table)
user_service = UserService(supabase)
await asyncio.to_thread(user_service.ensure_profile_exists, user_id)
print("[PROFILE] ✓ User profile ensured")

# Initialize user from onboarding data (creates profile + memories)
try:
    logging.info(f"[ONBOARDING] Initializing user {user_id[:8]}...")
    onboarding_service_tmp = OnboardingService(supabase)
    await onboarding_service_tmp.initialize_user_from_onboarding(user_id)
    logging.info("[ONBOARDING] ✓ User initialization complete")
except Exception as e:
    logging.error(f"[ONBOARDING] Failed to initialize: {e}", exc_info=True)
```

### Fix 2: Remove non-existent function call

**Location:** `services/onboarding_service.py` line 65-72

**Change from:**
```python
# Detect gender from name for appropriate pronoun usage
gender_info = None
if full_name:
    try:
        gender_info = await profile_service.detect_gender_from_name(full_name, user_id)
        print(f"[ONBOARDING SERVICE] Gender detected: {gender_info['gender']} ({gender_info['pronouns']})")
    except Exception as e:
        print(f"[ONBOARDING SERVICE] Gender detection failed: {e}")
```

**Change to:**
```python
# Determine pronouns from gender (from onboarding_details)
gender_info = None
if gender:
    pronouns_map = {
        "male": "he/him",
        "female": "she/her",
        "non-binary": "they/them",
        "other": "they/them"
    }
    pronouns = pronouns_map.get(gender.lower(), "they/them")
    gender_info = {"gender": gender, "pronouns": pronouns}
    logging.info(f"[ONBOARDING] Gender: {gender} ({pronouns})")
```

### Fix 3: Add gender to query

**Location:** `services/onboarding_service.py` line 44

**Change from:**
```python
result = self.supabase.table("onboarding_details").select("full_name, occupation, interests").eq("user_id", user_id).execute()
```

**Change to:**
```python
result = self.supabase.table("onboarding_details").select("full_name, gender, occupation, interests").eq("user_id", user_id).execute()
```

### Fix 4: Replace print with logging

**Location:** Throughout `services/onboarding_service.py`

Add at top of file:
```python
import logging
logger = logging.getLogger(__name__)
```

Replace all `print()` statements with:
- `logger.info()` for informational messages
- `logger.warning()` for warnings
- `logger.error()` for errors (with `exc_info=True`)

This ensures output is visible in console even with LiveKit CLI.

---

## Testing After Fixes

### Test 1: New User Signup
1. Create a new user account
2. Complete onboarding (name, gender, occupation, interests)
3. Check logs for:
   ```
   [INFO] services.onboarding_service: 🔄 Checking if user needs initialization...
   [INFO] services.onboarding_service: ⚠️ Missing user_profiles row - will create
   [INFO] services.onboarding_service: ✓ Created initial profile
   [INFO] services.onboarding_service: ✓ Created 5 memories
   [INFO] services.onboarding_service: ✓ User initialization complete
   ```

4. Verify in database:
   - ✅ `profiles` table has row
   - ✅ `user_profiles` table has row with profile_text
   - ✅ `memory` table has rows for name, gender, occupation, interests

### Test 2: Conversation Updates
1. Have a conversation with user
2. User shares new information: "I like cricket"
3. Check logs for:
   ```
   [INFO] [MEMORY] ✅ Auto-saved: [INTEREST] sports_cricket
   [INFO] [RAG] ✅ Indexed for search
   [INFO] [PROFILE] ✅ Updated
   ```

4. Verify memories and profile updated in database

### Test 3: Existing User (Already Initialized)
1. Log in with user who already has profile + memories
2. Check logs for:
   ```
   [INFO] services.onboarding_service: ✓ User already fully initialized, skipping
   ```

3. Verify no duplicate memories created

---

## Summary

### Current State (c969d78):
- ❌ `initialize_user_from_onboarding` never called
- 🐛 Bug: Non-existent function call
- ⚠️ Missing gender field in query
- 🔇 Print statements not visible

### After Fixes:
- ✅ Full onboarding initialization on first login
- ✅ `user_profiles` table populated
- ✅ Initial memories created
- ✅ Gender/pronouns stored
- ✅ RAG system populated
- ✅ Logs visible via logging framework
- ✅ Conversation updates work properly

### Impact:
- Users get proper personalized experience from day 1
- Agent remembers onboarding information
- Profile and memories update during conversations
- Better debugging with visible logs

