"""
Quick diagnostic script to check profile table issue
Run with: python diagnose_profile_issue.py
"""
import os
from supabase import create_client

# Get Supabase credentials from environment
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variables")
    exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

test_user_id = "bb4a6f7c-1e1d-4db8-9fcd-f7095759aba2"

print("\n" + "="*80)
print("🔍 PROFILE TABLE DIAGNOSTIC")
print("="*80)

# Test 1: Check if profile exists with SELECT
print("\n1️⃣  Testing SELECT on profiles table...")
try:
    result = supabase.table("profiles").select("*").eq("user_id", test_user_id).execute()
    if result.data:
        print(f"✅ SELECT found profile:")
        print(f"   {result.data}")
    else:
        print(f"❌ SELECT found NO profile for user {test_user_id[:8]}")
except Exception as e:
    print(f"❌ SELECT failed: {e}")

# Test 2: Try to insert a test memory
print("\n2️⃣  Testing INSERT to memory table...")
try:
    memory_data = {
        "user_id": test_user_id,
        "category": "TEST",
        "key": "diagnostic_test",
        "value": "This is a test memory"
    }
    result = supabase.table("memory").insert(memory_data).execute()
    if result.data:
        print(f"✅ INSERT to memory succeeded!")
        print(f"   Cleaning up test memory...")
        supabase.table("memory").delete().eq("user_id", test_user_id).eq("key", "diagnostic_test").execute()
    else:
        print(f"❌ INSERT to memory failed: {result.error}")
except Exception as e:
    error_str = str(e)
    if "23503" in error_str or "foreign key constraint" in error_str.lower():
        print(f"❌ FK CONSTRAINT ERROR: Profile not visible to FK check!")
        print(f"   Error: {e}")
        print(f"\n🔥 ROOT CAUSE: The profiles table row exists for SELECT,")
        print(f"   but is NOT visible to the FK constraint checker!")
        print(f"\n   This is usually caused by:")
        print(f"   - RLS policies that block the FK constraint context")
        print(f"   - Profile created by a different role (anon vs service_role)")
        print(f"   - Missing RLS policy for authenticated/service role")
    else:
        print(f"❌ INSERT failed: {e}")

# Test 3: Check RLS status
print("\n3️⃣  Checking RLS status...")
try:
    # Try to query pg_tables (might not have permission)
    rls_query = f"""
    SELECT tablename, rowsecurity 
    FROM pg_tables 
    WHERE schemaname = 'public' 
    AND tablename IN ('profiles', 'memory', 'user_profiles');
    """
    # Note: This might not work with regular Supabase client
    print("   (RLS check requires direct SQL access - check Supabase dashboard)")
except Exception as e:
    print(f"   Cannot check RLS via API: {e}")

print("\n" + "="*80)
print("📋 RECOMMENDED FIXES:")
print("="*80)
print("\n1. Check Supabase Dashboard → Authentication → Policies")
print("   - Ensure 'profiles' table has policy allowing SERVICE_ROLE")
print("\n2. Disable RLS on profiles table (if it's a system table):")
print("   ALTER TABLE profiles DISABLE ROW LEVEL SECURITY;")
print("\n3. Or add policy for service role:")
print("""
   CREATE POLICY "Service role can do everything"
   ON profiles
   FOR ALL
   TO service_role
   USING (true)
   WITH CHECK (true);
""")
print("\n4. Verify the user was created properly:")
print(f"   SELECT * FROM auth.users WHERE id = '{test_user_id}';")
print("\n" + "="*80 + "\n")

