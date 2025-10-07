# System Architecture Diagram - First Message vs Subsequent Messages

## Overview
This document visualizes how the system handles the first message differently from subsequent messages, showing the flow of memory, user profile, and RAG integration.

---

## 🚀 First Message Flow (OPTIMIZED - Fast Start)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER JOINS SESSION                          │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
        ┌────────────────────────────────────────────┐
        │  Session Initialization (entrypoint)       │
        │  • Extract user_id from participant        │
        │  • Initialize connection pool              │
        │  • Initialize Redis cache                  │
        │  • Initialize database batcher             │
        └────────────┬───────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────────────┐
        │  Quick Onboarding Init (500ms max)         │
        │  • Minimal user setup                      │
        │  • Non-blocking, timeout protected         │
        └────────────┬───────────────────────────────┘
                     │
                     │
        ┌────────────┴───────────────────────────────┐
        │                                             │
        ▼                                             ▼
┌───────────────┐                        ┌─────────────────────────┐
│  FOREGROUND   │                        │  BACKGROUND (async)     │
│  (Blocking)   │                        │  (Non-blocking)         │
└───────┬───────┘                        └──────────┬──────────────┘
        │                                            │
        ▼                                            ▼
┌─────────────────────────────┐      ┌──────────────────────────────┐
│ Simple Greeting Prep        │      │ RAG System Loading           │
│ ─────────────────────       │      │ ──────────────────           │
│ 1. Fetch User Name          │      │ • Load ALL memories (500)    │
│    └─> DB Query (20-30ms)   │      │ • Build vector index         │
│                              │      │ • Takes 500-1000ms           │
│ 2. Fetch Last Conversation  │      │ • Ready for 2nd message      │
│    └─> DB Query (20-30ms)   │      └──────────────────────────────┘
│                              │
│ 3. Simple Follow-up Logic   │
│    if < 12 hours:           │
│      → Follow-up greeting    │
│    else:                     │
│      → Fresh start greeting  │
│                              │
│ 4. Build Instructions        │
│    └─> No AI call (5-10ms)  │
│                              │
│ ⏱️  Total: 50-80ms          │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ Update Agent Instructions   │
│ ────────────────────────    │
│ • Base instructions only    │
│ • Simple greeting strategy  │
│ • NO CONTEXT INJECTION      │
│   (skipped for speed)       │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ LLM Generation              │
│ ─────────────               │
│ • OpenAI GPT-4o-mini        │
│ • 1000-3000ms               │
│ • Uses minimal context      │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ TTS Generation              │
│ ─────────────               │
│ • Uplift TTS                │
│ • 200-800ms                 │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 🎤 First Message Delivered  │
│ ⏱️  Total: ~2100ms          │
│ (was 3030ms - 31% faster!)  │
└─────────────────────────────┘


┌─────────────────────────────────────────────────────────────┐
│                   WHAT'S AVAILABLE?                         │
├─────────────────────────────────────────────────────────────┤
│ ✅ User's name (if stored)                                  │
│ ✅ Last conversation summary                                │
│ ✅ Simple follow-up logic                                   │
│ ❌ User profile (NOT loaded)                                │
│ ❌ RAG memories (loading in background)                     │
│ ❌ Full context (skipped for speed)                         │
│ ❌ Conversation state (NOT loaded)                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 💬 Subsequent Messages Flow (FULL CONTEXT)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    USER SENDS MESSAGE                               │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
        ┌────────────────────────────────────────────┐
        │  on_user_turn_completed()                  │
        │  • Receive user text                       │
        │  • Set _is_first_message = False           │
        │  • Invalidate cache                        │
        └────────────┬───────────────────────────────┘
                     │
                     │
        ┌────────────┴───────────────────────────────┐
        │                                             │
        ▼                                             ▼
