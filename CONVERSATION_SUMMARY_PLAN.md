# Conversation Summary System - Implementation Plan

## 🎯 Goal
Create a progressive summarization system that:
- Updates as conversation progresses (every 5-10 turns)
- Stores summaries in database for future sessions
- Leverages existing RAG, memory, and profile data
- Provides rich context for next conversation

---

## 📊 Architecture Overview

### Data Flow:
```
Conversation Turns (User + Assistant)
    ↓
RAG System (already tracking conversation context)
    ↓
Summary Generator (LLM-based, incremental)
    ↓
conversation_summaries table (DB)
    ↓
Next Session: Load summary + recent memories
```

---

## 🗄️ Database Schema

### ✅ Use Existing `conversation_state` Table

**Good news!** The required columns already exist in `conversation_state`:

```sql
-- Already exists from add_conversation_state_context_columns.sql migration:
ALTER TABLE conversation_state
    ADD COLUMN IF NOT EXISTS last_summary TEXT,
    ADD COLUMN IF NOT EXISTS last_topics JSONB DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS last_user_message TEXT,
    ADD COLUMN IF NOT EXISTS last_assistant_message TEXT,
    ADD COLUMN IF NOT EXISTS last_conversation_at TIMESTAMPTZ;
```

**Benefits of using existing table:**
- ✅ No new table needed
- ✅ Summary stored with stage/trust_score
- ✅ Single query to get state + summary
- ✅ Simpler architecture
- ✅ No migration required

---

## 🔧 Implementation Strategy

### Approach: **Incremental Summarization with RAG**

**Why this approach:**
- ✅ Leverages existing RAG conversation context
- ✅ Progressive summaries prevent context loss
- ✅ Can recover from crashes/disconnections
- ✅ Reduces final summary complexity

### When to Summarize:

1. **Every 10 turns**: Generate incremental summary
2. **On disconnect**: Generate final summary
3. **On significant topic shift**: Optional mini-summary

---

## 💻 Code Implementation

### 1. Create Conversation Summary Service

**File: `services/conversation_summary_service.py`**

