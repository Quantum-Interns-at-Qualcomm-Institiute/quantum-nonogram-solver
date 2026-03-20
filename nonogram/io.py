"""
nonogram.io
~~~~~~~~~~~
Puzzle serialization / deserialization.

File format: JSON with extension ``.non.json``.

Schema::

    {
        "name":      "My Puzzle",
        "rows":      4,
        "cols":      6,
        "row_clues": [[1,1],[2,2],[1,2,1],[1,1]],
        "col_clues": [[4],[1],[1],[1],[1],[4]],
        "created":   "2026-03-11T12:00:00",
        "tags":      []
    }

Usage::

    from nonogram.io import save_puzzle, load_puzzle, save_batch, load_batch

    # Save one puzzle
    save_puzzle([[1,1],[2,2]], [[4],[1],[1]], "my_puzzle.non.json", name="Demo")

    # Load it back
    data = load_puzzle("my_puzzle.non.json")
    row_clues = [tuple(r) for r in data["row_clues"]]
    col_clues  = [tuple(c) for c in data["col_clues"]]

    # Batch helpers
    save_batch(list_of_dicts, folder="puzzles/")
    puzzles = load_batch("puzzles/")
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nonogram.errors import PuzzleIOError, ValidationError

__all__ = ["save_puzzle", "load_puzzle", "save_batch", "load_batch"]

_MAX_LINE = 6  # matches existing data.py lookup table


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_clues(row_clues: list, col_clues: list) -> None:
    """Raise ValidationError if clues are obviously malformed."""
    for i, clue in enumerate(row_clues):
        for v in clue:
            if not isinstance(v, int) or v < 0:
                raise ValidationError(
                    f"row_clues[{i}] contains non-integer or negative value: {v!r}"
                )
    for j, clue in enumerate(col_clues):
        for v in clue:
            if not isinstance(v, int) or v < 0:
                raise ValidationError(
                    f"col_clues[{j}] contains non-integer or negative value: {v!r}"
                )
    if len(row_clues) > _MAX_LINE or len(col_clues) > _MAX_LINE:
        raise ValidationError(
            f"Puzzle exceeds maximum supported size ({_MAX_LINE}×{_MAX_LINE}). "
            f"Got {len(row_clues)}×{len(col_clues)}."
        )


def _slugify(name: str) -> str:
    """Turn a puzzle name into a safe filename stem."""
    slug = name.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug or "puzzle"


def _to_serialisable(clues: list) -> list[list[int]]:
    """Convert list-of-tuples or list-of-lists to list-of-lists of plain ints."""
    return [[int(v) for v in group] for group in clues]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def save_puzzle(
    row_clues: list,
    col_clues: list,
    path: str | Path,
    name: str = "",
    tags: list[str] | None = None,
) -> None:
    """Serialise a single puzzle to *path* as JSON.

    Parameters
    ----------
    row_clues:
        List of row clue groups, e.g. ``[(1, 1), (2,), (3,)]``.
    col_clues:
        List of column clue groups in the same format.
    path:
        Destination file path.  The ``.non.json`` extension is recommended
        but not enforced.
    name:
        Human-readable puzzle name stored in the file.
    tags:
        Optional list of string tags (e.g. ``["easy", "5x5"]``).
    """
    _validate_clues(row_clues, col_clues)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {
        "name": name or path.stem,
        "rows": len(row_clues),
        "cols": len(col_clues),
        "row_clues": _to_serialisable(row_clues),
        "col_clues": _to_serialisable(col_clues),
        "created": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "tags": list(tags) if tags else [],
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_puzzle(path: str | Path) -> dict[str, Any]:
    """Load a puzzle from a ``.non.json`` file.

    Returns a dict with keys:
    ``name``, ``rows``, ``cols``, ``row_clues``, ``col_clues``,
    ``created``, ``tags``.

    Clue values are plain Python lists-of-lists of ``int``.
    Convert to tuples if your solver requires them::

        row_clues = [tuple(r) for r in data["row_clues"]]
    """
    path = Path(path)
    if not path.exists():
        raise PuzzleIOError(f"Puzzle file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))

    # Normalise older/hand-written files that may omit optional keys
    # Strip both suffixes for .non.json files (path.stem only removes one)
    stem = path.stem
    if stem.endswith(".non"):
        stem = stem[:-4]
    data.setdefault("name", stem)
    data.setdefault("tags", [])
    data.setdefault("created", "")
    data["rows"] = len(data["row_clues"])
    data["cols"] = len(data["col_clues"])
    return data


def save_batch(
    puzzles: list[dict[str, Any]],
    folder: str | Path,
) -> list[Path]:
    """Write a list of puzzle dicts to *folder*, one file each.

    Each dict must contain ``row_clues``, ``col_clues``, and optionally
    ``name`` and ``tags`` (all other keys are ignored / recomputed).

    Files are named ``{slug}_{idx:03d}.non.json``.  Returns the list of
    written file paths.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for idx, pz in enumerate(puzzles):
        name = pz.get("name", f"puzzle_{idx:03d}")
        slug = _slugify(name)
        dest = folder / f"{slug}_{idx:03d}.non.json"
        save_puzzle(
            row_clues=pz["row_clues"],
            col_clues=pz["col_clues"],
            path=dest,
            name=name,
            tags=pz.get("tags"),
        )
        written.append(dest)
    return written


def load_batch(folder: str | Path) -> list[dict[str, Any]]:
    """Load all ``.non.json`` files from *folder* and return a sorted list of
    puzzle dicts (sorted by filename for reproducibility).

    Each item is the same dict structure returned by :func:`load_puzzle`.
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise PuzzleIOError(f"Batch folder not found: {folder}")
    files = sorted(folder.glob("*.non.json"))
    return [load_puzzle(f) for f in files]
