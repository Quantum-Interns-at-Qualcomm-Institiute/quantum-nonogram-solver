"""IBM quantum hardware routes: backends, connect/disconnect."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from tools import state as _state_mod
from tools.state import emit_status, state, state_lock

bp = Blueprint("hardware", __name__)


@bp.route("/api/hw/backends", methods=["POST"])
def api_hw_backends():
    """List available IBM quantum backends."""
    data = request.json
    if data is None:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    try:
        from nonogram.quantum import list_backends

        backends = list_backends(data["token"], data["channel"])
        return jsonify(
            {"backends": [{"name": b[0], "qubits": b[1], "pending": b[2]} for b in backends]}
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@bp.route("/api/hw/config", methods=["POST"])
def api_hw_config():
    """Connect to or disconnect from IBM quantum hardware."""
    data = request.json
    if data is None or data.get("disconnect"):
        with state_lock:
            state["hw_config"] = None
        _state_mod.socketio.emit("hw_status", {"connected": False})
        emit_status("Reverted to local statevector simulator.", "ok")
    else:
        cfg = {
            "token": data["token"],
            "channel": data["channel"],
            "backend_name": data["backend_name"],
            "shots": int(data.get("shots", 1024)),
        }
        with state_lock:
            state["hw_config"] = cfg
        _state_mod.socketio.emit(
            "hw_status",
            {
                "connected": True,
                "backend_name": cfg["backend_name"],
                "shots": cfg["shots"],
            },
        )
        emit_status(
            f"Hardware mode: {cfg['backend_name']} ({cfg['shots']} shots) "
            f"\u2014 real quantum jobs may take several minutes.",
            "warn",
        )
    return jsonify({"ok": True})
