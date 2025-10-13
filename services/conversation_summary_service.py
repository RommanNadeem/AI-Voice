"""
Conversation Summary Service
Generates and manages progressive conversation summaries using RAG and LLM
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

Task: Summarize the NEW conversation segment and MERGE it with the previous summary.

Focus on:
1. Key topics discussed (list 2-4 main themes)
2. Important facts the user shared
3. Overall emotional tone
4. Any changes or progression from previous summary

Output Format:
Summary: [Concise 100-150 word overview in Urdu where natural]
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

Output Format:
Summary: [Concise 100-150 word overview, use Urdu where natural]
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
        is_final: bool = False,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Save conversation summary to database.
        
        Args:
            summary_data: Summary dict from generate_summary()
            turn_count: Number of turns in this summary
            is_final: True if this is the final session summary
            user_id: User ID (uses current user if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        if not can_write_for_current_user():
            print("[SUMMARY] ⚠️ Write permission denied")
            return False
        
        uid = user_id or get_current_user_id()
        
        if not uid or not self.current_session_id:
            print(f"[SUMMARY] ⚠️ Missing user_id or session_id")
            return False
        
        try:
            data = {
                "user_id": uid,
                "session_id": self.current_session_id,
                "summary_text": summary_data["summary_text"],
                "key_topics": summary_data.get("key_topics", []),
                "important_facts": summary_data.get("important_facts", []),
                "emotional_tone": summary_data.get("emotional_tone", "neutral"),
                "turn_count": turn_count,
                "is_final": is_final,
                "previous_summary_id": self.last_summary_id
            }
            
            # Set end_time if final
            if is_final:
                data["end_time"] = datetime.utcnow().isoformat()
            
            # Save to database
            resp = await asyncio.to_thread(
                lambda: self.supabase.table("conversation_summaries").insert(data).execute()
            )
            
            if resp.data:
                summary_id = resp.data[0]["id"]
                self.last_summary_id = summary_id
                
                summary_type = "FINAL" if is_final else "INCREMENTAL"
                print(f"[SUMMARY] ✅ {summary_type} summary saved")
                print(f"[SUMMARY]    ID: {summary_id[:8]}...")
                print(f"[SUMMARY]    User: {UserId.format_for_display(uid)}")
                print(f"[SUMMARY]    Turns: {turn_count}")
                
                return True
            
            print("[SUMMARY] ⚠️ No data returned from insert")
            return False
            
        except Exception as e:
            print(f"[SUMMARY] ❌ Save failed: {e}")
            return False
    
    async def get_recent_summaries(
        self,
        user_id: str,
        limit: int = 3,
        final_only: bool = False
    ) -> List[Dict]:
        """
        Get recent conversation summaries for a user.
        
        Args:
            user_id: User ID
            limit: Maximum number of summaries to return
            final_only: If True, only return final session summaries
            
        Returns:
            List of summary dicts ordered by most recent first
        """
        try:
            query = self.supabase.table("conversation_summaries").select("*").eq("user_id", user_id)
            
            if final_only:
                query = query.eq("is_final", True)
            
            resp = await asyncio.to_thread(
                lambda: query.order("created_at", desc=True).limit(limit).execute()
            )
            
            summaries = resp.data if resp.data else []
            
            if summaries:
                print(f"[SUMMARY] 📥 Loaded {len(summaries)} summaries for {UserId.format_for_display(user_id)}")
            
            return summaries
            
        except Exception as e:
            print(f"[SUMMARY] ❌ Fetch failed: {e}")
            return []
    
    async def get_session_summary(self, session_id: str) -> Optional[Dict]:
        """Get final summary for a specific session"""
        try:
            resp = await asyncio.to_thread(
                lambda: self.supabase
                    .table("conversation_summaries")
                    .select("*")
                    .eq("session_id", session_id)
                    .eq("is_final", True)
                    .single()
                    .execute()
            )
            
            return resp.data if resp.data else None
            
        except Exception as e:
            print(f"[SUMMARY] ⚠️ Session summary not found: {session_id[:20]}...")
            return None
    
    def format_summaries_for_context(self, summaries: List[Dict]) -> str:
        """
        Format summaries for ChatContext injection.
        
        Args:
            summaries: List of summary dicts from database
            
        Returns:
            Formatted string ready for ChatContext.add_message()
        """
        if not summaries:
            return ""
        
        context_parts = ["## Recent Conversation History\n"]
        
        for summ in summaries:
            # Format date
            created = summ.get("created_at", "")
            date_str = created[:10] if created else "Unknown date"
            
            # Build summary section
            context_parts.append(f"**Session: {date_str}** ({summ.get('turn_count', 0)} turns)")
            context_parts.append(summ.get("summary_text", ""))
            
            # Add topics and tone if available
            topics = summ.get("key_topics", [])
            if topics:
                context_parts.append(f"Topics: {', '.join(topics[:4])}")
            
            tone = summ.get("emotional_tone")
            if tone and tone != "neutral":
                context_parts.append(f"Mood: {tone}")
            
            context_parts.append("")  # Blank line between summaries
        
        return "\n".join(context_parts)

