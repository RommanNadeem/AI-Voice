import os
import uuid
import logging
from typing import Optional
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

# OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Supabase env
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# ---------------------------
# Session Context Management (Thread-safe with ContextVar)
# ---------------------------
_session_user_uuid: ContextVar[Optional[str]] = ContextVar("session_user_uuid", default=None)
_session_livekit_identity: ContextVar[Optional[str]] = ContextVar("session_livekit_identity", default=None)

def livekit_identity_to_uuid(identity: str) -> str:
    """Deterministic UUID (v5) for non-UUID identities."""
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    return str(uuid.uuid5(namespace, identity))

def set_session_user_from_identity(livekit_identity: str) -> str:
    """
    Prefer a real Supabase UUID if identity already is one; otherwise map to a stable UUIDv5.
    """
    user_uuid = livekit_identity
    try:
        uuid.UUID(livekit_identity)  # will raise if not uuid
    except Exception:
        user_uuid = livekit_identity_to_uuid(livekit_identity)

    _session_livekit_identity.set(livekit_identity)
    _session_user_uuid.set(user_uuid)
    print(f"[SESSION] Identity: {livekit_identity} → user_uuid: {user_uuid}")
    return user_uuid

def set_session_user_uuid(user_uuid: str):
    _session_livekit_identity.set(None)
    _session_user_uuid.set(user_uuid)
    print(f"[SESSION] (fallback) user_uuid set → {user_uuid}")

def get_session_user_uuid() -> Optional[str]:
    return _session_user_uuid.get()

def get_session_livekit_identity() -> Optional[str]:
    return _session_livekit_identity.get()

# ---------------------------
# Supabase helpers
# ---------------------------
def get_sb_admin() -> Optional[Client]:
    if not (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY):
        return None
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def get_sb_public() -> Optional[Client]:
    if not (SUPABASE_URL and SUPABASE_ANON_KEY):
        return None
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def bootstrap_user(email: str, password: str) -> Optional[str]:
    """
    Ensure a Supabase auth user exists and return its user_id.
    - Tries sign-in (anon client)
    - If fails, admin-create (service role)
    Also ensures a row in public.profiles (id, email).
    """
    sb_public = get_sb_public()
    sb_admin = get_sb_admin()
    if not sb_public:
        print("[BOOTSTRAP] Missing SUPABASE_ANON_KEY or URL")
        return None
    try:
        # Try sign in first
        auth = sb_public.auth.sign_in_with_password({"email": email, "password": password})
        user_id = auth.user.id
        print(f"[BOOTSTRAP] Signed in: {user_id}")
    except Exception as e:
        print(f"[BOOTSTRAP] Sign-in failed, will try admin create: {e}")
        if not sb_admin:
            print("[BOOTSTRAP] Missing service role key; cannot admin-create user.")
            return None
        auth = sb_admin.auth.admin.create_user({"email": email, "password": password, "email_confirm": True})
        user_id = auth.user.id
        print(f"[BOOTSTRAP] User created: {user_id}")

    # Ensure a profiles row exists (FK target for memory/user_profiles)
    try:
        (sb_admin or sb_public).table("profiles").upsert({
            "id": user_id,
            "email": email,
            "is_first_login": True,
        }).execute()
        print(f"[BOOTSTRAP] profiles row ensured for: {user_id}")
    except Exception as e:
        print(f"[BOOTSTRAP] profiles upsert error: {e}")

    return user_id

