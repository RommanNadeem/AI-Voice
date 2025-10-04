#!/usr/bin/env python3

import os
import asyncio
import json
import logging
from typing import Optional
from dotenv import load_dotenv

# Disable verbose HTTP/2 logging
logging.getLogger("hpack.hpack").setLevel(logging.WARNING)
logging.getLogger("hpack.table").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Load environment variables
load_dotenv()

# Import LiveKit components
import livekit.agents as agents
from livekit.agents import Agent, AgentSession, RoomInputOptions, RunContext, function_tool
import livekit.plugins.openai as lk_openai
import livekit.plugins.silero as silero

# Import TTS
from uplift_tts import TTS

# Import Supabase
from supabase import create_client, Client

# ---------------------------
# Simple Configuration
# ---------------------------

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Optional[Client] = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("[SUPABASE] Connected")
    except Exception as e:
        print(f"[SUPABASE ERROR] Connection failed: {e}")
        supabase = None

# ---------------------------
# Simple Onboarding System
# ---------------------------

# Simple onboarding questions
ONBOARDING_QUESTIONS = [
    "آپ کا نام کیا ہے؟",
    "آپ کیا کام کرتے ہیں؟", 
    "آپ کو کیا کرنے کا شوق ہے؟"
]

# Simple onboarding state
onboarding_state = {
    "is_active": True,
    "current_question": 0,
    "responses": [],
    "story_told": False
}

# ---------------------------
# Simple Memory System
# ---------------------------

def save_to_memory(category: str, key: str, value: str):
    """Save to Supabase memory table."""
    if supabase is None:
        print(f"[MEMORY] Offline: {category} - {key} = {value}")
        return
    
    try:
        response = supabase.table('memory').upsert({
            'user_id': 'default_user',
            'category': category,
            'key': key,
            'value': value
        }).execute()
        print(f"[MEMORY] Saved: {category} - {key}")
    except Exception as e:
        print(f"[MEMORY ERROR] Failed to save: {e}")

def get_from_memory(category: str, key: str):
    """Get from Supabase memory table."""
    if supabase is None:
        return None
    
    try:
        response = supabase.table('memory').select('value').eq('user_id', 'default_user').eq('category', category).eq('key', key).execute()
        if response.data:
            return response.data[0]['value']
        return None
    except Exception as e:
        print(f"[MEMORY ERROR] Failed to get: {e}")
        return None

def is_onboarding_complete():
    """Check if onboarding is complete based on responses."""
    return len(onboarding_state["responses"]) >= len(ONBOARDING_QUESTIONS)

def reset_onboarding_state():
    """Reset onboarding state for new session."""
    global onboarding_state
    onboarding_state = {
        "is_active": True,
        "current_question": 0,
        "responses": [],
        "story_told": False
    }
    print("[ONBOARDING] State reset for new session")

# ---------------------------
# Simple Onboarding Functions
# ---------------------------

async def start_onboarding(session):
    """Start the onboarding process."""
    if not onboarding_state["story_told"]:
        # Tell the story
        story = "خوش آمدید! میں آپ سے کچھ سوالات پوچھنا چاہتا ہوں تاکہ میں آپ کی بہتر مدد کر سکوں۔"
        await session.generate_reply(instructions=f"Say this in Urdu: {story}")
        onboarding_state["story_told"] = True
    
    # Ask first question
    await ask_next_question(session)

async def ask_next_question(session):
    """Ask the next onboarding question."""
    if onboarding_state["current_question"] < len(ONBOARDING_QUESTIONS):
        question = ONBOARDING_QUESTIONS[onboarding_state["current_question"]]
        
        # Add acknowledgment if not first question
        if onboarding_state["current_question"] > 0:
            prev_response = onboarding_state["responses"][-1]
            if onboarding_state["current_question"] == 1:
                message = f"شکریہ! اب بتائیے، {question}"
            else:
                message = f"اچھا! آخر میں، {question}"
        else:
            message = question
        
        await session.generate_reply(instructions=f"Say this in Urdu: {message}")
        print(f"[ONBOARDING] Asked question {onboarding_state['current_question'] + 1}: {question}")

