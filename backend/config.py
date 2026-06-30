"""
config.py – VentAlert Backend
==============================
Single source of truth for all application constants.

Every other module (simulator.py, alert_engine.py, weaning_engine.py,
future FastAPI routers) must import from here.  No developer should
hardcode threshold values, WebSocket URLs, or API identifiers in
their own file.

Environment variables
---------------------
Sensitive or deployment-specific values are read from the environment
at import time via ``os.getenv``.  For local development, copy
``.env.example`` to ``.env`` and fill in the real values, then load
them with ``python-dotenv`` (optional dev dependency) before starting
the application.

Sections
--------
1. Project metadata
2. Alert severity levels
3. Vital names
4. Vital normal ranges
5. Vital alarm & critical thresholds
6. Data generation settings
7. WebSocket configuration
8. AI / LLM configuration
9. Weaning readiness thresholds
"""

import os

# ---------------------------------------------------------------------------
# 1. Project metadata
# ---------------------------------------------------------------------------

PROJECT_NAME: str = "VentAlert"
PROJECT_VERSION: str = "1.0.0"
PROJECT_DESCRIPTION: str = (
    "Real-time ventilator monitoring system with alert detection "
    "and weaning readiness scoring."
)

# ---------------------------------------------------------------------------
# 2. Alert severity levels
# ---------------------------------------------------------------------------

SEVERITY_NORMAL: str = "NORMAL"
SEVERITY_ALARM: str = "ALARM"
SEVERITY_CRITICAL: str = "CRITICAL"

# ---------------------------------------------------------------------------
# 3. Vital names  (use these constants everywhere — never bare strings)
# ---------------------------------------------------------------------------

VITAL_SPO2: str = "SpO2"
VITAL_HR: str = "HR"
VITAL_RR: str = "RR"
VITAL_FIO2: str = "FiO2"
VITAL_PEEP: str = "PEEP"
VITAL_TIDAL_VOLUME: str = "Tidal Volume"

# Ordered list — used by the simulator and UI layers
ALL_VITALS: list[str] = [
    VITAL_SPO2,
    VITAL_HR,
    VITAL_RR,
    VITAL_FIO2,
    VITAL_PEEP,
    VITAL_TIDAL_VOLUME,
]

# ---------------------------------------------------------------------------
# 4. Vital normal ranges  {vital_name: (low_inclusive, high_inclusive)}
# ---------------------------------------------------------------------------

NORMAL_RANGES: dict[str, tuple[int, int]] = {
    VITAL_SPO2:         (95, 100),
    VITAL_HR:           (60, 100),
    VITAL_RR:           (12, 20),
    VITAL_FIO2:         (21, 40),
    VITAL_PEEP:         (5, 10),
    VITAL_TIDAL_VOLUME: (400, 600),
}

# ---------------------------------------------------------------------------
# 5. Vital alarm & critical thresholds
#
#    Structure:
#      THRESHOLDS[vital] = {
#          "critical_low"  : int | None,
#          "alarm_low"     : int | None,
#          "alarm_high"    : int | None,
#          "critical_high" : int | None,
#      }
#
#    A None value means that boundary does not apply for this vital.
# ---------------------------------------------------------------------------

THRESHOLDS: dict[str, dict[str, int | None]] = {
    VITAL_SPO2: {
        "critical_low":  90,   # SpO2 < 90  -> CRITICAL
        "alarm_low":     95,   # SpO2 < 95  -> ALARM
        "alarm_high":    None,
        "critical_high": None,
    },
    VITAL_HR: {
        "critical_low":  50,   # HR < 50    -> CRITICAL
        "alarm_low":     60,   # HR < 60    -> ALARM
        "alarm_high":    100,  # HR > 100   -> ALARM
        "critical_high": 120,  # HR > 120   -> CRITICAL
    },
    VITAL_RR: {
        "critical_low":  None,
        "alarm_low":     12,   # RR < 12    -> ALARM
        "alarm_high":    20,   # RR > 20    -> ALARM
        "critical_high": 30,   # RR > 30    -> CRITICAL
    },
    VITAL_FIO2: {
        "critical_low":  None,
        "alarm_low":     None,
        "alarm_high":    40,   # FiO2 > 40  -> ALARM
        "critical_high": 60,   # FiO2 > 60  -> CRITICAL
    },
    VITAL_PEEP: {
        "critical_low":  None,
        "alarm_low":     5,    # PEEP < 5   -> ALARM
        "alarm_high":    10,   # PEEP > 10  -> ALARM
        "critical_high": 15,   # PEEP > 15  -> CRITICAL
    },
    VITAL_TIDAL_VOLUME: {
        "critical_low":  300,  # TV < 300   -> CRITICAL
        "alarm_low":     400,  # TV < 400   -> ALARM
        "alarm_high":    600,  # TV > 600   -> ALARM
        "critical_high": None,
    },
}

# Abnormal ranges used by the simulator to inject realistic bad readings
ABNORMAL_RANGES: dict[str, list[tuple[int, int]]] = {
    VITAL_SPO2:         [(80, 94)],
    VITAL_HR:           [(40, 59), (101, 150)],
    VITAL_RR:           [(8, 11), (21, 40)],
    VITAL_FIO2:         [(41, 100)],
    VITAL_PEEP:         [(2, 4), (11, 25)],
    VITAL_TIDAL_VOLUME: [(200, 399), (601, 800)],
}

# Probability of an abnormal reading being generated (12%)
ABNORMAL_PROBABILITY: float = 0.12

# ---------------------------------------------------------------------------
# 6. Data generation settings
# ---------------------------------------------------------------------------

# Interval (in seconds) between simulator readings
DATA_GENERATION_INTERVAL: int = 2

# ---------------------------------------------------------------------------
# 7. WebSocket configuration
# ---------------------------------------------------------------------------

WEBSOCKET_HOST: str = os.getenv("WEBSOCKET_HOST", "localhost")
WEBSOCKET_PORT: int = int(os.getenv("WEBSOCKET_PORT", "8765"))
WEBSOCKET_URL: str = f"ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}"

# FastAPI HTTP server settings (used when adding the API layer)
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))

# ---------------------------------------------------------------------------
# 8. AI / LLM configuration
#    All keys are read exclusively from the environment -- never hardcoded.
# ---------------------------------------------------------------------------

# Primary AI model identifier (e.g. "gpt-4o", "claude-3-5-sonnet-20241022")
AI_MODEL: str = os.getenv("AI_MODEL", "gpt-4o")

# API keys -- populated from environment / .env file; default is empty string
# so the application starts but AI features degrade gracefully.
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# ---------------------------------------------------------------------------
# 9. Weaning readiness score thresholds
#    Percentage of maximum possible score required for each status label.
# ---------------------------------------------------------------------------

WEANING_READY_THRESHOLD: int = 80        # >= 80% -> READY
WEANING_BORDERLINE_THRESHOLD: int = 50   # >= 50% -> BORDERLINE
                                          # <  50% -> NOT_READY
