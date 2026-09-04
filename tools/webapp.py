"""
Flask + Socket.IO web interface for interactive nonogram solving.

**Features:**

  - Real-time grid editing with mouse drawing
  - Classical and quantum solver backends
  - Benchmark comparison with visualization
  - Puzzle save/load via JSON
  - IBM quantum hardware integration (with API token)
  - Live metrics and circuit analysis

**Usage:**

  Run from the project root::

    python tools/webapp.py

  The browser opens automatically at the assigned port.

**Architecture:**

  - **Frontend**: HTML5 canvas grid, responsive UI, Socket.IO client
  - **Backend**: Flask server, threaded solver workers, real-time metric updates
  - **State**: Single-user local state managed with thread safety
  - **Modules**:
    - ``tools/state.py``   — server state and Socket.IO helpers
    - ``tools/chart.py``   — chart rendering and report serialization
    - ``tools/routes/``    — route blueprints (grid, solver, puzzle, hardware, runs)

**Ports & Configuration:**

  - HTTP: dynamically assigned (or set via PORT env var)
  - WebSocket: Socket.IO over HTTP (CORS restricted to localhost by default)
  - Puzzle storage: ./puzzles/ directory (auto-created)
  - Max grid size: 6x6 (limited by data.py lookup table)
  - Max clues per line: 3 blocks
"""

from __future__ import annotations

import hmac
import os
import re
import sys
import threading
import webbrowser
from pathlib import Path

# ── path setup ────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))

from flask import Flask, jsonify, request  # noqa: E402
from flask_cors import CORS  # noqa: E402
from flask_socketio import SocketIO  # noqa: E402

from tools import state as app_state  # noqa: E402
from tools.config import MAX_CLUES, MAX_CONTENT_LENGTH, MAX_GRID  # noqa: E402
from tools.errors import register_error_handlers  # noqa: E402
from tools.routes import ALL_BLUEPRINTS  # noqa: E402

# ── Flask setup ──────────────────────────────────────────────────────────────
app = Flask(__name__)
# Cap request bodies — clues are a few hundred bytes of JSON; this rejects
# oversized payloads with a 413 before Flask parses them.
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.secret_key = os.environ.get("NONOGRAM_SECRET_KEY", os.urandom(32).hex())

# NOTE the anchored regex: flask-cors treats any entry containing "*" as a
# start-anchored-only regex, so the old "http://localhost:*" allowed the
# registrable origin http://localhostevil.com. The ^...$ form does not.
_CORS_ORIGINS = os.environ.get(
    "NONOGRAM_CORS_ORIGINS",
    r"^https?://localhost(:\d+)?$,https://andypeterson.dev",
).split(",")
CORS(app, origins=_CORS_ORIGINS)


def _socketio_origin_ok(origin: str) -> bool:
    """Match Socket.IO origins with the same anchored semantics as flask-cors.

    python-socketio exact-matches plain strings (so the old wildcard entry
    silently allowed nothing); a callable applies the regex entries properly.
    """
    for entry in _CORS_ORIGINS:
        if any(ch in entry for ch in "^$*?[]"):
            if re.fullmatch(entry.lstrip("^").rstrip("$"), origin):
                return True
        elif origin == entry:
            return True
    return False


socketio = SocketIO(
    app,
    async_mode="threading",
    cors_allowed_origins=_socketio_origin_ok,
)


# ── Front-door guard (fail closed) ───────────────────────────────────────────
# Every route except /health requires the X-Origin-Secret the gateway injects
# (andypeterson-gateway sets LIVE_ORIGIN_SECRET for this backend). Unlike the
# classifier service's opt-in guard, this one FAILS CLOSED: with ORIGIN_SECRET
# unset the API refuses to serve, unless NONOGRAM_ALLOW_INSECURE=1 explicitly
# opts into unguarded local dev. Without this, the hardware routes let any
# caller spend real IBM Quantum credits on the owner's account.
@app.before_request
def _origin_guard():
    if request.path == "/health":
        return None
    want = os.environ.get("ORIGIN_SECRET")
    if not want:
        if os.environ.get("NONOGRAM_ALLOW_INSECURE") == "1":
            return None
        return jsonify(
            {
                "error": {
                    "code": "origin_guard_unconfigured",
                    "message": "set ORIGIN_SECRET (or NONOGRAM_ALLOW_INSECURE=1 for local dev)",
                }
            }
        ), 403
    got = request.headers.get("X-Origin-Secret") or ""
    # compare_digest: a plain != on a secret leaks timing.
    if not hmac.compare_digest(got, want):
        return jsonify({"error": {"code": "forbidden", "message": "origin"}}), 403
    return None

# Bind SocketIO to state module so helpers can emit
app_state.init(socketio)

# Register route blueprints
for bp in ALL_BLUEPRINTS:
    app.register_blueprint(bp)

# Uniform JSON error envelope for framework-raised errors (404/405/500, ...).
register_error_handlers(app)


# ── Config API (frontend lives in the website repo) ──────────────────────────


@app.route("/api/config")
def api_config():
    """Return solver configuration for the static frontend."""
    from flask import jsonify

    return jsonify({"max_clues": MAX_CLUES, "max_grid": MAX_GRID})


# ── Entry point ──────────────────────────────────────────────────────────────


def _get_ssl_context():
    """Return (cert, key) paths if dev certs exist, else None."""
    for d in [
        Path(os.environ.get("DEV_CERT_DIR", "")),
        Path(__file__).resolve().parents[2] / ".certs",
    ]:
        cert, key = d / "cert.pem", d / "key.pem"
        if cert.is_file() and key.is_file():
            return (str(cert), str(key))
    return None


def _find_port(host="127.0.0.1"):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


if __name__ == "__main__":
    HOST = os.environ.get("NONOGRAM_HOST", "127.0.0.1")
    PORT = int(os.environ.get("PORT") or 0) or _find_port(HOST)
    ssl_ctx = _get_ssl_context()
    scheme = "https" if ssl_ctx else "http"
    threading.Timer(1.2, lambda: webbrowser.open(f"{scheme}://localhost:{PORT}")).start()
    print(f"Starting Nonogram web app \u2192 {scheme}://localhost:{PORT}")  # noqa: T201 \u2014 startup banner
    socketio.run(
        app, host=HOST, port=PORT, debug=False, ssl_context=ssl_ctx,
        allow_unsafe_werkzeug=True,
    )