┌───────────────┐                        ┌─────────────────────────┐
│  FOREGROUND   │                        │  BACKGROUND (async)     │
│  (Agent turn) │                        │  (Non-blocking)         │
└───────┬───────┘                        └──────────┬──────────────┘
        │                                            │
        ▼                                            ▼
┌─────────────────────────────┐      ┌──────────────────────────────┐
│ on_agent_turn_started()     │      │ Background Processing        │
│ (Before LLM)                │      │ ─────────────────────        │
│ ───────────────             │      │                              │
│ 1. Check _is_first_message  │      │ 1. Categorize User Input     │
│    └─> False (2nd+ message) │      │    └─> AI call (GPT-4o-mini)│
│                              │      │    └─> FACT/GOAL/INTEREST   │
│ 2. Get Enhanced Context     │      │                              │
│    (Multi-layer caching)    │      │ 2. Save Memory to DB         │
│                              │      │    └─> Supabase insert       │
│    ┌──────────────────────┐ │      │                              │
│    │ Session Cache (5ms)  │ │      │ 3. Add to RAG System         │
│    │   ↓ (miss)           │ │      │    └─> Update vector index   │
│    │ Redis Cache (20ms)   │ │      │                              │
│    │   ↓ (miss)           │ │      │ 4. Update User Profile       │
│    │ Database (150ms)     │ │      │    └─> AI profile generation │
│    └──────────────────────┘ │      │    └─> Save to DB + cache    │
│                              │      │                              │
│ 3. Fetch Full Context       │      │ 5. Update Conversation State │
│    (Parallel queries)       │      │    └─> Stage transitions     │
│                              │      │    └─> Trust score updates   │
│    a) User Profile          │      │                              │
│       • Profile text         │      │ ⏱️  Total: 500-1500ms       │
│       • Generated by AI      │      │ (Non-blocking!)             │
│                              │      └──────────────────────────────┘
│    b) Conversation State     │
│       • Stage (ORIENTATION,  │
│         ENGAGEMENT, etc.)    │
│       • Trust score (0-10)   │
│                              │
│    c) Recent Memories        │
│       • Last 10 memories     │
│       • Prioritized by       │
│         category + recency   │
│                              │
│    d) RAG Memories           │
│       • Semantic search      │
│       • Top 5 relevant       │
│       • Vector similarity    │
│                              │
│    e) Last Conversation      │
│       • Recent messages      │
│       • Time since last      │
│                              │
│ 4. Format Context            │
│    └─> Structured sections   │
│                              │
│ 5. Inject into Instructions  │
│    └─> update_instructions() │
│                              │
│ ⏱️  Cache Hit: 10-30ms      │
│ ⏱️  Cache Miss: 50-150ms    │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ LLM Generation              │
│ (with FULL CONTEXT)         │
│ ─────────────               │
│ • OpenAI GPT-4o-mini        │
│ • 1000-3000ms               │
│ • Has complete user context │
│ • Can reference memories    │
│ • Knows conversation stage  │
│ • Uses appropriate pronouns │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ TTS Generation              │
│ ─────────────               │
│ • Uplift TTS                │
│ • 200-800ms                 │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 🎤 Response Delivered       │
│ ⏱️  Total: ~1200-4000ms     │
│ (+ 10-150ms for context)    │
└─────────────────────────────┘


┌─────────────────────────────────────────────────────────────┐
│                   WHAT'S AVAILABLE?                         │
├─────────────────────────────────────────────────────────────┤
│ ✅ Full user profile                                        │
│ ✅ Conversation state (stage + trust)                       │
│ ✅ Recent memories (last 10)                                │
│ ✅ RAG memories (semantic search)                           │
│ ✅ Last conversation context                                │
│ ✅ All AI tools available                                   │
│ ✅ Complete context injection                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🗄️ Memory System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MEMORY FLOW                                 │
└─────────────────────────────────────────────────────────────────────┘

User Input
    │
    ▼