# ---------------------------
# Memory Manager
# ---------------------------
class MemoryManager:
    ALLOWED_CATEGORIES = {
        "CAMPAIGNS", "EXPERIENCE", "FACT", "GOAL", "INTEREST",
        "LORE", "OPINION", "PLAN", "PREFERENCE",
        "PRESENTATION", "RELATIONSHIP",
    }

    def __init__(self):
        # Prefer service role for server-side ops; fall back to anon
        self.supabase_url = SUPABASE_URL or "https://your-project.supabase.co"
        self.supabase_key = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY or "your-anon-key"

        if self.supabase_url == "https://your-project.supabase.co" or self.supabase_key == "your-anon-key":
            self.supabase = None
            self.connection_error = "Supabase credentials not configured"
        else:
            try:
                self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
                key_type = "SERVICE_ROLE" if SUPABASE_SERVICE_ROLE_KEY else "ANON"
                print(f"[SUPABASE] Connected using {key_type} key")
                self.connection_error = None
            except Exception as e:
                self.supabase = None
                self.connection_error = str(e)

    def store(self, category: str, key: str, value: str):
        category = (category or "").upper()
        if category not in self.ALLOWED_CATEGORIES:
            category = "FACT"
        if self.supabase is None:
            return f"Stored: [{category}] {key} = {value} (offline)"
        try:
            user_id = get_user_id()
            if not ensure_profile_exists(user_id):
                return f"Error storing: Profile not found for user {user_id}"
            resp = self.supabase.table("memory").upsert({
                "user_id": user_id,
                "category": category,
                "key": key,
                "value": value,
            }).execute()
            if getattr(resp, "error", None):
                print(f"[SUPABASE ERROR] memory upsert: {resp.error}")
            return f"Stored: [{category}] {key} = {value}"
        except Exception as e:
            return f"Error storing: {e}"

    def retrieve(self, category: str, key: str):
        if self.supabase is None:
            return None
        try:
            user_id = get_user_id()
            resp = self.supabase.table("memory").select("value").eq("user_id", user_id).eq("category", category).eq("key", key).execute()
            if getattr(resp, "error", None):
                print(f"[SUPABASE ERROR] memory select: {resp.error}")
            if resp.data:
                return resp.data[0]["value"]
            return None
        except Exception:
            return None

    def retrieve_all(self):
        if self.supabase is None:
            return {}
        try:
            user_id = get_user_id()
            resp = self.supabase.table("memory").select("category, key, value").eq("user_id", user_id).execute()
            if getattr(resp, "error", None):
                print(f"[SUPABASE ERROR] memory select all: {resp.error}")
            return {f"{row['category']}:{row['key']}": row["value"] for row in (resp.data or [])}
        except Exception:
            return {}

    def forget(self, category: str, key: str):
        if self.supabase is None:
            return f"Forgot: [{category}] {key} (offline)"
        try:
            user_id = get_user_id()
            resp = self.supabase.table("memory").delete().eq("user_id", user_id).eq("category", category).eq("key", key).execute()
            if getattr(resp, "error", None):
                print(f"[SUPABASE ERROR] memory delete: {resp.error}")
            return f"Forgot: [{category}] {key}"
        except Exception as e:
            return f"Error forgetting: {e}"

    def save_profile(self, profile_text: str):
        if self.supabase is None:
            return
        try:
            user_id = get_user_id()
            if not ensure_profile_exists(user_id):
                print(f"[PROFILE ERROR] Profile not found for user {user_id}")
                return
            resp = self.supabase.table("user_profiles").upsert({
                "user_id": user_id,
                "profile_text": profile_text,
            }).execute()
            if getattr(resp, "error", None):
                print(f"[SUPABASE ERROR] user_profiles upsert: {resp.error}")
        except Exception as e:
            print(f"[PROFILE ERROR] save_profile: {e}")

    def load_profile(self):
        if self.supabase is None:
            return ""
        try:
            user_id = get_user_id()
            resp = self.supabase.table("user_profiles").select("profile_text").eq("user_id", user_id).execute()
            if getattr(resp, "error", None):
                print(f"[SUPABASE ERROR] user_profiles select: {resp.error}")
            if resp.data:
                return resp.data[0]["profile_text"]
            return ""
        except Exception:
            return ""

memory_manager = MemoryManager()

# ---------------------------
# Authentication Helpers
# ---------------------------
def get_current_user() -> str:
    """Get the current user UUID from session context (or fallback)."""
    try:
        user_uuid = get_session_user_uuid()
        if user_uuid:
            return user_uuid
        print("[AUTH] No session user yet; using fallback")
        return get_or_create_default_user()
    except Exception as e:
        print(f"[AUTH ERROR] Failed to get current user: {e}")
        return get_or_create_default_user()

def get_or_create_default_user() -> str:
    try:
        if memory_manager.supabase is None:
            return "de8f4740-0d33-475c-8fa5-c7538bdddcfa"
        resp = memory_manager.supabase.table("profiles").select("id").limit(1).execute()
        if resp.data and len(resp.data) > 0:
            return resp.data[0]["id"]
        return "de8f4740-0d33-475c-8fa5-c7538bdddcfa"
    except Exception:
        return "de8f4740-0d33-475c-8fa5-c7538bdddcfa"

