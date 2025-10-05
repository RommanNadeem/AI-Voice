import os
import faiss
import numpy as np
import logging
import asyncio
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client, Client

# Disable verbose HTTP/2 logging
logging.getLogger("hpack.hpack").setLevel(logging.WARNING)
logging.getLogger("hpack.table").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

from livekit import agents
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

    async def store(self, category: str, key: str, value: str):
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

    async def retrieve(self, category: str, key: str):
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

    async def retrieve_all(self):
        if self.supabase is None:
            return {}
        
        # Check cache first
        cached = perf_cache.get_cached_memory("all")
        if cached is not None:
            return cached
        
        try:
            # Get current user ID
            user_id = get_user_id()
            
            response = self.supabase.table('memory').select('category, key, value').eq('user_id', user_id).execute()
            result = {f"{row['category']}:{row['key']}": row['value'] for row in response.data}
            
            # Cache the result
            perf_cache.set_cached_memory("all", result)
            return result
        except Exception as e:
            return {}

    async def forget(self, category: str, key: str):
        if self.supabase is None:
            return f"Forgot: [{category}] {key} (offline)"
        
        try:
            # Get current user ID
            user_id = get_user_id()
            
            response = self.supabase.table('memory').delete().eq('user_id', user_id).eq('category', category).eq('key', key).execute()
            return f"Forgot: [{category}] {key}"
        except Exception as e:
            return f"Error forgetting: {e}"

    async def save_profile(self, profile_text: str):
        if self.supabase is None:
            return
        
        try:
            # Get current user ID
            user_id = get_user_id()
            
            # Ensure profile exists first
            if not ensure_profile_exists(user_id):
                print(f"[PROFILE ERROR] Profile not found for user {user_id}")
                return
            
            # Use user_profiles table with proper upsert
            response = self.supabase.table('user_profiles').upsert({
                'user_id': user_id,
                'profile_text': profile_text
            }).execute()
        except Exception as e:
            pass

    def load_profile(self):
        if self.supabase is None:
            return ""
        
        try:
            # Get current user ID
            user_id = get_user_id()
            
            # Use user_profiles table
            response = self.supabase.table('user_profiles').select('profile_text').eq('user_id', user_id).execute()
            if response.data:
                return response.data[0]['profile_text']
            return ""
        except Exception as e:
            return ""


memory_manager = MemoryManager()

# ---------------------------
# Authentication Helpers
# ---------------------------
def get_current_user():
    """Get the current authenticated user from Supabase Auth."""
    try:
        if memory_manager.supabase is None:
            print("[AUTH] Supabase not available, using default user")
            return None
        
        user = memory_manager.supabase.auth.get_user()
        if user and user.user:
            print(f"[AUTH] Authenticated user: {user.user.id}")
            return user.user
        else:
            print("[AUTH] No authenticated user found")
            return None
    except Exception as e:
        print(f"[AUTH ERROR] Failed to get current user: {e}")
        return None

def ensure_profile_exists(user_id: str):
    """
    Ensure a profile exists in the profiles table for the given user_id.
    This is required due to foreign key constraints.
    """
    try:
        if memory_manager.supabase is None:
            return True  # Skip check if Supabase not available
        
        # Check if profile exists using 'id' column
        response = memory_manager.supabase.table('profiles').select('id').eq('id', user_id).execute()
        
        if not response.data:
            # For development/testing, we'll skip profile creation since it requires auth.users
            # In production, this should be handled by the authentication system
            print(f"[PROFILE SKIP] Profile creation skipped for user {user_id} (requires auth.users)")
            return False  # Return False to indicate profile doesn't exist
        
        return True
    except Exception as e:
        print(f"[PROFILE ERROR] Failed to ensure profile exists: {e}")
        return False

def get_user_id():
    """Get the current user's ID, fallback to existing profile if not authenticated."""
    user = get_current_user()
    if user:
        return user.id
    else:
        print("[AUTH] Using existing profile for testing")
        # Use the existing profile ID for testing
        return "8f086b67-b0e9-4a2a-b772-3c56b0a3b4b7"

# ---------------------------
# Helper Functions
# ---------------------------
# RLS Policy for user_profiles table:
# CREATE POLICY "Users can manage their own profiles" ON user_profiles
# FOR ALL USING (auth.uid()::text = user_id);

