import os
import logging
import time
import uuid
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
# ---------------------------
supabase = None
if SUPABASE_URL:
    if SUPABASE_SERVICE_ROLE_KEY:
        try:
            supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            print("[SUPABASE] Connected using SERVICE_ROLE key")
        except Exception as e:
            print(f"[SUPABASE ERROR] Failed to connect with service role: {e}")
    
    if not supabase and SUPABASE_ANON_KEY:
        try:
            supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            print("[SUPABASE] Connected using ANON key")
        except Exception as e:
            print(f"[SUPABASE ERROR] Failed to connect with anon key: {e}")
    
    if not supabase:
        print("[SUPABASE ERROR] No valid Supabase keys configured")
else:
    print("[SUPABASE ERROR] SUPABASE_URL not configured")

# ---------------------------
# Session Management
# ---------------------------
def set_current_user_id(user_id: str):
    """Set the current user ID from LiveKit session"""
    global current_user_id
    current_user_id = user_id
    print(f"[SESSION] User ID set to: {user_id}")

def get_current_user_id() -> Optional[str]:
    """Get the current user ID"""
    return current_user_id

def extract_uuid_from_identity(identity: str) -> str:
    """Extract UUID from various identity formats"""
    if not identity:
        # Generate a new UUID for empty identity
        return str(uuid.uuid4())
    
    # Handle "user-4e3efa3d-d8fe-431e-a78f-4efffb0cf43a" format
    if identity.startswith("user-"):
        uuid_part = identity[5:]  # Remove "user-" prefix
        if is_valid_uuid(uuid_part):
            return uuid_part
        else:
            # Generate a new UUID if the extracted part is invalid
            print(f"[UUID WARNING] Invalid UUID in user- prefix: {uuid_part}, generating new UUID")
            return str(uuid.uuid4())
    
    # Handle direct UUID format
    if is_valid_uuid(identity):
        return identity
    
    # For any other format, generate a new UUID
    print(f"[UUID WARNING] Invalid identity format: {identity}, generating new UUID")
    return str(uuid.uuid4())

def is_valid_uuid(uuid_string: str) -> bool:
    """Check if string is a valid UUID format"""
    try:
        uuid.UUID(uuid_string)
        return True
    except ValueError:
        return False

# ---------------------------
# User Profile Management
# ---------------------------
def save_user_profile(profile_text: str) -> bool:
    """Save user profile to Supabase"""
    user_id = get_current_user_id()
    if not user_id:
        print("[PROFILE ERROR] No user ID set")
        return False
    
    # Validate UUID format before saving
    if not is_valid_uuid(user_id):
        print(f"[PROFILE ERROR] Invalid UUID format: {user_id}")
        return False
    
    if not supabase:
        print("[PROFILE ERROR] Supabase not connected")
        return False
    
    # Ensure profile exists before saving user profile
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
    user_id = get_current_user_id()
    if not user_id:
        print("[PROFILE ERROR] No user ID set")
        return ""
    
    # Validate UUID format before querying
    if not is_valid_uuid(user_id):
        print(f"[PROFILE ERROR] Invalid UUID format: {user_id}")
        return ""
    
    if not supabase:
        print("[PROFILE ERROR] Supabase not connected")
        return ""
    
    try:
        resp = supabase.table("user_profiles").select("profile_text").eq("user_id", user_id).execute()
        
        if getattr(resp, "error", None):
            print(f"[SUPABASE ERROR] user_profiles select: {resp.error}")
            return ""
        
        if resp.data:
            return resp.data[0]["profile_text"]
        return ""
    except Exception as e:
        print(f"[PROFILE ERROR] Failed to get profile: {e}")
        return ""

