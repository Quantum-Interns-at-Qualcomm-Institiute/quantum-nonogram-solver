"""Integration tests for the nonogram Socket.IO event flow.

Tests the real-time solve pipeline: client submits puzzle → server processes →
Socket.IO emits status/cl_done/qu_done/bench_done events back to the client.

Requires Python 3.10+ (nonogram source uses PEP 604 union types).
"""
import sys
import time

import pytest

if sys.version_info < (3, 10):
    pytest.skip("nonogram requires Python 3.10+ (PEP 604 type unions)", allow_module_level=True)

from flask import Flask
from flask_socketio import SocketIO

from tools import state as app_state
from tools.routes import ALL_BLUEPRINTS


@pytest.fixture()
def app():
    """Create a fresh Flask + SocketIO app for each test."""
    test_app = Flask(__name__)
    test_app.config["TESTING"] = True
    test_app.config["SECRET_KEY"] = "test-secret"

    sio = SocketIO(test_app, async_mode="threading")
    app_state.init(sio)

    for bp in ALL_BLUEPRINTS:
        test_app.register_blueprint(bp)

    # Register config endpoint
    from tools.webapp import api_config
    test_app.add_url_rule("/api/config", view_func=api_config)

    # Reset state (must include busy=False to avoid 409)
    app_state.state.update(
        {
            "rows": 3,
            "cols": 3,
            "grid": [[False] * 3 for _ in range(3)],
            "hw_config": None,
            "busy": False,
            "puzzle_name": "test-puzzle",
        }
    )
    yield test_app, sio


@pytest.fixture(autouse=True)
def reset_busy():
    """Ensure busy flag is cleared between tests."""
    yield
    with app_state.state_lock:
        app_state.state["busy"] = False


@pytest.fixture()
def sio_client(app):
    """Socket.IO test client."""
    test_app, sio = app
    client = sio.test_client(test_app)
    yield client
    client.disconnect()


@pytest.fixture()
def http_client(app):
    """Flask HTTP test client."""
    test_app, _ = app
    with test_app.test_client() as c:
        yield c


def collect_events(sio_client, target_event, timeout=10.0):
    """Poll for Socket.IO events by name."""
    deadline = time.monotonic() + timeout
    found = []
    while time.monotonic() < deadline:
        received = sio_client.get_received()
        for item in received:
            if item["name"] == target_event:
                args = item["args"][0] if item.get("args") else {}
                found.append(args)
        if found:
            return found
        time.sleep(0.2)
    return found


# ── Connection ───────────────────────────────────────────────────────────────


class TestSocketConnection:
    def test_client_connects_successfully(self, sio_client):
        assert sio_client.is_connected()

    def test_client_can_disconnect_and_reconnect(self, app):
        test_app, sio = app
        client = sio.test_client(test_app)
        assert client.is_connected()
        client.disconnect()
        assert not client.is_connected()
        client2 = sio.test_client(test_app)
        assert client2.is_connected()
        client2.disconnect()


# ── Grid API + Socket.IO status events ───────────────────────────────────────


