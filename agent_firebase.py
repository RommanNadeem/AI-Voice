import os
import re
import uuid
import json
import logging
from typing import Optional, Dict, Any, List
from contextvars import ContextVar
from datetime import datetime

import faiss
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

# Firebase imports
import firebase_admin
from firebase_admin import credentials, firestore, auth
from google.cloud.firestore import Client as FirestoreClient

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

# Firebase Configuration
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
FIREBASE_PRIVATE_KEY = os.getenv("FIREBASE_PRIVATE_KEY")
FIREBASE_CLIENT_EMAIL = os.getenv("FIREBASE_CLIENT_EMAIL")
FIREBASE_CLIENT_ID = os.getenv("FIREBASE_CLIENT_ID")

# Initialize Firebase Admin SDK
def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    if not all([FIREBASE_PROJECT_ID, FIREBASE_PRIVATE_KEY, FIREBASE_CLIENT_EMAIL]):
        print("[ERROR] Missing Firebase configuration")
        return None, None
    
    try:
        # Create credentials from environment variables
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": FIREBASE_PROJECT_ID,
            "private_key": FIREBASE_PRIVATE_KEY.replace('\\n', '\n'),
            "client_email": FIREBASE_CLIENT_EMAIL,
            "client_id": FIREBASE_CLIENT_ID,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        })
        
        # Initialize Firebase Admin
        firebase_admin.initialize_app(cred)
        
        # Get Firestore client
        db = firestore.client()
        
        print("[SUCCESS] Firebase initialized successfully")
        return db, auth
        
    except Exception as e:
        print(f"[ERROR] Failed to initialize Firebase: {e}")
        return None, None

