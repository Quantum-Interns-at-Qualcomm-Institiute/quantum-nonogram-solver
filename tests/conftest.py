"""Shared fixtures and helpers for the nonogram test suite."""

from __future__ import annotations

import sys
from pathlib import Path

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
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("IBM_QUANTUM_TOKEN="):
            tok = line[len("IBM_QUANTUM_TOKEN=") :].strip()
            return tok if tok else None
    return None
