"""
Onboarding Service - Handles new user initialization from onboarding data
"""

from typing import Optional
from supabase import Client
from core.validators import get_current_user_id
from core.config import Config


class OnboardingService:
    """Service for user onboarding operations"""
    
    def __init__(self, supabase_client: Optional[Client] = None):
        self.supabase = supabase_client
    
    async def initialize_user_from_onboarding(self, user_id: str):
        """
        Initialize new user profile and memories from onboarding_details table.
        Creates initial profile and categorized memories for name, occupation, and interests.
        
        Args:
            user_id: User UUID
        """
        if not self.supabase or not user_id:
            return
        
        try:
            print(f"[ONBOARDING SERVICE] Checking if user {user_id} needs initialization...")
            
            # Check if profile already exists
            profile_resp = self.supabase.table("user_profiles").select("profile_text").eq("user_id", user_id).execute()
            has_profile = bool(profile_resp.data)
            
            # Check if memories already exist
            memory_resp = self.supabase.table("memory").select("id").eq("user_id", user_id).limit(1).execute()
            has_memories = bool(memory_resp.data)
            
            if has_profile and has_memories:
                print(f"[ONBOARDING SERVICE] User already initialized, skipping")
                return
            
            # Fetch onboarding details
            result = self.supabase.table("onboarding_details").select("full_name, occupation, interests").eq("user_id", user_id).execute()
            
            if not result.data:
                print(f"[ONBOARDING SERVICE] No onboarding data found for user {user_id}")
                return
            
            onboarding = result.data[0]
            full_name = onboarding.get("full_name", "")
            occupation = onboarding.get("occupation", "")
            interests = onboarding.get("interests", "")
            
            print(f"[ONBOARDING SERVICE] Found data - Name: {full_name}, Occupation: {occupation}")
            
            # Import services here to avoid circular dependency
            from services.profile_service import ProfileService
            from services.memory_service import MemoryService
            from rag_system import get_or_create_rag
            
            profile_service = ProfileService(self.supabase)
            memory_service = MemoryService(self.supabase)
            
            # Detect gender from name for appropriate pronoun usage (will be stored with other memories)
            gender_info = None
            if full_name:
                try:
                    gender_info = await profile_service.detect_gender_from_name(full_name, user_id)
                    print(f"[ONBOARDING SERVICE] Gender detected: {gender_info['gender']} ({gender_info['pronouns']})")
                except Exception as e:
                    print(f"[ONBOARDING SERVICE] Gender detection failed: {e}")
            
            # Create initial profile from onboarding data
            if not has_profile and any([full_name, occupation, interests]):
                profile_parts = []
                
                if full_name:
                    profile_parts.append(f"Their name is {full_name}.")
                
                if occupation:
                    profile_parts.append(f"They work as {occupation}.")
                
                if interests:
                    profile_parts.append(f"Their interests include: {interests}.")
                
                initial_profile = " ".join(profile_parts)
                
                # Use AI to create a more natural profile
                enhanced_profile = profile_service.generate_profile(
                    f"Name: {full_name}. Occupation: {occupation}. Interests: {interests}",
                    ""
                )
                
                profile_to_save = enhanced_profile if enhanced_profile else initial_profile
                
                if profile_service.save_profile(profile_to_save, user_id):
                    print(f"[ONBOARDING SERVICE] ✓ Created initial profile")
            
            # Add memories for each onboarding field
            if not has_memories:
                memories_added = 0
                rag = get_or_create_rag(user_id, Config.OPENAI_API_KEY)
                
                if full_name:
                    # Store name
                    if memory_service.save_memory("FACT", "full_name", full_name, user_id):
                        memories_added += 1
                        rag.add_memory_background(f"User's name is {full_name}", "FACT")
                    
                    # Store detected gender and pronouns
                    if gender_info:
                        if memory_service.save_memory("FACT", "gender", gender_info['gender'], user_id):
                            memories_added += 1
                            rag.add_memory_background(f"User's gender is {gender_info['gender']}", "FACT")
                        
                        if memory_service.save_memory("PREFERENCE", "pronouns", gender_info['pronouns'], user_id):
                            memories_added += 1
                            rag.add_memory_background(f"Use {gender_info['pronouns']} pronouns for user", "PREFERENCE")
                        
                        print(f"[ONBOARDING SERVICE] ✓ Stored gender: {gender_info['gender']} ({gender_info['pronouns']})")
                
                if occupation:
                    if memory_service.save_memory("FACT", "occupation", occupation, user_id):
                        memories_added += 1
                        rag.add_memory_background(f"User works as {occupation}", "FACT")
                
                if interests:
                    # Split interests if comma-separated
                    interest_list = [i.strip() for i in interests.split(',') if i.strip()]
                    
                    if interest_list:
                        # Save all interests as one memory
                        interests_text = ", ".join(interest_list)
                        if memory_service.save_memory("INTEREST", "main_interests", interests_text, user_id):
                            memories_added += 1
                        
                        # Add each interest to RAG for better semantic search
                        for interest in interest_list:
                            rag.add_memory_background(f"User is interested in {interest}", "INTEREST")
                
                print(f"[ONBOARDING SERVICE] ✓ Created {memories_added} memories from onboarding data")
            
            print(f"[ONBOARDING SERVICE] ✓ User initialization complete")
            
        except Exception as e:
            print(f"[ONBOARDING SERVICE] initialize_user_from_onboarding failed: {e}")

