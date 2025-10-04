#!/usr/bin/env python3
"""
Multi-Agent Voice Companion Coordinator

This script manages the handover between the Onboarding Agent and Core Agent.
It ensures proper coordination and data flow between the two agents.
"""

import asyncio
import os
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentSession, RoomInputOptions
import livekit_openai as lk_openai
from livekit.agents.voice_assistant import silero

# Import our agents
from Onboarding import OnboardingAgent
from agent import Assistant

# Load environment variables
load_dotenv()

class MultiAgentCoordinator:
    def __init__(self):
        self.current_agent = None
        self.onboarding_complete = False
        self.user_id = None
        
    def check_onboarding_status(self):
        """Check if onboarding is complete."""
        try:
            from agent import memory_manager
            onboarding_complete = memory_manager.retrieve("FACT", "onboarding_complete")
            return onboarding_complete == "true"
        except Exception as e:
            print(f"[COORDINATOR ERROR] Failed to check onboarding status: {e}")
            return False
    
    def get_user_id(self):
        """Get or generate user ID."""
        if not self.user_id:
            # In a real implementation, this would come from authentication
            self.user_id = "user_" + str(hash(os.getenv("LIVEKIT_URL", "default")))
        return self.user_id
    
    async def start_onboarding_agent(self, ctx: agents.JobContext):
        """Start the onboarding agent."""
        print("[COORDINATOR] Starting Onboarding Agent...")
        
        from uplift_tts import TTS
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
        
        self.current_agent = "onboarding"
        print("[COORDINATOR] Onboarding Agent started successfully")
    
    async def start_core_agent(self, ctx: agents.JobContext):
        """Start the core agent."""
        print("[COORDINATOR] Starting Core Agent...")
        
        from uplift_tts import TTS
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
        
        self.current_agent = "core"
        print("[COORDINATOR] Core Agent started successfully")
    
    async def monitor_handover(self, ctx: agents.JobContext):
        """Monitor for handover signal from onboarding agent."""
        print("[COORDINATOR] Monitoring for handover signal...")
        
        # Check every 5 seconds for onboarding completion
        while not self.onboarding_complete:
            await asyncio.sleep(5)
            self.onboarding_complete = self.check_onboarding_status()
            
            if self.onboarding_complete:
                print("[COORDINATOR] Handover signal detected! Switching to Core Agent...")
                break
        
        # Start core agent after handover
        if self.onboarding_complete:
            await self.start_core_agent(ctx)

async def entrypoint(ctx: agents.JobContext):
    """Main entrypoint for the multi-agent system."""
    coordinator = MultiAgentCoordinator()
    
    print("[COORDINATOR] Multi-Agent Voice Companion starting...")
    print("[COORDINATOR] User ID:", coordinator.get_user_id())
    
    # Check if onboarding is already complete
    if coordinator.check_onboarding_status():
        print("[COORDINATOR] Onboarding already complete, starting Core Agent directly...")
        await coordinator.start_core_agent(ctx)
    else:
        print("[COORDINATOR] Starting onboarding process...")
        # Start onboarding agent
        await coordinator.start_onboarding_agent(ctx)
        
        # Monitor for handover in background
        await coordinator.monitor_handover(ctx)

if __name__ == "__main__":
    agents.run(entrypoint)
