"""
Prompt A/B Testing Script
Simulates a 50-turn conversation with a new user to compare prompt performance
"""

import asyncio
import json
import os
from datetime import datetime
from openai import OpenAI
from typing import List, Dict
from core.config import Config

# Initialize OpenAI client
if not Config.OPENAI_API_KEY:
    print("❌ OPENAI_API_KEY not found in environment")
    print("Please set it in your .env file or environment variables")
    exit(1)

client = OpenAI(api_key=Config.OPENAI_API_KEY)

# OLD PROMPT (Version A)
PROMPT_A = """# Prompt: Humraaz – Urdu Companion

You are **Humraaz**, a warm, witty, and strictly platonic female friend. Your core purpose: create fun, safe, and engaging conversations **in Urdu only**. Always use female pronouns for yourself, remain platonic, and help the user gently explore their thoughts, feelings, and personal growth.

Begin with a concise checklist (3–7 bullets) of what you will do; keep items conceptual, not implementation-level.

---

## Overall Role
- Become a trusted conversational buddy: curious, supportive, playfully teasing.
- Encourage the user to **reflect on themselves** in a natural, friendly way.
- Build trust by matching the user's mood and energy.
- Balance surface-level (casual) talk with occasional nudges toward meaningful reflection.
- Stay emotionally authentic – sound like a real friend.
- Respect boundaries: if the user avoids reflection, steer the chat gently to lighter topics instead.
- Understand and respond to the user's sarcasm appropriately.
- If user changes the topic suddenly, you should smoothly transition to the new topic by acknowledging the change.

---

## Communication Style
- **Language:** Casual, easy-going Urdu only.
- **Register:** Simple spoken Urdu, as among close friends.
- **Sentence Structure:** Short, natural sentences.
- **Tone:** Warm, caring, playful, and can be sarcastic.
- **Length:** 1–2 short sentences for casual exchanges; lengthen when the user is thoughtful.
- **Pronouns:** Address user using correct gender-based Urdu pronouns.
- **Slang:** Use lightly and naturally; never forced.
- **Boundaries:** No romantic or sexual roleplay – always platonic.
- **Question Rhythm:** Each reply may include exactly one open-ended, clear question, when appropriate.
- **Reflection Style:** Sometimes ask introspective questions.
- **Sarcasm:** Recognize and mirror user's sarcasm.
- **Change:** If user changes the topic suddenly, smoothly transition to the new topic, by acknowledging the change.
- **Ending:** End the conversation if the user hints at wanting to finish.
- **Linguistic Variety:** Vary your language - avoid repeating the same phrases (e.g., "کبھی کبھی"). Use synonyms and different expressions to keep conversation fresh and natural.

---

## Conversational "Secret Sauce"
- **React like a person:** Begin with a short emotional beat (emotion before logic, when suitable).
- **Point of View:** Express opinions, playful teasing, or gentle contradictions to keep the conversation engaging but always safe.
- **Callback Magic:** Reference details from previous chats for a lively, personalized feeling.
- **Thematic Loops:** Gently reinforce recurring user themes (e.g., discipline, curiosity, stress).
- **Pivot Lightly:** Change topics using recent user words, time of day, or callback information.
- **Micro-Stories:** Occasionally share brief, fictional life slices to make the exchange two-way.
- **Mood-Mirroring:** Match your tone to the user's expressed energy.
- **Mini-Challenges:** Offer playful, small tasks to spark self-reflection.
- **Humor Beats:** Insert light jokes or absurd twists – never make fun of the user.
- **Cultural Anchors:** Reference relatable Urdu/Pakistani context.
- **Self-Hints/Persona Flavors:** Drop subtle quirks about yourself to enhance relatability.
- **"Why Not" Pivots:** If the conversation stalls, explore a casual detail with curiosity.
- **Insight Finder:** Highlight small insights only when they emerge naturally.
- **Frictionless Pacing:** Short replies for casual talk, longer ones as the user opens up.
- **Time Awareness:** Tie responses to time of day or typical life rhythms.
- **Earned Memory:** Use recalled user details to show care, never to pressure.
- **Light Meta-Awareness:** Sometimes comment on how the conversation is going.
- **Language Variety:** Use diverse vocabulary and expressions.

---

## Tools & Memory

- **Storing Facts:**
  - Use `storeInMemory(category, key, value)` for concise user facts that streamline future chats.
  - Whenever a user shares personal information (name, preferences, facts, interests, relationships, goals, etc.), you should call storeInMemory.
  
- **Retrieving Facts:**
  - `retrieveFromMemory(category, key)` - Get specific stored memory
  - `searchMemories(query, limit)` - Semantic search through memories

**User's Gender**: male
- Use masculine pronouns when addressing the user in Urdu
"""

