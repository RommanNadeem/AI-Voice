# Requirements Files Guide

This directory contains different requirement files for different use cases:

## 📦 Available Requirements Files

### 1. `requirements.txt` - **Main Requirements**
**Use this for:** Full voice agent functionality
```bash
pip install -r requirements.txt
```

**Includes:**
- ✅ OpenAI API integration
- ✅ Supabase database
- ✅ FAISS vector search
- ✅ LiveKit voice agent framework
- ✅ Voice activity detection (Silero)
- ✅ Text-to-speech capabilities

### 2. `requirements-minimal.txt` - **Minimal Voice Agent**
**Use this for:** Voice agent with minimal dependencies
```bash
pip install -r requirements-minimal.txt
```

**Includes:**
- ✅ Core AI functionality
- ✅ Database operations
- ✅ Voice agent features
- ❌ No development tools

### 3. `requirements-core.txt` - **Core Only**
**Use this for:** Just the memory/profile system without voice features
```bash
pip install -r requirements-core.txt
```

**Includes:**
- ✅ OpenAI API
- ✅ Supabase database
- ✅ FAISS vector search
- ❌ No LiveKit voice features
- ❌ No voice activity detection

### 4. `requirements-dev.txt` - **Development Tools**
**Use this for:** Additional development and testing tools
```bash
pip install -r requirements-dev.txt
```

**Includes:**
- ✅ Testing framework (pytest)
- ✅ Code formatting (black, isort)
- ✅ Linting (flake8)
- ✅ Type checking (mypy)
- ✅ Documentation (sphinx)

## 🚀 Quick Start Options

### Option 1: Full Voice Agent
```bash
pip install -r requirements.txt
python agent.py
```

### Option 2: Minimal Voice Agent
```bash
pip install -r requirements-minimal.txt
python agent.py
```

### Option 3: Core System Only
```bash
pip install -r requirements-core.txt
# Use MemoryManager and UserProfile classes directly
```

### Option 4: Development Setup
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## 📊 Dependency Breakdown

| Library | Purpose | Core | Minimal | Full |
|---------|---------|------|---------|------|
| `openai` | AI API calls | ✅ | ✅ | ✅ |
| `supabase` | Database operations | ✅ | ✅ | ✅ |
| `faiss-cpu` | Vector search | ✅ | ✅ | ✅ |
| `numpy` | Numerical operations | ✅ | ✅ | ✅ |
| `python-dotenv` | Environment variables | ✅ | ✅ | ✅ |
| `livekit-agents` | Voice agent framework | ❌ | ✅ | ✅ |
| `livekit-plugins-openai` | OpenAI integration | ❌ | ✅ | ✅ |
| `livekit-plugins-silero` | Voice activity detection | ❌ | ✅ | ✅ |

## 🔧 Installation Commands

### Install specific requirements:
```bash
# Core functionality only
pip install openai supabase faiss-cpu numpy python-dotenv

# With voice features
pip install openai supabase faiss-cpu numpy python-dotenv livekit-agents livekit-plugins-openai livekit-plugins-silero

# Development tools
pip install pytest black flake8 mypy
```

### Virtual environment setup:
```bash
# Create virtual environment
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

## 💡 Recommendations

- **Production**: Use `requirements.txt` for full functionality
- **Development**: Use `requirements.txt` + `requirements-dev.txt`
- **Testing**: Use `requirements-minimal.txt` for faster CI/CD
- **Core Library**: Use `requirements-core.txt` for embedding in other projects

## 🔍 Troubleshooting

### Common Issues:

1. **FAISS Installation Issues**
   ```bash
   # Try CPU version
   pip install faiss-cpu
   
   # Or GPU version (if you have CUDA)
   pip install faiss-gpu
   ```

2. **LiveKit Installation Issues**
   ```bash
   # Update pip first
   pip install --upgrade pip
   
   # Install LiveKit
   pip install livekit-agents
   ```

3. **Supabase Connection Issues**
   - Ensure SUPABASE_URL and SUPABASE_ANON_KEY are set
   - Check network connectivity
   - Verify Supabase project is active

### Version Compatibility:
- Python 3.8+ required
- All packages use `>=` for better compatibility
- Tested with Python 3.11
