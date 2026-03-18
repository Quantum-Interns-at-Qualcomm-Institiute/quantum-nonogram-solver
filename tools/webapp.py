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

from flask import Flask, render_template
from flask_socketio import SocketIO

from tools import state as app_state
from tools.config import MAX_CLUES, MAX_GRID
from tools.routes import ALL_BLUEPRINTS

# ── Flask setup ──────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = "nonogram-dev-key"
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

# Bind SocketIO to state module so helpers can emit
app_state.init(socketio)

# Register route blueprints
for bp in ALL_BLUEPRINTS:
    app.register_blueprint(bp)


# ── Index route ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main HTML interface."""
    return render_template("index.html",
                           MAX_CLUES=MAX_CLUES, MAX_GRID=MAX_GRID)


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    PORT = 5055
    threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    print(f"Starting Nonogram web app \u2192 http://localhost:{PORT}")
    HOST = os.environ.get("NONOGRAM_HOST", "0.0.0.0")
    socketio.run(app, host=HOST, port=PORT, debug=False, allow_unsafe_werkzeug=True)
