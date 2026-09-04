"""Pass C resource/robustness regressions (2026-09 security round).

Covers: malformed-body 400s (not 500s) on solve and puzzle routes, the
run-artifact cap, per-request hardware config shape, and sanitized errors.
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
        rc, cc, rows, cols = _parse_clues({"row_clues": [[1], [2]], "col_clues": [[1], [1], [1]]})
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
