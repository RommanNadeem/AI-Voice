"""
Memory Service - Handles memory storage and retrieval operations
"""

import time
from typing import Optional, List, Dict
from supabase import Client
from core.validators import can_write_for_current_user, get_current_user_id


class MemoryService:
    """Service for memory-related operations"""
    
    def __init__(self, supabase_client: Optional[Client] = None):
        self.supabase = supabase_client
    
    def save_memory(self, category: str, key: str, value: str, user_id: Optional[str] = None) -> bool:
        """
        Save memory to Supabase.
        
        Args:
            category: Memory category (FACT, GOAL, INTEREST, etc.)
            key: Memory key
            value: Memory value
            user_id: Optional user ID (uses current user if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        if not can_write_for_current_user():
            return False
        
        uid = user_id or get_current_user_id()
        if not uid:
            return False
        
        try:
            memory_data = {
                "user_id": uid,
                "category": category,
                "key": key,
                "value": value,
            }
            resp = self.supabase.table("memory").upsert(memory_data).execute()
            if getattr(resp, "error", None):
                print(f"[MEMORY SERVICE] Save error: {resp.error}")
                return False
            print(f"[MEMORY SERVICE] Saved [{category}] {key}")
            return True
        except Exception as e:
            print(f"[MEMORY SERVICE] save_memory failed: {e}")
            return False
    
    def get_memory(self, category: str, key: str, user_id: Optional[str] = None) -> Optional[str]:
        """
        Get memory from Supabase.
        
        Args:
            category: Memory category
            key: Memory key
            user_id: Optional user ID (uses current user if not provided)
            
        Returns:
            Memory value or None
        """
        if not can_write_for_current_user():
            return None
        
        uid = user_id or get_current_user_id()
        if not uid:
            return None
        
        try:
            resp = self.supabase.table("memory").select("value") \
                            .eq("user_id", uid) \
                            .eq("category", category) \
                            .eq("key", key) \
                            .execute()
            if getattr(resp, "error", None):
                print(f"[MEMORY SERVICE] Get error: {resp.error}")
                return None
            data = getattr(resp, "data", []) or []
            return data[0].get("value") if data else None
        except Exception as e:
            print(f"[MEMORY SERVICE] get_memory failed: {e}")
            return None
    
    def get_memories_by_category(self, category: str, limit: int = 50, user_id: Optional[str] = None) -> List[Dict]:
        """
        Get all memories for a category.
        
        Args:
            category: Memory category
            limit: Maximum number of memories to return
            user_id: Optional user ID (uses current user if not provided)
            
        Returns:
            List of memory dicts
        """
        if not can_write_for_current_user():
            return []
        
        uid = user_id or get_current_user_id()
        if not uid:
            return []
        
        try:
            resp = self.supabase.table("memory").select("*") \
                            .eq("user_id", uid) \
                            .eq("category", category) \
                            .order("created_at", desc=True) \
                            .limit(limit) \
                            .execute()
            return getattr(resp, "data", []) or []
        except Exception as e:
            print(f"[MEMORY SERVICE] get_memories_by_category failed: {e}")
            return []
    
    def delete_memory(self, category: str, key: str, user_id: Optional[str] = None) -> bool:
        """
        Delete a memory.
        
        Args:
            category: Memory category
            key: Memory key
            user_id: Optional user ID (uses current user if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        if not can_write_for_current_user():
            return False
        
        uid = user_id or get_current_user_id()
        if not uid:
            return False
        
        try:
            resp = self.supabase.table("memory").delete() \
                            .eq("user_id", uid) \
                            .eq("category", category) \
                            .eq("key", key) \
                            .execute()
            if getattr(resp, "error", None):
                print(f"[MEMORY SERVICE] Delete error: {resp.error}")
                return False
            return True
        except Exception as e:
            print(f"[MEMORY SERVICE] delete_memory failed: {e}")
            return False

