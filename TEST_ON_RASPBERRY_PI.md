# Testing HealthDiary on Raspberry Pi

This guide will help you quickly test your HealthDiary project after cloning it.

---

## Step 1: Navigate to Project Directory

```bash
cd ~/HealthDiary
# Or if you cloned to a different location:
# cd /path/to/HealthDiary
```

---

## Step 2: Check Python Version

```bash
python3 --version
# Should be Python 3.9 or higher
```

---

## Step 3: Create Virtual Environment

```bash
python3 -m venv .venv
```

---

## Step 4: Activate Virtual Environment

```bash
source .venv/bin/activate
```

You should see `(.venv)` in your prompt, like:
```
pi@raspberrypi:~/HealthDiary $ (.venv)
```

---

## Step 5: Upgrade pip

```bash
pip install --upgrade pip setuptools wheel
```

---

## Step 6: Install Dependencies

```bash
pip install -r backend/requirements.txt
```

This will install:
- FastAPI
- Uvicorn
- SQLAlchemy
- HTTPX
- Pydantic
- python-multipart

---

## Step 7: Create Required Directories

```bash
mkdir -p backend/app/data
mkdir -p temp_audio
```

---

## Step 8: Configure Environment Variables

Create a `.env` file with your API keys:

```bash
nano .env
```

Add (replace with your actual API key):
```
QWEN_ENDPOINT=https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions
QWEN_API_KEY=your_api_key_here
QWEN_MODEL=qwen2.5-7b-instruct
QWEN_SPEECH_MODEL=qwen2.5-omni-7b
```

Save: Ctrl+X, then Y, then Enter

**Or if you don't have API keys yet**, you can skip this - the app will use heuristic/fallback mode (limited functionality, but it will still run).

---

## Step 9: Start the Server

**Option A: Simple start**
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

**Option B: Using the startup script** (if you ran setup script)
```bash
./start_healthdiary.sh
```

**Option C: Load environment from .env file**
```bash
# Install python-dotenv first
pip install python-dotenv

# Then create a startup script or run manually:
export $(cat .env | grep -v '^#' | xargs)
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

You should see output like:
```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

## Step 10: Test the Server

### Test 1: Health Check (From Raspberry Pi)

Open a **new terminal** (keep the server running in the first terminal), and run:

```bash
curl http://localhost:8000/healthz
```

Expected response:
```json
{"ok": true}
```

### Test 2: Health Check (From Another Device)

Find your Raspberry Pi's IP address:
```bash
hostname -I
```

From another computer/phone on the same network, open a browser or use curl:
```
http://YOUR_PI_IP:8000/healthz
```

Or use curl:
```bash
curl http://YOUR_PI_IP:8000/healthz
```

### Test 3: Check API Documentation

From a browser (on Pi or another device):
```
http://YOUR_PI_IP:8000/docs
```

This shows the interactive API documentation (Swagger UI).

### Test 4: Demo UI

If available:
```
http://YOUR_PI_IP:8000/demo
```

---

## Step 11: Test API Endpoints

### Test Diary Entry (Simple)
```bash
curl -X POST "http://localhost:8000/diary" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-123",
    "ts": "2025-01-27T10:00:00Z",
    "symptom_raw": "headache after lunch",
    "input_mode": "text",
    "fields": {},
    "provenance": {}
  }'
```

Expected response:
```json
{"id": "some-uuid", "ok": true}
```

### Test List Entries
```bash
curl "http://localhost:8000/diary?user_id=test-user-123"
```

---

## Troubleshooting

### Issue: "ModuleNotFoundError" or "No module named 'fastapi'"
**Solution**: Make sure virtual environment is activated:
```bash
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### Issue: "Address already in use" (port 8000)
**Solution**: Kill the process or use a different port:
```bash
# Find process on port 8000
sudo lsof -i :8000
# Kill it
sudo kill -9 <PID>

# OR use different port
uvicorn backend.app.main:app --host 0.0.0.0 --port 8001
```

### Issue: Can't connect from other devices
**Solution**: 
- Check firewall: `sudo ufw status`
- Verify server is running: `curl http://localhost:8000/healthz`
- Check IP address: `hostname -I`
- Make sure you're using `--host 0.0.0.0` (not `127.0.0.1`)

### Issue: Database errors
**Solution**: Make sure data directory exists:
```bash
mkdir -p backend/app/data
```

The database will be created automatically on first use.

### Issue: "QWEN_ENDPOINT not configured"
**Solution**: This is normal if you didn't set up API keys. The app will use heuristic/fallback mode. It will still work, but with limited functionality.

---

## Quick Test Script

You can also use the automated setup script if available:

```bash
cd ~/HealthDairy
chmod +x setup_raspberry_pi.sh
./setup_raspberry_pi.sh
```

Then manually start the server:
```bash
source .venv/bin/activate
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

---

## Running in Background (Optional)

To run the server in the background:

```bash
# Start in background
nohup uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &

# View logs
tail -f server.log

# Stop it
pkill -f uvicorn
```

Or better: Set up as a systemd service (see `RASPBERRY_PI_SETUP.md` Part 9 for details).

---

## Next Steps

Once the server is running and tested:

1. **Set up as a system service** (auto-start on boot) - see `RASPBERRY_PI_SETUP.md`
2. **Configure audio devices** (if you have ICS-43434/MAX98357A connected)
3. **Test audio recording/playback** endpoints
4. **Connect your frontend/client** application

---

## Summary Commands

```bash
# Navigate to project
cd ~/HealthDairy

# Activate virtual environment
source .venv/bin/activate

# Start server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# In another terminal, test:
curl http://localhost:8000/healthz
```

