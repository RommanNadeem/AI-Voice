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
            print(f"[SUPABASE WARNING] Using placeholder credentials. Please set SUPABASE_URL and SUPABASE_ANON_KEY in .env file")
            self.supabase = None
            self.connection_error = "Supabase credentials not configured"
        else:
            try:
                self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
                print(f"[SUPABASE CONNECTED] Successfully connected to Supabase")
                self.connection_error = None
            except Exception as e:
                print(f"[SUPABASE ERROR] Connection failed: {e}")
                self.supabase = None
                self.connection_error = str(e)

    def store(self, category: str, key: str, value: str):
        category = category.upper()
        if category not in self.ALLOWED_CATEGORIES:
            category = "FACT"
        
        if self.supabase is None:
            print(f"[MEMORY STORED] [{category}] {key} = {value} (Supabase not available)")
            return f"Stored: [{category}] {key} = {value} (offline mode)"
        
        try:
            # Get current user ID
            user_id = get_user_id()
            
            # Use upsert to insert or update
            response = self.supabase.table('memory').upsert({
                'user_id': user_id,
                'category': category,
                'key': key,
                'value': value
            }).execute()
            
            print(f"[MEMORY STORED] [{category}] {key} = {value}")
            return f"Stored: [{category}] {key} = {value}"
        except Exception as e:
            print(f"[SUPABASE ERROR] Store failed: {e}")
            return f"Error storing: {e}"

    def retrieve(self, category: str, key: str):
        if self.supabase is None:
            print(f"[MEMORY RETRIEVE] [{category}] {key} (Supabase not available)")
            return None
        
        try:
            # Get current user ID
            user_id = get_user_id()
            
            response = self.supabase.table('memory').select('value').eq('user_id', user_id).eq('category', category).eq('key', key).execute()
            if response.data:
                return response.data[0]['value']
            return None
        except Exception as e:
            print(f"[SUPABASE ERROR] Retrieve failed: {e}")
            return None

    def retrieve_all(self):
        if self.supabase is None:
            print(f"[MEMORY RETRIEVE ALL] (Supabase not available)")
            return {}
        
        try:
            # Get current user ID
            user_id = get_user_id()
            
            response = self.supabase.table('memory').select('category, key, value').eq('user_id', user_id).execute()
            return {f"{row['category']}:{row['key']}": row['value'] for row in response.data}
        except Exception as e:
            print(f"[SUPABASE ERROR] Retrieve all failed: {e}")
            return {}

    def save_profile(self, profile_text: str):
        if self.supabase is None:
            print(f"[PROFILE STORED] (Supabase not available)")
            return
        
        try:
            # Get current user ID
            user_id = get_user_id()
            
            # Use user_profiles table with proper upsert
            response = self.supabase.table('user_profiles').upsert({
                'user_id': user_id,
                'profile_text': profile_text
            }).execute()
            
            print(f"[PROFILE STORED] for {user_id}")
        except Exception as e:
            print(f"[SUPABASE ERROR] Save profile failed: {e}")

    def load_profile(self):
        if self.supabase is None:
            print(f"[PROFILE LOAD] (Supabase not available)")
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
            print(f"[SUPABASE ERROR] Load profile failed: {e}")
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

def get_user_id():
    """Get the current user's ID, fallback to default if not authenticated."""
    user = get_current_user()
    if user:
        return user.id
    else:
        print("[AUTH] Using default user ID")
        return "default_user"

# ---------------------------
# User Profile Manager
# ---------------------------
class UserProfile:
    def __init__(self):
        self.user_id = get_user_id()
        self.profile_text = memory_manager.load_profile()
        if self.profile_text:
            print(f"[PROFILE LOADED] for {self.user_id}: {self.profile_text}")
        else:
            print(f"[PROFILE EMPTY] No existing profile for {self.user_id}")

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
            memory_manager.save_profile(new_profile)
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


user_profile = UserProfile()

# ---------------------------
# Onboarding Content
# ---------------------------
WELCOME_STORY = """
آپ کا خیر مقدم! میں آپ کو ایک چھوٹی سی کہانی سناتا ہوں۔

ایک بار ایک گاؤں میں دو دوست رہتے تھے - علی اور حسن۔ وہ بچپن سے ساتھ کھیلتے، پڑھتے اور بڑے ہوتے رہے۔ علی کو گاڑیاں چلانے کا شوق تھا، جبکہ حسن کو کمپیوٹر میں دلچسپی تھی۔

سالوں بعد، علی ایک اچھا ڈرائیور بن گیا اور حسن نے سافٹ ویئر انجینئرنگ سیکھی۔ دونوں نے اپنے خوابوں کو حقیقت بنایا۔

یہ کہانی اس لیے سنائی کہ میں چاہتا ہوں کہ ہم بھی دوست بنیں۔ آپ کے خواب، خواہشات اور دلچسپیاں جاننا چاہتا ہوں تاکہ میں آپ کی بہتر مدد کر سکوں۔
"""

ONBOARDING_QUESTIONS = [
    "آپ کا نام کیا ہے؟",
    "آپ کیا کام کرتے ہیں یا کیا پڑھتے ہیں؟",
    "آپ کو کیا کرنے کا شوق ہے؟ کوئی خاص ہابی یا دلچسپی؟"
]

# JSON extraction template
JSON_TEMPLATE = {
    "name": "",
    "occupation": "",
    "interests": ""
}

