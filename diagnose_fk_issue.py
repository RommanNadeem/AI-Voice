#!/usr/bin/env python3
"""
Diagnose the FK constraint issue by checking database state
"""

import os
import sys
from supabase import create_client, Client

def diagnose_issue():
    """Check the current state of the database for the failing user"""
    
    # Get Supabase credentials from environment or .env file
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url:
        print("❌ SUPABASE_URL not found in environment")
        print("   Please set SUPABASE_URL environment variable")
        return
    
    if not supabase_key:
        print("❌ SUPABASE_SERVICE_ROLE_KEY not found in environment")
        print("   Please set SUPABASE_SERVICE_ROLE_KEY environment variable")
        return
    
    print(f"🔍 Connecting to Supabase: {supabase_url[:50]}...")
    supabase: Client = create_client(supabase_url, supabase_key)
    
    # Test user from your logs
    test_user_id = "bb4a6f7c-1e1d-4db8-9fcd-f7095759aba2"
    
    print(f"\n{'='*80}")
    print(f"DIAGNOSING USER: {test_user_id}")
    print(f"{'='*80}")
    
    # Check 1: Does user exist in profiles table?
    print(f"\n1️⃣ Checking profiles table...")
    try:
        resp = supabase.table("profiles").select("user_id, email, created_at").eq("user_id", test_user_id).execute()
        if resp.data:
            profile = resp.data[0]
            print(f"   ✅ Found in profiles table:")
            print(f"      - Email: {profile.get('email', 'N/A')}")
            print(f"      - Created: {profile.get('created_at', 'N/A')}")
        else:
            print(f"   ❌ NOT found in profiles table")
            print(f"   🔧 This is likely the root cause!")
            
            # Try to create it
            print(f"\n   🔧 Attempting to create profiles entry...")
            try:
                create_resp = supabase.table("profiles").insert({
                    "user_id": test_user_id,
                    "email": f"user_{test_user_id[:8]}@companion.local",
                    "is_first_login": True,
                }).execute()
                
                if create_resp.data:
                    print(f"   ✅ Successfully created profiles entry")
                    print(f"   📝 Created: {create_resp.data[0]}")
                else:
                    print(f"   ❌ Create returned no data")
                    
            except Exception as create_err:
                print(f"   ❌ Failed to create profiles entry: {create_err}")
                print(f"   💡 This confirms the RLS issue - can't insert into profiles either")
                
    except Exception as e:
        print(f"   ❌ Error checking profiles: {e}")
    
    # Check 2: Does user exist in memory table?
    print(f"\n2️⃣ Checking memory table...")
    try:
        resp = supabase.table("memory").select("id, category, key, created_at").eq("user_id", test_user_id).execute()
        if resp.data:
            print(f"   ✅ Found {len(resp.data)} memories:")
            for mem in resp.data[:3]:  # Show first 3
                print(f"      - [{mem.get('category', 'N/A')}] {mem.get('key', 'N/A')}")
            if len(resp.data) > 3:
                print(f"      ... and {len(resp.data) - 3} more")
        else:
            print(f"   ❌ No memories found")
    except Exception as e:
        print(f"   ❌ Error checking memory: {e}")
    
    # Check 3: Does user exist in user_profiles table?
    print(f"\n3️⃣ Checking user_profiles table...")
    try:
        resp = supabase.table("user_profiles").select("user_id, created_at").eq("user_id", test_user_id).execute()
        if resp.data:
            profile = resp.data[0]
            print(f"   ✅ Found in user_profiles table:")
            print(f"      - Created: {profile.get('created_at', 'N/A')}")
        else:
            print(f"   ❌ NOT found in user_profiles table")
    except Exception as e:
        print(f"   ❌ Error checking user_profiles: {e}")
    
    # Check 4: Does user exist in onboarding_details table?
    print(f"\n4️⃣ Checking onboarding_details table...")
    try:
        resp = supabase.table("onboarding_details").select("user_id, full_name, created_at").eq("user_id", test_user_id).execute()
        if resp.data:
            onboarding = resp.data[0]
            print(f"   ✅ Found in onboarding_details table:")
            print(f"      - Name: {onboarding.get('full_name', 'N/A')}")
            print(f"      - Created: {onboarding.get('created_at', 'N/A')}")
        else:
            print(f"   ❌ NOT found in onboarding_details table")
    except Exception as e:
        print(f"   ❌ Error checking onboarding_details: {e}")
    
    # Check 5: Test memory insert to confirm FK issue
    print(f"\n5️⃣ Testing memory insert (to confirm FK issue)...")
    try:
        test_memory = {
            "user_id": test_user_id,
            "category": "TEST",
            "key": "diagnostic_test",
            "value": "This is a test memory to check FK constraints"
        }
        
        resp = supabase.table("memory").insert(test_memory).execute()
        print(f"   ✅ Memory insert succeeded - FK constraint is working")
        
        # Clean up test memory
        try:
            supabase.table("memory").delete().eq("user_id", test_user_id).eq("key", "diagnostic_test").execute()
            print(f"   🧹 Cleaned up test memory")
        except:
            pass
            
    except Exception as e:
        err_str = str(e)
        if "foreign key constraint" in err_str.lower():
            print(f"   ❌ FK constraint violation confirmed: {err_str}")
            print(f"   💡 This confirms the RLS issue - need to apply the migration")
        else:
            print(f"   ❌ Other error: {err_str}")
    
    print(f"\n{'='*80}")
    print("SUMMARY & NEXT STEPS")
    print(f"{'='*80}")
    
    print(f"\n🔧 TO FIX THIS ISSUE:")
    print(f"\n1. Apply the RLS fix migration in Supabase Dashboard:")
    print(f"   - Go to https://app.supabase.com")
    print(f"   - Select your project")
    print(f"   - Go to SQL Editor")
    print(f"   - Run the SQL from: migrations/fix_profiles_rls_for_service_role.sql")
    
    print(f"\n2. OR ensure profiles table entry exists before memory operations:")
    print(f"   - Call UserService.ensure_profile_exists() first")
    print(f"   - Then create memories and user_profiles")
    
    print(f"\n3. The issue is that RLS policies block FK constraint validation")
    print(f"   - Your code can SELECT from profiles (so checks pass)")
    print(f"   - But PostgreSQL FK checker can't see the rows")
    print(f"   - Result: All memory/user_profiles inserts fail")
    
    print(f"\n{'='*80}")

if __name__ == "__main__":
    diagnose_issue()
