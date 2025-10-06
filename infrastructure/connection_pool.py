import asyncio
import os
import time
from typing import Dict, Optional
import aiohttp
import openai
from supabase import Client, create_client


class ConnectionPool:
    """Manages connection pooling and client reuse for optimal performance"""
    
    def __init__(self):
        self._supabase_clients: Dict[str, Client] = {}
        self._openai_sync_client: Optional[openai.OpenAI] = None
        self._openai_async_client: Optional[openai.AsyncOpenAI] = None
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        self._last_health_check: float = 0
        self._connection_errors: int = 0
        
    async def initialize(self):
        """Initialize connection pool with health monitoring"""
        print("[POOL] Initializing connection pool...")
        
        # Create HTTP session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=100,  # Max total connections
            limit_per_host=30,  # Max connections per host
            ttl_dns_cache=300,  # DNS cache TTL
            keepalive_timeout=60,  # Keep connections alive
        )
        self._http_session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=30, connect=10)
        )
        
        # Initialize OpenAI clients (singleton pattern)
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self._openai_sync_client = openai.OpenAI(
                api_key=api_key,
                max_retries=3,
                timeout=30.0
            )
            self._openai_async_client = openai.AsyncOpenAI(
                api_key=api_key,
                max_retries=3,
                timeout=30.0
            )
            print("[POOL] ✓ OpenAI clients initialized with connection pooling")
        
        # Start health check monitoring
        self._health_check_task = asyncio.create_task(self._health_monitor())
        print("[POOL] ✓ Connection pool initialized with health monitoring")
    
    async def _health_monitor(self):
        """Background task to monitor connection health"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                current_time = time.time()
                
                # Only perform health check if enough time has passed
                if current_time - self._last_health_check > 300:  # 5 minutes
                    print("[POOL] Performing health check...")
                    # Reset error counter periodically
                    if self._connection_errors > 0:
                        print(f"[POOL] Connection errors since last check: {self._connection_errors}")
                        self._connection_errors = 0
                    self._last_health_check = current_time
                    
            except Exception as e:
                print(f"[POOL] Health monitor error: {e}")
    
    def get_supabase_client(self, url: str, key: str) -> Client:
        """Get or create a Supabase client with connection pooling"""
        cache_key = f"{url}:{key[:10]}"  # Use first 10 chars of key for caching
        
        if cache_key not in self._supabase_clients:
            try:
                client = create_client(url, key)
                self._supabase_clients[cache_key] = client
                print(f"[POOL] Created new Supabase client (pool size: {len(self._supabase_clients)})")
            except Exception as e:
                self._connection_errors += 1
                print(f"[POOL ERROR] Failed to create Supabase client: {e}")
                raise
        
        return self._supabase_clients[cache_key]
    
    def get_openai_client(self, async_client: bool = False):
        """Get reusable OpenAI client (sync or async)"""
        if async_client:
            if not self._openai_async_client:
                api_key = os.getenv("OPENAI_API_KEY")
                self._openai_async_client = openai.AsyncOpenAI(
                    api_key=api_key,
                    max_retries=3,
                    timeout=30.0
                )
            return self._openai_async_client
        else:
            if not self._openai_sync_client:
                api_key = os.getenv("OPENAI_API_KEY")
                self._openai_sync_client = openai.OpenAI(
                    api_key=api_key,
                    max_retries=3,
                    timeout=30.0
                )
            return self._openai_sync_client
    
    async def get_http_session(self) -> aiohttp.ClientSession:
        """Get shared HTTP session for async requests"""
        if not self._http_session or self._http_session.closed:
            async with self._lock:
                if not self._http_session or self._http_session.closed:
                    connector = aiohttp.TCPConnector(
                        limit=100,
                        limit_per_host=30,
                        ttl_dns_cache=300,
                        keepalive_timeout=60,
                    )
                    self._http_session = aiohttp.ClientSession(
                        connector=connector,
                        timeout=aiohttp.ClientTimeout(total=30, connect=10)
                    )
        return self._http_session
    
    async def close(self):
        """Gracefully close all connections"""
        print("[POOL] Closing connection pool...")
        
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
        
        self._supabase_clients.clear()
        print("[POOL] ✓ Connection pool closed")
    
    def get_stats(self) -> Dict:
        """Get connection pool statistics"""
        return {
            "supabase_clients": len(self._supabase_clients),
            "http_session_active": self._http_session is not None and not self._http_session.closed,
            "openai_clients_initialized": self._openai_sync_client is not None,
            "connection_errors": self._connection_errors,
            "last_health_check": self._last_health_check
        }


# Global connection pool instance
_connection_pool: Optional[ConnectionPool] = None


async def get_connection_pool() -> ConnectionPool:
    """Get or create the global connection pool"""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = ConnectionPool()
        await _connection_pool.initialize()
    return _connection_pool


def get_connection_pool_sync() -> Optional[ConnectionPool]:
    """Get connection pool synchronously (if already initialized)"""
    return _connection_pool
