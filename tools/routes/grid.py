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
    if data is None:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    rows = int(data.get("rows", state.get("rows", 5)))
    cols = int(data.get("cols", state.get("cols", 5)))
    if not (1 <= rows <= MAX_GRID and 1 <= cols <= MAX_GRID):
        return jsonify({"error": f"Grid dimensions must be 1-{MAX_GRID}"}), 400
    grid = data.get("grid")
    if grid is not None:
        if not isinstance(grid, list) or not all(isinstance(row, list) for row in grid):
            return jsonify({"error": "Grid must be a 2D array"}), 400
        if len(grid) != rows or any(len(row) != cols for row in grid):
            return jsonify({"error": f"Grid dimensions must be {rows}x{cols}"}), 400
    else:
        grid = [[False] * cols for _ in range(rows)]
    with state_lock:
        state["rows"] = rows
        state["cols"] = cols
        state["grid"] = grid
    return jsonify({"ok": True})


@bp.route("/api/randomize", methods=["POST"])
def api_randomize():
    """Generate a random grid of specified dimensions."""
    data = request.json or {}
    rows = int(data.get("rows", state.get("rows", 5)))
    cols = int(data.get("cols", state.get("cols", 5)))
    if not (1 <= rows <= MAX_GRID and 1 <= cols <= MAX_GRID):
        return jsonify({"error": f"Grid dimensions must be 1-{MAX_GRID}"}), 400
    grid = [[random.random() > 0.5 for _ in range(cols)] for _ in range(rows)]
    with state_lock:
        state["rows"] = rows
        state["cols"] = cols
        state["grid"] = grid
    return jsonify({"rows": rows, "cols": cols, "grid": grid})
