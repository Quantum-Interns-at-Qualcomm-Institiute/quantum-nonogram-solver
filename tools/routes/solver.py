"""Solver routes: classical solve, quantum solve, benchmark.

Each operation has two forms:

* **async** (``POST /api/solve/classical`` etc.) — returns ``{"ok": true}`` and
  delivers the result over Socket.IO (``cl_done`` / ``qu_done`` / ``bench_done``).
* **synchronous** (``POST /api/solve/classical/sync`` etc.) — runs inline and
  returns the same result payload directly in the HTTP response, so the whole
  API is reachable with no Socket.IO client (the cross-repo "curl-able" rule).

Both forms share the same compute helpers and honour the single-solver busy lock.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from tools.chart import render_chart_b64, report_to_dict
from tools.config import MAX_TRIALS, RUNS_DIR
from tools.errors import respond_error
from tools.state import emit_status, set_busy, state, state_lock

bp = Blueprint("solver", __name__)


def _sanitize_error(exc: Exception) -> str:
    """Strip potential credentials from error messages."""
    import re

    msg = str(exc)
    # Remove anything that looks like an API token (long alphanumeric strings)
    msg = re.sub(r'[a-zA-Z0-9_-]{40,}', '[REDACTED]', msg)
    # Truncate to reasonable length
    return msg[:500]


def _save_run(payload: dict) -> None:
    """Persist run payload as JSON to RUNS_DIR; errors are non-fatal.

    The store is capped (NONOGRAM_MAX_RUNS, default 50): oldest run files are
    pruned first, so repeated benchmarks can never fill the volume.
    """
    try:
        max_runs = int(os.environ.get("NONOGRAM_MAX_RUNS", "50"))
        existing = sorted(RUNS_DIR.glob("run_*.json"), key=lambda p: p.stat().st_mtime)
        for stale in existing[: max(0, len(existing) - (max_runs - 1))]:
            stale.unlink(missing_ok=True)
        run_file = RUNS_DIR / f"run_{payload['run_id']}.json"
        with run_file.open("w") as fh:
            json.dump(payload, fh, indent=2)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to save run: %s", exc)


def _build_payload(
    report,
    solutions,
    qu_counts,
    rows,
    cols,
    trials,
    cl_times,
    qu_times,
    chart_b64,
    hardware=None,
    row_clues=None,
    col_clues=None,
    qu_counts_per_trial=None,
) -> dict:
    """Build the common payload dict for bench_done events and run persistence."""
    return {
        "run_id": uuid.uuid4().hex[:8],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "report": report_to_dict(report),
        "solutions": solutions,
        "qu_counts": qu_counts,
        "qu_counts_per_trial": qu_counts_per_trial,
        "rows": rows,
        "cols": cols,
        "trials": trials,
        "cl_times": cl_times,
        "qu_times": qu_times,
        "chart_img": chart_b64,
        "hardware": hardware,
        "puzzle": {
            "row_clues": [list(r) for r in row_clues] if row_clues else [],
            "col_clues": [list(c) for c in col_clues] if col_clues else [],
        },
    }


def _parse_clues(data: dict) -> tuple[list, list, int, int]:
    """Extract and convert clues from request JSON.

    Raises ValueError on a malformed body shape (missing keys, non-list
    entries) so routes can 400 instead of 500ing on a KeyError/TypeError.
    """
    try:
        row_clues = [tuple(c) for c in data["row_clues"]]
        col_clues = [tuple(c) for c in data["col_clues"]]
    except (KeyError, TypeError) as exc:
        msg = "body must carry 'row_clues' and 'col_clues' as lists of clue lists"
        raise ValueError(msg) from exc
    return row_clues, col_clues, len(row_clues), len(col_clues)


def _request_hw_cfg(data: dict) -> dict | None:
    """Per-request hardware config (preferred over the global toggle).

    The request may carry {"hw": {"backend_name": ..., "shots": ...}} — the
    token always comes from the server environment and shots are capped, so a
    caller chooses parameters but never credentials or unbounded spend. Falls
    back to the global hw_config state for the existing UI flow.
    """
    from tools.routes.hardware import MAX_SHOTS, _ibm_channel, _ibm_token

    hw_req = data.get("hw") if isinstance(data, dict) else None
    if isinstance(hw_req, dict) and hw_req.get("backend_name"):
        token = _ibm_token()
        if not token:
            return None
        try:
            shots = int(hw_req.get("shots", 1024))
        except (TypeError, ValueError):
            shots = 1024
        return {
            "token": token,
            "channel": _ibm_channel(hw_req),
            "backend_name": str(hw_req["backend_name"]),
            "shots": min(MAX_SHOTS, max(1, shots)),
        }
    with state_lock:
        return state.get("hw_config")


def _get_quantum_solver(hw_cfg=None):
    """Build the appropriate quantum Solver (per-request config, else global)."""
    if hw_cfg is None:
        with state_lock:
            hw_cfg = state.get("hw_config")
    if hw_cfg:
        from nonogram.solver import QuantumHardwareSolver

        return QuantumHardwareSolver(
            token=hw_cfg["token"],
            backend_name=hw_cfg["backend_name"],
            channel=hw_cfg["channel"],
            shots=hw_cfg["shots"],
        )
    from nonogram.solver import QuantumSimulatorSolver

    return QuantumSimulatorSolver()


def _run_benchmark(row_clues, col_clues, rows, cols, trials, hw_cfg) -> dict:
    """Run a benchmark and return the bench payload (also persisted to RUNS_DIR).

    Pure compute + persistence — no Socket.IO emits — so it is shared by both the
    async ``bench_done`` path and the synchronous ``/api/benchmark/sync`` route.
    """
    from nonogram import benchmark, classical_solve

    if hw_cfg:
        import time

        from nonogram.quantum import quantum_solve_hardware

        cl_times: list[float] = []
        for _ in range(trials):
            rpt = benchmark((row_clues, col_clues), run_classical=True, run_quantum=False)
            if rpt.classical:
                cl_times.append(rpt.classical.solve_time_s)
        t0 = time.perf_counter()
        hw_counts, backend_name = quantum_solve_hardware(
            (row_clues, col_clues),
            token=hw_cfg["token"],
            backend_name=hw_cfg["backend_name"],
            channel=hw_cfg["channel"],
            shots=hw_cfg["shots"],
        )
        qu_times = [time.perf_counter() - t0]
        report = benchmark((row_clues, col_clues), run_classical=True, run_quantum=False)
        solutions = classical_solve((row_clues, col_clues))
        chart_b64 = render_chart_b64(report, cl_times, qu_times)
        payload = _build_payload(
            report,
            solutions,
            hw_counts,
            rows,
            cols,
            trials,
            cl_times,
            qu_times,
            chart_b64,
            hardware=backend_name,
            row_clues=row_clues,
            col_clues=col_clues,
        )
    else:
        reports = [
            benchmark((row_clues, col_clues), run_classical=True, run_quantum=True)
            for _ in range(trials)
        ]
        cl_times = [r.classical.solve_time_s for r in reports if r.classical]
        qu_times = [r.quantum.solve_time_s for r in reports if r.quantum]
        report = reports[-1]
        solutions = classical_solve((row_clues, col_clues))
        # Get raw counts for histogram from a single quantum run
        # (timing data already collected by benchmark above)
        from nonogram import quantum_solve

        try:
            qu_result = quantum_solve((row_clues, col_clues))
            raw_counts = dict(qu_result.circuit_results[0])
        except Exception:
            raw_counts = {}
        chart_b64 = render_chart_b64(report, cl_times, qu_times)
        payload = _build_payload(
            report,
            solutions,
            raw_counts,
            rows,
            cols,
            trials,
            cl_times,
            qu_times,
            chart_b64,
            row_clues=row_clues,
            col_clues=col_clues,
            qu_counts_per_trial=None,
        )
    _save_run(payload)
    return payload


# ── Shared request preamble for the synchronous routes ───────────────────────


def _acquire_or_busy():
    """Return None if the busy lock was acquired, else a 409 error response."""
    with state_lock:
        if state["busy"]:
            return respond_error("solver_busy", "Solver busy", 409)
        state["busy"] = True
    return None


def _parse_validated_clues():
    """Parse + validate clues from the request body.

    Returns ``(row_clues, col_clues, rows, cols, None)`` on success, or
    ``(None, None, None, None, error_response)`` on a bad body.
    """
    data = request.json
    if data is None:
        return None, None, None, None, respond_error(
            "invalid_json", "Invalid or missing JSON body", 400
        )
    row_clues, col_clues, rows, cols = _parse_clues(data)
    from nonogram.io import _MAX_CELLS, _validate_clues

    try:
        _validate_clues(row_clues, col_clues, max_cells=_MAX_CELLS)
    except Exception as e:
        return None, None, None, None, respond_error("invalid_clues", str(e), 400)
    return row_clues, col_clues, rows, cols, None


@bp.route("/api/solve/classical", methods=["POST"])
def api_solve_classical():
    """Trigger a classical (brute-force) solve in a background thread."""
    # Parse + validate (incl. the grid-area cap) BEFORE taking the busy lock, so a
    # bad or oversized body (400/413) can never leave the solver wedged as busy.
    data = request.json
    if data is None:
        return respond_error("invalid_json", "Invalid or missing JSON body", 400)
    try:
        row_clues, col_clues, rows, cols = _parse_clues(data)
    except ValueError as e:
        return respond_error("invalid_clues", str(e), 400)

    from nonogram.io import _MAX_CELLS, _validate_clues
    try:
        _validate_clues(row_clues, col_clues, max_cells=_MAX_CELLS)
    except Exception as e:
        return respond_error("invalid_clues", str(e), 400)

    with state_lock:
        if state["busy"]:
            return respond_error("solver_busy", "Solver busy", 409)
        state["busy"] = True

    # Scope result emits to the requesting client when it tells us its sid.
    to = data.get("sid") or None

    from nonogram.solver import ClassicalSolver

    solver = ClassicalSolver()
    emit_status(f"{solver.name} solver running…", "warn", to=to)

    def _work():
        try:
            from tools.state import socketio

            result = solver.solve((row_clues, col_clues))
            solutions = result["solutions"]
            socketio.emit("cl_done", {"solutions": solutions, "rows": rows, "cols": cols}, to=to)
            emit_status(f"{solver.name}: {len(solutions)} solution(s) found.", "ok", to=to)
        except Exception as exc:
            from tools.state import socketio

            socketio.emit("solver_error", {"message": _sanitize_error(exc)}, to=to)
            emit_status(f"{solver.name} error: {_sanitize_error(exc)}", "err", to=to)
        finally:
            set_busy(False)

    threading.Thread(target=_work, daemon=True).start()
    return jsonify({"ok": True})


@bp.route("/api/solve/quantum", methods=["POST"])
def api_solve_quantum():
    """Trigger a quantum (Grover) solve in a background thread."""
    # Parse + validate (incl. the grid-area cap) BEFORE taking the busy lock, so a
    # bad or oversized body (400/413) can never leave the solver wedged as busy.
    data = request.json
    if data is None:
        return respond_error("invalid_json", "Invalid or missing JSON body", 400)
    try:
        row_clues, col_clues, rows, cols = _parse_clues(data)
    except ValueError as e:
        return respond_error("invalid_clues", str(e), 400)

    from nonogram.io import _MAX_CELLS, _validate_clues
    try:
        _validate_clues(row_clues, col_clues, max_cells=_MAX_CELLS)
    except Exception as e:
        return respond_error("invalid_clues", str(e), 400)

    with state_lock:
        if state["busy"]:
            return respond_error("solver_busy", "Solver busy", 409)
        state["busy"] = True

    to = data.get("sid") or None
    solver = _get_quantum_solver(_request_hw_cfg(data))
    emit_status(f"{solver.name} running…", "warn", to=to)

    def _work():
        try:
            from tools.state import socketio

            result = solver.solve((row_clues, col_clues))
            counts = result["counts"]
            socketio.emit("qu_done", {"counts": counts, "rows": rows, "cols": cols}, to=to)
            if "backend_name" in result:
                emit_status(f"{solver.name} complete.", "ok", to=to)
            else:
                n_above = sum(
                    1 for p in counts.values() if p >= max(3.0 / (2 ** (rows * cols)), 0.005)
                )
                emit_status(
                    f"Quantum: simulation complete. {n_above} above-threshold outcome(s).",
                    "ok",
                    to=to,
                )
        except Exception as exc:
            from tools.state import socketio

            socketio.emit("solver_error", {"message": _sanitize_error(exc)}, to=to)
            emit_status(f"Quantum error: {_sanitize_error(exc)}", "err", to=to)
        finally:
            set_busy(False)

    threading.Thread(target=_work, daemon=True).start()
    return jsonify({"ok": True})


@bp.route("/api/benchmark", methods=["POST"])
def api_benchmark():
    """Run a benchmark comparing classical and quantum solvers."""
    # Parse + validate (incl. the grid-area cap) BEFORE taking the busy lock, so a
    # bad or oversized body (400/413) can never leave the solver wedged as busy.
    data = request.json
    if data is None:
        return respond_error("invalid_json", "Invalid or missing JSON body", 400)
    try:
        row_clues, col_clues, rows, cols = _parse_clues(data)
    except ValueError as e:
        return respond_error("invalid_clues", str(e), 400)

    from nonogram.io import _MAX_CELLS, _validate_clues
    try:
        _validate_clues(row_clues, col_clues, max_cells=_MAX_CELLS)
    except Exception as e:
        return respond_error("invalid_clues", str(e), 400)

    with state_lock:
        if state["busy"]:
            return respond_error("solver_busy", "Solver busy", 409)
        state["busy"] = True
    trials = min(MAX_TRIALS, max(1, int(data.get("trials", 1))))
    to = data.get("sid") or None
    hw_cfg = _request_hw_cfg(data)
    label = f"{trials} trial{'s' if trials > 1 else ''}"
    emit_status(f"Benchmarking both solvers ({label}) — please wait…", "warn", to=to)

    def _work():
        try:
            from tools.state import socketio

            payload = _run_benchmark(row_clues, col_clues, rows, cols, trials, hw_cfg)
            socketio.emit("bench_done", payload, to=to)
            if payload.get("hardware"):
                emit_status(
                    f"Benchmark complete ({label}) — hardware: {payload['hardware']}.", "ok", to=to
                )
            else:
                emit_status(f"Benchmark complete ({label}) — metrics and chart below.", "ok", to=to)
        except Exception as exc:
            from tools.state import socketio

            socketio.emit("solver_error", {"message": _sanitize_error(exc)}, to=to)
            emit_status(f"Benchmark error: {_sanitize_error(exc)}", "err", to=to)
        finally:
            set_busy(False)

    threading.Thread(target=_work, daemon=True).start()
    return jsonify({"ok": True})


# ── Synchronous (curl-able) equivalents ──────────────────────────────────────


@bp.route("/api/solve/classical/sync", methods=["POST"])
def api_solve_classical_sync():
    """Classical solve, synchronous: returns {solutions, rows, cols} in the response."""
    busy = _acquire_or_busy()
    if busy is not None:
        return busy
    try:
        row_clues, col_clues, rows, cols, err = _parse_validated_clues()
        if err is not None:
            return err
        from nonogram.solver import ClassicalSolver

        result = ClassicalSolver().solve((row_clues, col_clues))
        return jsonify({"solutions": result["solutions"], "rows": rows, "cols": cols})
    except Exception as exc:
        return respond_error("solve_error", _sanitize_error(exc), 500)
    finally:
        set_busy(False)


@bp.route("/api/solve/quantum/sync", methods=["POST"])
def api_solve_quantum_sync():
    """Quantum solve, synchronous: returns {counts, rows, cols} in the response."""
    busy = _acquire_or_busy()
    if busy is not None:
        return busy
    try:
        row_clues, col_clues, rows, cols, err = _parse_validated_clues()
        if err is not None:
            return err
        result = _get_quantum_solver().solve((row_clues, col_clues))
        return jsonify({"counts": result["counts"], "rows": rows, "cols": cols})
    except Exception as exc:
        return respond_error("solve_error", _sanitize_error(exc), 500)
    finally:
        set_busy(False)


@bp.route("/api/benchmark/sync", methods=["POST"])
def api_benchmark_sync():
    """Benchmark, synchronous: returns the full bench payload in the response."""
    busy = _acquire_or_busy()
    if busy is not None:
        return busy
    try:
        row_clues, col_clues, rows, cols, err = _parse_validated_clues()
        if err is not None:
            return err
        trials = min(MAX_TRIALS, max(1, int((request.json or {}).get("trials", 1))))
        with state_lock:
            hw_cfg = state.get("hw_config")
        payload = _run_benchmark(row_clues, col_clues, rows, cols, trials, hw_cfg)
        return jsonify(payload)
    except Exception as exc:
        return respond_error("benchmark_error", _sanitize_error(exc), 500)
    finally:
        set_busy(False)
