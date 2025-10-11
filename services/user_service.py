"""
User Service - Handles user profile and authentication operations
"""

import logging
from typing import Optional
from supabase import Client
from core.validators import can_write_for_current_user, get_current_user_id
from core.user_id import UserId, UserIdError

logger = logging.getLogger(__name__)


class UserService:
    """Service for user-related operations"""
    
    def __init__(self, supabase_client: Optional[Client] = None):
        self.supabase = supabase_client
    
    def profile_exists(self, user_id: str) -> bool:
        """
        Check if a profile exists for the user_id in the profiles table.
        Uses STRICT equality check on full UUID (no LIKE, no prefix).
        
        Args:
            user_id: Full user UUID (not a prefix)
            
        Returns:
            True if profile exists, False otherwise
        """
        if not self.supabase:
            logger.error("[USER SERVICE] Supabase not connected")
            print("[USER SERVICE] Supabase not connected")
            return False
        
        # STRICT VALIDATION: Ensure full UUID
        try:
            UserId.assert_full_uuid(user_id)
        except UserIdError as e:
            logger.error(f"[USER SERVICE] ❌ Invalid user_id: {e}")
            print(f"[USER SERVICE] ❌ Invalid user_id: {e}")
            return False
        
        try:
            logger.info(f"[USER SERVICE] Checking if profile exists for {UserId.format_for_display(user_id)}")
            print(f"[USER SERVICE] Checking if profile exists for {UserId.format_for_display(user_id)}")
            
            # STRICT EQUALITY: profiles.id = :user_id (exact match on full UUID)
            resp = self.supabase.table("profiles").select("id").eq("id", user_id).execute()
            rows = getattr(resp, "data", []) or []
            
            exists = len(rows) > 0
            if exists:
                logger.info(f"[USER SERVICE] ✅ Profile EXISTS for {UserId.format_for_display(user_id)}")
                print(f"[USER SERVICE] ✅ Profile EXISTS for {UserId.format_for_display(user_id)}")
            else:
                logger.info(f"[USER SERVICE] ℹ️  Profile NOT FOUND for {UserId.format_for_display(user_id)}")
                print(f"[USER SERVICE] ℹ️  Profile NOT FOUND for {UserId.format_for_display(user_id)}")
            
            return exists
            
        except Exception as e:
            logger.error(f"[USER SERVICE] profile_exists query failed: {e}", exc_info=True)
            print(f"[USER SERVICE] profile_exists query failed: {e}")
            return False
    
    def ensure_profile_exists(self, user_id: str) -> bool:
        """
        Ensure a profile exists for the user_id in the profiles table.
        Creates one if it doesn't exist (upsert behavior).
        
        Note: profiles.id stores the UUID (same as user_id) to match FK constraints.
        
        Args:
            user_id: Full user UUID (not a prefix)
            
        Returns:
            True if profile exists or was created, False on error
        """
        if not self.supabase:
            logger.error("[USER SERVICE] Supabase not connected")
            print("[USER SERVICE] Supabase not connected")
            return False
        
        # STRICT VALIDATION: Ensure full UUID
        try:
            UserId.assert_full_uuid(user_id)
        except UserIdError as e:
            logger.error(f"[USER SERVICE] ❌ Invalid user_id: {e}")
            print(f"[USER SERVICE] ❌ Invalid user_id: {e}")
            return False
        
        try:
            # Check if profile already exists
            if self.profile_exists(user_id):
                return True

            # Create profile (profiles table uses id column for UUID, same as user_id)
            logger.info(f"[USER SERVICE] Creating new profile for {UserId.format_for_display(user_id)}")
            print(f"[USER SERVICE] Creating new profile for {UserId.format_for_display(user_id)}")
            
            profile_data = {
                "id": user_id,  # profiles.id column stores the UUID (same as user_id)
                "user_id": user_id,  # Keep both for consistency
                "email": f"user_{user_id[:8]}@companion.local",
                "is_first_login": True,
            }
            
            try:
                # Use upsert to prevent race conditions - will insert if new, update if exists
                create_resp = self.supabase.table("profiles").upsert(profile_data, on_conflict="user_id").execute()
                
                # Verify the upsert actually worked
                if getattr(create_resp, "error", None):
                    logger.error(f"[USER SERVICE] Upsert returned error: {create_resp.error}")
                    print(f"[USER SERVICE] Upsert returned error: {create_resp.error}")
                    return False
                
                if not create_resp.data or len(create_resp.data) == 0:
                    logger.error(f"[USER SERVICE] Upsert returned no data - operation may have failed")
                    print(f"[USER SERVICE] Upsert returned no data - operation may have failed")
                    return False
                
                logger.info(f"[USER SERVICE] ✅ Ensured profile exists for user {UserId.format_for_display(user_id)}")
                print(f"[USER SERVICE] ✅ Ensured profile exists for user {UserId.format_for_display(user_id)}")
                print(f"[USER SERVICE] Verification: {create_resp.data}")
                return True
            except Exception as upsert_error:
                # Upsert should rarely fail, but handle any unexpected errors
                err_str = str(upsert_error)
                logger.error(f"[USER SERVICE] Upsert exception: {err_str}")
                print(f"[USER SERVICE] Upsert exception: {err_str}")
                return False

        except Exception as e:
            logger.error(f"[USER SERVICE] ensure_profile_exists failed: {e}", exc_info=True)
            print(f"[USER SERVICE] ensure_profile_exists failed: {e}")
            return False
    
    def get_user_info(self, user_id: str) -> Optional[dict]:
        """
        Get user information from profiles table.
        
        Note: Queries profiles.id column which stores the UUID.
        
        Args:
            user_id: Full user UUID (not a prefix)
            
        Returns:
            User profile dict or None
        """
        if not self.supabase:
            return None
        
        # STRICT VALIDATION: Ensure full UUID
        try:
            UserId.assert_full_uuid(user_id)
        except UserIdError as e:
            logger.error(f"[USER SERVICE] ❌ Invalid user_id: {e}")
            print(f"[USER SERVICE] ❌ Invalid user_id: {e}")
            return None
        
        try:
            # Query by id column (which stores the UUID)
            resp = self.supabase.table("profiles").select("*").eq("id", user_id).execute()
            data = getattr(resp, "data", []) or []
            return data[0] if data else None
        except Exception as e:
            print(f"[USER SERVICE] get_user_info failed: {e}")
            return None
    
    def update_user_profile(self, user_id: str, updates: dict) -> bool:
        """
        Update user profile fields.
        
        Note: Updates profiles.id column which stores the UUID.
        
        Args:
            user_id: Full user UUID (not a prefix)
            updates: Dict of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        if not self.supabase:
            return False
        
        # STRICT VALIDATION: Ensure full UUID
        try:
            UserId.assert_full_uuid(user_id)
        except UserIdError as e:
            logger.error(f"[USER SERVICE] ❌ Invalid user_id: {e}")
            print(f"[USER SERVICE] ❌ Invalid user_id: {e}")
            return False
        
        try:
            # Update by id column (which stores the UUID)
            resp = self.supabase.table("profiles").update(updates).eq("id", user_id).execute()
            if getattr(resp, "error", None):
                print(f"[USER SERVICE] Update error: {resp.error}")
                return False
            return True
        except Exception as e:
            print(f"[USER SERVICE] update_user_profile failed: {e}")
            return False

