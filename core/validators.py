"""
Validation utilities for Companion Agent
"""

import uuid
from typing import Optional
from core.user_id import UserId, UserIdError


# Current user session state
_current_user_id: Optional[str] = None
_supabase_client = None


def set_current_user_id(user_id: str):
    """
    Set the current user ID from LiveKit session.
    Validates that user_id is a full UUID.
    
    Args:
        user_id: Full UUID (not a prefix)
        
    Raises:
        UserIdError: If user_id is not a valid full UUID
    """
    global _current_user_id
    
    # STRICT VALIDATION: Ensure we only accept full UUIDs
    try:
        UserId.assert_full_uuid(user_id)
    except UserIdError as e:
        print(f"[CRITICAL][USER_ID] ❌ REJECTED invalid user_id: {e}")
        raise
    
    # DEBUG: Track user_id changes and potential collisions
    old_user_id = _current_user_id
    if old_user_id and old_user_id != user_id:
        print(f"[DEBUG][USER_ID] ⚠️  USER_ID COLLISION DETECTED!")
        print(f"[DEBUG][USER_ID]    Previous: {UserId.format_for_display(old_user_id)}")
        print(f"[DEBUG][USER_ID]    New:      {UserId.format_for_display(user_id)}")
        print(f"[DEBUG][USER_ID]    This indicates multiple sessions are active!")
    
    _current_user_id = user_id
    print(f"[SESSION] User ID set to: {user_id}")
    print(f"[DEBUG][USER_ID] ✅ Global _current_user_id = {UserId.format_for_display(user_id)}")


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
    Return a full UUID string from 'user-<uuid>' or '<uuid>'.
    Return None if invalid (do not fabricate a fallback UUID here).
    
    This is the ONLY function that should parse identity strings.
    All downstream code must use the returned full UUID.
    
    Args:
        identity: Identity string (e.g., "user-<uuid>" or "<uuid>")
        
    Returns:
        Full UUID string or None if invalid
    """
    if not identity:
        print("[UUID WARNING] Empty identity")
        return None
    
    try:
        full_uuid = UserId.parse_from_identity(identity)
        print(f"[UUID] ✅ Parsed identity '{identity}' -> full UUID {UserId.format_for_display(full_uuid)}")
        return full_uuid
    except UserIdError as e:
        print(f"[UUID ERROR] ❌ Failed to parse identity '{identity}': {e}")
        return None


def can_write_for_current_user() -> bool:
    """
    Centralized guard to ensure DB writes are safe.
    Validates that current user_id is a full UUID.
    """
    uid = get_current_user_id()
    if not uid:
        print("[GUARD] No current user_id; skipping DB writes")
        return False
    
    # STRICT VALIDATION: Ensure full UUID format
    try:
        UserId.assert_full_uuid(uid)
    except UserIdError as e:
        print(f"[GUARD] ❌ Invalid user_id: {e}")
        print(f"[GUARD] Skipping DB writes to prevent FK errors")
        return False
    
    if not _supabase_client:
        print("[GUARD] Supabase not connected; skipping DB writes")
        return False
    return True

