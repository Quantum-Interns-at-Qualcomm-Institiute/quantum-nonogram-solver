"""Integration tests for the nonogram Socket.IO event flow.

Tests the real-time solve pipeline against the deployed app: client submits a puzzle,
the server solves it in a worker thread, and status/cl_done/qu_done/bench_done reach
the client. Fixtures come from conftest.
"""

import pytest
from conftest import collect_events

from tools.webapp import socketio

# Connection


class TestSocketConnection:
    def test_client_connects_successfully(self, sio_client):
        assert sio_client.is_connected()

    def test_client_can_disconnect_and_reconnect(self, webapp):
        from flask_socketio import SocketIOTestClient

        first = SocketIOTestClient(webapp, socketio)
        assert first.is_connected()
        first.disconnect()
        assert not first.is_connected()

        second = SocketIOTestClient(webapp, socketio)
        assert second.is_connected()
        second.disconnect()


# Grid API + Socket.IO status events


class TestGridEvents:
    def test_post_grid_stores_the_grid(self, client):
        grid = [
            [True, True, False],
            [False, True, True],
            [True, False, True],
        ]
        resp = client.post("/api/grid", json={"rows": 3, "cols": 3, "grid": grid})
        assert resp.status_code == 200

        from tools.state import state

        assert state["rows"] == 3
        assert state["grid"] == grid

    def test_randomize_returns_valid_grid(self, client):
        resp = client.post("/api/randomize", json={"rows": 3, "cols": 3})
        assert resp.status_code == 200
        grid = resp.get_json()["grid"]
        assert len(grid) == 3
        assert all(len(row) == 3 for row in grid)


# Classical solve flow


class TestClassicalSolveFlow:
    def test_classical_solve_emits_cl_done_with_the_solution(self, client, sio_client):
        payload = {"row_clues": [[2], [2]], "col_clues": [[2], [2]]}
        assert client.post("/api/solve/classical", json=payload).status_code == 200

        events = collect_events(sio_client, "cl_done")
        assert len(events) == 1
        assert events[0] == {"solutions": ["1111"], "rows": 2, "cols": 2}

    def test_classical_solve_emits_a_finishing_status(self, client, sio_client):
        payload = {"row_clues": [[2], [2]], "col_clues": [[2], [2]]}
        client.post("/api/solve/classical", json=payload)

        collect_events(sio_client, "cl_done")
        messages = [e.get("msg", "") for e in collect_events(sio_client, "status", timeout=2)]
        assert any("solution(s) found" in m for m in messages), messages


# Quantum solve flow


class TestQuantumSolveFlow:
    def test_quantum_solve_emits_qu_done(self, client, sio_client):
        payload = {"row_clues": [[1], [1]], "col_clues": [[1], [1]]}
        assert client.post("/api/solve/quantum", json=payload).status_code == 200

        events = collect_events(sio_client, "qu_done", timeout=30)
        assert len(events) == 1
        assert events[0]["rows"] == 2
        assert events[0]["cols"] == 2
        # Both diagonals satisfy this puzzle, so one of them tops the distribution.
        counts = events[0]["counts"]
        assert max(counts, key=counts.__getitem__)[::-1] in ("1001", "0110")


# Benchmark flow


class TestBenchmarkFlow:
    def test_benchmark_emits_bench_done_with_both_timings(self, client, sio_client):
        payload = {"row_clues": [[2], [2]], "col_clues": [[2], [2]], "trials": 1}
        assert client.post("/api/benchmark", json=payload).status_code == 200

        events = collect_events(sio_client, "bench_done", timeout=60)
        assert len(events) == 1
        payload_back = events[0]
        assert payload_back["solutions"] == ["1111"]
        assert len(payload_back["cl_times"]) == 1
        assert len(payload_back["qu_times"]) == 1
        assert payload_back["report"]["classical"]["solutions_found"] == 1


# Error handling


class TestSolverErrors:
    def test_empty_clues_are_rejected(self, client):
        resp = client.post("/api/solve/classical", json={"row_clues": [], "col_clues": []})
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "invalid_clues"

    def test_oversized_puzzle_is_rejected_before_solving(self, client):
        resp = client.post(
            "/api/solve/classical",
            json={"row_clues": [[10]] * 10, "col_clues": [[10]] * 10},
        )
        assert resp.status_code == 400
        assert "cell" in resp.get_data(as_text=True).lower()

    def test_solver_error_reaches_the_client(self, client, sio_client, monkeypatch):
        """A solver that raises mid-run reports over the socket, not into a hung page."""
        from nonogram.solver import ClassicalSolver

        def _boom(self, puzzle):
            raise RuntimeError("solver exploded")

        monkeypatch.setattr(ClassicalSolver, "solve", _boom)
        client.post("/api/solve/classical", json={"row_clues": [[1]], "col_clues": [[1]]})

        events = collect_events(sio_client, "solver_error")
        assert len(events) == 1
        assert "solver exploded" in events[0]["message"]


@pytest.mark.parametrize(
    "path", ["/api/solve/classical", "/api/solve/quantum", "/api/benchmark"]
)
def test_busy_is_released_after_every_solve(client, sio_client, path):
    from tools.state import state

    body = {"row_clues": [[1]], "col_clues": [[1]], "trials": 1}
    assert client.post(path, json=body).status_code == 200
    assert collect_events(sio_client, "busy", timeout=60)
    assert state["busy"] is False
