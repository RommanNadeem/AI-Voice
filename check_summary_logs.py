"""
Check Summary Logs - Verify if conversation summaries are being saved
"""

import asyncio
from supabase import create_client
from core.config import Config
from core.validators import set_current_user_id, set_supabase_client
from services.conversation_summary_service import ConversationSummaryService
from core.user_id import UserId

# Test user ID
TEST_USER_ID = "4e3efa3d-d8fe-431e-a78f-4efffb0cf43a"

async def check_summary_status():
    """Check if summaries are being saved and retrieve current status"""
    
    print("=" * 80)
    print("🔍 CHECKING CONVERSATION SUMMARY STATUS")
    print("=" * 80)
    
    # Initialize Supabase
    if not Config.SUPABASE_URL:
        print("❌ SUPABASE_URL not configured")
        return
    
    key = Config.get_supabase_key()
    if not key:
        print("❌ No Supabase key configured")
        return
    
    supabase = create_client(Config.SUPABASE_URL, key)
    set_supabase_client(supabase)
    set_current_user_id(TEST_USER_ID)
    
    print(f"✅ Supabase connected")
    print(f"✅ Checking for user: {UserId.format_for_display(TEST_USER_ID)}")
    
    # Check conversation_state table
    print("\n" + "-" * 80)
    print("📊 CHECKING CONVERSATION_STATE TABLE")
    print("-" * 80)
    
    try:
        resp = await asyncio.to_thread(
            lambda: supabase.table("conversation_state")
                .select("*")
                .eq("user_id", TEST_USER_ID)
                .single()
                .execute()
        )
        
        if resp.data:
            data = resp.data
            print(f"✅ Found conversation_state record:")
            print(f"   ID: {data.get('id')}")
            print(f"   User ID: {UserId.format_for_display(data.get('user_id'))}")
            print(f"   Stage: {data.get('stage')}")
            print(f"   Trust Score: {data.get('trust_score')}")
            print(f"   Created: {data.get('created_at')}")
            print(f"   Updated: {data.get('updated_at')}")
            
            # Check summary fields
            print(f"\n📝 SUMMARY FIELDS:")
            print(f"   Has last_summary: {'Yes' if data.get('last_summary') else 'No'}")
            
            if data.get('last_summary'):
                summary = data['last_summary']
                print(f"   Summary length: {len(summary)} chars")
                print(f"   Summary preview: {summary[:150]}...")
                print(f"   Summary full text:")
                print(f"   {'='*60}")
                print(f"   {summary}")
                print(f"   {'='*60}")
            else:
                print(f"   ❌ No summary found in last_summary field")
            
            # Check topics
            print(f"\n🏷️  TOPICS:")
            topics = data.get('last_topics', [])
            if topics:
                print(f"   Topics count: {len(topics)}")
                print(f"   Topics: {topics}")
            else:
                print(f"   ❌ No topics found")
            
            # Check conversation timestamp
            print(f"\n⏰ TIMESTAMPS:")
            last_convo = data.get('last_conversation_at')
            if last_convo:
                print(f"   Last conversation: {last_convo}")
            else:
                print(f"   ❌ No last_conversation_at timestamp")
            
            # Check other fields
            print(f"\n💬 MESSAGES:")
            last_user_msg = data.get('last_user_message')
            last_asst_msg = data.get('last_assistant_message')
            
            if last_user_msg:
                print(f"   Last user message: {last_user_msg[:100]}...")
            else:
                print(f"   ❌ No last_user_message")
            
            if last_asst_msg:
                print(f"   Last assistant message: {last_asst_msg[:100]}...")
            else:
                print(f"   ❌ No last_assistant_message")
                
        else:
            print(f"❌ No conversation_state found for user")
            
    except Exception as e:
        print(f"❌ Error querying conversation_state: {e}")
    
    # Test summary service directly
    print("\n" + "-" * 80)
    print("🧪 TESTING SUMMARY SERVICE DIRECTLY")
    print("-" * 80)
    
    try:
        summary_service = ConversationSummaryService(supabase)
        
        # Test loading last summary
        print("📥 Testing get_last_summary...")
        last_summary = await summary_service.get_last_summary(TEST_USER_ID)
        
        if last_summary:
            print(f"✅ Successfully loaded summary:")
            print(f"   Has summary: {bool(last_summary.get('last_summary'))}")
            print(f"   Summary length: {len(last_summary.get('last_summary', ''))} chars")
            print(f"   Topics: {last_summary.get('last_topics', [])}")
            print(f"   Last conversation: {last_summary.get('last_conversation_at', 'N/A')}")
            
            # Test formatting
            print(f"\n📄 Testing format_summary_for_context...")
            formatted = summary_service.format_summary_for_context(last_summary)
            if formatted:
                print(f"✅ Successfully formatted for context:")
                print(f"   Length: {len(formatted)} chars")
                print(f"   Preview: {formatted[:200]}...")
            else:
                print(f"❌ Failed to format summary")
        else:
            print(f"❌ No summary found via service")
            
    except Exception as e:
        print(f"❌ Error testing summary service: {e}")
    
    # Check for any recent activity
    print("\n" + "-" * 80)
    print("📈 CHECKING RECENT ACTIVITY")
    print("-" * 80)
    
    try:
        # Get all conversation_state records for this user (in case there are multiple)
        resp = await asyncio.to_thread(
            lambda: supabase.table("conversation_state")
                .select("*")
                .eq("user_id", TEST_USER_ID)
                .order("updated_at", desc=True)
                .execute()
        )
        
        if resp.data:
            print(f"📊 Found {len(resp.data)} conversation_state record(s):")
            for i, record in enumerate(resp.data, 1):
                print(f"\n   Record {i}:")
                print(f"     ID: {record.get('id')}")
                print(f"     Updated: {record.get('updated_at')}")
                print(f"     Has summary: {'Yes' if record.get('last_summary') else 'No'}")
                if record.get('last_summary'):
                    print(f"     Summary length: {len(record['last_summary'])} chars")
        else:
            print(f"❌ No conversation_state records found")
            
    except Exception as e:
        print(f"❌ Error checking recent activity: {e}")
    
    print("\n" + "=" * 80)
    print("🔍 SUMMARY STATUS CHECK COMPLETE")
    print("=" * 80)