# Initialize Firebase
db: Optional[FirestoreClient] = None
firebase_auth = None
db, firebase_auth = initialize_firebase()

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
# Firebase Database Helpers
# ---------------------------
def ensure_user_profile(user_id: str, email_hint: Optional[str] = None) -> bool:
    """
    Ensure a user profile exists in Firestore for the given user_id.
    """
    print(f"[FIREBASE DEBUG] Ensuring user profile for user: {user_id}")
    
    if not db:
        print(f"[FIREBASE ERROR] Firestore client not available")
        return False
        
    if not user_id:
        print(f"[FIREBASE ERROR] No user ID provided")
        return False
        
    try:
        # Check if user profile exists
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            print(f"[FIREBASE SUCCESS] User profile already exists")
            return True
            
        print(f"[FIREBASE DEBUG] Creating new user profile...")
        email = email_hint or f"user_{user_id[:8]}@local"
        
        # Create user profile
        user_data = {
            'id': user_id,
            'email': email,
            'is_first_login': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        user_ref.set(user_data)
        print(f"[FIREBASE SUCCESS] User profile created successfully")
        return True
        
    except Exception as e:
        print(f"[FIREBASE ERROR] ensure_user_profile failed: {e}")
        print(f"[FIREBASE ERROR] Exception type: {type(e).__name__}")
        import traceback
        print(f"[FIREBASE ERROR] Full traceback: {traceback.format_exc()}")
        return False

def fetch_profile_text(user_id: str) -> str:
    if not (db and user_id):
        return ""
    try:
        profile_ref = db.collection('user_profiles').document(user_id)
        profile_doc = profile_ref.get()
        
        if profile_doc.exists:
            return profile_doc.to_dict().get('profile_text', '')
    except Exception as e:
        print(f"[FIREBASE ERROR] user_profiles select error: {e}")
    return ""

def upsert_profile_text(user_id: str, text: str) -> bool:
    if not (db and user_id):
        return False
    try:
        if not ensure_user_profile(user_id):
            return False
            
        profile_ref = db.collection('user_profiles').document(user_id)
        profile_ref.set({
            'user_id': user_id,
            'profile_text': text,
            'updated_at': datetime.utcnow()
        }, merge=True)
        return True
    except Exception as e:
        print(f"[FIREBASE ERROR] user_profiles upsert error: {e}")
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

def fetch_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    if not (db and user_id):
        return None
    try:
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            return user_doc.to_dict()
    except Exception as e:
        print(f"[FIREBASE ERROR] users select error: {e}")
    return None

def fetch_memories(user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    if not (db and user_id):
        return []
    try:
        memories_ref = db.collection('memories').where('user_id', '==', user_id).limit(limit)
        memories = memories_ref.stream()
        
        return [{'id': doc.id, **doc.to_dict()} for doc in memories]
    except Exception as e:
        print(f"[FIREBASE ERROR] memories select error: {e}")
        return []

def upsert_memory(user_id: str, category: str, key: str, value: str) -> bool:
    print(f"[MEMORY DEBUG] Attempting to save memory:")
    print(f"[MEMORY DEBUG] - User ID: {user_id}")
    print(f"[MEMORY DEBUG] - Category: {category}")
    print(f"[MEMORY DEBUG] - Key: {key}")
    print(f"[MEMORY DEBUG] - Value: {value[:100]}...")
    print(f"[MEMORY DEBUG] - Firestore Client: {'Connected' if db else 'Not connected'}")
    
    if not db:
        print(f"[MEMORY ERROR] Firestore client not available")
        return False
        
    if not user_id:
        print(f"[MEMORY ERROR] No user ID provided")
        return False
        
    try:
        print(f"[MEMORY DEBUG] Ensuring user profile exists...")
        profile_ok = ensure_user_profile(user_id)
        print(f"[MEMORY DEBUG] User profile check: {'OK' if profile_ok else 'FAILED'}")
        
        if not profile_ok:
            print(f"[MEMORY ERROR] Could not ensure user profile exists")
            return False
            
        print(f"[MEMORY DEBUG] Attempting Firestore upsert...")
        
        # Create memory document
        memory_data = {
            'user_id': user_id,
            'category': (category or "FACT").upper(),
            'key': key,
            'value': value,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        # Use key as document ID for upsert behavior
        memory_ref = db.collection('memories').document(f"{user_id}_{key}")
        memory_ref.set(memory_data, merge=True)
        
        print(f"[MEMORY SUCCESS] Memory saved successfully!")
        return True
        
    except Exception as e:
        print(f"[MEMORY ERROR] Firestore upsert failed: {e}")
        print(f"[MEMORY ERROR] Exception type: {type(e).__name__}")
        import traceback
        print(f"[MEMORY ERROR] Full traceback: {traceback.format_exc()}")
        return False

def fetch_memory_value(user_id: str, category: str, key: str) -> Optional[str]:
    if not (db and user_id):
        return None
    try:
        memory_ref = db.collection('memories').document(f"{user_id}_{key}")
        memory_doc = memory_ref.get()
        
        if memory_doc.exists:
            data = memory_doc.to_dict()
            if data.get('category') == category:
                return data.get('value')
    except Exception as e:
        print(f"[FIREBASE ERROR] memory select one error: {e}")
    return None

def fetch_onboarding(user_id: str) -> Optional[Dict[str, Any]]:
    if not (db and user_id):
        return None
    try:
        onboarding_ref = db.collection('onboarding_details').document(user_id)
        onboarding_doc = onboarding_ref.get()
        
        if onboarding_doc.exists:
            return onboarding_doc.to_dict()
    except Exception as e:
        print(f"[FIREBASE ERROR] onboarding_details select error: {e}")
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
            "profile": fetch_user_profile(user_id),
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
          - profile:field:<column>        -> returns users.<column>
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
            row = fetch_user_profile(user_id) or {}
            return {"key": key, "value": row.get(route["column"])}
        return {"error": f"Unsupported key format: {key}"}

    @function_tool()
    async def updateByKey(self, context: RunContext, key: str, value: str):
        """
        Update by key route:
          - memory:<CATEGORY>:<KEY>  -> upsert into memory
          - profile:text             -> replace user_profiles.profile_text with 'value'
          - profile:merge            -> merge 'value' into profile_text (model-assisted), then save
          - profile:field:<column>   -> upsert column in users collection
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
            # Update user document field
            if not db:
                return {"error": "Firestore not available"}
            try:
                user_ref = db.collection('users').document(user_id)
                user_ref.update({
                    route["column"]: value,
                    'updated_at': datetime.utcnow()
                })
                return {"status": "ok", "key": key}
            except Exception as e:
                return {"error": f"Failed to update field: {e}"}

        return {"error": f"Unhandled route for key: {key}"}

    @function_tool()
    async def testMemorySave(self, context: RunContext, test_message: str):
        """Test memory saving functionality manually"""
        user_id = get_session_user_uuid()
        livekit_identity = get_session_livekit_identity()
        
        print(f"[TEST] LiveKit Identity: {livekit_identity}")
        print(f"[TEST] User UUID: {user_id}")
        print(f"[TEST] Firestore Client: {'Connected' if db else 'Not connected'}")
        
        if not user_id:
            return {"error": "No user UUID - check LiveKit identity extraction"}
        
        if not db:
            return {"error": "Firestore not connected - check Firebase configuration"}
        
        # Test memory save
        import time
        timestamp = int(time.time() * 1000)
        memory_key = f"test_{timestamp}"
        
        success = upsert_memory(user_id, "FACT", memory_key, test_message)
        
        return {
            "user_id": user_id,
            "livekit_identity": livekit_identity,
            "firestore_connected": db is not None,
            "memory_save_success": success,
            "test_key": memory_key,
            "test_message": test_message
        }

    @function_tool()
    async def debugFirebase(self, context: RunContext):
        """Debug Firebase environment issues"""
        user_id = get_session_user_uuid()
        livekit_identity = get_session_livekit_identity()
        
        debug_info = {
            "environment": {
                "firebase_project_id": FIREBASE_PROJECT_ID,
                "firebase_private_key_set": bool(FIREBASE_PRIVATE_KEY),
                "firebase_client_email_set": bool(FIREBASE_CLIENT_EMAIL),
                "firestore_client_connected": db is not None,
                "firebase_auth_available": firebase_auth is not None
            },
            "session": {
                "livekit_identity": livekit_identity,
                "user_uuid": user_id,
                "uuid_extracted": bool(user_id)
            },
            "database": {}
        }
        
        # Test database connectivity
        if db and user_id:
            try:
                # Test users collection
                user_ref = db.collection('users').document(user_id)
                user_doc = user_ref.get()
                debug_info["database"]["users_collection_accessible"] = True
                debug_info["database"]["user_document_exists"] = user_doc.exists
                
                # Test memories collection
                memories_ref = db.collection('memories').where('user_id', '==', user_id).limit(1)
                memories = list(memories_ref.stream())
                debug_info["database"]["memories_collection_accessible"] = True
                debug_info["database"]["memories_count"] = len(memories)
                
                # Test user_profiles collection
                profile_ref = db.collection('user_profiles').document(user_id)
                profile_doc = profile_ref.get()
                debug_info["database"]["user_profiles_collection_accessible"] = True
                debug_info["database"]["user_profile_exists"] = profile_doc.exists
                
            except Exception as e:
                debug_info["database"]["error"] = str(e)
                debug_info["database"]["error_type"] = type(e).__name__
        
        print(f"[FIREBASE DEBUG] {debug_info}")
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
    - Bind session to that UUID for all Firebase reads/writes.
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
            print(f"[SESSION INIT] Firestore Connected: {'Yes' if db else 'No'}")
            
            # Try to fetch user data from Firebase Auth to verify
            if firebase_auth and user_uuid:
                try:
                    # This will show you the user data format in console
                    user_data = firebase_auth.get_user(user_uuid)
                    print(f"[USER DATA] Found user in Firebase Auth:")
                    print(f"[USER DATA] UID: {user_data.uid}")
                    print(f"[USER DATA] Email: {user_data.email}")
                    print(f"[USER DATA] Created: {user_data.user_metadata.get('creation_timestamp')}")
                    print(f"[USER DATA] Metadata: {user_data.custom_claims}")
                except Exception as auth_error:
                    print(f"[USER DATA ERROR] Could not fetch user from Firebase Auth: {auth_error}")
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
