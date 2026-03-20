"""Grid state routes: update grid, randomize."""
from __future__ import annotations

import random

from flask import Blueprint, jsonify, request

from tools.config import MAX_GRID
from tools.state import state, state_lock

bp = Blueprint("grid", __name__)


@bp.route("/api/grid", methods=["POST"])
def api_grid():
    """Update the grid state from a client request."""
    data = request.json
    rows = max(1, min(MAX_GRID, int(data.get("rows", state["rows"]))))
    cols = max(1, min(MAX_GRID, int(data.get("cols", state["cols"]))))
    grid = data.get("grid") or [[False] * cols for _ in range(rows)]
    with state_lock:
        state["rows"] = rows
        state["cols"] = cols
        state["grid"] = grid
    return jsonify({"ok": True})


@bp.route("/api/randomize", methods=["POST"])
def api_randomize():
    """Generate a random grid of specified dimensions."""
    data = request.json or {}
    rows = max(1, min(MAX_GRID, int(data.get("rows", state["rows"]))))
    cols = max(1, min(MAX_GRID, int(data.get("cols", state["cols"]))))
    grid = [[random.random() > 0.5 for _ in range(cols)] for _ in range(rows)]
    with state_lock:
        state["rows"] = rows
        state["cols"] = cols
        state["grid"] = grid
    return jsonify({"rows": rows, "cols": cols, "grid": grid})
