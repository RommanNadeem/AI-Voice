import asyncio
import time
from typing import Any, Dict, List, Optional
from supabase import Client


class DatabaseBatcher:
    """
    Database query batching for optimizing multiple operations.
    Reduces N+1 query problems and improves throughput.
    """
    
    def __init__(self, supabase_client: Optional[Client] = None):
        self.supabase = supabase_client
        self._batch_size = 100  # Max items per batch
        self._queries_saved = 0
        self._total_operations = 0
        
    async def batch_get_memories(
        self, 
        user_id: str, 
        category: Optional[str] = None,
        keys: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Batch fetch memories for a user with optional filtering.
        
        Args:
            user_id: User ID
            category: Optional category filter
            keys: Optional list of specific keys
            limit: Maximum number of results
            
        Returns:
            List of memory records
        """
        if not self.supabase:
            return []
        
        try:
            query = self.supabase.table("memory").select("*").eq("user_id", user_id)
            
            if category:
                query = query.eq("category", category)
            
            if keys:
                # Use IN clause for multiple keys (single query vs N queries)
                query = query.in_("key", keys)
                self._queries_saved += len(keys) - 1  # Saved N-1 queries
            
            if limit:
                query = query.limit(limit)
            
            query = query.order("created_at", desc=True)
            
            resp = await asyncio.to_thread(lambda: query.execute())
            self._total_operations += 1
            
            if getattr(resp, "error", None):
                print(f"[BATCH] Error fetching memories: {resp.error}")
                return []
            
            return getattr(resp, "data", []) or []
            
        except Exception as e:
            print(f"[BATCH] Error in batch_get_memories: {e}")
            return []
    
    async def batch_save_memories(self, memories: List[Dict]) -> bool:
        """
        Batch insert/upsert multiple memories in a single transaction.
        
        Args:
            memories: List of memory dicts with keys: user_id, category, key, value
            
        Returns:
            True if successful, False otherwise
        """
        if not self.supabase or not memories:
            return False
        
        try:
            # Split into batches if too large
            batches = [
                memories[i:i + self._batch_size] 
                for i in range(0, len(memories), self._batch_size)
            ]
            
            self._queries_saved += len(memories) - len(batches)  # Saved individual inserts
            
            for batch in batches:
                resp = await asyncio.to_thread(
                    lambda b=batch: self.supabase.table("memory").upsert(b).execute()
                )
                
                if getattr(resp, "error", None):
                    print(f"[BATCH] Error saving batch: {resp.error}")
                    return False
                
                self._total_operations += 1
            
            print(f"[BATCH] Saved {len(memories)} memories in {len(batches)} batch(es)")
            return True
            
        except Exception as e:
            print(f"[BATCH] Error in batch_save_memories: {e}")
            return False
    
    async def batch_delete_memories(self, user_id: str, keys: List[str]) -> int:
        """
        Batch delete multiple memories.
        
        Args:
            user_id: User ID
            keys: List of memory keys to delete
            
        Returns:
            Number of records deleted
        """
        if not self.supabase or not keys:
            return 0
        
        try:
            # Use IN clause for efficient deletion
            resp = await asyncio.to_thread(
                lambda: self.supabase.table("memory")
                .delete()
                .eq("user_id", user_id)
                .in_("key", keys)
                .execute()
            )
            
            self._queries_saved += len(keys) - 1  # Saved N-1 delete queries
            self._total_operations += 1
            
            if getattr(resp, "error", None):
                print(f"[BATCH] Error deleting memories: {resp.error}")
                return 0
            
            data = getattr(resp, "data", []) or []
            return len(data)
            
        except Exception as e:
            print(f"[BATCH] Error in batch_delete_memories: {e}")
            return 0
    
    async def batch_get_profiles(self, user_ids: List[str]) -> Dict[str, str]:
        """
        Batch fetch multiple user profiles.
        
        Args:
            user_ids: List of user IDs
            
        Returns:
            Dict mapping user_id -> profile_text
        """
        if not self.supabase or not user_ids:
            return {}
        
        try:
            # Single query with IN clause instead of N queries
            resp = await asyncio.to_thread(
                lambda: self.supabase.table("user_profiles")
                .select("user_id, profile_text")
                .in_("user_id", user_ids)
                .execute()
            )
            
            self._queries_saved += len(user_ids) - 1
            self._total_operations += 1
            
            if getattr(resp, "error", None):
                print(f"[BATCH] Error fetching profiles: {resp.error}")
                return {}
            
            data = getattr(resp, "data", []) or []
            return {row["user_id"]: row.get("profile_text", "") for row in data}
            
        except Exception as e:
            print(f"[BATCH] Error in batch_get_profiles: {e}")
            return {}
    
    async def bulk_memory_search(
        self,
        user_id: str,
        categories: List[str],
        limit_per_category: int = 10
    ) -> Dict[str, List[Dict]]:
        """
        Efficiently fetch memories across multiple categories.
        
        Args:
            user_id: User ID
            categories: List of categories to fetch
            limit_per_category: Max items per category
            
        Returns:
            Dict mapping category -> list of memories
        """
        if not self.supabase or not categories:
            return {}
        
        try:
            # Fetch all categories in one query
            resp = await asyncio.to_thread(
                lambda: self.supabase.table("memory")
                .select("*")
                .eq("user_id", user_id)
                .in_("category", categories)
                .order("created_at", desc=True)
                .limit(limit_per_category * len(categories))
                .execute()
            )
            
            self._queries_saved += len(categories) - 1
            self._total_operations += 1
            
            if getattr(resp, "error", None):
                print(f"[BATCH] Error in bulk search: {resp.error}")
                return {}
            
            data = getattr(resp, "data", []) or []
            
            # Group by category
            result = {cat: [] for cat in categories}
            for row in data:
                cat = row.get("category")
                if cat in result and len(result[cat]) < limit_per_category:
                    result[cat].append(row)
            
            return result
            
        except Exception as e:
            print(f"[BATCH] Error in bulk_memory_search: {e}")
            return {}
    
    async def prefetch_user_data(self, user_id: str) -> Dict[str, Any]:
        """
        Prefetch all commonly needed user data in parallel queries.
        Dramatically reduces initial load time.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict with profile, recent_memories, stats
        """
        if not self.supabase:
            return {}
        
        try:
            print(f"[BATCH] Prefetching all user data for {user_id}...")
            start_time = time.time()
            
            # Run multiple queries in parallel
            profile_task = asyncio.to_thread(
                lambda: self.supabase.table("user_profiles")
                .select("profile_text")
                .eq("user_id", user_id)
                .execute()
            )
            
            memories_task = asyncio.to_thread(
                lambda: self.supabase.table("memory")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(50)
                .execute()
            )
            
            onboarding_task = asyncio.to_thread(
                lambda: self.supabase.table("onboarding_details")
                .select("*")
                .eq("user_id", user_id)
                .execute()
            )
            
            # Wait for all queries to complete
            profile_resp, memories_resp, onboarding_resp = await asyncio.gather(
                profile_task,
                memories_task,
                onboarding_task,
                return_exceptions=True
            )
            
            self._total_operations += 3
            self._queries_saved += 0  # These are parallel, not sequential
            
            # Process results
            result = {
                "profile": "",
                "recent_memories": [],
                "onboarding": {},
                "memory_count": 0
            }
            
            if not isinstance(profile_resp, Exception):
                profile_data = getattr(profile_resp, "data", []) or []
                if profile_data:
                    result["profile"] = profile_data[0].get("profile_text", "")
            
            if not isinstance(memories_resp, Exception):
                memories_data = getattr(memories_resp, "data", []) or []
                result["recent_memories"] = memories_data
                result["memory_count"] = len(memories_data)
            
            if not isinstance(onboarding_resp, Exception):
                onboarding_data = getattr(onboarding_resp, "data", []) or []
                if onboarding_data:
                    result["onboarding"] = onboarding_data[0]
            
            elapsed = time.time() - start_time
            print(f"[BATCH] Prefetch completed in {elapsed:.2f}s")
            
            return result
            
        except Exception as e:
            print(f"[BATCH] Error in prefetch_user_data: {e}")
            return {}
    
    def get_stats(self) -> Dict:
        """Get batching statistics"""
        efficiency = (
            (self._queries_saved / self._total_operations * 100)
            if self._total_operations > 0
            else 0
        )
        
        return {
            "total_operations": self._total_operations,
            "queries_saved": self._queries_saved,
            "efficiency_gain": f"{efficiency:.1f}%",
            "batch_size": self._batch_size
        }


# Global database batcher instance
_db_batcher: Optional[DatabaseBatcher] = None


async def get_db_batcher(supabase_client: Optional[Client] = None) -> DatabaseBatcher:
    """Get or create the global database batcher instance"""
    global _db_batcher
    if _db_batcher is None:
        _db_batcher = DatabaseBatcher(supabase_client)
        print("[BATCH] Database batcher initialized")
    return _db_batcher


def get_db_batcher_sync() -> Optional[DatabaseBatcher]:
    """Get database batcher synchronously (if already initialized)"""
    return _db_batcher
