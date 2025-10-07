# Comprehensive Logging Summary

## Overview

All key operations now have detailed console logging with emoji indicators for easy scanning.

## Logging Categories

### 1. Memory Operations

#### Memory Save (MemoryService.save_memory)
```
[MEMORY SERVICE] 💾 Saving memory: [CATEGORY] key_name
[MEMORY SERVICE]    Value: actual value text...
[MEMORY SERVICE]    User: 12345678...
[MEMORY SERVICE] ✅ Saved successfully: [CATEGORY] key_name
```

#### Memory Fetch (MemoryService.get_memory)
```
[MEMORY SERVICE] 🔍 Fetching memory: [CATEGORY] key_name
[MEMORY SERVICE]    User: 12345678...
[MEMORY SERVICE] ✅ Found: actual value text...
```
OR
```
[MEMORY SERVICE] ℹ️  Not found: [CATEGORY] key_name
```

#### Memory Fetch by Category (MemoryService.get_memories_by_category)
```
[MEMORY SERVICE] 🔍 Fetching memories by category: [CATEGORY] (limit: 50)
[MEMORY SERVICE]    User: 12345678...
[MEMORY SERVICE] ✅ Found 5 memories in category [CATEGORY]
```

### 2. User Profile Operations

#### Profile Generation (ProfileService.generate_profile)
```
[PROFILE SERVICE] ✅ Generated profile:
[PROFILE SERVICE]    A user who enjoys coding and reading. They work as a software engineer...
```

#### Profile Save (ProfileService.save_profile)
```
[PROFILE SERVICE] 💾 Saving profile for user 12345678...
[PROFILE SERVICE]    A user who enjoys coding and reading...
[PROFILE SERVICE] ✅ Profile saved successfully
```

#### Profile Save Async (ProfileService.save_profile_async)
```
[PROFILE SERVICE] ✅ Profile saved successfully (cache invalidated)
[PROFILE SERVICE]    User: 12345678...
```

#### Profile Fetch (ProfileService.get_profile)
```
[PROFILE SERVICE] 🔍 Fetching profile for user 12345678...
[PROFILE SERVICE] ✅ Profile found: A user who enjoys coding...
```
OR
```
[PROFILE SERVICE] ℹ️  No profile found yet
```

#### Profile Fetch Async (ProfileService.get_profile_async)
```
[PROFILE SERVICE] 🔍 Fetching profile (async) for user 12345678...
[PROFILE SERVICE] ✅ Cache hit - profile found in Redis
[PROFILE SERVICE]    A user who enjoys coding...
```
OR
```
[PROFILE SERVICE] ℹ️  Cache miss - fetching from database...
[PROFILE SERVICE] ✅ Profile fetched from DB and cached
[PROFILE SERVICE]    A user who enjoys coding...
```

### 3. User Name Operations

#### Name Fetch (ConversationContextService._fetch_user_name)
```
[CONTEXT SERVICE] 🔍 Fetching user's first name for 12345678...
[CONTEXT SERVICE] ✅ User's name found: 'Ahmed' (from key: name)
```
OR
```
[CONTEXT SERVICE] ℹ️  User's name not found yet
```

#### Name Injection into Context (ConversationContextService.format_context_for_instructions)
```
[CONTEXT FORMAT] 👤 Injecting user's name into context: 'Ahmed'
```
OR
```
[CONTEXT FORMAT] ℹ️  No user name available for context injection
```

### 4. Context Injection Operations

#### Context Refresh Before Agent Response (Agent.on_agent_turn_started)
```
[ON_AGENT_TURN #1] 🔄 Refreshing context before AI response...
[ON_AGENT_TURN #1] ✓ Context refreshed in 45.2ms
```

#### Context Injection Details (Agent.get_enhanced_instructions)
```
[CONTEXT INJECTION #1] 🔄 Fetching enhanced context for user 12345678...
[CONTEXT INJECTION #1] ✅ Enhanced context injected in 120.5ms (cache hit rate: 85.0%)
[CONTEXT DETAILS] RAG memories: 10, Recent memories: 5, Profile: True
[CONTEXT SIZE] Base: 5000 chars, Enhanced: 7500 chars, Overhead: 2500 chars
```

### 5. User Input Processing

#### User Input Received (Agent.on_user_turn_completed)
```
[USER INPUT] 💬 User message text here...
[CONTEXT UPDATE] ✓ RAG context updated with user input
[CACHE INVALIDATION] ✓ Context cache invalidated after user input
```

### 6. Background Processing

#### Background Processing Start (Agent._process_with_rag_background)
```
[BACKGROUND] 🔄 Processing user input with RAG (optimized)...
```

#### Memory Categorization
```
[AUTO MEMORY] 💾 Saving: [INTEREST] user_input_1234567890
```

#### Memory Save Result
```
[AUTO MEMORY] ✅ Saved to Supabase
```

#### Profile Update
```
[AUTO PROFILE] ✅ Updated (cache invalidated)
```
OR
```
[AUTO PROFILE] ℹ️  No new info to extract
```

#### State Updates
```
[AUTO STATE] 🔄 Transitioned: ORIENTATION → ENGAGEMENT
```
OR
```
[AUTO STATE] 📊 Trust adjusted: 5.0 → 6.5
```
OR
```
[AUTO STATE] ℹ️  No state changes needed
```

#### Background Completion
```
[BACKGROUND] ✅ Completed in 0.85s (optimized with parallel processing)
```

### 7. RAG Operations

#### RAG Memory Search (Agent._get_rag_memories)
```
[RAG] 🔍 Searching for relevant memories...
[RAG] ✅ Retrieved 10 relevant memories
[RAG #1] INTEREST: user loves playing cricket... (score: 0.892)
[RAG #2] GOAL: wants to learn machine learning... (score: 0.845)
[RAG #3] FACT: works as a software engineer... (score: 0.823)
```

