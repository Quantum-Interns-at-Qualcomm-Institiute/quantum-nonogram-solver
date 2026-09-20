"""Resource and robustness checks: malformed bodies return 400 rather than 500,
the run-artifact cap holds, hardware config shape is per-request, errors are sanitized.
"""

from __future__ import annotations

import json

import pytest

from tools.routes.solver import _parse_clues, _sanitize_error, _save_run


class TestParseCluesShape:
    """Malformed bodies raise ValueError (routes 400) instead of KeyError (500)."""

    @pytest.mark.parametrize(
        "body",
        [
            {},
            {"row_clues": [[1]]},
            {"row_clues": None, "col_clues": [[1]]},
            {"row_clues": 42, "col_clues": [[1]]},
            {"row_clues": [1, 2], "col_clues": [[1]]},  # entries not iterable
        ],
    )
    def test_bad_shapes_raise_value_error(self, body):
        with pytest.raises(ValueError):
            _parse_clues(body)

    def test_good_shape_parses(self):
        rc, _cc, rows, cols = _parse_clues({"row_clues": [[1], [2]], "col_clues": [[1], [1], [1]]})
        assert (rows, cols) == (2, 3)
        assert rc == [(1,), (2,)]


class TestSolveRouteBadBody:
    """The solve routes 400 on malformed bodies and stay un-wedged."""

    @pytest.fixture
    def client(self):
        from tools.webapp import app

        return app.test_client()

    @pytest.mark.parametrize(
        "path", ["/api/solve/classical", "/api/solve/quantum", "/api/benchmark"]
    )
    def test_missing_clues_is_400(self, client, path):
        resp = client.post(path, json={"nonsense": True})
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "invalid_clues"

    def test_puzzle_save_missing_clues_is_400(self, client):
        resp = client.post("/api/puzzle/save", json={"name": "x"})
        assert resp.status_code == 400

    def test_puzzle_load_garbage_is_400(self, client):
        resp = client.post(
            "/api/puzzle/load",
            data={"file": (__import__("io").BytesIO(b"not json"), "p.non.json")},
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "invalid_puzzle"

    @pytest.mark.parametrize(
        "document",
        [
            [1, 2],
            {"row_clues": 5, "col_clues": [[1]]},
            {"row_clues": [[-5]], "col_clues": [[1]]},
            {"row_clues": [[1]] * 40, "col_clues": [[1]] * 40},
        ],
        ids=["list", "scalar", "negative", "oversized"],
    )
    def test_upload_is_validated_before_it_reaches_state(self, client, document):
        """An upload past the size cap used to set rows/cols beyond MAX_GRID."""
        import io as _io

        from tools.state import state

        buf = _io.BytesIO(json.dumps(document).encode())
        resp = client.post(
            "/api/puzzle/load",
            data={"file": (buf, "p.non.json")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "invalid_puzzle"
        assert state["rows"] <= 10
        assert state["cols"] <= 10


class TestMalformedFieldsAre400:
    """A field the caller got wrong is a 400, never a 500.

    Every route below used to coerce or index a request field before checking its
    type, so `{"rows": "abc"}` surfaced as an internal error.
    """

    @pytest.fixture
    def client(self):
        from tools.webapp import app

        return app.test_client()

    @pytest.mark.parametrize(
        "path,body,code",
        [
            ("/api/grid", {"rows": "abc", "cols": 3}, "invalid_dimensions"),
            ("/api/grid", {"rows": None, "cols": None}, "invalid_dimensions"),
            ("/api/grid", {"rows": [1], "cols": 2}, "invalid_dimensions"),
            ("/api/grid", [1, 2], "invalid_dimensions"),
            ("/api/randomize", {"rows": "x", "cols": 2}, "invalid_dimensions"),
        ],
    )
    def test_grid_routes(self, client, path, body, code):
        resp = client.post(path, json=body)
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == code

    def test_hardware_shots(self, client, monkeypatch):
        monkeypatch.setenv("IBM_QUANTUM_TOKEN", "server-held-token")
        resp = client.post("/api/hw/config", json={"backend_name": "b", "shots": "lots"})
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "invalid_shots"

    def test_puzzle_save_non_string_name(self, client):
        resp = client.post(
            "/api/puzzle/save", json={"row_clues": [[1]], "col_clues": [[1]], "name": 5}
        )
        assert resp.status_code == 200

    @pytest.mark.parametrize(
        "path",
        ["/api/solve/classical/sync", "/api/solve/quantum/sync", "/api/benchmark/sync"],
    )
    def test_sync_routes_match_the_async_ones(self, client, path):
        # The async routes 400 on this body; the sync ones used to 500 on it.
        resp = client.post(path, json={"nonsense": True})
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "invalid_clues"


class TestBadTrialsDoesNotWedgeTheSolver:
    """A bad trial count is parsed before the busy lock, so it cannot strand it.

    Parsed after the lock, one such request left `busy` True for the life of the
    process and every later solve answered 409.
    """

    @pytest.fixture
    def client(self):
        from tools.webapp import app

        return app.test_client()

    @pytest.mark.parametrize("trials", ["x", None, [1]])
    def test_bad_trials_is_400_and_leaves_the_lock_free(self, client, trials):
        from tools.state import state

        body = {"row_clues": [[1], [1]], "col_clues": [[1], [1]], "trials": trials}
        resp = client.post("/api/benchmark", json=body)
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "invalid_trials"
        assert state["busy"] is False

        # The solver is still reachable.
        assert client.post("/api/benchmark/sync", json={**body, "trials": 1}).status_code == 200
        assert state["busy"] is False


class TestRunArtifactCap:
    """_save_run prunes oldest files so the store stays bounded."""

    def test_cap_prunes_oldest(self, tmp_path, monkeypatch):
        import tools.routes.solver as solver_mod

        monkeypatch.setattr(solver_mod, "RUNS_DIR", tmp_path)
        monkeypatch.setenv("NONOGRAM_MAX_RUNS", "3")
        for i in range(6):
            _save_run({"run_id": f"{i:03d}", "data": i})
        remaining = sorted(p.name for p in tmp_path.glob("run_*.json"))
        assert len(remaining) == 3
        assert remaining[-1] == "run_005.json"
        # Newest survives with intact content.
        assert json.loads((tmp_path / "run_005.json").read_text())["data"] == 5


class TestRequestHwConfig:
    """Per-request hardware config never carries caller credentials, caps shots."""

    def test_no_token_means_no_hw(self, monkeypatch):
        from tools.routes.solver import _request_hw_cfg

        monkeypatch.delenv("IBM_QUANTUM_TOKEN", raising=False)
        assert _request_hw_cfg({"hw": {"backend_name": "ibm_x"}}) is None

    def test_token_from_server_shots_capped(self, monkeypatch):
        from tools.routes.hardware import MAX_SHOTS
        from tools.routes.solver import _request_hw_cfg

        monkeypatch.setenv("IBM_QUANTUM_TOKEN", "server-held-token")
        cfg = _request_hw_cfg(
            {"hw": {"backend_name": "ibm_x", "shots": 10**9, "token": "attacker-token"}}
        )
        assert cfg["token"] == "server-held-token"  # caller's token ignored
        assert cfg["shots"] == MAX_SHOTS


class TestSanitizedErrors:
    """Errors that could carry credentials are redacted and truncated."""

    def test_long_tokens_redacted(self):
        secret = "a" * 64
        assert secret not in _sanitize_error(Exception(f"auth failed for {secret}"))

    def test_truncated(self):
        assert len(_sanitize_error(Exception("x" * 10_000))) <= 500


class TestMaxCluesIsEnforced:
    """/api/config advertises a block limit per clue; the solve routes hold it."""

    @pytest.fixture
    def client(self):
        from tools.webapp import app

        return app.test_client()

    def test_config_reports_the_limit(self, client):
        from tools.config import MAX_CLUES

        assert client.get("/api/config").get_json()["max_clues"] == MAX_CLUES

    @pytest.mark.parametrize(
        "path", ["/api/solve/classical", "/api/solve/quantum", "/api/benchmark"]
    )
    def test_too_many_blocks_is_400(self, client, path):
        from tools.config import MAX_CLUES

        clue = [1] * (MAX_CLUES + 1)
        body = {"row_clues": [clue], "col_clues": [[1]] * (2 * len(clue) - 1)}
        resp = client.post(path, json=body)
        assert resp.status_code == 400
        assert "block" in resp.get_json()["error"]["message"]

    def test_the_limit_itself_is_accepted(self, client):
        from tools.config import MAX_CLUES

        clue = [1] * MAX_CLUES
        body = {"row_clues": [clue], "col_clues": [[1]] * (2 * len(clue) - 1)}
        assert client.post("/api/solve/classical/sync", json=body).status_code == 200
