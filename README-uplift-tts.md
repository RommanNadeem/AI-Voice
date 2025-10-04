# Uplift TTS Requirements

This directory contains different requirements files for the `uplift_tts.py` module:

## 📁 Requirements Files

### 1. `requirements-uplift-tts-minimal.txt`
**Minimal dependencies only**
- `livekit-agents` - Core LiveKit agents framework
- `python-socketio` - WebSocket communication
- `loguru` - Logging framework

**Use when:** You want the smallest possible installation

### 2. `requirements-uplift-tts.txt`
**Standard dependencies with version constraints**
- All minimal dependencies with version specifications
- Optional dependencies commented out
- Production-ready configuration

**Use when:** You want a stable, production-ready setup

### 3. `requirements-uplift-tts-full.txt`
**Complete dependencies with all optional packages**
- All core dependencies
- Enhanced networking packages
- Additional utilities
- Maximum compatibility

**Use when:** You need full functionality and compatibility

## 🚀 Installation

**Minimal Installation:**
```bash
pip install -r requirements-uplift-tts-minimal.txt
```

**Standard Installation:**
```bash
pip install -r requirements-uplift-tts.txt
```

**Full Installation:**
```bash
pip install -r requirements-uplift-tts-full.txt
```

## 📋 Dependencies Explained

- **livekit-agents**: Core framework for LiveKit voice agents
- **python-socketio**: WebSocket client for real-time communication with Uplift API
- **loguru**: Modern logging library for better debugging
- **websockets**: Additional WebSocket support (optional)
- **aiohttp**: Async HTTP client (optional)
- **httpx**: Modern HTTP client (optional)

## 🔧 Usage

After installation, you can use the Uplift TTS in your LiveKit agents:

```python
from uplift_tts import TTS

# Create TTS instance
tts = TTS(voice_id="17", output_format="MP3_22050_32")

# Use in LiveKit agent
from livekit.agents import AgentSession
session = AgentSession(
    stt=stt,
    llm=llm,
    tts=tts,  # Your Uplift TTS instance
    vad=vad,
)
```
