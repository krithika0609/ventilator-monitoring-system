"""
alert_engine.py – VentAlert Backend
====================================
Provides threshold-based alert detection for ventilator vitals.

Public API
----------
check_thresholds(vitals)  -> list[dict]
    Evaluate a full vitals snapshot; return every breached alert.

emit_alert_event(alert)   -> dict
    Wrap a single alert in a WebSocket-compatible event envelope.

Design notes
------------
* Uses only Python standard-library modules (datetime).
* Each vital's rules live in ALERT_RULES so adding / changing a
  threshold never requires touching evaluation logic.
* Severity levels: CRITICAL > ALARM.
* Ready to be imported by a FastAPI router without modification.
"""

import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Threshold rules
# ---------------------------------------------------------------------------
# Each entry maps a vital name to a list of rule dictionaries.
# Rule fields:
#   condition  : callable(value) -> bool   – True when the threshold is breached
#   threshold  : human-readable threshold string shown in the alert
#   severity   : "CRITICAL" | "ALARM"
#   message    : short clinical description of the breach
#
# Rules are evaluated in order; ALL matching rules produce an alert object.
# ---------------------------------------------------------------------------

ALERT_RULES: dict[str, list[dict[str, Any]]] = {
    "SpO2": [
        {
            "condition": lambda v: v < 90,
            "threshold": "<90",
            "severity": "CRITICAL",
            "message": "Critical oxygen level detected",
        },
        {
            "condition": lambda v: 90 <= v < 95,
            "threshold": "<95",
            "severity": "ALARM",
            "message": "Low oxygen saturation detected",
        },
    ],
    "HR": [
        {
            "condition": lambda v: v > 120,
            "threshold": ">120",
            "severity": "CRITICAL",
            "message": "Critical high heart rate detected",
        },
        {
            "condition": lambda v: v < 50,
            "threshold": "<50",
            "severity": "CRITICAL",
            "message": "Critical low heart rate detected",
        },
    ],
    "RR": [
        {
            "condition": lambda v: v > 30,
            "threshold": ">30",
            "severity": "CRITICAL",
            "message": "Critical high respiratory rate detected",
        },
    ],
    "FiO2": [
        {
            "condition": lambda v: v > 60,
            "threshold": ">60",
            "severity": "CRITICAL",
            "message": "Critical high oxygen concentration detected",
        },
    ],
    "PEEP": [
        {
            "condition": lambda v: v > 15,
            "threshold": ">15",
            "severity": "CRITICAL",
            "message": "Critical high positive end-expiratory pressure detected",
        },
    ],
    "Tidal Volume": [
        {
            "condition": lambda v: v < 300,
            "threshold": "<300",
            "severity": "CRITICAL",
            "message": "Critical low tidal volume detected",
        },
    ],
}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Return the current UTC-local timestamp as an ISO-8601 string."""
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _build_alert(vital: str, value: int | float, rule: dict[str, Any]) -> dict:
    """
    Construct a single alert object from a matched rule.

    Parameters
    ----------
    vital : str
        Name of the vital that breached a threshold.
    value : int | float
        Observed value that triggered the breach.
    rule  : dict
        The matching entry from ALERT_RULES containing threshold,
        severity, and message fields.

    Returns
    -------
    dict
        Fully-formed alert object ready for serialisation or WebSocket
        emission.
    """
    return {
        "type": "alert",
        "vital": vital,
        "value": value,
        "threshold": rule["threshold"],
        "severity": rule["severity"],
        "timestamp": _now_iso(),
        "message": rule["message"],
    }


def _evaluate_vital(vital: str, value: int | float) -> list[dict]:
    """
    Check all rules for a single vital and return every triggered alert.

    Parameters
    ----------
    vital : str
        Name of the vital to evaluate.
    value : int | float
        Observed reading for that vital.

    Returns
    -------
    list[dict]
        Zero or more alert objects for this vital.
    """
    rules = ALERT_RULES.get(vital, [])
    alerts = []
    for rule in rules:
        if rule["condition"](value):
            alerts.append(_build_alert(vital, value, rule))
    return alerts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_thresholds(vitals: dict) -> list[dict]:
    """
    Evaluate an entire vitals snapshot against all configured thresholds.

    Iterates over every key present in *vitals*, looks up its rules in
    ALERT_RULES, and collects an alert object for each breach.  Multiple
    vitals can be in alarm simultaneously; all are returned.

    Parameters
    ----------
    vitals : dict
        Mapping of vital name -> numeric reading, for example::

            {
                "SpO2": 87,
                "HR": 128,
                "RR": 18,
                "FiO2": 35,
                "PEEP": 8,
                "Tidal Volume": 520,
            }

    Returns
    -------
    list[dict]
        List of alert objects (may be empty if all vitals are normal).
        Each alert object contains:
        ``type``, ``vital``, ``value``, ``threshold``,
        ``severity``, ``timestamp``, ``message``.

    Examples
    --------
    >>> alerts = check_thresholds({"SpO2": 87, "HR": 128})
    >>> [a["vital"] for a in alerts]
    ['SpO2', 'HR']
    """
    all_alerts: list[dict] = []

    for vital, value in vitals.items():
        # Skip vitals that have no defined rules (unknown vitals)
        if vital not in ALERT_RULES:
            continue
        triggered = _evaluate_vital(vital, value)
        all_alerts.extend(triggered)

    return all_alerts


def emit_alert_event(alert: dict) -> dict:
    """
    Wrap a single alert object in a WebSocket-compatible event envelope.

    This function is a stub for future real-time WebSocket integration.
    When FastAPI + WebSocket support is added, this envelope can be
    serialised to JSON and broadcast to connected clients without any
    change to this function's signature.

    Parameters
    ----------
    alert : dict
        A single alert object as returned by ``check_thresholds``.

    Returns
    -------
    dict
        Event envelope with keys ``event`` and ``data``::

            {
                "event": "alert",
                "data": { ... alert object ... }
            }

    Examples
    --------
    >>> event = emit_alert_event({"type": "alert", "vital": "SpO2", ...})
    >>> event["event"]
    'alert'
    """
    return {
        "event": "alert",
        "data": alert,
    }
