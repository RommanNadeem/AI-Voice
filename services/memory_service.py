"""
Memory Service - Handles memory storage and retrieval operations
"""

import logging
import time
from typing import Optional, List, Dict
from supabase import Client
from core.validators import can_write_for_current_user, get_current_user_id
from core.user_id import UserId, UserIdError
from services.user_service import UserService

logger = logging.getLogger(__name__)


class MemoryService:
    """Service for memory-related operations"""
    
    def __init__(self, supabase_client: Optional[Client] = None):
        self.supabase = supabase_client
    
    def save_memory(self, category: str, key: str, value: str, user_id: Optional[str] = None) -> bool:
        """
        Save memory to Supabase.
        ENSURES profile exists BEFORE attempting insert to prevent FK errors.
        
        Args:
            category: Memory category (FACT, GOAL, INTEREST, etc.)
            key: Memory key (must be English, snake_case, no timestamp format)
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
        
        # STRICT VALIDATION: Ensure full UUID
        try:
            UserId.assert_full_uuid(uid)
        except UserIdError as e:
            logger.error(f"[MEMORY SERVICE] ❌ Invalid user_id: {e}")
            print(f"[MEMORY SERVICE] ❌ Invalid user_id: {e}")
            return False
        
        # Validate key format - reject timestamp-based keys
        if key.startswith("user_input_"):
            print(f"[MEMORY SERVICE] ❌ Rejected timestamp-based key: {key}")
            print(f"[MEMORY SERVICE]    Use descriptive English keys instead (e.g., 'favorite_food', 'nickname')")
            return False
        
        # CRITICAL: Ensure profile exists BEFORE any memory insert
        user_service = UserService(self.supabase)
        if not user_service.ensure_profile_exists(uid):
            logger.error(f"[MEMORY SERVICE] ❌ CRITICAL: Cannot save memory - profile does not exist for {UserId.format_for_display(uid)}")
            print(f"[MEMORY SERVICE] ❌ CRITICAL: Cannot save memory - profile does not exist for {UserId.format_for_display(uid)}")
            print(f"[MEMORY SERVICE] ❌ This is a FK constraint violation waiting to happen!")
            return False
        
        try:
            memory_data = {
                "user_id": uid,
                "category": category,
                "key": key,
                "value": value,
            }
            logger.info(f"[MEMORY SERVICE] 💾 Saving memory (sync): [{category}] {key}")
            logger.debug(f"[MEMORY SERVICE]    User: {UserId.format_for_display(uid)} Value: {value[:50]}...")
            print(f"[MEMORY SERVICE] 💾 Saving memory: [{category}] {key}")
            print(f"[MEMORY SERVICE]    Value: {value[:100]}{'...' if len(value) > 100 else ''}")
            print(f"[MEMORY SERVICE]    User: {UserId.format_for_display(uid)}")
            
            # Upsert with conflict resolution on unique constraint (user_id, category, key)
            try:
                resp = self.supabase.table("memory").upsert(
                    memory_data,
                    on_conflict="user_id,category,key"
                ).execute()
            except Exception as db_error:
                # Handle FK constraint errors from Postgrest exceptions
                err_str = str(db_error)
                logger.error(f"[MEMORY SERVICE] ❌ Database error (sync): {err_str}")
                
                # Check if it's a FK constraint violation (23503)
                if "23503" in err_str or ("violates foreign key constraint" in err_str.lower() and "profiles" in err_str.lower()):
                    # This should NEVER happen because we called ensure_profile_exists above
                    logger.critical(f"[MEMORY SERVICE] 🚨 CRITICAL BUG: FK error after ensure_profile_exists!")
                    logger.critical(f"[MEMORY SERVICE] 🚨 user_id: {uid}")
                    logger.critical(f"[MEMORY SERVICE] 🚨 Error: {err_str}")
                    print(f"[MEMORY SERVICE] 🚨 CRITICAL BUG: FK error despite ensuring profile exists!")
                    print(f"[MEMORY SERVICE] 🚨 This indicates a serious consistency issue")
                    print(f"[MEMORY SERVICE] 🚨 user_id: {uid}")
                    return False
                else:
                    # Some other database error
                    logger.error(f"[MEMORY SERVICE] ❌ Non-FK database error (sync): {err_str}")
                    print(f"[MEMORY SERVICE] ❌ Save error: {err_str}")
                    return False
            
            # Check response for errors (old error handling pattern)
            if getattr(resp, "error", None):
                err = resp.error
                logger.error(f"[MEMORY SERVICE] ❌ Save error in response (sync): {err}")
                print(f"[MEMORY SERVICE] ❌ Save error: {err}")
                return False
            
            logger.info(f"[MEMORY SERVICE] ✅ Saved successfully (sync): [{category}] {key}")
            print(f"[MEMORY SERVICE] ✅ Saved successfully: [{category}] {key}")
            return True
        except Exception as e:
            logger.error(f"[MEMORY SERVICE] save_memory failed: {e}", exc_info=True)
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
        
        # STRICT VALIDATION: Ensure full UUID
        try:
            UserId.assert_full_uuid(uid)
        except UserIdError as e:
            logger.error(f"[MEMORY SERVICE] ❌ Invalid user_id: {e}")
            print(f"[MEMORY SERVICE] ❌ Invalid user_id: {e}")
            return None
        
        try:
            print(f"[MEMORY SERVICE] 🔍 Fetching memory: [{category}] {key}")
            print(f"[MEMORY SERVICE]    User: {UserId.format_for_display(uid)}")
            
            resp = self.supabase.table("memory").select("value") \
                            .eq("user_id", uid) \
                            .eq("category", category) \
                            .eq("key", key) \
                            .execute()
            if getattr(resp, "error", None):
                print(f"[MEMORY SERVICE] ❌ Fetch error: {resp.error}")
                return None
            data = getattr(resp, "data", []) or []
            
            if data:
                value = data[0].get("value")
                print(f"[MEMORY SERVICE] ✅ Found: {value[:100]}{'...' if len(value) > 100 else ''}")
                return value
            else:
                print(f"[MEMORY SERVICE] ℹ️  Not found: [{category}] {key}")
                return None
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
        
        # STRICT VALIDATION: Ensure full UUID
        try:
            UserId.assert_full_uuid(uid)
        except UserIdError as e:
            logger.error(f"[MEMORY SERVICE] ❌ Invalid user_id: {e}")
            print(f"[MEMORY SERVICE] ❌ Invalid user_id: {e}")
            return []
        
        try:
            print(f"[MEMORY SERVICE] 🔍 Fetching memories by category: [{category}] (limit: {limit})")
            print(f"[MEMORY SERVICE]    User: {UserId.format_for_display(uid)}")
            
            resp = self.supabase.table("memory").select("*") \
                            .eq("user_id", uid) \
                            .eq("category", category) \
                            .order("created_at", desc=True) \
                            .limit(limit) \
                            .execute()
            data = getattr(resp, "data", []) or []
            print(f"[MEMORY SERVICE] ✅ Found {len(data)} memories in category [{category}]")
            return data
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
    
    def get_memories_by_categories_batch(
        self, 
        categories: List[str], 
        limit_per_category: int = 3, 
        user_id: Optional[str] = None
    ) -> Dict[str, List[Dict]]:
        """
        🚀 OPTIMIZED: Fetch memories from multiple categories in ONE database query.
        This replaces sequential queries and reduces DB load by 80%+.
        
        Args:
            categories: List of categories to fetch (e.g., ["FACT", "GOAL", "INTEREST"])
            limit_per_category: Maximum memories per category
            user_id: Optional user ID (uses current user if not provided)
            
        Returns:
            Dict mapping category name to list of memories:
            {"FACT": [mem1, mem2], "GOAL": [mem3, mem4], ...}
        """
        if not can_write_for_current_user():
            return {cat: [] for cat in categories}
        
        uid = user_id or get_current_user_id()
        if not uid:
            return {cat: [] for cat in categories}
        
        # STRICT VALIDATION: Ensure full UUID
        try:
            UserId.assert_full_uuid(uid)
        except UserIdError as e:
            logger.error(f"[MEMORY SERVICE] ❌ Invalid user_id: {e}")
            print(f"[MEMORY SERVICE] ❌ Invalid user_id: {e}")
            return {cat: [] for cat in categories}
        
        try:
            print(f"[MEMORY SERVICE] 🚀 Batch fetching {len(categories)} categories (optimized)...")
            print(f"[MEMORY SERVICE]    User: {UserId.format_for_display(uid)}")
            
            # Single query with .in_() filter - gets all categories at once!
            resp = self.supabase.table("memory").select("*") \
                .eq("user_id", uid) \
                .in_("category", categories) \
                .order("created_at", desc=True) \
                .limit(limit_per_category * len(categories)) \
                .execute()
            
            data = getattr(resp, "data", []) or []
            
            # Group by category and limit each
            grouped = {cat: [] for cat in categories}
            
            for mem in data:
                cat = mem.get("category")
                if cat in grouped and len(grouped[cat]) < limit_per_category:
                    grouped[cat].append(mem)
            
            # Log results
            total = sum(len(mems) for mems in grouped.values())
            print(f"[MEMORY SERVICE] ✅ Fetched {total} memories across {len(categories)} categories in 1 query")
            
            return grouped
            
        except Exception as e:
            print(f"[MEMORY SERVICE] ❌ Batch fetch error: {e}")
            return {cat: [] for cat in categories}
    
    async def store_memory_async(self, category: str, key: str, value: str, user_id: str) -> bool:
        """
        Save memory to Supabase (async version).
        ENSURES profile exists BEFORE attempting insert to prevent FK errors.
        
        Args:
            category: Memory category (FACT, GOAL, INTEREST, etc.)
            key: Memory key (must be English, snake_case, no timestamp format)
            value: Memory value
            user_id: User ID (explicit, required - full UUID)
            
        Returns:
            True if successful, False otherwise
        """
        if not user_id:
            return False
        
        # STRICT VALIDATION: Ensure full UUID
        try:
            UserId.assert_full_uuid(user_id)
        except UserIdError as e:
            logger.error(f"[MEMORY SERVICE] ❌ Invalid user_id: {e}")
            print(f"[MEMORY SERVICE] ❌ Invalid user_id: {e}")
            return False
        
        # Validate key format - reject timestamp-based keys
        if key.startswith("user_input_"):
            print(f"[MEMORY SERVICE] ❌ Rejected timestamp-based key: {key}")
            print(f"[MEMORY SERVICE]    Use descriptive English keys instead (e.g., 'favorite_food', 'nickname')")
            return False
        
        # CRITICAL: Ensure profile exists BEFORE any memory insert
        import asyncio
        user_service = UserService(self.supabase)
        profile_exists = await asyncio.to_thread(user_service.ensure_profile_exists, user_id)
        if not profile_exists:
            logger.error(f"[MEMORY SERVICE] ❌ CRITICAL: Cannot save memory - profile does not exist for {UserId.format_for_display(user_id)}")
            print(f"[MEMORY SERVICE] ❌ CRITICAL: Cannot save memory - profile does not exist for {UserId.format_for_display(user_id)}")
            print(f"[MEMORY SERVICE] ❌ This is a FK constraint violation waiting to happen!")
            return False
        
        try:
            memory_data = {
                "user_id": user_id,
                "category": category,
                "key": key,
                "value": value,
            }
            
            logger.info(f"[MEMORY SERVICE] 💾 Attempting async save: [{category}] {key}")
            logger.debug(f"[MEMORY SERVICE]    User: {UserId.format_for_display(user_id)} Value: {value[:50]}...")
            
            try:
                resp = await asyncio.to_thread(
                    lambda: self.supabase.table("memory").upsert(memory_data, on_conflict="user_id,category,key").execute()
                )
            except Exception as db_error:
                # Handle FK constraint errors from Postgrest exceptions
                err_str = str(db_error)
                logger.error(f"[MEMORY SERVICE] ❌ Database error (async): {err_str}")
                
                # Check if it's a FK constraint violation (23503)
                if "23503" in err_str or ("violates foreign key constraint" in err_str.lower() and "profiles" in err_str.lower()):
                    # This should NEVER happen because we called ensure_profile_exists above
                    logger.critical(f"[MEMORY SERVICE] 🚨 CRITICAL BUG: FK error after ensure_profile_exists! (async)")
                    logger.critical(f"[MEMORY SERVICE] 🚨 user_id: {user_id}")
                    logger.critical(f"[MEMORY SERVICE] 🚨 Error: {err_str}")
                    print(f"[MEMORY SERVICE] 🚨 CRITICAL BUG: FK error despite ensuring profile exists! (async)")
                    print(f"[MEMORY SERVICE] 🚨 This indicates a serious consistency issue")
                    print(f"[MEMORY SERVICE] 🚨 user_id: {user_id}")
                    return False
                else:
                    # Some other database error
                    logger.error(f"[MEMORY SERVICE] ❌ Non-FK database error (async): {err_str}")
                    print(f"[MEMORY SERVICE] ❌ Non-FK database error (async): {err_str}")
                    return False
            
            # Check response for errors (old error handling pattern)
            if getattr(resp, "error", None):
                err = resp.error
                logger.error(f"[MEMORY SERVICE] ❌ Save error in response: {err}")
                print(f"[MEMORY SERVICE] ❌ Save error in response: {err}")
                return False
            
            logger.info(f"[MEMORY SERVICE] ✅ Saved async: [{category}] {key}")
            print(f"[MEMORY SERVICE] ✅ Saved async: [{category}] {key}")
            return True
        except Exception as e:
            logger.error(f"[MEMORY SERVICE] store_memory_async failed: {e}", exc_info=True)
            print(f"[MEMORY SERVICE] store_memory_async failed: {e}")
            return False
    
    async def get_value_async(self, user_id: str, category: str, key: str) -> Optional[str]:
        """
        Get a specific memory value by category and key (async version).
        
        Args:
            user_id: User ID (explicit, required)
            category: Memory category
            key: Memory key
            
        Returns:
            Memory value or None
        """
        if not user_id:
            return None
        
        try:
            import asyncio
            resp = await asyncio.to_thread(
                lambda: self.supabase.table("memory").select("value")
                    .eq("user_id", user_id)
                    .eq("category", category)
                    .eq("key", key)
                    .execute()
            )
            if getattr(resp, "error", None):
                return None
            data = getattr(resp, "data", []) or []
            return data[0].get("value") if data else None
        except Exception as e:
            print(f"[MEMORY SERVICE] get_value_async failed: {e}")
            return None

