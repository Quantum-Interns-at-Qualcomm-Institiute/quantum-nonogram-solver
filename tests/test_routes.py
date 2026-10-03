"""
test_routes.py
~~~~~~~~~~~~~~
Integration tests for the Flask route blueprints.

Uses Flask's test client — no real server, no Socket.IO transport needed.
All solver routes are tested with mocked solvers to avoid slow computation.
"""

from __future__ import annotations

import json

import pytest

# Fixtures come from conftest: `client` is the deployed app's test client.


# Grid routes


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


# Puzzle routes


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


# Solver routes


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

    def test_solver_busy_rejection(self, client, busy_solver):
        """Solver endpoints reject requests when busy."""
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
        # An oversized-grid 400 releases the busy lock, so a valid solve still runs.
        from tools.state import state, state_lock

        assert client.post("/api/solve/classical", json=self.OVERSIZED).status_code == 400
        ok = client.post(
            "/api/solve/classical", json={"row_clues": [[2], [2]], "col_clues": [[2], [2]]}
        )
        assert ok.status_code == 200

        # Clean up the background solve's busy flag.
        with state_lock:
            state["busy"] = False

    def test_benchmark_clamps_excessive_trials(self, client):
        # Each trial is a full classical+quantum solve, so a huge trials count is
        # clamped to MAX_TRIALS (not run verbatim) — one request can't wedge the
        # single-worker solver for minutes on end.
        from tools.config import MAX_TRIALS

        resp = client.post(
            "/api/benchmark/sync",
            json={"row_clues": [[1], [1]], "col_clues": [[1], [1]], "trials": MAX_TRIALS + 50},
        )
        assert resp.status_code == 200
        assert len(resp.get_json()["cl_times"]) == MAX_TRIALS


# Hardware routes


class TestHardwareRoutes:
    def test_there_is_no_hardware_toggle(self, client):
        """Hardware is per solve. A server-wide toggle would put one caller's choice
        on every other caller's run until someone turned it off."""
        assert client.post("/api/hw/config", json={"backend_name": "ibm_test"}).status_code == 404

    def test_server_state_holds_no_hardware_config(self):
        from tools.state import default_state

        assert "hw_config" not in default_state()

    def test_hw_backends_missing_runtime(self, client, monkeypatch):
        """With server credentials present, a bad token surfaces as 400 from the runtime."""
        monkeypatch.setenv("IBM_QUANTUM_TOKEN", "bad-token")
        resp = client.post("/api/hw/backends", json={"channel": "ibm_quantum_platform"})
        # Should return 400 with an error message (auth will fail)
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_hardware_routes_are_503_without_server_credentials(self, client, monkeypatch):
        """No server-held token ⇒ hardware is unavailable. A caller cannot supply one:
        that would let a stranger spend the owner's quantum credits (or make this
        server relay their token)."""
        monkeypatch.delenv("IBM_QUANTUM_TOKEN", raising=False)
        attacker = {"token": "attacker-supplied", "backend_name": "ibm_test"}
        assert client.post("/api/hw/backends", json=attacker).status_code == 503


# Runs routes


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

    def test_runs_delete_rejected_when_busy(self, client, busy_solver):
        resp = client.post("/api/runs/delete")
        assert resp.status_code == 409


# Hardware is reached per request, and only for a caller the front door vouched for


