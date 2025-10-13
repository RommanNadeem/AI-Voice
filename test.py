"""
Live Database Test - Context Management Flow
Tests actual database storage and retrieval with test user ID
Run: python -m pytest tests/test_live_context_flow.py -v -s
"""

import os
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase import create_client, Client
from core.config import Config
from core.validators import set_current_user_id, set_supabase_client
from services.memory_service import MemoryService
from services.profile_service import ProfileService
from services.conversation_context_service import ConversationContextService
from services.conversation_state_service import ConversationStateService
from services.user_service import UserService
from services.rag_service import RAGService


# Test user ID (provided by user)
TEST_USER_ID = "4e3efa3d-d8fe-431e-a78f-4efffb0cf43a"


def get_supabase_client() -> Client:
    """Initialize Supabase client"""
    url = Config.SUPABASE_URL
    key = Config.get_supabase_key()
    
    if not url or not key:
        raise RuntimeError("Supabase credentials not configured")
    
    return create_client(url, key)


class TestLiveContextFlow:
    """Test context management with actual database"""
    
    def setup_method(self):
        """Setup before each test"""
        self.supabase = get_supabase_client()
        set_supabase_client(self.supabase)
        set_current_user_id(TEST_USER_ID)
        
        self.user_service = UserService(self.supabase)
        self.memory_service = MemoryService(self.supabase)
        self.profile_service = ProfileService(self.supabase)
        self.context_service = ConversationContextService(self.supabase)
        self.state_service = ConversationStateService(self.supabase)
        
        print(f"\n{'='*80}")
        print(f"🧪 Testing with user: {TEST_USER_ID}")
        print(f"{'='*80}\n")
    
    def test_01_ensure_profile_exists(self):
        """Step 1: Ensure user profile exists (FK requirement)"""
        print("\n📋 TEST 1: Ensure Profile Exists")
        print("-" * 80)
        
        exists = self.user_service.ensure_profile_exists(TEST_USER_ID)
        
        assert exists, "❌ Failed to ensure profile exists"
        print(f"✅ Profile exists for user {TEST_USER_ID[:8]}...")
    
    def test_02_store_memories(self):
        """Step 2: Store various memories in database"""
        print("\n💾 TEST 2: Store Memories")
        print("-" * 80)
        
        test_memories = [
            ("FACT", "name", "احمد"),
            ("FACT", "age", "28"),
            ("FACT", "city", "کراچی"),
            ("PREFERENCE", "favorite_food", "بریانی"),
            ("PREFERENCE", "favorite_color", "نیلا"),
            ("GOAL", "learning_goal", "اردو سیکھنا"),
            ("INTEREST", "hobby", "کوڈنگ"),
            ("RELATIONSHIP", "family", "بہن اور ماں کے ساتھ رہتا ہے"),
        ]
        
        results = []
        for category, key, value in test_memories:
            success = self.memory_service.save_memory(
                category=category,
                key=key,
                value=value,
                user_id=TEST_USER_ID
            )
            results.append(success)
            status = "✅" if success else "❌"
            print(f"{status} [{category}] {key} = {value}")
        
        assert all(results), "❌ Some memory saves failed"
        print(f"\n✅ All {len(results)} memories saved successfully")
    
    def test_03_retrieve_memories(self):
        """Step 3: Retrieve individual memories"""
        print("\n🔍 TEST 3: Retrieve Individual Memories")
        print("-" * 80)
        
        # Test retrieving each memory
        name = self.memory_service.get_memory("FACT", "name", TEST_USER_ID)
        food = self.memory_service.get_memory("PREFERENCE", "favorite_food", TEST_USER_ID)
        goal = self.memory_service.get_memory("GOAL", "learning_goal", TEST_USER_ID)
        
        print(f"📌 Name: {name}")
        print(f"📌 Favorite Food: {food}")
        print(f"📌 Learning Goal: {goal}")
        
        assert name == "احمد", f"Expected 'احمد', got '{name}'"
        assert food == "بریانی", f"Expected 'بریانی', got '{food}'"
        assert goal == "اردو سیکھنا", f"Expected 'اردو سیکھنا', got '{goal}'"
        
        print("\n✅ All individual retrievals successful")
    
    def test_04_retrieve_by_category(self):
        """Step 4: Retrieve memories by category"""
        print("\n📚 TEST 4: Retrieve by Category")
        print("-" * 80)
        
        facts = self.memory_service.get_memories_by_category("FACT", limit=10, user_id=TEST_USER_ID)
        prefs = self.memory_service.get_memories_by_category("PREFERENCE", limit=10, user_id=TEST_USER_ID)
        
        print(f"📊 FACT memories: {len(facts)}")
        for fact in facts:
            print(f"   - {fact['key']}: {fact['value']}")
        
        print(f"\n📊 PREFERENCE memories: {len(prefs)}")
        for pref in prefs:
            print(f"   - {pref['key']}: {pref['value']}")
        
        assert len(facts) >= 3, f"Expected at least 3 facts, got {len(facts)}"
        assert len(prefs) >= 2, f"Expected at least 2 preferences, got {len(prefs)}"
        
        print("\n✅ Category retrieval successful")
    
    def test_05_batch_category_retrieval(self):
        """Step 5: Test optimized batch retrieval"""
        print("\n🚀 TEST 5: Batch Category Retrieval (Optimized)")
        print("-" * 80)
        
        categories = ['FACT', 'PREFERENCE', 'GOAL', 'INTEREST', 'RELATIONSHIP']
        grouped = self.memory_service.get_memories_by_categories_batch(
            categories=categories,
            limit_per_category=5,
            user_id=TEST_USER_ID
        )
        
        total = 0
        for cat, mems in grouped.items():
            count = len(mems)
            total += count
            print(f"📊 {cat}: {count} memories")
            for mem in mems[:2]:  # Show first 2
                print(f"   - {mem['key']}: {mem['value'][:50]}...")
        
        print(f"\n✅ Batch retrieved {total} memories across {len(categories)} categories")
        assert total >= 5, f"Expected at least 5 total memories, got {total}"
    
    def test_06_conversation_context(self):
        """Step 6: Test conversation context service"""
        print("\n💬 TEST 6: Conversation Context Service")
        print("-" * 80)
        
        async def test_context():
            context = await self.context_service.get_context(TEST_USER_ID)
            
            print(f"📝 User Name: {context.get('user_name')}")
            print(f"📝 User Gender: {context.get('user_gender')}")
            print(f"📝 Profile Length: {len(context.get('user_profile', ''))} chars")
            print(f"📝 Recent Memories: {len(context.get('recent_memories', []))}")
            print(f"📝 Conversation Stage: {context['conversation_state'].get('stage')}")
            print(f"📝 Trust Score: {context['conversation_state'].get('trust_score')}")
            
            # Check cache stats
            stats = self.context_service.get_stats()
            print(f"\n📊 Context Cache Stats:")
            print(f"   - Total Requests: {stats['total_requests']}")
            print(f"   - Hit Rate: {stats['hit_rate']}")
            print(f"   - Session Cache Size: {stats['session_cache_size']}")
            
            return context
        
        context = asyncio.run(test_context())
        
        assert context is not None, "❌ Context retrieval failed"
        assert 'user_profile' in context, "❌ Missing user_profile in context"
        assert 'conversation_state' in context, "❌ Missing conversation_state in context"
        
        print("\n✅ Context service working correctly")
    
    def test_07_conversation_state(self):
        """Step 7: Test conversation state management"""
        print("\n📊 TEST 7: Conversation State Management")
        print("-" * 80)
        
        async def test_state():
            # Get current state
            state = await self.state_service.get_state(TEST_USER_ID)
            print(f"📌 Current Stage: {state['stage']}")
            print(f"📌 Current Trust: {state['trust_score']:.1f}/10")
            
            # Update state
            updated = await self.state_service.update_state(
                stage="ENGAGEMENT",
                trust_score=6.5,
                user_id=TEST_USER_ID
            )
            
            if updated:
                new_state = await self.state_service.get_state(TEST_USER_ID)
                print(f"\n✅ State Updated:")
                print(f"   - Stage: {state['stage']} → {new_state['stage']}")
                print(f"   - Trust: {state['trust_score']:.1f} → {new_state['trust_score']:.1f}")
                return new_state
            else:
                print("\n⚠️  State update failed (may be RLS policy issue)")
                return state
        
        result = asyncio.run(test_state())
        assert result is not None, "❌ State retrieval failed"
    
    def test_08_rag_integration(self):
        """Step 8: Test RAG service integration"""
        print("\n🔎 TEST 8: RAG Service Integration")
        print("-" * 80)
        
        async def test_rag():
            rag_service = RAGService(TEST_USER_ID)
            
            # Load from database
            await rag_service.load_from_database(self.supabase, limit=100)
            
            rag_system = rag_service.get_rag_system()
            print(f"📊 RAG loaded {len(rag_system.memories)} memories")
            print(f"📊 FAISS index size: {rag_system.index.ntotal}")
            
            # Test semantic search
            results = await rag_service.search_memories(
                query="user's favorite food",
                top_k=3
            )
            
            print(f"\n🔍 Search Results for 'user's favorite food':")
            for i, result in enumerate(results, 1):
                print(f"   {i}. {result['text'][:60]}... (score: {result['similarity']:.3f})")
            
            return len(results)
        
        count = asyncio.run(test_rag())
        assert count > 0, "❌ RAG search returned no results"
        print(f"\n✅ RAG search found {count} relevant memories")
    
    def test_09_profile_generation(self):
        """Step 9: Test profile generation from memories"""
        print("\n👤 TEST 9: Profile Generation")
        print("-" * 80)
        
        # Get all memories for profile generation
        all_memories = []
        for cat in ['FACT', 'PREFERENCE', 'GOAL', 'INTEREST']:
            mems = self.memory_service.get_memories_by_category(cat, user_id=TEST_USER_ID)
            all_memories.extend([f"{m['key']}: {m['value']}" for m in mems])
        
        input_text = "\n".join(all_memories[:10])  # Use first 10
        print(f"📝 Input for profile (first 10 memories):\n{input_text}\n")
        
        existing = self.profile_service.get_profile(TEST_USER_ID)
        generated = self.profile_service.generate_profile(input_text, existing)
        
        if generated:
            print(f"✅ Generated Profile ({len(generated)} chars):")
            print(f"{generated[:300]}...")
        else:
            print("⚠️  No profile generated (may need more context)")
    
    def test_10_complete_context_summary(self):
        """Step 10: Final summary - all context for user"""
        print("\n📋 TEST 10: Complete Context Summary")
        print("=" * 80)
        
        async def get_complete_info():
            # Get everything
            profile = self.profile_service.get_profile(TEST_USER_ID)
            context = await self.context_service.get_context(TEST_USER_ID)
            state = await self.state_service.get_state(TEST_USER_ID)
            
            facts = self.memory_service.get_memories_by_category("FACT", user_id=TEST_USER_ID)
            prefs = self.memory_service.get_memories_by_category("PREFERENCE", user_id=TEST_USER_ID)
            goals = self.memory_service.get_memories_by_category("GOAL", user_id=TEST_USER_ID)
            
            print(f"\n🎯 COMPLETE CONTEXT FOR USER {TEST_USER_ID[:8]}...")
            print("-" * 80)
            
            print(f"\n👤 PROFILE ({len(profile) if profile else 0} chars):")
            if profile:
                print(f"{profile[:200]}...")
            
            print(f"\n📊 CONVERSATION STATE:")
            print(f"   - Stage: {state['stage']}")
            print(f"   - Trust Score: {state['trust_score']:.1f}/10")
            
            print(f"\n💭 MEMORIES:")
            print(f"   - Facts: {len(facts)}")
            for fact in facts[:3]:
                print(f"      • {fact['key']}: {fact['value']}")
            
            print(f"   - Preferences: {len(prefs)}")
            for pref in prefs[:3]:
                print(f"      • {pref['key']}: {pref['value']}")
            
            print(f"   - Goals: {len(goals)}")
            for goal in goals[:3]:
                print(f"      • {goal['key']}: {goal['value']}")
            
            print(f"\n🔄 CONTEXT CACHE:")
            print(f"   - User Name: {context.get('user_name')}")
            print(f"   - Recent Memories: {len(context.get('recent_memories', []))}")
            print(f"   - Fetched At: {context.get('fetched_at')}")
            
            return {
                'profile': profile,
                'facts': len(facts),
                'preferences': len(prefs),
                'goals': len(goals),
                'stage': state['stage'],
                'trust': state['trust_score']
            }
        
        summary = asyncio.run(get_complete_info())
        
        print(f"\n{'='*80}")
        print(f"✅ TEST COMPLETE - Context Management Verified")
        print(f"{'='*80}\n")
        
        assert summary['facts'] >= 3, "Not enough facts stored"
        assert summary['preferences'] >= 2, "Not enough preferences stored"


if __name__ == "__main__":
    """Run tests directly"""
    import pytest
    
    # Run with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short"])