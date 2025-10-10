"""
RAG Service - Wrapper for RAG memory system operations
"""

import asyncio
from typing import List, Dict, Optional, Tuple
from rag_system import get_or_create_rag, RAGMemorySystem
from core.config import Config
from core.validators import get_current_user_id


class RAGService:
    """Service for RAG (Retrieval-Augmented Generation) operations"""
    
    def __init__(self, user_id: Optional[str] = None):
        self.user_id = user_id or get_current_user_id()
        self.rag_system: Optional[RAGMemorySystem] = None
    
    def get_rag_system(self) -> RAGMemorySystem:
        """Get or create RAG system for current user"""
        if not self.rag_system and self.user_id:
            self.rag_system = get_or_create_rag(self.user_id, Config.OPENAI_API_KEY)
        return self.rag_system
    
    async def add_memory(self, text: str, category: str = "GENERAL", metadata: Dict = None):
        """
        Add memory to RAG system (async).
        
        Args:
            text: Memory text
            category: Memory category
            metadata: Optional metadata dict
        """
        rag = self.get_rag_system()
        if rag:
            await rag.add_memory_async(text, category, metadata)
    
    # Backward-compatible alias used by call sites
    async def add_memory_async(self, text: str, category: str = "GENERAL", metadata: Dict = None):
        """Compatibility wrapper for older call sites that expect add_memory_async."""
        await self.add_memory(text, category, metadata)
    
    def add_memory_background(self, text: str, category: str = "GENERAL", metadata: Dict = None):
        """
        Add memory in background (fire-and-forget, zero latency).
        
        Args:
            text: Memory text
            category: Memory category
            metadata: Optional metadata dict
        """
        rag = self.get_rag_system()
        if rag:
            rag.add_memory_background(text, category, metadata)
    
    async def search_memories(
        self,
        query: str,
        top_k: int = 5,
        category_filter: Optional[str] = None,
        use_advanced_features: bool = True
    ) -> List[Dict]:
        """
        Search memories semantically using Advanced RAG.
        
        Args:
            query: Search query
            top_k: Number of results to return
            category_filter: Optional category to filter by
            use_advanced_features: Enable Tier 1 features
            
        Returns:
            List of relevant memories with scores
        """
        rag = self.get_rag_system()
        if not rag:
            return []
        
        return await rag.retrieve_relevant_memories(
            query=query,
            top_k=top_k,
            category_filter=category_filter,
            use_advanced_features=use_advanced_features
        )
    
    def update_conversation_context(self, text: str):
        """
        Update conversation context for better retrieval.
        
        Args:
            text: Recent conversation turn
        """
        rag = self.get_rag_system()
        if rag:
            rag.update_conversation_context(text)
    
    def reset_conversation_context(self):
        """Reset conversation context (e.g., new session)"""
        rag = self.get_rag_system()
        if rag:
            rag.reset_conversation_context()
    
    def get_stats(self) -> Dict:
        """Get RAG system statistics including Tier 1 metrics"""
        rag = self.get_rag_system()
        if not rag:
            return {"total_memories": 0, "message": "RAG not initialized"}
        
        return rag.get_stats()
    
    async def load_from_database(self, supabase_client, limit: int = 500):
        """
        Load recent memories from Supabase and build FAISS index.
        
        Args:
            supabase_client: Supabase client instance
            limit: Maximum memories to load
        """
        rag = self.get_rag_system()
        if rag:
            await rag.load_from_supabase(supabase_client, limit)
    
    def save_index(self, filepath: str):
        """Save FAISS index and memories to disk"""
        rag = self.get_rag_system()
        if rag:
            rag.save_index(filepath)
    
    def load_index(self, filepath: str):
        """Load FAISS index and memories from disk"""
        rag = self.get_rag_system()
        if rag:
            rag.load_index(filepath)

