"""Shared fixtures and helpers for the nonogram test suite."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

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


_DEFAULT_STATE = {
    "rows": 4,
    "cols": 4,
    "grid": [[False] * 4 for _ in range(4)],
    "hw_config": None,
    "busy": False,
    "puzzle_name": "puzzle",
}


@pytest.fixture(autouse=True)
def reset_server_state():
    """Give every test the same server state; the app object is a process-wide singleton.

    Teardown waits for a solve still running in its worker thread: clearing the busy
    flag under it would let the next test's solve start alongside it, and the loser of
    that race gets a 409 it never asked for.
    """
    from tools import state as app_state

    with app_state.state_lock:
        app_state.state.update({**_DEFAULT_STATE, "grid": [[False] * 4 for _ in range(4)]})
    yield
    deadline = time.monotonic() + 60
    while app_state.state["busy"] and time.monotonic() < deadline:
        time.sleep(0.05)
    with app_state.state_lock:
        app_state.state["busy"] = False


@pytest.fixture()
def webapp():
    """The deployed app object — guard, CORS allowlist, body cap and error envelope included."""
    from tools.webapp import app

    app.config["TESTING"] = True
    return app


@pytest.fixture()
def client(webapp):
    return webapp.test_client()


@pytest.fixture()
def sio_client(webapp):
    """Socket.IO client attached to the deployed app."""
    from flask_socketio import SocketIOTestClient

    from tools.webapp import socketio

    test_client = SocketIOTestClient(webapp, socketio)
    yield test_client
    test_client.disconnect()


def collect_events(sio_client, target_event: str, timeout: float = 15.0) -> list[dict]:
    """Poll a Socket.IO test client for *target_event* until timeout.

    ``get_received`` drains the queue, so events of other names are buffered on the
    client and stay visible to later calls: a test can wait for ``cl_done`` and then
    still read the ``status`` that preceded it.
    """
    buffer = getattr(sio_client, "_collected", None)
    if buffer is None:
        buffer = sio_client._collected = []
    deadline = time.monotonic() + timeout
    while True:
        buffer.extend(sio_client.get_received())
        matched = [item for item in buffer if item["name"] == target_event]
        if matched or time.monotonic() >= deadline:
            for item in matched:
                buffer.remove(item)
            return [item["args"][0] if item.get("args") else {} for item in matched]
        time.sleep(0.1)


@pytest.fixture()
def busy_solver():
    """Hold the busy flag for a test, and release it however the test ends.

    Tests that set the flag by hand and leave it set strand the teardown wait, which
    exists for solves that are genuinely still running.
    """
    from tools import state as app_state

    with app_state.state_lock:
        app_state.state["busy"] = True
    yield
    with app_state.state_lock:
        app_state.state["busy"] = False
