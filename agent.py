import os
import faiss
import numpy as np
import logging
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client, Client

# Disable verbose HTTP/2 logging
logging.getLogger("hpack.hpack").setLevel(logging.WARNING)
logging.getLogger("hpack.table").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

import livekit.agents as agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, function_tool, RunContext
from livekit.plugins import openai as lk_openai
from livekit.plugins import silero
from uplift_tts import TTS

# ---------------------------
# Setup
# ---------------------------
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------------
# Memory Manager
# ---------------------------
class MemoryManager:
    ALLOWED_CATEGORIES = {
        "CAMPAIGNS", "EXPERIENCE", "FACT", "GOAL", "INTEREST",
        "LORE", "OPINION", "PLAN", "PREFERENCE",
        "PRESENTATION", "RELATIONSHIP"
    }

    def __init__(self):
        # Supabase configuration
        self.supabase_url = os.getenv('SUPABASE_URL', 'https://your-project.supabase.co')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY', 'your-anon-key')
        
        # Check if Supabase credentials are properly configured
        if self.supabase_url == 'https://your-project.supabase.co' or self.supabase_key == 'your-anon-key':
            self.supabase = None
            self.connection_error = "Supabase credentials not configured"
        else:
            try:
                self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
                print(f"[SUPABASE] Connected")
                self.connection_error = None
            except Exception as e:
                self.supabase = None
                self.connection_error = str(e)

    def store(self, category: str, key: str, value: str):
        category = category.upper()
        if category not in self.ALLOWED_CATEGORIES:
            category = "FACT"
        
        if self.supabase is None:
            return f"Stored: [{category}] {key} = {value} (offline)"
        
        try:
            # Get current user ID
            user_id = get_user_id()
            
            # Ensure profile exists first
            if not ensure_profile_exists(user_id):
                return f"Error storing: Profile not found for user {user_id}"
            
            # Use upsert to insert or update
            response = self.supabase.table('memory').upsert({
                'user_id': user_id,
                'category': category,
                'key': key,
                'value': value
            }).execute()
            
            return f"Stored: [{category}] {key} = {value}"
        except Exception as e:
            return f"Error storing: {e}"

    def retrieve(self, category: str, key: str):
        if self.supabase is None:
            return None
        
        try:
            # Get current user ID
            user_id = get_user_id()
            
            response = self.supabase.table('memory').select('value').eq('user_id', user_id).eq('category', category).eq('key', key).execute()
            if response.data:
                return response.data[0]['value']
            return None
        except Exception as e:
            return None

    def retrieve_all(self):
        if self.supabase is None:
            return {}
        
        try:
            # Get current user ID
            user_id = get_user_id()
            
            response = self.supabase.table('memory').select('*').eq('user_id', user_id).execute()
            if response.data:
                return {f"{item['category']}:{item['key']}": item['value'] for item in response.data}
            return {}
        except Exception as e:
            print(f"[SUPABASE ERROR] Retrieve all failed: {e}")
            return {}

    def forget(self, category: str, key: str):
        if self.supabase is None:
            return f"Forgot: [{category}] {key} (offline)"
        
        try:
            # Get current user ID
            user_id = get_user_id()
            
            response = self.supabase.table('memory').delete().eq('user_id', user_id).eq('category', category).eq('key', key).execute()
            return f"Forgot: [{category}] {key}"
        except Exception as e:
            return f"Error forgetting: {e}"

memory_manager = MemoryManager()

# ---------------------------
# User Profile Management
# ---------------------------
class UserProfile:
    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL', 'https://your-project.supabase.co')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY', 'your-anon-key')
        
        if self.supabase_url == 'https://your-project.supabase.co' or self.supabase_key == 'your-anon-key':
            self.supabase = None
            self.connection_error = "Supabase credentials not configured"
        else:
            try:
                self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
                self.connection_error = None
            except Exception as e:
                self.supabase = None
                self.connection_error = str(e)

    def save_profile(self, profile_text: str):
        if self.supabase is None:
            return f"Profile saved (offline): {profile_text[:50]}..."
        
        try:
            # Get current user ID
            user_id = get_user_id()
            
            # Ensure profile exists first
            if not ensure_profile_exists(user_id):
                return f"Error saving profile: Profile not found for user {user_id}"
            
            # Use upsert to insert or update
            response = self.supabase.table('user_profiles').upsert({
                'user_id': user_id,
                'profile_text': profile_text
            }).execute()
            
            print(f"[User Profile Updated]: {profile_text}")
            return f"Profile saved successfully"
        except Exception as e:
            return f"Error saving profile: {e}"

    def get_profile(self):
        if self.supabase is None:
            return None
        
        try:
            # Get current user ID
            user_id = get_user_id()
            
            response = self.supabase.table('user_profiles').select('profile_text').eq('user_id', user_id).execute()
            if response.data:
                return response.data[0]['profile_text']
            return None
        except Exception as e:
            return None

    def forget(self, profile_text: str):
        if self.supabase is None:
            return f"Profile forgotten (offline): {profile_text[:50]}..."
        
        try:
            # Get current user ID
            user_id = get_user_id()
            
            response = self.supabase.table('user_profiles').delete().eq('user_id', user_id).execute()
            return f"Profile forgotten"
        except Exception as e:
            return f"Error deleting profile: {e}"

