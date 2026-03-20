"""Solver routes: classical solve, quantum solve, benchmark."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from tools.chart import render_chart_b64, report_to_dict
from tools.config import RUNS_DIR
from tools.state import emit_status, set_busy, state

bp = Blueprint("solver", __name__)


def _save_run(payload: dict) -> None:
    """Persist run payload as JSON to RUNS_DIR; errors are non-fatal."""
    try:
        run_file = RUNS_DIR / f"run_{payload['run_id']}.json"
        with open(run_file, "w") as fh:
            json.dump(payload, fh, indent=2)
    except Exception:
        pass


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
    """Extract and convert clues from request JSON."""
    row_clues = [tuple(c) for c in data["row_clues"]]
    col_clues = [tuple(c) for c in data["col_clues"]]
    return row_clues, col_clues, len(row_clues), len(col_clues)


def _get_quantum_solver():
    """Build the appropriate quantum Solver from hw_config state."""
    hw_cfg = state["hw_config"]
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


@bp.route("/api/solve/classical", methods=["POST"])
def api_solve_classical():
    """Trigger a classical (brute-force) solve in a background thread."""
    if state["busy"]:
        return jsonify({"error": "Solver busy"}), 409
    row_clues, col_clues, rows, cols = _parse_clues(request.json)
    set_busy(True)

    from nonogram.solver import ClassicalSolver

    solver = ClassicalSolver()
    emit_status(f"{solver.name} solver running\u2026", "warn")

    def _work():
        try:
            from tools.state import socketio

            result = solver.solve((row_clues, col_clues))
            solutions = result["solutions"]
            socketio.emit("cl_done", {"solutions": solutions, "rows": rows, "cols": cols})
            emit_status(f"{solver.name}: {len(solutions)} solution(s) found.", "ok")
        except Exception as exc:
            from tools.state import socketio

            socketio.emit("solver_error", {"message": str(exc)})
            emit_status(f"{solver.name} error: {exc}", "err")
        finally:
            set_busy(False)

    threading.Thread(target=_work, daemon=True).start()
    return jsonify({"ok": True})


@bp.route("/api/solve/quantum", methods=["POST"])
def api_solve_quantum():
    """Trigger a quantum (Grover) solve in a background thread."""
    if state["busy"]:
        return jsonify({"error": "Solver busy"}), 409
    row_clues, col_clues, rows, cols = _parse_clues(request.json)
    solver = _get_quantum_solver()
    set_busy(True)
    emit_status(f"{solver.name} running\u2026", "warn")

    def _work():
        try:
            from tools.state import socketio

            result = solver.solve((row_clues, col_clues))
            counts = result["counts"]
            socketio.emit("qu_done", {"counts": counts, "rows": rows, "cols": cols})
            if "backend_name" in result:
                emit_status(f"{solver.name} complete.", "ok")
            else:
                n_above = sum(
                    1 for p in counts.values() if p >= max(3.0 / (2 ** (rows * cols)), 0.005)
                )
                emit_status(
                    f"Quantum: simulation complete. {n_above} above-threshold outcome(s).", "ok"
                )
        except Exception as exc:
            from tools.state import socketio

            socketio.emit("solver_error", {"message": str(exc)})
            emit_status(f"Quantum error: {exc}", "err")
        finally:
            set_busy(False)

    threading.Thread(target=_work, daemon=True).start()
    return jsonify({"ok": True})


@bp.route("/api/benchmark", methods=["POST"])
def api_benchmark():
    """Run a benchmark comparing classical and quantum solvers."""
    if state["busy"]:
        return jsonify({"error": "Solver busy"}), 409
    data = request.json
    row_clues, col_clues, rows, cols = _parse_clues(data)
    trials = max(1, int(data.get("trials", 1)))
    hw_cfg = state["hw_config"]
    set_busy(True)
    label = f"{trials} trial{'s' if trials > 1 else ''}"
    emit_status(f"Benchmarking both solvers ({label}) \u2014 please wait\u2026", "warn")

    def _work():
        try:
            from nonogram import benchmark, classical_solve
            from tools.state import socketio

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
                _save_run(payload)
                socketio.emit("bench_done", payload)
                emit_status(f"Benchmark complete ({label}) \u2014 hardware: {backend_name}.", "ok")
            else:
                reports = [
                    benchmark((row_clues, col_clues), run_classical=True, run_quantum=True)
                    for _ in range(trials)
                ]
                cl_times = [r.classical.solve_time_s for r in reports if r.classical]
                qu_times = [r.quantum.solve_time_s for r in reports if r.quantum]
                report = reports[-1]
                solutions = classical_solve((row_clues, col_clues))
                # Collect per-trial quantum counts for histogram comparison
                from nonogram import quantum_solve

                qu_counts_list: list[dict] = []
                for _ in range(trials):
                    try:
                        qu_result = quantum_solve((row_clues, col_clues))
                        qu_counts_list.append(dict(qu_result.circuit_results[0]))
                    except Exception:
                        qu_counts_list.append({})
                raw_counts = qu_counts_list[-1] if qu_counts_list else {}
                per_trial = qu_counts_list if len(qu_counts_list) > 1 else None
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
                    qu_counts_per_trial=per_trial,
                )
                _save_run(payload)
                socketio.emit("bench_done", payload)
                emit_status(f"Benchmark complete ({label}) \u2014 metrics and chart below.", "ok")
        except Exception as exc:
            from tools.state import socketio

            socketio.emit("solver_error", {"message": str(exc)})
            emit_status(f"Benchmark error: {exc}", "err")
        finally:
            set_busy(False)

    threading.Thread(target=_work, daemon=True).start()
    return jsonify({"ok": True})
