"""
main.py – VentAlert FastAPI Backend
=====================================
Hosts the WebSocket endpoint, orchestrates the simulator loop,
manages multi-client connections, and broadcasts real-time events.

Architecture
------------
    simulator.generate_reading()   (every DATA_GENERATION_INTERVAL seconds)
           │
           ▼
    alert_engine.check_thresholds()
           │
           ▼
    ConnectionManager.broadcast()  →  all connected WebSocket clients

WebSocket endpoint
------------------
    ws://localhost:8000/ws?role=doctor   full access (send + receive)
    ws://localhost:8000/ws?role=nurse    read-only (receive only)

Events broadcast
----------------
    vital_update        every 2 seconds
    alert               whenever a threshold is breached
    instruction         when a doctor sends a message (broadcast to all)
    weaning_score       on demand
    ai_suggestion       placeholder (Phase 2)
    history             sent once to every newly connected client

Usage
-----
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

Notes
-----
* Does NOT duplicate simulator logic — imports generate_reading() directly.
* All constants imported from backend.config — no hardcoded values here.
* AI functions are placeholders ready for OpenAI integration (Phase 2).
* PEP8 compliant, fully type-hinted, production-ready.
"""

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# Internal imports — no logic is duplicated from these modules
# ---------------------------------------------------------------------------
from backend.config import (
    PROJECT_NAME,
    PROJECT_VERSION,
    PROJECT_DESCRIPTION,
    DATA_GENERATION_INTERVAL,
    AI_MODEL,
    OPENAI_API_KEY,
)
from backend.alert_engine import check_thresholds, emit_alert_event
from backend.weaning_engine import calculate_weaning_score

# Import the simulator's public functions only — main() is never called
from simulator import generate_reading

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(PROJECT_NAME)

# ---------------------------------------------------------------------------
# Instruction history
# ---------------------------------------------------------------------------

MAX_INSTRUCTION_HISTORY: int = 20  # Number of instructions kept in memory


# ---------------------------------------------------------------------------
# ConnectionManager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """
    Manages all active WebSocket connections.

    Responsibilities
    ----------------
    * Track every connected client and their role (doctor / nurse).
    * Maintain a rolling history of the last MAX_INSTRUCTION_HISTORY
      doctor instructions.
    * Provide broadcast methods for every event type.

    Thread / async safety
    ----------------------
    All methods are called from the same asyncio event loop; no locking
    is required for the in-memory data structures.
    """

    def __init__(self) -> None:
        # Map WebSocket → role string
        self._clients: dict[WebSocket, str] = {}
        # Rolling list of past doctor instructions (oldest first)
        self._instruction_history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self, websocket: WebSocket, role: str) -> None:
        """
        Accept a new WebSocket connection and register it.

        Parameters
        ----------
        websocket : WebSocket
            The incoming connection object.
        role : str
            Client role — ``"doctor"`` or ``"nurse"``.
        """
        await websocket.accept()
        self._clients[websocket] = role
        logger.info(
            "Client connected  role=%-8s  total_clients=%d",
            role,
            len(self._clients),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove a client from the active pool on disconnect.

        Parameters
        ----------
        websocket : WebSocket
            The connection that was closed.
        """
        role = self._clients.pop(websocket, "unknown")
        logger.info(
            "Client disconnected  role=%-8s  total_clients=%d",
            role,
            len(self._clients),
        )

    # ------------------------------------------------------------------
    # Role helpers
    # ------------------------------------------------------------------

    def get_role(self, websocket: WebSocket) -> str:
        """Return the role assigned to a WebSocket connection."""
        return self._clients.get(websocket, "unknown")

    @property
    def active_count(self) -> int:
        """Number of currently connected clients."""
        return len(self._clients)

    # ------------------------------------------------------------------
    # Broadcast helpers
    # ------------------------------------------------------------------

    async def broadcast(self, payload: dict[str, Any]) -> None:
        """
        Send a JSON payload to every connected client.

        Clients that have disconnected mid-broadcast are silently removed.

        Parameters
        ----------
        payload : dict
            The event dictionary to serialise and send.
        """
        disconnected: list[WebSocket] = []
        message = json.dumps(payload)

        for client in list(self._clients):
            try:
                await client.send_text(message)
            except Exception:
                # Client dropped — mark for removal
                disconnected.append(client)

        # Clean up dead connections discovered during broadcast
        for client in disconnected:
            self.disconnect(client)

    async def send_to(self, websocket: WebSocket, payload: dict[str, Any]) -> None:
        """
        Send a JSON payload to a single specific client.

        Parameters
        ----------
        websocket : WebSocket
            The target connection.
        payload : dict
            The event dictionary to serialise and send.
        """
        try:
            await websocket.send_text(json.dumps(payload))
        except Exception as exc:
            logger.warning("Failed to send to client: %s", exc)

    async def broadcast_alert(self, alert: dict[str, Any]) -> None:
        """
        Wrap an alert object in the event envelope and broadcast it.

        Uses ``emit_alert_event`` from alert_engine to construct the
        standard ``{ "event": "alert", "data": ... }`` envelope.

        Parameters
        ----------
        alert : dict
            A single alert object returned by ``check_thresholds``.
        """
        event_payload = emit_alert_event(alert)
        logger.warning(
            "ALERT  vital=%-15s  value=%-5s  severity=%s",
            alert.get("vital"),
            alert.get("value"),
            alert.get("severity"),
        )
        await self.broadcast(event_payload)

    async def broadcast_instruction(self, instruction: dict[str, Any]) -> None:
        """
        Store an instruction in history and broadcast it to all clients.

        The history is capped at MAX_INSTRUCTION_HISTORY entries (FIFO).

        Parameters
        ----------
        instruction : dict
            Fully-formed instruction payload including ``sender``,
            ``message``, and ``timestamp``.
        """
        # Append and trim history
        self._instruction_history.append(instruction)
        if len(self._instruction_history) > MAX_INSTRUCTION_HISTORY:
            self._instruction_history.pop(0)

        logger.info(
            "Instruction  sender=doctor  msg='%.60s'",
            instruction.get("message", ""),
        )
        await self.broadcast(instruction)

    async def broadcast_history(self, websocket: WebSocket) -> None:
        """
        Send the full instruction history to a single newly connected client.

        Parameters
        ----------
        websocket : WebSocket
            The client that just connected and should receive history.
        """
        history_payload = {
            "event": "history",
            "data": self._instruction_history,
        }
        await self.send_to(websocket, history_payload)
        logger.info(
            "History sent  instructions=%d",
            len(self._instruction_history),
        )


