#!/usr/bin/env python3
"""
Test script to verify Supabase data storage functionality.
This script tests memory storage, profile storage, and retrieval.
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the agent components
from agent import memory_manager, user_profile

async def test_storage():
    """Test all storage functionality."""
    print("🧪 Testing Supabase Storage Functionality")
    print("=" * 50)
    
    # Test 1: Memory Storage
    print("\n1️⃣ Testing Memory Storage...")
    try:
        result = await memory_manager.store("FACT", "test_key", "This is a test memory entry")
        print(f"✅ Memory Storage Result: {result}")
    except Exception as e:
        print(f"❌ Memory Storage Error: {e}")
    
    # Test 2: Memory Retrieval
    print("\n2️⃣ Testing Memory Retrieval...")
    try:
        result = await memory_manager.retrieve("FACT", "test_key")
        print(f"✅ Memory Retrieval Result: {result}")
    except Exception as e:
        print(f"❌ Memory Retrieval Error: {e}")
    
    # Test 3: Profile Storage
    print("\n3️⃣ Testing Profile Storage...")
    try:
        test_profile = "Test user profile: Software developer, interested in AI and machine learning, lives in Karachi"
        await memory_manager.save_profile(test_profile)
        print(f"✅ Profile Storage: Success")
    except Exception as e:
        print(f"❌ Profile Storage Error: {e}")
    
    # Test 4: Profile Retrieval
    print("\n4️⃣ Testing Profile Retrieval...")
    try:
        result = memory_manager.load_profile()
        print(f"✅ Profile Retrieval Result: {result[:100]}...")
    except Exception as e:
        print(f"❌ Profile Retrieval Error: {e}")
    
    # Test 5: Retrieve All Memories
    print("\n5️⃣ Testing Retrieve All Memories...")
    try:
        result = await memory_manager.retrieve_all()
        print(f"✅ Retrieve All Result: {len(result)} memories found")
        for key, value in result.items():
            print(f"   - {key}: {value[:50]}...")
    except Exception as e:
        print(f"❌ Retrieve All Error: {e}")
    
    print("\n" + "=" * 50)
    print("🏁 Storage Test Complete!")

if __name__ == "__main__":
    asyncio.run(test_storage())
