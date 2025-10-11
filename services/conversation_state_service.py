"""
Conversation State Service - Manages conversation state and trust progression
Based on Social Penetration Theory for depth and breadth in conversations
"""

import asyncio
import json
from typing import Dict, Optional, Tuple
from datetime import datetime
from supabase import Client
from core.validators import get_current_user_id
from infrastructure.connection_pool import get_connection_pool
from infrastructure.redis_cache import get_redis_cache


# Conversation stages based on Social Penetration Theory
STAGES = [
    "ORIENTATION",    # Safety, comfort, light small talk
    "ENGAGEMENT",     # Explore breadth (work, family, interests)
    "GUIDANCE",       # Go deeper with consent
    "REFLECTION",     # Reflect on progress, set routines
    "INTEGRATION"     # Identity-level insights
]

# Default trust score
DEFAULT_TRUST_SCORE = 2.0
MIN_TRUST = 0.0
MAX_TRUST = 10.0


class ConversationStateService:
    """
    Service for managing conversation state and trust progression.
    
    Implements Social Penetration Theory stages and trust scoring
    to guide natural conversation depth and breadth.
    """
    
    def __init__(self, supabase_client: Optional[Client] = None):
        self.supabase = supabase_client
    
    async def get_state(self, user_id: Optional[str] = None) -> Dict:
        """
        Get current conversation state for user.
        
        Args:
            user_id: Optional user ID (uses current user if not provided)
            
        Returns:
            Dict with stage, trust_score, last_updated, metadata
        """
        uid = user_id or get_current_user_id()
        if not uid or not self.supabase:
            return self._default_state()
        
        try:
            # Try Redis cache first
            redis_cache = await get_redis_cache()
            cache_key = f"user:{uid}:conversation_state"
            cached_state = await redis_cache.get(cache_key)
            
            if cached_state:
                print(f"[STATE SERVICE] Cache hit for user {uid}")
                return cached_state
            
            # Cache miss - fetch from database
            resp = await asyncio.to_thread(
                lambda: self.supabase.table("conversation_state")
                .select("*")
                .eq("user_id", uid)
                .execute()
            )
            
            if getattr(resp, "error", None):
                print(f"[STATE SERVICE] Get error: {resp.error}")
                return self._default_state()
            
            data = getattr(resp, "data", []) or []
            
            if data:
                state = {
                    "stage": data[0].get("stage", "ORIENTATION"),
                    "trust_score": float(data[0].get("trust_score", DEFAULT_TRUST_SCORE)),
                    "last_updated": data[0].get("updated_at"),
                    "metadata": data[0].get("metadata", {}),
                    "stage_history": data[0].get("stage_history", []),
                    "last_summary": data[0].get("last_summary"),
                    "last_topics": data[0].get("last_topics", []),
                    "last_user_message": data[0].get("last_user_message"),
                    "last_assistant_message": data[0].get("last_assistant_message"),
                    "last_conversation_at": data[0].get("last_conversation_at"),
                }
                
                # Cache for 5 minutes
                await redis_cache.set(cache_key, state, ttl=300)
                print(f"[STATE SERVICE] Cached state for user {uid}")
                
                return state
            else:
                # No state exists, return default
                return self._default_state()
                
        except Exception as e:
            print(f"[STATE SERVICE] get_state failed: {e}")
            return self._default_state()
    
    async def update_state(
        self,
        stage: Optional[str] = None,
        trust_score: Optional[float] = None,
        metadata: Optional[Dict] = None,
        user_id: Optional[str] = None,
        last_user_message: Optional[str] = None,
        last_assistant_message: Optional[str] = None
    ) -> bool:
        """
        Update conversation state for user.
        
        Args:
            stage: New conversation stage
            trust_score: New trust score (0-10)
            metadata: Additional metadata to store
            user_id: Optional user ID (uses current user if not provided)
            last_user_message: Last message from user
            last_assistant_message: Last message from assistant
            
        Returns:
            True if successful, False otherwise
        """
        uid = user_id or get_current_user_id()
        if not uid or not self.supabase:
            return False
        
        try:
            # Get current state
            current_state = await self.get_state(uid)
            
            # Validate stage
            if stage and stage not in STAGES:
                print(f"[STATE SERVICE] Invalid stage: {stage}")
                return False
            
            # Validate and clamp trust score
            if trust_score is not None:
                trust_score = max(MIN_TRUST, min(MAX_TRUST, trust_score))
            
            # Build update data
            update_data = {
                "user_id": uid,
                "stage": stage or current_state["stage"],
                "trust_score": trust_score if trust_score is not None else current_state["trust_score"],
                "metadata": metadata or current_state.get("metadata", {}),
                "updated_at": datetime.utcnow().isoformat(),
                "last_conversation_at": datetime.utcnow().isoformat(),
            }
            
            # Add last messages if provided
            if last_user_message is not None:
                update_data["last_user_message"] = last_user_message
            if last_assistant_message is not None:
                update_data["last_assistant_message"] = last_assistant_message
            
            # Track stage history
            stage_history = current_state.get("stage_history", [])
            if stage and stage != current_state["stage"]:
                stage_history.append({
                    "from": current_state["stage"],
                    "to": stage,
                    "timestamp": datetime.utcnow().isoformat(),
                    "trust_score": update_data["trust_score"]
                })
                update_data["stage_history"] = stage_history
            
            # Upsert to database with conflict resolution on user_id
            resp = await asyncio.to_thread(
                lambda: self.supabase.table("conversation_state")
                .upsert(update_data, on_conflict="user_id")
                .execute()
            )
            
            # Check for errors
            error = getattr(resp, "error", None)
            if error:
                error_dict = error if isinstance(error, dict) else {}
                error_code = error_dict.get("code", "")
                error_msg = error_dict.get("message", str(error))
                
                # Special handling for RLS policy violations
                if error_code == "42501":
                    print(f"[STATE SERVICE] ⚠️  RLS Policy Error: Cannot update conversation_state")
                    print(f"[STATE SERVICE] → This happens when using ANON key instead of SERVICE_ROLE key")
                    print(f"[STATE SERVICE] → See CRITICAL_FIXES_APPLIED.md for solution")
                    print(f"[STATE SERVICE] → Continuing without state persistence...")
                    # Continue gracefully - update cache even if DB fails
                    # This allows the system to work with in-memory state
                    pass  # Don't return False
                else:
                    print(f"[STATE SERVICE] update_state failed: {error_dict}")
                    return False
            
            # Invalidate cache (or update it with new state if DB failed)
            redis_cache = await get_redis_cache()
            cache_key = f"user:{uid}:conversation_state"
            
            # If we had an RLS error, at least cache the state so it works in-memory
            if error and error_dict.get("code") == "42501":
                await redis_cache.delete(cache_key)
                # Cache the intended state even though DB update failed
                state_to_cache = {
                    "stage": update_data["stage"],
                    "trust_score": update_data["trust_score"],
                    "last_updated": update_data["updated_at"],
                    "metadata": update_data.get("metadata", {}),
                    "stage_history": update_data.get("stage_history", []),
                }
                await redis_cache.set(cache_key, state_to_cache, ttl=300)
                print(f"[STATE SERVICE] ⚠️  State cached (DB update failed) - Stage: {update_data['stage']}, Trust: {update_data['trust_score']:.1f}")
            else:
                # Normal case - invalidate cache so next read comes from DB
                await redis_cache.delete(cache_key)
                print(f"[STATE SERVICE] Updated state - Stage: {update_data['stage']}, Trust: {update_data['trust_score']:.1f}")
            
            return True
            
        except Exception as e:
            print(f"[STATE SERVICE] update_state failed: {e}")
            return False
    
    async def adjust_trust(
        self,
        delta: float,
        reason: str = "",
        user_id: Optional[str] = None
    ) -> float:
        """
        Adjust trust score by delta amount.
        
        Args:
            delta: Amount to add/subtract from trust score
            reason: Reason for adjustment (for logging)
            user_id: Optional user ID
            
        Returns:
            New trust score
        """
        current_state = await self.get_state(user_id)
        new_trust = max(MIN_TRUST, min(MAX_TRUST, current_state["trust_score"] + delta))
        
        await self.update_state(
            trust_score=new_trust,
            metadata={
                **current_state.get("metadata", {}),
                "last_trust_adjustment": {
                    "delta": delta,
                    "reason": reason,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            },
            user_id=user_id
        )
        
        print(f"[STATE SERVICE] Trust adjusted: {delta:+.1f} ({reason}) -> {new_trust:.1f}")
        return new_trust
    
    async def suggest_stage_transition(
        self,
        user_input: str,
        user_profile: str = "",
        user_id: Optional[str] = None
    ) -> Dict:
        """
        Use AI to analyze if stage transition is appropriate.
        
        Args:
            user_input: Recent user message
            user_profile: User profile context
            user_id: Optional user ID
            
        Returns:
            Dict with suggested_stage, confidence, reason, trust_adjustment
        """
        try:
            # Get current state
            current_state = await self.get_state(user_id)
            current_stage = current_state["stage"]
            current_trust = current_state["trust_score"]
            
            # Don't suggest if already at highest stage
            if current_stage == "INTEGRATION":
                return {
                    "suggested_stage": current_stage,
                    "should_transition": False,
                    "confidence": 1.0,
                    "reason": "Already at highest stage",
                    "trust_adjustment": 0.0
                }
            
            # Use AI to analyze
            pool = await get_connection_pool()
            client = pool.get_openai_client(async_client=True)
            
            # Stage descriptions
            stage_descriptions = {
                "ORIENTATION": "Safety, comfort, light small talk, building rapport",
                "ENGAGEMENT": "Exploring breadth - work, family, interests, habits, general topics",
                "GUIDANCE": "Going deeper with consent - feelings, needs, triggers, offering guidance",
                "REFLECTION": "Reflecting on progress, setting routines, handling obstacles",
                "INTEGRATION": "Identity-level insights, celebrating growth, choosing next focus"
            }
            
            current_stage_desc = stage_descriptions.get(current_stage, "")
            next_stage = STAGES[STAGES.index(current_stage) + 1] if STAGES.index(current_stage) < len(STAGES) - 1 else current_stage
            next_stage_desc = stage_descriptions.get(next_stage, "")
            
            prompt = f"""
Analyze if the user is ready to progress to the next conversation stage.

CURRENT STATE:
- Stage: {current_stage} - {current_stage_desc}
- Trust Score: {current_trust:.1f}/10
- User Profile: {user_profile[:200] if user_profile else "No profile"}

USER'S RECENT MESSAGE:
"{user_input}"

NEXT STAGE:
- {next_stage} - {next_stage_desc}

ANALYSIS CRITERIA:
1. User shows self-disclosure (sharing personal info)
2. User accepts previous guidance or suggestions
3. User requests deeper conversation
4. Trust score is sufficient (>5 for GUIDANCE+)
5. User signals comfort and openness

SIGNS TO STAY:
- User deflects or changes topic
- Gives short/closed responses
- Shows discomfort
- Trust is low (<5 for deeper stages)

Respond in JSON:
{{
    "should_transition": true/false,
    "confidence": 0.0-1.0,
    "reason": "brief explanation",
    "trust_adjustment": -2.0 to +2.0 (how much to adjust trust),
    "detected_signals": ["signal1", "signal2"]
}}
"""
            
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are an expert at analyzing conversation depth and readiness for stage transitions. Respond with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3,
                    max_tokens=200,
                    timeout=3.0
                ),
                timeout=3.0
            )
            
            analysis = json.loads(response.choices[0].message.content)
            
            result = {
                "current_stage": current_stage,
                "suggested_stage": next_stage if analysis.get("should_transition") else current_stage,
                "should_transition": analysis.get("should_transition", False),
                "confidence": analysis.get("confidence", 0.0),
                "reason": analysis.get("reason", ""),
                "trust_adjustment": analysis.get("trust_adjustment", 0.0),
                "detected_signals": analysis.get("detected_signals", [])
            }
            
            print(f"[STATE SERVICE] Stage analysis: {result['should_transition']} (confidence: {result['confidence']:.2f})")
            
            return result
            
        except asyncio.TimeoutError:
            print(f"[STATE SERVICE] Stage analysis timeout")
            return {
                "current_stage": current_state["stage"],
                "suggested_stage": current_state["stage"],
                "should_transition": False,
                "confidence": 0.0,
                "reason": "Analysis timeout",
                "trust_adjustment": 0.0
            }
        except Exception as e:
            print(f"[STATE SERVICE] suggest_stage_transition failed: {e}")
            return {
                "current_stage": current_state.get("stage", "ORIENTATION"),
                "suggested_stage": current_state.get("stage", "ORIENTATION"),
                "should_transition": False,
                "confidence": 0.0,
                "reason": f"Error: {e}",
                "trust_adjustment": 0.0
            }
    
    async def auto_update_from_interaction(
        self,
        user_input: str,
        user_profile: str = "",
        user_id: Optional[str] = None
    ) -> Dict:
        """
        Automatically analyze interaction and update state if appropriate.
        
        Args:
            user_input: User's message
            user_profile: User profile for context
            user_id: Optional user ID
            
        Returns:
            Dict with action_taken, old_state, new_state
        """
        try:
            uid = user_id or get_current_user_id()
            
            # Get current state
            old_state = await self.get_state(uid)
            
            # Get AI suggestion
            suggestion = await self.suggest_stage_transition(user_input, user_profile, uid)
            
            # Apply trust adjustment
            if suggestion["trust_adjustment"] != 0:
                await self.adjust_trust(
                    suggestion["trust_adjustment"],
                    reason=suggestion["reason"],
                    user_id=uid
                )
            
            # Apply stage transition if suggested
            action_taken = "none"
            if suggestion["should_transition"] and suggestion["confidence"] > 0.7:
                success = await self.update_state(
                    stage=suggestion["suggested_stage"],
                    user_id=uid
                )
                if success:
                    action_taken = "stage_transition"
                    print(f"[STATE SERVICE] Transitioned: {old_state['stage']} → {suggestion['suggested_stage']}")
            elif suggestion["trust_adjustment"] != 0:
                action_taken = "trust_adjustment"
            
            new_state = await self.get_state(uid)
            
            return {
                "action_taken": action_taken,
                "old_state": old_state,
                "new_state": new_state,
                "suggestion": suggestion
            }
            
        except Exception as e:
            print(f"[STATE SERVICE] auto_update_from_interaction failed: {e}")
            return {
                "action_taken": "error",
                "error": str(e)
            }
    
    def get_stage_guidance(self, stage: str) -> str:
        """
        Get conversation guidance for a specific stage.
        
        Args:
            stage: Conversation stage
            
        Returns:
            Guidance text for the assistant
        """
        guidance = {
            "ORIENTATION": """
## Current Stage: ORIENTATION (Trust: Building)
**Goal**: Build safety and comfort through light conversation.

**Approach**:
- Use warm, friendly greetings
- Ask simple, non-intrusive questions
- Show genuine interest and active listening
- Offer one small, easy "win" (micro-action <5 min)
- Avoid pushing for personal details

**Topics**: Weather, general interests, daily activities, light topics
**Trust Building**: Consistency, warmth, respect boundaries
""",
            "ENGAGEMENT": """
## Current Stage: ENGAGEMENT (Trust: Growing)
**Goal**: Explore breadth across life domains to identify energetic areas.

**Approach**:
- Explore multiple life areas (work, family, health, interests, habits)
- Ask open-ended questions
- Identify one domain that energizes them
- Continue offering small wins
- Show you remember previous conversations

**Topics**: Work, family, hobbies, health, learning, finances (surface level)
**Trust Building**: Remember details, show genuine curiosity, celebrate shares
""",
            "GUIDANCE": """
## Current Stage: GUIDANCE (Trust: Established)
**Goal**: Go deeper with consent and offer meaningful guidance.

**Approach**:
- **Ask for consent** before going deeper ("Would you like to explore this more?")
- Discuss feelings, needs, triggers (if comfortable)
- Offer one actionable skill or reframing technique
- Validate emotions and experiences
- Back off if any discomfort signals

**Topics**: Emotions, underlying needs, patterns, gentle challenges
**Trust Building**: Respect consent, validate feelings, offer useful insights
""",
            "REFLECTION": """
## Current Stage: REFLECTION (Trust: Strong)
**Goal**: Help reflect on progress and build sustainable routines.

**Approach**:
- Review progress on previous micro-actions
- Set small, sustainable routines
- Address obstacles with problem-solving
- Celebrate small wins
- Encourage self-reflection

**Topics**: Progress review, habit formation, obstacle handling, next steps
**Trust Building**: Acknowledge progress, support through setbacks, consistency
""",
            "INTEGRATION": """
## Current Stage: INTEGRATION (Trust: Deep)
**Goal**: Identity-level insights and choosing next growth area.

**Approach**:
- Facilitate identity-level reflection ("Who am I becoming?")
- Celebrate consistent growth
- Help choose next focus area or domain
- Acknowledge transformation
- Maintain deep, authentic connection

**Topics**: Identity, values, long-term vision, life purpose, next chapter
**Trust Building**: Deep authenticity, celebrate transformation, honor growth
"""
        }
        
        return guidance.get(stage, guidance["ORIENTATION"])
    
    async def generate_conversation_summary(
        self, 
        user_message: str, 
        assistant_message: str, 
        user_id: Optional[str] = None
    ) -> str:
        """
        Generate a brief summary of the conversation exchange.
        
        Args:
            user_message: User's message
            assistant_message: Assistant's response
            user_id: Optional user ID
            
        Returns:
            Brief conversation summary
        """
        try:
            # Get OpenAI client for summary generation
            pool = await get_connection_pool()
            if not pool:
                return "Summary unavailable"
                
            openai_client = pool.get_openai_client()
            if not openai_client:
                return "Summary unavailable"
            
            # Create a concise summary prompt
            prompt = f"""Create a brief 1-2 sentence summary of this conversation exchange in English:

User: {user_message}
Assistant: {assistant_message}

Focus on the main topic or sentiment. Keep it concise and factual."""
            
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content.strip()
            print(f"[STATE SERVICE] Generated conversation summary: {summary[:50]}...")
            return summary
            
        except Exception as e:
            print(f"[STATE SERVICE] Summary generation failed: {e}")
            return "Summary unavailable"
    
    async def extract_conversation_topics(
        self, 
        user_message: str, 
        assistant_message: str, 
        user_id: Optional[str] = None
    ) -> list:
        """
        Extract key topics from the conversation exchange.
        
        Args:
            user_message: User's message
            assistant_message: Assistant's response
            user_id: Optional user ID
            
        Returns:
            List of topic strings
        """
        try:
            # Get OpenAI client for topic extraction
            pool = await get_connection_pool()
            if not pool:
                return []
                
            openai_client = pool.get_openai_client()
            if not openai_client:
                return []
            
            # Create topic extraction prompt
            prompt = f"""Extract 2-3 key topics from this conversation exchange. Return as a JSON array of strings:

User: {user_message}
Assistant: {assistant_message}

Example: ["work", "family", "hobbies"]
Focus on main subjects discussed."""
            
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.2
            )
            
            topics_text = response.choices[0].message.content.strip()
            
            # Try to parse as JSON
            try:
                topics = json.loads(topics_text)
                if isinstance(topics, list):
                    print(f"[STATE SERVICE] Extracted topics: {topics}")
                    return topics
                else:
                    return [topics_text]
            except json.JSONDecodeError:
                # If JSON parsing fails, split by comma
                topics = [t.strip() for t in topics_text.split(',')]
                print(f"[STATE SERVICE] Extracted topics (fallback): {topics}")
                return topics
            
        except Exception as e:
            print(f"[STATE SERVICE] Topic extraction failed: {e}")
            return []
    
    async def update_conversation_context(
        self,
        user_message: str,
        assistant_message: str,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Update conversation context with last messages, summary, and topics.
        This runs in background to avoid blocking the main conversation flow.
        
        Args:
            user_message: User's message
            assistant_message: Assistant's response
            user_id: Optional user ID
            
        Returns:
            True if successful
        """
        uid = user_id or get_current_user_id()
        if not uid:
            return False
        
        try:
            # Generate summary and topics in parallel
            summary_task = self.generate_conversation_summary(user_message, assistant_message, uid)
            topics_task = self.extract_conversation_topics(user_message, assistant_message, uid)
            
            summary, topics = await asyncio.gather(summary_task, topics_task)
            
            # Update state with all the new information
            update_data = {
                "last_user_message": user_message,
                "last_assistant_message": assistant_message,
                "last_conversation_at": datetime.utcnow().isoformat(),
                "last_summary": summary,
                "last_topics": topics
            }
            
            # Update in database
            resp = await asyncio.to_thread(
                lambda: self.supabase.table("conversation_state")
                .update(update_data)
                .eq("user_id", uid)
                .execute()
            )
            
            error = getattr(resp, "error", None)
            if error:
                print(f"[STATE SERVICE] Context update failed: {error}")
                return False
            
            print(f"[STATE SERVICE] ✅ Updated conversation context with summary and {len(topics)} topics")
            return True
            
        except Exception as e:
            print(f"[STATE SERVICE] Context update failed: {e}")
            return False
    
    def _default_state(self) -> Dict:
        """Return default conversation state"""
        return {
            "stage": "ORIENTATION",
            "trust_score": DEFAULT_TRUST_SCORE,
            "last_updated": None,
            "metadata": {},
            "stage_history": [],
            "last_summary": None,
            "last_topics": [],
            "last_user_message": None,
            "last_assistant_message": None,
            "last_conversation_at": None
        }

