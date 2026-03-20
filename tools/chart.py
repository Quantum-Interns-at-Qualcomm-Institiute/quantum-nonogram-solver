"""Chart rendering and report serialization for benchmark results."""

from __future__ import annotations

import base64
import io
import statistics
from typing import Any

# Chart colours (match tools/static/style.css CSS custom properties)
BG_CARD = "#ffffff"
BTN_CL = "#27ae60"
BTN_QU = "#8e44ad"
FG_DIM = "#666666"
FG_MAIN = "#222222"


def report_to_dict(report: Any) -> dict:
    """Convert a ComparisonReport to a JSON-serializable dictionary."""
    cl = report.classical
    qu = report.quantum
    return {
        "num_variables": report.num_variables,
        "search_space_size": report.search_space_size,
        "boolean_expression_length": report.boolean_expression_length,
        "theoretical_grover_speedup": report.theoretical_grover_speedup,
        "actual_speedup": report.actual_speedup,
        "quantum_advantage_ratio": report.quantum_advantage_ratio,
        "classical": {
            "solve_time_s": cl.solve_time_s,
            "configurations_evaluated": cl.configurations_evaluated,
            "solutions_found": cl.solutions_found,
            "peak_memory_kb": cl.peak_memory_kb,
            "configs_per_second": cl.configs_per_second,
        }
        if cl
        else None,
        "quantum": {
            "solve_time_s": qu.solve_time_s,
            "num_qubits": qu.num_qubits,
            "circuit_depth": qu.circuit_depth,
            "total_gate_count": qu.total_gate_count,
            "two_qubit_gate_count": qu.two_qubit_gate_count,
            "grover_iterations": qu.grover_iterations,
            "top_result_probability": qu.top_result_probability,
            "oracle_evaluation_correct": qu.oracle_evaluation_correct,
            "solutions_found": qu.solutions_found,
            "peak_memory_kb": qu.peak_memory_kb,
        }
        if qu
        else None,
    }


def render_chart_b64(
    report: Any,
    cl_times: list[float],
    qu_times: list[float],
) -> str:
    """Render benchmark metrics as a side-by-side matplotlib chart in base64."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return ""

    cl = report.classical
    qu = report.quantum
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7, 3.5), facecolor=BG_CARD)
    fig.suptitle("Solver Benchmark Comparison", color=FG_MAIN, fontsize=12, fontweight="bold")

    SPINE = "#c0c8d0"

    def _style(ax: Any, title: str) -> None:
        ax.set_facecolor("#f4f8fc")
        ax.set_title(title, color=FG_MAIN, fontsize=9)
        ax.tick_params(colors=FG_MAIN, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(SPINE)

    _style(ax1, "Solve Time (seconds)")
    labels, vals, colors, errs = [], [], [], []
    if cl:
        labels.append("Classical")
        vals.append(cl.solve_time_s)
        colors.append(BTN_CL)
        errs.append(0 if not cl_times or len(cl_times) < 2 else statistics.stdev(cl_times))
    if qu:
        labels.append("Quantum")
        vals.append(qu.solve_time_s)
        colors.append(BTN_QU)
        errs.append(0 if not qu_times or len(qu_times) < 2 else statistics.stdev(qu_times))
    if labels:
        bars = ax1.bar(
            labels,
            vals,
            color=colors,
            width=0.4,
            yerr=errs if any(e > 0 for e in errs) else None,
            capsize=5,
            error_kw={"color": FG_MAIN},
        )
        ax1.set_ylabel("seconds", color=FG_MAIN, fontsize=8)
        for bar, v in zip(bars, vals):
            ax1.text(
                bar.get_x() + bar.get_width() / 2,
                v * 1.03,
                f"{v:.4f}s",
                ha="center",
                va="bottom",
                color=FG_MAIN,
                fontsize=7,
            )
    ax1.tick_params(axis="x", colors=FG_MAIN)
    ax1.tick_params(axis="y", colors=FG_MAIN)

    _style(ax2, "Quantum Circuit Metrics")
    if qu:
        q_labels = ["Qubits", "Depth", "Gates", "2Q-Gates", "Iter"]
        q_vals = [
            qu.num_qubits,
            qu.circuit_depth,
            qu.total_gate_count,
            qu.two_qubit_gate_count,
            qu.grover_iterations,
        ]
        bars = ax2.bar(q_labels, q_vals, color=BTN_QU)
        ax2.set_ylabel("count", color=FG_MAIN, fontsize=8)
        ax2.tick_params(axis="x", rotation=12, colors=FG_MAIN)
        ax2.tick_params(axis="y", colors=FG_MAIN)
        for bar, v in zip(bars, q_vals):
            ax2.text(
                bar.get_x() + bar.get_width() / 2,
                v + 0.05,
                str(v),
                ha="center",
                va="bottom",
                color=FG_MAIN,
                fontsize=7,
            )
    else:
        ax2.text(
            0.5,
            0.5,
            "Quantum solver not run",
            ha="center",
            va="center",
            color=FG_DIM,
            fontsize=9,
            transform=ax2.transAxes,
        )

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=110)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()
