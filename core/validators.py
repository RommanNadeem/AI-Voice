"""
Validation utilities for Companion Agent
"""

import uuid
from typing import Optional


# Current user session state
_current_user_id: Optional[str] = None
_supabase_client = None


def set_current_user_id(user_id: str):
    """Set the current user ID from LiveKit session"""
    global _current_user_id
    
    # DEBUG: Track user_id changes and potential collisions
    old_user_id = _current_user_id
    if old_user_id and old_user_id != user_id:
        print(f"[DEBUG][USER_ID] ⚠️  USER_ID COLLISION DETECTED!")
        print(f"[DEBUG][USER_ID]    Previous: {old_user_id[:8]}")
        print(f"[DEBUG][USER_ID]    New:      {user_id[:8]}")
        print(f"[DEBUG][USER_ID]    This indicates multiple sessions are active!")
    
    _current_user_id = user_id
    print(f"[SESSION] User ID set to: {user_id}")
    print(f"[DEBUG][USER_ID] ✅ Global _current_user_id = {user_id[:8]}")


def get_current_user_id() -> Optional[str]:
    """Get the current user ID"""
    result = _current_user_id
    # DEBUG: Only log when result is None (reduce noise)
    if result is None:
        print(f"[DEBUG][USER_ID] ⚠️  Retrieved user_id: NONE")
    return result


def set_supabase_client(client):
    """Set the global Supabase client reference"""
    global _supabase_client
    _supabase_client = client


def get_supabase_client():
    """Get the global Supabase client"""
    return _supabase_client


def is_valid_uuid(uuid_string: str) -> bool:
    """Check if string is a valid UUID format"""
    try:
        uuid.UUID(uuid_string)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def extract_uuid_from_identity(identity: Optional[str]) -> Optional[str]:
    """
    Return a UUID string from 'user-<uuid>' or '<uuid>'.
    Return None if invalid (do not fabricate a fallback UUID here).
    """
    if not identity:
        print("[UUID WARNING] Empty identity")
        return None

    if identity.startswith("user-"):
        uuid_part = identity[5:]
        if is_valid_uuid(uuid_part):
            return uuid_part
        print(f"[UUID WARNING] Invalid UUID in 'user-' identity: {uuid_part}")
        return None

    if is_valid_uuid(identity):
        return identity

    print(f"[UUID WARNING] Invalid identity format: {identity}")
    return None


def can_write_for_current_user() -> bool:
    """Centralized guard to ensure DB writes are safe."""
    uid = get_current_user_id()
    if not uid:
        print("[GUARD] No current user_id; skipping DB writes")
        return False
    if not is_valid_uuid(uid):
        print(f"[GUARD] Invalid user_id format: {uid}; skipping DB writes")
        return False
    if not _supabase_client:
        print("[GUARD] Supabase not connected; skipping DB writes")
        return False
    return True