def extract_user_info_to_json(user_responses: str):
    """Extract name, occupation, and interests from user responses and return JSON."""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """Extract the following information from the user's responses and return ONLY a JSON object:
                    - name: User's name
                    - occupation: What they do for work/study
                    - interests: Their hobbies/interests
                    
                    Return ONLY valid JSON, no other text. If information is not provided, use empty string "".
                    Example: {"name": "احمد", "occupation": "سافٹ ویئر انجینئر", "interests": "گاڑی چلانا"}"""
                },
                {"role": "user", "content": user_responses}
            ]
        )
        json_str = resp.choices[0].message.content.strip()
        # Try to parse and return as dict
        import json
        return json.loads(json_str)
    except Exception as e:
        print(f"[JSON EXTRACTION ERROR] {e}")
        return JSON_TEMPLATE

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
# Onboarding Agent
# ---------------------------
class OnboardingAgent(Agent):
    def __init__(self):
        super().__init__(instructions=f"""
        ## Role
        You are a warm, friendly onboarding assistant who helps new users get started. 
        Your main goal is to create a welcoming experience and gather essential information about the user.

        ## Communication Style
        - Speak in Urdu Language, no English words
        - Speak in casual Urdu words, not difficult literature Urdu
        - Give short responses (2-3 sentences max)
        - Be warm, welcoming, and encouraging
        - Use a storytelling approach to make the experience engaging

        ## Welcome Story
        When greeting a new user, tell this story:
        {WELCOME_STORY}

        ## Onboarding Questions
        After the story, ask these questions naturally in conversation:
        {chr(10).join([f"- {q}" for q in ONBOARDING_QUESTIONS])}

        ## Guidelines
        - Keep questions natural and conversational
        - Don't overwhelm with too many questions at once
        - Show genuine interest in their responses
        - Use the user's answers to ask follow-up questions
        - Make the user feel comfortable and valued
        - Ask one question at a time, wait for response, then ask the next
        
        ## Focus and Restriction
        - STAY FOCUSED on the core onboarding questions only
        - If user tries to go off-topic, gently nudge them back: "یہ بہت اچھا ہے، لیکن پہلے میں آپ سے کچھ بنیادی باتیں جاننا چاہتا ہوں"
        - If user shows disinterest or wants to leave, politely let them go: "ٹھیک ہے، اگر آپ چاہیں تو بعد میں بات کر سکتے ہیں"
        - Do NOT engage in topics outside of name, occupation, and interests
        - Complete all 3 core questions before allowing other topics

        ## Handover Process
        - Once you have collected the user's name, occupation, and interests, use the 'extractUserInfoJSON' tool
        - After extracting the information, clearly announce: "اب میں آپ کو اپنے اہم ساتھی کے حوالے کر رہا ہوں"
        - Output the exact signal: >>> HANDOVER_TO_CORE
        - This signals that onboarding is complete and the Core Agent should take over

        ## Tool Usage
        - Use 'storeInMemory' to save important user information
        - Use 'updateUserProfile' to build their profile
        - Use 'extractUserInfoJSON' when you have enough information to complete onboarding
        - Use 'getUserProfile' to reference what you know about them
        """)

    @function_tool()
    async def storeInMemory(self, context: RunContext, category: str, key: str, value: str):
        return {"result": memory_manager.store(category, key, value)}

    @function_tool()
    async def retrieveFromMemory(self, context: RunContext, category: str, key: str):
        val = memory_manager.retrieve(category, key)
        return {"value": val or ""}

    @function_tool()
    async def updateUserProfile(self, context: RunContext, new_info: str):
        updated_profile = user_profile.update_profile(new_info)
        return {"updated_profile": updated_profile}

    @function_tool()
    async def getUserProfile(self, context: RunContext):
        return {"profile": user_profile.get()}

    @function_tool()
    async def extractUserInfoJSON(self, context: RunContext, user_responses: str):
        """Extract user information in JSON format and trigger handover to Core Agent."""
        json_data = extract_user_info_to_json(user_responses)
        print(f"[JSON EXTRACTED] {json_data}")
        
        # Store the extracted information
        memory_manager.store("FACT", "user_info_json", str(json_data))
        
        # Mark onboarding as complete and trigger handover
        memory_manager.store("FACT", "onboarding_complete", "true")
        
        # Signal handover to Core Agent
        print("\n" + "="*50)
        print(">>> HANDOVER_TO_CORE")
        print("="*50)
        print("Onboarding complete! Handing over to Core Agent...")
        
        return {"user_info": json_data, "handover": ">>> HANDOVER_TO_CORE"}

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
        
        # Extract JSON information from all user responses
        all_responses = memory_manager.retrieve_all()
        user_responses_text = " ".join([f"{key}: {value}" for key, value in all_responses.items() if "user_input" in key])
        if user_responses_text:
            json_data = extract_user_info_to_json(user_responses_text)
            print(f"[JSON EXTRACTED] {json_data}")
            # Store JSON data in memory
            memory_manager.store("FACT", "user_info_json", str(json_data))

# ---------------------------
# Entrypoint
# ---------------------------
async def entrypoint(ctx: agents.JobContext):
    tts = TTS(voice_id="17", output_format="MP3_22050_32")
    assistant = OnboardingAgent()

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
                instructions=f"""Welcome the user warmly in Urdu and tell them this story:
                {WELCOME_STORY}
                
                After the story, ask them the first onboarding question naturally: "{ONBOARDING_QUESTIONS[0]}"
                
                {extra_context}"""
            )
        else:
            await session.generate_reply(
                instructions=f"{base_instructions}\n\nUse this context:\n{extra_context}\nUser said: {user_text}"
            )

    # Send initial greeting with story and questions
    await generate_with_memory(greet=True)

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        initialize_process_timeout=60,
    ))