class TestHardwareIsPerRequest:
    """A solve reaches the QPU only when it asks AND the front door says it may."""

    PUZZLE = {"row_clues": [[2], [2]], "col_clues": [[2], [2]]}

    @pytest.fixture()
    def spy(self, monkeypatch):
        """Record every hardware submission instead of calling IBM."""
        calls = []

        def fake(puzzle, **kwargs):
            calls.append(kwargs)
            return {"1111": 1024}, kwargs.get("backend_name") or "ibm_fake"

        import nonogram.quantum

        monkeypatch.setattr(nonogram.quantum, "quantum_solve_hardware", fake)
        monkeypatch.setenv("IBM_QUANTUM_TOKEN", "server-held-token")
        return calls

    def _benchmark(self, client, spy, headers):
        body = {**self.PUZZLE, "trials": 1, "hw": {"backend_name": "ibm_test", "shots": 8}}
        resp = client.post("/api/benchmark/sync", json=body, headers=headers)
        assert resp.status_code == 200, resp.get_json()
        return resp.get_json()

    def test_an_hw_block_alone_stays_on_the_simulator(self, client, spy):
        payload = self._benchmark(client, spy, headers={})
        assert spy == []
        assert payload["hardware"] is None

    def test_the_entitlement_header_reaches_the_qpu(self, client, spy):
        from tools.routes.solver import HW_ALLOWED_HEADER

        payload = self._benchmark(client, spy, headers={HW_ALLOWED_HEADER: "1"})
        assert len(spy) == 1
        assert spy[0]["token"] == "server-held-token"  # never a caller's
        assert spy[0]["shots"] == 8
        assert payload["hardware"] == "ibm_test"

    def test_shots_alone_reaches_the_qpu_on_the_least_busy_device(self, client, spy):
        """The browser names no backend, so asking for hardware must not require one."""
        from tools.routes.solver import HW_ALLOWED_HEADER

        body = {**self.PUZZLE, "trials": 1, "hw": {"shots": 8}}
        resp = client.post("/api/benchmark/sync", json=body, headers={HW_ALLOWED_HEADER: "1"})
        assert resp.status_code == 200, resp.get_json()
        assert len(spy) == 1
        assert spy[0]["backend_name"] is None  # IBM picks the least busy one
        assert spy[0]["shots"] == 8

    def test_no_hw_block_stays_on_the_simulator_even_when_entitled(self, client, spy):
        """Entitlement is not a request: without an "hw" block nothing is submitted."""
        from tools.routes.solver import HW_ALLOWED_HEADER

        body = {**self.PUZZLE, "trials": 1}
        resp = client.post("/api/benchmark/sync", json=body, headers={HW_ALLOWED_HEADER: "1"})
        assert resp.status_code == 200, resp.get_json()
        assert spy == []

    def test_one_entitled_run_does_not_entitle_the_next(self, client, spy):
        from tools.routes.solver import HW_ALLOWED_HEADER

        self._benchmark(client, spy, headers={HW_ALLOWED_HEADER: "1"})
        self._benchmark(client, spy, headers={})
        assert len(spy) == 1  # the second run found no toggle left behind

    def test_a_grid_too_deep_for_hardware_is_refused_before_submission(self, client, spy):
        """Past MAX_HW_CELLS a job can only return noise, and still costs allowance."""
        from tools.config import MAX_HW_CELLS
        from tools.routes.solver import HW_ALLOWED_HEADER

        side = 3  # 3x3 = 9 cells
        assert side * side > MAX_HW_CELLS
        body = {
            "row_clues": [[3]] * side,
            "col_clues": [[3]] * side,
            "trials": 1,
            "hw": {"backend_name": "ibm_test", "shots": 8},
        }
        resp = client.post("/api/benchmark/sync", json=body, headers={HW_ALLOWED_HEADER: "1"})
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "hardware_grid_too_large"
        assert spy == []  # nothing reached IBM

    def test_the_largest_allowed_grid_still_reaches_the_qpu(self, client, spy):
        """3x2 is six cells: the deepest circuit still worth measuring."""
        from tools.routes.solver import HW_ALLOWED_HEADER

        body = {
            "row_clues": [[2], [2], [2]],
            "col_clues": [[3], [3]],
            "trials": 1,
            "hw": {"backend_name": "ibm_test", "shots": 8},
        }
        resp = client.post("/api/benchmark/sync", json=body, headers={HW_ALLOWED_HEADER: "1"})
        assert resp.status_code == 200, resp.get_json()
        assert len(spy) == 1

    def test_an_oversized_grid_without_hardware_is_untouched(self, client, spy):
        """The ceiling is a hardware rule; the simulator keeps its own limits."""
        body = {"row_clues": [[3]] * 3, "col_clues": [[3]] * 3, "trials": 1}
        assert client.post("/api/benchmark/sync", json=body).status_code == 200
        assert spy == []