user_profile = UserProfile()

# ---------------------------
# Helper Functions
# ---------------------------
def get_current_user():
    """Get the current authenticated user from Supabase."""
    try:
        if memory_manager.supabase is None:
            print("[AUTH] Supabase not available")
            return None
        
        user_response = memory_manager.supabase.auth.get_user()
        if user_response.user:
            print(f"[AUTH] Authenticated user: {user_response.user.id}")
            return user_response.user
        else:
            print("[AUTH] No authenticated user found")
            return None
    except Exception as e:
        print(f"[AUTH ERROR] Failed to get current user: {e}")
        return None

def ensure_profile_exists(user_id: str):
    """Ensure a profile exists in the profiles table for the given user_id."""
    try:
        if memory_manager.supabase is None:
            return False
        
        # Check if profile exists
        response = memory_manager.supabase.table('profiles').select('id').eq('id', user_id).execute()
        
        if not response.data:
            # Profile doesn't exist, but we can't create it without auth.users entry
            # For development/testing, we'll skip profile creation
            print(f"[PROFILE] Profile not found for user {user_id}, skipping creation")
            return False
        
        return True
    except Exception as e:
        print(f"[PROFILE ERROR] Failed to ensure profile exists: {e}")
        return False

def get_user_id():
    """Get the current user's ID or return a default for testing."""
    user = get_current_user()
    if user:
        return user.id
    else:
        # For development/testing, use a consistent UUID
        import uuid
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, "default_user"))

def save_user_profile(profile_text: str):
    """Helper function to save user profile."""
    try:
        result = user_profile.save_profile(profile_text)
        print(f"[PROFILE] {result}")
        return result
    except Exception as e:
        print(f"[PROFILE ERROR] {e}")
        return f"Error: {e}"

def get_user_profile():
    """Helper function to get user profile."""
    try:
        return user_profile.get_profile()
    except Exception as e:
        print(f"[PROFILE ERROR] {e}")
        return None

def save_memory(category: str, key: str, value: str):
    """Helper function to save memory."""
    try:
        result = memory_manager.store(category, key, value)
        print(f"[MEMORY] {result}")
        return result
    except Exception as e:
        print(f"[MEMORY ERROR] {e}")
        return f"Error: {e}"

# ---------------------------
# FAISS Vector Store (RAG)
# ---------------------------
embedding_dim = 1536
index = faiss.IndexFlatL2(embedding_dim)
vector_store = []  # (text, embedding)

def add_to_vectorstore(text: str, source: str):
    """Add text to the FAISS vector store."""
    try:
        # Generate embedding
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        embedding = np.array(response.data[0].embedding, dtype=np.float32)
        
        # Add to FAISS index
        index.add(embedding.reshape(1, -1))
        vector_store.append((text, source))
        
        print(f"[RAG] Added to vector store: {text[:50]}...")
    except Exception as e:
        print(f"[RAG ERROR] Failed to add to vector store: {e}")