```python
import asyncio
from typing import Optional, List, Dict
from openai import OpenAI
from core.config import Config
from core.validators import get_current_user_id

class ConversationSummaryService:
    """
    Manages progressive conversation summarization using existing RAG data.
    """
    
    def __init__(self, supabase, openai_client: Optional[OpenAI] = None):
        self.supabase = supabase
        self.openai = openai_client or OpenAI(api_key=Config.OPENAI_API_KEY)
        self.current_session_id = None
        self.last_summary_id = None
        self.turns_since_last_summary = 0
    
    def set_session(self, session_id: str):
        """Set current session ID"""
        self.current_session_id = session_id
        self.turns_since_last_summary = 0
    
    async def generate_incremental_summary(
        self, 
        conversation_turns: List[tuple],  # [(user_msg, asst_msg), ...]
        existing_summary: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict:
        """
        Generate summary using LLM, optionally building on previous summary.
        
        Args:
            conversation_turns: Recent conversation turns to summarize
            existing_summary: Previous summary to build upon (if any)
            user_id: User ID for attribution
            
        Returns:
            Dict with summary_text, key_topics, emotional_tone
        """
        uid = user_id or get_current_user_id()
        
        # Build conversation context
        conversation_text = self._format_turns_for_summary(conversation_turns)
        
        # Create summary prompt
        prompt = self._build_summary_prompt(conversation_text, existing_summary)
        
        # Call LLM
        response = await asyncio.to_thread(
            self.openai.chat.completions.create,
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": conversation_text}
            ],
            temperature=0.3,  # Lower temp for consistent summaries
            max_tokens=300
        )
        
        summary_data = self._parse_summary_response(response.choices[0].message.content)
        
        print(f"[SUMMARY] ✅ Generated: {len(summary_data['summary_text'])} chars")
        print(f"[SUMMARY]    Topics: {', '.join(summary_data['key_topics'][:3])}")
        
        return summary_data
    
    def _format_turns_for_summary(self, turns: List[tuple]) -> str:
        """Format conversation turns for summarization"""
        lines = []
        for i, (user_msg, asst_msg) in enumerate(turns, 1):
            lines.append(f"Turn {i}:")
            lines.append(f"User: {user_msg}")
            lines.append(f"Assistant: {asst_msg}")
            lines.append("")
        return "\n".join(lines)
    
    def _build_summary_prompt(self, conversation: str, previous_summary: Optional[str]) -> str:
        """Build prompt for summary generation"""
        if previous_summary:
            return f"""Summarize this conversation segment and UPDATE the previous summary.

Previous Summary:
{previous_summary}

Focus on:
1. Key topics discussed (2-3 main themes)
2. Important facts shared by user
3. Overall emotional tone
4. Progress or changes from previous summary

Keep summary concise (100-150 words). Use Urdu where natural."""
        else:
            return """Summarize this conversation focusing on:
1. Key topics discussed (2-3 main themes)
2. Important facts the user shared
3. Overall emotional tone (happy, stressed, reflective, etc.)

Keep concise (100-150 words). Use Urdu where natural.

Format:
Summary: [concise overview]
Topics: [topic1, topic2, topic3]
Tone: [emotional tone]
Facts: [important facts]"""
    
    def _parse_summary_response(self, response: str) -> Dict:
        """Parse LLM summary response into structured format"""
        lines = response.strip().split('\n')
        
        result = {
            "summary_text": "",
            "key_topics": [],
            "important_facts": [],
            "emotional_tone": "neutral"
        }
        
        current_section = None
        for line in lines:
            line = line.strip()
            if line.startswith("Summary:"):
                current_section = "summary"
                result["summary_text"] = line.replace("Summary:", "").strip()
            elif line.startswith("Topics:"):
                topics_text = line.replace("Topics:", "").strip()
                result["key_topics"] = [t.strip() for t in topics_text.split(",")]
            elif line.startswith("Tone:"):
                result["emotional_tone"] = line.replace("Tone:", "").strip()
            elif line.startswith("Facts:"):
                facts_text = line.replace("Facts:", "").strip()
                result["important_facts"] = [f.strip() for f in facts_text.split(",")]
            elif current_section == "summary" and line:
                result["summary_text"] += " " + line
        
        return result
    
    async def save_summary(
        self,
        summary_data: Dict,
        turn_count: int,
        is_final: bool = False,
        user_id: Optional[str] = None
    ) -> bool:
        """Save summary to database"""
        uid = user_id or get_current_user_id()
        
        if not uid or not self.current_session_id:
            print("[SUMMARY] ⚠️ Missing user_id or session_id")
            return False
        
        try:
            data = {
                "user_id": uid,
                "session_id": self.current_session_id,
                "summary_text": summary_data["summary_text"],
                "key_topics": summary_data["key_topics"],
                "important_facts": summary_data.get("important_facts", []),
                "emotional_tone": summary_data.get("emotional_tone", "neutral"),
                "turn_count": turn_count,
                "is_final": is_final,
                "previous_summary_id": self.last_summary_id,
                "end_time": "NOW()" if is_final else None
            }
            
            # Save to DB
            resp = await asyncio.to_thread(
                lambda: self.supabase.table("conversation_summaries").insert(data).execute()
            )
            
            if resp.data:
                self.last_summary_id = resp.data[0]["id"]
                print(f"[SUMMARY] ✅ Saved to DB (ID: {self.last_summary_id[:8]}...)")
                return True
            
            return False
            
        except Exception as e:
            print(f"[SUMMARY] ❌ Save failed: {e}")
            return False
    
    async def get_recent_summaries(
        self,
        user_id: str,
        limit: int = 3
    ) -> List[Dict]:
        """Get recent conversation summaries for a user"""
        try:
            resp = await asyncio.to_thread(
                lambda: self.supabase
                    .table("conversation_summaries")
                    .select("*")
                    .eq("user_id", user_id)
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute()
            )
            
            return resp.data if resp.data else []
            
        except Exception as e:
            print(f"[SUMMARY] ❌ Fetch failed: {e}")
            return []
```

### 2. Integrate into Agent

**Add to `agent.py`:**

