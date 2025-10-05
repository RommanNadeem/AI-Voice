#!/usr/bin/env python3
"""
Migration script to move data from Supabase to Firebase
Run this script to migrate existing data
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
import firebase_admin
from firebase_admin import credentials, firestore

# Load environment variables
load_dotenv()

# Supabase configuration (existing)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Firebase configuration (new)
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
FIREBASE_PRIVATE_KEY = os.getenv("FIREBASE_PRIVATE_KEY")
FIREBASE_CLIENT_EMAIL = os.getenv("FIREBASE_CLIENT_EMAIL")
FIREBASE_CLIENT_ID = os.getenv("FIREBASE_CLIENT_ID")

def initialize_clients():
    """Initialize both Supabase and Firebase clients"""
    # Initialize Supabase
    if not (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY):
        print("[ERROR] Supabase credentials not found")
        return None, None
    
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        print("[SUCCESS] Supabase client initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize Supabase: {e}")
        return None, None
    
    # Initialize Firebase
    if not all([FIREBASE_PROJECT_ID, FIREBASE_PRIVATE_KEY, FIREBASE_CLIENT_EMAIL]):
        print("[ERROR] Firebase credentials not found")
        return supabase, None
    
    try:
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": FIREBASE_PROJECT_ID,
            "private_key": FIREBASE_PRIVATE_KEY.replace('\\n', '\n'),
            "client_email": FIREBASE_CLIENT_EMAIL,
            "client_id": FIREBASE_CLIENT_ID,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        })
        
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("[SUCCESS] Firebase client initialized")
        return supabase, db
        
    except Exception as e:
        print(f"[ERROR] Failed to initialize Firebase: {e}")
        return supabase, None

def migrate_profiles(supabase, db):
    """Migrate profiles from Supabase to Firebase"""
    print("\n[MIGRATION] Migrating profiles...")
    
    try:
        # Get all profiles from Supabase
        response = supabase.table('profiles').select('*').execute()
        profiles = response.data
        
        print(f"[MIGRATION] Found {len(profiles)} profiles to migrate")
        
        for profile in profiles:
            user_id = profile['id']
            
            # Create user document in Firebase
            user_data = {
                'id': user_id,
                'email': profile.get('email', f'user_{user_id[:8]}@local'),
                'is_first_login': profile.get('is_first_login', True),
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            db.collection('users').document(user_id).set(user_data)
            print(f"[MIGRATION] Migrated profile for user: {user_id}")
        
        print(f"[MIGRATION] Successfully migrated {len(profiles)} profiles")
        
    except Exception as e:
        print(f"[MIGRATION ERROR] Failed to migrate profiles: {e}")

def migrate_user_profiles(supabase, db):
    """Migrate user_profiles from Supabase to Firebase"""
    print("\n[MIGRATION] Migrating user profiles...")
    
    try:
        # Get all user profiles from Supabase
        response = supabase.table('user_profiles').select('*').execute()
        user_profiles = response.data
        
        print(f"[MIGRATION] Found {len(user_profiles)} user profiles to migrate")
        
        for profile in user_profiles:
            user_id = profile['user_id']
            
            # Create user profile document in Firebase
            profile_data = {
                'user_id': user_id,
                'profile_text': profile.get('profile_text', ''),
                'updated_at': datetime.utcnow()
            }
            
            db.collection('user_profiles').document(user_id).set(profile_data)
            print(f"[MIGRATION] Migrated user profile for user: {user_id}")
        
        print(f"[MIGRATION] Successfully migrated {len(user_profiles)} user profiles")
        
    except Exception as e:
        print(f"[MIGRATION ERROR] Failed to migrate user profiles: {e}")

def migrate_memories(supabase, db):
    """Migrate memories from Supabase to Firebase"""
    print("\n[MIGRATION] Migrating memories...")
    
    try:
        # Get all memories from Supabase
        response = supabase.table('memory').select('*').execute()
        memories = response.data
        
        print(f"[MIGRATION] Found {len(memories)} memories to migrate")
        
        for memory in memories:
            user_id = memory['user_id']
            key = memory['key']
            
            # Create memory document in Firebase
            memory_data = {
                'user_id': user_id,
                'category': memory.get('category', 'FACT'),
                'key': key,
                'value': memory.get('value', ''),
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            # Use user_id + key as document ID
            doc_id = f"{user_id}_{key}"
            db.collection('memories').document(doc_id).set(memory_data)
            print(f"[MIGRATION] Migrated memory: {doc_id}")
        
        print(f"[MIGRATION] Successfully migrated {len(memories)} memories")
        
    except Exception as e:
        print(f"[MIGRATION ERROR] Failed to migrate memories: {e}")

def migrate_onboarding_details(supabase, db):
    """Migrate onboarding details from Supabase to Firebase"""
    print("\n[MIGRATION] Migrating onboarding details...")
    
    try:
        # Get all onboarding details from Supabase
        response = supabase.table('onboarding_details').select('*').execute()
        onboarding_details = response.data
        
        print(f"[MIGRATION] Found {len(onboarding_details)} onboarding details to migrate")
        
        for details in onboarding_details:
            user_id = details['user_id']
            
            # Create onboarding document in Firebase
            onboarding_data = {
                'user_id': user_id,
                'full_name': details.get('full_name', ''),
                'occupation': details.get('occupation', ''),
                'interests': details.get('interests', []),
                'created_at': datetime.utcnow()
            }
            
            db.collection('onboarding_details').document(user_id).set(onboarding_data)
            print(f"[MIGRATION] Migrated onboarding details for user: {user_id}")
        
        print(f"[MIGRATION] Successfully migrated {len(onboarding_details)} onboarding details")
        
    except Exception as e:
        print(f"[MIGRATION ERROR] Failed to migrate onboarding details: {e}")

def main():
    """Main migration function"""
    print("🔥 Starting Supabase to Firebase Migration")
    print("=" * 50)
    
    # Initialize clients
    supabase, db = initialize_clients()
    
    if not supabase:
        print("[ERROR] Cannot proceed without Supabase client")
        return
    
    if not db:
        print("[ERROR] Cannot proceed without Firebase client")
        return
    
    # Confirm migration
    response = input("\n⚠️  This will migrate all data from Supabase to Firebase. Continue? (y/N): ")
    if response.lower() != 'y':
        print("Migration cancelled.")
        return
    
    # Run migrations
    migrate_profiles(supabase, db)
    migrate_user_profiles(supabase, db)
    migrate_memories(supabase, db)
    migrate_onboarding_details(supabase, db)
    
    print("\n🎉 Migration completed!")
    print("Next steps:")
    print("1. Update your .env file with Firebase credentials")
    print("2. Replace agent.py with agent_firebase.py")
    print("3. Test the Firebase integration")
    print("4. Update your frontend to use Firebase Auth")

if __name__ == "__main__":
    main()
