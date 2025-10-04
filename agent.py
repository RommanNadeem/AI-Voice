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
            
            response = self.supabase.table('memory').select('category, key, value').eq('user_id', user_id).execute()
            return {f"{row['category']}:{row['key']}": row['value'] for row in response.data}
        except Exception as e:
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

    def save_profile(self, profile_text: str):
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

# ---------------------------
# Onboarding Flag Management
# ---------------------------
def get_onboarding_flags():
    """Get onboarding flags from Supabase auth user metadata for current user."""
    try:
        if memory_manager.supabase is None:
            print("[FLAGS] Supabase not available, using default flags")
            return {
                "is_new_user": True,
                "is_onboarding_done": False,
                "onboarding_questions": False,
                "story_told": False,
                "answered_questions": [],
                "current_question_index": 0,
                "user_responses": []
            }
        
        # Try to get current user and their metadata
        try:
            user_response = memory_manager.supabase.auth.get_user()
            if user_response.user and user_response.user.user_metadata:
                metadata = user_response.user.user_metadata
                flags = metadata.get('data', {})
                
                # Ensure all required flags exist
                flags.setdefault('is_new_user', True)
                flags.setdefault('is_onboarding_done', False)
                flags.setdefault('onboarding_questions', False)
                
                print(f"[FLAGS] Loaded from auth user metadata: {flags}")
                return flags
        except Exception as e:
            print(f"[FLAGS] Auth user metadata access failed, using defaults: {e}")
        
        # Fallback: return default flags
        default_flags = {
            "is_new_user": True,
            "is_onboarding_done": False,
            "onboarding_questions": False,
            "story_told": False,
            "answered_questions": [],
            "current_question_index": 0,
            "user_responses": []
        }
        print(f"[FLAGS] Using defaults: {default_flags}")
        return default_flags
            
    except Exception as e:
        print(f"[FLAGS ERROR] Failed to get flags: {e}")
        return {
            "is_new_user": True,
            "is_onboarding_done": False,
            "onboarding_questions": False,
            "story_told": False,
            "answered_questions": [],
            "current_question_index": 0,
            "user_responses": []
        }

def set_onboarding_flags(flags):
    """Set onboarding flags in Supabase auth user metadata for current user."""
    try:
        if memory_manager.supabase is None:
            print("[FLAGS] Supabase not available, cannot save flags")
            return False
        
        # Try to update user metadata through auth API
        try:
            response = memory_manager.supabase.auth.update_user({
                'data': flags
            })
            
            if response.user:
                print(f"[FLAGS] Saved to auth user metadata: {flags}")
                return True
            else:
                print(f"[FLAGS] Failed to update user metadata")
                return False
        except Exception as e:
            print(f"[FLAGS] Auth user metadata update failed: {e}")
            return False
        
    except Exception as e:
        print(f"[FLAGS ERROR] Failed to save flags: {e}")
        return False

def update_onboarding_flag(flag_name, value):
    """Update a specific onboarding flag."""
    global user_state
    
    # Update local state
    user_state[flag_name] = value
    
    # Update Supabase
    flags_to_save = {
        "is_new_user": user_state.get("is_new_user", True),
        "is_onboarding_done": user_state.get("is_onboarding_done", False),
        "onboarding_questions": user_state.get("onboarding_questions", False),
        "story_told": user_state.get("story_told", False),
        "answered_questions": user_state.get("answered_questions", []),
        "current_question_index": user_state.get("current_question_index", 0),
        "user_responses": user_state.get("user_responses", [])
    }
    
    set_onboarding_flags(flags_to_save)
    print(f"[FLAGS] Updated {flag_name} = {value}")

# ---------------------------
# State Management
# ---------------------------
# Initialize user state with flags from Supabase
user_state = {
    "current_question_index": 0,
    "user_responses": [],
    "story_told": False,
    "answered_questions": []
}

# Load onboarding flags from Supabase
onboarding_flags = get_onboarding_flags()
user_state.update(onboarding_flags)

