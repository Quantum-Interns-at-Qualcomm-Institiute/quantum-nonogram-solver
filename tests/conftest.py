"""Shared fixtures and helpers for the nonogram test suite."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# The real app's front-door guard fails closed; tests opt into unguarded local mode
# (the guard's own tests set ORIGIN_SECRET and override this).
os.environ.setdefault("NONOGRAM_ALLOW_INSECURE", "1")

# Ensure the project root is importable regardless of how pytest is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load_ibm_token() -> str | None:
    """Load the IBM Quantum API token.

    Checks (in order):
      1. ``IBM_QUANTUM_TOKEN`` environment variable
      2. ``KEY=<token>`` in the project-root ``.env`` file

    Returns *None* when neither source provides a token — callers
    typically use this with ``pytest.mark.skipif`` to skip hardware tests
    on machines that haven't configured an IBM Quantum token.

    No ``python-dotenv`` dependency is required.
    """
    import os

    # Prefer environment variable
    tok = os.environ.get("IBM_QUANTUM_TOKEN", "").strip()
    if tok:
        return tok

    # Fall back to .env file
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return None
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if line.startswith("IBM_QUANTUM_TOKEN="):
            tok = line[len("IBM_QUANTUM_TOKEN=") :].strip()
            return tok or None
    return None


def save_hardware_run(name: str, puzzle: tuple[list, list], counts: dict, run_info: dict) -> Path:
    """Write a hardware run's counts and job metadata to runs/hardware/, which is gitignored."""
    import json
    from datetime import datetime, timezone

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = Path(__file__).resolve().parent.parent / "runs" / "hardware" / f"{name}-{stamp}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "puzzle": {"row_clues": puzzle[0], "col_clues": puzzle[1]},
        **run_info,
        "saved_at": stamp,
        "counts": counts,
    }
    dest.write_text(json.dumps(record, indent=2) + "\n")
    return dest
