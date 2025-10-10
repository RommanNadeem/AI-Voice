"""
Conversation Service - Handles conversation continuity and greeting logic
"""

import asyncio
import json
from typing import Dict, List, Optional
from datetime import datetime
from supabase import Client
from infrastructure.connection_pool import get_connection_pool
from infrastructure.redis_cache import get_redis_cache


class ConversationService:
    """Service for conversation-related operations"""
    
    def __init__(self, supabase_client: Optional[Client] = None):
        self.supabase = supabase_client
    
    async def get_last_conversation_context(self, user_id: str) -> Dict:
        """
        Retrieve last conversation context for continuity analysis.
        
        Args:
            user_id: User UUID
            
        Returns:
            Dict with conversation context including messages and timestamps
        """
        if not self.supabase:
            return {"has_history": False}
        
        try:
            print(f"[CONVERSATION SERVICE] Retrieving last conversation for user {user_id}...")
            
            # Get last 5 user messages
            result = self.supabase.table("memory")\
                .select("value, created_at")\
                .eq("user_id", user_id)\
                .not_.like("key", "user_input_%")\
                .order("created_at", desc=True)\
                .limit(5)\
                .execute()
            
            if not result.data:
                print(f"[CONVERSATION SERVICE] No previous conversation found")
                return {"has_history": False}
            
            messages = [m["value"] for m in result.data]
            
            # Calculate time since last message
            last_timestamp = result.data[0]["created_at"]
            
            try:
                last_time = datetime.fromisoformat(last_timestamp.replace('Z', '+00:00'))
                hours_since = (datetime.now(last_time.tzinfo) - last_time).total_seconds() / 3600
            except:
                hours_since = 999  # Very old
            
            print(f"[CONVERSATION SERVICE] Found {len(messages)} messages, last {hours_since:.1f} hours ago")
            
            return {
                "has_history": True,
                "last_messages": messages,
                "time_since_last_hours": hours_since,
                "most_recent": messages[0],
                "last_timestamp": last_timestamp
            }
            
        except Exception as e:
            print(f"[CONVERSATION SERVICE] get_last_conversation_context failed: {e}")
            return {"has_history": False}
    
    async def analyze_conversation_continuity(
        self,
        last_messages: List[str],
        time_hours: float,
        user_profile: str
    ) -> Dict:
        """
        Use AI to decide if follow-up is appropriate.
        
        Args:
            last_messages: Recent conversation messages
            time_hours: Hours since last conversation
            user_profile: User profile text
            
        Returns:
            Dict with decision, confidence, reason, and suggested opening
        """
        try:
            # Use pooled async OpenAI client
            pool = await get_connection_pool()
            client = pool.get_openai_client(async_client=True)
            
            # Format messages for analysis
            messages_text = "\n".join([f"{i+1}. {msg}" for i, msg in enumerate(reversed(last_messages[:3]))])
            
            prompt = f"""
Analyze if a follow-up greeting is appropriate for this conversation:

USER PROFILE:
{user_profile[:300] if user_profile else "No profile available"}

LAST CONVERSATION ({time_hours:.1f} hours ago):
{messages_text}

DECISION CRITERIA:
- FOLLOW-UP if: Unfinished discussion, important topic, emotional weight, < 12 hours
- FRESH START if: Natural ending, casual chat concluded, > 24 hours, goodbye signals

EXAMPLES:
1. "Interview kal hai, nervous" (3hrs ago) → FOLLOW-UP (confidence: 0.9)
2. "Okay bye, baad mein baat karte hain" (6hrs ago) → FRESH START (confidence: 0.8)
3. "Project khatam nahi hua" (2hrs ago) → FOLLOW-UP (confidence: 0.85)
4. "Theek hai thanks" (48hrs ago) → FRESH START (confidence: 0.9)

Respond in JSON format:
{{
    "decision": "FOLLOW_UP" or "FRESH_START",
    "confidence": 0.0-1.0,
    "reason": "brief explanation in English",
    "detected_topic": "main topic discussed",
    "suggested_opening": "what to say in Urdu (only if FOLLOW-UP)"
}}
"""
            
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are an expert at analyzing conversation continuity for natural dialogue flow. Always respond with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3,
                    max_tokens=250,
                    timeout=3.0
                ),
                timeout=3.0
            )
            
            analysis = json.loads(response.choices[0].message.content)
            
            print(f"[CONVERSATION SERVICE] Decision: {analysis.get('decision', 'FRESH_START')} (confidence: {analysis.get('confidence', 0.0):.2f})")
            print(f"[CONVERSATION SERVICE] Reason: {analysis.get('reason', 'Unknown')}")
            
            return analysis
            
        except asyncio.TimeoutError:
            print(f"[CONVERSATION SERVICE] Analysis timeout, defaulting to fresh start")
            return {
                "decision": "FRESH_START",
                "confidence": 0.0,
                "reason": "Analysis timeout"
            }
        except Exception as e:
            print(f"[CONVERSATION SERVICE] analyze_conversation_continuity failed: {e}")
            return {
                "decision": "FRESH_START",
                "confidence": 0.0,
                "reason": f"Analysis error: {str(e)}"
            }
    
    async def get_simple_greeting_instructions(
        self,
        user_id: str,
        assistant_instructions: str
    ) -> str:
        """
        Generate SIMPLE first message instructions using only name + last conversation summary.
        OPTIMIZED for speed - minimal database queries, no AI analysis.
        
        Args:
            user_id: User UUID
            assistant_instructions: Base assistant instructions
            
        Returns:
            Lightweight greeting instructions (name + last conversation summary only)
        """
        try:
            print(f"[CONVERSATION SERVICE] 🚀 Simple greeting generation (name + last convo only)...")
            
            # Check Redis cache for recent greeting
            redis_cache = await get_redis_cache()
            cache_key = f"user:{user_id}:simple_greeting"
            cached_instructions = await redis_cache.get(cache_key)
            
            if cached_instructions:
                print(f"[CONVERSATION SERVICE] ✓ Cache hit for greeting")
                return cached_instructions
            
            # Fetch only name + last conversation (parallel, no profile)
            name_task = self._get_user_name_fast(user_id)
            last_convo_task = self.get_last_conversation_context(user_id)
            
            try:
                user_name, context = await asyncio.wait_for(
                    asyncio.gather(name_task, last_convo_task, return_exceptions=True),
                    timeout=1.0  # Max 1 second
                )
            except asyncio.TimeoutError:
                print(f"[CONVERSATION SERVICE] ⚠️  Timeout, using defaults")
                user_name = None
                context = {"has_history": False}
            
            # Handle exceptions
            if isinstance(user_name, Exception):
                user_name = None
            if isinstance(context, Exception):
                context = {"has_history": False}
            
            # Build simple instructions
            name_text = f"User's name: **{user_name}**\n\n" if user_name else ""
            
            if not context["has_history"]:
                # New user - simple greeting
                print(f"[CONVERSATION SERVICE] ✓ New user - simple greeting")
                instructions = f"""

## First Message - Simple Greeting
{name_text}
This is a new conversation. Start with a warm, welcoming greeting in Urdu. Keep it simple and friendly.

Example: "Assalam-o-alaikum{f" {user_name}" if user_name else ""}! Aaj aap kaise hain?"

"""
            else:
                # Returning user - check if follow-up is appropriate
                hours = context.get("time_since_last_hours", 999)
                last_msg = context.get("most_recent", "")
                
                # Simple heuristic: follow-up if < 12 hours
                if hours < 12:
                    print(f"[CONVERSATION SERVICE] ✓ Follow-up greeting ({hours:.1f}h ago)")
                    instructions = f"""

## First Message - Follow-up
{name_text}
Last conversation was {hours:.1f} hours ago. Last message: "{last_msg[:100]}"

Continue naturally from where you left off. Reference the previous conversation briefly.

Example: "Assalam-o-alaikum{f" {user_name}" if user_name else ""}! Kaisi hain aap? [reference previous topic briefly]"

"""
                else:
                    print(f"[CONVERSATION SERVICE] ✓ Fresh start ({hours:.1f}h ago)")
                    instructions = f"""

## First Message - Fresh Start
{name_text}
Last conversation was {hours:.1f} hours ago (a while back). Start fresh with a warm greeting.

Example: "Assalam-o-alaikum{f" {user_name}" if user_name else ""}! Kaafi time baad baat ho rahi hai. Aap kaise hain?"

"""
            
            # Cache for 2 minutes
            await redis_cache.set(cache_key, instructions, ttl=120)
            return instructions
            
        except Exception as e:
            print(f"[CONVERSATION SERVICE] ❌ get_simple_greeting_instructions failed: {e}")
            return """

## First Message - Fallback
Start with a simple, warm greeting in Urdu.

Example: "Assalam-o-alaikum! Aap kaise hain?"

"""
    
    async def _get_user_name_fast(self, user_id: str) -> Optional[str]:
        """
        Fetch user's name quickly from memory.
        Checks only the most common name key.
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("memory")
                .select("value")
                .eq("user_id", user_id)
                .eq("key", "name")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if result.data:
                name = result.data[0].get("value", None)
                if name:
                    print(f"[CONVERSATION SERVICE] ✓ Name found: '{name}'")
                    return name
            return None
        except Exception as e:
            print(f"[CONVERSATION SERVICE] Name fetch error: {e}")
            return None
    
    async def get_intelligent_greeting_instructions(
        self,
        user_id: str,
        assistant_instructions: str
    ) -> str:
        """
        DEPRECATED: Use get_simple_greeting_instructions() instead for faster first message.
        
        This method does heavy AI analysis and is kept for backward compatibility only.
        """
        print(f"[CONVERSATION SERVICE] ⚠️  Using deprecated get_intelligent_greeting_instructions()")
        print(f"[CONVERSATION SERVICE] ⚠️  Consider using get_simple_greeting_instructions() for faster first message")
        
        # Fallback to simple version
        return await self.get_simple_greeting_instructions(user_id, assistant_instructions)

