"""
Quick RLS verification script - Run this to check if the SQL migration was applied
Usage: python check_rls_setup.py
"""
import os
import sys
from supabase import create_client

# Get Supabase credentials from environment
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variables")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

print("\n" + "="*80)
print("🔍 RLS POLICY VERIFICATION")
print("="*80)

# Test user ID from the logs
test_user_id = "bb4a6f7c-1e1d-4db8-9fcd-f7095759aba2"

print(f"\n📝 Testing with user: {test_user_id[:8]}...\n")

# Step 1: Check if profile exists
print("1️⃣  Checking if profile exists...")
try:
    result = supabase.table("profiles").select("id, user_id, email").eq("user_id", test_user_id).execute()
    if result.data:
        print(f"   ✅ Profile EXISTS (SELECT query can see it)")
        print(f"   Data: {result.data[0]}")
    else:
        print(f"   ❌ Profile DOES NOT EXIST")
        print(f"   Creating test profile...")
        try:
            create_result = supabase.table("profiles").insert({
                "user_id": test_user_id,
                "email": f"test_{test_user_id[:8]}@test.com",
                "is_first_login": True
            }).execute()
            if create_result.data:
                print(f"   ✅ Profile created successfully")
            else:
                print(f"   ❌ Profile creation failed: {create_result.error}")
        except Exception as create_err:
            print(f"   ❌ Profile creation error: {create_err}")
except Exception as e:
    print(f"   ❌ Error checking profile: {e}")
    sys.exit(1)

# Step 2: Try to insert a test memory
print("\n2️⃣  Testing memory INSERT (this is where FK check happens)...")
test_memory = {
    "user_id": test_user_id,
    "category": "TEST",
    "key": "rls_diagnostic_test",
    "value": "Testing RLS setup"
}

try:
    result = supabase.table("memory").insert(test_memory).execute()
    if result.data:
        print(f"   ✅✅✅ SUCCESS! Memory insert worked!")
        print(f"   🎉 RLS policies are configured correctly!")
        print(f"\n   Cleaning up test memory...")
        supabase.table("memory").delete().eq("user_id", test_user_id).eq("key", "rls_diagnostic_test").execute()
        print(f"   ✅ Cleanup complete")
        print("\n" + "="*80)
        print("✅ RLS IS WORKING CORRECTLY - Memories should now save!")
        print("="*80 + "\n")
        sys.exit(0)
    else:
        print(f"   ❌ Insert failed: {result.error}")
except Exception as e:
    error_str = str(e)
    if "23503" in error_str or "foreign key constraint" in error_str.lower():
        print(f"   ❌❌❌ FK CONSTRAINT ERROR!")
        print(f"   Error: {error_str}")
        print("\n" + "="*80)
        print("❌ RLS POLICIES NOT FIXED YET")
        print("="*80)
        print("\n🔧 YOU NEED TO RUN THIS SQL IN SUPABASE:\n")
        print("="*80)
        print("""
-- Copy and paste this into Supabase SQL Editor:

DROP POLICY IF EXISTS "Service role full access to profiles" ON profiles;
CREATE POLICY "Service role full access to profiles"
ON profiles FOR ALL TO service_role
USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Service role full access to memory" ON memory;
CREATE POLICY "Service role full access to memory"
ON memory FOR ALL TO service_role
USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Service role full access to user_profiles" ON user_profiles;
CREATE POLICY "Service role full access to user_profiles"
ON user_profiles FOR ALL TO service_role
USING (true) WITH CHECK (true);
""")
        print("="*80)
        print("\n📍 Steps:")
        print("1. Go to Supabase Dashboard → SQL Editor")
        print("2. Paste the SQL above")
        print("3. Click 'Run'")
        print("4. Run this script again to verify")
        print("5. Restart your container\n")
        sys.exit(1)
    else:
        print(f"   ❌ Other error: {e}")
        sys.exit(1)