def ensure_profile_exists(user_id: str, original_identity: Optional[str] = None) -> bool:
    """Ensure a row exists in public.profiles for the user_id."""
    try:
        if memory_manager.supabase is None:
            return True
        resp = memory_manager.supabase.table("profiles").select("id").eq("id", user_id).execute()
        if resp.data:
            return True

        identity_label = original_identity or user_id
        email_base = (original_identity or user_id[:8]).replace(" ", "_")
        print(f"[PROFILE CREATE] Creating profile for: {identity_label}")

        create_resp = memory_manager.supabase.table("profiles").insert({
            "id": user_id,
            "email": f"livekit_{email_base}@companion.local",
            "is_first_login": True,
        }).execute()
        if getattr(create_resp, "error", None):
            print(f"[SUPABASE ERROR] profiles insert: {create_resp.error}")
            return False
        return True
    except Exception as e:
        print(f"[PROFILE ERROR] ensure_profile_exists: {e}")
        return False

def get_user_id() -> str:
    return get_current_user()

# ---------------------------
# Memory Categorization
# ---------------------------
def categorize_user_input(user_text: str) -> str:
    t = (user_text or "").lower()

    goal = ["want to", "want to be", "aspire to", "goal is", "hoping to", "planning to",
            "dream of", "aim to", "strive for", "working towards", "trying to achieve",
            "would like to", "my goal", "my dream", "my aspiration"]
    if any(p in t for p in goal): return "GOAL"

    interest = ["i like", "i love", "i enjoy", "i'm interested in", "my hobby", "hobbies",
                "i'm passionate about", "favorite", "i prefer", "i'm into", "i'm a fan of"]
    if any(p in t for p in interest): return "INTEREST"

    opinion = ["i think", "i believe", "in my opinion", "i feel", "i consider",
               "i'm of the view", "my view is", "i'm convinced", "i disagree", "i agree"]
    if any(p in t for p in opinion): return "OPINION"

    experience = ["i experienced", "i went through", "happened to me", "i had", "i did",
                  "i've been", "i was", "i used to", "i remember", "i recall",
                  "my experience", "when i", "once i"]
    if any(p in t for p in experience): return "EXPERIENCE"

    preference = ["i prefer", "i'd rather", "i like better", "my choice is", "i choose",
                  "instead of", "rather than", "over tea", "over coffee", "better than",
                  "more than", "rather have"]
    if any(p in t for p in preference): return "PREFERENCE"

    plan = ["i'm planning", "i plan to", "i will", "i'm going to", "i intend to",
            "my plan is", "i'm thinking of", "i'm considering", "next week", "tomorrow",
            "this weekend", "i'll do"]
    if any(p in t for p in plan): return "PLAN"

    relationship = ["my friend", "my family", "my partner", "my spouse", "my parents",
                    "my children", "my colleague", "my boss", "my teacher", "my mentor",
                    "my relationship", "we are", "they are", "he is", "she is"]
    if any(p in t for p in relationship): return "RELATIONSHIP"

    campaign = ["my project", "working on", "i'm developing", "building", "creating",
                "campaign", "initiative", "program", "my work on", "i'm building"]
    if any(p in t for p in campaign): return "CAMPAIGNS"

    return "FACT"

# ---------------------------
# Onboarding Integration
# ---------------------------
def get_onboarding_details(user_id: str):
    """Fetch onboarding details for a user from onboarding_details table."""
    try:
        if memory_manager.supabase is None:
            print("[ONBOARDING] Supabase not available")
            return None

        print(f"[ONBOARDING] Querying onboarding_details for user_id: {user_id}")
        resp = memory_manager.supabase.table("onboarding_details").select(
            "full_name, occupation, interests"
        ).eq("user_id", user_id).execute()

        if getattr(resp, "error", None):
            print(f"[SUPABASE ERROR] onboarding_details select: {resp.error}")
            return None

        if resp.data and len(resp.data) > 0:
            details = resp.data[0]
            print(f"[ONBOARDING] ✓ Found details: {details}")
            return details
        else:
            print(f"[ONBOARDING] No onboarding details for {user_id}")
            return None
    except Exception as e:
        print(f"[ONBOARDING ERROR] {e}")
        return None

