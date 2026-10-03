"""Server state and Socket.IO helpers for the nonogram web app.

The posted grid is validated but not kept: no route serves it back, and solves take
their clues from the request body. Whether a run reaches the QPU is decided per
request, so it is not held here either.
"""

from __future__ import annotations

import threading
from typing import Any

from flask_socketio import SocketIO

_DEFAULT_SIZE = 4


def default_state() -> dict[str, Any]:
    """A fresh copy of the state a server starts with."""
    return {
        "rows": _DEFAULT_SIZE,
        "cols": _DEFAULT_SIZE,
        "busy": False,
        "puzzle_name": "puzzle",
    }


state: dict[str, Any] = default_state()
state_lock = threading.Lock()

# Set once the SocketIO server exists.
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
    """Update the busy flag and broadcast it.

    Broadcast on purpose: there is one solver, so its state is everyone's. The flag
    carries no puzzle and no result — those are addressed to the room that asked for
    them — so it says only that the shared solver is occupied.
    """
    with state_lock:
        state["busy"] = busy
    if socketio is not None:
        socketio.emit("busy", {"busy": busy})
