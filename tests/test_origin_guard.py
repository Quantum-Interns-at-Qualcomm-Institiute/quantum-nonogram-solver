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


class TestRotation:
    """ORIGIN_SECRET is a set, so the gateway can move to a new value in its own
    deploy: add the new secret, switch the sender, then drop the old one."""

    @pytest.fixture()
    def rotating_client(self, monkeypatch):
        monkeypatch.setenv("ORIGIN_SECRET", "new-door, front-door")
        monkeypatch.delenv("NONOGRAM_ALLOW_INSECURE", raising=False)
        from tools.webapp import app

        app.config["TESTING"] = True
        return app.test_client()

    def test_both_secrets_admitted_mid_rotation(self, rotating_client):
        for secret in ("front-door", "new-door"):
            res = rotating_client.get("/api/config", headers={"X-Origin-Secret": secret})
            assert res.status_code == 200, secret

    def test_other_secrets_still_rejected(self, rotating_client):
        res = rotating_client.get("/api/config", headers={"X-Origin-Secret": "nope"})
        assert res.status_code == 403

    def test_the_whole_list_is_not_a_secret(self, rotating_client):
        # A sender that forwards the raw setting instead of one entry must not pass.
        res = rotating_client.get(
            "/api/config", headers={"X-Origin-Secret": "new-door, front-door"}
        )
        assert res.status_code == 403

    def test_retired_secret_rejected_once_dropped(self, monkeypatch):
        monkeypatch.setenv("ORIGIN_SECRET", "new-door")
        monkeypatch.delenv("NONOGRAM_ALLOW_INSECURE", raising=False)
        from tools.webapp import app

        app.config["TESTING"] = True
        res = app.test_client().get("/api/config", headers={"X-Origin-Secret": "front-door"})
        assert res.status_code == 403

    def test_blank_entries_do_not_open_the_door(self, monkeypatch):
        # " , " parses to an empty set, which is "unconfigured", not "allow anything".
        monkeypatch.setenv("ORIGIN_SECRET", " , ")
        monkeypatch.delenv("NONOGRAM_ALLOW_INSECURE", raising=False)
        from tools.webapp import app

        app.config["TESTING"] = True
        res = app.test_client().get("/api/config", headers={"X-Origin-Secret": ""})
        assert res.status_code == 403


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
