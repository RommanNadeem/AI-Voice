"""
Quick Test: Verify Name Retrieval from Memory & Profile
=========================================================
Tests if name is correctly retrieved when already stored in:
1. memory table (as FACT)
2. user_profile table

Usage:
    python test_memory_retrieval.py YOUR_USER_ID
"""

import sys
import os
import asyncio
from supabase import create_client, Client

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import Config
from services.memory_service import MemoryService
from services.profile_service import ProfileService
from services.conversation_context_service import ConversationContextService
from rag_system import RAGMemorySystem, get_or_create_rag
from core.validators import set_current_user_id, get_current_user_id


def print_section(title):
    """Print formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


async def test_memory_retrieval(user_id: str):
    """Test memory retrieval for a user"""
    
    print_section("TEST: Memory Retrieval for Name")
    print(f"User ID: {user_id}")
    
    # Initialize Supabase
    print("\n[SETUP] Connecting to Supabase...")
    supabase_url = Config.SUPABASE_URL
    supabase_key = Config.get_supabase_key()
    
    if not supabase_url or not supabase_key:
        print("❌ Supabase credentials not configured!")
        return False
    
    supabase = create_client(supabase_url, supabase_key)
    print("✅ Supabase connected")
    
    # Set current user
    set_current_user_id(user_id)
    print(f"✅ Set current user_id: {get_current_user_id()[:8]}...")
    
    # ============================================================
    # TEST 1: Check Memory Table
    # ============================================================
    print_section("TEST 1: Memory Table Query")
    
    try:
        result = supabase.table("memory")\
            .select("*")\
            .eq("user_id", user_id)\
            .execute()
        
        memories = result.data if result.data else []
        print(f"📊 Total memories in database: {len(memories)}")
        
        if memories:
            print(f"\n📝 Sample memories:")
            for i, mem in enumerate(memories[:5], 1):
                category = mem.get('category', 'N/A')
                key = mem.get('key', 'N/A')
                value = mem.get('value', '')
                print(f"  {i}. [{category}] {key}: {value[:60]}...")
            
            # Look for name specifically
            name_memories = [m for m in memories if 'name' in m.get('key', '').lower() 
                           or 'name' in m.get('value', '').lower()
                           or m.get('category') == 'FACT']
            
            if name_memories:
                print(f"\n🔍 Found {len(name_memories)} potential name-related memories:")
                for mem in name_memories[:3]:
                    print(f"   - [{mem['category']}] {mem['key']}: {mem['value']}")
            else:
                print(f"\n⚠️  No name-related memories found")
        else:
            print("⚠️  No memories found in database for this user")
            
    except Exception as e:
        print(f"❌ Memory table query failed: {e}")
        return False
    
    # ============================================================
    # TEST 2: Check User Profile Table
    # ============================================================
    print_section("TEST 2: User Profile Table Query")
    
    try:
        result = supabase.table("user_profiles")\
            .select("*")\
            .eq("user_id", user_id)\
            .execute()
        
        profiles = result.data if result.data else []
        
        if profiles:
            profile = profiles[0]
            profile_text = profile.get('profile_text', '')
            print(f"✅ Profile found: {len(profile_text)} chars")
            print(f"\n📄 Profile content:")
            print(f"   {profile_text[:300]}...")
            
            # Check if name is in profile
            if any(word in profile_text.lower() for word in ['name is', 'called', 'i\'m', 'i am']):
                print(f"\n✅ Profile appears to contain name information")
            else:
                print(f"\n⚠️  Profile may not contain explicit name")
        else:
            print("⚠️  No profile found for this user")
            
    except Exception as e:
        print(f"❌ Profile table query failed: {e}")
    
    # ============================================================
    # TEST 3: Memory Service Retrieval
    # ============================================================
    print_section("TEST 3: Memory Service Name Retrieval")
    
    memory_service = MemoryService(supabase)
    
    # Try common name keys
    name_keys = ["name", "user_name", "full_name", "first_name"]
    name_found = None
    
    for key in name_keys:
        result = memory_service.get_memory("FACT", key)
        if result:
            print(f"✅ Found name with key '{key}': {result}")
            name_found = result
            break
    
    if not name_found:
        print(f"⚠️  No name found using standard keys: {name_keys}")
    
    # ============================================================
    # TEST 4: Profile Service Retrieval
    # ============================================================
    print_section("TEST 4: Profile Service Retrieval")
    
    profile_service = ProfileService(supabase)
    profile = await profile_service.get_profile_async(user_id)
    
    if profile and profile.strip():
        print(f"✅ Profile retrieved: {len(profile)} chars")
        print(f"📄 Content: {profile[:200]}...")
    else:
        print(f"⚠️  No profile retrieved")
    
    # ============================================================
    # TEST 5: RAG System Loading
    # ============================================================
    print_section("TEST 5: RAG System Memory Loading")
    
    try:
        # Create RAG instance
        print(f"\n[RAG] Creating RAG system...")
        rag = RAGMemorySystem(user_id, Config.OPENAI_API_KEY)
        
        # Load from Supabase
        print(f"[RAG] Loading memories from database...")
        await rag.load_from_supabase(supabase, limit=100)
        
        print(f"✅ RAG loaded {len(rag.memories)} memories")
        print(f"   FAISS index size: {rag.index.ntotal}")
        
        if rag.memories:
            print(f"\n📝 Sample RAG memories:")
            for i, mem in enumerate(rag.memories[:3], 1):
                print(f"  {i}. [{mem['category']}] {mem['text'][:60]}...")
        
        # Test search for name
        print(f"\n[RAG] Searching for 'name'...")
        results = await rag.retrieve_relevant_memories("user name", top_k=3)
        
        if results:
            print(f"✅ Found {len(results)} relevant memories:")
            for i, r in enumerate(results, 1):
                print(f"  {i}. {r['text'][:80]}... (score: {r['similarity']:.3f})")
        else:
            print(f"⚠️  No memories found for query 'user name'")
            
    except Exception as e:
        print(f"❌ RAG system failed: {e}")
        import traceback
        traceback.print_exc()
    
    # ============================================================
    # TEST 6: Conversation Context Service
    # ============================================================
    print_section("TEST 6: ConversationContextService Name Retrieval")
    
    context_service = ConversationContextService(supabase)
    context = await context_service.get_context(user_id)
    
    user_name = context.get("user_name")
    if user_name:
        print(f"✅ Name found in context: '{user_name}'")
    else:
        print(f"⚠️  No name found in context")
    
    print(f"\n📊 Full context keys: {list(context.keys())}")
    
    # ============================================================
    # SUMMARY
    # ============================================================
    print_section("TEST SUMMARY")
    
    results = {
        "Memory table has data": len(memories) > 0,
        "Name in memory table": name_found is not None,
        "Profile exists": profile and profile.strip() if 'profile' in locals() else False,
        "RAG loaded memories": len(rag.memories) > 0 if 'rag' in locals() else False,
        "RAG can search": len(results) > 0 if 'results' in locals() and results else False,
        "Context has name": user_name is not None
    }
    
    print("\n📊 Results:")
    for test, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {test}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print(f"\n🎉 ALL TESTS PASSED - Name retrieval working correctly!")
        return True
    else:
        print(f"\n⚠️  SOME TESTS FAILED - Check results above")
        failed_tests = [test for test, passed in results.items() if not passed]
        print(f"\nFailed tests:")
        for test in failed_tests:
            print(f"  - {test}")
        return False


async def run_test():
    """Main test runner"""
    if len(sys.argv) < 2:
        print("❌ Usage: python test_memory_retrieval.py YOUR_USER_ID")
        print("\nExample:")
        print("  python test_memory_retrieval.py abc12345-1234-1234-1234-123456789abc")
        sys.exit(1)
    
    user_id = sys.argv[1]
    
    # Validate UUID format (basic check)
    if len(user_id) < 30 or '-' not in user_id:
        print(f"⚠️  Warning: '{user_id}' doesn't look like a valid UUID")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(0)
    
    success = await test_memory_retrieval(user_id)
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_test())

