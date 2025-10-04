# AI Voice Project

A comprehensive voice AI agent system with Supabase integration, user profiling, and intelligent onboarding capabilities.

## 🚀 Features

- **Voice AI Agent**: LiveKit-based voice interaction with OpenAI GPT-4
- **User Profiling**: Intelligent user profile building and management
- **Onboarding System**: Structured user onboarding with Urdu storytelling
- **Supabase Integration**: Modern API-first database with real-time capabilities
- **Memory Management**: Persistent memory storage with FAISS vector search
- **Text-to-Speech**: Custom TTS integration with Uplift API

## 🤖 Agent Architecture

### 1. Core Agent (`agent.py`)
- **Purpose**: Main AI companion with full functionality
- **Features**:
  - Long-term memory and reflection
  - Context-aware conversations
  - User profile management
  - Urdu language support
  - RAG (Retrieval-Augmented Generation) system

### 2. Onboarding Agent (`Onboarding.py`)
- **Purpose**: Collect essential user information (name, occupation, interests)
- **Features**: 
  - Warm Urdu storytelling welcome
  - Structured question flow
  - JSON data extraction
  - Focused conversation flow

## 📁 Project Structure

```
ai_voice/
├── agent.py                    # Core voice agent with Supabase integration
├── Onboarding.py              # Onboarding agent with Urdu storytelling
├── uplift_tts.py              # Text-to-speech integration
├── requirements.txt           # Full dependencies
└── README.md                  # This file
```

## 🛠️ Quick Start

### 1. Install Dependencies

**Option A: Full Voice Agent**
```bash
pip install -r requirements.txt
```

**Option B: Core Functionality Only**
```bash
pip install -r requirements-core.txt
```

### 2. Setup Environment

Create a `.env` file:
```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key-here

# LiveKit Configuration (for voice features)
LIVEKIT_URL=your_livekit_url_here
LIVEKIT_API_KEY=your_livekit_api_key_here
LIVEKIT_API_SECRET=your_livekit_api_secret_here
```

### 3. Run the Agents

**Core Agent (Main Companion):**
```bash
python agent.py dev
```

**Onboarding Agent:**
```bash
python Onboarding.py dev
```

## 🎯 Core Components

### Core Agent (`agent.py`)
- **MemoryManager**: Supabase-based memory storage and retrieval
- **UserProfile**: AI-powered user profile building
- **Assistant**: LiveKit voice agent with Urdu language support
- **RAG System**: FAISS vector search for contextual responses

### Onboarding Agent (`Onboarding.py`)
- **Welcome Story**: Engaging Urdu storytelling
- **Essential Questions**: Structured user information gathering
- **JSON Extraction**: Automatic data extraction (name, occupation, interests)
- **User Restrictions**: Focused conversation flow

## 📊 Database Schema

### Database Schema

**Note:** The actual database has foreign key constraints that require `user_id` to exist in the `profiles` table first.

### Profiles Table (Base Table)
```sql
CREATE TABLE profiles (
    user_id UUID PRIMARY KEY,
    email VARCHAR(255),
    is_first_login BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Memory Table
```sql
CREATE TABLE memory (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES profiles(user_id),
    category VARCHAR(50) NOT NULL,
    key VARCHAR(255) NOT NULL,
    value TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, category, key)
);
```

### User Profiles Table
```sql
CREATE TABLE user_profiles (
    user_id UUID PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
    profile_text TEXT,
    onboarding_flags JSONB DEFAULT '{"is_new_user": true, "is_onboarding_done": false, "onboarding_questions": false}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Row Level Security (RLS) Policies

**Memory Table Policy:**
```sql
CREATE POLICY "Users can manage their own memory" ON memory
FOR ALL USING (auth.uid()::text = user_id);
```

**User Profiles Table Policy:**
```sql
CREATE POLICY "Users can manage their own profiles" ON user_profiles
FOR ALL USING (auth.uid()::text = user_id);
```

## 🔧 Configuration Options

### Requirements Files
- `requirements.txt` - Full voice agent functionality
- `requirements-minimal.txt` - Minimal voice agent
- `requirements-core.txt` - Core functionality only (no voice)
- `requirements-dev.txt` - Development tools

### Environment Variables
| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `SUPABASE_URL` | Supabase project URL | Yes |
| `SUPABASE_ANON_KEY` | Supabase anonymous key | Yes |
| `LIVEKIT_URL` | LiveKit server URL | For voice features |
| `LIVEKIT_API_KEY` | LiveKit API key | For voice features |
| `LIVEKIT_API_SECRET` | LiveKit API secret | For voice features |

## 🌟 Key Features

### Voice AI Agent
- **Urdu Language Support**: Native Urdu conversation
- **Context Awareness**: Memory-based responses
- **User Profiling**: Automatic profile building
- **Real-time Interaction**: LiveKit voice processing

### Onboarding System
- **Storytelling**: Engaging Urdu stories
- **Structured Questions**: Essential information gathering
- **JSON Extraction**: Automatic data structuring
- **User Focus**: Keeps conversations on track

### Supabase Integration
- **API-First**: Modern database approach
- **Real-time**: Live data updates
- **Security**: Row Level Security support
- **Scalability**: Cloud-hosted database

## 🚀 Advanced Usage

### Custom Voice Agent
```python
from agent import MemoryManager, UserProfile

# Initialize components
memory_manager = MemoryManager()
user_profile = UserProfile(user_id="custom_user")

# Store information
memory_manager.store("FACT", "user_preference", "loves coffee")

# Update profile
user_profile.smart_update("I'm a software engineer")
```

### Onboarding Customization
```python
# Modify welcome story
WELCOME_STORY = "Your custom story here..."

# Modify questions
ONBOARDING_QUESTIONS = [
    "Your custom question 1?",
    "Your custom question 2?",
    "Your custom question 3?"
]
```

## 📚 Documentation

- [Supabase Integration Guide](README_SUPABASE.md)
- [Requirements Guide](REQUIREMENTS_README.md)
- [Supabase Python Documentation](https://supabase.com/docs/reference/python/select)

## 🔒 Security

- **API Key Management**: Environment variable storage
- **Row Level Security**: Supabase RLS support
- **Data Validation**: Automatic input validation
- **Secure Connections**: HTTPS/TLS encryption

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For issues and questions:
1. Check the documentation
2. Review the requirements guide
3. Test with core dependencies first
4. Create an issue with detailed information

## 🎉 Acknowledgments

- **OpenAI**: GPT-4 API integration
- **Supabase**: Modern database platform
- **LiveKit**: Voice AI framework
- **FAISS**: Vector search capabilities
