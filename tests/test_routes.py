"""
test_routes.py
~~~~~~~~~~~~~~
Integration tests for the Flask route blueprints.

Uses Flask's test client — no real server, no Socket.IO transport needed.
All solver routes are tested with mocked solvers to avoid slow computation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app():
    """Create a Flask app wired with all blueprints and a test SocketIO."""
    from flask import Flask
    from flask_socketio import SocketIO

    from tools import state as app_state
    from tools.routes import ALL_BLUEPRINTS

    test_app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parent.parent / "tools" / "templates"),
        static_folder=str(Path(__file__).resolve().parent.parent / "tools" / "static"),
    )
    test_app.config["TESTING"] = True
    test_app.config["SECRET_KEY"] = "test"
    # Mirror the production body-size guard (see tools/webapp.py).
    from tools.config import MAX_CONTENT_LENGTH

    test_app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    sio = SocketIO(test_app, async_mode="threading")
    app_state.init(sio)

    for bp in ALL_BLUEPRINTS:
        test_app.register_blueprint(bp)

    # Reset state before each test
    app_state.state.update(
        {
            "rows": 4,
            "cols": 4,
            "grid": [[False] * 4 for _ in range(4)],
            "hw_config": None,
            "busy": False,
            "puzzle_name": "puzzle",
        }
    )

    yield test_app


@pytest.fixture()
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Grid routes
# ---------------------------------------------------------------------------


class TestGridRoutes:
    def test_update_grid(self, client):
        resp = client.post("/api/grid", json={"rows": 3, "cols": 3})
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_grid_rejects_oversized(self, client):
        resp = client.post("/api/grid", json={"rows": 99, "cols": 99})
        assert resp.status_code == 400

    def test_grid_rejects_undersized(self, client):
        resp = client.post("/api/grid", json={"rows": 0, "cols": -1})
        assert resp.status_code == 400

    def test_randomize(self, client):
        resp = client.post("/api/randomize", json={"rows": 3, "cols": 3})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["rows"] == 3
        assert data["cols"] == 3
        assert len(data["grid"]) == 3
        assert all(len(row) == 3 for row in data["grid"])

    def test_randomize_defaults(self, client):
        resp = client.post("/api/randomize", json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["rows"] == 4  # default from state
        assert data["cols"] == 4


# ---------------------------------------------------------------------------
# Puzzle routes
# ---------------------------------------------------------------------------


class TestPuzzleRoutes:
    def test_save_puzzle(self, client):
        payload = {
            "row_clues": [[2], [2]],
            "col_clues": [[2], [2]],
            "name": "test-puzzle",
        }
        resp = client.post("/api/puzzle/save", json=payload)
        assert resp.status_code == 200
        assert resp.content_type == "application/json"
        body = json.loads(resp.data)
        assert body["name"] == "test-puzzle"
        assert body["rows"] == 2

    def test_load_puzzle(self, client, tmp_path):
        puzzle = {
            "name": "loaded",
            "rows": 2,
            "cols": 2,
            "row_clues": [[1], [1]],
            "col_clues": [[1], [1]],
        }
        puzzle_file = tmp_path / "test.non.json"
        puzzle_file.write_text(json.dumps(puzzle))

        from io import BytesIO

        with puzzle_file.open("rb") as f:
            data = BytesIO(f.read())
        data.seek(0)

        resp = client.post(
            "/api/puzzle/load",
            data={"file": (data, "test.non.json")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["name"] == "loaded"
        assert body["rows"] == 2

    def test_load_puzzle_no_file(self, client):
        resp = client.post("/api/puzzle/load")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Solver routes
# ---------------------------------------------------------------------------


class TestSolverRoutes:
    def test_classical_solve_returns_ok(self, client):
        """Classical solve endpoint accepts the request and returns 200."""
        payload = {
            "row_clues": [[2], [2]],
            "col_clues": [[2], [2]],
        }
        resp = client.post("/api/solve/classical", json=payload)
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_quantum_solve_returns_ok(self, client):
        """Quantum solve endpoint accepts the request and returns 200."""
        payload = {
            "row_clues": [[2], [2]],
            "col_clues": [[2], [2]],
        }
        resp = client.post("/api/solve/quantum", json=payload)
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_solver_busy_rejection(self, client):
        """Solver endpoints reject requests when busy."""
        from tools.state import state, state_lock

        with state_lock:
            state["busy"] = True

        payload = {
            "row_clues": [[2], [2]],
            "col_clues": [[2], [2]],
        }
        resp = client.post("/api/solve/classical", json=payload)
        assert resp.status_code == 409

        resp = client.post("/api/solve/quantum", json=payload)
        assert resp.status_code == 409

        resp = client.post("/api/benchmark", json={**payload, "trials": 1})
        assert resp.status_code == 409

        # Clean up
        with state_lock:
            state["busy"] = False

    def test_benchmark_returns_ok(self, client):
        payload = {
            "row_clues": [[2], [2]],
            "col_clues": [[2], [2]],
            "trials": 1,
        }
        resp = client.post("/api/benchmark", json=payload)
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True


class TestSolveDoSGuards:
    """P0: solve routes cap grid AREA (both solvers are exponential in rows*cols)
    and request-body size, and never leave the solver wedged 'busy' on a bad body."""

    # 5×5 = 25 cells, over the 20-cell solve cap.
    OVERSIZED = {"row_clues": [[1]] * 5, "col_clues": [[1]] * 5}

    def test_classical_rejects_oversized_grid(self, client):
        resp = client.post("/api/solve/classical", json=self.OVERSIZED)
        assert resp.status_code == 400
        assert "cell" in resp.get_data(as_text=True).lower()

    def test_quantum_rejects_oversized_grid(self, client):
        resp = client.post("/api/solve/quantum", json=self.OVERSIZED)
        assert resp.status_code == 400

    def test_benchmark_rejects_oversized_grid(self, client):
        resp = client.post("/api/benchmark", json={**self.OVERSIZED, "trials": 1})
        assert resp.status_code == 400

    def test_oversized_body_rejected_with_413(self, client):
        big = b'{"row_clues":[' + b"[1]," * 80000 + b'[1]],"col_clues":[[1]]}'  # > 256 KB
        resp = client.post("/api/solve/classical", data=big, content_type="application/json")
        assert resp.status_code == 413

    def test_bad_request_does_not_wedge_busy(self, client):
        # An oversized-grid 400 must NOT hold the busy lock — a valid solve still runs.
        from tools.state import state, state_lock

        assert client.post("/api/solve/classical", json=self.OVERSIZED).status_code == 400
        ok = client.post(
            "/api/solve/classical", json={"row_clues": [[2], [2]], "col_clues": [[2], [2]]}
        )
        assert ok.status_code == 200

        # Clean up the background solve's busy flag.
        with state_lock:
            state["busy"] = False


# ---------------------------------------------------------------------------
# Hardware routes
# ---------------------------------------------------------------------------


class TestHardwareRoutes:
    def test_hw_config_connect_disconnect(self, client):
        cfg = {
            "token": "fake-token",
            "channel": "ibm_quantum_platform",
            "backend_name": "ibm_test",
            "shots": 512,
        }
        resp = client.post("/api/hw/config", json=cfg)
        assert resp.status_code == 200

        from tools.state import state

        assert state["hw_config"] is not None
        assert state["hw_config"]["backend_name"] == "ibm_test"

        # Disconnect
        resp = client.post("/api/hw/config", json={"disconnect": True})
        assert resp.status_code == 200
        assert state["hw_config"] is None

    def test_hw_config_disconnect_via_disconnect_flag(self, client):
        resp = client.post("/api/hw/config", json={"disconnect": True})
        assert resp.status_code == 200

    def test_hw_backends_missing_runtime(self, client):
        """Backends endpoint returns 400 when qiskit-ibm-runtime errors."""
        resp = client.post(
            "/api/hw/backends",
            json={
                "token": "bad-token",
                "channel": "ibm_quantum_platform",
            },
        )
        # Should return 400 with an error message (auth will fail)
        assert resp.status_code == 400
        assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# Runs routes
# ---------------------------------------------------------------------------


class TestRunsRoutes:
    def test_runs_info(self, client):
        resp = client.get("/api/runs/info")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "count" in data
        assert "total_bytes" in data

    def test_runs_delete(self, client):
        resp = client.post("/api/runs/delete")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_runs_delete_rejected_when_busy(self, client):
        from tools.state import state, state_lock

        with state_lock:
            state["busy"] = True

        resp = client.post("/api/runs/delete")
        assert resp.status_code == 409

        with state_lock:
            state["busy"] = False