```python
class Assistant(Agent):
    def __init__(self, ...):
        # ... existing code ...
        
        # Add summary service
        self.summary_service = None  # Will be set in entrypoint
        self._turn_counter = 0
        self.SUMMARY_INTERVAL = 10  # Summarize every 10 turns
    
    async def on_user_turn_completed(self, turn_ctx, new_message):
        # ... existing code ...
        
        # Increment turn counter
        self._turn_counter += 1
        
        # Check if we should generate incremental summary
        if self._turn_counter % self.SUMMARY_INTERVAL == 0:
            asyncio.create_task(self._generate_incremental_summary())
    
    async def _generate_incremental_summary(self):
        """Generate and save incremental summary every N turns"""
        try:
            if not self.summary_service or not self.rag_service:
                return
            
            # Get recent conversation from RAG context
            conversation_context = self.rag_service.get_conversation_context()
            
            # Or use tracked history
            recent_turns = self._conversation_history[-10:]  # Last 10 turns
            
            if not recent_turns:
                return
            
            print(f"[SUMMARY] 📝 Generating incremental summary (Turn {self._turn_counter})")
            
            # Generate summary
            summary_data = await self.summary_service.generate_incremental_summary(
                conversation_turns=recent_turns,
                existing_summary=None  # Could load previous summary here
            )
            
            # Save to DB
            await self.summary_service.save_summary(
                summary_data=summary_data,
                turn_count=self._turn_counter,
                is_final=False
            )
            
        except Exception as e:
            print(f"[SUMMARY] ⚠️ Incremental summary failed: {e}")
    
    async def generate_final_summary(self):
        """Generate final summary when session ends"""
        try:
            if not self.summary_service:
                return
            
            print("[SUMMARY] 📋 Generating FINAL session summary...")
            
            # Get all conversation from history
            all_turns = self._conversation_history
            
            if not all_turns:
                print("[SUMMARY] ℹ️ No conversation to summarize")
                return
            
            # Generate comprehensive summary
            summary_data = await self.summary_service.generate_incremental_summary(
                conversation_turns=all_turns,
                existing_summary=None
            )
            
            # Save as final
            success = await self.summary_service.save_summary(
                summary_data=summary_data,
                turn_count=len(all_turns),
                is_final=True
            )
            
            if success:
                print(f"[SUMMARY] ✅ Final summary saved ({len(all_turns)} turns)")
            
        except Exception as e:
            print(f"[SUMMARY] ❌ Final summary failed: {e}")
```

### 3. Hook into Session Lifecycle

**In `entrypoint()` function:**

```python
async def entrypoint(ctx: JobContext):
    # ... existing setup ...
    
    # Initialize summary service
    summary_service = ConversationSummaryService(supabase)
    summary_service.set_session(ctx.room.name)  # Use room name as session_id
    assistant.summary_service = summary_service
    
    print("[SUMMARY] ✓ Summary service initialized")
    
    # ... conversation happens ...
    
    # On disconnect (in cleanup):
    try:
        await disconnect_event.wait()
        print("[ENTRYPOINT] ✓ Session completed - generating final summary...")
        
        # Generate final summary before cleanup
        await assistant.generate_final_summary()
        
    except Exception as e:
        print(f"[ENTRYPOINT] ⚠️ Cleanup warning: {e}")
```

---

## 🚀 Usage in Future Sessions

### Loading Summary on Next Session:

```python
# In entrypoint, before creating ChatContext:
if user_id:
    # Get recent summaries
    summary_service = ConversationSummaryService(supabase)
    recent_summaries = await summary_service.get_recent_summaries(user_id, limit=2)
    
    # Add to initial context
    if recent_summaries:
        summary_context = "## Recent Conversation History:\n\n"
        for summ in recent_summaries:
            date = summ['created_at'][:10]
            summary_context += f"**Session {date}** ({summ['turn_count']} turns):\n"
            summary_context += f"{summ['summary_text']}\n\n"
            summary_context += f"Topics: {', '.join(summ['key_topics'])}\n"
            summary_context += f"Mood: {summ['emotional_tone']}\n\n"
        
        initial_ctx.add_message(
            role="assistant",
            content=summary_context
        )
        
        print(f"[CONTEXT] ✅ Loaded {len(recent_summaries)} conversation summaries")
```

---

## 📈 Leveraging Existing Infrastructure

### Option 1: Use RAG Conversation Context (RECOMMENDED)
**Pros:**
- ✅ Already tracking conversation in `rag_service.conversation_context`
- ✅ No duplication of data
- ✅ Includes recency and relevance info

```python
async def _generate_summary_from_rag(self):
    """Use RAG's conversation context for summarization"""
    
    # Get conversation from RAG
    rag_system = self.rag_service.get_rag_system()
    conversation_context = self.rag_service.conversation_context
    
    # conversation_context is a list of recent user messages
    # We need both user and assistant, so use _conversation_history instead
    
    recent_turns = self._conversation_history[-10:]
    
    # Generate summary
    summary = await self.summary_service.generate_incremental_summary(
        conversation_turns=recent_turns
    )
    
    return summary
```

