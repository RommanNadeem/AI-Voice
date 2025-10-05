# Onboarding Integration - Implementation Guide

## Overview
The agent now integrates with the `onboarding_details` table to personalize the first interaction after onboarding and store user occupation and interests in their profile.

## Features Implemented

### 1. ✅ Fetch Onboarding Details
- Fetches `first_name`, `occupation`, and `interests` from `onboarding_details` table
- Happens automatically during session initialization (before first response)
- Uses the session user UUID to query the table

### 2. ✅ Personalized First Greeting
- Uses user's first name in the initial greeting
- Shows that the agent remembers them from onboarding
- Creates a warm, personalized welcome experience
- Greeting is in Urdu as per agent instructions

### 3. ✅ Populate User Profile
- Automatically stores occupation and interests in `user_profiles` table
- Creates structured profile: `Name: [first_name] | Occupation: [occupation] | Interests: [interests]`
- Profile is immediately available for all subsequent interactions
- Supports interests as both list and string formats

## Database Schema Required

### onboarding_details Table
```sql
CREATE TABLE onboarding_details (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  first_name TEXT,
  occupation TEXT,
  interests TEXT, -- Can be JSON array or text
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookups
CREATE INDEX idx_onboarding_details_user_id ON onboarding_details(user_id);

-- RLS Policy
ALTER TABLE onboarding_details ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all operations on onboarding_details" 
ON onboarding_details FOR ALL USING (true);
```

## Implementation Details

### New Functions

#### `get_onboarding_details(user_id: str)`
Fetches onboarding details for a user.

**Parameters:**
- `user_id`: The user's UUID

**Returns:**
- Dictionary with `first_name`, `occupation`, `interests`
- `None` if no onboarding data found

**Example:**
```python
details = get_onboarding_details("c112f154-a0fc-53b7-9c57-a741e6ee091c")
# Returns: {'first_name': 'Alice', 'occupation': 'Software Engineer', 'interests': 'AI, Reading, Music'}
```

#### `populate_profile_from_onboarding(user_id: str)`
Fetches onboarding data and populates user profile.

**Parameters:**
- `user_id`: The user's UUID

**Returns:**
- `first_name` if onboarding data found
- `None` if no onboarding data

**Side Effects:**
- Saves profile to `user_profiles` table
- Profile format: `Name: [name] | Occupation: [job] | Interests: [interests]`

**Example:**
```python
first_name = populate_profile_from_onboarding("c112f154-...")
# Returns: "Alice"
# Saves: "Name: Alice | Occupation: Software Engineer | Interests: AI, Reading, Music"
```

### Modified Functions

#### `entrypoint(ctx: agents.JobContext)`
Updated to fetch onboarding data during initialization.

**Flow:**
```
1. Extract LiveKit participant identity
2. Convert to UUID and set session user
3. Ensure profile exists in profiles table
4. ✨ NEW: Fetch onboarding details and populate profile
5. Initialize TTS and Assistant
6. Start LiveKit session
7. ✨ NEW: Send personalized greeting with first name
```

#### `generate_with_memory()`
Updated to accept `user_first_name` parameter.

**Parameters:**
- `user_text`: User's message (optional)
- `greet`: Whether this is a greeting (default: False)
- `user_first_name`: User's first name for personalized greeting (optional)

**Greeting Behavior:**
- **With first name:** "Greet the user warmly in Urdu using their name '{first_name}'. Make them feel welcome and show that you remember them from onboarding."
- **Without first name:** "Greet the user warmly in Urdu."

## Usage Examples

### Example 1: User with Onboarding Data

**Onboarding Data:**
```json
{
  "user_id": "c112f154-a0fc-53b7-9c57-a741e6ee091c",
  "first_name": "Ahmed",
  "occupation": "Doctor",
  "interests": ["Health", "Exercise", "Reading"]
}
```

**Session Logs:**
```
[SESSION INIT] Identity: ahmed@example.com → UUID: c112f154-a0fc-53b7-9c57-a741e6ee091c
[SESSION INIT] ✓ Profile ready for user: c112f154-a0fc-53b7-9c57-a741e6ee091c
[SESSION INIT] Checking for onboarding data...
[ONBOARDING] Found details for user c112f154-a0fc-53b7-9c57-a741e6ee091c: Ahmed
[ONBOARDING] Populated profile from onboarding: Name: Ahmed | Occupation: Doctor | Interests: Health, Exercise, Reading
[SESSION INIT] ✓ Onboarding data loaded - user: Ahmed
```

**First Greeting:**
```
AI: "احمد، خوش آمدید! کیا حال ہے؟"
(Ahmed, welcome! How are you?)
```

**User Profile:**
```
Name: Ahmed | Occupation: Doctor | Interests: Health, Exercise, Reading
```

### Example 2: User without Onboarding Data

**Session Logs:**
```
[SESSION INIT] Identity: newuser@example.com → UUID: abc12345-...
[SESSION INIT] ✓ Profile ready for user: abc12345-...
[SESSION INIT] Checking for onboarding data...
[ONBOARDING] No onboarding details found for user abc12345-...
[SESSION INIT] No onboarding data found (user may not have completed onboarding)
```

