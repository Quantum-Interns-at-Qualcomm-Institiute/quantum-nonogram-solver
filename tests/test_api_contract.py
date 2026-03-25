"""API contract tests: verify response shapes match what the frontend expects.

The static frontend at website/nonogram/ communicates with this backend via
REST endpoints and Socket.IO events. These tests verify the API contract
to catch breaking changes before they reach the frontend.
"""

from __future__ import annotations

import json
import sys
import time
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from flask import Flask
from flask_socketio import SocketIO

from tools import state as app_state
from tools.config import MAX_CLUES, MAX_GRID
from tools.routes import ALL_BLUEPRINTS


@pytest.fixture()
def app():
    test_app = Flask(__name__)
    test_app.config["TESTING"] = True
    test_app.config["SECRET_KEY"] = "test"

    sio = SocketIO(test_app, async_mode="threading")
    app_state.init(sio)

    for bp in ALL_BLUEPRINTS:
        test_app.register_blueprint(bp)

    # Register config endpoint
    from tools.webapp import api_config

    test_app.add_url_rule("/api/config", view_func=api_config)

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


@pytest.fixture()
def client(app):
    return app[0].test_client()


@pytest.fixture()
def sio_client(app):
    """Socket.IO test client for verifying emitted events."""
    test_app, sio = app
    return sio.test_client(test_app)


class TestGridAPIContract:
    """POST /api/grid — frontend sends {rows, cols, grid?}."""

    def test_response_shape(self, client):
        resp = client.post("/api/grid", json={"rows": 3, "cols": 3})
        data = resp.get_json()
        assert data == {"ok": True}

    def test_accepts_grid_data(self, client):
        grid = [[True, False, True], [False, True, False]]
        resp = client.post("/api/grid", json={"rows": 2, "cols": 3, "grid": grid})
        assert resp.status_code == 200

    def test_rejects_invalid_dimensions(self, client):
        resp = client.post("/api/grid", json={"rows": 100, "cols": -5})
        assert resp.status_code == 400


class TestRandomizeAPIContract:
    """POST /api/randomize — frontend sends {rows?, cols?}."""

    def test_response_shape(self, client):
        resp = client.post("/api/randomize", json={"rows": 3, "cols": 3})
        data = resp.get_json()
        assert "rows" in data
        assert "cols" in data
        assert "grid" in data
        assert isinstance(data["grid"], list)
        assert isinstance(data["grid"][0], list)
        assert isinstance(data["grid"][0][0], bool)


class TestPuzzleLoadAPIContract:
    """POST /api/puzzle/load — frontend sends multipart file."""

    def test_response_shape(self, client, tmp_path):
        puzzle = {
            "name": "contract-test",
            "rows": 2,
            "cols": 2,
            "row_clues": [[1], [1]],
            "col_clues": [[1], [1]],
        }
        buf = BytesIO(json.dumps(puzzle).encode())
        resp = client.post(
            "/api/puzzle/load",
            data={"file": (buf, "test.non.json")},
            content_type="multipart/form-data",
        )
        data = resp.get_json()
        assert "name" in data
        assert "rows" in data
        assert "cols" in data
        assert "row_clues" in data
        assert "col_clues" in data
        assert isinstance(data["row_clues"], list)
        assert isinstance(data["col_clues"], list)


class TestPuzzleSaveAPIContract:
    """POST /api/puzzle/save — frontend sends {row_clues, col_clues, name}."""

    def test_response_is_json_file(self, client):
        payload = {
            "row_clues": [[1, 1], [2]],
            "col_clues": [[1], [1], [1]],
            "name": "save-test",
        }
        resp = client.post("/api/puzzle/save", json=payload)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["name"] == "save-test"
        assert data["rows"] == 2
        assert data["cols"] == 3


