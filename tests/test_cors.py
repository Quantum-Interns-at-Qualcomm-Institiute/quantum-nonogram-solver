"""CORS tests for the nonogram Flask API.

These run against the deployed app object and its real allowlist. A test-local
``CORS(app)`` would allow every origin, so it would pass whatever the app config
said — including the unanchored pattern that once admitted registrable domains
beginning with "localhost".
"""

from __future__ import annotations

import pytest

from tools.webapp import _socketio_origin_ok, app

ALLOWED = [
    "https://andypeterson.dev",
    "http://localhost",
    "http://localhost:3000",
    "https://localhost:8443",
]

REFUSED = [
    "http://localhostevil.com",
    "https://andypeterson.dev.evil.example",
    "https://evil.example",
]


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    return app.test_client()


class TestAllowedOrigins:
    @pytest.mark.parametrize("origin", ALLOWED)
    def test_post_carries_the_origin_back(self, client, origin):
        res = client.post(
            "/api/grid",
            json={"rows": 3, "cols": 3, "grid": [[False] * 3] * 3},
            headers={"Origin": origin},
        )
        assert res.headers.get("Access-Control-Allow-Origin") == origin

    @pytest.mark.parametrize("origin", ALLOWED)
    def test_preflight_succeeds(self, client, origin):
        res = client.options(
            "/api/grid",
            headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
        )
        assert res.status_code == 200
        assert res.headers.get("Access-Control-Allow-Origin") == origin

    @pytest.mark.parametrize("origin", ALLOWED)
    def test_get_carries_the_origin_back(self, client, origin):
        res = client.get("/api/runs/info", headers={"Origin": origin})
        assert res.headers.get("Access-Control-Allow-Origin") == origin


class TestRefusedOrigins:
    @pytest.mark.parametrize("origin", REFUSED)
    def test_no_allow_origin_header(self, client, origin):
        res = client.post(
            "/api/grid",
            json={"rows": 3, "cols": 3, "grid": [[False] * 3] * 3},
            headers={"Origin": origin},
        )
        assert res.headers.get("Access-Control-Allow-Origin") is None

    @pytest.mark.parametrize("origin", REFUSED)
    def test_preflight_carries_no_allow_origin(self, client, origin):
        res = client.options(
            "/api/grid",
            headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
        )
        assert res.headers.get("Access-Control-Allow-Origin") is None


class TestSocketIOOriginCheck:
    """python-socketio exact-matches plain strings, so the regex entries need a callable."""

    @pytest.mark.parametrize("origin", ALLOWED)
    def test_allowed(self, origin):
        assert _socketio_origin_ok(origin) is True

    @pytest.mark.parametrize("origin", REFUSED)
    def test_refused(self, origin):
        assert _socketio_origin_ok(origin) is False
