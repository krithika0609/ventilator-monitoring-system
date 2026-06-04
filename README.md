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