┌─────────────────────────────┐
│ Categorization (Background) │
│ ─────────────────────────── │
│ • AI analyzes input          │
│ • Assigns category:          │
│   - FACT                     │
│   - GOAL                     │
│   - INTEREST                 │
│   - EXPERIENCE               │
│   - PREFERENCE               │
│   - PLAN                     │
│   - RELATIONSHIP             │
│   - OPINION                  │
└────────────┬────────────────┘
             │
             ├────────────────────────┐
             │                        │
             ▼                        ▼
┌─────────────────────┐    ┌──────────────────────┐
│ Save to Database    │    │ Add to RAG System    │
│ ──────────────────  │    │ ───────────────────  │
│ Table: memory       │    │ • Vectorize text     │
│                     │    │ • Add to FAISS index │
│ Fields:             │    │ • Metadata:          │
│ • user_id           │    │   - category         │
│ • category          │    │   - timestamp        │
│ • key               │    │   - key              │
│ • value             │    │ • Available for      │
│ • created_at        │    │   semantic search    │
│                     │    │                      │
│ ⏱️  20-50ms         │    │ ⏱️  10-30ms          │
└─────────────────────┘    └──────────────────────┘
             │                        │
             └────────────┬───────────┘
                          │
                          ▼
             ┌─────────────────────────┐
             │ Available for Retrieval │
             │ ─────────────────────── │
             │ • Next agent turn       │
             │ • Automatic injection   │
             │ • Or tool-based search  │
             └─────────────────────────┘
```

---

## 👤 User Profile System

```
┌─────────────────────────────────────────────────────────────────────┐
│                      USER PROFILE FLOW                              │
└─────────────────────────────────────────────────────────────────────┘

User shares personal info
    │
    ▼
┌─────────────────────────────────────────────┐
│ Profile Generation (Background)             │
│ ──────────────────────────────────────────  │
│ • Fetch existing profile                    │
│ • AI analyzes new input                     │
│ • Merges with existing profile              │
│ • Generates comprehensive summary           │
│                                             │
│ AI Prompt includes:                         │
│ • Extract: name, age, occupation, location  │
│ • Extract: interests, goals, relationships  │
│ • Extract: preferences, opinions            │
│ • Maintain continuity with existing profile │
│                                             │
│ ⏱️  100-500ms (background, non-blocking)    │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Save to Database + Cache                    │
│ ──────────────────────────────────────────  │
│ Table: user_profiles                        │
│                                             │
│ Fields:                                     │
│ • user_id (primary key)                     │
│ • profile_text (AI-generated summary)       │
│ • last_updated                              │
│                                             │
│ Cache:                                      │
│ • Redis: 30 min TTL                         │
│ • Session: 15 min TTL                       │
│                                             │
│ ⏱️  20-50ms                                 │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Invalidate Context Cache                    │
│ ──────────────────────────────────────────  │
│ • Clear session cache                       │
│ • Clear Redis cache                         │
│ • Forces refresh on next agent turn         │
│                                             │
│ Next message will have updated profile!     │
└─────────────────────────────────────────────┘
```

---

## 🔍 RAG System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      RAG SYSTEM (Advanced)                          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────┐
│ Initialization  │
│ (Background)    │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ Load Memories from Database          │
│ ────────────────────────────────     │
│ • Fetch all memories for user        │
│ • Limit: 500 most recent             │
│ • Ordered by created_at DESC         │
│                                      │
│ ⏱️  500-1000ms (background)          │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│ Build Vector Index                   │
│ ────────────────────                 │
│ • Use sentence-transformers          │
│ • Model: all-MiniLM-L6-v2            │
│ • Create embeddings (384 dims)       │
│ • Build FAISS index (fast search)    │
│                                      │
│ ⏱️  200-500ms                        │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│ Ready for Semantic Search            │
│ ────────────────────────             │
│ • searchMemories(query, limit)       │
│ • Automatic context injection        │
│ • Real-time updates                  │
└──────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────┐
│                   SEARCH FLOW (Tier 1 Advanced)                     │
└─────────────────────────────────────────────────────────────────────┘

Query: "user's hobbies"
    │
    ▼
┌──────────────────────────────────────┐
│ Query Expansion                      │
│ ────────────────                     │
│ • Generate synonyms                  │
│ • Expand semantic meaning            │
│ • Example: "hobbies" → "interests",  │
│   "passions", "activities"           │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│ Vector Similarity Search             │
│ ────────────────────────             │
│ • Embed query                        │
│ • FAISS search (top 20 candidates)   │
│ • Calculate cosine similarity        │
│                                      │
│ ⏱️  5-20ms                           │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│ Advanced Re-ranking (Tier 1)         │
│ ────────────────────────────────     │
│ • Temporal boost (recent = higher)   │
│ • Importance boost (by category)     │
│ • Context matching (conversation)    │
│ • Final relevance score              │
│                                      │
│ ⏱️  2-10ms                           │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│ Return Top Results                   │
│ ────────────────                     │
│ • Top 5 most relevant                │
│ • Includes:                          │
│   - text                             │
│   - category                         │
│   - similarity score                 │
│   - relevance score                  │
│   - is_recent flag                   │
└──────────────────────────────────────┘
```

