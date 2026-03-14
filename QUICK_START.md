# 🚀 Quick Start Guide - Fixed Version

## ✅ Fixes Applied

1. **Port Configuration** - Chatbot service now uses port 8000 (was 8002)
2. **Dependencies** - Fixed duplicate/conflicting versions in requirements.txt
3. **Service URLs** - Updated .env to reference correct ports
4. **Health Checks** - Added automatic health checks to start_dev.sh

---

## 🔧 Quick Fix & Start

If chatbot service was failing, run this to fix dependencies:

```bash
# Fix chatbot dependencies
./fix_chatbot_deps.sh

# Stop any running services
bash start_dev.sh stop

# Start all services with correct ports
bash start_dev.sh
```

---

## 📋 Service Ports (Updated)

- **Case Service**: http://localhost:8001
- **Chatbot Service**: http://localhost:8000 ✅ (Changed from 8002)
- **MCP Service**: http://localhost:8003
- **Frontend**: http://localhost:5173

---

## ✅ Verify Everything Works

After starting services, run:

```bash
# Run automated tests
./run_tests.sh
```

**Expected output:**
```
✅ MCP Service is running
✅ Chatbot Service is running
✅ Case Service is running

✓ ALL TESTS PASSED
```

---

## 🐛 Troubleshooting

### Chatbot service fails to start

```bash
# Check logs
tail -f logs/chatbot-service.log

# Common issue: Dependencies
./fix_chatbot_deps.sh

# Or manually:
cd chatbot-service
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Port already in use

```bash
# Find and kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Or stop all services and restart
bash start_dev.sh stop
bash start_dev.sh
```

### ChromaDB ingestion fails

```bash
# Delete and recreate ChromaDB
rm -rf data/chromadb
bash start_dev.sh
# Will automatically re-ingest documents
```

---

## 📝 What Changed

### .env
- `CHATBOT_SERVICE_PORT=8000` (was 8002)
- `CHATBOT_SERVICE_URL=http://chatbot-service:8000`

### start_dev.sh
- Chatbot service starts on port 8000
- Added health checks after startup
- Better status reporting

### chatbot-service/requirements.txt
- Removed duplicate versions
- Consolidated to single version per package

---

## ✨ Running Tests

### Backend Tests
```bash
./run_tests.sh
```

### Frontend Tests
```bash
# Open in browser
open tests/test_frontend_integration.html
```

### Manual Health Check
```bash
curl http://localhost:8000/health  # Chatbot
curl http://localhost:8001/health  # Case service
curl http://localhost:8003/health  # MCP service
```

---

## 🎯 Next Steps

1. **Start services**: `bash start_dev.sh`
2. **Wait for health checks**: Services auto-checked after 3 seconds
3. **Run tests**: `./run_tests.sh`
4. **Start frontend**: `npm run dev`
5. **Open browser**: http://localhost:5173

---

## 📚 Key Files

- `start_dev.sh` - Starts all backend services
- `run_tests.sh` - Runs integration tests
- `fix_chatbot_deps.sh` - Fixes chatbot dependencies
- `.env` - Configuration (ports, URLs, API keys)
- `logs/` - Service logs for debugging

---

**Status**: ✅ All configuration issues fixed!

Run `bash start_dev.sh` to start with correct ports.