def retrieve_from_vectorstore(query: str, k: int = 3):
    """Retrieve similar texts from the vector store."""
    try:
        if len(vector_store) == 0:
            return []
        
        # Generate query embedding
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=query
        )
        query_embedding = np.array(response.data[0].embedding, dtype=np.float32)
        
        # Search in FAISS
        distances, indices = index.search(query_embedding.reshape(1, -1), k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(vector_store):
                text, source = vector_store[idx]
                results.append({
                    'text': text,
                    'source': source,
                    'distance': distances[0][i]
                })
        
        return results
    except Exception as e:
        print(f"[RAG ERROR] Failed to retrieve from vector store: {e}")
        return []

# ---------------------------
# Core Agent Logic
# ---------------------------
def generate_with_memory(user_input: str, context: str = ""):
    """Generate response using memory and context."""
    try:
        # Get relevant memories
        memories = memory_manager.retrieve_all()
        memory_context = ""
        if memories:
            memory_context = "\n".join([f"- {k}: {v}" for k, v in memories.items()])
        
        # Get user profile
        profile = get_user_profile()
        profile_context = f"\nUser Profile: {profile}" if profile else ""
        
        # Get RAG context
        rag_results = retrieve_from_vectorstore(user_input)
        rag_context = ""
        if rag_results:
            rag_context = "\n".join([f"- {r['text']}" for r in rag_results])
        
        # Create system prompt
        system_prompt = f"""You are a helpful AI assistant. Use the following context to provide relevant responses:

{context}
{profile_context}

Memory Context:
{memory_context}

RAG Context:
{rag_context}

Instructions:
1. Be helpful and conversational
2. Use the context provided to give relevant responses
3. If you learn something new about the user, store it in memory
4. Respond in a natural, friendly way"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[GENERATION ERROR] {e}")
        return "I'm sorry, I encountered an error processing your request."

def check_importance(user_input: str):
    """Check if user input contains important information."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """Determine if the user input contains important information that should be stored in memory. 
                    Important information includes: personal facts, preferences, goals, plans, relationships, experiences, opinions.
                    Return only 'YES' or 'NO'."""
                },
                {"role": "user", "content": user_input}
            ]
        )
        
        return response.choices[0].message.content.strip().upper() == "YES"
    except Exception as e:
        print(f"[IMPORTANCE CHECK ERROR] {e}")
        return False

def check_contradiction(user_input: str, existing_memory: str):
    """Check if user input contradicts existing memory."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """Determine if the user input contradicts the existing memory. 
                    Return only 'YES' if there's a contradiction, 'NO' if there isn't."""
                },
                {"role": "user", "content": f"Existing memory: {existing_memory}\nUser input: {user_input}"}
            ]
        )
        
        return response.choices[0].message.content.strip().upper() == "YES"
    except Exception as e:
        print(f"[CONTRADICTION CHECK ERROR] {e}")
        return False

def extract_key_information(user_input: str):
    """Extract key information from user input."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """Extract key information from the user input. 
                    Return a JSON object with categories and key-value pairs.
                    Categories: FACT, PREFERENCE, GOAL, PLAN, RELATIONSHIP, EXPERIENCE, OPINION
                    Example: {"FACT": {"name": "John"}, "PREFERENCE": {"food": "pizza"}}"""
                },
                {"role": "user", "content": user_input}
            ]
        )
        
        import json
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        print(f"[EXTRACTION ERROR] {e}")
        return {}

# ---------------------------
# LiveKit Agent
# ---------------------------
class Assistant(Agent):
    def __init__(self):
        super().__init__(instructions="""
        You are a helpful AI assistant that speaks in Urdu.
        
        - Speak in casual Urdu, not formal language
        - Keep responses short and friendly
        - Be like a close friend
        - Ask follow-up questions to keep conversation going
        - Remember what the user has told you
        """)
        self.tts = TTS()

    async def on_user_turn_completed(self, turn_ctx: agents.ChatContext):
        """Handle user turn completion."""
        user_text = turn_ctx.user_message.content
        print(f"[USER INPUT] {user_text}")
        
        # Check if input is important
        if check_importance(user_text):
            # Extract key information
            key_info = extract_key_information(user_text)
            
            # Store in memory
            for category, items in key_info.items():
                for key, value in items.items():
                    # Check for contradictions
                    existing = memory_manager.retrieve(category, key)
                    if existing and check_contradiction(user_text, existing):
                        # Update existing memory
                        memory_manager.store(category, key, value)
                        print(f"[MEMORY] Updated {category}:{key} = {value}")
                    else:
                        # Store new memory
                        memory_manager.store(category, key, value)
                        print(f"[MEMORY] Stored {category}:{key} = {value}")
            
            # Add to RAG vector store
            add_to_vectorstore(user_text, "user_input")
            
            # Update user profile
            profile_text = f"User input: {user_text}"
            save_user_profile(profile_text)
        
        # Generate response
        response = generate_with_memory(user_text)
        
        # Send response
        await turn_ctx.send_message(response)
        
        # Convert to speech
        try:
            audio_data = self.tts.synthesize(response)
            await turn_ctx.send_audio(audio_data)
        except Exception as e:
            print(f"[TTS ERROR] {e}")

# ---------------------------
# Entry Point
# ---------------------------
async def entrypoint(ctx: agents.JobContext):
    """Main entry point for the agent."""
    session = await ctx.connect()
    
    # Initialize agent
    assistant = Assistant()
    
    # Start the agent with proper configuration
    await session.start(
        room=ctx.room,
        agent=assistant,
        room_input_options=RoomInputOptions(),
    )
    
    # Send initial greeting
    greeting = "ہیلو! میں آپ کی مدد کے لیے یہاں ہوں۔"
    await session.generate_reply(instructions=f"Say this in Urdu: {greeting}")

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
    ))
