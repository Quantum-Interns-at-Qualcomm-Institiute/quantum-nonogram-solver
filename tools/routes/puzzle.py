"""Puzzle I/O routes: load and save puzzles."""

from __future__ import annotations

import io
import json

from flask import Blueprint, jsonify, request, send_file

from tools.errors import respond_error
from tools.state import state, state_lock

bp = Blueprint("puzzle", __name__)


@bp.route("/api/puzzle/load", methods=["POST"])
def api_puzzle_load():
    """Load a puzzle from a .non.json file upload."""
    f = request.files.get("file")
    if not f:
        return respond_error("no_file", "No file", 400)
    import tempfile
    from pathlib import Path

    from nonogram.errors import PuzzleIOError, ValidationError
    from nonogram.io import load_puzzle

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        f.save(tmp.name)
        try:
            # load_puzzle validates clue shape, values, and the per-line size cap
            # BEFORE we allocate the grid below. A bad upload is a 400, not a 500.
            data = load_puzzle(tmp.name)
        except (ValidationError, PuzzleIOError, ValueError, KeyError) as exc:
            return respond_error("invalid_puzzle", str(exc)[:500], 400)
        finally:
            Path(tmp.name).unlink()
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
    if data is None:
        return respond_error("invalid_json", "Invalid or missing JSON body", 400)
    try:
        row_clues = [tuple(c) for c in data["row_clues"]]
        col_clues = [tuple(c) for c in data["col_clues"]]
    except (KeyError, TypeError):
        return respond_error(
            "invalid_clues", "body must carry 'row_clues' and 'col_clues' as lists", 400
        )
    from nonogram.errors import ValidationError
    from nonogram.io import _slugify, _validate_clues

    try:
        _validate_clues(row_clues, col_clues)
    except ValidationError as exc:
        return respond_error("invalid_clues", str(exc)[:500], 400)
    # The display name stays as given (bounded); only the filename is slugified,
    # since it lands in a Content-Disposition header.
    name = (data.get("name", state["puzzle_name"]) or "puzzle")[:100]
    safe_name = _slugify(name)
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
        buf, mimetype="application/json", as_attachment=True, download_name=f"{safe_name}.non.json"
    )
