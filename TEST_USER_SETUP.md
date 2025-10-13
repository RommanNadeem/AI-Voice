# Test User ID Configuration

## Overview

For development and testing purposes, you can configure a mock user ID that will be used when user ID extraction fails or when explicitly enabled.

## Default Test User

**User ID:** `4e3efa3d-d8fe-431e-a78f-4efffb0cf43a`

This user has:
- Name: Romman (Muhammad Ruman Nadeem)
- Gender: Male
- Location: Karachi/Gilgit
- 46+ memories across multiple categories
- Full profile and conversation history

---

## Configuration

### Option 1: Enable Test Mode (Always Use Test User)

Set environment variable:
```bash
USE_TEST_USER=true
```

**When to use:**
- Local development
- Testing AI personality
- Testing memory system
- No real users available

**Behavior:**
```
[DEBUG][USER_ID] 🧪 Using TEST_USER_ID: 4e3efa3d...
→ Always uses test user, regardless of participant identity
```

---

### Option 2: Fallback Mode (Use Test User Only When Extraction Fails)

Default behavior - no environment variable needed.

**When to use:**
- Production with fallback safety
- Testing with malformed identities
- Graceful degradation

**Behavior:**
```
If user_id extraction succeeds:
  → Use real user_id
  
If user_id extraction fails:
  → Falls back to test user (if USE_TEST_USER=true)
  → Or continues with no user data (if USE_TEST_USER=false)
```

---

### Option 3: Custom Test User

Override the default test user:
```bash
TEST_USER_ID=your-uuid-here
USE_TEST_USER=true
```

---

## Usage Examples

### Example 1: Local Development
```bash
# .env file
USE_TEST_USER=true
TEST_USER_ID=4e3efa3d-d8fe-431e-a78f-4efffb0cf43a
```

**Result:** All connections use the test user, you can test with full data

### Example 2: Production (Default)
```bash
# .env file
USE_TEST_USER=false  # or not set
```

**Result:** Only real user IDs work, no test fallback

### Example 3: Staging with Safety Net
```bash
# .env file
USE_TEST_USER=true
```

**Result:** Real users work normally, but if extraction fails, uses test user instead of crashing

---

## Logs to Expect

### With Real User (Successful):
```
[DEBUG][IDENTITY] Extracting user_id from identity: 'user-abc123...'
[DEBUG][USER_ID] ✅ Successfully extracted user_id: abc123...
[CONTEXT] ✅ Loaded profile + 21 memories
```

### With Test User (Fallback):
```
[DEBUG][IDENTITY] Extracting user_id from identity: 'invalid-format'
[DEBUG][USER_ID] ❌ Failed to extract user_id from 'invalid-format'
[DEBUG][USER_ID] 🧪 Using TEST_USER_ID: 4e3efa3d...
[DEBUG][USER_ID] → Set USE_TEST_USER=false to disable test mode
[CONTEXT] ✅ Loaded profile + 21 memories
```

### Without Test User (No Data):
```
[DEBUG][IDENTITY] Extracting user_id from identity: 'invalid-format'
[DEBUG][USER_ID] ❌ Failed to extract user_id from 'invalid-format'
[DEBUG][USER_ID] → No user data will be available
[DEBUG][USER_ID] → To enable test mode: set USE_TEST_USER=true
[CONTEXT] No valid user_id, creating assistant with empty context
```

---

## Testing Checklist

- [ ] Set `USE_TEST_USER=true` in `.env`
- [ ] Restart agent
- [ ] Connect with any identity (even invalid)
- [ ] Verify logs show: `🧪 Using TEST_USER_ID: 4e3efa3d...`
- [ ] Confirm AI greets as "Romman"
- [ ] Confirm AI has Humraaz personality
- [ ] Confirm AI references your memories

---

## Security Note

⚠️ **Never enable `USE_TEST_USER=true` in production!**

This bypasses user authentication and will give all users access to the test user's data.

**Safe for:**
- ✅ Local development
- ✅ Staging/testing environments
- ✅ Demo purposes

**Unsafe for:**
- ❌ Production deployments
- ❌ Multi-user environments
- ❌ Any public-facing instance

---

## Quick Start

1. Add to `.env`:
   ```
   USE_TEST_USER=true
   ```

2. Restart agent

3. Connect - you'll be greeted as Romman with full personality!

That's it! 🎉

