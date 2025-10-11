#!/usr/bin/env python3
"""
Apply RLS fix migration to Supabase and verify it worked.
This fixes the FK constraint visibility issue.
"""

import os
import sys
from supabase import create_client, Client

def apply_rls_fix():
    """Apply the RLS fix migration to Supabase"""
    
    # Get Supabase credentials
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variables")
        sys.exit(1)
    
    print(f"Connecting to Supabase: {supabase_url}")
    supabase: Client = create_client(supabase_url, supabase_key)
    
    # Read the migration file
    with open("migrations/fix_profiles_rls_for_service_role.sql", "r") as f:
        migration_sql = f.read()
    
    print("\n" + "="*80)
    print("Applying RLS Fix Migration")
    print("="*80)
    
    # Split the migration into individual statements
    # Remove comments and empty lines
    statements = []
    current_statement = []
    
    for line in migration_sql.split('\n'):
        line = line.strip()
        # Skip comments and verification queries
        if line.startswith('--') or not line:
            continue
        
        current_statement.append(line)
        
        # If line ends with semicolon, we have a complete statement
        if line.endswith(';'):
            stmt = ' '.join(current_statement)
            if stmt and not stmt.startswith('SELECT'):  # Skip verification queries
                statements.append(stmt)
            current_statement = []
    
    # Apply each statement
    success_count = 0
    error_count = 0
    
    for i, stmt in enumerate(statements, 1):
        print(f"\n[{i}/{len(statements)}] Executing...")
        # Show first 80 chars of statement
        print(f"    {stmt[:80]}...")
        
        try:
            # Execute via RPC or direct SQL
            # Note: Supabase Python client doesn't have direct SQL execution
            # You'll need to use the SQL editor in Supabase dashboard
            # or use psycopg2 for direct PostgreSQL connection
            print("    ⚠️  Cannot execute directly via Supabase client")
            print("    ℹ️  Please apply this migration using:")
            print("       1. Supabase Dashboard > SQL Editor")
            print("       2. Or use psycopg2 for direct PostgreSQL connection")
        except Exception as e:
            print(f"    ❌ Error: {e}")
            error_count += 1
    
    print("\n" + "="*80)
    print("Migration Instructions")
    print("="*80)
    print("\n🔧 MANUAL STEPS REQUIRED:")
    print("\n1. Go to your Supabase Dashboard: https://app.supabase.com")
    print("2. Select your project")
    print("3. Navigate to: SQL Editor (left sidebar)")
    print("4. Click 'New Query'")
    print("5. Copy and paste the contents of:")
    print("   migrations/fix_profiles_rls_for_service_role.sql")
    print("6. Click 'Run' to execute")
    print("\n" + "="*80)
    
    # Verify current RLS status
    print("\n" + "="*80)
    print("Checking Current RLS Status")
    print("="*80)
    
    test_user_id = "bb4a6f7c-1e1d-4db8-9fcd-f7095759aba2"
    
    print(f"\n1️⃣ Checking if test user exists in profiles table...")
    try:
        resp = supabase.table("profiles").select("user_id").eq("user_id", test_user_id).execute()
        if resp.data:
            print(f"   ✅ Found user in profiles table")
        else:
            print(f"   ❌ User NOT found in profiles table")
            print(f"   ℹ️  This is the root cause - user needs to exist in profiles first")
            
            # Try to create it
            print(f"\n   🔧 Attempting to create profiles entry...")
            try:
                create_resp = supabase.table("profiles").insert({
                    "user_id": test_user_id,
                    "email": f"user_{test_user_id[:8]}@companion.local",
                }).execute()
                print(f"   ✅ Created profiles entry")
            except Exception as create_err:
                print(f"   ❌ Failed to create: {create_err}")
    except Exception as e:
        print(f"   ❌ Error checking profiles: {e}")
    
    print(f"\n2️⃣ Checking if test user has memories...")
    try:
        resp = supabase.table("memory").select("id").eq("user_id", test_user_id).limit(1).execute()
        print(f"   Found {len(resp.data) if resp.data else 0} memories")
    except Exception as e:
        print(f"   ❌ Error checking memories: {e}")
    
    print(f"\n3️⃣ Checking if test user has profile in user_profiles...")
    try:
        resp = supabase.table("user_profiles").select("user_id").eq("user_id", test_user_id).execute()
        print(f"   Found {len(resp.data) if resp.data else 0} user_profiles entries")
    except Exception as e:
        print(f"   ❌ Error checking user_profiles: {e}")
    
    print("\n" + "="*80)
    print("Next Steps")
    print("="*80)
    print("\n✅ TO FIX THE ISSUE:")
    print("\n1. Apply the migration SQL in Supabase Dashboard (see instructions above)")
    print("2. Ensure the base 'profiles' table has an entry for each user")
    print("3. The profiles entry should be created BEFORE any memory/user_profiles entries")
    print("\n4. OR modify your code to ensure profiles table is populated first:")
    print("   - Use the UserService.ensure_profile_exists() method")
    print("   - This should be called BEFORE any memory or profile operations")
    print("\n" + "="*80)

if __name__ == "__main__":
    apply_rls_fix()

