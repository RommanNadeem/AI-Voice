import os
import re
import uuid
import json
import logging
from typing import Optional, Dict, Any, List
from contextvars import ContextVar

import faiss
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client, Client

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, function_tool, RunContext
from livekit.plugins import openai as lk_openai
from livekit.plugins import silero

# Import TTS with fallback
try:
    from uplift_tts import TTS
except ImportError:
    print("[WARNING] uplift_tts not available, using default TTS")
    # Fallback to a basic TTS implementation
    class TTS:
        def __init__(self, voice_id="17", output_format="MP3_22050_32"):
            self.voice_id = voice_id
            self.output_format = output_format

# ---------------------------
# Logging: keep output clean
# ---------------------------
logging.basicConfig(level=logging.INFO)
for noisy in ("httpx", "httpcore", "hpack", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

# ---------------------------
# Setup
# ---------------------------
load_dotenv()

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("[ERROR] OPENAI_API_KEY not found in environment variables")
    client = None
else:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        print("[SUCCESS] OpenAI client initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize OpenAI client: {e}")
        client = None

# Supabase env
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # preferred for server writes/reads
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")                  # fallback for public reads

# Validate environment variables
def validate_environment():
    """Validate required environment variables"""
    missing_vars = []
    
    if not OPENAI_API_KEY:
        missing_vars.append("OPENAI_API_KEY")
    
    if not SUPABASE_URL:
        missing_vars.append("SUPABASE_URL")
    
    if not SUPABASE_SERVICE_ROLE_KEY and not SUPABASE_ANON_KEY:
        missing_vars.append("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY")
    
    if missing_vars:
        print(f"[ERROR] Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    print("[SUCCESS] All required environment variables found")
    return True

# Validate environment on startup
validate_environment()

# ---------------------------
# Session Context (thread-safe)
# ---------------------------
_session_user_uuid: ContextVar[Optional[str]] = ContextVar("session_user_uuid", default=None)
_session_livekit_identity: ContextVar[Optional[str]] = ContextVar("session_livekit_identity", default=None)

UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)

def extract_uuid_from_identity(identity: str) -> Optional[str]:
    """
    Accepts LiveKit identity like:
      - '02e0fa39-d583-4051-8ff5-2a0880721204'
      - 'user-02e0fa39-d583-4051-8ff5-2a0880721204'
      - 'prefix_user-<uuid>_suffix'
    Returns the first valid UUID found, else None.
    """
    if not identity:
        return None
    m = UUID_RE.search(identity)
    return m.group(0) if m else None

def set_session_user_from_identity(livekit_identity: str) -> Optional[str]:
    """
    Bind session user from LiveKit identity by extracting the UUID inside it.
    If no UUID found, DB-bound user is not set.
    """
    user_uuid = extract_uuid_from_identity(livekit_identity)
    _session_livekit_identity.set(livekit_identity)
    _session_user_uuid.set(user_uuid)
    if user_uuid:
        print(f"[SESSION] Bound LiveKit identity '{livekit_identity}' → user_uuid: {user_uuid}")
    else:
        print(f"[SESSION] No UUID found in identity: '{livekit_identity}'. Running unbound.")
    return user_uuid

def get_session_user_uuid() -> Optional[str]:
    return _session_user_uuid.get()

def get_session_livekit_identity() -> Optional[str]:
    return _session_livekit_identity.get()

# ---------------------------
# Supabase clients
# ---------------------------
def get_sb_client() -> Optional[Client]:
    # Prefer service role for writes/reads with RLS-sensitive tables
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            print("[SUCCESS] Supabase client initialized with service role key")
            return client
        except Exception as e:
            print(f"[ERROR] Failed to create Supabase client with service role: {e}")
    
    if SUPABASE_URL and SUPABASE_ANON_KEY:
        try:
            client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            print("[SUCCESS] Supabase client initialized with anon key")
            return client
        except Exception as e:
            print(f"[ERROR] Failed to create Supabase client with anon key: {e}")
    
    print("[ERROR] No valid Supabase credentials found")
    return None

SB: Optional[Client] = get_sb_client()

# ---------------------------
# DB helpers
# ---------------------------
def ensure_profiles_row(user_id: str, email_hint: Optional[str] = None) -> bool:
    """
    Ensure a row exists in public.profiles for the given user_id (FK to auth.users).
    NOTE: This succeeds only if auth.users already has this UUID.
    """
    print(f"[PROFILES DEBUG] Ensuring profiles row for user: {user_id}")
    
    if not SB:
        print(f"[PROFILES ERROR] Supabase client not available")
        return False
        
    if not user_id:
        print(f"[PROFILES ERROR] No user ID provided")
        return False
        
    try:
        print(f"[PROFILES DEBUG] Checking if profile exists...")
        chk = SB.table("profiles").select("id").eq("id", user_id).limit(1).execute()
        print(f"[PROFILES DEBUG] Check result: {chk}")
        
        if chk.data:
            print(f"[PROFILES SUCCESS] Profile already exists")
            return True
            
        print(f"[PROFILES DEBUG] Profile not found, creating new one...")
        email = email_hint or f"user_{user_id[:8]}@local"
        print(f"[PROFILES DEBUG] Using email: {email}")
        
        # Insert a placeholder row; will fail if FK to auth.users is missing
        result = SB.table("profiles").insert({
            "id": user_id,
            "email": email,
            "is_first_login": True
        }).execute()
        
        print(f"[PROFILES DEBUG] Insert result: {result}")
        print(f"[PROFILES SUCCESS] Profile created successfully")
        return True
        
    except Exception as e:
        print(f"[PROFILES ERROR] ensure_profiles_row failed: {e}")
        print(f"[PROFILES ERROR] Exception type: {type(e).__name__}")
        import traceback
        print(f"[PROFILES ERROR] Full traceback: {traceback.format_exc()}")
        return False

def fetch_profile_text(user_id: str) -> str:
    if not (SB and user_id):
        return ""
    try:
        resp = SB.table("user_profiles").select("profile_text").eq("user_id", user_id).limit(1).execute()
        if resp.data:
            return resp.data[0].get("profile_text") or ""
    except Exception as e:
        print(f"[DB] user_profiles select error: {e}")
    return ""

def upsert_profile_text(user_id: str, text: str) -> bool:
    if not (SB and user_id):
        return False
    try:
        if not ensure_profiles_row(user_id):
            return False
        SB.table("user_profiles").upsert({
            "user_id": user_id,
            "profile_text": text
        }).execute()
        return True
    except Exception as e:
        print(f"[DB] user_profiles upsert error: {e}")
        return False

def merge_profile_text(user_id: str, snippet: str) -> str:
    """
    Model-assisted merge of snippet into existing profile_text, then persist.
    """
    base = fetch_profile_text(user_id)
    
    if not client:
        print(f"[PROFILE MERGE ERROR] OpenAI client not available")
        return base
        
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system",
                 "content": "Merge the new info into the profile (≤10 lines), most-recent-wins, no hallucinations."},
                {"role": "system", "content": f"Current profile:\n{base}"},
                {"role": "user", "content": f"New information to integrate:\n{snippet}"},
            ],
        )
        merged = resp.choices[0].message.content.strip()
        upsert_profile_text(user_id, merged)
        return merged
    except Exception as e:
        print(f"[PROFILE MERGE ERROR] {e}")
        return base

