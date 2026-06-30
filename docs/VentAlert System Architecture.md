# VentAlert – System Architecture

> Version 1.0.0 | Real-time Ventilator Monitoring System

---

## 1. Overall Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        VentAlert System                             │
│                                                                     │
│   ┌──────────────┐                                                  │
│   │  simulator.py │  Generates ventilator vitals every 2 seconds   │
│   │  (Python)    │  SpO2, HR, RR, FiO2, PEEP, Tidal Volume        │
│   └──────┬───────┘                                                  │
│          │  Python function call (generate_reading)                 │
│          ▼                                                           │
│   ┌──────────────┐     ┌──────────────────┐                        │
│   │  FastAPI     │────▶│  alert_engine.py  │  Threshold checks     │
│   │  backend/    │     │  weaning_engine   │  Severity scoring     │
│   │  main.py     │     └──────────────────┘                        │
│   └──────┬───────┘                                                  │
│          │  WebSocket (ws://localhost:8000/ws)                      │
│          ▼                                                           │
│   ┌──────────────────────────────────────┐                         │
│   │        Browser Dashboard             │                         │
│   │  (HTML + CSS + Vanilla JavaScript)   │                         │
│   │                                      │                         │
│   │  • Live vital displays               │                         │
│   │  • Alert notifications               │                         │
│   │  • Doctor / Nurse messaging          │                         │
│   │  • Weaning score panel               │                         │
│   └──────┬───────────────────────────────┘                         │
│          │                                                           │
│          ▼  (Future – Phase 2)                                      │
│   ┌──────────────┐                                                  │
│   │  OpenAI API  │  Clinical AI suggestions, patient summaries     │
│   │  (GPT-4o)    │  Weaning predictions                            │
│   └──────┬───────┘                                                  │
│          │                                                           │
│          ▼                                                           │
│   ┌──────────────────────────────┐                                  │
│   │  Doctor / Nurse Workstation  │  Reviews AI output + acts       │
│   └──────────────────────────────┘                                  │
│                                                                     │
│   ┌──────────────┐                                                  │
│   │    ngrok     │  Exposes localhost to internet (remote access)  │
│   └──────────────┘                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Complete Data Flow Explanation

### Step-by-step flow:

```
1. simulator.py::generate_reading()
       │
       │  Returns: { "vital": "SpO2", "value": 92, "status": "ALARM", ... }
       ▼
2. backend/main.py  (background asyncio task, every 2 seconds)
       │
       │  Wraps reading in event="vital_update"
       │  Passes reading dict to alert_engine.check_thresholds()
       ▼
3. alert_engine.py::check_thresholds()
       │
       │  Returns: [] if normal  OR  [{ alert object }, ...]
       ▼
4. ConnectionManager.broadcast()
       │
       │  Sends vital_update JSON to ALL connected WebSocket clients
       │  If alerts exist → sends event="alert" to ALL clients
       ▼
5. Browser JavaScript
       │
       │  Receives JSON events
       │  Updates DOM: vital cards, alert banners, waveform history
       ▼
6. Doctor sends instruction via WebSocket
       │
       │  { "event": "instruction", "message": "Increase FiO2 to 40%" }
       │
       │  Server stores it (last 20) + broadcasts to all nurses
       ▼
7. Future: AI API processes instruction + patient context
       │
       │  Returns clinical suggestion
       │  Broadcast as event="ai_suggestion"
       ▼
8. ngrok tunnel (optional)
       │
       │  Makes ws://localhost:8000/ws accessible as wss://xxxx.ngrok.io/ws
       │  Enables mobile / remote access
```

---

## 3. Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| **Simulator** | `simulator.py` | Generates realistic ventilator vitals with configurable probability of abnormal readings. Runs independently. |
| **Config** | `backend/config.py` | Single source of truth for all constants — thresholds, vital names, WebSocket config, AI keys (from env). |
| **Alert Engine** | `backend/alert_engine.py` | Stateless function that evaluates vitals against thresholds. Returns structured alert objects. No I/O. |
| **Weaning Engine** | `backend/weaning_engine.py` | Scores patient readiness for ventilator weaning. Criteria-driven, awaiting clinical input. |
| **FastAPI Backend** | `backend/main.py` | Orchestrates everything. Hosts WebSocket endpoint, runs simulator loop, manages connections, broadcasts events. |
| **Connection Manager** | `backend/main.py::ConnectionManager` | Manages all WebSocket clients, roles, instruction history. Handles connect/disconnect/broadcast. |
| **Browser Dashboard** | `frontend/index.html` | Displays live vitals, alerts, messaging UI. Connects to WebSocket. Role-aware (doctor/nurse). |
| **AI Layer** | `backend/main.py` (placeholder) | Future: summarize patient, predict weaning, generate clinical suggestions via OpenAI GPT-4o. |
| **ngrok** | External tool | Creates a public HTTPS/WSS tunnel to the local FastAPI server for remote/mobile access. |
| **GitHub** | Remote repo | Version control, collaboration, CI/CD pipeline (future). |

---

## 4. Technology Stack

### Python 3.11+
**Why chosen:** The entire scientific and medical computing ecosystem is Python-first. `simulator.py`, `alert_engine.py`, and `weaning_engine.py` are all Python. FastAPI and asyncio give us production-grade async performance in the same language.

### FastAPI
**Why chosen:** Fastest Python web framework. Native async/await support. Built-in WebSocket handling. Automatic OpenAPI docs. Type-safe with Pydantic. Production deployable via uvicorn. Ideal for real-time medical systems where latency matters.

### WebSocket (via FastAPI + websockets library)
**Why chosen:** HTTP polling would introduce 2–10 second latency. WebSocket provides a persistent, full-duplex channel. This is essential for alert latency requirements (< 3 seconds). Also enables doctor → nurse push messaging without polling.

### HTML5 + CSS + Vanilla JavaScript
**Why chosen:** No framework overhead. Every nurse/doctor workstation can open a browser tab. No build step required. The frontend is a single `index.html` file that works offline and on mobile. Zero dependencies = zero supply chain risk in a clinical environment.

### ngrok
**Why chosen:** Clinicians need to access the dashboard from tablets, phones, and remote workstations. ngrok provides instant HTTPS + WSS tunneling without firewall configuration or cloud deployment. Perfect for rapid deployment in ICU settings.

### OpenAI API – GPT-4o (Future Phase 2)
**Why chosen:** Best-in-class clinical language understanding. Can interpret ventilator context and generate human-readable summaries for nurses. The `AI_MODEL` constant in `config.py` allows swapping to Claude or any other model with a single config change.

### GitHub
**Why chosen:** Version control with pull request workflow. Every team member (Dr. Mugesh, developers, nurses) can review changes. GitHub Actions enables automated testing. The `.env.example` pattern keeps secrets out of version control.

### python-dotenv
**Why chosen:** Loads `.env` files into `os.environ` at startup. Prevents API keys from being hardcoded. Required by `backend/config.py` to resolve `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `WEBSOCKET_HOST`, etc.

---

## 5. Folder Structure

```
ventilator-monitoring-system/
│
├── simulator.py                    ← Vital data generator (DO NOT MODIFY)
│
├── backend/
│   ├── __init__.py                 ← Package init
│   ├── config.py                   ← All constants (single source of truth)
│   ├── alert_engine.py             ← Threshold evaluation + alert objects
│   ├── weaning_engine.py           ← Weaning readiness scoring framework
│   └── main.py                     ← FastAPI app, WebSocket, ConnectionManager
│
├── frontend/
│   └── index.html                  ← Browser dashboard (single file)
│
├── docs/
│   ├── VentAlert System Architecture.md   ← This document
│   ├── data-schema.json            ← JSON contract for all event payloads
│   └── api-contracts.md            ← WebSocket event documentation
│
├── .env                            ← Local secrets (git-ignored)
├── .env.example                    ← Template for environment variables
├── .gitignore                      ← Excludes .env, __pycache__, venv
├── requirements.txt                ← Python dependencies
├── SETUP.md                        ← Developer onboarding guide
└── README.md                       ← Project overview
```

---

## 6. Backend Workflow

```
Application Startup
    │
    ├── FastAPI app initialises
    ├── Logging configured
    ├── ConnectionManager instantiated
    └── asyncio background task: broadcast_vitals_loop() started
            │
            │  Every DATA_GENERATION_INTERVAL (2 seconds):
            │
            ├── simulator.generate_reading() → one vital reading
            ├── Wrap as event="vital_update" → broadcast to all clients
            ├── alert_engine.check_thresholds({vital: value})
            │       │
            │       ├── No alerts → continue
            │       └── Alert(s) found →
            │               emit_alert_event(alert) → broadcast to all clients
            └── weaning_engine.calculate_weaning_score() (on demand or periodic)

WebSocket Client Connects (/ws?role=doctor|nurse)
    ├── ConnectionManager.connect() called
    ├── Role stored
    ├── Log: "Client connected, role=doctor"
    └── ConnectionManager.broadcast_history() → sends last 20 instructions

Doctor sends message
    ├── Server receives { "event": "instruction", "message": "..." }
    ├── Timestamp added
    ├── Stored in instruction_history (capped at 20)
    └── ConnectionManager.broadcast_instruction() → all clients receive it

Client Disconnects
    ├── ConnectionManager.disconnect()
    └── Log: "Client disconnected"
```

---

## 7. Frontend Workflow

```
Browser opens index.html
    │
    ├── JavaScript creates WebSocket:
    │       ws://localhost:8000/ws?role=doctor   (or ?role=nurse)
    │
    ├── On connection:
    │       Display "Connected" indicator
    │
    ├── On message received:
    │       Parse JSON → check event field
    │
    │       event = "vital_update"
    │           → Update vital card (SpO2, HR, RR, FiO2, PEEP, TV)
    │           → Append to waveform history
    │
    │       event = "alert"
    │           → Show alert banner with severity colour
    │           → Play audio beep (CRITICAL)
    │           → Log to alert history panel
    │
    │       event = "instruction"
    │           → Show in doctor console / messaging panel
    │
    │       event = "history"
    │           → Populate instruction history on connect
    │
    │       event = "weaning_score"
    │           → Update weaning readiness panel
    │
    │       event = "ai_suggestion"
    │           → Display AI suggestion card
    │
    └── Doctor UI: text input → send instruction via WebSocket
```

---

## 8. AI Workflow (Phase 2 – Not Yet Implemented)

```
Trigger: Alert generated OR doctor requests summary
    │
    ├── Collect patient context:
    │       { last 10 vitals, active alerts, weaning score, doctor notes }
    │
    ├── Call OpenAI API (GPT-4o):
    │       POST https://api.openai.com/v1/chat/completions
    │       Model: AI_MODEL from config.py (env var)
    │       System prompt: clinical ICU context
    │       User prompt: patient data JSON
    │
    ├── Parse response → extract clinical suggestion text
    │
    └── Broadcast as event="ai_suggestion" to all connected clients
```

---

## 9. Alert Workflow

```
simulator.generate_reading() → { vital: "SpO2", value: 87 }
    │
    ├── alert_engine.check_thresholds({"SpO2": 87})
    │       │
    │       └── SpO2 < 90 → CRITICAL threshold breached
    │               Returns: [{ type: "alert", vital: "SpO2",
    │                           value: 87, severity: "CRITICAL",
    │                           message: "Critical oxygen level detected", ... }]
    │
    ├── emit_alert_event(alert)
    │       → { "event": "alert", "data": { alert object } }
    │
    ├── ConnectionManager.broadcast_alert()
    │       → Sends to ALL connected WebSocket clients
    │
    └── Client browser:
            → Red alert banner
            → Audio beep
            → Alert logged in history
            Target latency: < 3 seconds end-to-end
```

---

## 10. Weaning Workflow

```
Trigger: Periodic or on-demand (doctor requests score)
    │
    ├── Collect current full vitals snapshot
    │       { SpO2, HR, RR, FiO2, PEEP, Tidal Volume }
    │
    ├── weaning_engine.calculate_weaning_score(vitals)
    │       │
    │       ├── WEANING_CRITERIA is empty → PENDING_CLINICAL_APPROVAL
    │       └── Once populated by Dr. Mugesh:
    │               Score criteria → weighted total
    │               Compare to WEANING_READY_THRESHOLD (80%)
    │               Return: READY | BORDERLINE | NOT_READY
    │
    └── Broadcast as event="weaning_score" to all clients
```