def populate_profile_from_onboarding(user_id: str):
    """
    Fetch onboarding details and populate user profile with name/occupation/interests.
    Returns first_name if found, else None.
    """
    try:
        onboarding = get_onboarding_details(user_id)
        if not onboarding:
            return None

        full_name = onboarding.get("full_name")
        first_name = (full_name or "").split(" ")[0] if full_name else None
        occupation = onboarding.get("occupation")
        interests = onboarding.get("interests")

        parts = []
        if full_name:
            parts.append(f"Name: {full_name}")
        if occupation:
            parts.append(f"Occupation: {occupation}")
        if interests:
            interests_str = ", ".join(interests) if isinstance(interests, list) else str(interests)
            parts.append(f"Interests: {interests_str}")

        if parts:
            profile_text = " | ".join(parts)
            memory_manager.save_profile(profile_text)
            print(f"[ONBOARDING] Profile seeded → {profile_text}")

        return first_name
    except Exception as e:
        print(f"[ONBOARDING ERROR] Failed to populate profile: {e}")
        return None

# ---------------------------
# Helper Functions
# ---------------------------
def save_user_profile(profile_text: str) -> bool:
    try:
        user_id = get_user_id()
        if not ensure_profile_exists(user_id):
            return False
        resp = memory_manager.supabase.table("user_profiles").upsert({
            "user_id": user_id,
            "profile_text": profile_text,
        }).execute()
        if getattr(resp, "error", None):
            print(f"[SUPABASE ERROR] user_profiles upsert: {resp.error}")
            return False
        print(f"[PROFILE SAVED] user {user_id}")
        return True
    except Exception as e:
        print(f"[PROFILE ERROR] Failed to save profile: {e}")
        return False

def get_user_profile() -> str:
    try:
        user_id = get_user_id()
        resp = memory_manager.supabase.table("user_profiles").select("profile_text").eq("user_id", user_id).execute()
        if getattr(resp, "error", None):
            print(f"[SUPABASE ERROR] user_profiles select: {resp.error}")
        if resp.data:
            return resp.data[0]["profile_text"]
        return ""
    except Exception as e:
        print(f"[PROFILE ERROR] Failed to get profile: {e}")
        return ""

def save_memory(category: str, key: str, value: str) -> bool:
    try:
        user_id = get_user_id()
        if not ensure_profile_exists(user_id):
            return False
        resp = memory_manager.supabase.table("memory").upsert({
            "user_id": user_id,
            "category": category,
            "key": key,
            "value": value,
        }).execute()
        if getattr(resp, "error", None):
            print(f"[SUPABASE ERROR] memory upsert: {resp.error}")
            return False
        print(f"[MEMORY SAVED] [{category}] {key} for user {user_id}")
        return True
    except Exception as e:
        print(f"[MEMORY ERROR] Failed to save memory: {e}")
        return False

# ---------------------------
# User Profile Manager
# ---------------------------
class UserProfile:
    """Lazy-load profile; always resolve user_id at call time."""
    def __init__(self):
        self._profile_text = None
        self._loaded = False

    def _ensure_loaded(self):
        if not self._loaded:
            self._profile_text = memory_manager.load_profile()
            self._loaded = True
            print("[PROFILE] Loaded from storage" if self._profile_text else "[PROFILE] No existing profile")

    def update_profile(self, snippet: str):
        self._ensure_loaded()
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a system that builds and maintains a concise user profile (≤10 lines). "
                            "Include personal info, interests, goals, skills, traits, values, relationships, "
                            "preferences, experiences, activities, and communication style. Most recent info wins. "
                            "No hallucinations."
                        ),
                    },
                    {"role": "system", "content": f"Current profile:\n{self._profile_text}"},
                    {"role": "user", "content": f"New information to incorporate:\n{snippet}"},
                ],
            )
            new_profile = resp.choices[0].message.content.strip()
            self._profile_text = new_profile
            memory_manager.save_profile(new_profile)
            print(f"[PROFILE UPDATED] {new_profile}")
        except Exception as e:
            print(f"[PROFILE ERROR] {e}")
        return self._profile_text

    def smart_update(self, snippet: str):
        self._ensure_loaded()
        skip = ["hello", "hi", "hey", "سلام", "ہیلو", "کیا حال ہے", "کیا ہال ہے",
                "what", "how", "when", "where", "why", "کیا", "کیسے", "کب", "کہاں", "کیوں"]
        if any(p in (snippet or "").lower() for p in skip) and len((snippet or "").split()) <= 3:
            print(f"[PROFILE SKIP] Basic greeting/question: {snippet[:50]}...")
            return self._profile_text
        print(f"[PROFILE UPDATE] Processing: {snippet[:50]}...")
        return self.update_profile(snippet)

    def get(self):
        self._ensure_loaded()
        return self._profile_text

    def forget(self):
        self._ensure_loaded()
        if memory_manager.supabase is None:
            self._profile_text = ""
            return "Profile deleted (offline mode)"
        try:
            user_id = get_user_id()
            resp = memory_manager.supabase.table("user_profiles").delete().eq("user_id", user_id).execute()
            if getattr(resp, "error", None):
                print(f"[SUPABASE ERROR] user_profiles delete: {resp.error}")
                return "Error deleting profile"
            self._profile_text = ""
            print(f"[PROFILE FORGOT] for {user_id}")
            return f"Profile deleted for {user_id}"
        except Exception as e:
            print(f"[SUPABASE ERROR] Forget profile failed: {e}")
            return f"Error deleting profile: {e}"

