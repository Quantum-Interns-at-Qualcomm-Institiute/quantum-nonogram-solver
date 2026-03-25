"""
Grover vs brute-force benchmarking comparison across nonogram sizes.

Runs both classical brute-force and quantum Grover solvers on puzzles of
increasing size, collecting execution counts, static circuit metrics, and
constraint density. Outputs a structured comparison showing O(N) classical
constraint checks vs O(sqrt(N)) Grover iterations with circuit depth overhead.

Usage::

    python tools/benchmark_comparison.py
    python tools/benchmark_comparison.py --max-size 5 --json results.json
"""

from __future__ import annotations

import argparse
import json
import math

from nonogram.metrics import benchmark, print_report

# Puzzles of increasing size with known solutions for benchmarking.
BENCHMARK_PUZZLES: dict[str, tuple[list, list]] = {
    "1x1": ([(1,)], [(1,)]),
    "2x2": ([(1,), (1,)], [(1,), (1,)]),
    "3x3": ([(1,), (1, 1), (1,)], [(1,), (1, 1), (1,)]),
    "3x4": ([(1,), (2,), (1, 1)], [(1,), (1, 1), (1,), (1,)]),
    "4x4": ([(1,), (2,), (1, 1), (1,)], [(1,), (1, 1), (1,), (2,)]),
    "5x5": (
        [(2,), (1, 1), (3,), (1,), (2,)],
        [(1,), (2,), (1, 1), (2,), (1, 1)],
    ),
}


def run_comparison(
    max_size: int = 5,
    run_quantum: bool = True,
    output_json: str | None = None,
) -> list[dict]:
    """Run benchmarks across puzzle sizes and collect comparison data.

    Parameters
    ----------
    max_size : int
        Maximum grid dimension to benchmark (e.g., 5 means up to 5x5).
    run_quantum : bool
        Whether to run the quantum solver (requires qiskit).
    output_json : str, optional
        Path to write JSON results.

    Returns
    -------
    list[dict]
        Benchmark results for each puzzle size.
    """
    results = []

    for name, puzzle in BENCHMARK_PUZZLES.items():
        n, d = len(puzzle[0]), len(puzzle[1])
        if max(n, d) > max_size:
            continue

        num_vars = n * d
        search_space = 2**num_vars

        print(f"\n{'=' * 60}")
        print(f"  Benchmarking {name} puzzle ({n}x{d}, {num_vars} variables)")
        print(f"  Search space: {search_space:,} configurations")
        print(f"{'=' * 60}")

        # Full benchmark with all features
        report = benchmark(
            puzzle,
            run_classical=True,
            run_quantum=run_quantum and num_vars <= 20,
            static_analysis=run_quantum,
            compute_constraint_density=True,
        )

        print_report(report)

        # Collect structured data
        entry = {
            "name": name,
            "rows": n,
            "cols": d,
            "num_variables": num_vars,
            "search_space": search_space,
            "theoretical_grover_speedup": math.sqrt(search_space),
        }

        if report.classical:
            entry["classical"] = {
                "solve_time_s": report.classical.solve_time_s,
                "configurations_evaluated": report.classical.configurations_evaluated,
                "clause_evaluations": report.classical.clause_evaluations,
                "subclause_evaluations": report.classical.subclause_evaluations,
                "literal_evaluations": report.classical.literal_evaluations,
                "constraint_checks": report.classical.constraint_checks,
                "early_terminations": report.classical.early_terminations,
                "solutions_found": report.classical.solutions_found,
            }

        if report.static_circuit:
            sc = report.static_circuit
            entry["quantum_static"] = {
                "num_qubits": sc.num_qubits,
                "circuit_depth": sc.circuit_depth,
                "total_gate_count": sc.total_gate_count,
                "two_qubit_gate_count": sc.two_qubit_gate_count,
                "two_qubit_gate_density": sc.two_qubit_gate_density,
                "grover_iterations": sc.grover_iterations,
                "depth_per_iteration": sc.depth_per_iteration,
                "gates_per_qubit": sc.gates_per_qubit,
            }

        if report.quantum:
            entry["quantum_simulated"] = {
                "solve_time_s": report.quantum.solve_time_s,
                "grover_iterations": report.quantum.grover_iterations,
                "oracle_correct": report.quantum.oracle_evaluation_correct,
                "top_probability": report.quantum.top_result_probability,
                "solutions_found": report.quantum.solutions_found,
            }

        if report.constraint_density_metrics:
            entry["constraint_density"] = report.constraint_density_metrics

        if report.classical and report.quantum:
            entry["comparison"] = {
                "actual_speedup": report.actual_speedup,
                "theoretical_speedup": report.theoretical_grover_speedup,
                "advantage_ratio": report.quantum_advantage_ratio,
            }

        results.append(entry)

    # Print scaling summary
    print(f"\n{'=' * 60}")
    print("  SCALING SUMMARY: Grover vs Brute-Force")
    print(f"{'=' * 60}\n")
    print(f"  {'Size':<8} {'Vars':>5} {'Search Space':>14} "
          f"{'Classical Checks':>16} {'Grover Iters':>13} {'Theoretical':>12}")
    print(f"  {'─' * 72}")

    for entry in results:
        n_vars = entry["num_variables"]
        ss = entry["search_space"]
        cl_checks = entry.get("classical", {}).get("constraint_checks", "N/A")
        gr_iters = entry.get("quantum_static", {}).get("grover_iterations", "N/A")
        theoretical = f"sqrt({ss})"

        cl_str = f"{cl_checks:>16,}" if isinstance(cl_checks, int) else f"{'N/A':>16}"
        gr_str = f"{gr_iters:>13,}" if isinstance(gr_iters, int) else f"{'N/A':>13}"
        print(f"  {entry['name']:<8} {n_vars:>5} {ss:>14,} "
              f"{cl_str} {gr_str} {theoretical:>12}")

    print("\n  O(N) classical constraint checks vs O(sqrt(N)) Grover iterations")
    print("  Circuit depth overhead: O(log N) per iteration\n")

    if output_json:
        with open(output_json, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"  Results written to {output_json}\n")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Grover vs brute-force benchmarking comparison"
    )
    parser.add_argument(
        "--max-size", type=int, default=5,
        help="Maximum grid dimension to benchmark (default: 5)",
    )
    parser.add_argument(
        "--no-quantum", action="store_true",
        help="Skip quantum solver (classical-only benchmarks)",
    )
    parser.add_argument(
        "--json", type=str, default=None,
        help="Output JSON file for structured results",
    )
    args = parser.parse_args()
    run_comparison(
        max_size=args.max_size,
        run_quantum=not args.no_quantum,
        output_json=args.json,
    )


if __name__ == "__main__":
    main()
