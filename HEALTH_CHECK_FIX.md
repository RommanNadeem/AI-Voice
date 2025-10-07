# 🏥 Health Check Fix - Agent Stuck at "Listening"

## ✅ What Was Fixed

Your agent was being killed by Railway because it didn't respond to health checks. Railway was sending SIGTERM (signal 15) to kill the container because it thought the service was unhealthy.

### Changes Made:

1. **Added HTTP Health Check Server** (`agent.py`)
   - Runs on port 8080 in background thread
   - Responds to `GET /` and `GET /health` with `200 OK`
   - Lets Railway know the agent is alive and healthy

2. **Updated Main Block** (`agent.py`)
   - Starts health server before LiveKit agent
   - Added startup logging for better visibility

---

## 🔧 What to Configure in Railway

### Option 1: Automatic (Recommended)

Railway should auto-detect the health endpoint. Just wait 1-2 minutes after deployment.

### Option 2: Manual Configuration

If it doesn't auto-detect, configure manually in Railway:

1. Go to your service → **Settings** → **Health Checks**
2. Set these values:
   ```
   Health Check Path: /health
   Health Check Port: 8080
   Health Check Timeout: 30
   Health Check Interval: 20
   ```
3. Save and redeploy

---

## 📊 Expected Logs After Fix

### Before (BAD - Agent Gets Killed):
```
registered worker
WARNING:watchfiles.main:received signal 15, raising KeyboardInterrupt
Stopping Container
```

### After (GOOD - Agent Stays Alive):
```
🚀 Starting Companion Agent
[HEALTH] Background health check thread started
[HEALTH] ✓ HTTP health check server running on port 8080
[MAIN] Starting LiveKit agent worker...
registered worker
[Agent stays running, waiting for jobs...]
```

---

## 🧪 Testing the Health Endpoint

### Test Locally:
```bash
# Terminal 1: Run agent
python agent.py

# Terminal 2: Test health
curl http://localhost:8080/health
# Should return: OK
```

### Test on Railway:
```bash
# Replace YOUR-APP with your Railway URL
curl https://YOUR-APP.up.railway.app/health
# Should return: OK
```

---

## 🐛 If Still Having Issues

### Issue 1: Port Not Exposed
Railway needs to know about port 8080. Add to Railway env vars:
```
PORT=8080
```

### Issue 2: Still Getting Killed
Check Railway service settings:
- Service type should be **Worker** or **Web Service**
- Auto-sleep should be **Disabled**
- Restart policy should be **On Failure** (not "Always")

### Issue 3: Health Check Failing
Check Railway logs for:
```
[HEALTH] ✓ HTTP health check server running on port 8080
```

If you don't see this, there may be a Python dependency issue with `aiohttp`.

---

## 🎯 Root Cause Explained

**The Problem:**
- LiveKit agents are WebSocket-based services
- They don't have HTTP endpoints by default
- Railway (and most platforms) use HTTP health checks
- Without HTTP responses, Railway thought your agent was dead
- Railway sent SIGTERM to kill the "unhealthy" container

**The Solution:**
- Added a tiny HTTP server on port 8080
- It runs in a background thread
- Responds "OK" to health check requests
- Railway now knows the agent is alive and healthy
- Agent stays running indefinitely

---

## 📝 Technical Details

### Health Server Implementation:
```python
# Runs in background thread (daemon)
# Listens on 0.0.0.0:8080
# Routes:
#   GET /health → 200 OK
#   GET /       → 200 OK

# This doesn't interfere with the LiveKit agent
# The agent still handles WebSocket connections normally
```

### Thread Safety:
- Health server runs in separate thread
- Has its own asyncio event loop
- Daemon thread (won't prevent shutdown)
- No shared state with main agent

---

## ✅ Deployment Checklist

- [x] Added health check server code
- [x] Updated requirements.txt (aiohttp already present)
- [ ] Deploy to Railway
- [ ] Wait 1-2 minutes for health checks to pass
- [ ] Check logs for `[HEALTH] ✓ HTTP health check server running`
- [ ] Verify agent no longer gets killed
- [ ] Test with actual LiveKit room

---

## 🚀 Next Steps

1. **Deploy these changes to Railway**
2. **Monitor the logs** - look for the health check startup message
3. **Wait 2-3 minutes** for Railway to detect healthy status
4. **Test with a LiveKit room** to verify agent connects

The agent should now stay alive indefinitely, waiting for LiveKit job assignments!

---

## 📞 Alternative Solutions

If this doesn't work, other options:

1. **Change Railway service type to "Worker"** (no health checks required)
2. **Use LiveKit Cloud's managed agents** (they handle health checks)
3. **Deploy to a different platform** (Render, Fly.io, etc.)

But the health check fix should solve it! 🎉