#### RAG Memory Indexing
```
[RAG] ✅ Memory queued for indexing
```

### 8. Initialization Logging

#### RAG Loading
```
[INIT] 🔄 Starting parallel initialization (RAG + Onboarding)...
[RAG] Loading memories from database...
[RAG] ✓ Memories loaded and indexed before first message
```

#### Greeting Generation
```
[GREETING] 🎯 Generating intelligent first message...
[GREETING] Context will be auto-injected via on_agent_turn_started() hook
[GREETING] ✓ Greeting strategy prepared
[GREETING] 🚀 Generating response (context will be auto-injected)...
```

## Emoji Legend

- 🔄 - Processing/Loading
- 💾 - Saving operation
- 🔍 - Fetching/Searching operation
- ✅ - Success
- ❌ - Error
- ℹ️  - Info/Not found
- ⚠️  - Warning
- 👤 - User name related
- 📊 - Statistics/Metrics
- 💬 - User message
- 🎯 - Target/Goal
- 🚀 - Launch/Start

## Log Filtering Tips

### To see only memory operations:
```bash
grep "MEMORY SERVICE" output.log
```

### To see only profile operations:
```bash
grep "PROFILE SERVICE" output.log
```

### To see only name operations:
```bash
grep -E "(User's name|first name)" output.log
```

### To see only successful operations:
```bash
grep "✅" output.log
```

### To see only errors:
```bash
grep "❌" output.log
```

### To see context injection flow:
```bash
grep -E "(ON_AGENT_TURN|CONTEXT INJECTION)" output.log
```

### To see background processing:
```bash
grep "BACKGROUND" output.log
```

## Key Logging Locations

### Services:
- `/services/memory_service.py` - Memory CRUD operations
- `/services/profile_service.py` - Profile generation and storage
- `/services/conversation_context_service.py` - Name fetching and context formatting

### Agent:
- `/agent.py` - Context injection, background processing, RAG operations

## Debugging Workflow

1. **Check if memory is being saved:**
   - Look for `[MEMORY SERVICE] 💾 Saving memory`
   - Verify with `[MEMORY SERVICE] ✅ Saved successfully`

2. **Check if profile is being updated:**
   - Look for `[PROFILE SERVICE] ✅ Generated profile`
   - Verify save with `[PROFILE SERVICE] ✅ Profile saved successfully`

3. **Check if name is being captured:**
   - Look for `[CONTEXT SERVICE] ✅ User's name found`
   - Verify injection with `[CONTEXT FORMAT] 👤 Injecting user's name`

4. **Check if context is being refreshed:**
   - Look for `[ON_AGENT_TURN #N] 🔄 Refreshing context`
   - Verify injection with `[CONTEXT INJECTION #N] ✅ Enhanced context injected`

5. **Check background processing:**
   - Look for `[BACKGROUND] 🔄 Processing user input`
   - Verify completion with `[BACKGROUND] ✅ Completed in X.XXs`

## Performance Monitoring

### Context Injection Performance:
- Target: < 100ms with cache hits
- Target: < 300ms with cache misses

### Background Processing Performance:
- Target: < 2s for complete processing
- Parallel execution should show multiple operations completing simultaneously

### Cache Hit Rates:
- Profile cache: Should be > 80% after warmup
- Context cache: Should be > 70% after warmup
- Redis cache: Should be > 60% overall

## Example Complete Flow

```
[USER INPUT] 💬 My name is Ahmed and I love cricket
[CONTEXT UPDATE] ✓ RAG context updated with user input
[CACHE INVALIDATION] ✓ Context cache invalidated after user input

[BACKGROUND] 🔄 Processing user input with RAG (optimized)...
[AUTO MEMORY] 💾 Saving: [FACT] user_input_1234567890
[MEMORY SERVICE] 💾 Saving memory: [FACT] user_input_1234567890
[MEMORY SERVICE]    Value: My name is Ahmed and I love cricket
[MEMORY SERVICE]    User: 12345678...
[MEMORY SERVICE] ✅ Saved successfully: [FACT] user_input_1234567890
[AUTO MEMORY] ✅ Saved to Supabase

[RAG] ✅ Memory queued for indexing

[PROFILE SERVICE] ✅ Generated profile:
[PROFILE SERVICE]    Ahmed is a cricket enthusiast...
[PROFILE SERVICE] ✅ Profile saved successfully (cache invalidated)
[AUTO PROFILE] ✅ Updated (cache invalidated)

[AUTO STATE] ℹ️  No state changes needed
[BACKGROUND] ✅ Completed in 0.92s (optimized with parallel processing)

[ON_AGENT_TURN #2] 🔄 Refreshing context before AI response...
[CONTEXT INJECTION #2] 🔄 Fetching enhanced context for user 12345678...
[CONTEXT SERVICE] 🔍 Fetching user's first name for 12345678...
[CONTEXT SERVICE] ✅ User's name found: 'Ahmed' (from key: user_input_1234567890)
[CONTEXT FORMAT] 👤 Injecting user's name into context: 'Ahmed'
[RAG] 🔍 Searching for relevant memories...
[RAG] ✅ Retrieved 5 relevant memories
[CONTEXT INJECTION #2] ✅ Enhanced context injected in 85.3ms (cache hit rate: 75.0%)
[CONTEXT DETAILS] RAG memories: 5, Recent memories: 1, Profile: True
[ON_AGENT_TURN #2] ✓ Context refreshed in 87.1ms
```

This shows the complete lifecycle of a user message with all logging checkpoints.

