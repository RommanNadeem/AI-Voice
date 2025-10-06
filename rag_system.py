"""
RAG (Retrieval-Augmented Generation) System for Companion Agent
================================================================

High-performance semantic memory retrieval using FAISS vector database.
Optimized for zero-latency impact with async processing and caching.

Features:
- Async embedding generation (non-blocking)
- In-memory FAISS index for fast retrieval
- Background processing for adding memories
- Cached embeddings to avoid redundant API calls
- Supabase integration for persistence
"""

import asyncio
import numpy as np
import faiss
import pickle
import os
import time
from typing import List, Dict, Optional, Tuple
from openai import AsyncOpenAI
import logging

# RAG Configuration
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
CACHE_EMBEDDINGS = True
MAX_CACHE_SIZE = 1000

class RAGMemorySystem:
    """
    High-performance RAG system with FAISS vector database.
    Designed for zero-latency impact on conversation.
    """
    
    def __init__(self, user_id: str, openai_api_key: str):
        self.user_id = user_id
        self.client = AsyncOpenAI(api_key=openai_api_key)
        
        # FAISS index for vector search
        self.index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
        
        # Memory storage
        self.memories = []  # List of {"text": str, "category": str, "timestamp": float, "embedding": np.array}
        self.embedding_cache = {}  # {text_hash: embedding} - avoid duplicate API calls
        
        # Performance tracking
        self.stats = {
            "embeddings_created": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "retrievals": 0
        }
        
        logging.info(f"[RAG] Initialized for user {user_id}")
    
    async def create_embedding(self, text: str, use_cache: bool = True) -> np.ndarray:
        """
        Create embedding for text with caching.
        
        Args:
            text: Text to embed
            use_cache: Whether to use cache (default True)
        
        Returns:
            Numpy array of embedding vector
        """
        if not text or not text.strip():
            return np.zeros(EMBEDDING_DIMENSION)
        
        # Check cache
        text_hash = hash(text)
        if use_cache and CACHE_EMBEDDINGS and text_hash in self.embedding_cache:
            self.stats["cache_hits"] += 1
            logging.debug(f"[RAG] Cache hit for text: {text[:50]}...")
            return self.embedding_cache[text_hash]
        
        # Create embedding
        try:
            self.stats["cache_misses"] += 1
            response = await self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text,
                timeout=5.0  # Fast timeout
            )
            
            embedding = np.array(response.data[0].embedding, dtype=np.float32)
            
            # Cache it
            if use_cache and CACHE_EMBEDDINGS:
                # Limit cache size
                if len(self.embedding_cache) >= MAX_CACHE_SIZE:
                    # Remove oldest entry (simple FIFO)
                    self.embedding_cache.pop(next(iter(self.embedding_cache)))
                self.embedding_cache[text_hash] = embedding
            
            self.stats["embeddings_created"] += 1
            logging.debug(f"[RAG] Created embedding for: {text[:50]}...")
            return embedding
            
        except Exception as e:
            logging.error(f"[RAG] Embedding creation failed: {e}")
            return np.zeros(EMBEDDING_DIMENSION)
    
    async def add_memory_async(self, text: str, category: str = "GENERAL", metadata: Dict = None):
        """
        Add memory to RAG system (async, non-blocking).
        
        Args:
            text: Memory text
            category: Memory category
            metadata: Optional additional metadata
        """
        if not text or not text.strip():
            return
        
        try:
            # Create embedding asynchronously
            embedding = await self.create_embedding(text)
            
            # Add to FAISS index
            self.index.add(embedding.reshape(1, -1))
            
            # Store memory with metadata
            memory = {
                "text": text,
                "category": category,
                "timestamp": time.time(),
                "embedding": embedding,
                "metadata": metadata or {}
            }
            self.memories.append(memory)
            
            logging.info(f"[RAG] Added memory: [{category}] {text[:50]}...")
            
        except Exception as e:
            logging.error(f"[RAG] Failed to add memory: {e}")
    
    def add_memory_background(self, text: str, category: str = "GENERAL", metadata: Dict = None):
        """
        Add memory in background (fire-and-forget, zero latency).
        
        Args:
            text: Memory text
            category: Memory category
            metadata: Optional metadata
        """
        asyncio.create_task(self.add_memory_async(text, category, metadata))
    
    async def retrieve_relevant_memories(
        self, 
        query: str, 
        top_k: int = 5,
        category_filter: Optional[str] = None,
        time_filter: Optional[Tuple[float, float]] = None
    ) -> List[Dict]:
        """
        Retrieve semantically relevant memories.
        
        Args:
            query: Search query
            top_k: Number of results to return
            category_filter: Optional category to filter by
            time_filter: Optional (start_time, end_time) tuple
        
        Returns:
            List of relevant memories with scores
        """
        if not self.memories:
            logging.debug("[RAG] No memories to search")
            return []
        
        try:
            self.stats["retrievals"] += 1
            
            # Create query embedding
            query_embedding = await self.create_embedding(query)
            
            # Search FAISS index
            distances, indices = self.index.search(
                query_embedding.reshape(1, -1), 
                min(top_k * 2, len(self.memories))  # Get more for filtering
            )
            
            # Build results
            results = []
            for i, idx in enumerate(indices[0]):
                if idx < 0 or idx >= len(self.memories):
                    continue
                
                memory = self.memories[idx]
                
                # Apply filters
                if category_filter and memory["category"] != category_filter:
                    continue
                
                if time_filter:
                    mem_time = memory["timestamp"]
                    if mem_time < time_filter[0] or mem_time > time_filter[1]:
                        continue
                
                # Calculate similarity score (L2 distance to similarity)
                similarity = 1 / (1 + distances[0][i])
                
                results.append({
                    "text": memory["text"],
                    "category": memory["category"],
                    "timestamp": memory["timestamp"],
                    "similarity": float(similarity),
                    "metadata": memory.get("metadata", {})
                })
                
                if len(results) >= top_k:
                    break
            
            logging.info(f"[RAG] Retrieved {len(results)} memories for query: {query[:50]}...")
            return results
            
        except Exception as e:
            logging.error(f"[RAG] Retrieval failed: {e}")
            return []
    
    def get_stats(self) -> Dict:
        """Get RAG system statistics."""
        return {
            **self.stats,
            "total_memories": len(self.memories),
            "cache_size": len(self.embedding_cache),
            "cache_hit_rate": self.stats["cache_hits"] / max(1, self.stats["cache_hits"] + self.stats["cache_misses"])
        }
    
    async def load_from_supabase(self, supabase_client, limit: int = 500):
        """
        Load recent memories from Supabase and build FAISS index.
        
        Args:
            supabase_client: Supabase client instance
            limit: Maximum memories to load
        """
        try:
            logging.info(f"[RAG] Loading memories from Supabase for user {self.user_id}...")
            
            # Fetch recent memories
            result = supabase_client.table("memory")\
                .select("category, key, value, created_at")\
                .eq("user_id", self.user_id)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            memories_data = result.data if result.data else []
            logging.info(f"[RAG] Loaded {len(memories_data)} memories from database")
            
            # Create embeddings in parallel (batched for efficiency)
            embedding_tasks = []
            for mem in memories_data:
                text = mem.get("value", "")
                if text:
                    embedding_tasks.append(self.create_embedding(text))
            
            if embedding_tasks:
                embeddings = await asyncio.gather(*embedding_tasks, return_exceptions=True)
                
                # Add to FAISS index
                for i, mem in enumerate(memories_data):
                    if i < len(embeddings) and not isinstance(embeddings[i], Exception):
                        embedding = embeddings[i]
                        
                        # Add to index
                        self.index.add(embedding.reshape(1, -1))
                        
                        # Store memory
                        self.memories.append({
                            "text": mem.get("value", ""),
                            "category": mem.get("category", "GENERAL"),
                            "timestamp": time.time(),  # Use current time or parse created_at
                            "embedding": embedding,
                            "metadata": {"key": mem.get("key")}
                        })
                
                logging.info(f"[RAG] ✓ Indexed {len(self.memories)} memories")
            
        except Exception as e:
            logging.error(f"[RAG] Failed to load from Supabase: {e}")
    
    def save_index(self, filepath: str):
        """Save FAISS index and memories to disk."""
        try:
            # Save FAISS index
            faiss.write_index(self.index, f"{filepath}.faiss")
            
            # Save memories (without embeddings to save space)
            memories_to_save = [
                {k: v for k, v in m.items() if k != "embedding"}
                for m in self.memories
            ]
            with open(f"{filepath}.pkl", "wb") as f:
                pickle.dump({
                    "memories": memories_to_save,
                    "stats": self.stats
                }, f)
            
            logging.info(f"[RAG] Saved index to {filepath}")
        except Exception as e:
            logging.error(f"[RAG] Failed to save index: {e}")
    
    def load_index(self, filepath: str):
        """Load FAISS index and memories from disk."""
        try:
            # Load FAISS index
            self.index = faiss.read_index(f"{filepath}.faiss")
            
            # Load memories
            with open(f"{filepath}.pkl", "rb") as f:
                data = pickle.load(f)
                self.memories = data.get("memories", [])
                self.stats = data.get("stats", self.stats)
            
            logging.info(f"[RAG] Loaded {len(self.memories)} memories from {filepath}")
        except Exception as e:
            logging.warning(f"[RAG] Could not load index: {e}")


# Global RAG instance (initialized per user)
user_rag_systems = {}  # {user_id: RAGMemorySystem}

def get_or_create_rag(user_id: str, openai_api_key: str) -> RAGMemorySystem:
    """Get existing RAG system or create new one for user."""
    if user_id not in user_rag_systems:
        user_rag_systems[user_id] = RAGMemorySystem(user_id, openai_api_key)
    return user_rag_systems[user_id]