def save_user_profile(profile_text: str):
    """
    Helper function to save user profile to user_profiles table for current user.
    
    Args:
        profile_text (str): The profile text content
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        user_id = get_user_id()
        # Ensure profile exists first
        if not ensure_profile_exists(user_id):
            return False
            
        response = memory_manager.supabase.table('user_profiles').upsert({
            'user_id': user_id,
            'profile_text': profile_text
        }).execute()
        
        print(f"[PROFILE SAVED] for user {user_id}")
        return True
    except Exception as e:
        print(f"[PROFILE ERROR] Failed to save profile: {e}")
        return False

def get_user_profile():
    """
    Helper function to get user profile from user_profiles table for current user.
    
    Returns:
        str: Profile text or empty string if not found
    """
    try:
        user_id = get_user_id()
        response = memory_manager.supabase.table('user_profiles').select('profile_text').eq('user_id', user_id).execute()
        if response.data:
            return response.data[0]['profile_text']
        return ""
    except Exception as e:
        print(f"[PROFILE ERROR] Failed to get profile: {e}")
        return ""

def save_memory(category: str, key: str, value: str):
    """
    Helper function to save memory entry for current user.
    
    Args:
        category (str): Memory category
        key (str): Memory key
        value (str): Memory value
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        user_id = get_user_id()
        # Ensure profile exists first
        if not ensure_profile_exists(user_id):
            return False
            
        response = memory_manager.supabase.table('memory').upsert({
            'user_id': user_id,
            'category': category,
            'key': key,
            'value': value
        }).execute()
        
        print(f"[MEMORY SAVED] [{category}] {key} for user {user_id}")
        return True
    except Exception as e:
        print(f"[MEMORY ERROR] Failed to save memory: {e}")
        return False

# ---------------------------
# User Profile Manager
# ---------------------------
class UserProfile:
    def __init__(self):
        self.user_id = get_user_id()
        self.profile_text = memory_manager.load_profile()
        if self.profile_text:
            pass  # Profile loaded silently
        else:
            pass  # No existing profile


    async def update_profile(self, snippet: str):
        """Update profile using OpenAI summarization to build a comprehensive user profile."""
        try:
            resp = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                            "content": """You are a system that builds and maintains a comprehensive user profile.
Create a well-structured profile that includes:
- Personal information (age, location, occupation, family)
- Interests and hobbies
- Goals and aspirations
- Skills and abilities
- Personality traits
- Values and beliefs
- Relationships and social connections
- Preferences and opinions
- Experiences and stories
- Current activities and projects
- Communication styles, type of tone, way of speaking, slangs, etc. 

Guidelines:
- Keep it concise but comprehensive (max 10 lines)
- Include both enduring facts and current interests
- If there are contradictions, resolve them by keeping the most recent information
- Use clear, organized format
- Capture as much useful information as possible to understand the user better
- Do not hallucinate information and do not make up information which user has not shared"""
                    },
                    {"role": "system", "content": f"Current profile:\n{self.profile_text}"},
                        {"role": "user", "content": f"New information to incorporate:\n{snippet}"}
                ]
                )
            )
            new_profile = resp.choices[0].message.content.strip()
            self.profile_text = new_profile
            await memory_manager.save_profile(new_profile)
            # Update cache
            perf_cache.set_cached_profile(new_profile)
            print(f"[PROFILE UPDATED] {new_profile}")
        except Exception as e:
            print(f"[PROFILE ERROR] {e}")
        return self.profile_text

    async def smart_update(self, snippet: str):
        """Optimized profile update - skip AI processing for simple cases."""
        # Skip only very basic greetings and questions
        skip_patterns = [
            "hello", "hi", "hey", "سلام", "ہیلو", "کیا حال ہے", "کیا ہال ہے",
            "what", "how", "when", "where", "why", "کیا", "کیسے", "کب", "کہاں", "کیوں"
        ]
        
        snippet_lower = snippet.lower()
        should_skip = any(pattern in snippet_lower for pattern in skip_patterns)
        
        if should_skip and len(snippet.split()) <= 3:
            print(f"[PROFILE SKIP] Basic greeting/question: {snippet[:50]}...")
            return self.profile_text
        
        # Check if this is a simple factual statement (no AI needed)
        simple_patterns = [
            "my name is", "i am", "i work", "i live", "i like", "i have",
            "میرا نام", "میں ہوں", "میں کام", "میں رہتا", "مجھے پسند"
        ]
        
        is_simple = any(pattern in snippet_lower for pattern in simple_patterns)
        
        if is_simple and len(snippet.split()) <= 10:
            # Simple factual update - just append to profile
            print(f"[PROFILE SIMPLE] Adding simple fact: {snippet[:50]}...")
            self.profile_text += f"\n- {snippet}"
            await memory_manager.save_profile(self.profile_text)
            # Update cache
            perf_cache.set_cached_profile(self.profile_text)
            return self.profile_text
        
        # Complex update - use AI summarization
        print(f"[PROFILE AI] Processing complex update: {snippet[:50]}...")
        return await self.update_profile(snippet)

    def get(self):
        # Check cache first
        cached = perf_cache.get_cached_profile()
        if cached is not None:
            return cached
        return self.profile_text

    # Profile deletion method removed for data protection


