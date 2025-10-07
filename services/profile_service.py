"""
Profile Service - Handles user profile generation and management
"""

import asyncio
import json
from typing import Optional, Dict
from supabase import Client
import openai
from core.validators import can_write_for_current_user, get_current_user_id
from core.config import Config
from infrastructure.connection_pool import get_connection_pool_sync, get_connection_pool
from infrastructure.redis_cache import get_redis_cache


class ProfileService:
    """Service for user profile operations"""
    
    def __init__(self, supabase_client: Optional[Client] = None):
        self.supabase = supabase_client
    
    def generate_profile(self, user_input: str, existing_profile: str = "") -> str:
        """
        Generate or update comprehensive user profile using OpenAI.
        OPTIMIZED: Skip generation for trivial inputs or when profile is complete.
        
        Args:
            user_input: New information to incorporate
            existing_profile: Current profile text
            
        Returns:
            Generated profile text or existing profile if generation fails
        """
        if not user_input or not user_input.strip():
            return existing_profile
        
        # OPTIMIZATION: Skip profile generation for short/trivial inputs
        if len(user_input.strip()) < 15:
            return existing_profile
        
        # OPTIMIZATION: Skip if profile is long enough and input seems trivial
        if existing_profile and len(existing_profile) > 200:
            # Check if input contains meaningful profile information
            trivial_patterns = ["ok", "okay", "yes", "no", "haan", "nahi", "achha", "theek"]
            if user_input.lower().strip() in trivial_patterns:
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
                print(f"[PROFILE SERVICE] ℹ️  No meaningful profile info found in: {user_input[:50]}...")
                return existing_profile
            
            print(f"[PROFILE SERVICE] ✅ {'Updated' if existing_profile else 'Generated'} profile:")
            print(f"[PROFILE SERVICE]    {profile[:150]}{'...' if len(profile) > 150 else ''}")
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
            print(f"[PROFILE SERVICE] 💾 Saving profile for user {uid[:8]}...")
            print(f"[PROFILE SERVICE]    {profile_text[:150]}{'...' if len(profile_text) > 150 else ''}")
            
            resp = self.supabase.table("user_profiles").upsert({
                "user_id": uid,
                "profile_text": profile_text,
            }).execute()
            if getattr(resp, "error", None):
                print(f"[PROFILE SERVICE] ❌ Save error: {resp.error}")
                return False
            print(f"[PROFILE SERVICE] ✅ Profile saved successfully")
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
            print(f"[PROFILE SERVICE] ✅ Profile saved successfully (cache invalidated)")
            print(f"[PROFILE SERVICE]    User: {uid[:8]}...")
            
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
            print(f"[PROFILE SERVICE] 🔍 Fetching profile for user {uid[:8]}...")
            
            resp = self.supabase.table("user_profiles").select("profile_text").eq("user_id", uid).execute()
            if getattr(resp, "error", None):
                print(f"[PROFILE SERVICE] ❌ Fetch error: {resp.error}")
                return ""
            data = getattr(resp, "data", []) or []
            
            if data:
                profile = data[0].get("profile_text", "")
                print(f"[PROFILE SERVICE] ✅ Profile found: {profile[:100]}{'...' if len(profile) > 100 else ''}")
                return profile
            else:
                print(f"[PROFILE SERVICE] ℹ️  No profile found yet")
                return ""
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
        print(f"[PROFILE SERVICE] 🔍 Fetching profile (async) for user {uid[:8]}...")
        redis_cache = await get_redis_cache()
        cache_key = f"user:{uid}:profile"
        cached_profile = await redis_cache.get(cache_key)
        
        if cached_profile is not None:
            print(f"[PROFILE SERVICE] ✅ Cache hit - profile found in Redis")
            print(f"[PROFILE SERVICE]    {cached_profile[:100]}{'...' if len(cached_profile) > 100 else ''}")
            return cached_profile
        
        # Cache miss - fetch from Supabase
        print(f"[PROFILE SERVICE] ℹ️  Cache miss - fetching from database...")
        try:
            resp = await asyncio.to_thread(
                lambda: self.supabase.table("user_profiles").select("profile_text").eq("user_id", uid).execute()
            )
            if getattr(resp, "error", None):
                print(f"[PROFILE SERVICE] ❌ Fetch error: {resp.error}")
                return ""
            data = getattr(resp, "data", []) or []
            if data:
                profile = data[0].get("profile_text", "") or ""
                # Cache for 1 hour
                await redis_cache.set(cache_key, profile, ttl=3600)
                print(f"[PROFILE SERVICE] ✅ Profile fetched from DB and cached")
                print(f"[PROFILE SERVICE]    {profile[:100]}{'...' if len(profile) > 100 else ''}")
                return profile
            print(f"[PROFILE SERVICE] ℹ️  No profile found in database yet")
            return ""
        except Exception as e:
            print(f"[PROFILE SERVICE] get_profile_async failed: {e}")
            return ""
    
    async def get_display_name_async(self, user_id: str) -> Optional[str]:
        """
        Get user's display name from profile (async version).
        
        Args:
            user_id: User ID (explicit, required)
            
        Returns:
            Display name or None
        """
        if not user_id:
            return None
        
        try:
            resp = await asyncio.to_thread(
                lambda: self.supabase.table("user_profiles").select("display_name")
                    .eq("user_id", user_id)
                    .execute()
            )
            if getattr(resp, "error", None):
                return None
            data = getattr(resp, "data", []) or []
            return data[0].get("display_name") if data else None
        except Exception as e:
            print(f"[PROFILE SERVICE] get_display_name_async failed: {e}")
            return None
    
    async def detect_gender_from_name(self, name: str, user_id: Optional[str] = None) -> Dict[str, str]:
        """
        Detect likely gender from user's name using OpenAI.
        Returns gender prediction for appropriate pronoun usage.
        
        Args:
            name: User's full name or first name
            user_id: Optional user ID for caching
            
        Returns:
            Dict with gender ("male", "female", "neutral"), confidence, and pronouns
        """
        if not name or not name.strip():
            return {
                "gender": "neutral",
                "confidence": "unknown",
                "pronouns": "they/them",
                "reason": "No name provided"
            }
        
        uid = user_id or get_current_user_id()
        
        # Try Redis cache first
        if uid:
            try:
                redis_cache = await get_redis_cache()
                cache_key = f"user:{uid}:gender_detection"
                cached_result = await redis_cache.get(cache_key)
                
                if cached_result:
                    print(f"[PROFILE SERVICE] Gender cache hit for {name}")
                    return cached_result
            except Exception as e:
                print(f"[PROFILE SERVICE] Cache check failed: {e}")
        
        try:
            # Use pooled async OpenAI client
            pool = await get_connection_pool()
            client = pool.get_openai_client(async_client=True)
            
            prompt = f"""
Based on the name "{name}", determine the most likely gender for appropriate pronoun usage in conversation.

Consider:
- Cultural name patterns (South Asian, Arabic, Western, etc.)
- Common gender associations with names
- Return "neutral" if uncertain or gender-neutral name

Respond in JSON format:
{{
    "gender": "male" | "female" | "neutral",
    "confidence": "high" | "medium" | "low",
    "pronouns": "he/him" | "she/her" | "they/them",
    "reason": "brief explanation"
}}
"""
            
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that identifies likely gender from names for pronoun selection. Be respectful and default to neutral when uncertain. Always respond with valid JSON."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3,
                    max_tokens=150,
                    timeout=3.0
                ),
                timeout=3.0
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Validate result
            valid_genders = ["male", "female", "neutral"]
            if result.get("gender") not in valid_genders:
                result["gender"] = "neutral"
            
            # Ensure pronouns are set
            if "pronouns" not in result:
                result["pronouns"] = {
                    "male": "he/him",
                    "female": "she/her",
                    "neutral": "they/them"
                }.get(result["gender"], "they/them")
            
            print(f"[PROFILE SERVICE] Gender detected for '{name}': {result['gender']} ({result.get('confidence', 'unknown')} confidence)")
            
            # Cache result for 30 days (gender from name is stable)
            if uid:
                try:
                    redis_cache = await get_redis_cache()
                    cache_key = f"user:{uid}:gender_detection"
                    await redis_cache.set(cache_key, result, ttl=2592000)  # 30 days
                except Exception as e:
                    print(f"[PROFILE SERVICE] Cache save failed: {e}")
            
            return result
            
        except asyncio.TimeoutError:
            print(f"[PROFILE SERVICE] Gender detection timeout for '{name}'")
            return {
                "gender": "neutral",
                "confidence": "unknown",
                "pronouns": "they/them",
                "reason": "Detection timeout"
            }
        except Exception as e:
            print(f"[PROFILE SERVICE] detect_gender_from_name failed: {e}")
            return {
                "gender": "neutral",
                "confidence": "unknown",
                "pronouns": "they/them",
                "reason": f"Error: {str(e)}"
            }

