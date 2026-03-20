"""Run cache routes: info, delete."""

from __future__ import annotations

import json

from flask import Blueprint, jsonify

from tools.config import RUNS_DIR
from tools.state import state, state_lock

bp = Blueprint("runs", __name__)


@bp.route("/api/runs/info", methods=["GET"])
def api_runs_info():
    """Return metadata about cached run files in RUNS_DIR."""
    files = sorted(RUNS_DIR.glob("run_*.json"))
    total_bytes = sum(f.stat().st_size for f in files)
    timestamps: list[str] = []
    for f in files:
        try:
            with open(f) as fh:
                d = json.load(fh)
            if d.get("timestamp"):
                timestamps.append(d["timestamp"])
        except Exception:
            pass
    return jsonify(
        {
            "count": len(files),
            "total_bytes": total_bytes,
            "oldest": min(timestamps) if timestamps else None,
            "newest": max(timestamps) if timestamps else None,
        }
    )


@bp.route("/api/runs/delete", methods=["POST"])
def api_runs_delete():
    """Delete all cached run files. Rejected while a solve is in progress."""
    with state_lock:
        busy = state["busy"]
    if busy:
        return jsonify({"ok": False, "error": "A run is in progress"}), 409
    deleted = 0
    for f in RUNS_DIR.glob("run_*.json"):
        try:
            f.unlink()
            deleted += 1
        except Exception:
            pass
    return jsonify({"ok": True, "deleted": deleted})