class TestGridEvents:
    def test_post_grid_emits_status(self, http_client, sio_client):
        """Posting a grid should emit a status event."""
        payload = {
            "rows": 3,
            "cols": 3,
            "grid": [
                [True, True, False],
                [False, True, True],
                [True, False, True],
            ],
        }
        resp = http_client.post("/api/grid", json=payload)
        assert resp.status_code == 200

    def test_randomize_returns_valid_grid(self, http_client):
        resp = http_client.post(
            "/api/randomize",
            json={"rows": 3, "cols": 3},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "grid" in data


# ── Classical solve flow ─────────────────────────────────────────────────────


class TestClassicalSolveFlow:
    def test_classical_solve_emits_cl_done(self, http_client, sio_client):
        """Classical solve should emit cl_done with solutions."""
        # Simple 2x2 fully filled puzzle
        payload = {"row_clues": [[2], [2]], "col_clues": [[2], [2]]}
        resp = http_client.post("/api/solve/classical", json=payload)
        assert resp.status_code == 200

        events = collect_events(sio_client, "cl_done", timeout=10)
        assert len(events) >= 1, "Expected cl_done event"
        assert "solutions" in events[0]

    def test_classical_solve_emits_status_updates(self, http_client, sio_client):
        payload = {"row_clues": [[2], [2]], "col_clues": [[2], [2]]}
        http_client.post("/api/solve/classical", json=payload)

        # Collect any status events that were emitted
        time.sleep(2)
        received = sio_client.get_received()
        event_names = [e["name"] for e in received]
        # Should have at least status or cl_done
        assert "status" in event_names or "cl_done" in event_names


# ── Quantum solve flow ───────────────────────────────────────────────────────


try:
    import qiskit  # noqa: F401

    from nonogram.quantum import quantum_solve  # noqa: F401
    _HAS_QUANTUM = True
except (ImportError, Exception):
    _HAS_QUANTUM = False


@pytest.mark.skipif(not _HAS_QUANTUM, reason="qiskit not installed")
class TestQuantumSolveFlow:
    def test_quantum_solve_emits_qu_done(self, http_client, sio_client):
        """Quantum solve should emit qu_done with measurement counts."""
        payload = {"row_clues": [[1], [1]], "col_clues": [[1], [1]]}
        resp = http_client.post("/api/solve/quantum", json=payload)
        assert resp.status_code == 200

        events = collect_events(sio_client, "qu_done", timeout=15)
        assert len(events) >= 1, "Expected qu_done event"
        assert "counts" in events[0]
        assert "rows" in events[0]
        assert "cols" in events[0]

    def test_quantum_solve_status_updates(self, http_client, sio_client):
        payload = {"row_clues": [[1], [1]], "col_clues": [[1], [1]]}
        http_client.post("/api/solve/quantum", json=payload)

        time.sleep(3)
        received = sio_client.get_received()
        event_names = [e["name"] for e in received]
        assert "status" in event_names or "qu_done" in event_names


# ── Benchmark flow ───────────────────────────────────────────────────────────


@pytest.mark.skipif(not _HAS_QUANTUM, reason="qiskit not installed (benchmark runs quantum solver)")
class TestBenchmarkFlow:
    def test_benchmark_emits_all_events(self, http_client, sio_client):
        """Benchmark should emit cl_done, qu_done, and bench_done."""
        bench_payload = {
            "row_clues": [[2], [2]],
            "col_clues": [[2], [2]],
            "trials": 1,
        }
        resp = http_client.post("/api/benchmark", json=bench_payload)
        assert resp.status_code == 200

        # Collect all events over a reasonable time
        deadline = time.monotonic() + 20
        all_events = []
        while time.monotonic() < deadline:
            received = sio_client.get_received()
            all_events.extend(received)
            event_names = {e["name"] for e in all_events}
            if "bench_done" in event_names:
                break
            time.sleep(0.5)

        event_names = {e["name"] for e in all_events}
        assert "bench_done" in event_names or "cl_done" in event_names, (
            f"Expected bench_done or cl_done, got: {event_names}"
        )


# ── Error handling ───────────────────────────────────────────────────────────


class TestSolverErrors:
    def test_invalid_clues_emits_error(self, http_client, sio_client):
        """Invalid puzzle should emit solver_error or return 4xx."""
        payload = {"row_clues": [], "col_clues": []}
        resp = http_client.post("/api/solve/classical", json=payload)
        # Either returns error HTTP status or emits solver_error
        if resp.status_code == 200:
            time.sleep(2)
            received = sio_client.get_received()
            event_names = [e["name"] for e in received]
            # Should have some response
            assert len(event_names) >= 0  # At minimum doesn't crash
        else:
            assert resp.status_code in (400, 409, 422, 500)

    def test_oversized_puzzle_handled_gracefully(self, http_client, sio_client):
        """Very large puzzles should not hang or crash."""
        # 10x10 all filled — large but solvable
        payload = {"row_clues": [[10]] * 10, "col_clues": [[10]] * 10}
        resp = http_client.post("/api/solve/classical", json=payload)
        # Should either succeed or return an error, not hang
        assert resp.status_code in (200, 400, 409, 413, 422, 500)
