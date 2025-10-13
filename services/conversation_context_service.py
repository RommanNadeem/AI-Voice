"""
Conversation Context Service - Automatic Context Injection
===========================================================
Provides automatic, fast, and reliable conversation context without requiring AI tool calls.

Features:
- In-memory session cache for instant access
- Redis caching for cross-session persistence
- Batched database queries for efficiency
- Automatic context injection into every AI response
- No manual tool calls required

Benefits:
- Faster: Context available instantly from memory
- Reliable: Always has context, no risk of AI forgetting to call tools
- Efficient: Multi-layer caching reduces database load
- Automatic: Context injected without AI intervention
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from supabase import Client
from core.user_id import UserId, UserIdError
from infrastructure.redis_cache import get_redis_cache
from infrastructure.database_batcher import get_db_batcher


class ConversationContextService:
    """
    Manages conversation context with multi-layer caching for optimal performance.
    
    Context Layers:
    1. Session Cache (in-memory) - Instant access, cleared on session end
    2. Redis Cache - Fast cross-session persistence (30 min TTL)
    3. Database - Source of truth, batch-optimized queries
    """
    
    def __init__(self, supabase_client: Optional[Client] = None):
        self.supabase = supabase_client
        
        # Layer 1: In-memory session cache (fastest)
        self._session_cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_ttl = 900  # 15 minutes for session cache (increased from 5 min)
        
        # Statistics
        self._session_hits = 0
        self._redis_hits = 0
        self._db_hits = 0
        self._total_requests = 0
    
    async def get_context(self, user_id: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get comprehensive conversation context with multi-layer caching.
        
        Args:
            user_id: User UUID
            force_refresh: Skip caches and fetch fresh data
            
        Returns:
            Dict containing:
            - user_profile: User profile text
            - conversation_state: Current stage and trust score
            - recent_memories: Last 10 important memories
            - onboarding_data: User preferences and goals
            - last_conversation: Recent conversation context
            - rag_context: Relevant memories from RAG (if available)
        """
        self._total_requests += 1
        cache_key = f"context:{user_id}"
        
        # Layer 1: Check session cache (in-memory)
        if not force_refresh:
            cached = self._get_from_session_cache(cache_key)
            if cached:
                self._session_hits += 1
                print(f"[CONTEXT] ✓ Session cache hit ({self._get_hit_rate()}% hit rate)")
                return cached
        
        # Layer 2: Check Redis cache
        if not force_refresh:
            try:
                redis_cache = await get_redis_cache()
                cached = await redis_cache.get(cache_key)
                if cached:
                    self._redis_hits += 1
                    # Store in session cache for next time
                    self._store_in_session_cache(cache_key, cached)
                    print(f"[CONTEXT] ✓ Redis cache hit ({self._get_hit_rate()}% hit rate)")
                    return cached
            except Exception as e:
                print(f"[CONTEXT] Redis check failed: {e}")
        
        # Layer 3: Fetch from database with batching
        self._db_hits += 1
        print(f"[CONTEXT] Fetching from database...")
        start_time = time.time()
        
        context = await self._fetch_from_database(user_id)
        
        elapsed = time.time() - start_time
        print(f"[CONTEXT] ✓ Database fetch completed in {elapsed:.2f}s")
        
        # Store in both caches
        self._store_in_session_cache(cache_key, context)
        
        try:
            redis_cache = await get_redis_cache()
            await redis_cache.set(cache_key, context, ttl=1800)  # 30 minutes
        except Exception as e:
            print(f"[CONTEXT] Redis cache store failed: {e}")
        
        return context
    
    async def _fetch_from_database(self, user_id: str) -> Dict[str, Any]:
        """
        Fetch all context from database using parallel batched queries.
        OPTIMIZED: Prioritizes critical data and uses timeouts.
        """
        if not self.supabase:
            return self._get_empty_context()
        
        try:
            # OPTIMIZATION: Use parallel execution with timeout for faster failures
            tasks = [
                self._fetch_user_profile(user_id),
                self._fetch_conversation_state(user_id),
                self._fetch_recent_memories(user_id),
                self._fetch_onboarding_data(user_id),
                self._fetch_last_conversation(user_id),
                self._fetch_user_name(user_id),  # Fetch name specifically
                self._fetch_user_gender(user_id),  # Fetch gender from memory
            ]
            
            # Add timeout to prevent slow queries from blocking
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=2.0  # Max 2 seconds for all queries
            )
            
            # Unpack results
            profile = results[0] if not isinstance(results[0], Exception) else ""
            state = results[1] if not isinstance(results[1], Exception) else self._get_default_state()
            memories = results[2] if not isinstance(results[2], Exception) else []
            onboarding = results[3] if not isinstance(results[3], Exception) else {}
            last_conv = results[4] if not isinstance(results[4], Exception) else {}
            user_name = results[5] if not isinstance(results[5], Exception) else None
            user_gender = results[6] if not isinstance(results[6], Exception) else None
            
            return {
                "user_profile": profile,
                "conversation_state": state,
                "recent_memories": memories,
                "onboarding_data": onboarding,
                "last_conversation": last_conv,
                "user_name": user_name,  # Add name separately
                "user_gender": user_gender,  # Add gender separately
                "fetched_at": datetime.utcnow().isoformat(),
            }
        except asyncio.TimeoutError:
            print(f"[CONTEXT] ⚠️  Database fetch timeout (>2s), returning cached or empty")
            # Try to return stale cache if available
            cache_key = f"context:{user_id}"
            if cache_key in self._session_cache:
                print(f"[CONTEXT] Using stale cache due to timeout")
                return self._session_cache[cache_key]
            return self._get_empty_context()
        except Exception as e:
            print(f"[CONTEXT] Error fetching context: {e}")
            return self._get_empty_context()
    
    async def _fetch_user_name(self, user_id: str) -> Optional[str]:
        """
        Fetch user's name ONLY from onboarding_details table.
        🔥 FIX: Always use onboarding table as the source of truth for names.
        """
        try:
            print(f"[CONTEXT SERVICE] 🔍 Fetching user's name from onboarding_details for {UserId.format_for_display(user_id)}...")
            
            # 🔥 ALWAYS use onboarding_details table for names
            onboarding_result = await asyncio.to_thread(
                lambda: self.supabase.table("onboarding_details")
                .select("full_name")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            if onboarding_result.data:
                name = onboarding_result.data[0].get("full_name", None)
                if name:
                    print(f"[CONTEXT SERVICE] ✅ User's name found in onboarding_details: '{name}'")
                    return name
            
            print(f"[CONTEXT SERVICE] ℹ️  User's name not found in onboarding_details")
            return None
        except Exception as e:
            print(f"[CONTEXT SERVICE] ❌ Name fetch error: {e}")
            return None
    
    async def _fetch_user_gender(self, user_id: str) -> Optional[str]:
        """
        Fetch user's gender from memory table.
        """
        try:
            print(f"[CONTEXT SERVICE] 🔍 Fetching user's gender from memory for {UserId.format_for_display(user_id)}...")
            
            # Fetch gender from memory table
            gender_result = await asyncio.to_thread(
                lambda: self.supabase.table("memory")
                .select("value")
                .eq("user_id", user_id)
                .eq("category", "FACT")
                .eq("key", "gender")
                .limit(1)
                .execute()
            )
            if gender_result.data:
                gender = gender_result.data[0].get("value", None)
                if gender:
                    print(f"[CONTEXT SERVICE] ✅ User's gender found in memory: '{gender}'")
                    return gender
            
            print(f"[CONTEXT SERVICE] ℹ️  User's gender not found in memory")
            return None
        except Exception as e:
            print(f"[CONTEXT SERVICE] ❌ Gender fetch error: {e}")
            return None
    
    async def _fetch_user_profile(self, user_id: str) -> str:
        """Fetch user profile"""
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("user_profiles")
                .select("profile_text")
                .eq("user_id", user_id)
                .execute()
            )
            if result.data:
                return result.data[0].get("profile_text", "")
            return ""
        except Exception as e:
            print(f"[CONTEXT] Profile fetch error: {e}")
            return ""
    
    async def _fetch_conversation_state(self, user_id: str) -> Dict[str, Any]:
        """Fetch conversation state"""
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("conversation_state")
                .select("stage, trust_score, updated_at")
                .eq("user_id", user_id)
                .execute()
            )
            if result.data:
                return result.data[0]
            return self._get_default_state()
        except Exception as e:
            print(f"[CONTEXT] State fetch error: {e}")
            return self._get_default_state()
    
    async def _fetch_recent_memories(self, user_id: str, limit: int = 10) -> List[Dict]:
        """
        Fetch recent important memories with priority for critical info.
        Prioritizes: name, preferences, goals, then recent memories.
        """
        try:
            # First, get critical memories (name, preferences)
            critical_result = await asyncio.to_thread(
                lambda: self.supabase.table("memory")
                .select("category, key, value, created_at")
                .eq("user_id", user_id)
                .in_("category", ["FACT", "PREFERENCE", "PRESENTATION"])
                .order("created_at", desc=True)
                .limit(5)
                .execute()
            )
            
            # Then get recent memories
            recent_result = await asyncio.to_thread(
                lambda: self.supabase.table("memory")
                .select("category, key, value, created_at")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            
            # Combine and deduplicate
            critical_memories = critical_result.data or []
            recent_memories = recent_result.data or []
            
            # Create a dict to deduplicate by key
            memory_dict = {}
            
            # Add critical memories first (higher priority)
            for mem in critical_memories:
                key = f"{mem['category']}:{mem['key']}"
                memory_dict[key] = mem
            
            # Add recent memories
            for mem in recent_memories:
                key = f"{mem['category']}:{mem['key']}"
                if key not in memory_dict:
                    memory_dict[key] = mem
            
            # Return as list, limit to specified amount
            return list(memory_dict.values())[:limit]
            
        except Exception as e:
            print(f"[CONTEXT] Memories fetch error: {e}")
            return []
    
    async def _fetch_onboarding_data(self, user_id: str) -> Dict[str, Any]:
        """Fetch onboarding preferences and goals"""
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("onboarding_details")
                .select("*")
                .eq("user_id", user_id)
                .execute()
            )
            if result.data:
                return result.data[0]
            return {}
        except Exception as e:
            print(f"[CONTEXT] Onboarding fetch error: {e}")
            return {}
    
    async def _fetch_last_conversation(self, user_id: str) -> Dict[str, Any]:
        """Fetch last conversation context"""
        try:
            # Get last 5 messages
            result = await asyncio.to_thread(
                lambda: self.supabase.table("memory")
                .select("value, created_at")
                .eq("user_id", user_id)
                .not_.like("key", "user_input_%")
                .order("created_at", desc=True)
                .limit(5)
                .execute()
            )
            
            if not result.data:
                return {"has_history": False}
            
            messages = [m["value"] for m in result.data]
            last_msg_time = result.data[0]["created_at"]
            
            # Calculate time since last message
            try:
                last_time = datetime.fromisoformat(last_msg_time.replace("Z", "+00:00"))
                hours_since = (datetime.now(last_time.tzinfo) - last_time).total_seconds() / 3600
            except:
                hours_since = 999
            
            return {
                "has_history": True,
                "last_messages": messages,
                "time_since_last_hours": hours_since,
                "last_message_time": last_msg_time,
            }
        except Exception as e:
            print(f"[CONTEXT] Last conversation fetch error: {e}")
            return {"has_history": False}
    
    def _get_from_session_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get from in-memory session cache"""
        if key in self._session_cache:
            # Check if expired
            timestamp = self._cache_timestamps.get(key, 0)
            if time.time() - timestamp < self._cache_ttl:
                return self._session_cache[key]
            else:
                # Expired, remove
                del self._session_cache[key]
                del self._cache_timestamps[key]
        return None
    
    def _store_in_session_cache(self, key: str, value: Dict[str, Any]):
        """Store in in-memory session cache"""
        self._session_cache[key] = value
        self._cache_timestamps[key] = time.time()
    
    def clear_session_cache(self):
        """Clear in-memory session cache"""
        self._session_cache.clear()
        self._cache_timestamps.clear()
        print("[CONTEXT] Session cache cleared")
    
    async def invalidate_cache(self, user_id: str):
        """Invalidate all cached context for a user"""
        cache_key = f"context:{user_id}"
        
        # Clear session cache
        if cache_key in self._session_cache:
            del self._session_cache[cache_key]
            del self._cache_timestamps[cache_key]
        
        # Clear Redis cache
        try:
            redis_cache = await get_redis_cache()
            await redis_cache.delete(cache_key)
        except Exception as e:
            print(f"[CONTEXT] Redis invalidation failed: {e}")
        
        print(f"[CONTEXT] Cache invalidated for user {user_id}")
    
    def _get_empty_context(self) -> Dict[str, Any]:
        """Return empty context structure"""
        return {
            "user_profile": "",
            "conversation_state": self._get_default_state(),
            "recent_memories": [],
            "onboarding_data": {},
            "last_conversation": {"has_history": False},
            "user_name": None,
            "fetched_at": datetime.utcnow().isoformat(),
        }
    
    def _get_default_state(self) -> Dict[str, Any]:
        """Return default conversation state"""
        return {
            "stage": "ORIENTATION",
            "trust_score": 5.0,
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    def _get_hit_rate(self) -> float:
        """Calculate overall cache hit rate"""
        if self._total_requests == 0:
            return 0.0
        hits = self._session_hits + self._redis_hits
        return (hits / self._total_requests) * 100
    
    def get_stats(self) -> Dict[str, Any]:
        """Get context service statistics"""
        return {
            "total_requests": self._total_requests,
            "session_cache_hits": self._session_hits,
            "redis_cache_hits": self._redis_hits,
            "database_hits": self._db_hits,
            "hit_rate": f"{self._get_hit_rate():.1f}%",
            "session_cache_size": len(self._session_cache),
        }

