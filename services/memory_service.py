"""
Memory Service - Handles memory storage and retrieval operations
"""

import logging
import time
from typing import Optional, List, Dict
from supabase import Client
from core.validators import can_write_for_current_user, get_current_user_id
from services.user_service import UserService

logger = logging.getLogger(__name__)


class MemoryService:
    """Service for memory-related operations"""
    
    def __init__(self, supabase_client: Optional[Client] = None):
        self.supabase = supabase_client
    
    def save_memory(self, category: str, key: str, value: str, user_id: Optional[str] = None) -> bool:
        """
        Save memory to Supabase.
        
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
        
        # Validate key format - reject timestamp-based keys
        if key.startswith("user_input_"):
            print(f"[MEMORY SERVICE] ❌ Rejected timestamp-based key: {key}")
            print(f"[MEMORY SERVICE]    Use descriptive English keys instead (e.g., 'favorite_food', 'nickname')")
            return False
        
        try:
            memory_data = {
                "user_id": uid,
                "category": category,
                "key": key,
                "value": value,
            }
            print(f"[MEMORY SERVICE] 💾 Saving memory: [{category}] {key}")
            print(f"[MEMORY SERVICE]    Value: {value[:100]}{'...' if len(value) > 100 else ''}")
            print(f"[MEMORY SERVICE]    User: {uid[:8]}...")
            
            # Upsert with conflict resolution on unique constraint (user_id, category, key)
            resp = self.supabase.table("memory").upsert(
                memory_data,
                on_conflict="user_id,category,key"
            ).execute()
            if getattr(resp, "error", None):
                # Handle possible FK error to profiles by ensuring parent exists, then retry once
                err = resp.error
                err_str = str(err)
                if isinstance(err, dict):
                    err_code = err.get("code")
                else:
                    err_code = None
                if err_code == "23503" or ("violates foreign key constraint" in err_str and "profiles" in err_str.lower()):
                    print(f"[MEMORY SERVICE] ⚠️  FK error, ensuring profiles row exists then retrying once...")
                    user_service = UserService(self.supabase)
                    if user_service.ensure_profile_exists(uid):
                        retry = self.supabase.table("memory").upsert(
                            memory_data,
                            on_conflict="user_id,category,key"
                        ).execute()
                        if not getattr(retry, "error", None):
                            print(f"[MEMORY SERVICE] ✅ Saved successfully after ensuring profiles parent")
                            return True
                    print(f"[MEMORY SERVICE] ❌ Save error persists after retry: {resp.error}")
                    return False
                print(f"[MEMORY SERVICE] ❌ Save error: {resp.error}")
                return False
            print(f"[MEMORY SERVICE] ✅ Saved successfully: [{category}] {key}")
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
            print(f"[MEMORY SERVICE] 🔍 Fetching memory: [{category}] {key}")
            print(f"[MEMORY SERVICE]    User: {uid[:8]}...")
            
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
        
        try:
            print(f"[MEMORY SERVICE] 🔍 Fetching memories by category: [{category}] (limit: {limit})")
            print(f"[MEMORY SERVICE]    User: {uid[:8]}...")
            
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
        
        try:
            print(f"[MEMORY SERVICE] 🚀 Batch fetching {len(categories)} categories (optimized)...")
            print(f"[MEMORY SERVICE]    User: {uid[:8]}...")
            
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
        
        Args:
            category: Memory category (FACT, GOAL, INTEREST, etc.)
            key: Memory key (must be English, snake_case, no timestamp format)
            value: Memory value
            user_id: User ID (explicit, required)
            
        Returns:
            True if successful, False otherwise
        """
        if not user_id:
            return False
        
        # Validate key format - reject timestamp-based keys
        if key.startswith("user_input_"):
            print(f"[MEMORY SERVICE] ❌ Rejected timestamp-based key: {key}")
            print(f"[MEMORY SERVICE]    Use descriptive English keys instead (e.g., 'favorite_food', 'nickname')")
            return False
        
        try:
            import asyncio
            memory_data = {
                "user_id": user_id,
                "category": category,
                "key": key,
                "value": value,
            }
            
            logger.info(f"[MEMORY SERVICE] 💾 Attempting async save: [{category}] {key}")
            logger.debug(f"[MEMORY SERVICE]    User: {user_id[:8]}... Value: {value[:50]}...")
            
            try:
                resp = await asyncio.to_thread(
                    lambda: self.supabase.table("memory").upsert(memory_data, on_conflict="user_id,category,key").execute()
                )
            except Exception as db_error:
                # Handle FK constraint errors from Postgrest exceptions
                err_str = str(db_error)
                logger.error(f"[MEMORY SERVICE] ❌ Database error: {err_str}")
                
                # Check if it's a FK constraint violation
                if "23503" in err_str or ("violates foreign key constraint" in err_str.lower() and "profiles" in err_str.lower()):
                    logger.warning(f"[MEMORY SERVICE] ⚠️  FK error detected, ensuring profiles row exists...")
                    print(f"[MEMORY SERVICE] ⚠️  FK error detected, ensuring profiles row exists...")
                    
                    # Ensure profile exists and retry
                    user_service = UserService(self.supabase)
                    profile_created = await asyncio.to_thread(user_service.ensure_profile_exists, user_id)
                    
                    if profile_created:
                        logger.info(f"[MEMORY SERVICE] ✓ Profile exists, retrying memory save...")
                        print(f"[MEMORY SERVICE] ✓ Profile exists, retrying memory save...")
                        try:
                            retry = await asyncio.to_thread(
                                lambda: self.supabase.table("memory").upsert(memory_data, on_conflict="user_id,category,key").execute()
                            )
                            logger.info(f"[MEMORY SERVICE] ✅ Saved successfully after ensuring profiles parent (async)")
                            print(f"[MEMORY SERVICE] ✅ Saved successfully after ensuring profiles parent (async)")
                            return True
                        except Exception as retry_error:
                            logger.error(f"[MEMORY SERVICE] ❌ Retry failed: {retry_error}")
                            print(f"[MEMORY SERVICE] ❌ Retry failed: {retry_error}")
                            return False
                    else:
                        logger.error(f"[MEMORY SERVICE] ❌ Failed to ensure profile exists")
                        print(f"[MEMORY SERVICE] ❌ Failed to ensure profile exists")
                        return False
                else:
                    # Some other database error
                    logger.error(f"[MEMORY SERVICE] ❌ Non-FK database error: {err_str}")
                    print(f"[MEMORY SERVICE] ❌ Non-FK database error: {err_str}")
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

