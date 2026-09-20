"""Grid state routes: update grid, randomize."""

from __future__ import annotations

import random

from flask import Blueprint, jsonify, request

from nonogram.errors import ValidationError
from tools.config import MAX_GRID
from tools.errors import json_object, require_int, respond_error
from tools.state import state, state_lock

bp = Blueprint("grid", __name__)


def _dimensions(data: dict) -> tuple[int, int]:
    """Read rows and cols from the body, defaulting to the current state."""
    rows = require_int(data, "rows", state.get("rows", 5), minimum=1, maximum=MAX_GRID)
    cols = require_int(data, "cols", state.get("cols", 5), minimum=1, maximum=MAX_GRID)
    return rows, cols


@bp.route("/api/grid", methods=["POST"])
def api_grid():
    """Update the grid state from a client request."""
    data = request.json
    if data is None:
        return respond_error("invalid_json", "Invalid or missing JSON body", 400)
    try:
        rows, cols = _dimensions(json_object(data))
    except ValidationError as exc:
        return respond_error("invalid_dimensions", str(exc), 400)
    grid = data.get("grid")
    if grid is not None:
        if not isinstance(grid, list) or not all(isinstance(row, list) for row in grid):
            return respond_error("invalid_grid", "Grid must be a 2D array", 400)
        if len(grid) != rows or any(len(row) != cols for row in grid):
            return respond_error("invalid_grid", f"Grid dimensions must be {rows}x{cols}", 400)
    else:
        grid = [[False] * cols for _ in range(rows)]
    with state_lock:
        state["rows"] = rows
        state["cols"] = cols
    return jsonify({"ok": True})


@bp.route("/api/randomize", methods=["POST"])
def api_randomize():
    """Generate a random grid of specified dimensions."""
    try:
        rows, cols = _dimensions(json_object(request.json or {}))
    except ValidationError as exc:
        return respond_error("invalid_dimensions", str(exc), 400)
    grid = [[random.random() > 0.5 for _ in range(cols)] for _ in range(rows)]  # noqa: S311 — puzzle randomization
    with state_lock:
        state["rows"] = rows
        state["cols"] = cols
    return jsonify({"rows": rows, "cols": cols, "grid": grid})
