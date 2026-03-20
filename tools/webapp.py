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

  The browser opens automatically at http://localhost:5055.

**Architecture:**

  - **Frontend**: HTML5 canvas grid, responsive UI, Socket.IO client
  - **Backend**: Flask server, threaded solver workers, real-time metric updates
  - **State**: Single-user local state managed with thread safety
  - **Modules**:
    - ``tools/state.py``   — server state and Socket.IO helpers
    - ``tools/chart.py``   — chart rendering and report serialization
    - ``tools/routes/``    — route blueprints (grid, solver, puzzle, hardware, runs)

**Ports & Configuration:**

  - HTTP: Port 5055 (configured to avoid AirPlay/preview server conflicts)
  - WebSocket: Socket.IO over HTTP (cors_allowed_origins="*" for dev)
  - Puzzle storage: ./puzzles/ directory (auto-created)
  - Max grid size: 6x6 (limited by data.py lookup table)
  - Max clues per line: 3 blocks
"""

from __future__ import annotations

import os
import sys
import threading
import webbrowser
from pathlib import Path

# ── path setup ────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))

from flask import Flask  # noqa: E402
from flask_cors import CORS  # noqa: E402
from flask_socketio import SocketIO  # noqa: E402

from tools import state as app_state  # noqa: E402
from tools.config import MAX_CLUES, MAX_GRID  # noqa: E402
from tools.routes import ALL_BLUEPRINTS  # noqa: E402

# ── Flask setup ──────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"] = "nonogram-dev-key"
CORS(app)
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

# Bind SocketIO to state module so helpers can emit
app_state.init(socketio)

# Register route blueprints
for bp in ALL_BLUEPRINTS:
    app.register_blueprint(bp)


# ── Config API (frontend lives in the website repo) ──────────────────────────


@app.route("/api/config")
def api_config():
    """Return solver configuration for the static frontend."""
    from flask import jsonify

    return jsonify({"max_clues": MAX_CLUES, "max_grid": MAX_GRID})


# ── Entry point ──────────────────────────────────────────────────────────────


def _get_ssl_context():
    """Return (cert, key) paths if dev certs exist, else None."""
    from pathlib import Path

    for d in [
        Path(os.environ.get("DEV_CERT_DIR", "")),
        Path(__file__).resolve().parents[2] / ".certs",
    ]:
        cert, key = d / "cert.pem", d / "key.pem"
        if cert.is_file() and key.is_file():
            return (str(cert), str(key))
    return None


if __name__ == "__main__":
    PORT = 5055
    ssl_ctx = _get_ssl_context()
    scheme = "https" if ssl_ctx else "http"
    threading.Timer(1.2, lambda: webbrowser.open(f"{scheme}://localhost:{PORT}")).start()
    print(f"Starting Nonogram web app \u2192 {scheme}://localhost:{PORT}")
    HOST = os.environ.get("NONOGRAM_HOST", "0.0.0.0")
    socketio.run(
        app, host=HOST, port=PORT, debug=False, allow_unsafe_werkzeug=True, ssl_context=ssl_ctx
    )