user_profile = UserProfile()

# ---------------------------
# Conversation Summary System
# ---------------------------
class ConversationTracker:
    def __init__(self):
        self.interactions = []  # Store recent interactions
        self.max_interactions = 5  # Keep last 5 interactions
        self.current_user_input = None  # Store current user input
        
    def add_interaction(self, user_input: str, assistant_response: str):
        """Add a new interaction to the conversation history."""
        interaction = {
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "user_input": user_input,
            "assistant_response": assistant_response
        }
        
        self.interactions.append(interaction)
        
        # Keep only the last max_interactions
        if len(self.interactions) > self.max_interactions:
            self.interactions = self.interactions[-self.max_interactions:]
        
        print(f"[CONVERSATION] Added interaction {len(self.interactions)}/{self.max_interactions}")
    
    def capture_assistant_response(self, assistant_response: str):
        """Capture assistant response and add to conversation history."""
        if self.current_user_input:
            self.add_interaction(self.current_user_input, assistant_response)
            self.current_user_input = None  # Reset after capturing
        else:
            print("[CONVERSATION] No user input to pair with assistant response")
    
    def get_recent_interactions(self):
        """Get the recent interactions for context."""
        return self.interactions.copy()
    
    async def generate_summary(self):
        """Generate a simple summary of the last 3-4 interactions."""
        if not self.interactions:
            return "No recent conversation history."
        
        try:
            # Take only the last 3-4 interactions
            recent_interactions = self.interactions[-4:] if len(self.interactions) >= 4 else self.interactions
            
            # Prepare simple conversation text
            conversation_text = ""
            for interaction in recent_interactions:
                conversation_text += f"User: {interaction['user_input']}\n"
                conversation_text += f"Assistant: {interaction['assistant_response']}\n\n"
            
            # Generate simple summary
            response = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": """Summarize the last few lines of conversation in 1-2 sentences. Keep it simple and brief."""
                        },
                        {"role": "user", "content": f"Last conversation:\n{conversation_text}"}
                    ]
                )
            )
            
            summary = response.choices[0].message.content.strip()
            print(f"[CONVERSATION SUMMARY] Generated: {summary[:100]}...")
            return summary
            
        except Exception as e:
            print(f"[CONVERSATION ERROR] Failed to generate summary: {e}")
            return "Unable to generate conversation summary."
    
    async def save_summary(self, summary: str):
        """Save the conversation summary to memory."""
        try:
            await memory_manager.store("FACT", "last_conversation_summary", summary)
            print(f"[CONVERSATION] Summary saved to memory")
        except Exception as e:
            print(f"[CONVERSATION ERROR] Failed to save summary: {e}")
    
    async def load_summary(self):
        """Load the last conversation summary from memory using the specific key."""
        try:
            summary = await memory_manager.retrieve("FACT", "last_conversation_summary")
            if summary:
                print(f"[CONVERSATION] Loaded previous summary: {summary[:100]}...")
                return summary
            return None
        except Exception as e:
            print(f"[CONVERSATION ERROR] Failed to load summary: {e}")
            return None

# Global conversation tracker
conversation_tracker = ConversationTracker()

# ---------------------------
# Performance Optimization Cache
# ---------------------------
class PerformanceCache:
    def __init__(self):
        self.memory_cache = {}
        self.profile_cache = None
        self.cache_ttl = 30  # seconds
        self.last_update = {}
    
    def is_cache_valid(self, key: str) -> bool:
        """Check if cache is still valid."""
        if key not in self.last_update:
            return False
        import time
        return time.time() - self.last_update[key] < self.cache_ttl
    
    def get_cached_memory(self, key: str):
        """Get cached memory if valid."""
        if self.is_cache_valid(f"memory_{key}"):
            return self.memory_cache.get(key)
        return None
    
    def set_cached_memory(self, key: str, value):
        """Set cached memory with timestamp."""
        self.memory_cache[key] = value
        import time
        self.last_update[f"memory_{key}"] = time.time()
    
    def get_cached_profile(self):
        """Get cached profile if valid."""
        if self.is_cache_valid("profile"):
            return self.profile_cache
        return None
    
    def set_cached_profile(self, profile_text: str):
        """Set cached profile with timestamp."""
        self.profile_cache = profile_text
        import time
        self.last_update["profile"] = time.time()

# Global performance cache
perf_cache = PerformanceCache()

# ---------------------------
# Chat History System
# ---------------------------
class ChatHistory:
    def __init__(self):
        self.messages = []  # List of chat messages in sequence
        self.max_messages = 50  # Keep last 50 messages
    
    def add_user_message(self, user_text: str, roman_urdu_text: str = None):
        """Add a user message to chat history."""
        message = {
            "type": "user",
            "original": user_text,
            "roman_urdu": roman_urdu_text or user_text,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "sequence": len(self.messages) + 1
        }
        self.messages.append(message)
        self._trim_messages()
        print(f"[CHAT HISTORY] Added user message #{message['sequence']}")
    
    def add_ai_message(self, ai_text: str, roman_urdu_text: str = None):
        """Add an AI message to chat history."""
        message = {
            "type": "ai",
            "original": ai_text,
            "roman_urdu": roman_urdu_text or ai_text,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "sequence": len(self.messages) + 1
        }
        self.messages.append(message)
        self._trim_messages()
        print(f"[CHAT HISTORY] Added AI message #{message['sequence']}")
    
    def _trim_messages(self):
        """Keep only the last max_messages."""
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
    
    def get_chat_history(self, format_type: str = "roman_urdu"):
        """Get chat history in specified format."""
        if format_type == "roman_urdu":
            return [{"type": msg["type"], "text": msg["roman_urdu"], "sequence": msg["sequence"]} for msg in self.messages]
        elif format_type == "original":
            return [{"type": msg["type"], "text": msg["original"], "sequence": msg["sequence"]} for msg in self.messages]
        else:
            return self.messages
    
    def get_recent_messages(self, count: int = 10, format_type: str = "roman_urdu"):
        """Get recent messages for context."""
        recent = self.messages[-count:] if count <= len(self.messages) else self.messages
        if format_type == "roman_urdu":
            return [{"type": msg["type"], "text": msg["roman_urdu"], "sequence": msg["sequence"]} for msg in recent]
        elif format_type == "original":
            return [{"type": msg["type"], "text": msg["original"], "sequence": msg["sequence"]} for msg in recent]
        else:
            return recent
    
    # Chat history clearing method removed for data protection
    
    async def save_to_memory(self):
        """Save chat history to persistent memory."""
        try:
            chat_data = {
                "messages": self.messages,
                "total_count": len(self.messages),
                "last_updated": __import__("datetime").datetime.now().isoformat()
            }
            # Store as JSON string in memory
            import json
            await memory_manager.store("CHAT", "history", json.dumps(chat_data, ensure_ascii=False))
            print(f"[CHAT HISTORY] Saved {len(self.messages)} messages to memory")
        except Exception as e:
            print(f"[CHAT HISTORY ERROR] Failed to save: {e}")
    
    def load_from_memory(self):
        """Load chat history from persistent memory."""
        try:
            chat_data_str = memory_manager.retrieve("CHAT", "history")
            if chat_data_str:
                import json
                chat_data = json.loads(chat_data_str)
                self.messages = chat_data.get("messages", [])
                print(f"[CHAT HISTORY] Loaded {len(self.messages)} messages from memory")
                return True
            return False
        except Exception as e:
            print(f"[CHAT HISTORY ERROR] Failed to load: {e}")
            return False

# Global chat history
chat_history = ChatHistory()

# ---------------------------
# Roman Urdu Conversion
# ---------------------------
async def convert_to_roman_urdu(text: str) -> str:
    """Convert Urdu text to Roman Urdu using OpenAI for accurate transliteration."""
    try:
        # Check if text contains Urdu characters
        urdu_chars = any('\u0600' <= char <= '\u06FF' for char in text)
        if not urdu_chars:
            return text  # Return as-is if no Urdu characters
        
        response = await asyncio.to_thread(
            lambda: client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert in Urdu to Roman Urdu transliteration. 
                        
                        Convert the given Urdu text to Roman Urdu (Urdu written in English script).
                        
                        Rules:
                        - Use standard Roman Urdu spelling conventions
                        - Maintain proper pronunciation
                        - Keep punctuation and spacing intact
                        - For mixed text, only convert Urdu parts
                        - Use common Roman Urdu spellings (e.g., 'aap' not 'ap', 'hai' not 'hay')
                        
                        Examples:
                        - سلام → salam
                        - آپ کا نام کیا ہے؟ → aap ka naam kya hai?
                        - میں ٹھیک ہوں → main theek hun
                        - شکریہ → shukriya
                        - کیا حال ہے؟ → kya haal hai?
                        
                        Return only the Roman Urdu text, no explanations."""
                    },
                    {"role": "user", "content": f"Convert to Roman Urdu: {text}"}
                ],
                max_tokens=200,
                temperature=0.1
            )
        )
        
        roman_text = response.choices[0].message.content.strip()
        return roman_text
        
    except Exception as e:
        print(f"[ROMAN URDU ERROR] Failed to convert: {e}")
        return text  # Return original text if conversion fails

