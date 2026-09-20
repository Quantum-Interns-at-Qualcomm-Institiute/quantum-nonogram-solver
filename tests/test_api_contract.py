"""API contract tests: verify response shapes match what the frontend expects.

The static frontend at website/nonogram/ communicates with this backend via
REST endpoints and Socket.IO events. These tests verify the API contract
to catch breaking changes before they reach the frontend.
"""

from __future__ import annotations

import json
from io import BytesIO

from conftest import collect_events

from tools.config import MAX_CLUES, MAX_GRID


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

    def test_busy_returns_409(self, client, busy_solver):
        resp = client.post(
            "/api/solve/classical",
            json={"row_clues": [[1]], "col_clues": [[1]]},
        )
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "solver_busy"


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

    def test_connect_response(self, client, monkeypatch):
        # Credentials come from the environment; the request body carries none.
        monkeypatch.setenv("IBM_QUANTUM_TOKEN", "server-held-token")
        cfg = {
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
    """The result events the frontend subscribes to, and the shape it reads from them."""

    def test_classical_solve_emits_cl_done(self, sio_client, client):
        payload = {"row_clues": [[2], [2]], "col_clues": [[2], [2]]}
        client.post("/api/solve/classical", json=payload)

        events = collect_events(sio_client, "cl_done")
        assert len(events) == 1
        assert set(events[0]) == {"solutions", "rows", "cols"}
        assert events[0]["solutions"] == ["1111"]

    def test_quantum_solve_emits_qu_done(self, sio_client, client):
        payload = {"row_clues": [[2], [2]], "col_clues": [[2], [2]]}
        client.post("/api/solve/quantum", json=payload)

        events = collect_events(sio_client, "qu_done", timeout=30)
        assert len(events) == 1
        assert set(events[0]) == {"counts", "rows", "cols", "outcomes"}
        assert isinstance(events[0]["counts"], dict)
        assert events[0]["outcomes"][0]["grid"] == "1111"