# Defer creation until entrypoint
user_profile: Optional[UserProfile] = None

# ---------------------------
# FAISS Vector Store (RAG)
# ---------------------------
embedding_dim = 1536
index = faiss.IndexFlatL2(embedding_dim)
vector_store = []  # (text, embedding)

def embed_text(text: str):
    emb = client.embeddings.create(model="text-embedding-3-small", input=text).data[0].embedding
    return np.array(emb, dtype="float32")

def add_to_vectorstore(text: str):
    emb = embed_text(text)
    index.add(np.array([emb]))
    vector_store.append((text, emb))
    print(f"[RAG STORED] {text[:60]}...")

def retrieve_from_vectorstore(query: str, k: int = 3):
    if not vector_store:
        return []
    q_emb = embed_text(query)
    D, I = index.search(np.array([q_emb]), k)
    return [vector_store[i][0] for i in I[0] if i < len(vector_store)]

# ---------------------------
# Assistant Agent with Tools
# ---------------------------
class Assistant(Agent):
    def __init__(self):
        super().__init__(instructions="""
        ## Overall Role
        ... (prompt content unchanged) ...
        """)

    @function_tool()
    async def storeInMemory(self, context: RunContext, category: str, key: str, value: str):
        return {"result": memory_manager.store(category, key, value)}

    @function_tool()
    async def retrieveFromMemory(self, context: RunContext, category: str, key: str):
        val = memory_manager.retrieve(category, key)
        return {"value": val or ""}

    @function_tool()
    async def forgetMemory(self, context: RunContext, category: str, key: str):
        return {"result": memory_manager.forget(category, key)}

    @function_tool()
    async def listAllMemories(self, context: RunContext):
        return {"memories": memory_manager.retrieve_all()}

    # ---- Profile Tools ----
    @function_tool()
    async def updateUserProfile(self, context: RunContext, new_info: str):
        return {"updated_profile": user_profile.update_profile(new_info)}

    @function_tool()
    async def getUserProfile(self, context: RunContext):
        return {"profile": user_profile.get()}

    @function_tool()
    async def forgetUserProfile(self, context: RunContext):
        return {"result": user_profile.forget()}

    async def on_user_turn_completed(self, turn_ctx, new_message):
        user_text = new_message.text_content
        print(f"[USER INPUT] {user_text}")

        # Fire-and-forget background write (no profile update here)
        import asyncio, time
        async def store_user_data_async():
            try:
                ts = int(time.time() * 1000)
                memory_key = f"user_input_{ts}"
                category = categorize_user_input(user_text)
                print(f"[MEMORY CATEGORIZATION] '{user_text[:50]}...' -> {category}")
                result = memory_manager.store(category, memory_key, user_text)
                print(f"[MEMORY STORED] {result}")
            except Exception as e:
                print(f"[STORAGE ERROR] Background storage failed: {e}")
        asyncio.create_task(store_user_data_async())