# ---------------------------------------------------------------------------
# Singleton connection manager (shared across all WebSocket connections)
# ---------------------------------------------------------------------------

manager = ConnectionManager()

# ---------------------------------------------------------------------------
# Vital state cache
# ---------------------------------------------------------------------------
# Maintains the most recent reading per vital so weaning_engine can be
# called with a complete snapshot at any time.
_current_vitals: dict[str, int] = {}


# ---------------------------------------------------------------------------
# AI placeholder functions (Phase 2)
# ---------------------------------------------------------------------------

def generate_ai_suggestion(
    latest_vital: dict[str, Any],
    active_alert_count: int,
    weaning_status: str,
) -> dict[str, Any]:
    """
    Generate a clinical AI suggestion for the current patient state.

    Phase 1 — returns a realistic mock response.
    Phase 2 — replace the body with an actual OpenAI API call.

    Parameters
    ----------
    latest_vital : dict
        The most recent vital reading (vital, value, status).
    active_alert_count : int
        Number of alerts currently active.
    weaning_status : str
        Readiness status from ``weaning_engine``.

    Returns
    -------
    dict
        Structured AI suggestion payload ready for WebSocket broadcast.

    TODO (Phase 2)
    --------------
    Replace the mock response block with::

        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": "You are a clinical ICU decision-support AI."},
                {"role": "user", "content": json.dumps(patient_context)},
            ],
        )
        suggestion_text = response.choices[0].message.content
    """
    # -- MOCK RESPONSE (remove in Phase 2) ----------------------------------
    vital_name = latest_vital.get("vital", "unknown")
    vital_value = latest_vital.get("value", "N/A")
    vital_status = latest_vital.get("status", "NORMAL")

    if vital_status == "CRITICAL":
        suggestion_text = (
            f"Patient {vital_name} is critically low at {vital_value}. "
            "Consider immediate clinical assessment and intervention. "
            "Verify ventilator settings and airway position."
        )
        confidence = "HIGH"
    elif vital_status == "ALARM":
        suggestion_text = (
            f"Patient {vital_name} is trending outside normal range ({vital_value}). "
            "Monitor closely and reassess in 10 minutes."
        )
        confidence = "MEDIUM"
    else:
        suggestion_text = (
            "Patient vitals are currently within normal ranges. "
            "Continue current ventilator settings and monitoring protocol."
        )
        confidence = "LOW"
    # -- END MOCK RESPONSE --------------------------------------------------

    return {
        "event": "ai_suggestion",
        "data": {
            "model": AI_MODEL,
            "patient_context": {
                "latest_vital": latest_vital,
                "active_alerts": active_alert_count,
                "weaning_status": weaning_status,
            },
            "suggestion": suggestion_text,
            "confidence": confidence,
            "generated_at": _now_iso(),
            "disclaimer": (
                "AI-generated suggestion. "
                "Requires physician review before clinical action."
            ),
        },
    }


