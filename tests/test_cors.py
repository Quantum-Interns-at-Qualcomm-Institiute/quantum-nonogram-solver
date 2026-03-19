"""CORS header tests for the nonogram Flask API."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from tools import state as app_state
from tools.routes import ALL_BLUEPRINTS


@pytest.fixture()
def client():
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parent.parent / "tools" / "templates"),
        static_folder=str(Path(__file__).resolve().parent.parent / "tools" / "static"),
    )
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test"
    CORS(app)
    sio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")
    app_state.init(sio)
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)
    app_state.state.update({"rows": 3, "cols": 3, "grid": [[False]*3 for _ in range(3)], "hw_config": None, "busy": False, "puzzle_name": "test"})
    yield app.test_client()


class TestCORS:
    def test_cors_headers_on_post(self, client):
        res = client.post("/api/grid", json={"rows": 3, "cols": 3, "grid": [[False]*3]*3},
                          headers={"Origin": "https://andypeterson2.github.io"})
        assert res.headers.get("Access-Control-Allow-Origin") is not None

    def test_options_preflight(self, client):
        res = client.options("/api/grid",
                             headers={"Origin": "https://andypeterson2.github.io",
                                      "Access-Control-Request-Method": "POST"})
        assert res.status_code == 200
        assert "Access-Control-Allow-Origin" in res.headers

    def test_cors_on_get(self, client):
        res = client.get("/api/runs/info",
                         headers={"Origin": "https://andypeterson2.github.io"})
        assert res.headers.get("Access-Control-Allow-Origin") is not None