# ---------------------------
# Entrypoint
# ---------------------------
async def entrypoint(ctx: agents.JobContext):
    """
    LiveKit agent entrypoint:
    - Bootstrap a test user (server-side)
    - Bind session user BEFORE starting the session
    - Ensure profile exists
    - Seed profile + memory for that user (guaranteed write)
    """
    print(f"[ENTRYPOINT] Starting session for room: {ctx.room.name}")

    # (Optional) Bootstrap your test user one-time (or set TEST_EMAIL/TEST_PASSWORD envs)
    TEST_EMAIL = os.getenv("TEST_EMAIL") or "test3@gmail.com"
    TEST_PASSWORD = os.getenv("TEST_PASSWORD") or "12345678"
    try:
        bootstrap_user(TEST_EMAIL, TEST_PASSWORD)
    except Exception as e:
        print(f"[BOOTSTRAP WARN] {e}")

    # 1) Extract identity early and bind session user
    livekit_identity = None
    user_uuid = None
    try:
        participants = ctx.room.remote_participants
        if participants:
            participant = list(participants.values())[0]
            livekit_identity = participant.identity
            # If you mint LiveKit token with identity = auth.users.id, this stays a real UUID
            user_uuid = set_session_user_from_identity(livekit_identity)
            print(f"[SESSION INIT] Room: {ctx.room.name}")
            print(f"[SESSION INIT] Participant SID: {participant.sid}")
        else:
            print("[SESSION WARNING] No remote participants found - using fallback user")
            user_uuid = get_or_create_default_user()
            set_session_user_uuid(user_uuid)
    except Exception as e:
        print(f"[SESSION ERROR] Failed to extract participant: {e}")
        user_uuid = get_or_create_default_user()
        set_session_user_uuid(user_uuid)

    # 2) Ensure profile exists FOR THIS user and seed DB (profile + memory) BEFORE session start
    first_name = None
    if user_uuid:
        print(f"[SESSION INIT] Ensuring profile exists for UUID: {user_uuid}")
        if ensure_profile_exists(user_uuid, original_identity=livekit_identity):
            print(f"[SESSION INIT] ✓ Profile ready for user: {user_uuid}")

            # Try onboarding (optional)
            try:
                first_name = populate_profile_from_onboarding(user_uuid)
            except Exception as e:
                print(f"[SESSION INIT ERROR] Onboarding fetch failed: {e}")
                first_name = None

            # --- GUARANTEED WRITES: profile + one memory row ---
            # (These will always run and persist to Supabase for this session user)
            profile_text = f"Name: {first_name or 'Test User'} | Occupation: Tester | Interests: AI, coding, tea"
            memory_manager.save_profile(profile_text)
            print("[SEED] user_profiles upserted")

            save_memory("PREFERENCE", "beverage", "chai")
            print("[SEED] memory upserted: [PREFERENCE] beverage = chai")
            # ---------------------------------------------------
        else:
            print("[SESSION WARNING] Could not ensure profile exists")
    else:
        print("[SESSION WARNING] No user_uuid resolved; skipping seed")

    # 3) Initialize TTS and Assistant
    global user_profile
    user_profile = UserProfile()  # now that session user is set

    tts = TTS(voice_id="17", output_format="MP3_22050_32")
    assistant = Assistant()

    # 4) Create and start session
    session = AgentSession(
        stt=lk_openai.STT(model="gpt-4o-transcribe", language="ur"),
        llm=lk_openai.LLM(model="gpt-4o-mini"),
        tts=tts,
        vad=silero.VAD.load(),
    )

    print("[SESSION INIT] Starting LiveKit session…")
    await session.start(room=ctx.room, agent=assistant, room_input_options=RoomInputOptions())
    print("[SESSION INIT] ✓ Session started")

    # Minimal greeting (optionally personalized)
    async def generate_with_memory(greet: bool = False, user_first_name: Optional[str] = None):
        base_instructions = assistant.instructions
        if greet:
            if user_first_name:
                instr = f"Greet the user warmly in Urdu using their name '{user_first_name}'. Make them feel welcome.\n\n{base_instructions}"
            else:
                instr = f"Greet the user warmly in Urdu.\n\n{base_instructions}"
            await session.generate_reply(instructions=instr)
        else:
            await session.generate_reply(instructions=base_instructions)

    await generate_with_memory(greet=True, user_first_name=first_name)

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        initialize_process_timeout=60,
    ))