def summarize_patient(vitals_snapshot: dict[str, int]) -> dict[str, Any]:
    """
    Generate a plain-language patient summary from a vitals snapshot.

    Phase 1 — mock summary.
    Phase 2 — call OpenAI with the full vitals context.

    Parameters
    ----------
    vitals_snapshot : dict
        Mapping of vital name → current value.

    Returns
    -------
    dict
        Summary payload ready for broadcast.

    TODO (Phase 2): Replace mock with OpenAI API call.
    """
    # -- MOCK RESPONSE --
    return {
        "event": "ai_suggestion",
        "data": {
            "model": AI_MODEL,
            "type": "patient_summary",
            "summary": (
                f"Patient currently monitored on {len(vitals_snapshot)} parameters. "
                "Vitals snapshot collected. Full AI analysis available in Phase 2."
            ),
            "generated_at": _now_iso(),
            "disclaimer": "Mock summary. Full AI analysis requires Phase 2 integration.",
        },
    }


def predict_weaning(vitals_snapshot: dict[str, int]) -> dict[str, Any]:
    """
    Predict weaning readiness using an AI model.

    Phase 1 — delegates to ``weaning_engine`` (rule-based).
    Phase 2 — augment with OpenAI prediction on top of the rule score.

    Parameters
    ----------
    vitals_snapshot : dict
        Current patient vitals to evaluate.

    Returns
    -------
    dict
        Weaning prediction payload.

    TODO (Phase 2): Send vitals + rule score to AI for enhanced prediction.
    """
    score_result = calculate_weaning_score(vitals_snapshot)
    return {
        "event": "weaning_score",
        "data": {
            **score_result,
            "evaluated_at": _now_iso(),
            "vitals_snapshot": vitals_snapshot,
        },
    }


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Return current local time as ISO-8601 string (YYYY-MM-DDTHH:MM:SS)."""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------------------
# Background task – vital broadcast loop
# ---------------------------------------------------------------------------

async def broadcast_vitals_loop() -> None:
    """
    Asyncio background task: generate and broadcast vitals indefinitely.

    Every ``DATA_GENERATION_INTERVAL`` seconds:
    1. Call ``simulator.generate_reading()`` for one vital reading.
    2. Broadcast as ``event="vital_update"`` to all clients.
    3. Pass the reading to ``alert_engine.check_thresholds()``.
    4. Broadcast every triggered alert as ``event="alert"``.

    The task runs until the application shuts down (``asyncio.CancelledError``).
    Exceptions inside the loop are caught and logged so the loop never exits
    silently.
    """
    logger.info("Vital broadcast loop started — interval=%ds", DATA_GENERATION_INTERVAL)

    while True:
        try:
            # ── Step 1: Generate one vital reading ──────────────────────
            reading = generate_reading()

            # Keep the current vitals cache up to date for weaning eval
            vital_name: str = reading["vital"]
            vital_value: int = reading["value"]
            _current_vitals[vital_name] = vital_value

            # ── Step 2: Broadcast vital_update to all clients ────────────
            if manager.active_count > 0:
                vital_event = {"event": "vital_update", "data": reading}
                await manager.broadcast(vital_event)

            # ── Step 3: Check thresholds using the alert engine ──────────
            alerts = check_thresholds({vital_name: vital_value})

            # ── Step 4: Broadcast each triggered alert ───────────────────
            for alert in alerts:
                await manager.broadcast_alert(alert)

        except asyncio.CancelledError:
            # Graceful shutdown — re-raise so the task exits cleanly
            logger.info("Vital broadcast loop cancelled — shutting down")
            raise
        except Exception as exc:
            logger.error("Error in broadcast loop: %s", exc, exc_info=True)

        # Wait for the next cycle
        await asyncio.sleep(DATA_GENERATION_INTERVAL)


# ---------------------------------------------------------------------------
# Application lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.

    On startup: log server info and launch the vital broadcast background task.
    On shutdown: cancel the background task cleanly.
    """
    logger.info("%s v%s starting up...", PROJECT_NAME, PROJECT_VERSION)
    logger.info("WebSocket endpoint: ws://localhost:8000/ws")
    logger.info("API docs available: http://localhost:8000/docs")

    # Start the background vital broadcast loop
    broadcast_task = asyncio.create_task(broadcast_vitals_loop())

    yield  # Application runs here

    # Shutdown — cancel background task gracefully
    broadcast_task.cancel()
    try:
        await broadcast_task
    except asyncio.CancelledError:
        pass
    logger.info("%s shutdown complete", PROJECT_NAME)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title=PROJECT_NAME,
    version=PROJECT_VERSION,
    description=PROJECT_DESCRIPTION,
    lifespan=lifespan,
)

