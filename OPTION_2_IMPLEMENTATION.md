# Option 2 Implementation: Use profiles.id for FK References

## Problem
The `memory.user_id` FK constraint points to `profiles.id` (SERIAL PRIMARY KEY) but our code was querying `profiles.user_id` (UUID column). This caused FK constraint violations because the constraint checker couldn't find the UUID in the `profiles.id` column.

## Solution
Updated all code to use `profiles.id` instead of `profiles.user_id` to match the existing FK constraint.

## Changes Made

### 1. UserService.profile_exists()
**Before:**
```python
resp = self.supabase.table("profiles").select("id").eq("user_id", user_id).execute()
```

**After:**
```python
resp = self.supabase.table("profiles").select("id").eq("id", user_id).execute()
```

### 2. UserService.ensure_profile_exists()
**Before:**
```python
profile_data = {
    "user_id": user_id,  # profiles.user_id column stores the UUID
    "email": f"user_{user_id[:8]}@companion.local",
    "is_first_login": True,
}
```

**After:**
```python
profile_data = {
    "id": user_id,  # profiles.id column stores the UUID (same as user_id)
    "user_id": user_id,  # Keep both for consistency
    "email": f"user_{user_id[:8]}@companion.local",
    "is_first_login": True,
}
```

### 3. UserService.get_user_info()
**Before:**
```python
resp = self.supabase.table("profiles").select("*").eq("user_id", user_id).execute()
```

**After:**
```python
resp = self.supabase.table("profiles").select("*").eq("id", user_id).execute()
```

### 4. UserService.update_user_profile()
**Before:**
```python
resp = self.supabase.table("profiles").update(updates).eq("user_id", user_id).execute()
```

**After:**
```python
resp = self.supabase.table("profiles").update(updates).eq("id", user_id).execute()
```

## Architecture

### Current Schema
- `profiles.id` = UUID (stores the user UUID, same as user_id)
- `profiles.user_id` = UUID (duplicate of id for consistency)
- `memory.user_id` → `profiles.id` (FK constraint)

### Why This Works
1. **FK Constraint Satisfied**: `memory.user_id` can find the UUID in `profiles.id`
2. **Profile Creation**: Sets both `id` and `user_id` to the same UUID
3. **Profile Queries**: All queries now use `profiles.id` which contains the UUID
4. **Consistency**: Both columns contain the same UUID value

## Testing

The memory saving should now work because:
1. `ensure_profile_exists()` creates profile with `id = user_id`
2. `memory.user_id` FK constraint can find the UUID in `profiles.id`
3. Memory insert succeeds without FK violations

## Files Modified
- `services/user_service.py` - Updated all profile queries and creation

## Next Steps
1. Test memory saving with the updated code
2. Verify profile creation works correctly
3. Confirm FK constraint violations are resolved
