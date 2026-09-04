"""IBM quantum hardware routes: backends, connect/disconnect.

The IBM credentials are held by the SERVER (an environment secret), never supplied
by a caller: a client must not be able to spend the owner's quantum credits, and
this server must not relay a stranger's token. Who may reach these routes at all is
decided upstream by the front door (Cloudflare Access for the owner, or a
time-boxed recruiter pass), so the token stays out of the browser entirely.
"""

from __future__ import annotations

import os

from flask import Blueprint, jsonify, request

from tools import state as _state_mod
from tools.errors import respond_error
from tools.state import emit_status, state, state_lock

bp = Blueprint("hardware", __name__)

#: Upper bound on shots per hardware job — each shot costs real quantum credits.
MAX_SHOTS = 4096


def _ibm_token() -> str | None:
    """The IBM Quantum API token from the server environment, or None if unset.

    Deploy it as a secret (e.g. ``fly secrets set IBM_QUANTUM_TOKEN=…``). Unset ⇒ the
    hardware routes report 503 and the solver stays on the local simulator.
    """
    return os.environ.get("IBM_QUANTUM_TOKEN") or None


def _ibm_channel(data: dict) -> str:
    """The Runtime channel (not a secret): env override, else caller, else default."""
    return os.environ.get("IBM_QUANTUM_CHANNEL") or data.get("channel") or "ibm_quantum"


@bp.route("/api/hw/backends", methods=["POST"])
def api_hw_backends():
    """List available IBM quantum backends, using the server-held credentials."""
    token = _ibm_token()
    if not token:
        return respond_error(
            "hardware_unconfigured", "IBM hardware is not configured on this server", 503
        )
    data = request.json or {}
    try:
        from nonogram.quantum import list_backends

        backends = list_backends(token, _ibm_channel(data))
        return jsonify(
            {"backends": [{"name": b[0], "qubits": b[1], "pending": b[2]} for b in backends]}
        )
    except Exception as exc:
        from tools.routes.solver import _sanitize_error

        # Runtime client errors can echo request internals or credentials —
        # sanitize before they reach a browser.
        return respond_error("hardware_error", _sanitize_error(exc), 400)


@bp.route("/api/hw/config", methods=["POST"])
def api_hw_config():
    """Enable or disable hardware mode. Credentials come from the server, not the body."""
    data = request.json or {}
    if not data or data.get("disconnect"):
        with state_lock:
            state["hw_config"] = None
        _state_mod.socketio.emit("hw_status", {"connected": False})
        emit_status("Reverted to local statevector simulator.", "ok")
        return jsonify({"ok": True})

    token = _ibm_token()
    if not token:
        return respond_error(
            "hardware_unconfigured", "IBM hardware is not configured on this server", 503
        )
    cfg = {
        "token": token,  # server-held; a caller can never set or read this
        "channel": _ibm_channel(data),
        "backend_name": data.get("backend_name"),
        "shots": min(MAX_SHOTS, max(1, int(data.get("shots", 1024)))),
    }
    with state_lock:
        state["hw_config"] = cfg
    _state_mod.socketio.emit(
        "hw_status",
        {"connected": True, "backend_name": cfg["backend_name"], "shots": cfg["shots"]},
    )
    emit_status(
        f"Hardware mode: {cfg['backend_name']} ({cfg['shots']} shots) "
        f"— real quantum jobs may take several minutes.",
        "warn",
    )
    return jsonify({"ok": True})
