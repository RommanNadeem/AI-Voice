#!/usr/bin/env python3
"""
Diagnose database schema and FK issues
Run this to see exactly what's happening with profiles/memory tables
"""

import os
import sys
from supabase import create_client

# Get credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    sys.exit(1)

# Create client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
print(f"✅ Connected to Supabase")
print(f"   URL: {SUPABASE_URL}")
print()

# Test user_id
test_user_id = "bb4a6f7c-1e1d-4db8-9fcd-f7095759aba2"
print(f"Testing with user_id: {test_user_id}")
print("=" * 80)

# 1. Check profiles table structure
print("\n1️⃣  PROFILES TABLE STRUCTURE")
print("-" * 80)
try:
    # Try to get column info by doing a select with limit 0
    result = supabase.table("profiles").select("*").limit(0).execute()
    print("✅ profiles table exists")
    
    # Check if any profiles exist
    all_profiles = supabase.table("profiles").select("*").limit(5).execute()
    print(f"   Found {len(all_profiles.data)} profiles in database")
    
    if all_profiles.data:
        print("\n   Sample profile structure:")
        first_profile = all_profiles.data[0]
        for key, value in first_profile.items():
            print(f"      {key}: {type(value).__name__} = {str(value)[:50]}")
    
except Exception as e:
    print(f"❌ Error accessing profiles table: {e}")

# 2. Check if our test user exists in profiles
print("\n2️⃣  TEST USER IN PROFILES TABLE")
print("-" * 80)

# Try different queries to see which column exists
queries_to_try = [
    ("id", test_user_id),
    ("user_id", test_user_id),
]

for column, value in queries_to_try:
    try:
        result = supabase.table("profiles").select("*").eq(column, value).execute()
        print(f"✅ Query by {column}: Found {len(result.data)} rows")
        if result.data:
            print(f"   Data: {result.data[0]}")
    except Exception as e:
        print(f"❌ Query by {column} failed: {str(e)[:100]}")

# 3. Try to insert a test profile
print("\n3️⃣  TEST PROFILE INSERT")
print("-" * 80)

test_profile_data = {
    "user_id": test_user_id,
    "email": f"test_{test_user_id[:8]}@test.com",
    "is_first_login": True,
}

try:
    insert_result = supabase.table("profiles").insert(test_profile_data).execute()
    print(f"✅ Insert successful!")
    print(f"   Result: {insert_result.data}")
except Exception as e:
    error_str = str(e)
    print(f"❌ Insert failed: {error_str[:200]}")
    
    # Check what the error tells us
    if "user_id" in error_str and "does not exist" in error_str.lower():
        print("\n   ⚠️  ISSUE: profiles table doesn't have 'user_id' column!")
        print("   Need to check actual schema")
    elif "duplicate" in error_str.lower():
        print("\n   ℹ️  Profile already exists (good - means insert works)")
    elif "null value" in error_str.lower():
        print("\n   ⚠️  ISSUE: Some required column is missing")

# 4. Check memory table
print("\n4️⃣  MEMORY TABLE STRUCTURE")
print("-" * 80)
try:
    result = supabase.table("memory").select("*").eq("user_id", test_user_id).limit(1).execute()
    print(f"✅ memory table accessible")
    print(f"   Found {len(result.data)} memories for test user")
    
    if result.data:
        print("\n   Sample memory structure:")
        for key, value in result.data[0].items():
            print(f"      {key}: {type(value).__name__}")
            
except Exception as e:
    print(f"❌ Error accessing memory table: {e}")

# 5. Try to insert a test memory
print("\n5️⃣  TEST MEMORY INSERT")
print("-" * 80)

test_memory_data = {
    "user_id": test_user_id,
    "category": "TEST",
    "key": "diagnostic_test",
    "value": "Test memory for diagnostics",
}

try:
    memory_result = supabase.table("memory").insert(test_memory_data).execute()
    print(f"✅ Memory insert successful!")
    print(f"   Result: {memory_result.data}")
except Exception as e:
    error_str = str(e)
    print(f"❌ Memory insert failed: {error_str[:200]}")
    
    if "23503" in error_str or "foreign key" in error_str.lower():
        print("\n   ⚠️  FK CONSTRAINT ERROR!")
        print("   This means the profile doesn't exist or FK constraint is misconfigured")
        print(f"   Looking for user_id: {test_user_id}")

# 6. Check user_profiles table
print("\n6️⃣  USER_PROFILES TABLE")
print("-" * 80)
try:
    result = supabase.table("user_profiles").select("*").eq("user_id", test_user_id).execute()
    print(f"✅ user_profiles table accessible")
    print(f"   Found {len(result.data)} profile entries for test user")
except Exception as e:
    print(f"❌ Error accessing user_profiles table: {e}")

# 7. Summary and recommendations
print("\n" + "=" * 80)
print("📋 DIAGNOSTIC SUMMARY")
print("=" * 80)

print("\n🔍 Check the output above for:")
print("   1. What columns exist in profiles table (id vs user_id)")
print("   2. Whether test profile exists")
print("   3. FK constraint errors")
print("   4. RLS policy issues")

print("\n💡 NEXT STEPS:")
print("   • If 'user_id column doesn't exist': Need to add user_id column to profiles")
print("   • If FK errors persist: Check FK constraint references correct column")
print("   • If RLS blocks access: Apply RLS policy fixes")
print("   • If duplicate errors: Profile exists, need to fix query logic")
print()

