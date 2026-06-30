"""
weaning_engine.py – VentAlert Backend
=======================================
Provides a structured, configurable weaning-readiness scoring framework
for ventilated patients.

IMPORTANT – Clinical Criteria Placeholder
------------------------------------------
The WEANING_CRITERIA dictionary is intentionally left empty.

TODO (Dr. Mugesh): Insert approved clinical weaning criteria before
production deployment.  See the structure guide below.

The engine is fully functional once criteria are populated; no logic
changes are required.

Public API
----------
calculate_weaning_score(vitals) -> dict
    Evaluate vitals against WEANING_CRITERIA and return a readiness
    report containing score, met/unmet criteria, and a readiness status.

Design notes
------------
* Uses only Python standard-library modules.
* Criteria are fully data-driven; the evaluation loop never needs to
  change when criteria are updated.
* Ready to be imported by a FastAPI router without modification.

WEANING_CRITERIA structure guide
---------------------------------
Each entry in WEANING_CRITERIA maps a criterion name to a dict:

    WEANING_CRITERIA = {
        "<criterion_name>": {
            "vital"      : "<key in vitals dict>",
            "condition"  : callable(value) -> bool,
            "weight"     : <int>,   # contribution to total score
            "description": "<human-readable explanation>",
        },
        ...
    }

Example (do NOT add without Dr. Mugesh's approval)::

    "acceptable_spo2": {
        "vital"      : "SpO2",
        "condition"  : lambda v: v >= 95,
        "weight"     : 20,
        "description": "SpO2 >= 95 %",
    },
"""

from typing import Any

# ---------------------------------------------------------------------------
# Clinical criteria configuration
# ---------------------------------------------------------------------------
# TODO (Dr. Mugesh): Replace the empty dictionary below with clinically
# approved weaning criteria before this module is used in production.
# Refer to the WEANING_CRITERIA structure guide in the module docstring.
# ---------------------------------------------------------------------------

WEANING_CRITERIA: dict[str, dict[str, Any]] = {
    # ------------------------------------------------------------------ #
    # INSERT APPROVED CRITERIA HERE                                        #
    # ------------------------------------------------------------------ #
}

# Readiness thresholds (percentage of maximum possible score)
# These may also be updated in consultation with the clinical team.
READINESS_THRESHOLDS: dict[str, int] = {
    # Minimum score percentage to be considered READY
    "READY": 80,
    # Minimum score percentage to be considered BORDERLINE
    "BORDERLINE": 50,
    # Below BORDERLINE -> NOT_READY
}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _max_possible_score() -> int:
    """
    Calculate the maximum achievable score given current WEANING_CRITERIA.

    Returns
    -------
    int
        Sum of all criterion weights; 0 when no criteria are defined.
    """
    return sum(
        criterion["weight"]
        for criterion in WEANING_CRITERIA.values()
    )


def _evaluate_criterion(
    name: str,
    criterion: dict[str, Any],
    vitals: dict,
) -> bool:
    """
    Evaluate a single weaning criterion against the supplied vitals.

    A criterion is considered *met* when:
    1. Its ``vital`` key is present in *vitals*, AND
    2. Its ``condition`` callable returns True for the observed value.

    Missing vitals are treated as criterion-not-met (returns False) to
    ensure safe defaults.

    Parameters
    ----------
    name      : str
        Criterion identifier (used for logging/debug purposes only).
    criterion : dict
        A single entry from WEANING_CRITERIA.
    vitals    : dict
        Current patient vitals snapshot.

    Returns
    -------
    bool
        True if the criterion is met, False otherwise.
    """
    vital_key = criterion.get("vital")

    # If the required vital is absent from the snapshot, criterion fails
    if vital_key not in vitals:
        return False

    value = vitals[vital_key]

    # Evaluate the condition callable safely
    try:
        return bool(criterion["condition"](value))
    except Exception:
        # Any evaluation error is treated as criterion-not-met
        return False


def _calculate_score(criteria_met: list[str]) -> int:
    """
    Compute total score from the list of met criterion names.

    Parameters
    ----------
    criteria_met : list[str]
        Names of all criteria that were successfully met.

    Returns
    -------
    int
        Sum of weights for met criteria; 0 when none are met.
    """
    return sum(
        WEANING_CRITERIA[name]["weight"]
        for name in criteria_met
        if name in WEANING_CRITERIA
    )


def _determine_readiness_status(score: int, max_score: int) -> str:
    """
    Derive a readiness status label from the achieved score.

    When no criteria are configured the function returns
    ``"PENDING_CLINICAL_APPROVAL"`` to surface the incomplete setup
    explicitly rather than silently returning a misleading result.

    Parameters
    ----------
    score     : int
        Total score achieved by the patient.
    max_score : int
        Maximum possible score given current criteria.

    Returns
    -------
    str
        One of:
        * ``"PENDING_CLINICAL_APPROVAL"`` – no criteria configured yet
        * ``"READY"``                      – score >= READY threshold
        * ``"BORDERLINE"``                 – score >= BORDERLINE threshold
        * ``"NOT_READY"``                  – score below all thresholds
    """
    # Guard: no criteria have been configured
    if max_score == 0:
        return "PENDING_CLINICAL_APPROVAL"

    percentage = (score / max_score) * 100

    if percentage >= READINESS_THRESHOLDS["READY"]:
        return "READY"
    if percentage >= READINESS_THRESHOLDS["BORDERLINE"]:
        return "BORDERLINE"
    return "NOT_READY"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calculate_weaning_score(vitals: dict) -> dict:
    """
    Evaluate patient vitals against configured weaning criteria and
    return a structured readiness report.

    Each criterion in WEANING_CRITERIA is tested against *vitals*.
    The function aggregates met/unmet criteria, calculates a total
    score, and assigns an overall readiness status.

    Parameters
    ----------
    vitals : dict
        Current patient vitals snapshot, for example::

            {
                "SpO2": 97,
                "HR": 82,
                "RR": 16,
                "FiO2": 30,
                "PEEP": 6,
                "Tidal Volume": 480,
            }

    Returns
    -------
    dict
        Weaning readiness report::

            {
                "score"             : int,
                "criteria_met"      : list[str],
                "criteria_not_met"  : list[str],
                "readiness_status"  : str,
            }

        ``readiness_status`` values:
        * ``"PENDING_CLINICAL_APPROVAL"`` – no criteria have been loaded yet
        * ``"READY"``                      – patient appears ready to wean
        * ``"BORDERLINE"``                 – borderline; clinical judgement needed
        * ``"NOT_READY"``                  – patient is not ready to wean

    Examples
    --------
    >>> result = calculate_weaning_score({"SpO2": 97, "HR": 80})
    >>> result["readiness_status"]
    'PENDING_CLINICAL_APPROVAL'
    """
    criteria_met: list[str] = []
    criteria_not_met: list[str] = []

    # Evaluate each criterion in order
    for name, criterion in WEANING_CRITERIA.items():
        if _evaluate_criterion(name, criterion, vitals):
            criteria_met.append(name)
        else:
            criteria_not_met.append(name)

    # Compute numeric score and maximum achievable score
    score = _calculate_score(criteria_met)
    max_score = _max_possible_score()

    # Determine overall readiness label
    readiness_status = _determine_readiness_status(score, max_score)

    return {
        "score": score,
        "criteria_met": criteria_met,
        "criteria_not_met": criteria_not_met,
        "readiness_status": readiness_status,
    }
