"""Puzzle I/O routes: load and save puzzles."""

from __future__ import annotations

import io
import json

from flask import Blueprint, jsonify, request, send_file

from tools.state import state, state_lock

bp = Blueprint("puzzle", __name__)


@bp.route("/api/puzzle/load", methods=["POST"])
def api_puzzle_load():
    """Load a puzzle from a .non.json file upload."""
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file"}), 400
    import os
    import tempfile

    from nonogram.io import load_puzzle

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        f.save(tmp.name)
        try:
            data = load_puzzle(tmp.name)
        finally:
            os.unlink(tmp.name)
    row_clues = [list(r) for r in data["row_clues"]]
    col_clues = [list(c) for c in data["col_clues"]]
    with state_lock:
        state["puzzle_name"] = data.get("name", "puzzle") or "puzzle"
        state["rows"] = len(row_clues)
        state["cols"] = len(col_clues)
        state["grid"] = [[False] * len(col_clues) for _ in range(len(row_clues))]
    return jsonify(
        {
            "name": state["puzzle_name"],
            "rows": state["rows"],
            "cols": state["cols"],
            "row_clues": row_clues,
            "col_clues": col_clues,
        }
    )


@bp.route("/api/puzzle/save", methods=["POST"])
def api_puzzle_save():
    """Download the current puzzle as a .non.json file."""
    data = request.json
    row_clues = [tuple(c) for c in data["row_clues"]]
    col_clues = [tuple(c) for c in data["col_clues"]]
    name = data.get("name", state["puzzle_name"]) or "puzzle"
    buf = io.BytesIO()
    payload = {
        "name": name,
        "rows": len(row_clues),
        "cols": len(col_clues),
        "row_clues": [list(c) for c in row_clues],
        "col_clues": [list(c) for c in col_clues],
    }
    buf.write(json.dumps(payload, indent=2).encode())
    buf.seek(0)
    return send_file(
        buf, mimetype="application/json", as_attachment=True, download_name=f"{name}.non.json"
    )
