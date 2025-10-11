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
from services.user_service import UserService


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
        
        # OPTIMIZATION: Skip profile generation for very short inputs (reduced from 15 to 5)
        if len(user_input.strip()) < 5:
            return existing_profile
        
        # OPTIMIZATION: Skip only single-word trivial responses
        if existing_profile and len(existing_profile) > 200:
            # Check if input is a single trivial word
            trivial_patterns = ["ok", "okay", "yes", "no", "haan", "nahi"]
            if user_input.lower().strip() in trivial_patterns:
                return existing_profile
        
        try:
            # Use pooled OpenAI client
            pool = get_connection_pool_sync()
            client = pool.get_openai_client() if pool else openai.OpenAI(api_key=Config.OPENAI_API_KEY)
            
            prompt = f"""
            {"Update" if existing_profile else "Create"} a concise 3-4 line user profile that captures ONLY the most essential information about their persona.
            
            CRITICAL RULES:
            1. ONLY include information that is explicitly stated in the user's input - DO NOT infer, assume, or add anything on your own
            2. DO NOT add information that is not directly verifiable from what the user said
            3. Focus ONLY on the most important details - skip minor or trivial information
            4. Be selective - quality over quantity
            
            Priority information (only if explicitly mentioned):
            - Core interests & passions (not casual mentions)
            - Significant goals or life aspirations
            - Important relationships or family (key people only)
            - Defining personality traits or values
            - Critical life details (profession, major life events)
            
            {"Existing profile: " + existing_profile if existing_profile else ""}
            
            New information: "{user_input}"
            
            {"Carefully merge ONLY the important new information with the existing profile. Keep it concise and factual." if existing_profile else "Create a profile from ONLY the important information provided."}
            
            Format: Write 3-4 concise sentences with ONLY verified, important facts.
            Style: Factual and natural - like essential notes about the person.
            
            Return only the profile text (3-4 sentences). If no meaningful information is found, return "NO_PROFILE_INFO".
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"You are an expert at creating concise, factual user profiles. {'Update' if existing_profile else 'Create'} a 3-4 sentence profile with ONLY the most important information explicitly provided by the user. Never infer, assume, or add information that wasn't directly stated. Be selective and truthful."},
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
            # Ensure FK parent exists in profiles table
            user_service = UserService(self.supabase)
            if not user_service.ensure_profile_exists(uid):
                print(f"[PROFILE SERVICE] ❌ Cannot save profile - missing parent row in profiles for {uid[:8]}")
                return False
            
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
        🚀 OPTIMIZED: Save user profile with smart caching - only updates if content changed significantly.
        Reduces unnecessary DB writes and prevents cache thrashing.
        
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
            # 🚀 OPTIMIZATION: Check if profile actually changed before saving
            redis_cache = await get_redis_cache()
            cache_key = f"user:{uid}:profile"
            cached_profile = await redis_cache.get(cache_key)
            
            # Compare profiles - skip if identical or trivially different
            if cached_profile and self._is_profile_unchanged(cached_profile, profile_text):
                print(f"[PROFILE SERVICE] ℹ️  Profile unchanged, skipping save (smart cache)")
                print(f"[PROFILE SERVICE]    Similarity: 95%+, avoiding unnecessary DB write")
                return True
            
            # Ensure FK parent exists in profiles table before saving to user_profiles
            user_service = UserService(self.supabase)
            if not user_service.ensure_profile_exists(uid):
                print(f"[PROFILE SERVICE] ❌ Cannot save profile - missing parent row in profiles for {uid[:8]}")
                return False

            # Profile changed significantly - save to DB
            resp = await asyncio.to_thread(
                lambda: self.supabase.table("user_profiles").upsert({
                    "user_id": uid,
                    "profile_text": profile_text,
                }).execute()
            )
            if getattr(resp, "error", None):
                print(f"[PROFILE SERVICE] Save error: {resp.error}")
                return False
            
            # 🚀 OPTIMIZATION: Update cache instead of deleting (prevents cache miss)
            await redis_cache.set(cache_key, profile_text, ttl=3600)
            print(f"[PROFILE SERVICE] ✅ Profile saved and cache updated (smart)")
            print(f"[PROFILE SERVICE]    User: {uid[:8]}...")
            
            return True
        except Exception as e:
            print(f"[PROFILE SERVICE] save_profile_async failed: {e}")
            return False
    
    def _is_profile_unchanged(self, old: str, new: str) -> bool:
        """
        🚀 OPTIMIZATION: Check if two profiles are substantially the same.
        Returns True if no significant change detected (>95% similar).
        
        This prevents unnecessary DB writes and cache invalidation for trivial changes.
        """
        # Normalize whitespace for fair comparison
        old_norm = " ".join(old.split())
        new_norm = " ".join(new.split())
        
        # Exact match - definitely unchanged
        if old_norm == new_norm:
            return True
        
        # Check length difference
        if len(old_norm) == 0:
            return False
        
        len_diff_pct = abs(len(new_norm) - len(old_norm)) / len(old_norm)
        
        # If length changed by more than 10%, consider it changed (relaxed from 5%)
        if len_diff_pct > 0.10:
            return False
        
        # Small length change - check word-level similarity
        old_words = set(old_norm.lower().split())
        new_words = set(new_norm.lower().split())
        
        if len(old_words) == 0:
            return False
        
        overlap = len(old_words & new_words)
        total = max(len(old_words), len(new_words))
        similarity = overlap / total if total > 0 else 0
        
        # If 90%+ similar, consider unchanged (relaxed from 95%)
        is_similar = similarity > 0.90
        
        if is_similar:
            print(f"[PROFILE SERVICE] Profile similarity: {similarity*100:.1f}% (threshold: 90%)")
        
        return is_similar
    
    async def create_profile_from_onboarding_async(self, user_id: str) -> bool:
        """
        Create and save a concise (<=250 chars) profile_text from onboarding_details
        using OpenAI. Skips if no onboarding data or profile already exists.
        """
        if not user_id:
            return False
        if not self.supabase:
            return False
        
        try:
            # If a profile already exists and is non-empty, skip
            existing = await self.get_profile_async(user_id)
            if existing and existing.strip():
                return True
            
            # Fetch onboarding_details: full_name, gender, occupation, interests
            import asyncio
            result = await asyncio.to_thread(
                lambda: self.supabase.table("onboarding_details")
                    .select("full_name, gender, occupation, interests")
                    .eq("user_id", user_id)
                    .limit(1)
                    .execute()
            )
            data = getattr(result, "data", []) or []
            if not data:
                return False
            ob = data[0]
            full_name = (ob.get("full_name") or "").strip()
            gender = (ob.get("gender") or "").strip()
            occupation = (ob.get("occupation") or "").strip()
            
            # Handle interests as either list or string
            interests_raw = ob.get("interests")
            if isinstance(interests_raw, list):
                interests = ", ".join(str(i) for i in interests_raw if i)
            else:
                interests = (interests_raw or "").strip()
            
            if not any([full_name, gender, occupation, interests]):
                return False
            
            # Ensure parent profile row exists
            user_service = UserService(self.supabase)
            if not user_service.ensure_profile_exists(user_id):
                return False
            
            # Use pooled OpenAI client
            pool = get_connection_pool_sync()
            client = pool.get_openai_client() if pool else openai.OpenAI(api_key=Config.OPENAI_API_KEY)
            
            # Build concise prompt for <=250 chars, factual only from provided fields
            fields_text = (
                f"Name: {full_name}. " if full_name else ""
            ) + (
                f"Gender: {gender}. " if gender else ""
            ) + (
                f"Occupation: {occupation}. " if occupation else ""
            ) + (
                f"Interests: {interests}." if interests else ""
            )
            
            sys_msg = (
                "You write a single compact profile line (<=250 characters). "
                "ONLY use the provided facts; do not infer or add information. "
                "Return plain text without headings."
            )
            user_msg = (
                "Create a concise 250-character profile that includes available fields: "
                "name, gender, occupation, interests. Keep natural and factual.\n\n"
                f"Facts: {fields_text}"
            )
            
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=120,
                temperature=0.2,
            )
            profile_text = (resp.choices[0].message.content or "").strip()
            if len(profile_text) > 250:
                profile_text = profile_text[:250]
            if not profile_text:
                return False
            
            # Save to user_profiles.profile_text (async, cached)
            saved = await self.save_profile_async(profile_text, user_id)
            return saved
        except Exception as e:
            print(f"[PROFILE SERVICE] create_profile_from_onboarding_async failed: {e}")
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
    
