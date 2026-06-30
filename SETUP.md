# VentAlert – Developer Setup Guide

> Python 3.11+ required | Windows / macOS / Linux

---

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.11+ | `python --version` |
| pip | latest | `pip --version` |
| Git | any | `git --version` |
| ngrok | any | `ngrok --version` (optional) |

---

## 1. Clone the Repository

```bash
git clone https://github.com/krithika0609/ventilator-monitoring-system.git
cd ventilator-monitoring-system
```

---

## 2. Create a Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` in your prompt when activated.

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework + WebSocket support |
| `uvicorn[standard]` | ASGI server to run FastAPI |
| `python-dotenv` | Load `.env` file into environment variables |
| `websockets` | WebSocket client/server library |
| `pydantic` | Data validation (used by FastAPI) |

---

## 4. Configure Environment Variables

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` and fill in your values:

```env
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
AI_MODEL=gpt-4o
WEBSOCKET_HOST=localhost
WEBSOCKET_PORT=8765
API_HOST=0.0.0.0
API_PORT=8000
```

> **Note:** `.env` is git-ignored. Never commit it.

---

## 5. Run the Backend

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Expected output:
```
INFO  VentAlert v1.0.0 starting up...
INFO  WebSocket endpoint: ws://localhost:8000/ws
INFO  Uvicorn running on http://0.0.0.0:8000
INFO  Vital broadcast loop started
```

---

## 6. Run the Simulator (standalone test)

The simulator runs independently. In a second terminal:

```bash
# Normal mode — generates vitals every 2 seconds
python simulator.py

# Test mode — forces SpO2 critical alerts every 3rd reading
python simulator.py --test
```

> **Note:** When the FastAPI backend is running, it imports and calls the simulator internally. You only need to run `simulator.py` standalone for testing or debugging.

---

## 7. Open the Frontend Dashboard

Open `frontend/index.html` directly in your browser:

```bash
# Windows
start frontend\index.html

# macOS
open frontend/index.html

# Linux
xdg-open frontend/index.html
```

Or serve it via Python's built-in HTTP server (recommended for full feature support):

```bash
python -m http.server 3000 --directory frontend
```

Then open: **http://localhost:3000**

---

## 8. Connect to WebSocket

The dashboard connects automatically. To test manually:

**Browser console (F12):**
```javascript
// Doctor connection
const ws = new WebSocket("ws://localhost:8000/ws?role=doctor");
ws.onmessage = (e) => console.log(JSON.parse(e.data));

// Send an instruction
ws.send(JSON.stringify({ event: "instruction", message: "Reduce PEEP to 8" }));
```

**Python WebSocket client:**
```bash
pip install websockets
python -c "
import asyncio, websockets, json

async def test():
    async with websockets.connect('ws://localhost:8000/ws?role=doctor') as ws:
        while True:
            msg = await ws.recv()
            print(json.loads(msg))

asyncio.run(test())
"
```

---

## 9. Test in Browser

1. Open `frontend/index.html` in Chrome or Firefox
2. Set role to **Doctor** in the UI dropdown
3. Verify vital cards update every 2 seconds
4. Open a second tab — set role to **Nurse**
5. In Doctor tab, type an instruction and send
6. Verify the Nurse tab receives the instruction
7. Run `python simulator.py --test` to trigger SpO2 alerts
8. Verify alert banner appears on both tabs

---

## 10. Test Multiple Devices (LAN)

1. Find your machine's local IP:
   ```powershell
   # Windows
   ipconfig
   # Look for IPv4 Address e.g. 192.168.1.100
   ```

2. Run backend binding to all interfaces (already default):
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```

3. On another device on the same Wi-Fi, open:
   ```
   http://192.168.1.100:3000        ← Frontend
   ws://192.168.1.100:8000/ws?role=nurse   ← WebSocket
   ```

---

## 11. Run Using ngrok (Remote / Internet Access)

ngrok creates a public URL for your local server.

**Install ngrok:** https://ngrok.com/download

**Start your backend first:**
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

**In a new terminal:**
```bash
ngrok http 8000
```

Expected output:
```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:8000
```

**Update your frontend** to use the ngrok WebSocket URL:
```javascript
// Replace localhost with your ngrok URL
const ws = new WebSocket("wss://abc123.ngrok-free.app/ws?role=doctor");
```

> **Note:** `wss://` (secure) is required for ngrok HTTPS URLs. `ws://` only works for localhost.

---

## Expected Project Structure

```
ventilator-monitoring-system/
│
├── simulator.py              ← DO NOT MODIFY
│
├── backend/
│   ├── __init__.py
│   ├── config.py             ← All constants
│   ├── alert_engine.py       ← Threshold checks
│   ├── weaning_engine.py     ← Weaning scoring
│   └── main.py               ← FastAPI + WebSocket
│
├── frontend/
│   └── index.html            ← Browser dashboard
│
├── docs/
│   ├── VentAlert System Architecture.md
│   ├── data-schema.json
│   └── api-contracts.md
│
├── .env                      ← Local secrets (git-ignored)
├── .env.example              ← Template
├── .gitignore
├── requirements.txt
├── SETUP.md                  ← This file
└── README.md
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'backend'`
**Cause:** Running Python from the wrong directory.  
**Fix:** Always run from the project root:
```bash
cd ventilator-monitoring-system
uvicorn backend.main:app --reload
```

### `Address already in use` (port 8000)
**Fix:**
```bash
# Windows — find and kill the process on port 8000
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### WebSocket connection refused
**Check:**
1. Backend is running (`uvicorn` process active)
2. Correct URL: `ws://localhost:8000/ws?role=doctor`
3. Firewall not blocking port 8000

### ngrok `ERR_NGROK_3004` (tunnel expired)
**Fix:** Free ngrok sessions expire after a few hours. Restart ngrok:
```bash
ngrok http 8000
```
Then update the WebSocket URL in the frontend.

### Vitals not updating
**Check:**
1. Backend started successfully (check terminal for errors)
2. `generate_reading` from `simulator.py` is importable
3. Run: `python -c "from simulator import generate_reading; print(generate_reading())"`

### Alert not firing
**Check:**
1. Run `python simulator.py --test` to force SpO2 critical readings
2. Verify `alert_engine.check_thresholds` works:
   ```bash
   python -c "from backend.alert_engine import check_thresholds; print(check_thresholds({'SpO2': 85}))"
   ```

### `pip install` fails with permissions error
**Fix (Windows):**
```powershell
pip install -r requirements.txt --user
```

---

## Alert Latency Expectation

| Stage | Expected Time |
|-------|--------------|
| Simulator generates reading | 0ms |
| alert_engine evaluates | < 1ms |
| Server broadcasts via WebSocket | < 10ms |
| Browser DOM updates | < 100ms |
| **Total end-to-end** | **< 3 seconds** |

> The 2-second `DATA_GENERATION_INTERVAL` in `config.py` is the dominant latency factor.
