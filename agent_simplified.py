"""
Simplified Companion Agent - Clean Architecture
Based on working old pattern, adapted for Supabase
"""

import os
import logging
import asyncio
from typing import Optional
from supabase import create_client, Client
from livekit import agents, rtc
from livekit.agents import AgentSession, Agent, RoomInputOptions, RunContext, function_tool
from livekit.plugins import openai as lk_openai
from livekit.plugins import silero
from uplift_tts import TTS
from openai import OpenAI

# ---------------------------
# Setup
# ---------------------------
logging.basicConfig(level=logging.INFO)

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# OpenAI for categorization and embeddings
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------------
# Simple Memory Manager (Supabase)
# ---------------------------
class MemoryManager:
    ALLOWED_CATEGORIES = [
        "FACT", "GOAL", "INTEREST", "EXPERIENCE", 
        "PREFERENCE", "RELATIONSHIP", "PLAN", "OPINION"
    ]
    
    def __init__(self, user_id: str):
        self.user_id = user_id
    
    def store(self, category: str, key: str, value: str):
        """Store memory in Supabase"""
        category = category.upper()
        if category not in self.ALLOWED_CATEGORIES:
            category = "FACT"
        
        try:
            data = {
                "user_id": self.user_id,
                "category": category,
                "key": key,
                "value": value
            }
            supabase.table("memory").upsert(data).execute()
            print(f"[MEMORY STORED] [{category}] {key}")
            return f"Stored: [{category}] {key}"
        except Exception as e:
            print(f"[MEMORY ERROR] {e}")
            return f"Error: {e}"
    
    def retrieve(self, category: str, key: str):
        """Retrieve memory from Supabase"""
        try:
            resp = supabase.table("memory").select("value")\
                .eq("user_id", self.user_id)\
                .eq("category", category)\
                .eq("key", key)\
                .execute()
            if resp.data:
                return resp.data[0]["value"]
            return None
        except Exception as e:
            print(f"[MEMORY ERROR] {e}")
            return None
    
    def retrieve_all(self):
        """Get all memories for context"""
        try:
            resp = supabase.table("memory").select("category, key, value")\
                .eq("user_id", self.user_id)\
                .limit(50)\
                .execute()
            return {f"{m['category']}:{m['key']}": m['value'] for m in resp.data}
        except Exception as e:
            print(f"[MEMORY ERROR] {e}")
            return {}
    
    def forget(self, category: str, key: str):
        """Delete memory"""
        try:
            supabase.table("memory").delete()\
                .eq("user_id", self.user_id)\
                .eq("category", category)\
                .eq("key", key)\
                .execute()
            print(f"[MEMORY FORGOT] [{category}] {key}")
            return f"Forgot: [{category}] {key}"
        except Exception as e:
            print(f"[MEMORY ERROR] {e}")
            return f"Error: {e}"


# ---------------------------
# Simple Profile Manager (Supabase)
# ---------------------------
class ProfileManager:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.profile_text = self.load_profile()
    
    def load_profile(self):
        """Load profile from Supabase"""
        try:
            resp = supabase.table("profiles").select("profile")\
                .eq("user_id", self.user_id)\
                .execute()
            if resp.data:
                print(f"[PROFILE LOADED] for {self.user_id}")
                return resp.data[0]["profile"]
            print(f"[PROFILE EMPTY] No profile for {self.user_id}")
            return ""
        except Exception as e:
            print(f"[PROFILE ERROR] {e}")
            return ""
    
    def update_profile(self, new_info: str):
        """Update profile using OpenAI"""
        try:
            resp = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """Build comprehensive user profile. Include: personal info, interests, 
                        goals, personality, relationships, preferences. Keep concise (max 10 lines). 
                        Resolve contradictions with most recent info. Don't hallucinate."""
                    },
                    {"role": "system", "content": f"Current profile:\n{self.profile_text}"},
                    {"role": "user", "content": f"New information:\n{new_info}"}
                ]
            )
            new_profile = resp.choices[0].message.content.strip()
            self.profile_text = new_profile
            
            # Save to Supabase
            supabase.table("profiles").upsert({
                "user_id": self.user_id,
                "profile": new_profile
            }).execute()
            
            print(f"[PROFILE UPDATED]")
            return new_profile
        except Exception as e:
            print(f"[PROFILE ERROR] {e}")
            return self.profile_text
    
    def smart_update(self, text: str):
        """Update profile, skipping trivial inputs"""
        # Skip very short greetings/questions
        skip_patterns = ["hello", "hi", "hey", "سلام", "what", "how", "کیا", "کیسے"]
        if len(text.split()) <= 3 and any(p in text.lower() for p in skip_patterns):
            return self.profile_text
        
        if len(text.strip()) > 15:
            return self.update_profile(text)
        return self.profile_text
    
    def get(self):
        return self.profile_text


# ---------------------------
# Simple RAG (in-memory for now)
# ---------------------------
class SimpleRAG:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.memories = []  # List of (text, category) tuples
    
    def add(self, text: str, category: str):
        """Add to RAG memory"""
        self.memories.append((text, category))
        print(f"[RAG STORED] {text[:50]}...")
    
    def search(self, query: str, limit: int = 3):
        """Simple keyword search (can upgrade to vector search later)"""
        # For now, just return recent memories
        return [m[0] for m in self.memories[-limit:]]


