# Improved generate_reply_with_context method
# Replace lines 348-435 in agent.py with this implementation

async def generate_reply_with_context(self, session, user_text: str = None, greet: bool = False):
    """
    Generate reply with STRONG context emphasis.
    SKIPS RAG - queries memory table directly by categories.
    """
    user_id = get_current_user_id()
    
    # DEBUG: Track user_id during reply generation
    print(f"[DEBUG][USER_ID] generate_reply_with_context - user_id: {user_id[:8] if user_id else 'NONE'}")
    print(f"[DEBUG][CONTEXT] Is greeting: {greet}, User text: {user_text[:50] if user_text else 'N/A'}")
    
    if not user_id:
        print(f"[DEBUG][USER_ID] ⚠️  No user_id available for context building!")
        # No context - use base instructions only
        await session.generate_reply(instructions=self._base_instructions)
        return
    
    try:
        # === FETCH CONTEXT (Skip RAG, use direct queries) ===
        
        # 1. Fetch profile and context in parallel
        profile_task = self.profile_service.get_profile_async(user_id)
        context_task = self.conversation_context_service.get_context(user_id)
        
        profile, context_data = await asyncio.gather(
            profile_task,
            context_task,
            return_exceptions=True
        )
        
        # Extract user name
        user_name = None
        if context_data and not isinstance(context_data, Exception):
            user_name = context_data.get("user_name")
            print(f"[DEBUG][CONTEXT] User name from context: '{user_name}'")
        
        # Handle profile
        if isinstance(profile, Exception) or not profile:
            profile = None
            print(f"[DEBUG][CONTEXT] No profile available")
        else:
            print(f"[DEBUG][CONTEXT] Profile fetched: {len(profile)} chars")
        
        # 2. Query memory table directly by categories (SKIP RAG)
        print(f"[DEBUG][MEMORY] Querying memory table by categories...")
        memories_by_category = {}
        categories = ['FACT', 'GOAL', 'INTEREST', 'EXPERIENCE', 'PREFERENCE', 'RELATIONSHIP', 'PLAN', 'OPINION']
        
        for category in categories:
            try:
                mems = self.memory_service.get_memories_by_category(category, limit=3, user_id=user_id)
                if mems:
                    memories_by_category[category] = [m['value'] for m in mems]
            except Exception as e:
                print(f"[DEBUG][MEMORY] Error fetching {category}: {e}")
        
        print(f"[DEBUG][MEMORY] Categories with data: {list(memories_by_category.keys())}")
        print(f"[DEBUG][MEMORY] Total categories: {len(memories_by_category)}")
        
        # === FORMAT CONTEXT WITH STRONG EMPHASIS ===
        
        # Build categorized memories display
        mem_sections = []
        if memories_by_category:
            for category, values in memories_by_category.items():
                if values:
                    # Show each memory in the category
                    mem_list = "\n".join([f"    • {v[:150]}" for v in values[:3]])
                    mem_sections.append(f"  {category}:\n{mem_list}")
        
        categorized_mems = "\n\n".join(mem_sections) if mem_sections else "  (No memories stored yet)"
        
        # Build PROMINENT context block
        context_block = f"""
╔═══════════════════════════════════════════════════════════════════╗
║       🔴 CRITICAL: YOU MUST USE THIS EXISTING INFORMATION        ║
╚═══════════════════════════════════════════════════════════════════╝

👤 USER'S NAME: {user_name if user_name else "NOT YET KNOWN - ASK NATURALLY"}
   ⚠️  {'ALWAYS address them as: ' + user_name if user_name else 'Must ask for their name in conversation'}

📋 USER PROFILE:
{profile[:800] if profile and len(profile) > 800 else profile if profile else "(Profile not available yet - will be built from conversation)"}

🧠 WHAT YOU ALREADY KNOW ABOUT {'THIS USER' if not user_name else user_name.upper()}:
{categorized_mems}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  MANDATORY RULES FOR USING THIS CONTEXT:
✅ USE their name when greeting or responding (if known)
✅ Reference profile/memories naturally in your response
✅ Show you remember previous conversations
✅ Connect what they say to what you know about them
❌ DO NOT ask for information already listed above
❌ DO NOT ignore this context - it defines who they are!
❌ DO NOT say "I don't know about you" when context exists above

"""
        
        # === GENERATE WITH STRONG INSTRUCTIONS ===
        
        base = self._base_instructions
        
        if greet:
            # GREETING with strong emphasis
            full_instructions = f"""{base}

{context_block}

🎯 YOUR TASK: Generate FIRST GREETING in Urdu

REQUIREMENTS:
1. {'Use their name: ' + user_name if user_name else 'Greet warmly (name not yet known)'}
2. {
'Reference something specific from their profile or memories above' if (profile or memories_by_category) 
else 'Start building rapport - ask about them naturally'
}
3. Keep it warm, natural, and personal
4. Use simple spoken Urdu (2 short sentences)

{'Example: "السلام علیکم ' + user_name + '! کیسی ہیں؟ [mention something from context]"' if user_name 
else 'Example: "السلام علیکم! آج کیسے ہیں آپ؟"'}

Generate greeting NOW incorporating the context shown above:
"""
            print(f"[DEBUG][PROMPT] Greeting prompt length: {len(full_instructions)} chars")
            print(f"[DEBUG][PROMPT] Context block length: {len(context_block)} chars")
            print(f"[DEBUG][PROMPT] User name: '{user_name}'")
            print(f"[DEBUG][PROMPT] Has profile: {profile is not None}")
            print(f"[DEBUG][PROMPT] Memory categories: {list(memories_by_category.keys())}")
            
            await session.generate_reply(instructions=full_instructions)
            
        else:
            # REGULAR RESPONSE with strong context
            full_instructions = f"""{base}

{context_block}

🎯 YOUR TASK: Respond to user's message in Urdu

User said: "{user_text}"

REQUIREMENTS:
1. {'Address them by name: ' + user_name if user_name else 'Respond warmly'}
2. Consider their profile and memories when responding
3. Reference relevant context naturally if applicable
4. Connect their message to what you know about them
5. Respond in natural spoken Urdu (2-3 short sentences)

Generate response NOW using the context shown above:
"""
            print(f"[DEBUG][PROMPT] Response prompt length: {len(full_instructions)} chars")
            print(f"[DEBUG][PROMPT] User text: '{user_text[:100]}'")
            
            await session.generate_reply(instructions=full_instructions)
        
        logging.info(f"[CONTEXT] Generated reply with {len(context_block)} chars of context")
        
    except Exception as e:
        logging.error(f"[CONTEXT] Error in generate_reply_with_context: {e}")
        print(f"[DEBUG][CONTEXT] ❌ Exception: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"[DEBUG][CONTEXT] Traceback: {traceback.format_exc()}")
        # Fallback to base instructions
        await session.generate_reply(instructions=self._base_instructions)