def ensure_profile_exists(user_id: str) -> bool:
    """Ensure a profile exists for the user_id in the profiles table"""
    if not supabase:
        print("[PROFILE ERROR] Supabase not connected")
        return False
    
    try:
        # Check if profile already exists using user_id
        resp = supabase.table("profiles").select("id, user_id").eq("user_id", user_id).execute()
        
        if resp.data:
            print(f"[PROFILE] Profile already exists for user {user_id} (profile_id: {resp.data[0]['id']})")
            return True
        
        # Create new profile with user_id (let id be auto-generated)
        print(f"[PROFILE] Creating new profile for user {user_id}")
        create_resp = supabase.table("profiles").insert({
            "user_id": user_id,
            "email": f"user_{user_id[:8]}@companion.local",
            "is_first_login": True,
        }).execute()
        
        if getattr(create_resp, "error", None):
            print(f"[PROFILE ERROR] Failed to create profile: {create_resp.error}")
            return False
        
        # Get the created profile ID for logging
        created_profile_id = create_resp.data[0]['id'] if create_resp.data else 'unknown'
        print(f"[PROFILE] ✓ Profile created successfully!")
        print(f"[PROFILE]   - Profile ID: {created_profile_id}")
        print(f"[PROFILE]   - User ID: {user_id}")
        print(f"[PROFILE]   - Email: user_{user_id[:8]}@companion.local")
        return True
        
    except Exception as e:
        print(f"[PROFILE ERROR] ensure_profile_exists failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def save_memory(category: str, key: str, value: str) -> bool:
    """Save memory to Supabase"""
    user_id = get_current_user_id()
    if not user_id:
        print("[MEMORY ERROR] No user ID set")
        return False
    
    # Validate UUID format before saving
    if not is_valid_uuid(user_id):
        print(f"[MEMORY ERROR] Invalid UUID format: {user_id}")
        return False
    
    print(f"[DEBUG] save_memory called: category={category}, key={key}, value={value[:50]}...")
    
    if not supabase:
        print("[MEMORY ERROR] Supabase not connected")
        return False
    
    # Ensure profile exists before saving memory (foreign key constraint)
    if not ensure_profile_exists(user_id):
        print(f"[MEMORY ERROR] Could not ensure profile exists for user {user_id}")
        return False
    
    print(f"[DEBUG] Supabase client available: {supabase is not None}")
    print(f"[DEBUG] USER_ID: {user_id}")
    
    try:
        memory_data = {
            "user_id": user_id,
            "category": category,
            "key": key,
            "value": value,
        }
        print(f"[DEBUG] Memory data: {memory_data}")
        
        resp = supabase.table("memory").upsert(memory_data).execute()
        print(f"[DEBUG] Supabase response: {resp}")
        
        if getattr(resp, "error", None):
            print(f"[SUPABASE ERROR] memory upsert: {resp.error}")
            return False
        
        print(f"[MEMORY SAVED] [{category}] {key} for user {user_id}")
        return True
    except Exception as e:
        print(f"[MEMORY ERROR] Failed to save memory: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_memory(category: str, key: str) -> Optional[str]:
    """Get memory from Supabase"""
    user_id = get_current_user_id()
    if not user_id:
        print("[MEMORY ERROR] No user ID set")
        return None
    
    # Validate UUID format before querying
    if not is_valid_uuid(user_id):
        print(f"[MEMORY ERROR] Invalid UUID format: {user_id}")
        return None
    
    if not supabase:
        print("[MEMORY ERROR] Supabase not connected")
        return None
    
    try:
        resp = supabase.table("memory").select("value").eq("user_id", user_id).eq("category", category).eq("key", key).execute()
        
        if getattr(resp, "error", None):
            print(f"[SUPABASE ERROR] memory select: {resp.error}")
            return None
        
        if resp.data:
            return resp.data[0]["value"]
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
    
    # Goal-related keywords
    goal_keywords = ["want to", "want to be", "aspire to", "goal is", "hoping to", "planning to",
                    "dream of", "aim to", "strive for", "working towards", "trying to achieve",
                    "would like to", "my goal", "my dream", "my aspiration"]
    if any(keyword in text for keyword in goal_keywords):
        return "GOAL"
    
    # Interest-related keywords
    interest_keywords = ["i like", "i love", "i enjoy", "i'm interested in", "my hobby", "hobbies",
                        "i'm passionate about", "favorite", "i prefer", "i'm into", "i'm a fan of"]
    if any(keyword in text for keyword in interest_keywords):
        return "INTEREST"
    
    # Opinion-related keywords
    opinion_keywords = ["i think", "i believe", "in my opinion", "i feel", "i consider",
                       "i'm of the view", "my view is", "i'm convinced", "i disagree", "i agree"]
    if any(keyword in text for keyword in opinion_keywords):
        return "OPINION"
    
    # Experience-related keywords
    experience_keywords = ["i experienced", "i went through", "happened to me", "i had", "i did",
                          "i've been", "i was", "i used to", "i remember", "i recall",
                          "my experience", "when i", "once i"]
    if any(keyword in text for keyword in experience_keywords):
        return "EXPERIENCE"
    
    # Preference-related keywords
    preference_keywords = ["i prefer", "i'd rather", "i like better", "my choice is", "i choose",
                          "instead of", "rather than", "better than", "more than", "rather have"]
    if any(keyword in text for keyword in preference_keywords):
        return "PREFERENCE"
    
    # Plan-related keywords
    plan_keywords = ["i'm planning", "i plan to", "i will", "i'm going to", "i intend to",
                    "my plan is", "i'm thinking of", "i'm considering", "next week", "tomorrow",
                    "this weekend", "i'll do"]
    if any(keyword in text for keyword in plan_keywords):
        return "PLAN"
    
    # Relationship-related keywords
    relationship_keywords = ["my friend", "my family", "my partner", "my spouse", "my parents",
                            "my children", "my colleague", "my boss", "my teacher", "my mentor",
                            "my relationship", "we are", "they are", "he is", "she is"]
    if any(keyword in text for keyword in relationship_keywords):
        return "RELATIONSHIP"
    
    # Default to FACT for general information
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
        """Automatically save user input as memory"""
        user_text = new_message.text_content
        print(f"[USER INPUT] {user_text}")

        # Auto-save user input as memory
        import time
        timestamp = int(time.time() * 1000)
        memory_key = f"user_input_{timestamp}"
        
        # Categorize the input
        category = categorize_user_input(user_text)
        print(f"[AUTO MEMORY] Saving: [{category}] {memory_key}")
        
        success = save_memory(category, memory_key, user_text)
        if success:
            print(f"[AUTO MEMORY] ✓ Saved successfully")
        else:
            print(f"[AUTO MEMORY] ✗ Failed to save")

# ---------------------------
# Entrypoint
# ---------------------------
async def entrypoint(ctx: agents.JobContext):
    """
    LiveKit agent entrypoint:
    - Extract user ID from LiveKit session
    - Test Supabase connection
    - Initialize TTS and Assistant
    - Create and start session
    - Handle user interactions
    """
    print(f"[ENTRYPOINT] Starting session for room: {ctx.room.name}")
    
    # Extract user ID from LiveKit session
    user_id = None
    participants_found = False
    
    try:
        print(f"[ENTRYPOINT DEBUG] Room participants count: {len(ctx.room.remote_participants)}")
        print(f"[ENTRYPOINT DEBUG] All participants: {list(ctx.room.remote_participants.keys())}")
        
        participants = ctx.room.remote_participants
        if participants:
            participants_found = True
            # Get the first participant (there should typically be only one user)
            participant = list(participants.values())[0]
            raw_identity = participant.identity
            print(f"[ENTRYPOINT] Found participant: {participant.sid}")
            print(f"[ENTRYPOINT] Raw identity: {raw_identity}")
            print(f"[ENTRYPOINT] Participant metadata: {getattr(participant, 'metadata', 'No metadata')}")
            
            # Extract UUID from identity using helper function
            user_id = extract_uuid_from_identity(raw_identity)
            print(f"[ENTRYPOINT] Processed identity: {raw_identity} -> {user_id}")
                
        else:
            print("[ENTRYPOINT] No remote participants found")
            print("[ENTRYPOINT DEBUG] This could mean:")
            print("[ENTRYPOINT DEBUG] 1. User hasn't joined the room yet")
            print("[ENTRYPOINT DEBUG] 2. User joined but agent started before participant")
            print("[ENTRYPOINT DEBUG] 3. Room configuration issue")
            print("[ENTRYPOINT DEBUG] 4. LiveKit token/authentication issue")
            
            # Generate a proper UUID for fallback
            user_id = str(uuid.uuid4())
            print(f"[ENTRYPOINT] Using fallback user ID: {user_id}")
    except Exception as e:
        print(f"[ENTRYPOINT] Error extracting user ID: {e}")
        import traceback
        traceback.print_exc()
        # Generate a proper UUID for error fallback
        user_id = str(uuid.uuid4())
        print(f"[ENTRYPOINT] Using error fallback user ID: {user_id}")
    
    # Set the current user ID for this session
    set_current_user_id(user_id)
    print(f"[ENTRYPOINT] User ID set to: {user_id}")

    # If no participants found initially, wait a bit and try again
    if not participants_found:
        print("[ENTRYPOINT] Waiting for participants to join...")
        import asyncio
        await asyncio.sleep(2)  # Wait 2 seconds
        
        # Try again to get participants
        try:
            participants = ctx.room.remote_participants
            if participants:
                participant = list(participants.values())[0]
                raw_identity = participant.identity
                print(f"[ENTRYPOINT RETRY] Found participant: {participant.sid}")
                print(f"[ENTRYPOINT RETRY] Raw identity: {raw_identity}")
                
                # Extract UUID from identity using helper function
                user_id = extract_uuid_from_identity(raw_identity)
                print(f"[ENTRYPOINT RETRY] Processed identity: {raw_identity} -> {user_id}")
                
                # Update the current user ID
                set_current_user_id(user_id)
                print(f"[ENTRYPOINT RETRY] User ID updated to: {user_id}")
            else:
                print("[ENTRYPOINT RETRY] Still no participants found after waiting")
        except Exception as e:
            print(f"[ENTRYPOINT RETRY] Error in retry: {e}")

    # Test Supabase connection
    if supabase:
        print("[SUPABASE] ✓ Connected successfully")
        
        # Test memory table with a simple test
        print("[TEST] Testing memory table...")
        test_success = save_memory("TEST", "connection_test", "Supabase connection working")
        if test_success:
            print("[TEST] ✓ Memory table test successful")
            # Clean up test memory
            try:
                supabase.table("memory").delete().eq("user_id", user_id).eq("category", "TEST").eq("key", "connection_test").execute()
                print("[TEST] ✓ Test memory cleaned up")
            except Exception as e:
                print(f"[TEST] Warning: Could not clean up test memory: {e}")
        else:
            print("[TEST] ✗ Memory table test failed")
        
        # Try to get existing user profile
        existing_profile = get_user_profile()
        if existing_profile:
            print(f"[USER PROFILE] Found existing profile: {existing_profile[:100]}...")
        else:
            print("[USER PROFILE] No existing profile found")
            # Create initial profile
            initial_profile = f"User ID: {user_id} | Status: Active | Language: Urdu/English"
            save_user_profile(initial_profile)
            print("[USER PROFILE] Created initial profile")
    else:
        print("[SUPABASE] ✗ Connection failed - running in offline mode")

    # Initialize TTS and Assistant
    tts = TTS(voice_id="17", output_format="MP3_22050_32")
    assistant = Assistant()

    # Create and start session
    session = AgentSession(
        stt=lk_openai.STT(model="gpt-4o-transcribe", language="ur"),
        llm=lk_openai.LLM(model="gpt-4o-mini"),
        tts=tts,
        vad=silero.VAD.load(),
    )

    print("[SESSION INIT] Starting LiveKit session…")
    await session.start(room=ctx.room, agent=assistant, room_input_options=RoomInputOptions())
    print("[SESSION INIT] ✓ Session started")

    # Generate initial greeting
    await session.generate_reply(instructions=assistant.instructions)

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        initialize_process_timeout=60,
    ))