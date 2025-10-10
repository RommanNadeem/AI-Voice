"""
User Service - Handles user profile and authentication operations
"""

from typing import Optional
from supabase import Client
from core.validators import can_write_for_current_user, get_current_user_id


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
            print("[USER SERVICE] Supabase not connected")
            return False
        
        try:
            # Check if profile exists
            resp = self.supabase.table("profiles").select("id").eq("user_id", user_id).execute()
            rows = getattr(resp, "data", []) or []
            if rows:
                return True

            # Create profile
            profile_data = {
                "user_id": user_id,
                "email": f"user_{user_id[:8]}@companion.local",
                "is_first_login": True,
            }
            create_resp = self.supabase.table("profiles").insert(profile_data).execute()
            if getattr(create_resp, "error", None):
                print(f"[USER SERVICE] Profile creation error: {create_resp.error}")
                return False
            
            print(f"[USER SERVICE] Created profile for user {user_id}")
            return True

        except Exception as e:
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

