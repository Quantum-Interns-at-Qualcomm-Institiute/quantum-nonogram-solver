"""Shared constants for the nonogram web app."""
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent

MAX_CLUES = 3
MAX_GRID = 6

PUZZLES_DIR = ROOT / "puzzles"
PUZZLES_DIR.mkdir(parents=True, exist_ok=True)

RUNS_DIR = ROOT / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)