**First Greeting:**
```
AI: "السلام علیکم! کیسے ہیں آپ؟"
(Greetings! How are you?)
```

**User Profile:**
```
(Empty or existing profile if any)
```

## Data Flow Diagram

```
LiveKit Session Start
        ↓
Extract Participant Identity (e.g., "alice@example.com")
        ↓
Convert to UUID (e.g., "c112f154-...")
        ↓
Set Session User in ContextVar
        ↓
Ensure Profile Exists in profiles table
        ↓
[NEW] Query onboarding_details table
        ↓
        ├─→ Onboarding Data Found
        │     ↓
        │   Extract: first_name, occupation, interests
        │     ↓
        │   Build Profile Text
        │     ↓
        │   Save to user_profiles table
        │     ↓
        │   Return first_name
        │
        └─→ No Onboarding Data
              ↓
            Return None
        ↓
Start LiveKit Session
        ↓
Generate Greeting
        ↓
        ├─→ With first_name: "مرحبا [name]! ..."
        └─→ Without: "السلام علیکم! ..."
```

## Testing

### Test with Onboarding Data

```python
# 1. Insert test onboarding data
from agent import memory_manager

test_user_uuid = "c112f154-a0fc-53b7-9c57-a741e6ee091c"

memory_manager.supabase.table('onboarding_details').insert({
    'user_id': test_user_uuid,
    'first_name': 'Ali',
    'occupation': 'Engineer',
    'interests': 'Technology, Sports, Music'
}).execute()

# 2. Start LiveKit session with this user
# The agent will:
# - Fetch onboarding data
# - Populate profile: "Name: Ali | Occupation: Engineer | Interests: Technology, Sports, Music"
# - Greet with name: "علی، خوش آمدید!"

# 3. Verify profile was populated
response = memory_manager.supabase.table('user_profiles').select('profile_text').eq('user_id', test_user_uuid).execute()
print(response.data[0]['profile_text'])
# Output: "Name: Ali | Occupation: Engineer | Interests: Technology, Sports, Music"
```

### Test without Onboarding Data

```python
# 1. Start LiveKit session with new user (no onboarding data)
# The agent will:
# - Not find onboarding data
# - Use generic greeting
# - Profile will be built from conversation

# 2. Check logs
# [ONBOARDING] No onboarding details found for user ...
# [SESSION INIT] No onboarding data found (user may not have completed onboarding)
```

## Error Handling

### Onboarding Table Not Found
```
[ONBOARDING ERROR] Failed to fetch onboarding details: relation "onboarding_details" does not exist
```
**Solution:** Create the `onboarding_details` table using the schema above.

### Invalid User UUID
```
[ONBOARDING ERROR] Failed to fetch onboarding details: invalid input syntax for type uuid
```
**Solution:** Ensure the user UUID is valid. The agent automatically converts LiveKit identities to UUIDs.

### No Onboarding Data
```
[ONBOARDING] No onboarding details found for user c112f154-...
```
**Expected Behavior:** Agent continues normally with generic greeting. This is not an error.

## Benefits

### User Experience
- ✅ Personalized welcome using their name
- ✅ Shows continuity from onboarding to conversation
- ✅ Profile pre-populated with their interests and occupation
- ✅ More natural, familiar interaction

### Technical
- ✅ Automatic profile population from onboarding
- ✅ No manual data entry needed
- ✅ Seamless integration with existing profile system
- ✅ Graceful handling when onboarding data missing

### Conversation Quality
- ✅ Agent has context about user from start
- ✅ Can reference occupation and interests naturally
- ✅ Better topic suggestions based on interests
- ✅ More relevant and engaging conversations

## Configuration

### Environment Variables
No new environment variables needed. Uses existing:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` (preferred) or `SUPABASE_ANON_KEY`

### Database Permissions
Ensure the Supabase key has read access to `onboarding_details` table.

## Future Enhancements

### Potential Improvements
1. **Store onboarding completion status** in profiles table
2. **Track when profile was populated** from onboarding
3. **Update profile if onboarding data changes**
4. **Fetch additional onboarding fields** (age, location, etc.)
5. **Support multiple languages** for onboarding data
6. **Structured interests** using tags/categories

### Example Enhancement
```python
def populate_profile_from_onboarding(user_id: str, update_existing: bool = False):
    """
    Enhanced version with update_existing flag.
    Can re-fetch and update profile if onboarding data changes.
    """
    # Implementation
```

## Summary

**Status:** ✅ **IMPLEMENTED AND READY**

**Key Features:**
- ✅ Fetches onboarding data at session init
- ✅ Uses first name in personalized greeting
- ✅ Populates profile with occupation and interests
- ✅ Gracefully handles missing onboarding data
- ✅ Comprehensive logging and error handling

**Requirements:**
- `onboarding_details` table with schema above
- Supabase service role key or anon key with read permissions

**Next Steps:**
1. Create `onboarding_details` table in Supabase
2. Populate table with user onboarding data
3. Test with real users
4. Monitor logs for any issues
