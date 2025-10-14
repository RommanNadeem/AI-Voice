"""
Conversation Summary Service
Generates and manages conversation summaries using existing conversation_state table.

Uses columns:
- last_summary (TEXT): Most recent conversation summary
- last_topics (JSONB): Array of key topics discussed
- last_user_message (TEXT): Most recent user message
- last_assistant_message (TEXT): Most recent assistant message  
- last_conversation_at (TIMESTAMPTZ): Timestamp of last exchange
"""

import asyncio
import json
from typing import Optional, List, Dict, Tuple
from openai import OpenAI
from datetime import datetime

from core.config import Config
from core.validators import get_current_user_id, can_write_for_current_user
from core.user_id import UserId


class ConversationSummaryService:
    """
    Manages progressive conversation summarization.
    
    Strategy:
    - Incremental summaries every N turns (default: 10)
    - Final summary on session end
    - Leverages existing conversation history tracking
    - Stores in conversation_summaries table
    """
    
    def __init__(self, supabase, openai_client: Optional[OpenAI] = None):
        self.supabase = supabase
        self.openai = openai_client or OpenAI(api_key=Config.OPENAI_API_KEY)
        self.current_session_id = None
        self.last_summary_id = None
        self.turns_since_last_summary = 0
        
        print("[SUMMARY SERVICE] Initialized")
    
    def set_session(self, session_id: str):
        """Set current session ID for summary tracking"""
        self.current_session_id = session_id
        self.turns_since_last_summary = 0
        print(f"[SUMMARY SERVICE] Session set: {session_id[:20]}...")
    
    async def generate_summary(
        self,
        conversation_turns: List[Tuple[str, str]],
        existing_summary: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict:
        """
        Generate conversation summary using LLM.
        
        Args:
            conversation_turns: List of (user_msg, assistant_msg) tuples
            existing_summary: Previous summary to build upon (optional)
            user_id: User ID for logging
            
        Returns:
            Dict with summary_text, key_topics, emotional_tone, important_facts
        """
        uid = user_id or get_current_user_id()
        
        if not conversation_turns:
            print("[SUMMARY] ⚠️ No turns to summarize")
            return self._empty_summary()
        
        print(f"[SUMMARY] 🤖 Generating summary for {len(conversation_turns)} turns...")
        
        try:
            # Build conversation text
            conversation_text = self._format_turns(conversation_turns)
            
            # Create summary prompt
            prompt = self._build_prompt(existing_summary)
            
            # Call LLM
            response = await asyncio.to_thread(
                self.openai.chat.completions.create,
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": conversation_text}
                ],
                temperature=0.3,  # Lower for consistent summaries
                max_tokens=400
            )
            
            # Parse response
            summary_data = self._parse_response(response.choices[0].message.content)
            
            print(f"[SUMMARY] ✅ Generated: {len(summary_data['summary_text'])} chars")
            print(f"[SUMMARY]    Topics: {', '.join(summary_data['key_topics'][:3])}")
            print(f"[SUMMARY]    Tone: {summary_data['emotional_tone']}")
            
            return summary_data
            
        except Exception as e:
            print(f"[SUMMARY] ❌ Generation failed: {e}")
            return self._empty_summary()
    
    def _format_turns(self, turns: List[Tuple[str, str]]) -> str:
        """Format conversation turns for LLM summarization"""
        lines = []
        for i, (user_msg, asst_msg) in enumerate(turns, 1):
            lines.append(f"Turn {i}:")
            lines.append(f"U: {user_msg}")
            lines.append(f"A: {asst_msg}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _build_prompt(self, previous_summary: Optional[str]) -> str:
        """Build summarization prompt"""
        
        if previous_summary:
            return f"""You are summarizing a conversation segment to UPDATE a previous summary.

Previous Summary:
{previous_summary}

Task: Summarize the NEW conversation segment in and MERGE it with the previous summary.

Focus on:
1. Key topics discussed (list 2-4 main themes)
2. Important facts the user shared
3. Overall emotional tone
4. Any changes or progression from previous summary
5. Conversation hook for next session

Output Format:
Summary: [Concise 100-150 word overview in English where natural]
Topics: [topic1, topic2, topic3]
Tone: [emotional_tone]
Facts: [fact1, fact2, fact3]

Keep it concise and actionable."""
        
        else:
            return """Summarize this conversation segment focusing on what matters for future sessions.

Focus on:
1. Key topics discussed (2-4 main themes)
2. Important personal facts the user shared
3. Overall emotional tone (happy, stressed, reflective, excited, etc.)
4. User's goals or plans mentioned
5. Conversation hook for next session

Output Format:
Summary: [Concise 100-150 word overview, use English where natural]
Topics: [topic1, topic2, topic3]  
Tone: [emotional_tone]
Facts: [important_fact1, important_fact2]

Be specific and concise."""
    
    def _parse_response(self, response: str) -> Dict:
        """Parse LLM summary response into structured format"""
        
        result = {
            "summary_text": "",
            "key_topics": [],
            "important_facts": [],
            "emotional_tone": "neutral"
        }
        
        lines = response.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            if line.startswith("Summary:"):
                result["summary_text"] = line.replace("Summary:", "").strip()
            elif line.startswith("Topics:"):
                topics_text = line.replace("Topics:", "").strip()
                result["key_topics"] = [t.strip() for t in topics_text.split(",") if t.strip()]
            elif line.startswith("Tone:"):
                result["emotional_tone"] = line.replace("Tone:", "").strip()
            elif line.startswith("Facts:"):
                facts_text = line.replace("Facts:", "").strip()
                result["important_facts"] = [f.strip() for f in facts_text.split(",") if f.strip()]
            elif not line.startswith(("Summary:", "Topics:", "Tone:", "Facts:")) and line:
                # Continuation of summary
                if result["summary_text"]:
                    result["summary_text"] += " " + line
        
        return result
    
    def _empty_summary(self) -> Dict:
        """Return empty summary structure"""
        return {
            "summary_text": "No conversation to summarize",
            "key_topics": [],
            "important_facts": [],
            "emotional_tone": "neutral"
        }
    
    async def save_summary(
        self,
        summary_data: Dict,
        turn_count: int,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Save conversation summary to conversation_state table.
        Updates last_summary, last_topics, and last_conversation_at columns.
        
        Args:
            summary_data: Summary dict from generate_summary()
            turn_count: Number of turns in this summary
            user_id: User ID (uses current user if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        # Check write permissions
        if not can_write_for_current_user():
            print("[SUMMARY] ❌ Write permission denied")
            return False
        
        uid = user_id or get_current_user_id()
        
        if not uid:
            print("[SUMMARY] ❌ Missing user_id")
            return False
        
        try:
            # Update conversation_state with summary
            update_data = {
                "last_summary": summary_data["summary_text"],
                "last_topics": summary_data.get("key_topics", []),
                "last_conversation_at": datetime.utcnow().isoformat()
            }
            
            # Perform update
            resp = await asyncio.to_thread(
                lambda: self.supabase.table("conversation_state")
                    .update(update_data)
                    .eq("user_id", uid)
                    .execute()
            )
            
            if resp.data:
                print(f"[SUMMARY] ✅ Saved ({len(summary_data['summary_text'])} chars, {turn_count} turns)")
                return True
            else:
                print("[SUMMARY] ❌ Save failed - no rows updated")
                return False
            
        except Exception as e:
            print(f"[SUMMARY] ❌ Exception during save: {e}")
            return False
    
    async def get_last_summary(self, user_id: str) -> Optional[Dict]:
        """
        Get the last conversation summary from conversation_state table.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict with last_summary, last_topics, last_conversation_at or None
        """
        try:
            resp = await asyncio.to_thread(
                lambda: self.supabase
                    .table("conversation_state")
                    .select("last_summary, last_topics, last_conversation_at")
                    .eq("user_id", user_id)
                    .single()
                    .execute()
            )
            
            if resp.data and resp.data.get("last_summary"):
                print(f"[SUMMARY] ✅ Loaded summary ({len(resp.data.get('last_summary', ''))} chars)")
                return resp.data
            else:
                return None
            
        except Exception as e:
            print(f"[SUMMARY] ❌ Load failed: {e}")
            return None
    
    def format_summary_for_context(self, summary_data: Dict) -> str:
        """
        Format summary for ChatContext injection.
        Makes it actionable and easy for LLM to use naturally.
        
        Args:
            summary_data: Dict from conversation_state (last_summary, last_topics, last_conversation_at)
            
        Returns:
            Formatted string ready for ChatContext.add_message()
        """
        if not summary_data or not summary_data.get("last_summary"):
            return ""
        
        parts = ["## Last Conversation Context\n"]
        
        # Add timestamp for temporal awareness
        last_convo = summary_data.get("last_conversation_at")
        if last_convo:
            date_str = last_convo[:10] if isinstance(last_convo, str) else str(last_convo)[:10]
            parts.append(f"**When:** {date_str}\n")
        
        # Add the summary
        parts.append(f"**What was discussed:**\n{summary_data['last_summary']}")
        
        # Add topics for quick reference
        topics = summary_data.get("last_topics")
        if topics:
            # Handle both JSONB (list) and string formats
            if isinstance(topics, str):
                try:
                    topics = json.loads(topics)
                except:
                    pass
            
            if isinstance(topics, list) and topics:
                parts.append(f"\n**Key topics:** {', '.join(topics[:5])}")
        
        # Add usage guidance
        parts.append("\n*Use this context naturally when relevant. Don't force references to old topics.*")
        
        return "\n".join(parts)

