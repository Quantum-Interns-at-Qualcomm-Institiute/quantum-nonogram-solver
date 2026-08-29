"""Shared constants for the nonogram web app."""

from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent

MAX_CLUES = 3
MAX_GRID = 10
# Max API request-body size. Clue payloads are a few hundred bytes; anything larger
# is rejected with 413 before parsing (DoS guard). Shared by webapp.py and tests.
MAX_CONTENT_LENGTH = 256 * 1024  # 256 KB

PUZZLES_DIR = ROOT / "puzzles"
PUZZLES_DIR.mkdir(parents=True, exist_ok=True)

RUNS_DIR = ROOT / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)
