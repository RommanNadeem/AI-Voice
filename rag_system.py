"""
RAG (Retrieval-Augmented Generation) System for Companion Agent
================================================================

Advanced RAG with Tier 1 features for AI companion applications:

Core Features:
- Async embedding generation (non-blocking)
- In-memory FAISS index for fast retrieval
- Background processing for adding memories
- Cached embeddings to avoid redundant API calls
- Supabase integration for persistence

Tier 1 Advanced Features:
- Conversation-aware retrieval with context tracking
- Temporal filtering with time-decay scoring
- Memory importance scoring (emotional weight)
- Query expansion for intent understanding
- Context-aware re-ranking for personal relevance
"""

import asyncio
import numpy as np
import faiss
import pickle
import os
import time
import json
from typing import List, Dict, Optional, Tuple, Set
from openai import AsyncOpenAI
import logging

# RAG Configuration
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
CACHE_EMBEDDINGS = True
MAX_CACHE_SIZE = 1000

# Advanced RAG Configuration
ENABLE_QUERY_EXPANSION = True
ENABLE_TEMPORAL_FILTERING = True
ENABLE_IMPORTANCE_SCORING = True
ENABLE_CONVERSATION_CONTEXT = True
TIME_DECAY_HOURS = 24  # Memories decay over 24 hours
RECENCY_WEIGHT = 0.3  # 30% weight for recency, 70% for similarity