### Option 2: Query from conversation_turns table
**If you have conversation logging:**

```python
# Get from database
turns = await self.supabase
    .table("conversation_turns")
    .select("user_message, assistant_message")
    .eq("user_id", user_id)
    .eq("session_id", session_id)
    .order("created_at", desc=False)
    .execute()
```

### Option 3: Use Memory + Profile (Hybrid)
**For ultra-concise summaries:**

```python
async def generate_session_snapshot(self, user_id: str):
    """Quick session snapshot using existing data"""
    
    # Get all data in parallel
    profile = await self.profile_service.get_profile_async(user_id)
    state = await self.conversation_state_service.get_state(user_id)
    recent_memories = self.memory_service.get_recent_memories(user_id, limit=10)
    
    # Build snapshot
    snapshot = f"""
    Session Snapshot:
    - Profile: {profile[:100]}...
    - Stage: {state['stage']}, Trust: {state['trust_score']}
    - Recent memories: {len(recent_memories)} new items
    - Topics: [extract from memories]
    """
    
    return snapshot
```

---

## ⚡ Optimization: Smart Summarization

### Only Summarize When Needed:

```python
def should_generate_summary(self) -> bool:
    """Decide if summary is needed"""
    
    # Always summarize if:
    # 1. Every 10 turns
    if self._turn_counter % 10 == 0:
        return True
    
    # 2. Significant topic shift detected
    # (can use RAG to detect topic clustering)
    
    # 3. User shared important info (>5 memory saves in last 5 turns)
    
    # 4. Session ending
    
    return False
```

---

## 📊 Example Output

### Incremental Summary (After 10 turns):
```
Summary: User Osama discussed his passion for football and love for 
biryani. He works as a software engineer in Karachi and lives with his 
family. He's working on health goals and wants to lose 10kg. Conversation 
was casual and friendly with good engagement.

Topics: sports, food_preferences, career, health_goals
Tone: positive, engaged
Facts: plays_football_weekly, favorite_food_chicken_biryani, 
       weight_loss_goal_10kg
Turn Count: 10
```

### Final Summary (Session end):
```
Summary: Comprehensive conversation covering work-life balance, health goals, 
and personal interests. Osama is motivated to improve fitness while managing 
career at a startup. Strong rapport built with playful banter about food 
preferences and sports. Trust level increased from ORIENTATION to ENGAGEMENT.

Topics: career_development, health_fitness, food, sports, family
Tone: reflective, motivated, playful
Turn Count: 45
Stage Progression: ORIENTATION → ENGAGEMENT
```

---

## 🎯 Benefits

1. **Context Persistence**: Don't lose conversation context between sessions
2. **Faster Context Loading**: Summary < full conversation replay
3. **Better Continuity**: "Last time we talked about your fitness goals..."
4. **Analytics**: Track conversation patterns over time
5. **Recovery**: Can resume after crashes/disconnections
6. **Progressive**: Build knowledge incrementally

---

## 📝 Implementation Checklist

- [ ] Create `conversation_summaries` table in Supabase
- [ ] Create `ConversationSummaryService` class
- [ ] Add summary service to Agent initialization
- [ ] Hook into `on_user_turn_completed` for turn counting
- [ ] Add incremental summary trigger (every 10 turns)
- [ ] Add final summary on disconnect
- [ ] Load summaries in next session's initial context
- [ ] Add RLS policies for summaries table
- [ ] Add caching for recent summaries (Redis)
- [ ] Test with sample conversations

---

## 🔬 Testing Plan

1. **Unit Test**: Summary generation with mock conversations
2. **Integration Test**: Full session with summary saving
3. **Load Test**: Verify summaries load correctly in next session
4. **Performance Test**: Measure impact on latency (should be <100ms)

---

## 💡 Future Enhancements

1. **Topic Clustering**: Use RAG embeddings to detect topic shifts
2. **Sentiment Tracking**: Track emotional journey across sessions
3. **Highlight Extraction**: Pull out key quotes/moments
4. **Multi-session Summaries**: Weekly/monthly rollups
5. **Smart Context**: Only load relevant summaries based on current topic

---

## 📊 Estimated Impact

- **Token savings**: 80% reduction vs replaying full conversation
- **Load time**: <200ms to load 3 summaries vs 2s+ for full history
- **Context quality**: High-level continuity without noise
- **Storage**: ~200 bytes per summary vs ~2KB per full conversation

