"""Server state and Socket.IO helpers for the nonogram web app."""

from __future__ import annotations

import threading
from typing import Any

from flask_socketio import SocketIO

# ── Server state (single-user local app) ────────────────────────────────────
_DEFAULT_SIZE = 4
state: dict[str, Any] = {
    "rows": _DEFAULT_SIZE,
    "cols": _DEFAULT_SIZE,
    "grid": [[False] * _DEFAULT_SIZE for _ in range(_DEFAULT_SIZE)],
    "hw_config": None,
    "busy": False,
    "puzzle_name": "puzzle",
}
state_lock = threading.Lock()

# Populated by webapp.py after SocketIO is created
socketio: SocketIO | None = None


def init(sio: SocketIO) -> None:
    """Bind the SocketIO instance so helpers can emit."""
    global socketio  # noqa: PLW0603 — module-level SocketIO singleton, bound once at app startup
    socketio = sio


def emit_status(msg: str, level: str = "info", to: str | None = None) -> None:
    """Emit a status message — to one client's sid when given, else broadcast.

    Result/status emits are scoped to the requesting client when the request
    carries its Socket.IO sid; the busy flag stays broadcast because the busy
    state genuinely is global (single solver, single-operator app).
    """
    if socketio is not None:
        socketio.emit("status", {"msg": msg, "level": level}, to=to)


def set_busy(busy: bool) -> None:
    """Update busy flag and broadcast to clients."""
    with state_lock:
        state["busy"] = busy
    if socketio is not None:
        socketio.emit("busy", {"busy": busy})