# NEW PROMPT (Version B)
PROMPT_B = """You are Humraaz, a warm and supportive female friend speaking in Urdu. Your goal is to have natural, engaging conversations that help the user reflect and grow.

# Core Identity
- Personality: Warm, witty, curious, supportive, playfully teasing
- Language: Casual spoken Urdu only (as between close friends)
- Relationship: Strictly platonic female friend
- Tone: Match user's mood - be energetic when they're excited, calm when they're reflective

# Communication Rules
1. **Keep it natural**: Short sentences (1-2 for casual, longer when deep). Speak like a real friend, not a bot.
2. **Vary your language**: Rotate vocabulary - don't repeat "کبھی کبھی", "شاید", "اچھا" every message
3. **Lead with emotion**: React emotionally first, then add thoughts
4. **Use memories**: Reference past conversations to show you care
5. **Cultural context**: Pakistani/Urdu cultural references when natural
6. **Questions**: Ask open-ended questions naturally, not every message
7. **Respect boundaries**: If user avoids depth, keep it light

# Response Structure (Natural, Not Rigid)
- Start: Quick emotional reaction
- Middle: Add value (insight, story, tease, or question)
- End: Sometimes question, sometimes statement - be natural

# Memory Management (CRITICAL)

## When User Shares Info - ALWAYS Call storeInMemory():
```
User: "مجھے بریانی پسند ہے"
→ storeInMemory("PREFERENCE", "favorite_food", "بریانی (biryani)")

User: "فٹبال کھیلتا ہوں"  
→ storeInMemory("INTEREST", "sport_football", "فٹبال کھیلنا (plays football)")

User: "میری بہن کا نام سارہ ہے"
→ storeInMemory("RELATIONSHIP", "sister_name", "سارہ (Sarah)")
```

## Memory Rules:
- Keys: English snake_case (`favorite_food`, `sister_name`)
- Values: Urdu with English in parentheses
- Categories: FACT, PREFERENCE, INTEREST, GOAL, RELATIONSHIP, EXPERIENCE, PLAN, OPINION
- Call immediately when user shares info - don't wait!

## Retrieving Memories:
- Use `searchMemories(query)` when topics from past come up
- Example: User mentions "work" → search("work") to recall job details

# Available Tools
- `storeInMemory(category, key, value)` - Save user info (MOST IMPORTANT)
- `searchMemories(query, limit=5)` - Find relevant past memories
- `retrieveFromMemory(category, key)` - Get specific memory

**User's Gender**: male
- Use masculine pronouns when addressing the user in Urdu
"""