async def handle_onboarding_response(user_text: str, session):
    """Handle user response during onboarding."""
    # Store response
    onboarding_state["responses"].append(user_text)
    print(f"[ONBOARDING] Response {len(onboarding_state['responses'])}: {user_text}")
    
    # Move to next question
    onboarding_state["current_question"] += 1
    print(f"[ONBOARDING] Moved to question {onboarding_state['current_question']}")
    
    # Check if onboarding is complete
    if is_onboarding_complete():
        print("[ONBOARDING] All questions answered, completing onboarding...")
        await complete_onboarding(session)
    else:
        print(f"[ONBOARDING] Asking next question {onboarding_state['current_question'] + 1}...")
        await ask_next_question(session)

async def complete_onboarding(session):
    """Complete the onboarding process."""
    print("[ONBOARDING] Completing onboarding...")
    
    # Save all responses to memory
    for i, response in enumerate(onboarding_state["responses"]):
        save_to_memory("ONBOARDING", f"response_{i+1}", response)
    
    # Extract and save user info
    all_responses = " ".join(onboarding_state["responses"])
    save_to_memory("USER_INFO", "all_responses", all_responses)
    
    # Try to extract name from first response
    if onboarding_state["responses"]:
        first_response = onboarding_state["responses"][0]
        save_to_memory("USER_INFO", "name", first_response)
    
    # Mark onboarding as complete
    onboarding_state["is_active"] = False
    
    # Send completion message
    completion_message = "شکریہ! اب میں آپ کی مدد کے لیے تیار ہوں۔ آپ مجھ سے کچھ بھی پوچھ سکتے ہیں۔"
    await session.generate_reply(instructions=f"Say this in Urdu: {completion_message}")
    
    print("[ONBOARDING] Onboarding completed successfully!")

# ---------------------------
# Simple Agent
# ---------------------------

class SimpleAssistant(Agent):
    def __init__(self):
        super().__init__(instructions="""
        You are a helpful AI assistant that speaks in Urdu.
        
        - Speak in casual Urdu, not formal language
        - Keep responses short and friendly
        - Be like a close friend
        - Ask follow-up questions to keep conversation going
        - Remember what the user has told you
        """)

    async def on_user_turn_completed(self, turn_ctx, new_message):
        """Handle user input."""
        user_text = new_message.text_content
        print(f"[USER INPUT] {user_text}")
        print(f"[ONBOARDING STATE] Active: {onboarding_state['is_active']}, Question: {onboarding_state['current_question']}, Responses: {len(onboarding_state['responses'])}")
        
        # If onboarding is active, handle onboarding response
        if not is_onboarding_complete():
            print("[ONBOARDING] Handling onboarding response...")
            await handle_onboarding_response(user_text, turn_ctx.session)
            return
        
        # Normal conversation - save to memory
        print("[CONVERSATION] Handling normal conversation...")
        save_to_memory("CONVERSATION", "user_input", user_text)
        
        # Generate response with memory context
        memory_context = get_from_memory("USER_INFO", "all_responses") or ""
        if memory_context:
            instructions = f"""
            Respond to the user in Urdu. Use this context about the user:
            {memory_context}
            
            User said: {user_text}
            """
        else:
            instructions = f"Respond to the user in Urdu. User said: {user_text}"
        
        await turn_ctx.session.generate_reply(instructions=instructions)

# ---------------------------
# Entrypoint
# ---------------------------

async def entrypoint(ctx: agents.JobContext):
    """Main entrypoint for the agent."""
    print("[AGENT] Starting Simple Assistant...")
    
    # Initialize TTS
    tts = TTS()
    
    # Create assistant
    assistant = SimpleAssistant()
    
    # Create session
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
    
    # Check if onboarding is needed
    if not is_onboarding_complete():
        print("[AGENT] Starting onboarding...")
        await start_onboarding(session)
    else:
        print("[AGENT] Onboarding already completed, starting normal conversation...")
        greeting = "ہیلو! میں آپ کی مدد کے لیے یہاں ہوں۔"
        await session.generate_reply(instructions=f"Say this in Urdu: {greeting}")

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        initialize_process_timeout=60,
    ))
