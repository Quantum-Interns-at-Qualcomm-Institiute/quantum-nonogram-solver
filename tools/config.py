"""Shared constants for the nonogram web app."""

from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent

MAX_CLUES = 3
MAX_GRID = 10
# Clue payloads are a few hundred bytes; anything larger gets a 413 before parsing.
MAX_CONTENT_LENGTH = 256 * 1024  # 256 KB

# Each trial is a full solve, so this bounds compute; above it requests are clamped
# (the UI offers 20; beyond that the extra trials only add sampling noise).
MAX_TRIALS = 25

#: Largest puzzle a hardware run accepts. Transpiled depth is ~139 layers at 4 cells,
#: ~907 at 6 and ~3,020 at 9, against ~100-200 layers of Eagle/Heron coherence.
MAX_HW_CELLS = 6

RUNS_DIR = ROOT / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)
