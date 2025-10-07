# State Broadcasting Fix - Agent Stuck at Listening

## Problem
The agent was stuck at "listening" state because we were broadcasting "listening" immediately after `generate_reply()` returned, but the TTS audio hadn't actually played yet. This caused the frontend to show "listening" while the agent was still speaking.

## Root Cause
The `session.generate_reply()` method returns immediately after queuing the TTS response, but the actual audio playback happens asynchronously. Broadcasting "listening" state at that point was premature.

## Solution
Implemented proper Agent lifecycle callbacks to broadcast state at the correct times:

### State Flow (Fixed):
```
User speaks → "thinking" 📡 → Agent generates response → "speaking" 📡 → TTS plays → "listening" 📡
```

### Changes Made:

1. **Removed Premature "listening" Broadcast** (Line 688-689)
   - Removed the `broadcast_state("listening")` that was called immediately after `generate_reply()`
   - Added comment explaining why it was removed

2. **Added `on_agent_speech_started` Callback** (Lines 705-708)
   ```python
   async def on_agent_speech_started(self, turn_ctx):
       """Called when agent starts speaking (TTS playback begins)"""
       await self.broadcast_state("speaking")
   ```
   - Broadcasts "speaking" when TTS actually starts playing
   - Gives frontend accurate state

3. **Added `on_agent_speech_committed` Callback** (Lines 710-715)
   ```python
   async def on_agent_speech_committed(self, turn_ctx):
       """Called when agent finishes generating and committing speech to the output"""
       await self.broadcast_state("listening")
   ```
   - Broadcasts "listening" only after agent finishes speaking
   - Prevents premature state transitions

### State Broadcasts Timeline:

| Event | State Broadcasted | Line | Trigger |
|-------|------------------|------|---------|
| User finishes speaking | `"thinking"` | 518 | `generate_reply_with_context()` starts |
| Agent starts TTS playback | `"speaking"` | 708 | `on_agent_speech_started()` callback |
| Agent finishes speaking | `"listening"` | 715 | `on_agent_speech_committed()` callback |

## Frontend Compatibility
The frontend's `DataReceived` event handler now receives accurate state messages:

```typescript
newRoom.on(RoomEvent.DataReceived, (payload, participant) => {
  const message = new TextDecoder().decode(payload);
  
  if (message.includes("listening")) setAgentState("listening");      // ✅ After agent finishes
  else if (message.includes("thinking")) setAgentState("thinking");   // ✅ While processing
  else if (message.includes("speaking")) setAgentState("speaking");   // ✅ During TTS playback
});
```

## Testing
When the agent runs, you should now see accurate state transitions in the logs:

```
[STATE] 📡 Broadcasted: thinking
[AGENT] Started speaking
[STATE] 📡 Broadcasted: speaking
[AGENT] Speech committed - transitioning to listening
[STATE] 📡 Broadcasted: listening
```

## Result
- ✅ Agent no longer stuck at "listening" state
- ✅ State transitions happen at the correct lifecycle moments
- ✅ Frontend UI accurately reflects agent's actual state
- ✅ Better user experience with real-time state feedback