# ---------------------------
# Onboarding Functions
# ---------------------------
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
                    
                    Return only valid JSON, no other text."""
                },
                {"role": "user", "content": user_responses}
            ]
        )
        
        json_str = resp.choices[0].message.content.strip()
        # Try to parse JSON to validate
        import json
        user_info = json.loads(json_str)
        
        # Store in memory
        memory_manager.store("FACT", "user_name", user_info.get("name", ""))
        memory_manager.store("FACT", "user_occupation", user_info.get("occupation", ""))
        memory_manager.store("INTEREST", "user_interests", user_info.get("interests", ""))
        
        # Update user profile
        profile_text = f"Name: {user_info.get('name', '')}, Occupation: {user_info.get('occupation', '')}, Interests: {user_info.get('interests', '')}"
        user_profile.smart_update(profile_text)
        
        print(f"[ONBOARDING COMPLETE] User info extracted: {user_info}")
        return user_info
        
    except Exception as e:
        print(f"[ONBOARDING ERROR] Failed to extract user info: {e}")
        return JSON_TEMPLATE

async def run_onboarding(session):
    """Run the onboarding flow: story + questions."""
    global user_state
    
    print("[ONBOARDING] Starting onboarding flow...")
    
    # Tell the welcome story only if not told before
    if not user_state.get("story_told", False):
        await session.generate_reply(
            instructions=f"Tell the user this welcome story in Urdu: {WELCOME_STORY}"
        )
        user_state["story_told"] = True
        print("[ONBOARDING] Welcome story told")
    else:
        print("[ONBOARDING] Welcome story already told, skipping")
    
    # Find the first unanswered question
    answered_count = len(user_state.get("answered_questions", []))
    if answered_count < len(ONBOARDING_QUESTIONS):
        question_index = answered_count
        question = ONBOARDING_QUESTIONS[question_index]
        user_state["current_question_index"] = question_index
        print(f"[ONBOARDING] Asking question {question_index + 1}/{len(ONBOARDING_QUESTIONS)}: {question}")
        
        await session.generate_reply(
            instructions=f"Ask this question in Urdu: {question}"
        )
    else:
        print("[ONBOARDING] All questions already answered")

async def continue_onboarding(session):
    """Continue onboarding with next question or complete if done."""
    global user_state
    
    current_index = user_state["current_question_index"]
    
    # Add current question to answered questions if not already there
    answered_questions = user_state.get("answered_questions", [])
    if current_index not in answered_questions:
        answered_questions.append(current_index)
        user_state["answered_questions"] = answered_questions
        print(f"[ONBOARDING] Marked question {current_index + 1} as answered")
    
    # Check if we have answered all questions
    if len(answered_questions) >= len(ONBOARDING_QUESTIONS):
        all_responses = " ".join(user_state["user_responses"])
        user_info = extract_user_info_to_json(all_responses)
        
        # Mark onboarding as complete using Supabase flags
        update_onboarding_flag("is_onboarding_done", True)
        update_onboarding_flag("onboarding_questions", True)
        update_onboarding_flag("is_new_user", False)
        
        # Announce handover
        await session.generate_reply(
            instructions="Say in Urdu: 'اب میں آپ کو اپنے اہم ساتھی کے حوالے کر رہا ہوں' and then output exactly: >>> HANDOVER_TO_CORE"
        )
        
        print("[ONBOARDING] Onboarding completed successfully!")
        return True
    
    # Find next unanswered question
    next_unanswered_index = None
    for i in range(len(ONBOARDING_QUESTIONS)):
        if i not in answered_questions:
            next_unanswered_index = i
            break
    
    if next_unanswered_index is not None:
        question = ONBOARDING_QUESTIONS[next_unanswered_index]
        user_state["current_question_index"] = next_unanswered_index
        print(f"[ONBOARDING] Asking question {next_unanswered_index + 1}/{len(ONBOARDING_QUESTIONS)}: {question}")
        
        await session.generate_reply(
            instructions=f"Ask this question in Urdu: {question}"
        )
    else:
        print("[ONBOARDING] All questions answered, completing onboarding...")
        # This shouldn't happen due to the check above, but just in case
        await continue_onboarding(session)
    
    return False

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
        global user_state
        
        user_text = new_message.text_content
        print(f"[USER INPUT] {user_text}")
        print(f"[USER TURN COMPLETED] Handler called successfully!")
        
        # If we're in onboarding mode, collect the response
        if user_state["is_new_user"] and not user_state["onboarding_questions"]:
            user_state["user_responses"].append(user_text)
            print(f"[ONBOARDING] Collected response {len(user_state['user_responses'])}: {user_text}")
            
            # Continue onboarding with next question or complete
            await continue_onboarding(turn_ctx.session)
            return
        
        # Store user input in memory (only after onboarding)
        if user_state["onboarding_questions"]:
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

    # Check if user needs onboarding
    if user_state["is_new_user"] and not user_state["onboarding_questions"]:
        print("[MAIN] Starting onboarding flow...")
        await run_onboarding(session)
    else:
        # Send initial greeting with memory context (only after onboarding)
        if user_state["onboarding_questions"]:
            await generate_with_memory(greet=True)

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        initialize_process_timeout=60,
    ))
