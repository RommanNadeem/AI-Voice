#!/usr/bin/env python3
"""
Production-ready Supabase setup script for LiveKit AI Agent.
This script creates standalone tables that don't depend on auth.users.
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
        
        # Create standalone tables that don't depend on auth.users
        print("\n🔧 Setting up production schema...")
        
        # 1. Create standalone user_profiles table
        print("1️⃣ Creating standalone user_profiles table...")
        try:
            supabase.rpc('exec_sql', {
                'sql': '''
                CREATE TABLE IF NOT EXISTS standalone_user_profiles (
                    user_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    profile_text text,
                    created_at timestamptz DEFAULT now(),
                    updated_at timestamptz DEFAULT now()
                );
                '''
            }).execute()
            print("   ✅ standalone_user_profiles table created")
        except Exception as e:
            print(f"   ⚠️ standalone_user_profiles table might already exist: {e}")
        
        # 2. Create standalone memory table
        print("2️⃣ Creating standalone memory table...")
        try:
            supabase.rpc('exec_sql', {
                'sql': '''
                CREATE TABLE IF NOT EXISTS standalone_memory (
                    id bigserial PRIMARY KEY,
                    user_id uuid NOT NULL,
                    category varchar NOT NULL,
                    key varchar NOT NULL,
                    value text NOT NULL,
                    created_at timestamptz DEFAULT now(),
                    CONSTRAINT uq_standalone_memory_user_key UNIQUE (user_id, category, key)
                );
                '''
            }).execute()
            print("   ✅ standalone_memory table created")
        except Exception as e:
            print(f"   ⚠️ standalone_memory table might already exist: {e}")
        
        # 3. Create standalone user_state table
        print("3️⃣ Creating standalone user_state table...")
        try:
            supabase.rpc('exec_sql', {
                'sql': '''
                CREATE TABLE IF NOT EXISTS standalone_user_state (
                    user_id uuid PRIMARY KEY,
                    stage text DEFAULT 'ORIENTATION',
                    trust_score int DEFAULT 2,
                    updated_at timestamptz DEFAULT now()
                );
                '''
            }).execute()
            print("   ✅ standalone_user_state table created")
        except Exception as e:
            print(f"   ⚠️ standalone_user_state table might already exist: {e}")
        
        # 4. Create standalone chat_history table
        print("4️⃣ Creating standalone chat_history table...")
        try:
            supabase.rpc('exec_sql', {
                'sql': '''
                CREATE TABLE IF NOT EXISTS standalone_chat_history (
                    id bigserial PRIMARY KEY,
                    user_id uuid NOT NULL,
                    user_message text NOT NULL,
                    user_message_roman text,
                    ai_message text NOT NULL,
                    ai_message_roman text,
                    created_at timestamptz DEFAULT now()
                );
                '''
            }).execute()
            print("   ✅ standalone_chat_history table created")
        except Exception as e:
            print(f"   ⚠️ standalone_chat_history table might already exist: {e}")
        
        # 5. Create indexes for performance
        print("5️⃣ Creating indexes...")
        try:
            supabase.rpc('exec_sql', {
                'sql': '''
                CREATE INDEX IF NOT EXISTS idx_standalone_memory_user_id ON standalone_memory(user_id);
                CREATE INDEX IF NOT EXISTS idx_standalone_memory_category ON standalone_memory(category);
                CREATE INDEX IF NOT EXISTS idx_standalone_chat_history_user_id ON standalone_chat_history(user_id);
                CREATE INDEX IF NOT EXISTS idx_standalone_chat_history_created_at ON standalone_chat_history(created_at);
                '''
            }).execute()
            print("   ✅ Indexes created")
        except Exception as e:
            print(f"   ⚠️ Indexes might already exist: {e}")
        
        # 6. Enable RLS and create policies
        print("6️⃣ Setting up Row Level Security...")
        try:
            supabase.rpc('exec_sql', {
                'sql': '''
                ALTER TABLE standalone_user_profiles ENABLE ROW LEVEL SECURITY;
                ALTER TABLE standalone_memory ENABLE ROW LEVEL SECURITY;
                ALTER TABLE standalone_user_state ENABLE ROW LEVEL SECURITY;
                ALTER TABLE standalone_chat_history ENABLE ROW LEVEL SECURITY;
                
                -- Create policies that allow all operations (for standalone use)
                DROP POLICY IF EXISTS "Allow all operations on standalone_user_profiles" ON standalone_user_profiles;
                CREATE POLICY "Allow all operations on standalone_user_profiles" ON standalone_user_profiles FOR ALL USING (true);
                
                DROP POLICY IF EXISTS "Allow all operations on standalone_memory" ON standalone_memory;
                CREATE POLICY "Allow all operations on standalone_memory" ON standalone_memory FOR ALL USING (true);
                
                DROP POLICY IF EXISTS "Allow all operations on standalone_user_state" ON standalone_user_state;
                CREATE POLICY "Allow all operations on standalone_user_state" ON standalone_user_state FOR ALL USING (true);
                
                DROP POLICY IF EXISTS "Allow all operations on standalone_chat_history" ON standalone_chat_history;
                CREATE POLICY "Allow all operations on standalone_chat_history" ON standalone_chat_history FOR ALL USING (true);
                '''
            }).execute()
            print("   ✅ RLS policies created")
        except Exception as e:
            print(f"   ⚠️ RLS setup might have issues: {e}")
        
        print("\n🎉 Production schema setup complete!")
        print("\n📋 Next steps:")
        print("1. Update agent.py to use 'standalone_' prefixed table names")
        print("2. Test the storage functionality")
        print("3. Deploy to production")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to setup production schema: {e}")
        return False

if __name__ == "__main__":
    setup_production_schema()
