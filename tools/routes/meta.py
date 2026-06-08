"""Health and API-discovery routes (shared backend API contract).

Implements the cross-repo contract documented in the website repo at
``docs/api-contract/CONTRACT.md``:

  * ``GET /health`` — liveness probe ``{status, service, version, uptime_s}``
  * ``GET /api``    — discovery: every HTTP endpoint plus the Socket.IO
    streaming channels, so the whole surface is reachable with no frontend.

Both routes are read-only, unauthenticated, and require no prior state.
"""

from __future__ import annotations

import time
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from flask import Blueprint, current_app, jsonify

SERVICE = "nonogram"
_START = time.monotonic()

# Socket.IO events are not in the HTTP url-map, so enumerate them by hand.
# Each result event has a synchronous REST equivalent (see /api/solve/*/sync,
# /api/benchmark/sync) — the streaming layer is additive, never the only path.
_STREAMING = [
    {
        "protocol": "socket.io",
        "event": "status",
        "description": "Solver progress and status updates.",
    },
    {
        "protocol": "socket.io",
        "event": "cl_done",
        "description": "Classical solve result; live equivalent of POST /api/solve/classical/sync.",
    },
    {
        "protocol": "socket.io",
        "event": "qu_done",
        "description": "Quantum solve result; live equivalent of POST /api/solve/quantum/sync.",
    },
    {
        "protocol": "socket.io",
        "event": "bench_done",
        "description": "Benchmark result; live equivalent of POST /api/benchmark/sync.",
    },
    {
        "protocol": "socket.io",
        "event": "solver_error",
        "description": "Solver failure notification.",
    },
]

bp = Blueprint("meta", __name__)


def _version() -> str:
    try:
        return _pkg_version("nonogram")
    except PackageNotFoundError:
        return "0.1.0"


@bp.get("/health")
def health():
    """Liveness probe for the nonogram backend."""
    return jsonify(
        {
            "status": "ok",
            "service": SERVICE,
            "version": _version(),
            "uptime_s": round(time.monotonic() - _START, 1),
        }
    )


@bp.get("/api")
def api_index():
    """Discovery index: every HTTP endpoint plus streaming channels."""
    seen: set[tuple[str, str]] = set()
    endpoints = []
    for rule in current_app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = str(rule)
        view = current_app.view_functions.get(rule.endpoint)
        summary = ((getattr(view, "__doc__", "") or "").strip().splitlines() or [""])[0].strip()
        for method in (rule.methods or set()) - {"HEAD", "OPTIONS"}:
            key = (method, path)
            if key in seen:
                continue
            seen.add(key)
            endpoints.append({"method": method, "path": path, "summary": summary})
    endpoints.sort(key=lambda e: (e["path"], e["method"]))
    return jsonify(
        {
            "service": SERVICE,
            "version": _version(),
            "endpoints": endpoints,
            "streaming": _STREAMING,
        }
    )