async def test_summary_generation():
    """Test generating a new summary to verify the system works"""
    print("\n" + "=" * 80)
    print("🧪 TESTING SUMMARY GENERATION")
    print("=" * 80)
    
    # Initialize Supabase
    supabase = create_client(Config.SUPABASE_URL, Config.get_supabase_key())
    set_supabase_client(supabase)
    set_current_user_id(TEST_USER_ID)
    
    # Create test conversation
    test_conversation = [
        ("آج کیا کر رہے ہیں؟", "میں کام کر رہا ہوں"),
        ("کیا کام کر رہے ہیں؟", "AI پروجیکٹ پر کام کر رہا ہوں"),
        ("کون سا پروجیکٹ؟", "یہ ایک chatbot ہے"),
    ]
    
    print(f"📝 Testing with {len(test_conversation)} conversation turns...")
    
    try:
        summary_service = ConversationSummaryService(supabase)
        summary_service.set_session("test-session-logs")
        
        # Generate summary
        summary_data = await summary_service.generate_summary(
            conversation_turns=test_conversation,
            existing_summary=None
        )
        
        print(f"✅ Generated summary:")
        print(f"   Length: {len(summary_data['summary_text'])} chars")
        print(f"   Topics: {summary_data['key_topics']}")
        print(f"   Tone: {summary_data['emotional_tone']}")
        
        # Save summary
        success = await summary_service.save_summary(
            summary_data=summary_data,
            turn_count=len(test_conversation),
            user_id=TEST_USER_ID
        )
        
        if success:
            print(f"✅ Summary saved successfully!")
        else:
            print(f"❌ Failed to save summary")
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

async def main():
    """Main function"""
    await check_summary_status()
    await test_summary_generation()

if __name__ == "__main__":
    asyncio.run(main())
