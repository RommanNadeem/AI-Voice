import asyncio
import json
import os
import time
from typing import Any, Dict, Optional
import redis.asyncio as redis

# Redis Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "true").lower() == "true"


class RedisCache:
    """
    Redis caching layer with connection pooling and automatic fallback.
    Provides distributed caching for improved performance and scalability.
    """
    
    def __init__(self, redis_url: str = REDIS_URL, enabled: bool = REDIS_ENABLED):
        self.redis_url = redis_url
        self.enabled = enabled
        self._client: Optional[redis.Redis] = None
        self._lock = asyncio.Lock()
        self._connection_errors = 0
        self._total_requests = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._last_health_check = 0
        
    async def initialize(self):
        """Initialize Redis connection with connection pooling"""
        if not self.enabled:
            print("[REDIS] Caching disabled via configuration")
            return
        
        try:
            print(f"[REDIS] Connecting to {self.redis_url}...")
            
            # Create Redis client with connection pooling
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,  # Connection pool size
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            
            # Test connection
            await self._client.ping()
            print("[REDIS] ✓ Connected successfully with connection pooling")
            
        except Exception as e:
            print(f"[REDIS] Warning: Connection failed: {e}")
            print("[REDIS] Continuing without Redis caching (fallback to in-memory)")
            self.enabled = False
            self._client = None
    
    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from Redis cache with automatic deserialization.
        Falls back to default if Redis is unavailable.
        
        Args:
            key: Cache key
            default: Default value if key not found
            
        Returns:
            Cached value or default
        """
        if not self.enabled or not self._client:
            return default
        
        try:
            self._total_requests += 1
            value = await self._client.get(key)
            
            if value is None:
                self._cache_misses += 1
                return default
            
            self._cache_hits += 1
            
            # Try to deserialize JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
                
        except Exception as e:
            self._connection_errors += 1
            print(f"[REDIS] Get error for key '{key}': {e}")
            return default
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        nx: bool = False,
        xx: bool = False
    ) -> bool:
        """
        Set value in Redis cache with automatic serialization.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None = no expiration)
            nx: Only set if key doesn't exist
            xx: Only set if key exists
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self._client:
            return False
        
        try:
            # Serialize complex objects to JSON
            if isinstance(value, (dict, list, tuple)):
                value = json.dumps(value)
            elif not isinstance(value, (str, int, float, bool)):
                value = json.dumps(str(value))
            
            result = await self._client.set(
                key, 
                value, 
                ex=ttl,
                nx=nx,
                xx=xx
            )
            
            return bool(result)
            
        except Exception as e:
            self._connection_errors += 1
            print(f"[REDIS] Set error for key '{key}': {e}")
            return False
    
    async def delete(self, *keys: str) -> int:
        """
        Delete one or more keys from Redis.
        
        Args:
            *keys: Keys to delete
            
        Returns:
            Number of keys deleted
        """
        if not self.enabled or not self._client:
            return 0
        
        try:
            return await self._client.delete(*keys)
        except Exception as e:
            self._connection_errors += 1
            print(f"[REDIS] Delete error: {e}")
            return 0
    
    async def exists(self, *keys: str) -> int:
        """
        Check if keys exist in Redis.
        
        Args:
            *keys: Keys to check
            
        Returns:
            Number of keys that exist
        """
        if not self.enabled or not self._client:
            return 0
        
        try:
            return await self._client.exists(*keys)
        except Exception as e:
            print(f"[REDIS] Exists error: {e}")
            return 0
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for a key"""
        if not self.enabled or not self._client:
            return False
        
        try:
            return await self._client.expire(key, seconds)
        except Exception as e:
            print(f"[REDIS] Expire error: {e}")
            return False
    
    async def ttl(self, key: str) -> int:
        """Get remaining TTL for a key"""
        if not self.enabled or not self._client:
            return -2
        
        try:
            return await self._client.ttl(key)
        except Exception as e:
            print(f"[REDIS] TTL error: {e}")
            return -2
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.
        Useful for bulk cache invalidation.
        
        Args:
            pattern: Redis pattern (e.g., "user:123:*")
            
        Returns:
            Number of keys deleted
        """
        if not self.enabled or not self._client:
            return 0
        
        try:
            keys = []
            async for key in self._client.scan_iter(match=pattern, count=100):
                keys.append(key)
            
            if keys:
                return await self._client.delete(*keys)
            return 0
            
        except Exception as e:
            self._connection_errors += 1
            print(f"[REDIS] Invalidate pattern error: {e}")
            return 0
    
    async def clear_user_cache(self, user_id: str) -> int:
        """Clear all cache entries for a specific user"""
        return await self.invalidate_pattern(f"user:{user_id}:*")
    
    async def get_stats(self) -> Dict:
        """Get Redis cache statistics"""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0
        
        stats = {
            "enabled": self.enabled,
            "connected": self._client is not None,
            "total_requests": self._total_requests,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "connection_errors": self._connection_errors,
        }
        
        if self._client:
            try:
                info = await self._client.info("stats")
                stats.update({
                    "redis_keys": info.get("keyspace_keys", 0),
                    "redis_memory": info.get("used_memory_human", "N/A"),
                })
            except Exception as e:
                print(f"[REDIS] Stats error: {e}")
        
        return stats
    
    async def health_check(self) -> bool:
        """Check Redis connection health"""
        if not self.enabled or not self._client:
            return False
        
        try:
            await self._client.ping()
            self._last_health_check = time.time()
            return True
        except Exception as e:
            print(f"[REDIS] Health check failed: {e}")
            return False
    
    async def close(self):
        """Close Redis connection"""
        if self._client:
            try:
                await self._client.close()
                print("[REDIS] ✓ Connection closed")
            except Exception as e:
                print(f"[REDIS] Close error: {e}")


# Global Redis cache instance
_redis_cache: Optional[RedisCache] = None


async def get_redis_cache() -> RedisCache:
    """Get or create the global Redis cache instance"""
    global _redis_cache
    if _redis_cache is None:
        _redis_cache = RedisCache()
        await _redis_cache.initialize()
    return _redis_cache


def get_redis_cache_sync() -> Optional[RedisCache]:
    """Get Redis cache synchronously (if already initialized)"""
    return _redis_cache