---

## 🔄 Context Injection System

```
┌─────────────────────────────────────────────────────────────────────┐
│                   CONTEXT INJECTION (Multi-Layer Cache)             │
└─────────────────────────────────────────────────────────────────────┘

on_agent_turn_started()
    │
    ▼
┌──────────────────────────────┐
│ Check: First Message?        │
│ └─> _is_first_message        │
└──────┬───────────────────────┘
       │
       ├─── Yes ──> Skip context injection (return early)
       │            ⏱️  0ms
       │
       └─── No ──> Continue to full context
                    │
                    ▼
           ┌────────────────────────────┐
           │ Layer 1: Session Cache     │
           │ ─────────────────────      │
           │ • In-memory dictionary     │
           │ • TTL: 15 minutes          │
           │ • Hit rate: 70-80%         │
           │ • Latency: ~5ms            │
           └──────┬─────────────────────┘
                  │
                  ├─── Hit ──> Return cached context
                  │            ⏱️  5ms
                  │
                  └─── Miss ──> Continue to Layer 2
                                 │
                                 ▼
                        ┌────────────────────────────┐
                        │ Layer 2: Redis Cache       │
                        │ ─────────────────────      │
                        │ • Distributed cache        │
                        │ • TTL: 30 minutes          │
                        │ • Hit rate: 15-20%         │
                        │ • Latency: ~20ms           │
                        └──────┬─────────────────────┘
                               │
                               ├─── Hit ──> Store in L1, return
                               │            ⏱️  20ms
                               │
                               └─── Miss ──> Continue to Layer 3
                                              │
                                              ▼
                                     ┌────────────────────────────┐
                                     │ Layer 3: Database          │
                                     │ ─────────────────────      │
                                     │ Parallel queries (async):  │
                                     │                            │
                                     │ 1. User Profile            │
                                     │    └─> user_profiles       │
                                     │                            │
                                     │ 2. Conversation State      │
                                     │    └─> conversation_state  │
                                     │                            │
                                     │ 3. Recent Memories         │
                                     │    └─> memory (last 10)    │
                                     │                            │
                                     │ 4. User Name               │
                                     │    └─> memory (name key)   │
                                     │                            │
                                     │ 5. Last Conversation       │
                                     │    └─> memory (last 5)     │
                                     │                            │
                                     │ Timeout: 2 seconds max     │
                                     │ ⏱️  50-200ms               │
                                     └──────┬─────────────────────┘
                                            │
                                            ▼
                                   ┌────────────────────────────┐
                                   │ Store in L2 + L1           │
                                   │ Return complete context    │
                                   └────────────────────────────┘
                                            │
                                            ▼
                                   ┌────────────────────────────┐
                                   │ Get RAG Memories           │
                                   │ ─────────────────          │
                                   │ • Semantic search          │
                                   │ • Query: "user info"       │
                                   │ • Top 5 results            │
                                   │ • Timeout: 1 second        │
                                   │                            │
                                   │ ⏱️  10-50ms                │
                                   └──────┬─────────────────────┘
                                          │
                                          ▼
                                   ┌────────────────────────────┐
                                   │ Format Context             │
                                   │ ─────────────              │
                                   │ Sections:                  │
                                   │ • User's Name              │
                                   │ • Key Information          │
                                   │ • User Profile             │
                                   │ • Current Stage            │
                                   │ • Recent Context           │
                                   │ • Conversation Continuity  │
                                   │ • User Goals               │
                                   └──────┬─────────────────────┘
                                          │
                                          ▼
                                   ┌────────────────────────────┐
                                   │ update_instructions()      │
                                   │ ─────────────────          │
                                   │ Base + Context injected    │
                                   │ Ready for LLM              │
                                   └────────────────────────────┘
```

