import os
import sqlite3
import faiss
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

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

    def __init__(self, db_path="onboarding_memory.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    UNIQUE(category, key)
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id TEXT PRIMARY KEY,
                    profile_text TEXT NOT NULL
                )
            """)

    def store(self, category: str, key: str, value: str):
        category = category.upper()
        if category not in self.ALLOWED_CATEGORIES:
            category = "FACT"
        with self.conn:
            self.conn.execute("""
                INSERT INTO memory (category, key, value)
                VALUES (?, ?, ?)
                ON CONFLICT(category, key) DO UPDATE SET value=excluded.value
            """, (category, key, value))
        print(f"[MEMORY STORED] [{category}] {key} = {value}")
        return f"Stored: [{category}] {key} = {value}"

    def retrieve(self, category: str, key: str):
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM memory WHERE category=? AND key=?", (category, key))
        row = cur.fetchone()
        return row[0] if row else None

    def retrieve_all(self):
        cur = self.conn.cursor()
        cur.execute("SELECT category, key, value FROM memory")
        return {f"{cat}:{key}": val for cat, key, val in cur.fetchall()}

    def save_profile(self, user_id: str, profile_text: str):
        with self.conn:
            self.conn.execute("""
                INSERT INTO profiles (user_id, profile_text)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET profile_text=excluded.profile_text
            """, (user_id, profile_text))
        print(f"[PROFILE STORED] for {user_id}")

    def load_profile(self, user_id: str):
        cur = self.conn.cursor()
        cur.execute("SELECT profile_text FROM profiles WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        return row[0] if row else ""


memory_manager = MemoryManager()

# ---------------------------
# User Profile Manager
# ---------------------------
class UserProfile:
    def __init__(self, user_id="default_user"):
        self.user_id = user_id
        self.profile_text = memory_manager.load_profile(user_id)
        if self.profile_text:
            print(f"[PROFILE LOADED] for {user_id}: {self.profile_text}")
        else:
            print(f"[PROFILE EMPTY] No existing profile for {user_id}")

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
        with memory_manager.conn:
            memory_manager.conn.execute("DELETE FROM profiles WHERE user_id=?", (self.user_id,))
        self.profile_text = ""
        print(f"[PROFILE FORGOT] for {self.user_id}")
        return f"Profile deleted for {self.user_id}"


user_profile = UserProfile(user_id="onboarding_user")

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

        ## Tool Usage
        - Use 'storeInMemory' to save important user information
        - Use 'updateUserProfile' to build their profile
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
        """Extract user information in JSON format."""
        json_data = extract_user_info_to_json(user_responses)
        print(f"[JSON EXTRACTED] {json_data}")
        return {"user_info": json_data}

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
