import os
import logging
import time
import uuid
import asyncio
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client, Client

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, RunContext, function_tool
from livekit.plugins import openai as lk_openai
from livekit.plugins import silero
from uplift_tts import TTS

# ---------------------------
# Logging: keep things clean (no verbose httpx/hpack/httpcore spam)
# ---------------------------
logging.basicConfig(level=logging.INFO)
for noisy in ("httpx", "httpcore", "hpack", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

# ---------------------------
# Setup
# ---------------------------
load_dotenv()

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Dynamic User ID will be set from LiveKit session
current_user_id: Optional[str] = None

# ---------------------------
# Supabase Client Setup
# Prefer SERVICE_ROLE only in trusted server contexts; otherwise ANON + RLS
# ---------------------------
supabase: Optional[Client] = None
if not SUPABASE_URL:
    print("[SUPABASE ERROR] SUPABASE_URL not configured")
else:
    key = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY
    if not key:
        print("[SUPABASE ERROR] No Supabase key configured")
    else:
        try:
            supabase = create_client(SUPABASE_URL, key)
            print(f"[SUPABASE] Connected using {'SERVICE_ROLE' if SUPABASE_SERVICE_ROLE_KEY else 'ANON'} key")
        except Exception as e:
            print(f"[SUPABASE ERROR] Connect failed: {e}")
            supabase = None

# ---------------------------
# Session / Identity Helpers
# ---------------------------
def set_current_user_id(user_id: str):
    """Set the current user ID from LiveKit session"""
    global current_user_id
    current_user_id = user_id
    print(f"[SESSION] User ID set to: {user_id}")

def get_current_user_id() -> Optional[str]:
    """Get the current user ID"""
    return current_user_id

def is_valid_uuid(uuid_string: str) -> bool:
    """Check if string is a valid UUID format"""
    try:
        uuid.UUID(uuid_string)
        return True
    except ValueError:
        return False

def extract_uuid_from_identity(identity: Optional[str]) -> Optional[str]:
    """
    Return a UUID string from 'user-<uuid>' or '<uuid>'.
    Return None if invalid (do not fabricate a fallback UUID here).
    """
    if not identity:
        print("[UUID WARNING] Empty identity")
        return None

    if identity.startswith("user-"):
        uuid_part = identity[5:]
        if is_valid_uuid(uuid_part):
            return uuid_part
        print(f"[UUID WARNING] Invalid UUID in 'user-' identity: {uuid_part}")
        return None

    if is_valid_uuid(identity):
        return identity

    print(f"[UUID WARNING] Invalid identity format: {identity}")
    return None

async def wait_for_participant(room, *, target_identity: Optional[str] = None, timeout_s: int = 20):
    """
    Waits up to timeout_s for a remote participant.
    If target_identity is provided, returns only when that identity is present.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        parts = list(room.remote_participants.values())
        if parts:
            if target_identity:
                for p in parts:
                    if p.identity == target_identity:
                        return p
            else:
                # Prefer STANDARD participants if available, else first
                standard = [p for p in parts if getattr(p, "kind", None) == "STANDARD"]
                return (standard[0] if standard else parts[0])
        await asyncio.sleep(0.5)
    return None

def can_write_for_current_user() -> bool:
    """Centralized guard to ensure DB writes are safe."""
    uid = get_current_user_id()
    if not uid:
        print("[GUARD] No current user_id; skipping DB writes")
        return False
    if not is_valid_uuid(uid):
        print(f"[GUARD] Invalid user_id format: {uid}; skipping DB writes")
        return False
    if not supabase:
        print("[GUARD] Supabase not connected; skipping DB writes")
        return False
    return True

# ---------------------------
# User Profile & Memory Management
# ---------------------------
def ensure_profile_exists(user_id: str) -> bool:
    """Ensure a profile exists for the user_id in the profiles table (profiles.user_id FK -> auth.users.id)."""
    if not supabase:
        print("[PROFILE ERROR] Supabase not connected")
        return False
    try:
        resp = supabase.table("profiles").select("id").eq("user_id", user_id).execute()
        rows = getattr(resp, "data", []) or []
        if rows:
            return True

        profile_data = {
            "user_id": user_id,
            "email": f"user_{user_id[:8]}@companion.local",
            "is_first_login": True,
        }
        create_resp = supabase.table("profiles").insert(profile_data).execute()
        if getattr(create_resp, "error", None):
            print(f"[PROFILE ERROR] {create_resp.error}")
            return False
        return True

    except Exception as e:
        print(f"[PROFILE ERROR] ensure_profile_exists failed: {e}")
        return False

def save_user_profile(profile_text: str) -> bool:
    """Save user profile to Supabase"""
    if not can_write_for_current_user():
        return False
    user_id = get_current_user_id()
    if not ensure_profile_exists(user_id):
        print(f"[PROFILE ERROR] Could not ensure profile exists for user {user_id}")
        return False
    try:
        resp = supabase.table("user_profiles").upsert({
            "user_id": user_id,
            "profile_text": profile_text,
        }).execute()
        if getattr(resp, "error", None):
            print(f"[SUPABASE ERROR] user_profiles upsert: {resp.error}")
            return False
        print(f"[PROFILE SAVED] User {user_id}")
        return True
    except Exception as e:
        print(f"[PROFILE ERROR] Failed to save profile: {e}")
        return False

def get_user_profile() -> str:
    """Get user profile from Supabase"""
    if not can_write_for_current_user():
        return ""
    user_id = get_current_user_id()
    try:
        resp = supabase.table("user_profiles").select("profile_text").eq("user_id", user_id).execute()
        if getattr(resp, "error", None):
            print(f"[SUPABASE ERROR] user_profiles select: {resp.error}")
            return ""
        data = getattr(resp, "data", []) or []
        if data:
            return data[0].get("profile_text", "") or ""
        return ""
    except Exception as e:
        print(f"[PROFILE ERROR] Failed to get profile: {e}")
        return ""

def save_memory(category: str, key: str, value: str) -> bool:
    """Save memory to Supabase"""
    if not can_write_for_current_user():
        return False
    user_id = get_current_user_id()

    # Ensure profile exists before saving memory (foreign key safety)
    if not ensure_profile_exists(user_id):
        print(f"[MEMORY ERROR] Could not ensure profile exists for user {user_id}")
        return False

    try:
        memory_data = {
            "user_id": user_id,
            "category": category,
            "key": key,
            "value": value,
        }
        resp = supabase.table("memory").upsert(memory_data).execute()
        if getattr(resp, "error", None):
            print(f"[SUPABASE ERROR] memory upsert: {resp.error}")
            return False
        print(f"[MEMORY SAVED] [{category}] {key} for user {user_id}")
        return True
    except Exception as e:
        print(f"[MEMORY ERROR] Failed to save memory: {e}")
        return False

def get_memory(category: str, key: str) -> Optional[str]:
    """Get memory from Supabase"""
    if not can_write_for_current_user():
        return None
    user_id = get_current_user_id()
    try:
        resp = supabase.table("memory").select("value") \
                        .eq("user_id", user_id) \
                        .eq("category", category) \
                        .eq("key", key) \
                        .execute()
        if getattr(resp, "error", None):
            print(f"[SUPABASE ERROR] memory select: {resp.error}")
            return None
        data = getattr(resp, "data", []) or []
        if data:
            return data[0].get("value")
        return None
    except Exception as e:
        print(f"[MEMORY ERROR] Failed to get memory: {e}")
        return None

# ---------------------------
# Memory Categorization
# ---------------------------
def categorize_user_input(user_text: str) -> str:
    """Categorize user input for memory storage"""
    text = (user_text or "").lower()

    goal_keywords = ["want to", "want to be", "aspire to", "goal is", "hoping to", "planning to",
                     "dream of", "aim to", "strive for", "working towards", "trying to achieve",
                     "would like to", "my goal", "my dream", "my aspiration"]
    if any(keyword in text for keyword in goal_keywords):
        return "GOAL"

    interest_keywords = ["i like", "i love", "i enjoy", "i'm interested in", "my hobby", "hobbies",
                         "i'm passionate about", "favorite", "i prefer", "i'm into", "i'm a fan of"]
    if any(keyword in text for keyword in interest_keywords):
        return "INTEREST"

    opinion_keywords = ["i think", "i believe", "in my opinion", "i feel", "i consider",
                        "i'm of the view", "my view is", "i'm convinced", "i disagree", "i agree"]
    if any(keyword in text for keyword in opinion_keywords):
        return "OPINION"

    experience_keywords = ["i experienced", "i went through", "happened to me", "i had", "i did",
                           "i've been", "i was", "i used to", "i remember", "i recall",
                           "my experience", "when i", "once i"]
    if any(keyword in text for keyword in experience_keywords):
        return "EXPERIENCE"

    preference_keywords = ["i prefer", "i'd rather", "i like better", "my choice is", "i choose",
                           "instead of", "rather than", "better than", "more than", "rather have"]
    if any(keyword in text for keyword in preference_keywords):
        return "PREFERENCE"

    plan_keywords = ["i'm planning", "i plan to", "i will", "i'm going to", "i intend to",
                     "my plan is", "i'm thinking of", "i'm considering", "next week", "tomorrow",
                     "this weekend", "i'll do"]
    if any(keyword in text for keyword in plan_keywords):
        return "PLAN"

    relationship_keywords = ["my friend", "my family", "my partner", "my spouse", "my parents",
                             "my children", "my colleague", "my boss", "my teacher", "my mentor",
                             "my relationship", "we are", "they are", "he is", "she is"]
    if any(keyword in text for keyword in relationship_keywords):
        return "RELATIONSHIP"

    return "FACT"

# ---------------------------
# Assistant Agent with OpenAI Prompt
# ---------------------------
class Assistant(Agent):
    def __init__(self):
        super().__init__(instructions="""
        ## Overall Role
        You are a helpful Urdu AI assistant that can engage in natural conversations with users. 
        You have access to user profile and memory storage capabilities through Supabase.

        You should be friendly, informative, and helpful while maintaining appropriate boundaries.
        
        ## Core Guidelines
        - Respond naturally and conversationally
        - Be helpful and provide accurate information when possible
        - If you don't know something, admit it rather than making things up
        - Keep responses concise but complete
        - Be respectful and professional in all interactions
        - ALWAYS use the available tools to store and retrieve user information
        - Save important user details, preferences, and facts using saveMemory tool
        - Check existing memories before responding to provide personalized responses
        
        ## Language Support
        - You can communicate in multiple languages including English and Urdu
        - Adapt your language based on the user's preferred language
        - Maintain cultural sensitivity in your responses
        
        ## Interaction Style
        - Ask clarifying questions when needed
        - Provide examples when helpful
        - Break down complex topics into understandable parts
        - Be patient and encouraging
        - Remember important details about the user using the memory tools
        
        Remember: You are here to assist and have meaningful conversations with users.
        """)

    @function_tool()
    async def saveUserProfile(self, context: RunContext, profile_text: str):
        """Save user profile information"""
        success = save_user_profile(profile_text)
        return {"success": success, "message": "Profile saved" if success else "Failed to save profile"}

    @function_tool()
    async def getUserProfile(self, context: RunContext):
        """Get user profile information"""
        profile = get_user_profile()
        return {"profile": profile}

    @function_tool()
    async def saveMemory(self, context: RunContext, category: str, key: str, value: str):
        """Save a memory item"""
        success = save_memory(category, key, value)
        return {"success": success, "message": f"Memory [{category}] {key} saved" if success else "Failed to save memory"}

    @function_tool()
    async def getMemory(self, context: RunContext, category: str, key: str):
        """Get a memory item"""
        memory = get_memory(category, key)
        return {"value": memory or "", "found": memory is not None}

    async def on_user_turn_completed(self, turn_ctx, new_message):
        """Automatically save user input as memory (only if DB writes are permitted)"""
        user_text = new_message.text_content or ""
        print(f"[USER INPUT] {user_text}")

        if not can_write_for_current_user():
            print("[AUTO MEMORY] Skipped (no valid user_id or no DB)")
            return

        ts_ms = int(time.time() * 1000)
        memory_key = f"user_input_{ts_ms}"

        category = categorize_user_input(user_text)
        print(f"[AUTO MEMORY] Saving: [{category}] {memory_key}")

        success = save_memory(category, memory_key, user_text)
        if success:
            print(f"[AUTO MEMORY] ✓ Saved")
        else:
            print(f"[AUTO MEMORY] ✗ Failed")

# ---------------------------
# Entrypoint
# ---------------------------
async def entrypoint(ctx: agents.JobContext):
    """
    LiveKit agent entrypoint:
    - Start session to receive state updates
    - Wait for the intended participant deterministically
    - Extract & validate UUID from participant identity
    - Defer Supabase writes until we have a valid user_id
    - Initialize profile & proceed with conversation
    """
    print(f"[ENTRYPOINT] Starting session for room: {ctx.room.name}")

    # Initialize media + agent FIRST so room state/events begin flowing
    tts = TTS(voice_id="17", output_format="MP3_22050_32")
    assistant = Assistant()
    session = AgentSession(
        stt=lk_openai.STT(model="gpt-4o-transcribe", language="ur"),
        llm=lk_openai.LLM(model="gpt-4o-mini"),
        tts=tts,
        vad=silero.VAD.load(),
    )

    print("[SESSION INIT] Starting LiveKit session…")
    await session.start(room=ctx.room, agent=assistant, room_input_options=RoomInputOptions())
    print("[SESSION INIT] ✓ Session started")

    # If you know the expected identity (from your token minting), set it here
    expected_identity = None

    # Wait for the participant deterministically
    participant = await wait_for_participant(ctx.room, target_identity=expected_identity, timeout_s=20)
    if not participant:
        print("[ENTRYPOINT] No participant joined within timeout; running without DB writes")
        await session.generate_reply(instructions=assistant.instructions)
        return

    print(f"[ENTRYPOINT] Participant: sid={participant.sid}, identity={participant.identity}, kind={getattr(participant, 'kind', None)}")

    # Resolve to UUID
    user_id = extract_uuid_from_identity(participant.identity)
    if not user_id:
        print("[ENTRYPOINT] Participant identity could not be parsed as UUID; skipping DB writes")
        await session.generate_reply(instructions=assistant.instructions)
        return

    # Set current user
    set_current_user_id(user_id)

    # Now that we have a valid user_id, it's safe to touch Supabase
    if supabase:
        print("[SUPABASE] ✓ Connected")

        # Optional: smoke test memory table for this user
        if save_memory("TEST", "connection_test", "Supabase connection OK"):
            try:
                supabase.table("memory").delete() \
                        .eq("user_id", user_id) \
                        .eq("category", "TEST") \
                        .eq("key", "connection_test") \
                        .execute()
            except Exception as e:
                print(f"[TEST] Cleanup warning: {e}")

        # Profile bootstrap
        existing_profile = get_user_profile()
        if not existing_profile:
            initial_profile = f"User ID: {user_id} | Status: Active | Language: Urdu/English"
            save_user_profile(initial_profile)
    else:
        print("[SUPABASE] ✗ Not connected; running without persistence")

    # Greet after we’ve set up identity + (optional) storage
    await session.generate_reply(instructions=assistant.instructions)

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        initialize_process_timeout=60,
    ))
