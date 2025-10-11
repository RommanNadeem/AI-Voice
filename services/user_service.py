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
            
            # STRICT EQUALITY: profiles.user_id = :user_id (exact match on full UUID)
            resp = self.supabase.table("profiles").select("id").eq("user_id", user_id).execute()
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

            # Create profile (profiles table has user_id column for UUID)
            logger.info(f"[USER SERVICE] Creating new profile for {UserId.format_for_display(user_id)}")
            print(f"[USER SERVICE] Creating new profile for {UserId.format_for_display(user_id)}")
            
            profile_data = {
                "user_id": user_id,  # profiles.user_id column stores the UUID
                "email": f"user_{user_id[:8]}@companion.local",
                "is_first_login": True,
            }
            
            try:
                create_resp = self.supabase.table("profiles").insert(profile_data).execute()
                
                # Verify the insert actually worked
                if getattr(create_resp, "error", None):
                    logger.error(f"[USER SERVICE] Insert returned error: {create_resp.error}")
                    print(f"[USER SERVICE] Insert returned error: {create_resp.error}")
                    return False
                
                if not create_resp.data or len(create_resp.data) == 0:
                    logger.error(f"[USER SERVICE] Insert returned no data - creation may have failed")
                    print(f"[USER SERVICE] Insert returned no data - creation may have failed")
                    return False
                
                logger.info(f"[USER SERVICE] ✅ Created profile for user {UserId.format_for_display(user_id)}")
                print(f"[USER SERVICE] ✅ Created profile for user {UserId.format_for_display(user_id)}")
                print(f"[USER SERVICE] Verification: {create_resp.data}")
                return True
            except Exception as insert_error:
                # Handle duplicate key error (profile might have been created by another process)
                err_str = str(insert_error)
                logger.error(f"[USER SERVICE] Insert exception: {err_str}")
                
                if "duplicate key" in err_str.lower() or "unique constraint" in err_str.lower():
                    logger.warning(f"[USER SERVICE] Profile already exists (concurrent creation)")
                    print(f"[USER SERVICE] Profile already exists (concurrent creation)")
                    return True
                else:
                    logger.error(f"[USER SERVICE] Profile creation error: {insert_error}", exc_info=True)
                    print(f"[USER SERVICE] Profile creation error: {insert_error}")
                    return False

        except Exception as e:
            logger.error(f"[USER SERVICE] ensure_profile_exists failed: {e}", exc_info=True)
            print(f"[USER SERVICE] ensure_profile_exists failed: {e}")
            return False
    
    def get_user_info(self, user_id: str) -> Optional[dict]:
        """
        Get user information from profiles table.
        
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
            # Query by user_id column
            resp = self.supabase.table("profiles").select("*").eq("user_id", user_id).execute()
            data = getattr(resp, "data", []) or []
            return data[0] if data else None
        except Exception as e:
            print(f"[USER SERVICE] get_user_info failed: {e}")
            return None
    
    def update_user_profile(self, user_id: str, updates: dict) -> bool:
        """
        Update user profile fields.
        
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
            # Update by user_id column
            resp = self.supabase.table("profiles").update(updates).eq("user_id", user_id).execute()
            if getattr(resp, "error", None):
                print(f"[USER SERVICE] Update error: {resp.error}")
                return False
            return True
        except Exception as e:
            print(f"[USER SERVICE] update_user_profile failed: {e}")
            return False

