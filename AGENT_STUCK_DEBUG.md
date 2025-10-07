# Agent Stuck at "Listening" - Debug Guide

## 🔴 The Problem

Your agent starts successfully but then immediately stops:

```
INFO:livekit.agents:registered worker
2025-10-07 22:30:12,389 - INFO livekit.agents - registered worker
Stopping Container
```

The key issue is this warning:
```
WARNING:watchfiles.main:received signal 15, raising KeyboardInterrupt
```

**Signal 15 (SIGTERM)** means the container is being killed by the deployment platform, not by your code.

---

## 🔍 Root Causes

### 1. Health Check Failure
Railway (or your platform) may have health checks that expect HTTP responses, but LiveKit agents don't expose HTTP endpoints by default.

### 2. Idle Timeout
Some platforms kill containers that don't receive traffic within a certain time.

### 3. No Job Assignment
The agent registers but if no LiveKit room/job is assigned quickly, the platform might think it's idle.

### 4. Missing Keep-Alive
The platform expects some signal that the app is alive and working.

---

## ✅ Solutions

### Solution 1: Add Health Check Endpoint (Recommended)

Add a simple HTTP health endpoint so Railway knows the agent is alive:

```python
# Add at the top of agent.py
from aiohttp import web
import asyncio

# Add before entrypoint function
async def health_check_server():
    """Simple HTTP server for health checks"""
    async def health(request):
        return web.Response(text="OK", status=200)
    
    app = web.Application()
    app.router.add_get('/health', health)
    app.router.add_get('/', health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("[HEALTH] HTTP health check server running on port 8080")

# Modify the main block
if __name__ == "__main__":
    # Start health check server in background
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(health_check_server())
    
    # Run the agent
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        initialize_process_timeout=60,
    ))
```

Then in Railway, set:
- **Health Check Path**: `/health`
- **Health Check Port**: `8080`

### Solution 2: Increase Timeouts

In your Railway settings:
- Set health check timeout to 60 seconds
- Set health check interval to 30 seconds
- Set restart policy to "on-failure" not "always"

### Solution 3: Add Better Logging

Add this to see exactly when/why the agent exits:

```python
import signal

def handle_sigterm(signum, frame):
    print(f"[SIGNAL] Received signal {signum}, initiating graceful shutdown...")
    # Don't exit immediately, let the agent finish current job
    raise KeyboardInterrupt()

# Add in main block
if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_sigterm)
    print("[MAIN] SIGTERM handler registered")
    
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        initialize_process_timeout=60,
    ))
```

### Solution 4: Check Railway Configuration

Make sure your Railway service is configured as:
- **Type**: Worker (not Web Service with auto-sleep)
- **Region**: Same as LiveKit (Singapore in your logs)
- **Restart Policy**: On-failure
- **Auto-sleep**: Disabled

---

## 🔧 Quick Fix Implementation

Here's the minimal change to add health checks:

1. Install aiohttp:
```bash
pip install aiohttp
# Add to requirements.txt
```

2. Add this code to agent.py after imports:

```python
from aiohttp import web
import threading

def start_health_server():
    """Background HTTP server for health checks"""
    async def health(request):
        return web.Response(text="OK\n", status=200)
    
    async def run_server():
        app = web.Application()
        app.router.add_get('/health', health)
        app.router.add_get('/', health)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        print("[HEALTH] ✓ Health check server running on :8080")
        
        # Keep server running
        while True:
            await asyncio.sleep(3600)
    
    # Run in background thread
    def thread_target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_server())
    
    thread = threading.Thread(target=thread_target, daemon=True)
    thread.start()
```

3. Call it in main:
```python
if __name__ == "__main__":
    start_health_server()  # Add this line
    
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        initialize_process_timeout=60,
    ))
```

---

## 🧪 Testing

### Test Locally
```bash
# Terminal 1: Run agent
python agent.py

# Terminal 2: Test health endpoint
curl http://localhost:8080/health
# Should return: OK
```

### Test in Railway
1. Deploy with health check code
2. Check logs for: `[HEALTH] ✓ Health check server running on :8080`
3. In Railway settings, set Health Check Path to `/health`
4. Wait 1-2 minutes for health checks to pass

---

## 🔍 Additional Debugging

If still having issues, add this at the very start of your entrypoint:

```python
async def entrypoint(ctx: agents.JobContext):
    print("="*80)
    print("[ENTRYPOINT] 🚀 AGENT STARTING")
    print(f"[ENTRYPOINT] Room: {ctx.room.name}")
    print(f"[ENTRYPOINT] Room SID: {ctx.room.sid}")
    print(f"[ENTRYPOINT] Job ID: {ctx.job.id if ctx.job else 'No job'}")
    print("="*80)
    
    # ... rest of entrypoint
```

This will show if the entrypoint is even being called when a room is created.

---

## 📊 Expected Behavior After Fix

### Without Health Check (Current - BAD)
```
registered worker
Stopping Container  ← Platform kills it
```

### With Health Check (After Fix - GOOD)
```
[HEALTH] ✓ Health check server running on :8080
registered worker
[Health checks passing...]
[Agent stays alive waiting for jobs]
```

---

## 🎯 Most Likely Issue

Based on your logs, the most likely issue is:

1. ✅ Agent starts correctly
2. ✅ Registers with LiveKit
3. ❌ Railway doesn't see HTTP health checks
4. ❌ Railway thinks app is unhealthy/idle
5. ❌ Railway sends SIGTERM to kill it

**Solution**: Add the health check HTTP endpoint above.

---

## 📞 Alternative: Use LiveKit Cloud Agents

If the health check doesn't solve it, consider using LiveKit Cloud's managed agents instead of self-hosting on Railway. They handle all this automatically.

---

## 🚨 Emergency Workaround

If you need it working RIGHT NOW without code changes:

1. Railway → Settings
2. Change service type from "Web Service" to "Worker"
3. Disable health checks completely
4. Set restart policy to "never"

This will keep the container running but is not a proper long-term solution.