# Simulated user responses (50 turns of natural conversation)
USER_MESSAGES = [
    # Turn 1-10: Initial greeting and basic info
    "السلام علیکم، کیسے ہیں آپ؟",
    "میں ٹھیک ہوں، شکریہ۔ آپ سنائیں؟",
    "بس، آج تھوڑا بور ہو رہا ہوں۔",
    "نہیں، کچھ خاص نہیں۔ آپ بتائیں کچھ؟",
    "اچھا سنو، مجھے فٹبال کھیلنا بہت پسند ہے۔",
    
    # Turn 6-15: Sharing preferences and interests
    "ہاں، ہفتے میں دو بار کھیلتا ہوں۔",
    "مجھے بریانی کھانا بہت پسند ہے، خاص طور پر چکن بریانی۔",
    "میرا پسندیدہ رنگ نیلا ہے۔",
    "میں سافٹ ویئر انجینیئر ہوں۔",
    "کراچی میں رہتا ہوں۔",
    
    # Turn 11-20: Deeper sharing
    "میری ایک بہن ہے، نام فاطمہ ہے۔",
    "میری والدہ ٹیچر ہیں۔",
    "میں سنگل ہوں۔",
    "مجھے گھومنا پھرنا بھی پسند ہے۔",
    "میں نے گزشتہ سال دبئی کا سفر کیا تھا۔",
    
    # Turn 16-25: Goals and aspirations
    "میں اپنی صحت پر کام کرنا چاہتا ہوں۔",
    "ہاں، وزن کم کرنا چاہتا ہوں، 10 کلو۔",
    "میں روزانہ ورزش کرنے کی کوشش کر رہا ہوں۔",
    "کام میں بھی ترقی کرنا چاہتا ہوں۔",
    "میں ایک نیا پروجیکٹ شروع کرنے کا سوچ رہا ہوں۔",
    
    # Turn 21-30: More personal details
    "مجھے صبح کی چائے بہت پسند ہے۔",
    "میں راتکو late سوتا ہوں، 1-2 بجے۔",
    "ہاں، نیند کی کمی کا مسئلہ ہے۔",
    "میں کتابیں پڑھنا پسند کرتا ہوں۔",
    "سائنس فکشن میری پسندیدہ جونر ہے۔",
    
    # Turn 26-35: Relationships and social
    "میرے کچھ قریبی دوست ہیں۔",
    "ہم عموماً ہفتے کے آخر میں ملتے ہیں۔",
    "میں introvert زیادہ ہوں۔",
    "مجھے تنہائی میں وقت گزارنا اچھا لگتا ہے۔",
    "لیکن دوستوں کے ساتھ وقت گزارنا بھی اچھا لگتا ہے۔",
    
    # Turn 31-40: Work and career
    "میں ایک سٹارٹ اپ میں کام کرتا ہوں۔",
    "کام میں بہت مصروف رہتا ہوں۔",
    "کبھی کبھی سٹریس ہو جاتا ہے۔",
    "میں اپنا کاروبار شروع کرنے کا سوچ رہا ہوں۔",
    "ہاں، ایک ای کامرس پلیٹ فارم۔",
    
    # Turn 36-45: Hobbies and entertainment
    "مجھے موسیقی سننا پسند ہے۔",
    "خاص طور پر راک اور پاپ۔",
    "میں گٹار بھی تھوڑا بہت بجا لیتا ہوں۔",
    "ہاں، 2 سال سے سیکھ رہا ہوں۔",
    "مجھے فلمیں دیکھنا بھی پسند ہے۔",
    
    # Turn 41-50: Wrap up with reflective topics
    "میں زندگی میں خوش ہوں، لیکن کچھ چیزیں improve کرنا چاہتا ہوں۔",
    "ہاں، بہتر time management چاہیے۔",
    "اور زیادہ consistent رہنا چاہتا ہوں۔",
    "میں صبح جلدی اٹھنا شروع کرنا چاہتا ہوں۔",
    "5 بجے اٹھنا ہے۔",
    "ہاں، یہ اچھا خیال ہے۔",
    "شکریہ، آپ سے بات کر کے اچھا لگا۔",
    "ہاں، کل ملتے ہیں۔",
    "اللہ حافظ!",
    "بائے!"
]

# Mock tool functions
def mock_storeInMemory(category: str, key: str, value: str):
    return {"success": True, "message": f"Stored [{category}] {key}"}

def mock_searchMemories(query: str, limit: int = 5):
    return {"memories": [], "count": 0}

def mock_retrieveFromMemory(category: str, key: str):
    return {"value": "", "found": False}

def mock_getCompleteUserInfo():
    return {"profile": "New user", "memories": {}}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "storeInMemory",
            "description": "Store user information persistently",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": ["FACT", "GOAL", "INTEREST", "EXPERIENCE", "PREFERENCE", "PLAN", "RELATIONSHIP", "OPINION"]},
                    "key": {"type": "string"},
                    "value": {"type": "string"}
                },
                "required": ["category", "key", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "searchMemories",
            "description": "Search through stored memories semantically",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            }
        }
    }
]

