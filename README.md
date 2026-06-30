# Ventilator Patient Data Simulator

A Python-based simulator that generates real-time physiological data for a ventilated patient. This tool simulates key patient vitals continuously and outputs them in structured JSON format, making it ideal for healthcare monitoring dashboards, streaming telemetry, or FastAPI WebSocket integrations.

## Features

- **Continuous Simulation**: Emits a reading for a randomly selected vital parameter every 2 seconds.
- **Realistic Data Modeling**: Generates normal, physiological values most of the time, with realistic ranges for each vital parameter.
- **Emergency Simulation**: Introduces abnormal spikes/drops with a 10-15% probability to simulate clinical emergency scenarios (e.g., desaturation, tachycardias, hypercapnia).
- **Multi-Level Alarm Evaluation**: Automatically determines the status (`NORMAL`, `ALARM`, or `CRITICAL`) of each reading and maps it to the relevant physiological threshold.
- **WebSocket/API Ready**: Structured JSON outputs make it easy to stream via WebSockets or expose in REST endpoints.

## Vital Signs Monitored & Thresholds

| Vital Sign | Abbreviation | Normal Range | Alarm Threshold | Critical Threshold |
| :--- | :--- | :--- | :--- | :--- |
| **Oxygen Saturation** | SpO2 | 95% - 100% | < 95% | < 90% |
| **Heart Rate** | HR | 60 - 100 bpm | < 60 bpm or > 100 bpm | < 50 bpm or > 120 bpm |
| **Respiratory Rate** | RR | 12 - 20 breaths/min | < 12 bpm or > 20 bpm | > 30 bpm |
| **Fraction of Inspired Oxygen** | FiO2 | 21% - 40% | > 40% | > 60% |
| **Positive End-Expiratory Pressure** | PEEP | 5 - 10 cmH2O | < 5 cmH2O or > 10 cmH2O | > 15 cmH2O |
| **Tidal Volume** | TV | 400 - 600 mL | < 400 mL or > 600 mL | < 300 mL |

## Output Format

The simulator prints standard JSON objects of the following schema to standard output:

```json
{
  "vital": "SpO2",
  "value": 87,
  "threshold": 90,
  "timestamp": "2026-06-04T10:20:15",
  "status": "CRITICAL"
}
```

## How to Run

Execute the script using any Python 3 environment:

```bash
python simulator.py
```

Enable test mode (forces periodic SpO2 alerts):

```bash
python simulator.py --test
```

---

## Backend – `backend/` Package

### Structure

```
ventilator-monitoring-system/
│
├── simulator.py              # Real-time vitals generator (do not modify)
│
├── backend/
│   ├── __init__.py           # Package descriptor
│   ├── alert_engine.py       # Threshold checking + alert event emission
│   └── weaning_engine.py     # Weaning readiness scoring framework
│
├── README.md
└── requirements.txt
```

### `alert_engine` – Threshold Alerts

```python
from backend.alert_engine import check_thresholds, emit_alert_event

vitals = {
    "SpO2": 87, "HR": 128, "RR": 18,
    "FiO2": 35, "PEEP": 8, "Tidal Volume": 520,
}

alerts = check_thresholds(vitals)
# Returns a list of alert dicts – one per breached threshold

for alert in alerts:
    event = emit_alert_event(alert)
    # {"event": "alert", "data": { ... alert object ... }}
```

Each alert object schema:

```json
{
  "type"      : "alert",
  "vital"     : "SpO2",
  "value"     : 87,
  "threshold" : "<90",
  "severity"  : "CRITICAL",
  "timestamp" : "2026-06-26T18:30:00",
  "message"   : "Critical oxygen level detected"
}
```

### `weaning_engine` – Readiness Scoring

```python
from backend.weaning_engine import calculate_weaning_score

score_report = calculate_weaning_score(vitals)
# {
#   "score"            : 0,
#   "criteria_met"     : [],
#   "criteria_not_met" : [],
#   "readiness_status" : "PENDING_CLINICAL_APPROVAL"
# }
```

> **⚠ Clinical criteria pending**  
> `WEANING_CRITERIA` in `weaning_engine.py` is empty until Dr. Mugesh's
> approved clinical thresholds are inserted. The scoring engine is fully
> functional once criteria are added.

### Dependencies

No third-party packages required. The backend uses Python standard
library only (`datetime`). See `requirements.txt` for the optional
FastAPI/uvicorn lines needed when the REST + WebSocket layer is added.
