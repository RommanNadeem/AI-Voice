#!/usr/bin/env python3
"""
AI Voice Companion Launcher

This script provides different ways to run the voice companion:
1. Onboarding Agent only
2. Core Agent only  
3. Multi-Agent Coordinator (recommended)
"""

import sys
import asyncio
from livekit import agents

def print_usage():
    print("""
AI Voice Companion Launcher

Usage:
    python launcher.py onboarding    - Run Onboarding Agent only
    python launcher.py core          - Run Core Agent only
    python launcher.py coordinator   - Run Multi-Agent Coordinator (recommended)
    python launcher.py help          - Show this help message

The Multi-Agent Coordinator is recommended as it:
- Starts with Onboarding Agent for new users
- Automatically hands over to Core Agent when onboarding is complete
- Maintains user context between agents
""")

async def run_onboarding():
    """Run only the Onboarding Agent."""
    print("[LAUNCHER] Starting Onboarding Agent...")
    from Onboarding import entrypoint
    await agents.run(entrypoint)

async def run_core():
    """Run only the Core Agent."""
    print("[LAUNCHER] Starting Core Agent...")
    from agent import entrypoint
    await agents.run(entrypoint)

async def run_coordinator():
    """Run the Multi-Agent Coordinator."""
    print("[LAUNCHER] Starting Multi-Agent Coordinator...")
    from multi_agent_coordinator import entrypoint
    await agents.run(entrypoint)

def main():
    if len(sys.argv) < 2:
        print("Error: Please specify which agent to run")
        print_usage()
        sys.exit(1)
    
    mode = sys.argv[1].lower()
    
    if mode == "help":
        print_usage()
        sys.exit(0)
    elif mode == "onboarding":
        asyncio.run(run_onboarding())
    elif mode == "core":
        asyncio.run(run_core())
    elif mode == "coordinator":
        asyncio.run(run_coordinator())
    else:
        print(f"Error: Unknown mode '{mode}'")
        print_usage()
        sys.exit(1)

if __name__ == "__main__":
    main()