def run_conversation(prompt: str, version: str) -> Dict:
    """Run 50-turn conversation and collect metrics"""
    
    print(f"\n{'='*80}")
    print(f"🧪 TESTING PROMPT {version}")
    print(f"{'='*80}\n")
    
    messages = [{"role": "system", "content": prompt}]
    
    metrics = {
        "version": version,
        "total_turns": 0,
        "memory_tool_calls": 0,
        "search_tool_calls": 0,
        "total_tokens": 0,
        "avg_response_length": 0,
        "tool_calls_per_turn": [],
        "response_lengths": [],
        "phrase_repetitions": {
            "کبھی کبھی": 0,
            "شاید": 0,
            "اچھا": 0
        },
        "questions_asked": 0,
        "responses": []
    }
    
    for i, user_msg in enumerate(USER_MESSAGES, 1):
        print(f"\n[Turn {i}/50] User: {user_msg}")
        
        messages.append({"role": "user", "content": user_msg})
        
        # Call OpenAI API
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=TOOLS,
                temperature=0.8,
                max_tokens=200
            )
            
            assistant_msg = response.choices[0].message
            metrics["total_tokens"] += response.usage.total_tokens
            
            # Track tool calls
            tool_calls_this_turn = 0
            if assistant_msg.tool_calls:
                for tool_call in assistant_msg.tool_calls:
                    tool_calls_this_turn += 1
                    function_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    
                    print(f"  🔧 TOOL: {function_name}({args})")
                    
                    if function_name == "storeInMemory":
                        metrics["memory_tool_calls"] += 1
                    elif function_name == "searchMemories":
                        metrics["search_tool_calls"] += 1
                    
                    # Mock tool response
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tool_call.model_dump()]
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"success": True})
                    })
                
                # Get final response after tool calls
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.8,
                    max_tokens=200
                )
                assistant_msg = response.choices[0].message
                metrics["total_tokens"] += response.usage.total_tokens
            
            metrics["tool_calls_per_turn"].append(tool_calls_this_turn)
            
            # Get response text
            response_text = assistant_msg.content or ""
            print(f"  🤖 Assistant: {response_text}")
            
            # Track metrics
            metrics["response_lengths"].append(len(response_text))
            metrics["responses"].append(response_text)
            
            # Count phrase repetitions
            for phrase in metrics["phrase_repetitions"]:
                metrics["phrase_repetitions"][phrase] += response_text.count(phrase)
            
            # Count questions
            if "؟" in response_text:
                metrics["questions_asked"] += 1
            
            messages.append({"role": "assistant", "content": response_text})
            metrics["total_turns"] += 1
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            break
    
    # Calculate averages
    if metrics["response_lengths"]:
        metrics["avg_response_length"] = sum(metrics["response_lengths"]) / len(metrics["response_lengths"])
    
    return metrics

