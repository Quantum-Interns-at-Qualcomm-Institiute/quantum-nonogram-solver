"""Live-HTTP API contract tests for the nonogram backend (Flask).

Point ``NONOGRAM_URL`` at a running server; auto-skips if unreachable. Validates
the contract surface (``/health``, ``/api`` discovery, error envelope) against
the JSON Schemas, plus the read shapes the static frontend relies on.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _contract import (  # noqa: E402
    assert_matches,
    base_url,
    http_get,
    http_post,
    skip_unless_reachable,
)

BASE = base_url("NONOGRAM_URL", "http://127.0.0.1:5055")
pytestmark = skip_unless_reachable(BASE, "NONOGRAM_URL")


class TestContractSurface:
    def test_health(self):
        status, body = http_get(BASE, "/health")
        assert status == 200
        assert_matches("health", body)
        assert body["service"] == "nonogram"

    def test_discovery(self):
        status, body = http_get(BASE, "/api")
        assert status == 200
        assert_matches("manifest", body)
        assert body["service"] == "nonogram"

    def test_error_envelope_not_found(self):
        status, body = http_get(BASE, "/__contract_missing__")
        assert status == 404
        assert_matches("error", body)
        assert body["error"]["code"] == "not_found"

    def test_error_envelope_validation(self):
        # Out-of-range dimensions → 400 with the error envelope.
        status, body = http_post(BASE, "/api/grid", {"rows": 999, "cols": 999})
        assert status == 400
        assert_matches("error", body)


class TestReadShapes:
    def test_config(self):
        status, body = http_get(BASE, "/api/config")
        assert status == 200
        assert isinstance(body["max_clues"], int)
        assert isinstance(body["max_grid"], int)

    def test_randomize(self):
        status, body = http_post(BASE, "/api/randomize", {"rows": 3, "cols": 3})
        assert status == 200
        assert isinstance(body["grid"], list)
        assert isinstance(body["grid"][0], list)


class TestSyncRoutes:
    """Synchronous equivalents return the result over plain HTTP (no Socket.IO)."""

    def test_classical_sync(self):
        status, body = http_post(
            BASE,
            "/api/solve/classical/sync",
            {"row_clues": [[1], [1]], "col_clues": [[1], [1]]},
        )
        assert status == 200
        assert isinstance(body["solutions"], list)
        assert body["rows"] == 2
        assert body["cols"] == 2

    def test_quantum_sync(self):
        status, body = http_post(
            BASE,
            "/api/solve/quantum/sync",
            {"row_clues": [[1], [1]], "col_clues": [[1], [1]]},
        )
        assert status == 200
        assert isinstance(body["counts"], dict)
        assert body["rows"] == 2
        assert body["cols"] == 2
