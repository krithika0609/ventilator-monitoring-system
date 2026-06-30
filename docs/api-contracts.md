# VentAlert – WebSocket API Contracts

> Version 1.0.0 | Last updated: 2026-06-30
> WebSocket endpoint: `ws://localhost:8000/ws?role=<doctor|nurse>`

---

## Connection

```
ws://localhost:8000/ws?role=doctor   ← Full access: send + receive
ws://localhost:8000/ws?role=nurse    ← Read-only: receive only
```

**Query parameters:**

| Parameter | Required | Values | Description |
|-----------|----------|--------|-------------|
| `role` | Yes | `doctor`, `nurse` | Determines send permissions and UI access |

On successful connection the server immediately sends an `event="history"` payload containing the last 20 doctor instructions.

---

## Event Reference Table

| # | Event Name | Direction | Sender | Receiver | Trigger Condition |
|---|------------|-----------|--------|----------|-------------------|
| 1 | `vital_update` | Server → Client | FastAPI server | All clients | Every 2 seconds — simulator generates a new reading |
| 2 | `alert` | Server → Client | FastAPI server (alert_engine) | All clients | A vital crosses ALARM or CRITICAL threshold |
| 3 | `instruction` | Bidirectional | Doctor client → Server → All clients | All connected clients | Doctor sends a clinical instruction via the dashboard |
| 4 | `weaning_score` | Server → Client | FastAPI server (weaning_engine) | All clients | On demand or periodic evaluation trigger |
| 5 | `ai_suggestion` | Server → Client | FastAPI server (AI layer) | All clients | Alert triggered or doctor requests patient summary (Phase 2) |
| 6 | `history` | Server → Client | FastAPI server | Newly connected client only | Client connects — server replays last 20 instructions |
| 7 | `client_connected` | Internal | Server | Server log | New WebSocket connection established |
| 8 | `client_disconnected` | Internal | Server | Server log | WebSocket connection closed |

---

## Event Payloads

### 1. `vital_update`

**Direction:** Server → All clients  
**Frequency:** Every 2 seconds (one vital per message)  
**Trigger:** `simulator.generate_reading()` completes

```json
{
  "event": "vital_update",
  "data": {
    "vital": "SpO2",
    "value": 97,
    "threshold": 95,
    "status": "NORMAL",
    "timestamp": "2026-06-30T20:30:00"
  }
}
```

**Status values:**

| Status | Meaning |
|--------|---------|
| `NORMAL` | Value within configured normal range |
| `ALARM` | Value outside normal range but not critical |
| `CRITICAL` | Value has crossed a critical threshold — action required |

---

### 2. `alert`

**Direction:** Server → All clients  
**Trigger:** `alert_engine.check_thresholds()` returns one or more breaches  
**Latency target:** < 3 seconds from threshold breach to client receipt

```json
{
  "event": "alert",
  "data": {
    "type": "alert",
    "vital": "SpO2",
    "value": 87,
    "threshold": "<90",
    "severity": "CRITICAL",
    "timestamp": "2026-06-30T20:30:02",
    "message": "Critical oxygen level detected"
  }
}
```

**Severity levels:**