# Allow all origins for development (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    """
    Health check endpoint.

    Returns
    -------
    dict
        Project name, version, and WebSocket URL.
    """
    return {
        "project": PROJECT_NAME,
        "version": PROJECT_VERSION,
        "websocket": "ws://localhost:8000/ws?role=doctor",
        "docs": "http://localhost:8000/docs",
        "status": "running",
    }


@app.get("/vitals", tags=["Vitals"])
async def get_current_vitals() -> dict[str, Any]:
    """
    Return the latest known value for every monitored vital.

    Returns
    -------
    dict
        Snapshot of the most recent reading per vital plus a timestamp.
    """
    return {
        "vitals": _current_vitals,
        "timestamp": _now_iso(),
    }


@app.get("/weaning", tags=["Weaning"])
async def get_weaning_score() -> dict[str, Any]:
    """
    Evaluate and return the current weaning readiness score.

    Returns
    -------
    dict
        Weaning readiness report from ``weaning_engine``.
    """
    result = predict_weaning(_current_vitals)
    return result["data"]


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    role: str = Query(default="nurse", description="Client role: doctor | nurse"),
) -> None:
    """
    Primary WebSocket endpoint for real-time communication.

    Query Parameters
    ----------------
    role : str
        ``"doctor"``  — can send and receive all events.
        ``"nurse"``   — read-only; instruction sends are rejected.

    Protocol
    --------
    On connect:
        1. Register client with its role.
        2. Send ``event="history"`` with the last 20 instructions.

    On message received:
        Expect JSON with ``"event"`` field:
        * ``"instruction"`` — doctor sends a clinical instruction.
        * ``"weaning"``     — request a weaning score broadcast.
        * ``"ai_summary"``  — request an AI patient summary.
        * Any unknown event is logged and ignored.

    On disconnect:
        Client is removed from the active pool.
    """
    # Sanitise role — default unknown roles to nurse (read-only)
    role = role.lower() if role.lower() in ("doctor", "nurse") else "nurse"

    # Register the new client
    await manager.connect(websocket, role)

    # Send instruction history immediately on connect
    await manager.broadcast_history(websocket)

    try:
        while True:
            # Wait for a message from this client
            raw = await websocket.receive_text()

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Received malformed JSON from %s client", role)
                await manager.send_to(
                    websocket,
                    {"event": "error", "message": "Invalid JSON"},
                )
                continue

            event = payload.get("event", "")

            # ── Handle: instruction ────────────────────────────────────
            if event == "instruction":
                if role != "doctor":
                    # Nurses are read-only
                    await manager.send_to(
                        websocket,
                        {
                            "event": "error",
                            "message": (
                                "Read-only role. "
                                "Only doctors may send instructions."
                            ),
                        },
                    )
                    logger.warning("Nurse attempted to send instruction — blocked")
                    continue

                instruction = {
                    "event": "instruction",
                    "sender": "doctor",
                    "message": payload.get("message", "").strip(),
                    "timestamp": _now_iso(),
                }
                await manager.broadcast_instruction(instruction)

            # ── Handle: weaning score request ──────────────────────────
            elif event == "weaning":
                weaning_payload = predict_weaning(_current_vitals)
                await manager.broadcast(weaning_payload)

            # ── Handle: AI summary request ─────────────────────────────
            elif event == "ai_summary":
                summary = summarize_patient(_current_vitals)
                await manager.broadcast(summary)

            # ── Unknown event ──────────────────────────────────────────
            else:
                logger.warning("Unknown event '%s' from %s client", event, role)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:
        logger.error("Unexpected WebSocket error: %s", exc, exc_info=True)
        manager.disconnect(websocket)
