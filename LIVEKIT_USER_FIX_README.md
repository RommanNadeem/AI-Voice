# LiveKit User ID Dynamic Management - Solution

## Problem
The current database schema has a foreign key constraint: `profiles.id` → `auth.users.id`

This means we **cannot create new profiles** for LiveKit users without first creating them in Supabase Auth's `auth.users` table, which requires authentication flows.

**Current Behavior:**
- All LiveKit users fall back to using the same hardcoded user ID: `de8f4740-0d33-475c-8fa5-c7538bdddcfa`
- No user isolation - all LiveKit sessions share the same memory and profile

## Root Cause
```sql
-- Current Schema (PROBLEMATIC)
CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id),  -- ❌ Foreign key constraint
  email TEXT,
  is_first_login BOOLEAN
);
```

## Solution Options

### Option 1: Remove Foreign Key Constraint (RECOMMENDED)
Modify the `profiles` table to remove the foreign key constraint:

```sql
-- Step 1: Drop the existing foreign key constraint
ALTER TABLE profiles 
DROP CONSTRAINT IF EXISTS profiles_id_fkey;

-- Step 2: The agent code will now be able to create profiles for LiveKit users
-- No additional schema changes needed!
```

**Advantages:**
- Simple and quick
- Minimal changes to existing code
- Works immediately with current implementation

**Implementation:**
Run this SQL in your Supabase SQL Editor, then restart the agent.

---

### Option 2: Create Separate LiveKit Users Table
Create a dedicated table for LiveKit users that doesn't reference auth.users:

```sql
-- Create new table for LiveKit users
CREATE TABLE livekit_users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  livekit_identity TEXT UNIQUE NOT NULL,  -- Original LiveKit identity
  email TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Update memory table to reference livekit_users instead
ALTER TABLE memory 
DROP CONSTRAINT memory_user_id_fkey,
ADD CONSTRAINT memory_user_id_fkey 
  FOREIGN KEY (user_id) 
  REFERENCES livekit_users(id) 
  ON DELETE CASCADE;

-- Update user_profiles table similarly
ALTER TABLE user_profiles
DROP CONSTRAINT user_profiles_user_id_fkey,
ADD CONSTRAINT user_profiles_user_id_fkey 
  FOREIGN KEY (user_id) 
  REFERENCES livekit_users(id) 
  ON DELETE CASCADE;

-- Enable RLS
ALTER TABLE livekit_users ENABLE ROW LEVEL SECURITY;

-- Create policy
CREATE POLICY "Allow all operations on livekit_users" 
ON livekit_users FOR ALL USING (true);
```

**Advantages:**
- Clean separation between auth users and LiveKit users
- Maintains referential integrity
- Can track LiveKit-specific metadata

**Disadvantages:**
- More complex schema changes
- Requires updating multiple tables

---

### Option 3: Hybrid Approach
Keep both auth users and LiveKit users, with a union view:

```sql
-- Modify profiles to be optional reference
ALTER TABLE profiles 
ALTER COLUMN id DROP NOT NULL;

-- Create LiveKit users table (as in Option 2)
CREATE TABLE livekit_users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  livekit_identity TEXT UNIQUE NOT NULL,
  email TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create a view that unions both
CREATE VIEW all_users AS
SELECT id, email, 'auth' as user_type FROM profiles
UNION ALL
SELECT id, email, 'livekit' as user_type FROM livekit_users;
```

---

## Quick Fix for Development (Current Implementation)

The agent code NOW includes:
1. ✅ UUID conversion: Converts LiveKit identities to deterministic UUIDs
2. ✅ Profile creation: Attempts to create profiles for new LiveKit users
3. ✅ Fallback handling: Falls back to existing user if profile creation fails

**What's Missing:**
- Database schema still blocks profile creation due to foreign key constraint

**To Enable Dynamic User IDs:**
Run this ONE command in Supabase SQL Editor:

```sql
ALTER TABLE profiles DROP CONSTRAINT IF EXISTS profiles_id_fkey;
```

Then restart your agent - LiveKit users will now get separate profiles and memories!

---

## Code Changes Made

### 1. UUID Conversion Function
```python
def livekit_identity_to_uuid(identity: str) -> str:
    """Convert LiveKit identity to deterministic UUID"""
    namespace = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')
    return str(uuid.uuid5(namespace, identity))
```

### 2. Dynamic User ID Management
```python
def get_current_user():
    session_user_id = get_session_user_id()
    if session_user_id:
        user_uuid = livekit_identity_to_uuid(session_user_id)
        ensure_profile_exists(user_uuid, original_identity=session_user_id)
        return user_uuid
```

### 3. Automatic Profile Creation
```python
def ensure_profile_exists(user_id: str, original_identity: str = None):
    # Check if profile exists
    # If not, create it automatically
    # Returns True if profile exists or was created successfully
```

---

## Testing

After applying the schema fix, test with:

```python
from agent import set_session_user_id, get_user_id, memory_manager

# Test User 1
set_session_user_id("alice@example.com")
user1_id = get_user_id()
memory_manager.store("FACT", "test1", "Alice's memory")

# Test User 2
set_session_user_id("bob@example.com")
user2_id = get_user_id()
memory_manager.store("FACT", "test2", "Bob's memory")

# Verify isolation
set_session_user_id("alice@example.com")
assert memory_manager.retrieve("FACT", "test1") == "Alice's memory"
assert memory_manager.retrieve("FACT", "test2") is None  # Should not see Bob's memory

print("✅ User isolation working!")
```

---

## Recommendation

**For immediate fix:** Use **Option 1** - Remove the foreign key constraint

**For production:** Consider **Option 2** - Create separate LiveKit users table for better separation

---

## Summary

**Current Status:** ❌ All LiveKit users share one profile  
**After Schema Fix:** ✅ Each LiveKit user gets separate profile and memories  
**Required Action:** Run SQL command to remove foreign key constraint  
**Code Status:** ✅ Already implemented and ready to work once schema is fixed
