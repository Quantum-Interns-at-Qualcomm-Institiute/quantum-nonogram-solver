"""Live-HTTP API contract tests for the nonogram backend (Flask).

Point ``NONOGRAM_URL`` at a running server and ``NONOGRAM_ORIGIN_SECRET`` at its
``ORIGIN_SECRET``; auto-skips if unreachable. Validates the contract surface
(``/health``, ``/api`` discovery, error envelope) against the JSON Schemas, the
front-door guard, and the read shapes the static frontend relies on.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from _contract import (
    assert_matches,
    base_url,
    http_get,
    http_post,
    skip_unless_reachable,
)

BASE = base_url("NONOGRAM_URL", "http://127.0.0.1:5055")
pytestmark = skip_unless_reachable(BASE, "NONOGRAM_URL")

# The server's front-door guard wants the gateway's secret on every route but /health.
SECRET = os.environ.get("NONOGRAM_ORIGIN_SECRET", "")
GATEWAY = {"X-Origin-Secret": SECRET} if SECRET else {}


def get(path: str):
    return http_get(BASE, path, headers=GATEWAY)


def post(path: str, body=None):
    return http_post(BASE, path, body, headers=GATEWAY)


class TestContractSurface:
    def test_health(self):
        status, body = http_get(BASE, "/health")
        assert status == 200
        assert_matches("health", body)
        assert body["service"] == "nonogram"

    def test_discovery(self):
        status, body = get("/api")
        assert status == 200
        assert_matches("manifest", body)
        assert body["service"] == "nonogram"

    def test_error_envelope_not_found(self):
        status, body = get("/__contract_missing__")
        assert status == 404
        assert_matches("error", body)
        assert body["error"]["code"] == "not_found"

    def test_error_envelope_validation(self):
        # Out-of-range dimensions → 400 with the error envelope.
        status, body = post("/api/grid", {"rows": 999, "cols": 999})
        assert status == 400
        assert_matches("error", body)


@pytest.mark.skipif(not SECRET, reason="set NONOGRAM_ORIGIN_SECRET to the server's ORIGIN_SECRET")
class TestOriginGuard:
    """The guard is on, as in production: a caller without the secret is refused."""

    def test_refuses_without_secret(self):
        status, body = http_get(BASE, "/api")
        assert status == 403
        assert_matches("error", body)
        assert body["error"]["code"] == "forbidden"

    def test_refuses_wrong_secret(self):
        status, body = http_post(
            BASE, "/api/randomize", {"rows": 3, "cols": 3}, headers={"X-Origin-Secret": "wrong"}
        )
        assert status == 403
        assert_matches("error", body)


class TestReadShapes:
    def test_config(self):
        status, body = get("/api/config")
        assert status == 200
        assert isinstance(body["max_clues"], int)
        assert isinstance(body["max_grid"], int)

    def test_randomize(self):
        status, body = post("/api/randomize", {"rows": 3, "cols": 3})
        assert status == 200
        assert isinstance(body["grid"], list)
        assert isinstance(body["grid"][0], list)


class TestSyncRoutes:
    """Synchronous equivalents return the result over plain HTTP (no Socket.IO)."""

    def test_classical_sync(self):
        status, body = post(
            "/api/solve/classical/sync",
            {"row_clues": [[1], [1]], "col_clues": [[1], [1]]},
        )
        assert status == 200
        assert isinstance(body["solutions"], list)
        assert body["rows"] == 2
        assert body["cols"] == 2

    def test_quantum_sync(self):
        status, body = post(
            "/api/solve/quantum/sync",
            {"row_clues": [[1], [1]], "col_clues": [[1], [1]]},
        )
        assert status == 200
        assert isinstance(body["counts"], dict)
        assert body["rows"] == 2
        assert body["cols"] == 2
