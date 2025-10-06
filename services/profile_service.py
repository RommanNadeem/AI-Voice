"""
Profile Service - Handles user profile generation and management
"""

import asyncio
from typing import Optional
from supabase import Client
import openai
from core.validators import can_write_for_current_user, get_current_user_id
from core.config import Config
from infrastructure.connection_pool import get_connection_pool_sync
from infrastructure.redis_cache import get_redis_cache


class ProfileService:
    """Service for user profile operations"""
    
    def __init__(self, supabase_client: Optional[Client] = None):
        self.supabase = supabase_client
    
    def generate_profile(self, user_input: str, existing_profile: str = "") -> str:
        """
        Generate or update comprehensive user profile using OpenAI.
        
        Args:
            user_input: New information to incorporate
            existing_profile: Current profile text
            
        Returns:
            Generated profile text or existing profile if generation fails
        """
        if not user_input or not user_input.strip():
            return existing_profile
        
        try:
            # Use pooled OpenAI client
            pool = get_connection_pool_sync()
            client = pool.get_openai_client() if pool else openai.OpenAI(api_key=Config.OPENAI_API_KEY)
            
            prompt = f"""
            {"Update and enhance" if existing_profile else "Create"} a comprehensive 4-5 line user profile that captures their persona. Focus on:
            
            - Interests & Hobbies (what they like, enjoy doing)
            - Goals & Aspirations (what they want to achieve)
            - Family & Relationships (important people in their life)
            - Personality Traits (core characteristics, values, beliefs)
            - Important Life Details (profession, background, experiences)
            
            {"Existing profile: " + existing_profile if existing_profile else ""}
            
            New information: "{user_input}"
            
            {"Merge the new information with the existing profile, keeping all important details while adding new insights." if existing_profile else "Create a new profile from this information."}
            
            Format: Write 4-5 concise, flowing sentences that paint a complete picture of who this person is.
            Style: Natural, descriptive, like a character summary.
            
            Return only the profile text (4-5 sentences). If no meaningful information is found, return "NO_PROFILE_INFO".
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"You are an expert at creating and updating comprehensive user profiles. {'Update and merge' if existing_profile else 'Create'} a 4-5 sentence persona summary that captures the user's complete personality, interests, goals, and important life details."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            profile = response.choices[0].message.content.strip()
            
            if profile == "NO_PROFILE_INFO" or len(profile) < 20:
                print(f"[PROFILE SERVICE] No meaningful profile info found in: {user_input[:50]}...")
                return existing_profile
            
            print(f"[PROFILE SERVICE] {'Updated' if existing_profile else 'Generated'} profile")
            return profile
            
        except Exception as e:
            print(f"[PROFILE SERVICE] generate_profile failed: {e}")
            return existing_profile
    
    def save_profile(self, profile_text: str, user_id: Optional[str] = None) -> bool:
        """
        Save user profile to Supabase (sync version).
        
        Args:
            profile_text: Profile text to save
            user_id: Optional user ID (uses current user if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        if not can_write_for_current_user():
            return False
        
        uid = user_id or get_current_user_id()
        if not uid:
            return False
        
        try:
            resp = self.supabase.table("user_profiles").upsert({
                "user_id": uid,
                "profile_text": profile_text,
            }).execute()
            if getattr(resp, "error", None):
                print(f"[PROFILE SERVICE] Save error: {resp.error}")
                return False
            print(f"[PROFILE SERVICE] Saved profile for user {uid}")
            return True
        except Exception as e:
            print(f"[PROFILE SERVICE] save_profile failed: {e}")
            return False
    
    async def save_profile_async(self, profile_text: str, user_id: Optional[str] = None) -> bool:
        """
        Save user profile to Supabase and invalidate Redis cache (async version).
        
        Args:
            profile_text: Profile text to save
            user_id: Optional user ID (uses current user if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        if not can_write_for_current_user():
            return False
        
        uid = user_id or get_current_user_id()
        if not uid:
            return False
        
        try:
            resp = await asyncio.to_thread(
                lambda: self.supabase.table("user_profiles").upsert({
                    "user_id": uid,
                    "profile_text": profile_text,
                }).execute()
            )
            if getattr(resp, "error", None):
                print(f"[PROFILE SERVICE] Save error: {resp.error}")
                return False
            
            # Invalidate Redis cache
            redis_cache = await get_redis_cache()
            cache_key = f"user:{uid}:profile"
            await redis_cache.delete(cache_key)
            print(f"[PROFILE SERVICE] Saved profile for user {uid} (cache invalidated)")
            
            return True
        except Exception as e:
            print(f"[PROFILE SERVICE] save_profile_async failed: {e}")
            return False
    
    def get_profile(self, user_id: Optional[str] = None) -> str:
        """
        Get user profile from Supabase (sync version).
        
        Args:
            user_id: Optional user ID (uses current user if not provided)
            
        Returns:
            Profile text or empty string
        """
        if not can_write_for_current_user():
            return ""
        
        uid = user_id or get_current_user_id()
        if not uid:
            return ""
        
        try:
            resp = self.supabase.table("user_profiles").select("profile_text").eq("user_id", uid).execute()
            if getattr(resp, "error", None):
                print(f"[PROFILE SERVICE] Get error: {resp.error}")
                return ""
            data = getattr(resp, "data", []) or []
            return data[0].get("profile_text", "") if data else ""
        except Exception as e:
            print(f"[PROFILE SERVICE] get_profile failed: {e}")
            return ""
    
    async def get_profile_async(self, user_id: Optional[str] = None) -> str:
        """
        Get user profile from Redis cache or Supabase (async version).
        
        Args:
            user_id: Optional user ID (uses current user if not provided)
            
        Returns:
            Profile text or empty string
        """
        if not can_write_for_current_user():
            return ""
        
        uid = user_id or get_current_user_id()
        if not uid:
            return ""
        
        # Try Redis cache first
        redis_cache = await get_redis_cache()
        cache_key = f"user:{uid}:profile"
        cached_profile = await redis_cache.get(cache_key)
        
        if cached_profile is not None:
            print(f"[PROFILE SERVICE] Cache hit for user {uid}")
            return cached_profile
        
        # Cache miss - fetch from Supabase
        try:
            resp = await asyncio.to_thread(
                lambda: self.supabase.table("user_profiles").select("profile_text").eq("user_id", uid).execute()
            )
            if getattr(resp, "error", None):
                print(f"[PROFILE SERVICE] Get error: {resp.error}")
                return ""
            data = getattr(resp, "data", []) or []
            if data:
                profile = data[0].get("profile_text", "") or ""
                # Cache for 1 hour
                await redis_cache.set(cache_key, profile, ttl=3600)
                print(f"[PROFILE SERVICE] Cached profile for user {uid}")
                return profile
            return ""
        except Exception as e:
            print(f"[PROFILE SERVICE] get_profile_async failed: {e}")
            return ""