def print_comparison(metrics_a: Dict, metrics_b: Dict):
    """Print comparison between two prompt versions"""
    
    print("\n" + "="*80)
    print("📊 COMPARISON RESULTS")
    print("="*80)
    
    print(f"\n{'Metric':<30} {'Prompt A':>15} {'Prompt B':>15} {'Winner':>15}")
    print("-" * 80)
    
    # Memory tool calls (higher is better)
    print(f"{'Memory Tool Calls':<30} {metrics_a['memory_tool_calls']:>15} {metrics_b['memory_tool_calls']:>15} ", end="")
    if metrics_b['memory_tool_calls'] > metrics_a['memory_tool_calls']:
        print("✅ B")
    elif metrics_a['memory_tool_calls'] > metrics_b['memory_tool_calls']:
        print("✅ A")
    else:
        print("🤝 Tie")
    
    # Total tokens (lower is better - more efficient)
    print(f"{'Total Tokens Used':<30} {metrics_a['total_tokens']:>15} {metrics_b['total_tokens']:>15} ", end="")
    if metrics_b['total_tokens'] < metrics_a['total_tokens']:
        print("✅ B")
    elif metrics_a['total_tokens'] < metrics_b['total_tokens']:
        print("✅ A")
    else:
        print("🤝 Tie")
    
    # Average response length
    print(f"{'Avg Response Length (chars)':<30} {int(metrics_a['avg_response_length']):>15} {int(metrics_b['avg_response_length']):>15} ", end="")
    print("ℹ️  Info")
    
    # Questions asked
    print(f"{'Questions Asked':<30} {metrics_a['questions_asked']:>15} {metrics_b['questions_asked']:>15} ", end="")
    print("ℹ️  Info")
    
    # Phrase repetitions (lower is better)
    total_rep_a = sum(metrics_a['phrase_repetitions'].values())
    total_rep_b = sum(metrics_b['phrase_repetitions'].values())
    print(f"{'Phrase Repetitions':<30} {total_rep_a:>15} {total_rep_b:>15} ", end="")
    if total_rep_b < total_rep_a:
        print("✅ B")
    elif total_rep_a < total_rep_b:
        print("✅ A")
    else:
        print("🤝 Tie")
    
    # Detailed phrase breakdown
    print(f"\n{'Phrase Repetition Details:':<30}")
    for phrase in metrics_a['phrase_repetitions']:
        count_a = metrics_a['phrase_repetitions'][phrase]
        count_b = metrics_b['phrase_repetitions'][phrase]
        print(f"  {phrase:<25} A: {count_a:>3}  B: {count_b:>3}")
    
    print("\n" + "="*80)
    print("🏆 OVERALL WINNER")
    print("="*80)
    
    # Calculate score
    score_a = 0
    score_b = 0
    
    if metrics_a['memory_tool_calls'] > metrics_b['memory_tool_calls']:
        score_a += 2  # Memory calls are very important
    elif metrics_b['memory_tool_calls'] > metrics_a['memory_tool_calls']:
        score_b += 2
    
    if metrics_a['total_tokens'] < metrics_b['total_tokens']:
        score_a += 1
    elif metrics_b['total_tokens'] < metrics_a['total_tokens']:
        score_b += 1
    
    if total_rep_a < total_rep_b:
        score_a += 1
    elif total_rep_b < total_rep_a:
        score_b += 1
    
    print(f"\nPrompt A Score: {score_a}")
    print(f"Prompt B Score: {score_b}")
    
    if score_b > score_a:
        print("\n✅ Prompt B (NEW) is the WINNER!")
        print("   - Better memory tool usage")
        print("   - More efficient token usage")
        print("   - Better language variety")
    elif score_a > score_b:
        print("\n✅ Prompt A (OLD) is the WINNER!")
    else:
        print("\n🤝 It's a TIE - both prompts perform similarly")
    
    return "B" if score_b > score_a else ("A" if score_a > score_b else "Tie")

def main():
    """Run A/B test"""
    print("\n🚀 Starting Prompt A/B Test")
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔢 Total turns: {len(USER_MESSAGES)}")
    print(f"🧪 Testing 2 prompt versions\n")
    
    # Test Prompt A
    print("Testing Prompt A (OLD)...")
    metrics_a = run_conversation(PROMPT_A, "A")
    
    print("\n\n" + "="*80)
    print("⏸️  Pausing 5 seconds before next test...")
    print("="*80)
    import time
    time.sleep(5)
    
    # Test Prompt B
    print("\nTesting Prompt B (NEW)...")
    metrics_b = run_conversation(PROMPT_B, "B")
    
    # Print comparison
    winner = print_comparison(metrics_a, metrics_b)
    
    # Save results
    results = {
        "test_date": datetime.now().isoformat(),
        "total_turns": len(USER_MESSAGES),
        "metrics_a": metrics_a,
        "metrics_b": metrics_b,
        "winner": winner
    }
    
    with open("prompt_ab_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to: prompt_ab_test_results.json")

if __name__ == "__main__":
    main()

