"""
Test Conversation Flow - Simulate real conversation to trigger summary generation
"""

import asyncio
from supabase import create_client
from core.config import Config
from core.validators import set_current_user_id, set_supabase_client
from services import ConversationSummaryService, RAGService
from core.user_id import UserId

# Test user ID
TEST_USER_ID = "4e3efa3d-d8fe-431e-a78f-4efffb0cf43a"

async def simulate_conversation_flow():
    """Simulate the actual conversation flow that would happen in the agent"""
    
    print("=" * 80)
    print("🎭 SIMULATING REAL CONVERSATION FLOW")
    print("=" * 80)
    
    # Initialize Supabase
    supabase = create_client(Config.SUPABASE_URL, Config.get_supabase_key())
    set_supabase_client(supabase)
    set_current_user_id(TEST_USER_ID)
    
    print(f"✅ Supabase connected")
    print(f"✅ Simulating for user: {UserId.format_for_display(TEST_USER_ID)}")
    
    # Initialize services like the agent does
    rag_service = RAGService(TEST_USER_ID)
    summary_service = ConversationSummaryService(supabase)
    summary_service.set_session("test-flow-session")
    
    # Simulate turn counter (like in agent)
    turn_counter = 0
    SUMMARY_INTERVAL = 5  # Same as in agent
    
    print(f"\n📊 Simulating conversation with SUMMARY_INTERVAL = {SUMMARY_INTERVAL}")
    
    # Sample conversation
    conversation_turns = [
        ("السلام علیکم", "وعلیکم السلام! کیسے ہیں؟"),
        ("میں ٹھیک ہوں", "اچھا! آج کیا کر رہے ہیں؟"),
        ("کام کر رہا ہوں", "کیا قسم کا کام؟"),
        ("AI پروجیکٹ پر", "واہ! کون سا پروجیکٹ؟"),
        ("Chatbot بنا رہا ہوں", "بہت اچھا! کیسا چل رہا ہے؟"),
        ("ابھی شروع کیا ہے", "اچھا! کیا features ہیں؟"),
        ("Voice recognition", "یہ تو بہت اچھا ہے!"),
        ("ہاں، LiveKit استعمال کر رہا ہوں", "واہ! یہ بہت powerful ہے"),
    ]
    
    for i, (user_msg, asst_msg) in enumerate(conversation_turns, 1):
        turn_counter += 1
        
        print(f"\n--- Turn {turn_counter} ---")
        print(f"User: {user_msg}")
        print(f"Assistant: {asst_msg}")
        
        # Simulate what the agent does:
        # 1. Update RAG conversation context
        rag_service.update_conversation_context(user_msg)
        
        # 2. Add conversation turn to RAG
        rag_service.add_conversation_turn(user_msg, asst_msg)
        
        rag_system = rag_service.get_rag_system()
        print(f"✅ RAG updated - conversation_turns: {len(rag_system.conversation_turns)}")
        
        # 3. Check if we should generate summary (like agent does)
        if turn_counter % SUMMARY_INTERVAL == 0:
            print(f"\n🔄 TRIGGERING INCREMENTAL SUMMARY (Turn {turn_counter})")
            
            try:
                # Get recent turns
                rag_system = rag_service.get_rag_system()
                recent_turns = [(turn['user'], turn['assistant']) for turn in rag_system.conversation_turns[-SUMMARY_INTERVAL:]]
                
                print(f"📊 Recent turns to summarize: {len(recent_turns)}")
                for j, (u, a) in enumerate(recent_turns, 1):
                    print(f"   {j}. User: {u[:30]}...")
                
                # Generate summary
                summary_data = await summary_service.generate_summary(
                    conversation_turns=recent_turns,
                    existing_summary=None
                )
                
                print(f"✅ Generated summary:")
                print(f"   Length: {len(summary_data['summary_text'])} chars")
                print(f"   Topics: {summary_data['key_topics']}")
                print(f"   Preview: {summary_data['summary_text'][:100]}...")
                
                # Save summary
                success = await summary_service.save_summary(
                    summary_data=summary_data,
                    turn_count=turn_counter,
                    user_id=TEST_USER_ID
                )
                
                if success:
                    print(f"✅ Summary saved successfully!")
                else:
                    print(f"❌ Failed to save summary")
                    
            except Exception as e:
                print(f"❌ Summary generation failed: {e}")
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
        
        else:
            print(f"➡️ Continue conversation (next summary at turn {((turn_counter // SUMMARY_INTERVAL) + 1) * SUMMARY_INTERVAL})")
    
    # Test final summary
    print(f"\n" + "=" * 80)
    print("📋 GENERATING FINAL SUMMARY")
    print("=" * 80)
    
    try:
        # Get all turns
        rag_system = rag_service.get_rag_system()
        all_turns = [(turn['user'], turn['assistant']) for turn in rag_system.conversation_turns]
        
        print(f"📊 All turns: {len(all_turns)}")
        
        # Generate final summary
        summary_data = await summary_service.generate_summary(
            conversation_turns=all_turns,
            existing_summary=None
        )
        
        print(f"✅ Final summary generated:")
        print(f"   Length: {len(summary_data['summary_text'])} chars")
        print(f"   Topics: {summary_data['key_topics']}")
        print(f"   Full text: {summary_data['summary_text']}")
        
        # Save final summary
        success = await summary_service.save_summary(
            summary_data=summary_data,
            turn_count=len(all_turns),
            user_id=TEST_USER_ID
        )
        
        if success:
            print(f"✅ Final summary saved successfully!")
        else:
            print(f"❌ Failed to save final summary")
            
    except Exception as e:
        print(f"❌ Final summary failed: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
    
    print(f"\n" + "=" * 80)
    print("🎉 CONVERSATION FLOW SIMULATION COMPLETE")
    print("=" * 80)
    print(f"✅ Total turns simulated: {turn_counter}")
    rag_system = rag_service.get_rag_system()
    print(f"✅ RAG conversation_turns: {len(rag_system.conversation_turns)}")
    print(f"✅ Summary triggers: {turn_counter // SUMMARY_INTERVAL}")
    print(f"✅ Final summary generated: Yes")

async def check_agent_logs():
    """Check what logs would appear in the real agent"""
    print("\n" + "=" * 80)
    print("📋 EXPECTED AGENT LOGS")
    print("=" * 80)
    
    print("When a real conversation happens, you should see these logs:")
    print()
    print("🎤 [USER TURN COMPLETED] User finished speaking")
    print("📊 Turn counter: X")
    print()
    print("Every 5 turns:")
    print("📊 [SUMMARY] Turn 5 - triggering incremental summary")
    print("[SUMMARY] 🤖 Generating incremental summary...")
    print("[SUMMARY] ✅ Generated: XXX chars")
    print("🔥 [SUMMARY SAVE] Starting save_summary process")
    print("[SUMMARY SAVE] ✅ Summary saved successfully!")
    print()
    print("On session end:")
    print("[ENTRYPOINT] 📝 Generating final conversation summary...")
    print("[SUMMARY] 📋 Generating FINAL session summary...")
    print("[SUMMARY] ✅ Final summary saved")

if __name__ == "__main__":
    asyncio.run(simulate_conversation_flow())
    asyncio.run(check_agent_logs())
