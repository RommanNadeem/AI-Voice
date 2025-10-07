# Troubleshooting: Agent Worker "Listening" but No Job Received

## Current Situation

**Logs show:**
```
INFO:livekit.agents:registered worker {"id": "AW_LEZ4A8P3cZAX", "url": "wss://mahira-5efzx2ms.livekit.cloud"}
```

But **NO** entrypoint logs like:
```
[ENTRYPOINT] 🚀 NEW JOB RECEIVED
[ENTRYPOINT] Room: ...
```

## What This Means

✅ **Agent worker is running correctly**
✅ **Connected to LiveKit Cloud** (Singapore region)
✅ **Registered and waiting for jobs**
❌ **No room connection/job has been dispatched yet**

The worker is in "standby" mode waiting for someone to:
1. Create a room
2. Connect to that room
3. Trigger the agent to join

---

## Root Cause: No Frontend Connection

This is **NOT** a bug in the agent code. This means:
- Your **frontend hasn't connected** to a LiveKit room yet, OR
- The **agent dispatch rules** aren't configured to send the agent to the room

---

## How LiveKit Agent Dispatch Works

```
1. Frontend creates/joins room
   ↓
2. LiveKit server sees room has participants
   ↓
3. LiveKit checks if agent should be dispatched
   ↓
4. If YES → LiveKit calls your entrypoint function
   ↓
5. Agent joins room and starts conversation
```

Currently, you're stuck at step 1 or 3.

---

## Solution 1: Check Frontend Connection

### Verify Your Frontend Code:

```typescript
// React/Next.js example
import { Room } from 'livekit-client';

const connectToAgent = async (userId: string) => {
  // 1. Get token from your backend
  const response = await fetch('/api/livekit-token', {
    method: 'POST',
    body: JSON.stringify({ 
      userId,
      roomName: `user-${userId}-room`  // Unique room per user
    })
  });
  
  const { token, url } = await response.json();
  
  // 2. Connect to room
  const room = new Room();
  
  await room.connect(url, token, {
    autoSubscribe: true,
  });
  
  // 3. Enable microphone (REQUIRED for agent to hear you)
  await room.localParticipant.setMicrophoneEnabled(true);
  
  console.log('✅ Connected to room:', room.name);
};
```

### Required: Enable Microphone
```typescript
// The agent needs audio input to start
await room.localParticipant.setMicrophoneEnabled(true);
```

---

## Solution 2: Check Agent Dispatch Configuration

### Option A: Auto-dispatch on Room Creation

In your LiveKit Cloud dashboard or config:

```yaml
# livekit.yaml or dashboard settings
room:
  auto_create: true
  
agents:
  # Dispatch agent when ANY participant joins
  dispatch:
    - name: companion-agent
      on_participant_connected: true
      room_name: "*"  # Or specific pattern like "user-*"
```

### Option B: Manual Agent Dispatch from Backend

If you're manually dispatching agents:

```python
# Your backend API endpoint
from livekit import api

async def dispatch_agent(room_name: str):
    lk_api = api.LiveKitAPI(
        url='https://mahira-5efzx2ms.livekit.cloud',
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET
    )
    
    # Create agent dispatch request
    await lk_api.agent.create_dispatch(
        room=room_name,
        agent_name="companion-agent"  # Your agent name
    )
```

---

## Solution 3: Test with CLI

### Quick Test - Does Agent Respond to Room Creation?

```bash
# Terminal 1: Your agent is already running ✅

# Terminal 2: Create a test room and join it
# Install LiveKit CLI if not already:
# npm install -g livekit-cli

# Generate a test token
livekit-cli token create \
  --api-key <your-api-key> \
  --api-secret <your-api-secret> \
  --join --room test-room-123 \
  --identity test-user \
  --valid-for 1h

# This will output a token - use it to test
```

Or use the LiveKit Playground:
1. Go to: https://meet.livekit.io/custom
2. Enter your LiveKit Cloud URL
3. Use a test token
4. Join the room
5. Check if agent logs show `[ENTRYPOINT] 🚀 NEW JOB RECEIVED`

---

## Solution 4: Check LiveKit Token Generation

Your backend needs to generate tokens that:

```python
from livekit import api
import os

def create_livekit_token(user_id: str):
    # IMPORTANT: Each user gets their own room
    room_name = f"user-{user_id}-room"
    
    token = api.AccessToken(
        api_key=os.getenv("LIVEKIT_API_KEY"),
        api_secret=os.getenv("LIVEKIT_API_SECRET")
    )
    
    token.with_identity(user_id)  # User's identity
    token.with_name(user_id)      # Display name
    
    # Grant permissions
    token.with_grants(api.VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=True,      # User can publish audio
        can_subscribe=True,    # User can hear agent
    ))
    
    # Token valid for 1 hour
    token.with_ttl(timedelta(hours=1))
    
    return {
        'token': token.to_jwt(),
        'url': os.getenv("LIVEKIT_URL"),
        'room_name': room_name
    }
```

---

## Debugging Steps

### 1. Check LiveKit Dashboard

Go to: https://cloud.livekit.io/projects

**Look for:**
- ✅ Active rooms (should show your room when user connects)
- ✅ Participants in the room
- ✅ Agent dispatch events
- ❌ Any errors in the logs

### 2. Enable Verbose Logging

Add to your agent startup:

```bash
# Set log level to DEBUG
export LIVEKIT_LOG_LEVEL=debug

# Run agent with verbose output
python agent.py
```

### 3. Check Agent Logs

Look for these specific messages:

```bash
# ✅ Good - Agent received job
[ENTRYPOINT] 🚀 NEW JOB RECEIVED
[ENTRYPOINT] Room: user-123-room

# ❌ Bad - No entrypoint logs at all
# This means no room connection happened
```

### 4. Test Frontend Connection

Add logging to your frontend:

```typescript
room.on('connected', () => {
  console.log('✅ Room connected:', room.name);
  console.log('✅ Participants:', room.participants.size);
});

room.on('participantConnected', (participant) => {
  console.log('✅ Participant joined:', participant.identity);
  
  // Check if it's the agent
  if (participant.identity.includes('agent')) {
    console.log('🤖 Agent has joined the room!');
  }
});

room.on('trackSubscribed', (track) => {
  console.log('✅ Track subscribed:', track.kind);
});
```

---

## Expected Flow (When Working)

### Frontend:
```
1. User clicks "Start Conversation"
2. Frontend requests token from backend
3. Frontend connects to LiveKit room
4. Frontend enables microphone
5. Frontend waits for agent to join
```

### Backend Logs (Your Agent):
```
[ENTRYPOINT] 🚀 NEW JOB RECEIVED
[ENTRYPOINT] Room: user-abc123-room
[ENTRYPOINT] Waiting for participant to join...
[ENTRYPOINT] Participant joined: sid=PA_xxx, identity=abc123
[SESSION INIT] Starting LiveKit session with participant...
[SESSION INIT] ✓ Session started and ready to listen
[AUDIO] Waiting for participant audio track to be ready...
[AUDIO] ✓ Audio track subscribed: TR_xxx
[AUDIO] ✓ Audio track fully ready
[GREETING] Generating first message with context...
[GREETING] ✓ First message sent!
```

### Frontend (User Experience):
```
1. "Connecting..." 
2. "Connected!" (room joined)
3. Agent starts speaking (greeting)
4. User can now talk to agent
```

---

## Quick Checklist

- [ ] Frontend connects to LiveKit room
- [ ] Frontend enables microphone (`setMicrophoneEnabled(true)`)
- [ ] Room name follows pattern (e.g., `user-{userId}-room`)
- [ ] Token is valid and has correct permissions
- [ ] Agent dispatch is configured in LiveKit
- [ ] Agent worker is running (you see "registered worker" ✅)
- [ ] Check LiveKit dashboard for active rooms

---

## Still Not Working?

### Share These Logs:

1. **Frontend console logs** (browser DevTools)
2. **Backend token generation logs**
3. **Agent worker logs** (what you already shared)
4. **LiveKit dashboard** - screenshot of rooms/participants

### Environment Variables to Check:

```bash
# Agent needs these:
LIVEKIT_URL=wss://mahira-5efzx2ms.livekit.cloud
LIVEKIT_API_KEY=<your-key>
LIVEKIT_API_SECRET=<your-secret>

# Frontend needs:
NEXT_PUBLIC_LIVEKIT_URL=wss://mahira-5efzx2ms.livekit.cloud

# Backend needs (for token generation):
LIVEKIT_API_KEY=<your-key>
LIVEKIT_API_SECRET=<your-secret>
```

---

## Summary

**Current State:**
- ✅ Agent worker is running and healthy
- ✅ Connected to LiveKit Cloud
- ❌ No room connection/job received

**Next Steps:**
1. **Verify frontend is connecting** to a LiveKit room
2. **Enable microphone** in frontend
3. **Check agent dispatch configuration**
4. **Test with LiveKit Playground** to isolate issue

The agent code is working correctly. The issue is in the connection/dispatch flow, not the agent itself.

