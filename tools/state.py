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
    global socketio
    socketio = sio


def emit_status(msg: str, level: str = "info") -> None:
    """Broadcast a status message to all connected clients."""
    if socketio is not None:
        socketio.emit("status", {"msg": msg, "level": level})


def set_busy(busy: bool) -> None:
    """Update busy flag and broadcast to clients."""
    with state_lock:
        state["busy"] = busy
    if socketio is not None:
        socketio.emit("busy", {"busy": busy})