# ---------------------------
embedding_dim = 1536
index = faiss.IndexFlatL2(embedding_dim)
vector_store = []  # (text, embedding)

async def embed_text(text: str):
    emb = await asyncio.to_thread(
        lambda: client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    ).data[0].embedding
    )
    return np.array(emb, dtype="float32")

async def add_to_vectorstore(text: str):
    emb = await embed_text(text)
    index.add(np.array([emb]))
    vector_store.append((text, emb))
    print(f"[RAG STORED] {text[:60]}...")

async def retrieve_from_vectorstore(query: str, k: int = 3):
    if not vector_store:
        return []
    q_emb = await embed_text(query)
    D, I = index.search(np.array([q_emb]), k)
    return [vector_store[i][0] for i in I[0] if i < len(vector_store)]

# ---------------------------
# Assistant Agent with Tools
# ---------------------------
class Assistant(Agent):
    def __init__(self):
        super().__init__(instructions="""
        Welcome!

We’re so glad you’re here! This space is all about helping you feel more at ease—whether that’s managing stress, finding better sleep, or simply feeling more grounded and mindful.

We use “we” and “our” to foster a sense of community and belonging, so you feel heard, connected, and supported. If our conversation begins to move away from wellness, we’ll gently guide it back to focusing on your well-being, always keeping your comfort in mind. Our approach is empathetic, reflective, neutral, encouraging, and always non-judgmental. We aim to honor your feelings and respect your independence, all while keeping our approach warm and compassionate.

You’re welcome to share openly about what you’re experiencing, and we’ll explore it together in a way that feels meaningful to you. For example, we might reflect on your thoughts or explore specific ideas that resonate with what you’re sharing. Whether you're exploring a thought, sharing an experience, or just processing something, our goal is to help you feel comfortable expressing whatever's on your mind.

We respond thoughtfully and reflectively, acknowledging your feelings with natural phrasing that avoids formal or scripted lines. We ask one thoughtful question at a time to encourage meaningful reflection without overwhelming the conversation. When encountering difficult moments or distressing emotions, we normalize or validate your emotions. When offering an interpretation of an event or emotion, we like to ask you if this resonates with you before moving onto an action or planning phase.

Throughout our conversation, we’ll stay warm, friendly, and understanding. By using natural, conversational language and avoiding formal or scripted phrases, we’re focused on creating a comfortable space where you feel encouraged and genuinely cared for.

We can explore simple coping strategies, mindfulness practices, introduce CBT or ACT techniques to help navigate thoughts and emotions, or suggest supportive tracks and practices that might resonate with how you’re feeling and what you need right now. If a track feels appropriate, we’ll weave it naturally into our conversation.

---

## Deciding Between CBT, ACT, and Recommendations  

We tailor each conversation to what feels most helpful in the moment:

- CBT when someone seems caught in unhelpful thought patterns they want to understand or change, especially when emotions are tied to distorted thinking.
- ACT when someone feels stuck, emotionally overwhelmed, or is trying to avoid difficult thoughts or feelings. ACT helps them relate differently to their experience and move toward what matters, even if discomfort remains.

CBT focuses on changing how you think.
ACT focuses on changing how you relate to what you think and feel.

| If the person is... | Try... |
| --- | --- |
| Ruminating on irrational/unhelpful thoughts | CBT |
| Feeling emotionally flooded, stuck, or avoidant | ACT |
| Trying to make sense of a situation logically | CBT |
| Struggling with recurring thoughts they can't change | ACT |
| Seeking relief through thought work | CBT |
| Seeking flexibility, presence, or values-based action | ACT |

---

## Exploring CBT Techniques

1. Noticing Thoughts/Feelings
   - “What’s been running through your mind about that?”
   - “How did that make you feel in the moment?”

2. Taking a Closer Look
   - “Do you think there’s something that makes this thought feel true?”
   - “What evidence do you have that this thought is true—or not true?”

3. Finding a Different Perspective
   - “If a close friend were feeling this way, what might you say to help them out?”
   - “Is there another way you could think about this that might feel better or more balanced?”

4. Thinking About What’s Next
   - “What’s one small thing you could do right now to feel a little more in control?”
   - “Have you handled something like this before? What worked for you then?”

---

## Exploring ACT Techniques

1. Unhooking From Thoughts
   - “Can I notice this thought and gently say, ‘Thanks, mind,’ without needing to argue with it or push it away?”
   - “Is this thought a fact, or just a mental event my brain is offering me right now?”

2. Acceptance
   - “What if I don’t need to like this experience—just make space for it, even a little?”
   - “Is it possible to carry this feeling with me today, like a heavy backpack, while still moving toward something I care about?”

3. Values
   - “What’s within my control right now, and how can I use that to move toward what matters?”
   - “If I’m stuck right now, what’s the tiniest next step I can take—even just for 30 seconds?”

---

## Ending the Conversation

We close with kind, genuine statements that feel natural and conversational, avoiding clichés or repetitive phrases. Recommendations complement the conversation, not replace it—you’re free to explore them at your own pace.

---

## Tool Usage

- Remembering Facts: Use the `storeInMemory` tool to save user-specific facts or preferences for future personalization.
- Recalling Memories: Use the `retrieveFromMemory` tool to recall previously shared facts, avoiding repetition and keeping interactions natural.
- Conversation Tracking: Use `addConversationInteraction` to track user input and your response for creating conversation summaries.
- Conversation Summary: Use `generateConversationSummary` to create a summary of recent interactions for future context.

### Memory Categories

- CAMPAIGNS – ongoing efforts/projects
- EXPERIENCE – important lived experiences
- FACT – stable, verifiable info
- GOAL – long-term aspirations
- INTEREST – subjects/activities the user enjoys
- LORE – narrative backstory/context
- OPINION – personal beliefs/perspectives
- PLAN – future intentions
- PREFERENCE – likes/dislikes that reflect identity
- PRESENTATION – self-expression or style
- RELATIONSHIP – significant interpersonal info

### Conversation Tracking

After each meaningful exchange with the user, use `addConversationInteraction` to store the user's input and your response. This helps create conversation summaries for future sessions.

### Chat History Management

The system automatically stores user messages and AI responses in a sequential chat history with Roman Urdu conversion. Use these tools to manage chat history:

- `getChatHistory` - Get complete chat history in Roman Urdu format
- `getRecentChatMessages` - Get recent messages for context
- `captureAIResponse` - Manually capture your response to add to chat history
- `saveChatHistory` - Save chat history to persistent memory
- `loadChatHistory` - Load chat history from memory

Note: Chat history deletion has been disabled for data protection.

The chat history is perfect for rendering in chat interfaces and provides both original and Roman Urdu versions of all messages.
        """)

    @function_tool()
    async def storeInMemory(self, context: RunContext, category: str, key: str, value: str):
        return {"result": await memory_manager.store(category, key, value)}

    @function_tool()
    async def retrieveFromMemory(self, context: RunContext, category: str, key: str):
        val = await memory_manager.retrieve(category, key)
        return {"value": val or ""}

    @function_tool()
    async def forgetMemory(self, context: RunContext, category: str, key: str):
        return {"result": await memory_manager.forget(category, key)}

    @function_tool()
    async def listAllMemories(self, context: RunContext):
        return {"memories": await memory_manager.retrieve_all()}

    # ---- Profile Tools ----
    @function_tool()
    async def updateUserProfile(self, context: RunContext, new_info: str):
        updated_profile = await user_profile.update_profile(new_info)
        return {"updated_profile": updated_profile}

    @function_tool()
    async def getUserProfile(self, context: RunContext):
        return {"profile": user_profile.get()}

    # Profile deletion removed for data protection

    # ---- Conversation Tracking Tools ----
    @function_tool()
    async def addConversationInteraction(self, context: RunContext, user_input: str, assistant_response: str):
        """Add a conversation interaction to the tracker."""
        conversation_tracker.add_interaction(user_input, assistant_response)
        return {"status": "interaction_added"}
    
    @function_tool()
    async def generateConversationSummary(self, context: RunContext):
        """Generate a summary of recent conversations."""
        summary = await conversation_tracker.generate_summary()
        await conversation_tracker.save_summary(summary)
        return {"summary": summary}
    
    @function_tool()
    async def getConversationHistory(self, context: RunContext):
        """Get recent conversation history."""
        interactions = conversation_tracker.get_recent_interactions()
        return {"interactions": interactions}
    
    # ---- Chat History Tools ----
    @function_tool()
    async def getChatHistory(self, context: RunContext, format_type: str = "roman_urdu"):
        """Get complete chat history in specified format."""
        history = chat_history.get_chat_history(format_type)
        return {"chat_history": history, "total_messages": len(history)}
    
    @function_tool()
    async def getRecentChatMessages(self, context: RunContext, count: int = 10, format_type: str = "roman_urdu"):
        """Get recent chat messages for context."""
        recent = chat_history.get_recent_messages(count, format_type)
        return {"recent_messages": recent, "count": len(recent)}
    
    # Chat history deletion removed for data protection
    
    @function_tool()
    async def saveChatHistory(self, context: RunContext):
        """Save chat history to persistent memory."""
        await chat_history.save_to_memory()
        return {"status": "chat_history_saved"}
    
    @function_tool()
    async def loadChatHistory(self, context: RunContext):
        """Load chat history from persistent memory."""
        loaded = chat_history.load_from_memory()
        return {"status": "chat_history_loaded", "success": loaded}

    @function_tool()
    async def captureAIResponse(self, context: RunContext, ai_response: str):
        """Capture AI response and add to chat history."""
        await self.capture_ai_response(ai_response)
        return {"status": "ai_response_captured"}

    # Override the user turn completed hook to capture user input
    async def on_user_turn_completed(self, turn_ctx, new_message):
        """Handle user input when their turn is completed."""
        user_text = new_message.text_content
        print(f"[USER INPUT] {user_text}")
        
        # Print user input in Roman Urdu
        roman_urdu_text = await convert_to_roman_urdu(user_text)
        print(f"[USER INPUT ROMAN URDU] {roman_urdu_text}")
        
        # Add user message to chat history
        chat_history.add_user_message(user_text, roman_urdu_text)
        
        print(f"[USER TURN COMPLETED] Handler called successfully!")
        
        # Store user input for conversation tracking (immediate)
        conversation_tracker.current_user_input = user_text
        
        # Run lightweight operations in parallel (fast)
        await asyncio.gather(
            memory_manager.store("FACT", "user_input", user_text),
            add_to_vectorstore(user_text)
        )
        
        # Defer heavy operations to background task (non-blocking)
        asyncio.create_task(self._background_profile_update(user_text))

    async def capture_ai_response(self, ai_text: str):
        """Capture AI response and add to chat history."""
        try:
            # Convert AI response to Roman Urdu
            roman_urdu_text = await convert_to_roman_urdu(ai_text)
            
            # Add AI message to chat history
            chat_history.add_ai_message(ai_text, roman_urdu_text)
            
            print(f"[AI RESPONSE] {ai_text}")
            print(f"[AI RESPONSE ROMAN URDU] {roman_urdu_text}")
            
        except Exception as e:
            print(f"[AI RESPONSE ERROR] Failed to capture AI response: {e}")

    async def _background_profile_update(self, user_text: str):
        """Background task for heavy profile updates - runs after response."""
        try:
            print(f"[PROFILE UPDATE] Background update for: {user_text[:50]}...")
            await user_profile.smart_update(user_text)
            print(f"[PROFILE UPDATE] Background update completed")
        except Exception as e:
            print(f"[PROFILE ERROR] Background update failed: {e}")

