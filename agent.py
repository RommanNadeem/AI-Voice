import os
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
            # Use upsert to insert or update
            response = self.supabase.table('memory').upsert({
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
            response = self.supabase.table('memory').select('value').eq('category', category).eq('key', key).execute()
            if response.data:
                return response.data[0]['value']
            return None
        except Exception as e:
            return None

    def retrieve_all(self):
        if self.supabase is None:
            return {}
        
        try:
            response = self.supabase.table('memory').select('category, key, value').execute()
            return {f"{row['category']}:{row['key']}": row['value'] for row in response.data}
        except Exception as e:
            return {}

    def forget(self, category: str, key: str):
        if self.supabase is None:
            return f"Forgot: [{category}] {key} (offline)"
        
        try:
            response = self.supabase.table('memory').delete().eq('category', category).eq('key', key).execute()
            return f"Forgot: [{category}] {key}"
        except Exception as e:
            return f"Error forgetting: {e}"

    def save_profile(self, user_id: str, profile_text: str):
        if self.supabase is None:
            return
        
        try:
            # Use user_profiles table with proper upsert
            response = self.supabase.table('user_profiles').upsert({
                'user_id': user_id,
                'profile_text': profile_text
            }).execute()
        except Exception as e:
            pass

    def load_profile(self, user_id: str):
        if self.supabase is None:
            return ""
        
        try:
            # Use user_profiles table
            response = self.supabase.table('user_profiles').select('profile_text').eq('user_id', user_id).execute()
            if response.data:
                return response.data[0]['profile_text']
            return ""
        except Exception as e:
            return ""


memory_manager = MemoryManager()

# ---------------------------
# Helper Functions
# ---------------------------
# RLS Policy for user_profiles table:
# CREATE POLICY "Users can manage their own profiles" ON user_profiles
# FOR ALL USING (auth.uid()::text = user_id);

def save_user_profile(user_id: str, profile_text: str):
    """
    Helper function to save user profile to user_profiles table.
    
    Args:
        user_id (str): The user's ID (should match auth.users.id)
        profile_text (str): The profile text content
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        response = memory_manager.supabase.table('user_profiles').upsert({
            'user_id': user_id,
            'profile_text': profile_text
        }).execute()
        
        return True
    except Exception as e:
        return False

def get_user_profile(user_id: str):
    """
    Helper function to get user profile from user_profiles table.
    
    Args:
        user_id (str): The user's ID
    
    Returns:
        str: Profile text or empty string if not found
    """
    try:
        response = memory_manager.supabase.table('user_profiles').select('profile_text').eq('user_id', user_id).execute()
        if response.data:
            return response.data[0]['profile_text']
        return ""
    except Exception as e:
        return ""

# ---------------------------
# User Profile Manager
# ---------------------------
class UserProfile:
    def __init__(self, user_id="default_user"):
        self.user_id = user_id
        self.profile_text = memory_manager.load_profile(user_id)
        if self.profile_text:
            pass  # Profile loaded silently
        else:
            pass  # No existing profile


    def update_profile(self, snippet: str):
        """Update profile using OpenAI summarization to build a comprehensive user profile."""
        try:
            resp = client.chat.completions.create(
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
            new_profile = resp.choices[0].message.content.strip()
            self.profile_text = new_profile
            memory_manager.save_profile(self.user_id, new_profile)
            print(f"[PROFILE UPDATED] {new_profile}")
        except Exception as e:
            print(f"[PROFILE ERROR] {e}")
        return self.profile_text

    def smart_update(self, snippet: str):
        """Simple profile update - store most user input directly."""
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
        
        # Update profile with AI summarization for most input
        print(f"[PROFILE UPDATE] Processing: {snippet[:50]}...")
        return self.update_profile(snippet)

    def get(self):
        return self.profile_text

    def forget(self):
        if memory_manager.supabase is None:
            print(f"[PROFILE FORGOT] for {self.user_id} (Supabase not available)")
            self.profile_text = ""
            return f"Profile deleted for {self.user_id} (offline mode)"
        
        try:
            # Use user_profiles table
            response = memory_manager.supabase.table('user_profiles').delete().eq('user_id', self.user_id).execute()
            self.profile_text = ""
            print(f"[PROFILE FORGOT] for {self.user_id}")
            return f"Profile deleted for {self.user_id}"
        except Exception as e:
            print(f"[SUPABASE ERROR] Forget profile failed: {e}")
            return f"Error deleting profile: {e}"


user_profile = UserProfile(user_id="romman")

# ---------------------------
# FAISS Vector Store (RAG)
# ---------------------------
embedding_dim = 1536
index = faiss.IndexFlatL2(embedding_dim)
vector_store = []  # (text, embedding)

def embed_text(text: str):
    emb = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    ).data[0].embedding
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

## Using Track Recommendations

We may suggest supportive tracks (such as guided meditations or calming stories) if they feel relevant. These are offered naturally in the flow of conversation—never as a list—and always woven in a way that centers your needs.

Examples:
- “There’s a track called **Track Title** that’s great for calming anxious thoughts—it might feel helpful right now.”
- “You might enjoy **Track Title** for relaxation. Another one that could help is **Another Track**—it’s designed to create a sense of calm and focus.”

We won’t ask if you’d like a recommendation; instead, we’ll offer one directly if it feels appropriate.

---

## Ending the Conversation

We close with kind, genuine statements that feel natural and conversational, avoiding clichés or repetitive phrases. Recommendations complement the conversation, not replace it—you’re free to explore them at your own pace.

---

## Tool Usage

- Remembering Facts: Use the `storeInMemory` tool to save user-specific facts or preferences for future personalization.
- Recalling Memories: Use the `retrieveFromMemory` tool to recall previously shared facts, avoiding repetition and keeping interactions natural.

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
        updated_profile = user_profile.update_profile(new_info)
        return {"updated_profile": updated_profile}

    @function_tool()
    async def getUserProfile(self, context: RunContext):
        return {"profile": user_profile.get()}

    @function_tool()
    async def forgetUserProfile(self, context: RunContext):
        return {"result": user_profile.forget()}

    # Override the user turn completed hook to capture user input
    async def on_user_turn_completed(self, turn_ctx, new_message):
        """Handle user input when their turn is completed."""
        user_text = new_message.text_content
        print(f"[USER INPUT] {user_text}")
        print(f"[USER TURN COMPLETED] Handler called successfully!")
        
        # Store user input in memory
        memory_manager.store("FACT", "user_input", user_text)
        add_to_vectorstore(user_text)
        
        # Update user profile
        print(f"[PROFILE UPDATE] Starting profile update for: {user_text[:50]}...")
        user_profile.smart_update(user_text)

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

    # Wrap session.generate_reply so every reply includes memory + rag + profile
    async def generate_with_memory(user_text: str = None, greet: bool = False):
        past_memories = memory_manager.retrieve_all()
        rag_context = retrieve_from_vectorstore(user_text or "recent", k=2)
        user_profile_text = user_profile.get()

        base_instructions = assistant.instructions
        extra_context = f"""
        User Profile: {user_profile_text}
        Known memories: {past_memories}
        Related knowledge: {rag_context}
        """

        if greet:
            await session.generate_reply(
                instructions=f"Greet the user warmly in Urdu.\n\n{base_instructions}\n\n{extra_context}"
            )
        else:
            await session.generate_reply(
                instructions=f"{base_instructions}\n\nUse this context:\n{extra_context}\nUser said: {user_text}"
            )

    # Send initial greeting with memory context
    await generate_with_memory(greet=True)

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        initialize_process_timeout=60,
    ))
