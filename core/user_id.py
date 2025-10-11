"""
UserId Utility - Centralized user ID validation and parsing
"""

import re
import uuid
from typing import Optional


# UUID v4 regex pattern (strict)
UUID_V4_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
    re.IGNORECASE
)


class UserIdError(Exception):
    """Raised when user_id validation fails"""
    pass


class UserId:
    """
    Utility class for user ID operations.
    Enforces that all user IDs are full UUIDs (no prefixes allowed).
    """
    
    @staticmethod
    def parse_from_identity(identity: str) -> str:
        """
        Extract and return the full UUID from identity string.
        
        Args:
            identity: Identity string (e.g., "user-<uuid>" or "<uuid>")
            
        Returns:
            Full UUID string (36 characters)
            
        Raises:
            UserIdError: If identity is invalid or not a valid UUID
        """
        if not identity:
            raise UserIdError("Identity string is empty or None")
        
        identity = identity.strip()
        
        # Handle "user-<uuid>" format
        if identity.startswith("user-"):
            uuid_part = identity[5:]
        else:
            uuid_part = identity
        
        # Validate it's a proper UUID
        if not UserId.is_valid_uuid(uuid_part):
            raise UserIdError(
                f"Invalid UUID format: '{uuid_part}'. "
                f"Expected full UUID (e.g., 'bb4a6f7c-1e1d-4db8-9fcd-f7095759aba2'), "
                f"not a prefix."
            )
        
        return uuid_part
    
    @staticmethod
    def assert_full_uuid(user_id: str) -> None:
        """
        Assert that the given user_id is a valid full UUID.
        
        Args:
            user_id: User ID to validate
            
        Raises:
            UserIdError: If user_id is not a valid full UUID
        """
        if not user_id:
            raise UserIdError("user_id is empty or None")
        
        if not UserId.is_valid_uuid(user_id):
            # Check if it looks like a prefix (8 characters, no hyphens)
            if len(user_id) == 8 and '-' not in user_id:
                raise UserIdError(
                    f"Invalid user_id: '{user_id}' appears to be an 8-character prefix. "
                    f"Full UUID required (36 characters with hyphens)."
                )
            raise UserIdError(
                f"Invalid user_id: '{user_id}' is not a valid UUID v4. "
                f"Expected format: 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'"
            )
    
    @staticmethod
    def is_valid_uuid(uuid_string: str) -> bool:
        """
        Check if string is a valid UUID v4 format.
        
        Args:
            uuid_string: String to validate
            
        Returns:
            True if valid UUID v4, False otherwise
        """
        if not uuid_string:
            return False
        
        # First try regex pattern (fast)
        if UUID_V4_PATTERN.match(uuid_string):
            return True
        
        # Fallback to uuid library (handles edge cases)
        try:
            parsed = uuid.UUID(uuid_string, version=4)
            return str(parsed) == uuid_string.lower()
        except (ValueError, AttributeError, TypeError):
            return False
    
    @staticmethod
    def format_for_display(user_id: str) -> str:
        """
        Format full UUID for display (first 8 characters + ellipsis).
        Use this for logging only, never for database queries.
        
        Args:
            user_id: Full UUID
            
        Returns:
            Display string (e.g., "bb4a6f7c...")
        """
        if not user_id or len(user_id) < 8:
            return user_id or "(none)"
        return f"{user_id[:8]}..."

