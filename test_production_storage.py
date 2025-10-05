#!/usr/bin/env python3
"""
Production-ready test script for LiveKit AI Agent with existing Supabase schema.
This script tests the actual storage functionality with proper error handling.
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the agent components
from agent import memory_manager, user_profile

async def test_production_storage():
    """Test production storage functionality with existing schema."""
    print("🚀 Testing Production Storage with Existing Supabase Schema")
    print("=" * 60)
    
    # Test 1: Direct Memory Storage (bypassing profile constraints)
    print("\n1️⃣ Testing Direct Memory Storage...")
    try:
        # Test storing memory directly without profile dependency
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        
        # Try direct insert into memory table
        response = memory_manager.supabase.table('memory').insert({
            'user_id': user_id,
            'category': 'FACT',
            'key': 'test_direct',
            'value': 'This is a direct test memory entry'
        }).execute()
        
        if response.data:
            print(f"✅ Direct Memory Storage: SUCCESS")
            print(f"   Stored: {response.data}")
        else:
            print(f"❌ Direct Memory Storage: FAILED")
            
    except Exception as e:
        print(f"❌ Direct Memory Storage Error: {e}")
    
    # Test 2: Direct Profile Storage
    print("\n2️⃣ Testing Direct Profile Storage...")
    try:
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        
        # Try direct insert into user_profiles table
        response = memory_manager.supabase.table('user_profiles').insert({
            'user_id': user_id,
            'profile_text': 'Test user profile: Software developer, interested in AI and machine learning'
        }).execute()
        
        if response.data:
            print(f"✅ Direct Profile Storage: SUCCESS")
            print(f"   Stored: {response.data}")
        else:
            print(f"❌ Direct Profile Storage: FAILED")
            
    except Exception as e:
        print(f"❌ Direct Profile Storage Error: {e}")
    
    # Test 3: Memory Retrieval
    print("\n3️⃣ Testing Memory Retrieval...")
    try:
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        
        # Try to retrieve stored memory
        response = memory_manager.supabase.table('memory').select('*').eq('user_id', user_id).execute()
        
        if response.data:
            print(f"✅ Memory Retrieval: SUCCESS")
            print(f"   Found {len(response.data)} memory entries:")
            for item in response.data:
                print(f"   - {item['category']}:{item['key']} = {item['value'][:50]}...")
        else:
            print(f"❌ Memory Retrieval: No data found")
            
    except Exception as e:
        print(f"❌ Memory Retrieval Error: {e}")
    
    # Test 4: Profile Retrieval
    print("\n4️⃣ Testing Profile Retrieval...")
    try:
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        
        # Try to retrieve stored profile
        response = memory_manager.supabase.table('user_profiles').select('*').eq('user_id', user_id).execute()
        
        if response.data:
            print(f"✅ Profile Retrieval: SUCCESS")
            print(f"   Found {len(response.data)} profile entries:")
            for item in response.data:
                print(f"   - Profile: {item['profile_text'][:100]}...")
        else:
            print(f"❌ Profile Retrieval: No data found")
            
    except Exception as e:
        print(f"❌ Profile Retrieval Error: {e}")
    
    # Test 5: Cleanup Test Data
    print("\n5️⃣ Cleaning up test data...")
    try:
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        
        # Clean up memory
        memory_manager.supabase.table('memory').delete().eq('user_id', user_id).execute()
        
        # Clean up profiles
        memory_manager.supabase.table('user_profiles').delete().eq('user_id', user_id).execute()
        
        print(f"✅ Cleanup: SUCCESS")
        
    except Exception as e:
        print(f"❌ Cleanup Error: {e}")
    
    print("\n" + "=" * 60)
    print("🏁 Production Storage Test Complete!")
    print("\n📋 Summary:")
    print("- If direct storage works, the issue is in the agent's constraint handling")
    print("- If direct storage fails, there are schema/permission issues")
    print("- The agent needs to be updated to handle constraints gracefully")

if __name__ == "__main__":
    asyncio.run(test_production_storage())