| Severity | Colour (UI) | Audio | Clinical Action |
|----------|-------------|-------|-----------------|
| `CRITICAL` | Red (#EF4444) | Alarm beep | Immediate intervention |
| `ALARM` | Amber (#F59E0B) | Warning tone | Monitor closely |

**Threshold table (from `config.py`):**

| Vital | ALARM condition | CRITICAL condition |
|-------|----------------|-------------------|
| SpO2 | < 95% | < 90% |
| HR | < 60 or > 100 bpm | < 50 or > 120 bpm |
| RR | < 12 or > 20 br/min | > 30 br/min |
| FiO2 | > 40% | > 60% |
| PEEP | < 5 or > 10 cmH₂O | > 15 cmH₂O |
| Tidal Volume | < 400 or > 600 mL | < 300 mL |

---

### 3. `instruction`

**Direction (send):** Doctor client → Server  
**Direction (broadcast):** Server → All clients  
**Permission:** Only `role=doctor` clients may send  
**Storage:** Server stores last 20 instructions in memory

**Sent by doctor:**
```json
{
  "event": "instruction",
  "message": "Increase FiO2 to 40% — patient showing signs of desaturation."
}
```

**Broadcast by server (timestamp added server-side):**
```json
{
  "event": "instruction",
  "sender": "doctor",
  "message": "Increase FiO2 to 40% — patient showing signs of desaturation.",
  "timestamp": "2026-06-30T20:31:15"
}
```

**Error response (if nurse tries to send):**
```json
{
  "event": "error",
  "message": "Nurses are read-only. Only doctors may send instructions."
}
```

---

### 4. `weaning_score`

**Direction:** Server → All clients  
**Trigger:** On-demand or periodic (every N minutes — configurable)

```json
{
  "event": "weaning_score",
  "data": {
    "score": 0,
    "max_score": 0,
    "criteria_met": [],
    "criteria_not_met": [],
    "readiness_status": "PENDING_CLINICAL_APPROVAL",
    "evaluated_at": "2026-06-30T20:32:00",
    "vitals_snapshot": {
      "SpO2": 97,
      "HR": 78,
      "RR": 16,
      "FiO2": 30,
      "PEEP": 6,
      "Tidal Volume": 480
    }
  }
}
```

**Readiness status values:**

| Status | Meaning |
|--------|---------|
| `PENDING_CLINICAL_APPROVAL` | `WEANING_CRITERIA` is empty — Dr. Mugesh must populate criteria first |
| `READY` | Score ≥ 80% of max — patient may be ready to wean |
| `BORDERLINE` | Score ≥ 50% of max — clinical judgment required |
| `NOT_READY` | Score < 50% of max — continue ventilator support |

---

### 5. `ai_suggestion`

**Direction:** Server → All clients  
**Phase:** 2 (not yet implemented — placeholder returns mock data)  
**Trigger:** CRITICAL alert generated, or doctor requests patient summary

```json
{
  "event": "ai_suggestion",
  "data": {
    "model": "gpt-4o",
    "patient_context": {
      "latest_vital": { "vital": "SpO2", "value": 87, "status": "CRITICAL" },
      "active_alerts": 2,
      "weaning_status": "NOT_READY"
    },
    "suggestion": "Patient SpO2 at 87% — consider increasing FiO2 to 50% and verifying ETT position. Reassess ABG in 30 minutes.",
    "confidence": "HIGH",
    "generated_at": "2026-06-30T20:31:20",
    "disclaimer": "AI-generated suggestion. Requires physician review before clinical action."
  }
}
```

> ⚠️ **IMPORTANT:** AI suggestions are advisory only. No clinical action should be taken based solely on AI output without physician review.

---

### 6. `history`

**Direction:** Server → Newly connected client only  
**Trigger:** Immediately on client connection  
**Purpose:** Replay recent instructions so new connections are brought up to date

```json
{
  "event": "history",
  "data": [
    {
      "event": "instruction",
      "sender": "doctor",
      "message": "Reduce PEEP to 8 — patient tolerating well.",
      "timestamp": "2026-06-30T20:25:10"
    },
    {
      "event": "instruction",
      "sender": "doctor",
      "message": "Increase FiO2 to 40% — patient showing signs of desaturation.",
      "timestamp": "2026-06-30T20:31:15"
    }
  ]
}
```

---

### 7. `client_connected` (Server-side log only)

Not broadcast to clients. Logged by the Python `logging` module.

```
INFO  VentAlert | Client connected   role=doctor  addr=127.0.0.1  total=3
```

---

### 8. `client_disconnected` (Server-side log only)

Not broadcast to clients. Logged by the Python `logging` module.

```
INFO  VentAlert | Client disconnected  role=nurse  total=2
```

---

## Error Handling

| Scenario | Server Response |
|----------|----------------|
| Nurse sends instruction | `{ "event": "error", "message": "Read-only role" }` |
| Malformed JSON received | Logged, connection kept alive |
| Client disconnects unexpectedly | Removed from active pool silently |
| Simulator raises exception | Logged, loop continues after 2-second delay |

---

## Integration Checklist

- [ ] Connect with `?role=doctor` and verify `history` event received on connect
- [ ] Verify `vital_update` arrives every 2 seconds
- [ ] Force low SpO2 via `python simulator.py --test` and verify `alert` event
- [ ] Send instruction from doctor client — verify all clients receive it
- [ ] Connect as `?role=nurse` and verify instruction sending is blocked
- [ ] Request weaning score — verify `PENDING_CLINICAL_APPROVAL` status
- [ ] Verify total alert latency < 3 seconds
