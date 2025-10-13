"""
Onboarding Service - Handles new user initialization from onboarding data
"""

import logging
from typing import Optional
from supabase import Client
from core.validators import get_current_user_id
from core.user_id import UserId, UserIdError
from core.config import Config

logger = logging.getLogger(__name__)


class OnboardingService:
    """Service for user onboarding operations"""
    
    # Class-level cache to track which users have been initialized this session
    _initialized_users = set()
    
    def __init__(self, supabase_client: Optional[Client] = None):
        self.supabase = supabase_client
    
    async def initialize_user_from_onboarding(self, user_id: str):
        """
        Initialize new user profile and memories from onboarding_details table.
        Creates initial profile and categorized memories for name, occupation, and interests.
        
        OPTIMIZED: Uses session-level cache to skip DB checks for already-initialized users.
        
        Args:
            user_id: User UUID
        """
        if not self.supabase or not user_id:
            return
        
        try:
            # OPTIMIZATION: Check session cache first (instant, no DB query)
            if user_id in self._initialized_users:
                logger.info(f"✓ User {UserId.format_for_display(user_id)} already checked this session (cached), skipping")
                return
            
            logger.info(f"🔄 Checking if user {UserId.format_for_display(user_id)} needs initialization...")
            
            # Check if profile already exists
            profile_resp = self.supabase.table("user_profiles").select("profile_text").eq("user_id", user_id).execute()
            has_profile = bool(profile_resp.data)
            logger.info(f"  Profile exists: {has_profile}")
            
            # Check if memories already exist
            memory_resp = self.supabase.table("memory").select("id").eq("user_id", user_id).limit(1).execute()
            has_memories = bool(memory_resp.data)
            logger.info(f"  Memories exist: {has_memories}")
            
            if has_profile and has_memories:
                logger.info(f"✓ User already fully initialized, skipping")
                # Add to cache so we don't check again this session
                self._initialized_users.add(user_id)
                return
            
            if not has_profile:
                logger.warning(f"⚠️  Missing user_profiles row - will create")
            if not has_memories:
                logger.warning(f"⚠️  Missing memories - will create")
            
            # Fetch onboarding details
            result = self.supabase.table("onboarding_details").select("full_name, gender, occupation, interests").eq("user_id", user_id).execute()
            
            if not result.data:
                logger.error(f"❌ No onboarding_details found for user {UserId.format_for_display(user_id)}")
                logger.error(f"   User needs to complete onboarding first")
                return
            
            onboarding = result.data[0]
            full_name = onboarding.get("full_name", "")
            gender = onboarding.get("gender", "")
            occupation = onboarding.get("occupation", "")
            interests = onboarding.get("interests", "")
            
            logger.info(f"✓ Found onboarding data:")
            logger.info(f"  Name: {full_name}")
            logger.info(f"  Gender: {gender}")
            logger.info(f"  Occupation: {occupation}")
            logger.info(f"  Interests: {interests}")
            
            # Import services here to avoid circular dependency
            from services.profile_service import ProfileService
            from services.memory_service import MemoryService
            from rag_system import get_or_create_rag
            
            profile_service = ProfileService(self.supabase)
            memory_service = MemoryService(self.supabase)
            
            # Determine pronouns from gender (stored with other memories)
            gender_info = None
            if gender:
                # Map gender to pronouns
                pronouns_map = {
                    "male": "he/him",
                    "female": "she/her",
                    "non-binary": "they/them",
                    "other": "they/them"
                }
                pronouns = pronouns_map.get(gender.lower(), "they/them")
                gender_info = {
                    "gender": gender,
                    "pronouns": pronouns
                }
                logger.info(f"✓ Gender info: {gender} ({pronouns})")
            
            # Create initial profile from onboarding data using async 250-char generator
            if not has_profile and any([full_name, occupation, interests]):
                try:
                    created = await profile_service.create_profile_from_onboarding_async(user_id)
                    if created:
                        logger.info(f"✓ Created initial profile (<=250 chars)")
                except Exception as e:
                    logger.error(f"Failed to create initial profile: {e}")
            
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
                        
                        logger.info(f"✓ Stored gender: {gender_info['gender']} ({gender_info['pronouns']})")
                
                if occupation:
                    if memory_service.save_memory("FACT", "occupation", occupation, user_id):
                        memories_added += 1
                        rag.add_memory_background(f"User works as {occupation}", "FACT")
                
            if interests:
                # Handle interests as either list or string
                if isinstance(interests, list):
                    interest_list = [str(i).strip() for i in interests if i]
                else:
                    # Split comma-separated string
                    interest_list = [i.strip() for i in str(interests).split(',') if i.strip()]
                
                if interest_list:
                    # Save all interests as one memory
                    interests_text = ", ".join(interest_list)
                    if memory_service.save_memory("INTEREST", "main_interests", interests_text, user_id):
                        memories_added += 1
                    
                    # Add each interest to RAG for better semantic search
                    for interest in interest_list:
                        rag.add_memory_background(f"User is interested in {interest}", "INTEREST")
                
                logger.info(f"✓ Created {memories_added} memories from onboarding data")
            
            logger.info(f"✓ User initialization complete")
            
            # Add to session cache after successful initialization
            self._initialized_users.add(user_id)
            
        except Exception as e:
            logger.error(f"initialize_user_from_onboarding failed: {e}", exc_info=True)

