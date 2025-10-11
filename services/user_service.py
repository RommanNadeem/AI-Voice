"""
User Service - Handles user profile and authentication operations
"""

import logging
from typing import Optional
from supabase import Client
from core.validators import can_write_for_current_user, get_current_user_id

logger = logging.getLogger(__name__)


class UserService:
    """Service for user-related operations"""
    
    def __init__(self, supabase_client: Optional[Client] = None):
        self.supabase = supabase_client
    
    def ensure_profile_exists(self, user_id: str) -> bool:
        """
        Ensure a profile exists for the user_id in the profiles table.
        
        Args:
            user_id: User UUID
            
        Returns:
            True if profile exists or was created, False on error
        """
        if not self.supabase:
            logger.error("[USER SERVICE] Supabase not connected")
            print("[USER SERVICE] Supabase not connected")
            return False
        
        try:
            logger.info(f"[USER SERVICE] Checking if profile exists for {user_id[:8]}...")
            print(f"[USER SERVICE] Checking if profile exists for {user_id[:8]}...")
            
            # Check if profile exists
            resp = self.supabase.table("profiles").select("id").eq("user_id", user_id).execute()
            rows = getattr(resp, "data", []) or []
            if rows:
                logger.info(f"[USER SERVICE] ✓ Profile already exists for {user_id[:8]}")
                print(f"[USER SERVICE] ✓ Profile already exists for {user_id[:8]}")
                return True

            # Create profile
            logger.info(f"[USER SERVICE] Creating new profile for {user_id[:8]}...")
            print(f"[USER SERVICE] Creating new profile for {user_id[:8]}...")
            
            profile_data = {
                "user_id": user_id,
                "email": f"user_{user_id[:8]}@companion.local",
                "is_first_login": True,
            }
            
            try:
                create_resp = self.supabase.table("profiles").insert(profile_data).execute()
                logger.info(f"[USER SERVICE] ✅ Created profile for user {user_id[:8]}")
                print(f"[USER SERVICE] ✅ Created profile for user {user_id[:8]}")
                return True
            except Exception as insert_error:
                # Handle duplicate key error (profile might have been created by another process)
                err_str = str(insert_error)
                if "duplicate key" in err_str.lower() or "unique constraint" in err_str.lower():
                    logger.warning(f"[USER SERVICE] Profile already exists (concurrent creation)")
                    print(f"[USER SERVICE] Profile already exists (concurrent creation)")
                    return True
                else:
                    logger.error(f"[USER SERVICE] Profile creation error: {insert_error}")
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
            user_id: User UUID
            
        Returns:
            User profile dict or None
        """
        if not self.supabase:
            return None
        
        try:
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
            user_id: User UUID
            updates: Dict of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        if not self.supabase:
            return False
        
        try:
            resp = self.supabase.table("profiles").update(updates).eq("user_id", user_id).execute()
            if getattr(resp, "error", None):
                print(f"[USER SERVICE] Update error: {resp.error}")
                return False
            return True
        except Exception as e:
            print(f"[USER SERVICE] update_user_profile failed: {e}")
            return False