class RAGMemorySystem:
    """
    Advanced RAG system with Tier 1 features for AI companion.
    Designed for contextual awareness and emotional intelligence.
    """
    
    def __init__(self, user_id: str, openai_api_key: str):
        self.user_id = user_id
        self.client = AsyncOpenAI(api_key=openai_api_key)
        
        # FAISS index for vector search
        self.index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
        
        # Memory storage with enhanced metadata
        self.memories = []  # List of memory dicts with full metadata
        self.embedding_cache = {}  # {text_hash: embedding}
        
        # Tier 1: Conversation context tracking
        self.conversation_context: List[str] = []  # Recent conversation turns
        self.conversation_turns: List[Dict[str, str]] = []  # Full conversation turns with user/assistant
        self.current_topic: Optional[str] = None
        self.referenced_memories: Set[int] = set()  # Track mentioned memories
        
        # Tier 1: Importance weights by category
        self.importance_weights = {
            "GOAL": 2.0,           # Goals are highly important
            "RELATIONSHIP": 1.8,   # People matter
            "PREFERENCE": 1.5,     # User preferences
            "EXPERIENCE": 1.3,     # Life experiences
            "FACT": 1.2,           # Basic facts
            "INTEREST": 1.4,       # Interests and hobbies
            "OPINION": 1.1,        # Opinions
            "PLAN": 1.6,           # Future plans
            "GENERAL": 1.0         # Default
        }
        
        # Performance tracking
        self.stats = {
            "embeddings_created": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "retrievals": 0,
            "query_expansions": 0,
            "temporal_boosts": 0,
            "importance_boosts": 0,
            "context_matches": 0
        }
        
        logging.info(f"[RAG] Initialized Advanced RAG for user {user_id}")
    
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
    
    def update_conversation_context(self, text: str):
        """
        Tier 1: Track conversation context for better retrieval.
        
        Args:
            text: Recent conversation turn
        """
        if not ENABLE_CONVERSATION_CONTEXT:
            return
        
        self.conversation_context.append(text)
        # Keep only last 10 turns
        if len(self.conversation_context) > 10:
            self.conversation_context.pop(0)
        
        logging.debug(f"[RAG] Updated conversation context (size: {len(self.conversation_context)})")
    
    def add_conversation_turn(self, user_message: str, assistant_message: str):
        """
        Add a complete conversation turn (user + assistant) to context.
        
        Args:
            user_message: User's message
            assistant_message: Assistant's response
        """
        if not user_message or not assistant_message:
            return
        
        turn = {
            "user": user_message,
            "assistant": assistant_message,
            "timestamp": time.time()
        }
        
        self.conversation_turns.append(turn)
        # Keep only last 10 turns
        if len(self.conversation_turns) > 10:
            self.conversation_turns.pop(0)
        
        logging.debug(f"[RAG] Added conversation turn (total turns: {len(self.conversation_turns)})")
    
    def calculate_importance_score(self, memory: Dict) -> float:
        """
        Tier 1: Calculate memory importance based on category and metadata.
        
        Args:
            memory: Memory dict with category and metadata
            
        Returns:
            Importance multiplier (1.0 = baseline)
        """
        if not ENABLE_IMPORTANCE_SCORING:
            return 1.0
        
        score = 1.0
        
        # Category-based importance
        category = memory.get("category", "GENERAL")
        score *= self.importance_weights.get(category, 1.0)
        
        # Explicit importance flag
        metadata = memory.get("metadata", {})
        if metadata.get("important", False):
            score *= 1.5
        
        # Emotional content boost
        if metadata.get("emotional", False):
            score *= 1.3
        
        # User explicitly said "remember this"
        if metadata.get("explicit_save", False):
            score *= 2.0
        
        return score
    
    def calculate_temporal_score(self, timestamp: float) -> float:
        """
        Tier 1: Calculate time-decay score for temporal filtering.
        
        Args:
            timestamp: Unix timestamp of memory
            
        Returns:
            Temporal multiplier (1.0 = most recent, decays over time)
        """
        if not ENABLE_TEMPORAL_FILTERING:
            return 1.0
        
        age_hours = (time.time() - timestamp) / 3600
        
        # Exponential decay: 1.0 at 0 hours, 0.5 at TIME_DECAY_HOURS
        decay_factor = 0.5 ** (age_hours / TIME_DECAY_HOURS)
        
        return decay_factor
    
    async def expand_query(self, query: str) -> List[str]:
        """
        Tier 1: Expand query with LLM to capture user intent.
        
        Args:
            query: Original search query
            
        Returns:
            List of query variations including original
        """
        if not ENABLE_QUERY_EXPANSION or not query:
            return [query]
        
        try:
            self.stats["query_expansions"] += 1
            
            # Use LLM to generate semantic variations
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Generate 2-3 semantic variations of the search query to capture user intent. Return as JSON array."
                    },
                    {
                        "role": "user",
                        "content": f"Original query: '{query}'\n\nGenerate variations that capture the same intent with different wording."
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=100,
                timeout=3.0
            )
            
            result = json.loads(response.choices[0].message.content)
            variations = result.get("variations", [])
            
            # Always include original query first
            all_queries = [query] + variations[:2]  # Max 3 total
            
            logging.info(f"[RAG] Expanded query '{query}' to {len(all_queries)} variations")
            return all_queries
            
        except Exception as e:
            logging.warning(f"[RAG] Query expansion failed: {e}, using original")
            return [query]
    
    async def add_memory_async(self, text: str, category: str = "GENERAL", metadata: Dict = None):
        """
        Add memory to RAG system (async, non-blocking) with enhanced metadata.
        
        Args:
            text: Memory text
            category: Memory category
            metadata: Optional additional metadata (important, emotional, explicit_save, etc.)
        """
        if not text or not text.strip():
            return
        
        try:
            # Create embedding asynchronously
            embedding = await self.create_embedding(text)
            
            # Add to FAISS index
            self.index.add(embedding.reshape(1, -1))
            
            # Store memory with enhanced metadata
            memory = {
                "text": text,
                "category": category,
                "timestamp": time.time(),
                "embedding": embedding,
                "metadata": metadata or {},
                "access_count": 0,  # Track how often accessed
                "last_accessed": time.time()
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
        time_filter: Optional[Tuple[float, float]] = None,
        use_advanced_features: bool = True
    ) -> List[Dict]:
        """
        Tier 1: Advanced retrieval with context-awareness and intelligent scoring.
        
        Args:
            query: Search query
            top_k: Number of results to return
            category_filter: Optional category to filter by
            time_filter: Optional (start_time, end_time) tuple
            use_advanced_features: Enable Tier 1 features (default True)
        
        Returns:
            List of relevant memories with enhanced scores
        """
        if not self.memories:
            logging.debug("[RAG] No memories to search")
            return []
        
        try:
            self.stats["retrievals"] += 1
            
            # Tier 1: Query expansion
            queries = [query]
            if use_advanced_features:
                queries = await self.expand_query(query)
            
            # Collect all candidate results from expanded queries
            all_candidates = {}  # {memory_idx: best_similarity}
            
            for q in queries:
                # Create query embedding
                query_embedding = await self.create_embedding(q)
                
                # Search FAISS index (get more candidates for re-ranking)
                k_search = min(top_k * 4, len(self.memories))
                distances, indices = self.index.search(
                    query_embedding.reshape(1, -1), 
                    k_search
                )
                
                # Track best similarity for each memory
                for i, idx in enumerate(indices[0]):
                    if idx < 0 or idx >= len(self.memories):
                        continue
                    
                    similarity = 1 / (1 + distances[0][i])
                    
                    # Keep best score across all query variations
                    if idx not in all_candidates or similarity > all_candidates[idx]:
                        all_candidates[idx] = similarity
            
            # Build and score results
            scored_results = []
            
            for idx, base_similarity in all_candidates.items():
                memory = self.memories[idx]
                
                # Apply basic filters
                if category_filter and memory["category"] != category_filter:
                    continue
                
                if time_filter:
                    mem_time = memory["timestamp"]
                    if mem_time < time_filter[0] or mem_time > time_filter[1]:
                        continue
                
                # Tier 1: Calculate enhanced score
                final_score = base_similarity
                
                if use_advanced_features:
                    # Importance scoring
                    importance = self.calculate_importance_score(memory)
                    final_score *= importance
                    if importance > 1.0:
                        self.stats["importance_boosts"] += 1
                    
                    # Temporal scoring
                    temporal = self.calculate_temporal_score(memory["timestamp"])
                    final_score = (
                        final_score * (1 - RECENCY_WEIGHT) +  # Similarity component
                        final_score * temporal * RECENCY_WEIGHT  # Recency component
                    )
                    if temporal < 1.0:
                        self.stats["temporal_boosts"] += 1
                    
                    # Conversation context bonus
                    if self.conversation_context:
                        memory_text = memory["text"].lower()
                        for context_turn in self.conversation_context[-3:]:  # Last 3 turns
                            if any(word in memory_text for word in context_turn.lower().split()[:5]):
                                final_score *= 1.2  # 20% boost for context match
                                self.stats["context_matches"] += 1
                                break
                    
                    # Avoid recently referenced memories (diversity)
                    if idx in self.referenced_memories:
                        final_score *= 0.7  # Penalty for repetition
                
                scored_results.append({
                    "memory_idx": idx,
                    "text": memory["text"],
                    "category": memory["category"],
                    "timestamp": memory["timestamp"],
                    "similarity": float(base_similarity),
                    "final_score": float(final_score),
                    "metadata": memory.get("metadata", {})
                })
            
            # Sort by final score
            scored_results.sort(key=lambda x: x["final_score"], reverse=True)
            
            # Take top_k and mark as referenced
            results = scored_results[:top_k]
            
            if use_advanced_features:
                for result in results:
                    self.referenced_memories.add(result["memory_idx"])
                    # Update access tracking
                    memory = self.memories[result["memory_idx"]]
                    memory["access_count"] = memory.get("access_count", 0) + 1
                    memory["last_accessed"] = time.time()
                
                # Limit referenced set size
                if len(self.referenced_memories) > 20:
                    self.referenced_memories = set(list(self.referenced_memories)[-20:])
            
            # Remove internal fields from results
            for result in results:
                result.pop("memory_idx", None)
            
            logging.info(f"[RAG] Retrieved {len(results)} memories (advanced) for: {query[:50]}...")
            return results
            
        except Exception as e:
            logging.error(f"[RAG] Retrieval failed: {e}")
            return []
    
    def get_conversation_context(self) -> List[str]:
        """
        Get the current conversation context.
        
        Returns:
            List of recent conversation turns (last 10)
        """
        return self.conversation_context.copy()
    
    def get_last_conversation_turn(self) -> Optional[str]:
        """
        Get the last conversation turn.
        
        Returns:
            Last conversation turn text or None if empty
        """
        return self.conversation_context[-1] if self.conversation_context else None
    
    def get_last_complete_turn(self) -> Optional[Dict[str, str]]:
        """
        Get the last complete conversation turn (user + assistant).
        
        Returns:
            Dictionary with 'user' and 'assistant' keys or None if empty
        """
        return self.conversation_turns[-1] if self.conversation_turns else None
    
    def get_conversation_turns(self) -> List[Dict[str, str]]:
        """
        Get all conversation turns.
        
        Returns:
            List of conversation turns with user/assistant messages
        """
        return self.conversation_turns.copy()
    
    def reset_conversation_context(self):
        """Reset conversation context (e.g., new session)."""
        self.conversation_context.clear()
        self.conversation_turns.clear()
        self.referenced_memories.clear()
        self.current_topic = None
        logging.info("[RAG] Conversation context reset")
    
    def get_stats(self) -> Dict:
        """Get enhanced RAG system statistics including Tier 1 metrics."""
        total_requests = self.stats["cache_hits"] + self.stats["cache_misses"]
        
        return {
            **self.stats,
            "total_memories": len(self.memories),
            "cache_size": len(self.embedding_cache),
            "cache_hit_rate": self.stats["cache_hits"] / max(1, total_requests),
            "conversation_context_size": len(self.conversation_context),
            "referenced_memories_count": len(self.referenced_memories),
            "avg_queries_per_retrieval": self.stats["query_expansions"] / max(1, self.stats["retrievals"]),
            "temporal_boost_rate": self.stats["temporal_boosts"] / max(1, self.stats["retrievals"]),
            "importance_boost_rate": self.stats["importance_boosts"] / max(1, self.stats["retrievals"]),
            "context_match_rate": self.stats["context_matches"] / max(1, self.stats["retrievals"])
        }
    
    async def load_from_supabase(self, supabase_client, limit: int = 500):
        """
        Load recent memories from Supabase and build FAISS index.
        Uses ONLY the full UUID for querying (no prefix handling).
        
        Args:
            supabase_client: Supabase client instance
            limit: Maximum memories to load
        """
        try:
            from core.user_id import UserId, UserIdError
            
            # STRICT VALIDATION: Ensure we have a full UUID
            try:
                UserId.assert_full_uuid(self.user_id)
            except UserIdError as e:
                logging.error(f"[RAG] ❌ Invalid user_id for load_from_supabase: {e}")
                print(f"[RAG] ❌ Invalid user_id: {e}")
                return
            
            logging.info(f"[RAG] Loading memories from Supabase for user {UserId.format_for_display(self.user_id)}...")
            print(f"[DEBUG][DB] Querying memory table for user_id: {self.user_id} (full UUID), limit: {limit}")
            
            # Query using ONLY the full UUID - no prefix handling
            try:
                result = (
                    supabase_client.table("memory")
                    .select("category, key, value, created_at")
                    .eq("user_id", self.user_id)
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute()
                )
            except Exception as select_err:
                logging.error(f"[RAG] ❌ Select failed for user_id={self.user_id}: {select_err}")
                print(f"[RAG] ❌ Query failed: {select_err}")
                return
            
            if getattr(result, "error", None):
                logging.error(f"[RAG] ❌ Supabase select error: {result.error}")
                print(f"[RAG] ❌ Supabase error: {result.error}")
                return
            
            memories_data = result.data if result.data else []
            
            logging.info(f"[RAG] Loaded {len(memories_data)} memories from database")
            print(f"[DEBUG][DB] ✅ Query returned {len(memories_data)} memories from database")
            
            # DEBUG: Show sample of memories
            if memories_data:
                print(f"[DEBUG][DB] Sample memories retrieved:")
                for i, mem in enumerate(memories_data[:3], 1):
                    print(f"[DEBUG][DB]   #{i}: [{mem.get('category')}] {mem.get('value', '')[:60]}...")
            else:
                from core.user_id import UserId
                print(f"[DEBUG][DB] ⚠️  No memories found in database for user {UserId.format_for_display(self.user_id)}")
            
            # Create embeddings in parallel (batched for efficiency)
            embedding_tasks = []
            for mem in memories_data:
                text = mem.get("value", "")
                if text:
                    embedding_tasks.append(self.create_embedding(text))
            
            print(f"[DEBUG][DB] Creating embeddings for {len(embedding_tasks)} memories...")
            
            if embedding_tasks:
                embeddings = await asyncio.gather(*embedding_tasks, return_exceptions=True)
                
                print(f"[DEBUG][DB] Embeddings created: {len(embeddings)} total")
                
                # Count successful embeddings
                successful = sum(1 for e in embeddings if not isinstance(e, Exception))
                failed = len(embeddings) - successful
                print(f"[DEBUG][DB] Successful: {successful}, Failed: {failed}")
                
                # Add to FAISS index
                added_count = 0
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
                        added_count += 1
                
                logging.info(f"[RAG] ✓ Indexed {len(self.memories)} memories")
                print(f"[DEBUG][DB] ✅ Added {added_count} memories to FAISS index")
                print(f"[DEBUG][DB] Total memories in RAG: {len(self.memories)}")
                print(f"[DEBUG][DB] FAISS index size: {self.index.ntotal}")
            else:
                print(f"[DEBUG][DB] ⚠️  No embedding tasks created - no valid memory text found")
            
        except Exception as e:
            logging.error(f"[RAG] Failed to load from Supabase: {e}")
            print(f"[DEBUG][DB] ❌ Error loading from Supabase: {type(e).__name__}: {str(e)}")
            import traceback
            print(f"[DEBUG][DB] Traceback: {traceback.format_exc()}")
    
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
    """
    Get existing RAG system or create new one for user.
    Validates that user_id is a full UUID.
    """
    from core.user_id import UserId, UserIdError
    
    # STRICT VALIDATION: Ensure full UUID
    try:
        UserId.assert_full_uuid(user_id)
    except UserIdError as e:
        print(f"[RAG] ❌ CRITICAL: Invalid user_id: {e}")
        raise
    
    print(f"[DEBUG][RAG] get_or_create_rag called for user {UserId.format_for_display(user_id)}")
    print(f"[DEBUG][RAG] Current user_rag_systems keys: {[UserId.format_for_display(uid) for uid in user_rag_systems.keys()]}")
    
    if user_id not in user_rag_systems:
        print(f"[DEBUG][RAG] 🆕 Creating NEW RAG instance for {UserId.format_for_display(user_id)}")
        user_rag_systems[user_id] = RAGMemorySystem(user_id, openai_api_key)
        print(f"[DEBUG][RAG] ✅ RAG instance created and stored in global dict")
    else:
        existing_rag = user_rag_systems[user_id]
        print(f"[DEBUG][RAG] ♻️  Returning EXISTING RAG for {UserId.format_for_display(user_id)}")
        print(f"[DEBUG][RAG]    Existing RAG has {len(existing_rag.memories)} memories")
        print(f"[DEBUG][RAG]    FAISS index size: {existing_rag.index.ntotal}")
    
    return user_rag_systems[user_id]