---

## 📊 Performance Comparison

```
┌─────────────────────────────────────────────────────────────────────┐
│                    FIRST MESSAGE vs SUBSEQUENT                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────┬──────────────────┬──────────────────────┐
│ Component               │ First Message    │ Subsequent Messages  │
├─────────────────────────┼──────────────────┼──────────────────────┤
│ RAG Loading             │ Background (0ms) │ Available (cached)   │
│ User Profile            │ Not loaded       │ ✅ Loaded (cached)   │
│ Conversation State      │ Not loaded       │ ✅ Loaded (cached)   │
│ Recent Memories         │ Not loaded       │ ✅ Loaded (cached)   │
│ Context Injection       │ Skipped (0ms)    │ ✅ Active (10-150ms) │
│ Greeting Preparation    │ Simple (50ms)    │ Full context (10ms)  │
│ LLM Context             │ Minimal          │ Complete             │
├─────────────────────────┼──────────────────┼──────────────────────┤
│ Total Latency           │ ~2100ms          │ ~1200-4000ms         │
│ Context Overhead        │ +50ms            │ +10-150ms            │
│ Improvement             │ 31% faster       │ Always fresh context │
└─────────────────────────┴──────────────────┴──────────────────────┘

Key Insight:
• First message optimized for SPEED (minimal context)
• Subsequent messages optimized for QUALITY (full context)
• Background loading ensures no functionality loss
```

---

## 🎯 Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                                 │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│   SUPABASE DB    │
│   (PostgreSQL)   │
└────────┬─────────┘
         │
         ├─────> memory (categorized memories)
         ├─────> user_profiles (AI-generated profiles)
         ├─────> conversation_state (stage + trust)
         └─────> onboarding_details (user goals)
                 │
                 ▼
         ┌───────────────┐
         │  REDIS CACHE  │
         │  (30 min TTL) │
         └───────┬───────┘
                 │
                 ▼
         ┌───────────────┐
         │ SESSION CACHE │
         │ (15 min TTL)  │
         └───────┬───────┘
                 │
                 ▼
         ┌───────────────┐
         │  RAG SYSTEM   │
         │  (FAISS)      │
         └───────┬───────┘
                 │
                 ▼
         ┌───────────────┐
         │  AGENT LLM    │
         │  (OpenAI)     │
         └───────────────┘
```

---

## 🔧 Key Optimization Techniques

1. **Lazy Loading**: RAG loads in background, not blocking first message
2. **Conditional Context**: Skip heavy context injection for first message
3. **Multi-Layer Caching**: Session → Redis → Database
4. **Parallel Queries**: Fetch multiple data sources simultaneously
5. **Simple Heuristics**: Time-based follow-up logic (< 12 hours)
6. **Background Processing**: Memory saves, profile updates, state transitions
7. **Cache Invalidation**: Strategic invalidation only when data changes

---

**Result**: Fast first message + rich subsequent messages = best user experience! 🎉

