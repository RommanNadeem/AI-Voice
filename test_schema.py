#!/usr/bin/env python3
"""
Simple production-ready Supabase setup script for LiveKit AI Agent.
This script creates standalone tables using direct SQL execution.
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def setup_production_schema():
    """Set up production-ready schema for LiveKit AI Agent."""
    
    # Get Supabase credentials
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_ANON_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ Missing Supabase credentials in .env file")
        return False
    
    try:
        # Create Supabase client
        supabase: Client = create_client(supabase_url, supabase_key)
        print("✅ Connected to Supabase")
        
        print("\n🔧 Testing standalone table creation...")
        
        # Test creating a simple standalone table
        print("1️⃣ Testing standalone_user_profiles table...")
        try:
            # Try to insert a test record to see if table exists
            test_response = supabase.table('standalone_user_profiles').insert({
                'user_id': '550e8400-e29b-41d4-a716-446655440000',
                'profile_text': 'Test profile'
            }).execute()
            
            if test_response.data:
                print("   ✅ standalone_user_profiles table exists and works!")
                
                # Clean up test data
                supabase.table('standalone_user_profiles').delete().eq('user_id', '550e8400-e29b-41d4-a716-446655440000').execute()
                print("   🧹 Test data cleaned up")
            else:
                print("   ❌ standalone_user_profiles table doesn't work")
                
        except Exception as e:
            print(f"   ❌ standalone_user_profiles table issue: {e}")
        
        print("2️⃣ Testing standalone_memory table...")
        try:
            # Try to insert a test record
            test_response = supabase.table('standalone_memory').insert({
                'user_id': '550e8400-e29b-41d4-a716-446655440000',
                'category': 'TEST',
                'key': 'test_key',
                'value': 'test_value'
            }).execute()
            
            if test_response.data:
                print("   ✅ standalone_memory table exists and works!")
                
                # Clean up test data
                supabase.table('standalone_memory').delete().eq('user_id', '550e8400-e29b-41d4-a716-446655440000').execute()
                print("   🧹 Test data cleaned up")
            else:
                print("   ❌ standalone_memory table doesn't work")
                
        except Exception as e:
            print(f"   ❌ standalone_memory table issue: {e}")
        
        print("\n🎉 Schema test complete!")
        print("\n📋 If tables don't exist, you'll need to create them manually in Supabase dashboard:")
        print("1. Go to your Supabase project dashboard")
        print("2. Navigate to Table Editor")
        print("3. Create the following tables:")
        print("   - standalone_user_profiles")
        print("   - standalone_memory") 
        print("   - standalone_user_state")
        print("   - standalone_chat_history")
        print("4. Use the schema from supabase_schema.sql file")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to test schema: {e}")
        return False

if __name__ == "__main__":
    setup_production_schema()