def fetch_profile_row(user_id: str) -> Optional[Dict[str, Any]]:
    if not (SB and user_id):
        return None
    try:
        resp = SB.table("profiles").select("id, email, is_first_login").eq("id", user_id).limit(1).execute()
        if resp.data:
            return resp.data[0]
    except Exception as e:
        print(f"[DB] profiles select error: {e}")
    return None

def upsert_profile_field(user_id: str, column: str, value: Any) -> bool:
    """
    Upsert a single column in public.profiles (id must match auth.users.id).
    """
    if not (SB and user_id):
        return False
    try:
        if not ensure_profiles_row(user_id):
            return False
        row = {"id": user_id, column: value}
        SB.table("profiles").upsert(row).execute()
        return True
    except Exception as e:
        print(f"[DB] profiles field upsert error: {e}")
        return False

def fetch_memories(user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    if not (SB and user_id):
        return []
    try:
        resp = SB.table("memory").select("category, key, value").eq("user_id", user_id).limit(limit).execute()
        return resp.data or []
    except Exception as e:
        print(f"[DB] memory select error: {e}")
        return []

def upsert_memory(user_id: str, category: str, key: str, value: str) -> bool:
    print(f"[MEMORY DEBUG] Attempting to save memory:")
    print(f"[MEMORY DEBUG] - User ID: {user_id}")
    print(f"[MEMORY DEBUG] - Category: {category}")
    print(f"[MEMORY DEBUG] - Key: {key}")
    print(f"[MEMORY DEBUG] - Value: {value[:100]}...")
    print(f"[MEMORY DEBUG] - Supabase Client: {'Connected' if SB else 'Not connected'}")
    
    if not SB:
        print(f"[MEMORY ERROR] Supabase client not available")
        print(f"[MEMORY ERROR] SUPABASE_URL: {SUPABASE_URL}")
        print(f"[MEMORY ERROR] SUPABASE_SERVICE_ROLE_KEY: {'Set' if SUPABASE_SERVICE_ROLE_KEY else 'Not set'}")
        print(f"[MEMORY ERROR] SUPABASE_ANON_KEY: {'Set' if SUPABASE_ANON_KEY else 'Not set'}")
        return False
        
    if not user_id:
        print(f"[MEMORY ERROR] No user ID provided")
        return False
        
    try:
        print(f"[MEMORY DEBUG] Ensuring profiles row exists...")
        profiles_ok = ensure_profiles_row(user_id)
        print(f"[MEMORY DEBUG] Profiles row check: {'OK' if profiles_ok else 'FAILED'}")
        
        if not profiles_ok:
            print(f"[MEMORY ERROR] Could not ensure profiles row exists")
            return False
            
        print(f"[MEMORY DEBUG] Attempting database upsert...")
        result = SB.table("memory").upsert({
            "user_id": user_id,
            "category": (category or "FACT").upper(),
            "key": key,
            "value": value
        }).execute()
        
        print(f"[MEMORY DEBUG] Database response: {result}")
        print(f"[MEMORY SUCCESS] Memory saved successfully!")
        return True
        
    except Exception as e:
        print(f"[MEMORY ERROR] Database upsert failed: {e}")
        print(f"[MEMORY ERROR] Exception type: {type(e).__name__}")
        import traceback
        print(f"[MEMORY ERROR] Full traceback: {traceback.format_exc()}")
        return False

def fetch_memory_value(user_id: str, category: str, key: str) -> Optional[str]:
    if not (SB and user_id):
        return None
    try:
        resp = SB.table("memory").select("value")\
            .eq("user_id", user_id).eq("category", category).eq("key", key).limit(1).execute()
        if resp.data:
            return resp.data[0]["value"]
    except Exception as e:
        print(f"[DB] memory select one error: {e}")
    return None

def fetch_onboarding(user_id: str) -> Optional[Dict[str, Any]]:
    if not (SB and user_id):
        return None
    try:
        resp = SB.table("onboarding_details").select("full_name, occupation, interests")\
            .eq("user_id", user_id).limit(1).execute()
        if resp.data:
            return resp.data[0]
    except Exception as e:
        print(f"[DB] onboarding_details select error: {e}")
    return None

# ---------------------------
# Memory Manager (wrapper)
# ---------------------------
class MemoryManager:
    def load_profile(self) -> str:
        user_id = get_session_user_uuid()
        if not user_id:
            return ""
        return fetch_profile_text(user_id)

memory_manager = MemoryManager()

# ---------------------------
# Local User Profile cache
# ---------------------------
class UserProfile:
    def __init__(self):
        self._profile_text = None
        self._loaded = False

    def _ensure_loaded(self):
        if not self._loaded:
            uid = get_session_user_uuid()
            self._profile_text = fetch_profile_text(uid) if uid else ""
            self._loaded = True
            print("[PROFILE] loaded" if self._profile_text else "[PROFILE] empty")

    def get(self) -> str:
        self._ensure_loaded()
        return self._profile_text or ""

    def refresh(self):
        self._loaded = False
        return self.get()

user_profile: Optional[UserProfile] = None

# ---------------------------
# FAISS Vector Store (minimal)
# ---------------------------
embedding_dim = 1536
index = faiss.IndexFlatL2(embedding_dim)
vector_store = []  # (text, embedding)

def embed_text(text: str):
    if not client:
        print(f"[EMBEDDING ERROR] OpenAI client not available")
        return np.zeros(embedding_dim, dtype="float32")
    
    try:
        emb = client.embeddings.create(model="text-embedding-3-small", input=text).data[0].embedding
        return np.array(emb, dtype="float32")
    except Exception as e:
        print(f"[EMBEDDING ERROR] {e}")
        return np.zeros(embedding_dim, dtype="float32")

def add_to_vectorstore(text: str):
    emb = embed_text(text)
    index.add(np.array([emb]))
    vector_store.append((text, emb))
    print(f"[RAG] added: {text[:60]}...")

def retrieve_from_vectorstore(query: str, k: int = 3):
    if not vector_store:
        return []
    q_emb = embed_text(query)
    D, I = index.search(np.array([q_emb]), k)
    return [vector_store[i][0] for i in I[0] if i < len(vector_store)]

# ---------------------------
# Key Router
# ---------------------------
def parse_key_route(key: str) -> Dict[str, Any]:
    """
    Supported keys:
      - 'memory:<CATEGORY>:<KEY>'
      - 'profile:text'
      - 'profile:merge'
      - 'profile:field:<column>'
    """
    parts = (key or "").split(":")
    route = {"type": None}

    if len(parts) >= 1 and parts[0] == "memory" and len(parts) >= 3:
        route["type"] = "memory"
        route["category"] = parts[1].upper()
        route["mem_key"] = ":".join(parts[2:])  # allow colons inside the tail
        return route

    if key == "profile:text":
        return {"type": "profile_text"}

    if key == "profile:merge":
        return {"type": "profile_merge"}

    if len(parts) >= 3 and parts[0] == "profile" and parts[1] == "field":
        return {"type": "profile_field", "column": ":".join(parts[2:])}

    return route  # type: None

# ---------------------------
# Assistant + Tools
# ---------------------------
class Assistant(Agent):
    def __init__(self):
        super().__init__(instructions="""
        You are a helpful assistant. Keep responses concise and practical.
        Use the tools to read/update user data by key.
        """)

    @function_tool()
    async def getUserData(self, context: RunContext):
        """Return snapshot of current user's profile/profile_text/memories/onboarding."""
        user_id = get_session_user_uuid()
        if not user_id:
            return {"error": "No valid user UUID bound from LiveKit identity."}
        return {
            "user_uuid": user_id,
            "profile": fetch_profile_row(user_id),
            "profile_text": fetch_profile_text(user_id),
            "memories": fetch_memories(user_id, limit=100),
            "onboarding": fetch_onboarding(user_id),
        }

    @function_tool()
    async def getByKey(self, context: RunContext, key: str):
        """
        Read a value by key route:
          - memory:<CATEGORY>:<KEY>       -> returns memory value
          - profile:text                  -> returns full profile_text
          - profile:field:<column>        -> returns profiles.<column>
        """
        user_id = get_session_user_uuid()
        if not user_id:
            return {"error": "No valid user UUID bound."}

        route = parse_key_route(key)
        if route["type"] == "memory":
            val = fetch_memory_value(user_id, route["category"], route["mem_key"])
            return {"key": key, "value": val}
        if route["type"] == "profile_text":
            return {"key": key, "value": fetch_profile_text(user_id)}
        if route["type"] == "profile_field":
            row = fetch_profile_row(user_id) or {}
            return {"key": key, "value": row.get(route["column"])}
        return {"error": f"Unsupported key format: {key}"}

    @function_tool()
    async def updateByKey(self, context: RunContext, key: str, value: str):
        """
        Update by key route:
          - memory:<CATEGORY>:<KEY>  -> upsert into memory
          - profile:text             -> replace user_profiles.profile_text with 'value'
          - profile:merge            -> merge 'value' into profile_text (model-assisted), then save
          - profile:field:<column>   -> upsert column in public.profiles
        """
        user_id = get_session_user_uuid()
        if not user_id:
            return {"error": "No valid user UUID bound."}

        route = parse_key_route(key)
        if route["type"] is None:
            return {"error": f"Unsupported key format: {key}"}

        if route["type"] == "memory":
            ok = upsert_memory(user_id, route["category"], route["mem_key"], value)
            return {"status": "ok" if ok else "error", "key": key}

        if route["type"] == "profile_text":
            ok = upsert_profile_text(user_id, value)
            if ok and user_profile:
                user_profile.refresh()
            return {"status": "ok" if ok else "error", "key": key}

        if route["type"] == "profile_merge":
            merged = merge_profile_text(user_id, value)
            if user_profile:
                user_profile.refresh()
            return {"status": "ok", "key": key, "merged_profile_text": merged}

        if route["type"] == "profile_field":
            # Coerce booleans/numbers if value looks like JSON
            v: Any = value
            try:
                v = json.loads(value)
            except Exception:
                pass
            ok = upsert_profile_field(user_id, route["column"], v)
            return {"status": "ok" if ok else "error", "key": key}

        return {"error": f"Unhandled route for key: {key}"}

    @function_tool()
    async def testMemorySave(self, context: RunContext, test_message: str):
        """Test memory saving functionality manually"""
        user_id = get_session_user_uuid()
        livekit_identity = get_session_livekit_identity()
        
        print(f"[TEST] LiveKit Identity: {livekit_identity}")
        print(f"[TEST] User UUID: {user_id}")
        print(f"[TEST] Supabase Client: {'Connected' if SB else 'Not connected'}")
        
        if not user_id:
            return {"error": "No user UUID - check LiveKit identity extraction"}
        
        if not SB:
            return {"error": "Supabase not connected - check environment variables"}
        
        # Test memory save
        import time
        timestamp = int(time.time() * 1000)
        memory_key = f"test_{timestamp}"
        
        success = upsert_memory(user_id, "FACT", memory_key, test_message)
        
        return {
            "user_id": user_id,
            "livekit_identity": livekit_identity,
            "supabase_connected": SB is not None,
            "memory_save_success": success,
            "test_key": memory_key,
            "test_message": test_message
        }

    @function_tool()
    async def debugProduction(self, context: RunContext):
        """Debug production environment issues"""
        user_id = get_session_user_uuid()
        livekit_identity = get_session_livekit_identity()
        
        debug_info = {
            "environment": {
                "supabase_url": SUPABASE_URL,
                "supabase_service_role_key_set": bool(SUPABASE_SERVICE_ROLE_KEY),
                "supabase_anon_key_set": bool(SUPABASE_ANON_KEY),
                "supabase_client_connected": SB is not None
            },
            "session": {
                "livekit_identity": livekit_identity,
                "user_uuid": user_id,
                "uuid_extracted": bool(user_id)
            },
            "database": {}
        }
        
        # Test database connectivity
        if SB and user_id:
            try:
                # Test profiles table
                profiles_test = SB.table("profiles").select("id").eq("id", user_id).limit(1).execute()
                debug_info["database"]["profiles_table_accessible"] = True
                debug_info["database"]["profiles_row_exists"] = bool(profiles_test.data)
                
                # Test memory table
                memory_test = SB.table("memory").select("user_id").eq("user_id", user_id).limit(1).execute()
                debug_info["database"]["memory_table_accessible"] = True
                debug_info["database"]["memory_rows_count"] = len(memory_test.data or [])
                
                # Test user_profiles table
                user_profiles_test = SB.table("user_profiles").select("user_id").eq("user_id", user_id).limit(1).execute()
                debug_info["database"]["user_profiles_table_accessible"] = True
                debug_info["database"]["user_profiles_row_exists"] = bool(user_profiles_test.data)
                
            except Exception as e:
                debug_info["database"]["error"] = str(e)
                debug_info["database"]["error_type"] = type(e).__name__
        
        print(f"[PRODUCTION DEBUG] {debug_info}")
        return debug_info

    async def on_user_turn_completed(self, turn_ctx, new_message):
        user_text = new_message.text_content
        print(f"[USER INPUT] {user_text}")
        
        # Print LiveKit session ID for debugging
        user_id = get_session_user_uuid()
        livekit_identity = get_session_livekit_identity()
        print(f"[SESSION DEBUG] LiveKit Identity: {livekit_identity}")
        print(f"[SESSION DEBUG] User UUID: {user_id}")
        
        # Save user input to memory in background
        if user_id:
            import asyncio
            import time
            
            async def save_user_input():
                try:
                    # Create unique memory key with timestamp
                    timestamp = int(time.time() * 1000)
                    memory_key = f"user_input_{timestamp}"
                    
                    # Save to memory
                    success = upsert_memory(user_id, "FACT", memory_key, user_text)
                    if success:
                        print(f"[MEMORY SAVED] {memory_key}: {user_text[:50]}...")
                    else:
                        print(f"[MEMORY ERROR] Failed to save: {user_text[:50]}...")
                        
                    # Also update profile with new information
                    merged_profile = merge_profile_text(user_id, user_text)
                    print(f"[PROFILE UPDATED] {merged_profile[:100]}...")
                    
                except Exception as e:
                    print(f"[SAVE ERROR] {e}")
            
            # Run in background without blocking response
            asyncio.create_task(save_user_input())
        else:
            print("[MEMORY SKIP] No user UUID - cannot save memory")

# ---------------------------
# Entrypoint
# ---------------------------
async def entrypoint(ctx: agents.JobContext):
    """
    - Extract UUID from LiveKit identity strings like 'user-<uuid>'.
    - Bind session to that UUID for all Supabase reads/writes.
    - Expose key-based read/write tools.
    """
    print(f"[ENTRYPOINT] Room: {ctx.room.name}")

    # 1) Bind session user from LiveKit identity (handles 'user-<uuid>' etc.)
    livekit_identity = None
    user_uuid = None
    try:
        participants = ctx.room.remote_participants
        if participants:
            participant = list(participants.values())[0]
            livekit_identity = participant.identity  # e.g., 'user-02e0fa39-...'
            user_uuid = set_session_user_from_identity(livekit_identity)
            print(f"[SESSION INIT] Participant SID: {participant.sid}")
            print(f"[SESSION INIT] LiveKit Identity: {livekit_identity}")
            print(f"[SESSION INIT] Extracted User UUID: {user_uuid}")
            print(f"[SESSION INIT] Supabase Connected: {'Yes' if SB else 'No'}")
            
            # Try to fetch user data from Supabase Auth to verify
            if SB and user_uuid:
                try:
                    # This will show you the user data format in console
                    user_data = SB.auth.admin.get_user_by_id(user_uuid)
                    print(f"[USER DATA] Found user in Supabase Auth:")
                    print(f"[USER DATA] ID: {user_data.user.id}")
                    print(f"[USER DATA] Email: {user_data.user.email}")
                    print(f"[USER DATA] Created: {user_data.user.created_at}")
                    print(f"[USER DATA] Metadata: {user_data.user.user_metadata}")
                except AttributeError:
                    print(f"[USER DATA ERROR] Admin API not available - using service role key")
                except Exception as auth_error:
                    print(f"[USER DATA ERROR] Could not fetch user from Supabase Auth: {auth_error}")
                    print(f"[USER DATA ERROR] This might be normal if using service role key")
        else:
            print("[SESSION] No remote participants. Running without DB-bound user.")
    except Exception as e:
        print(f"[SESSION ERROR] {e}")

    # 2) Initialize local user profile cache (preload if UUID present)
    global user_profile
    user_profile = UserProfile()
    if user_uuid:
        _ = user_profile.get()

    # 3) Initialize TTS + Assistant + Session
    tts = TTS(voice_id="17", output_format="MP3_22050_32")
    assistant = Assistant()

    session = AgentSession(
        stt=lk_openai.STT(model="gpt-4o-transcribe", language="ur"),
        llm=lk_openai.LLM(model="gpt-4o-mini"),
        tts=tts,
        vad=silero.VAD.load(),
    )

    print("[SESSION] Starting LiveKit session…")
    await session.start(room=ctx.room, agent=assistant, room_input_options=RoomInputOptions())
    print("[SESSION] Started")

    # 4) Optional greeting (brief)
    greet_text = "Greet the user warmly in Urdu. Be brief and friendly."
    await session.generate_reply(instructions=greet_text)

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        initialize_process_timeout=60,
    ))
