"""Front-door guard: every route but /health requires the gateway's secret.

The hardware routes spend real IBM Quantum credits on the owner's account,
so the guard FAILS CLOSED — with ORIGIN_SECRET unset the API refuses to
serve unless NONOGRAM_ALLOW_INSECURE=1 explicitly opts into local dev.
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def webapp_client(monkeypatch):
    monkeypatch.setenv("ORIGIN_SECRET", "front-door")
    monkeypatch.delenv("NONOGRAM_ALLOW_INSECURE", raising=False)
    from tools.webapp import app

    app.config["TESTING"] = True
    return app.test_client()


class TestOriginGuard:
    def test_health_stays_public(self, webapp_client):
        assert webapp_client.get("/health").status_code == 200

    def test_missing_secret_rejected(self, webapp_client):
        res = webapp_client.get("/api/config")
        assert res.status_code == 403

    def test_wrong_secret_rejected(self, webapp_client):
        res = webapp_client.get("/api/config", headers={"X-Origin-Secret": "nope"})
        assert res.status_code == 403

    def test_hardware_route_guarded(self, webapp_client):
        res = webapp_client.post("/api/hw/config", json={"enabled": True})
        assert res.status_code == 403

    def test_correct_secret_admitted(self, webapp_client):
        res = webapp_client.get("/api/config", headers={"X-Origin-Secret": "front-door"})
        assert res.status_code == 200


class TestGuardFailsClosedWhenUnconfigured:
    def test_unset_secret_refuses_service(self, monkeypatch):
        monkeypatch.delenv("ORIGIN_SECRET", raising=False)
        monkeypatch.delenv("NONOGRAM_ALLOW_INSECURE", raising=False)
        from tools.webapp import app

        app.config["TESTING"] = True
        res = app.test_client().get("/api/config")
        assert res.status_code == 403
        assert res.get_json()["error"]["code"] == "origin_guard_unconfigured"

    def test_explicit_local_optout(self, monkeypatch):
        monkeypatch.delenv("ORIGIN_SECRET", raising=False)
        monkeypatch.setenv("NONOGRAM_ALLOW_INSECURE", "1")
        from tools.webapp import app

        app.config["TESTING"] = True
        assert app.test_client().get("/api/config").status_code == 200