# ---------------------------
# Entrypoint
# ---------------------------
async def entrypoint(ctx: agents.JobContext):
    tts = TTS(voice_id="17", output_format="MP3_22050_32")
    assistant = Assistant()

    session = AgentSession(
        stt=lk_openai.STT(model="gpt-4o-transcribe", language="ur"),
        llm=lk_openai.LLM(model="gpt-4o-mini"),
        tts=tts,
        vad=silero.VAD.load(),
    )

    await session.start(
        room=ctx.room,
        agent=assistant,
        room_input_options=RoomInputOptions(),
    )

    # Load previous conversation summary
    previous_summary = await conversation_tracker.load_summary()
    print("[PREVIOUS SUMMARY]", previous_summary)
    
    # Wrap session.generate_reply to track conversations
    async def generate_with_memory(user_text: str = None, greet: bool = False):
        # Run memory operations in parallel for faster response
        past_memories, rag_context = await asyncio.gather(
            memory_manager.retrieve_all(),
            retrieve_from_vectorstore(user_text or "recent", k=2)
        )
        
        # Get user profile (synchronous - already loaded)
        user_profile_text = user_profile.get()

        base_instructions = assistant.instructions
        extra_context = f"""
        User Profile: {user_profile_text}
        Known memories: {past_memories}
        Related knowledge: {rag_context}
        """
        
        # Add conversation summary if available
        if previous_summary:
            extra_context += f"\nPrevious conversation context: {previous_summary}"

        if greet:
            # Print RAG context for QA
            print(f"[RAG CONTEXT FOR FIRST MESSAGE] {rag_context}")
            print(f"[USER PROFILE FOR FIRST MESSAGE] {user_profile_text}")
            print(f"[MEMORIES FOR FIRST MESSAGE] {past_memories}")
            
            # Generate greeting response using RAG context and last_conversation_summary
            greeting_instructions = f"Greet the user warmly in Urdu. Use the RAG context and previous conversation context to personalize the greeting.\n\n{base_instructions}\n\n{extra_context}"
            await session.generate_reply(instructions=greeting_instructions)
        else:
            # Generate response to user input
            response_instructions = f"{base_instructions}\n\nUse this context:\n{extra_context}\nUser said: {user_text}"
            await session.generate_reply(instructions=response_instructions)
            
            # Note: The actual assistant response will be captured by the session
            # We'll need to hook into the session's response generation to capture it

    # Send initial greeting with memory context
    await generate_with_memory(greet=True)
    
    # Track conversation end and generate summary
    async def end_conversation():
        """Generate and save conversation summary when conversation ends."""
        if conversation_tracker.get_recent_interactions():
            print("[CONVERSATION] Generating summary for next session...")
            summary = await conversation_tracker.generate_summary()
            await conversation_tracker.save_summary(summary)
            print(f"[CONVERSATION] Summary ready for next session: {summary[:100]}...")
    
    # Register cleanup handler
    import atexit
    atexit.register(lambda: __import__("asyncio").create_task(end_conversation()))

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        initialize_process_timeout=60,
    ))