# ---------------------------
# Assistant Agent
# ---------------------------
class Assistant(Agent):
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.memory_manager = MemoryManager(user_id)
        self.profile_manager = ProfileManager(user_id)
        self.rag = SimpleRAG(user_id)
        
        # Your prompt here
        base_instructions = """
# Humraaz – Urdu Companion

You are **Humraaz**, a warm, witty, platonic female friend in Urdu.

## Role
- Trusted conversational buddy: curious, supportive, lightly playful
- Encourage reflection naturally
- Match user's mood and energy
- Balance casual talk with deeper conversations

## Communication Style
- **Language:** Casual Urdu only
- **Length:** 1-2 short sentences
- **Tone:** Warm, caring, playful
- **Questions:** One clean, open-ended question per turn
- **Boundaries:** Strictly platonic

## Tools
- `storeInMemory(category, key, value)` - Save user facts
- `retrieveFromMemory(category, key)` - Recall saved info
- `getUserProfile()` - Get user profile
- `updateUserProfile(new_info)` - Update profile

**Categories:** FACT, GOAL, INTEREST, EXPERIENCE, PREFERENCE, RELATIONSHIP, PLAN, OPINION

**Important:** Keys must be in English (e.g., "favorite_food"). Values can be Urdu.
"""
        super().__init__(instructions=base_instructions)
    
    # ===== TOOLS =====
    @function_tool()
    async def storeInMemory(self, context: RunContext, category: str, key: str, value: str):
        """Store memory"""
        result = self.memory_manager.store(category, key, value)
        return {"result": result}
    
    @function_tool()
    async def retrieveFromMemory(self, context: RunContext, category: str, key: str):
        """Retrieve memory"""
        value = self.memory_manager.retrieve(category, key)
        return {"value": value or ""}
    
    @function_tool()
    async def forgetMemory(self, context: RunContext, category: str, key: str):
        """Delete memory"""
        result = self.memory_manager.forget(category, key)
        return {"result": result}
    
    @function_tool()
    async def getUserProfile(self, context: RunContext):
        """Get user profile"""
        return {"profile": self.profile_manager.get()}
    
    @function_tool()
    async def updateUserProfile(self, context: RunContext, new_info: str):
        """Update user profile"""
        updated = self.profile_manager.update_profile(new_info)
        return {"updated_profile": updated}
    
    # ===== AUTO-SAVE ON USER INPUT (Clean Pattern!) =====
    async def on_user_turn_completed(self, turn_ctx, new_message):
        """Automatically save user input - NO WORKAROUND NEEDED!"""
        user_text = new_message.text_content or ""
        if not user_text:
            return
        
        print(f"[USER] {user_text}")
        
        # Auto-save to RAG
        self.rag.add(user_text, "USER_INPUT")
        
        # Auto-update profile
        self.profile_manager.smart_update(user_text)
        
        # Optionally auto-categorize and save to memory
        category = self.categorize(user_text)
        import time
        key = f"conv_{int(time.time() * 1000)}"
        self.memory_manager.store(category, key, user_text)
    
    def categorize(self, text: str) -> str:
        """Categorize user input"""
        try:
            resp = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Categorize into: FACT, GOAL, INTEREST, EXPERIENCE, PREFERENCE, RELATIONSHIP, PLAN, OPINION. Return only category name."},
                    {"role": "user", "content": text}
                ],
                max_tokens=10
            )
            return resp.choices[0].message.content.strip().upper()
        except:
            return "FACT"


# ---------------------------
# Entrypoint
# ---------------------------
async def entrypoint(ctx: agents.JobContext):
    # Get user ID from participant
    await ctx.room.wait_for_participant()
    participant = list(ctx.room.remote_participants.values())[0]
    user_id = participant.identity  # Assuming identity is UUID
    
    print(f"[SESSION START] User: {user_id}")
    
    # Initialize
    tts = TTS(voice_id="v_8eelc901", output_format="MP3_22050_32")
    assistant = Assistant(user_id)
    
    session = AgentSession(
        stt=lk_openai.STT(model="gpt-4o-transcribe", language="ur"),
        llm=lk_openai.LLM(model="gpt-4o-mini", temperature=0.8),
        tts=tts,
        vad=silero.VAD.load(),
    )
    
    await session.start(
        room=ctx.room,
        agent=assistant,
        room_input_options=RoomInputOptions()
    )
    
    # Generate greeting with context
    await generate_with_context(session, assistant, greet=True)


async def generate_with_context(session: AgentSession, assistant: Assistant, user_text: str = None, greet: bool = False):
    """Generate reply with memory/profile context injected"""
    # Get context
    memories = assistant.memory_manager.retrieve_all()
    profile = assistant.profile_manager.get()
    rag_context = assistant.rag.search(user_text or "recent", limit=3)
    
    # Build context
    context = f"""
User Profile: {profile}

Known Memories: {memories}

Recent Context: {rag_context}
"""
    
    # Generate
    if greet:
        await session.generate_reply(
            instructions=f"Greet user warmly in Urdu.\n\n{context}"
        )
    else:
        await session.generate_reply(
            instructions=f"{assistant.instructions}\n\nContext:\n{context}\n\nUser: {user_text}"
        )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
    ))