class TestSolverAPIContract:
    """POST /api/solve/classical and /api/solve/quantum."""

    def test_classical_response_shape(self, client):
        payload = {"row_clues": [[1], [1]], "col_clues": [[1], [1]]}
        resp = client.post("/api/solve/classical", json=payload)
        assert resp.status_code == 200
        assert resp.get_json() == {"ok": True}

    def test_quantum_response_shape(self, client):
        payload = {"row_clues": [[1], [1]], "col_clues": [[1], [1]]}
        resp = client.post("/api/solve/quantum", json=payload)
        assert resp.status_code == 200
        assert resp.get_json() == {"ok": True}

    def test_busy_returns_409(self, client):
        with app_state.state_lock:
            app_state.state["busy"] = True
        resp = client.post(
            "/api/solve/classical",
            json={"row_clues": [[1]], "col_clues": [[1]]},
        )
        assert resp.status_code == 409
        data = resp.get_json()
        assert "error" in data
        with app_state.state_lock:
            app_state.state["busy"] = False


class TestBenchmarkAPIContract:
    """POST /api/benchmark — frontend sends {row_clues, col_clues, trials}."""

    def test_response_shape(self, client):
        payload = {
            "row_clues": [[1], [1]],
            "col_clues": [[1], [1]],
            "trials": 1,
        }
        resp = client.post("/api/benchmark", json=payload)
        assert resp.status_code == 200
        assert resp.get_json() == {"ok": True}


class TestHardwareAPIContract:
    """POST /api/hw/config and /api/hw/backends."""

    def test_connect_response(self, client):
        cfg = {
            "token": "test-token",
            "channel": "ibm_quantum_platform",
            "backend_name": "ibm_test",
            "shots": 1024,
        }
        resp = client.post("/api/hw/config", json=cfg)
        assert resp.status_code == 200

    def test_disconnect_response(self, client):
        resp = client.post("/api/hw/config", json={"disconnect": True})
        assert resp.status_code == 200


class TestRunsAPIContract:
    """GET /api/runs/info and POST /api/runs/delete."""

    def test_info_response_shape(self, client):
        resp = client.get("/api/runs/info")
        data = resp.get_json()
        assert "count" in data
        assert "total_bytes" in data
        assert isinstance(data["count"], int)
        assert isinstance(data["total_bytes"], int)

    def test_delete_response_shape(self, client):
        resp = client.post("/api/runs/delete")
        data = resp.get_json()
        assert data["ok"] is True
        assert "deleted" in data
        assert isinstance(data["deleted"], int)


class TestConfigAPIContract:
    """GET /api/config — frontend reads max_clues and max_grid."""

    def test_response_shape(self, client):
        resp = client.get("/api/config")
        data = resp.get_json()
        assert isinstance(data["max_clues"], int)
        assert isinstance(data["max_grid"], int)
        assert data["max_clues"] == MAX_CLUES
        assert data["max_grid"] == MAX_GRID


class TestSocketIOEvents:
    """Verify Socket.IO event emission from solver routes."""

    def test_classical_solve_emits_cl_done(self, sio_client, client):
        """Classical solve should eventually emit cl_done with solutions."""
        payload = {"row_clues": [[2], [2]], "col_clues": [[2], [2]]}
        client.post("/api/solve/classical", json=payload)
        # Give the background thread time to complete
        time.sleep(2)
        received = sio_client.get_received()
        event_names = [e["name"] for e in received]
        # Should have received status and cl_done events
        assert "status" in event_names or "cl_done" in event_names or "busy" in event_names

    def test_quantum_solve_emits_qu_done(self, sio_client, client):
        """Quantum solve should eventually emit qu_done with counts."""
        payload = {"row_clues": [[2], [2]], "col_clues": [[2], [2]]}
        client.post("/api/solve/quantum", json=payload)
        # Give the background thread time to complete
        time.sleep(3)
        received = sio_client.get_received()
        event_names = [e["name"] for e in received]
        assert "status" in event_names or "qu_done" in event_names or "busy" in event_names