# Submit and collect are separate calls, so an IBM queue holds nobody


class TestHardwareJobLifecycle:
    """POST /api/hw/jobs hands back an id; GET /api/hw/jobs/<id> answers later."""

    PUZZLE = {"row_clues": [[2], [2]], "col_clues": [[2], [2]]}

    @pytest.fixture()
    def ibm(self, monkeypatch):
        """Stand in for IBM: record submissions, answer collections from a script."""
        state = {"submitted": [], "status": "QUEUED", "counts": {"1111": 8}}

        def fake_submit(puzzle, **kwargs):
            state["submitted"].append(kwargs)
            return {
                "job_id": "job-abc",
                "backend": kwargs.get("backend_name") or "ibm_fake",
                "shots": kwargs.get("shots"),
                "iterations": 1,
                "transpiled_depth": 139,
                "creg_names": ["meas"],
            }

        def fake_collect(job_id, token, channel="ibm_quantum_platform"):
            done = state["status"] == "DONE"
            return {
                "status": state["status"],
                "done": done,
                "counts": state["counts"] if done else None,
                "backend": "ibm_fake",
            }

        import nonogram.quantum

        monkeypatch.setattr(nonogram.quantum, "submit_hardware_job", fake_submit)
        monkeypatch.setattr(nonogram.quantum, "collect_hardware_job", fake_collect)
        monkeypatch.setenv("IBM_QUANTUM_TOKEN", "server-held-token")
        return state

    def _submit(self, client, entitled=True):
        from tools.routes.solver import HW_ALLOWED_HEADER

        headers = {HW_ALLOWED_HEADER: "1"} if entitled else {}
        body = {**self.PUZZLE, "hw": {"backend_name": "ibm_test", "shots": 8}}
        return client.post("/api/hw/jobs", json=body, headers=headers)

    def test_submitting_returns_an_id_without_waiting(self, client, ibm):
        resp = self._submit(client)
        assert resp.status_code == 202
        payload = resp.get_json()
        assert payload["job_id"] == "job-abc"
        assert payload["transpiled_depth"] == 139
        assert len(ibm["submitted"]) == 1
        assert ibm["submitted"][0]["token"] == "server-held-token"

    def test_the_solver_is_free_again_once_the_job_is_queued(self, client, ibm):
        from tools.state import state

        self._submit(client)
        assert state["busy"] is False  # the IBM queue holds nothing here

    def test_an_unentitled_submission_reaches_no_hardware(self, client, ibm):
        resp = self._submit(client, entitled=False)
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "hardware_not_allowed"
        assert ibm["submitted"] == []

    def test_a_grid_too_deep_is_refused_before_submission(self, client, ibm):
        from tools.routes.solver import HW_ALLOWED_HEADER

        body = {
            "row_clues": [[3]] * 3,
            "col_clues": [[3]] * 3,
            "hw": {"backend_name": "ibm_test", "shots": 8},
        }
        resp = client.post("/api/hw/jobs", json=body, headers={HW_ALLOWED_HEADER: "1"})
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "hardware_grid_too_large"
        assert ibm["submitted"] == []

    def test_collecting_a_queued_job_reports_that_it_is_waiting(self, client, ibm):
        resp = client.get("/api/hw/jobs/job-abc")
        assert resp.status_code == 200
        assert resp.get_json() == {
            "status": "QUEUED",
            "done": False,
            "counts": None,
            "backend": "ibm_fake",
        }

    def test_collecting_a_finished_job_returns_its_counts(self, client, ibm):
        ibm["status"] = "DONE"
        payload = client.get("/api/hw/jobs/job-abc").get_json()
        assert payload["done"] is True
        assert payload["counts"] == {"1111": 8}

    def test_collecting_needs_only_the_id(self, client, ibm):
        """Nothing is carried between the two calls, so a reload can still collect."""
        ibm["status"] = "DONE"
        assert client.get("/api/hw/jobs/job-abc").get_json()["counts"] == {"1111": 8}
        assert ibm["submitted"] == []  # collected without ever submitting in this test
