"""
Benchmarking and comparison metrics for classical vs quantum nonogram solving.

Usage::

    from nonogram.metrics import benchmark, print_report

    puzzle = (
        [(1, 1), (2, 2), (1, 2, 1), (1, 1)],
        [(4,),   (1,),   (1,),       (1,),   (1,), (4,)],
    )
    report = benchmark(puzzle, run_classical=True, run_quantum=True)
    print_report(report)
"""

from __future__ import annotations

import math
import time
import tracemalloc
from dataclasses import dataclass, field

from nonogram.core import puzzle_to_boolean, var_clauses


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ClassicalMetrics:
    """Performance metrics for the classical brute-force solver."""

    solve_time_s: float
    """Wall-clock seconds elapsed during the solve."""

    configurations_evaluated: int
    """Total candidates checked = 2^(n*d)."""

    solutions_found: int
    """Number of satisfying assignments found."""

    peak_memory_kb: float
    """Peak heap allocation during the solve (kilobytes)."""

    configs_per_second: float = field(init=False)
    """Throughput: configurations evaluated per second."""

    def __post_init__(self) -> None:
        self.configs_per_second = (
            self.configurations_evaluated / self.solve_time_s
            if self.solve_time_s > 0
            else float("inf")
        )


@dataclass
class QuantumMetrics:
    """Performance and circuit metrics for the Grover's-algorithm solver."""

    solve_time_s: float
    """Wall-clock seconds elapsed during the solve (includes circuit construction + simulation)."""

    num_qubits: int
    """Total qubits in the Grover circuit (problem + ancilla)."""

    circuit_depth: int
    """Critical-path length of the full Grover circuit (gate layers)."""

    total_gate_count: int
    """Total number of gates in the circuit."""

    two_qubit_gate_count: int
    """Number of 2+-qubit (entangling) gates — a key resource cost on real hardware."""

    gate_counts_by_type: dict[str, int]
    """Per-gate-type breakdown, e.g. {'cx': 120, 'h': 24, 't': 96, ...}."""

    grover_iterations: int
    """Number of Grover operator applications used."""

    top_result_probability: float
    """Sampling probability of the most-likely measurement outcome (0–1)."""

    oracle_evaluation_correct: bool
    """Whether the top measurement satisfies the nonogram constraints."""

    solutions_found: int
    """Number of distinct valid solutions recovered from the top measurements."""

    peak_memory_kb: float
    """Peak heap allocation during the solve (kilobytes)."""


@dataclass
class ComparisonReport:
    """Side-by-side comparison of classical and quantum nonogram solving."""

    # --- puzzle metadata ---
    rows: int
    cols: int
    num_variables: int
    """n × d — the number of Boolean variables in the SAT formulation."""

    search_space_size: int
    """2^(n*d) — total configurations for exhaustive search."""

    boolean_expression_length: int
    """Character length of the boolean SAT expression (proxy for problem complexity)."""

    # --- solver results (None if that solver was not run) ---
    classical: ClassicalMetrics | None = None
    quantum: QuantumMetrics | None = None

    # --- derived comparison metrics ---
    theoretical_grover_speedup: float = field(init=False, default=0.0)
    """√(search_space) — the asymptotic Grover speedup over exhaustive search."""

    actual_speedup: float = field(init=False, default=0.0)
    """classical_time / quantum_time — measured wall-clock speedup."""

    quantum_advantage_ratio: float = field(init=False, default=0.0)
    """actual_speedup / theoretical_grover_speedup — how close to the theoretical ideal."""

    def __post_init__(self) -> None:
        self.theoretical_grover_speedup = math.sqrt(self.search_space_size)
        if self.classical and self.quantum:
            self.actual_speedup = (
                self.classical.solve_time_s / self.quantum.solve_time_s
                if self.quantum.solve_time_s > 0
                else float("inf")
            )
            self.quantum_advantage_ratio = (
                self.actual_speedup / self.theoretical_grover_speedup
                if self.theoretical_grover_speedup > 0
                else 0.0
            )


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def benchmark(
    puzzle: tuple[list, list],
    run_classical: bool = True,
    run_quantum: bool = True,
) -> ComparisonReport:
    """Run one or both solvers on *puzzle* and collect comparison metrics.

    Args:
        puzzle: (row_clues, col_clues) tuple.
        run_classical: Whether to run the classical brute-force solver.
            Set False to skip if the puzzle is too large (> ~20 variables).
        run_quantum: Whether to run the quantum Grover solver.
            Requires qiskit and tweedledum.

    Returns:
        A :class:`ComparisonReport` populated with all measured metrics.

    Warning:
        The classical solver is O(2^(n*d)).  For the 4×6 demo puzzle (24
        variables) it takes ~18 minutes.  Use ``run_classical=False`` and
        supply ``classical_override`` if you already have timing data, or
        choose a smaller puzzle for interactive benchmarking.
    """
    row_clues, col_clues = puzzle
    n, d = len(row_clues), len(col_clues)
    num_vars = n * d
    search_space = 2 ** num_vars

    # Build the boolean expression once (shared cost)
    expression = puzzle_to_boolean(row_clues, col_clues, classical=False)
    expr_len = len(expression)

    classical_metrics: ClassicalMetrics | None = None
    quantum_metrics: QuantumMetrics | None = None

    # --- Classical ---
    if run_classical:
        from nonogram.classical import classical_solve

        tracemalloc.start()
        t0 = time.perf_counter()
        solutions = classical_solve(puzzle)
        elapsed = time.perf_counter() - t0
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        classical_metrics = ClassicalMetrics(
            solve_time_s=elapsed,
            configurations_evaluated=search_space,
            solutions_found=len(solutions),
            peak_memory_kb=peak / 1024,
        )

    # --- Quantum ---
    if run_quantum:
        from qiskit.circuit.library import PhaseOracleGate
        from qiskit.primitives import StatevectorSampler
        from qiskit_algorithms import AmplificationProblem, Grover

        oracle = PhaseOracleGate(expression)
        # AmplificationProblem auto-infers is_good_state from oracle.boolean_expression
        problem = AmplificationProblem(oracle)
        grover = Grover(sampler=StatevectorSampler())

        # Extract circuit metrics before running (no sampling cost)
        iterations_used = Grover.optimal_num_iterations(
            num_solutions=1, num_qubits=oracle.num_qubits
        )
        circuit = grover.construct_circuit(problem, power=iterations_used, measurement=False)
        ops = circuit.count_ops()
        two_qubit = circuit.num_nonlocal_gates()

        tracemalloc.start()
        t0 = time.perf_counter()
        result = grover.amplify(problem)
        elapsed = time.perf_counter() - t0
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        top_counts = result.circuit_results[0]
        top_prob = max(top_counts.values()) / sum(top_counts.values())
        top_bitstring = max(top_counts, key=top_counts.__getitem__)
        bool_expr = oracle.boolean_expression
        # Qiskit bitstrings are little-endian (rightmost bit = qubit 0).
        # BooleanExpression.simulate() expects variable order x0, x1, ...
        # so we reverse each bitstring before evaluating.
        oracle_correct = bool_expr.simulate(top_bitstring[::-1])
        valid_solutions = sum(
            1 for bs in top_counts if bool_expr.simulate(bs[::-1])
        )

        quantum_metrics = QuantumMetrics(
            solve_time_s=elapsed,
            num_qubits=circuit.num_qubits,
            circuit_depth=circuit.depth(),
            total_gate_count=sum(ops.values()),
            two_qubit_gate_count=two_qubit,
            gate_counts_by_type=dict(ops),
            grover_iterations=iterations_used,
            top_result_probability=top_prob,
            oracle_evaluation_correct=oracle_correct,
            solutions_found=valid_solutions,
            peak_memory_kb=peak / 1024,
        )

    return ComparisonReport(
        rows=n,
        cols=d,
        num_variables=num_vars,
        search_space_size=search_space,
        boolean_expression_length=expr_len,
        classical=classical_metrics,
        quantum=quantum_metrics,
    )


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------

def print_report(report: ComparisonReport) -> None:
    """Print a formatted side-by-side comparison of the benchmark results."""
    SEP = "─" * 62
    W = 28  # column width for value fields

    def row(label: str, classical_val: str, quantum_val: str) -> str:
        return f"  {label:<30} {classical_val:>{W}} {quantum_val:>{W}}"

    def section(title: str) -> str:
        return f"\n  {title}\n  {'─' * (60)}"

    print(f"\n{'═' * 64}")
    print(f"  NONOGRAM SOLVER BENCHMARK  —  {report.rows}×{report.cols} puzzle")
    print(f"{'═' * 64}")

    # Puzzle metadata
    print(section("Puzzle"))
    print(row("Variables (n×d)", str(report.num_variables), ""))
    print(row("Search space (2^vars)", f"{report.search_space_size:,}", ""))
    print(row("Boolean expr length (chars)", f"{report.boolean_expression_length:,}", ""))

    # Header
    print(section("Solver"))
    print(row("", "Classical", "Quantum (Grover)"))
    print(f"  {'─' * 60}")

    c = report.classical
    q = report.quantum

    def fmt(val, fmt_str: str, unit: str = "") -> str:
        if val is None:
            return "—"
        return format(val, fmt_str) + unit

    # Timing
    print(row("Solve time (s)",
              fmt(c and c.solve_time_s, ".4f", " s"),
              fmt(q and q.solve_time_s, ".4f", " s")))
    print(row("Peak memory (KB)",
              fmt(c and c.peak_memory_kb, ",.1f", " KB"),
              fmt(q and q.peak_memory_kb, ",.1f", " KB")))
    print(row("Solutions found",
              fmt(c and c.solutions_found, "d"),
              fmt(q and q.solutions_found, "d")))

    # Classical-specific
    print(row("Configs evaluated",
              fmt(c and c.configurations_evaluated, ",d"),
              "N/A"))
    print(row("Throughput (configs/s)",
              fmt(c and c.configs_per_second, ",.0f"),
              "N/A"))

    # Quantum-specific
    print(row("Qubits",
              "N/A",
              fmt(q and q.num_qubits, "d")))
    print(row("Circuit depth",
              "N/A",
              fmt(q and q.circuit_depth, ",d")))
    print(row("Total gates",
              "N/A",
              fmt(q and q.total_gate_count, ",d")))
    print(row("2-qubit (entangling) gates",
              "N/A",
              fmt(q and q.two_qubit_gate_count, ",d")))
    print(row("Grover iterations",
              "N/A",
              fmt(q and q.grover_iterations, "d")))
    print(row("Top-state probability",
              "N/A",
              fmt(q and q.top_result_probability, ".2%")))
    print(row("Oracle validation",
              "N/A",
              "✓ correct" if q and q.oracle_evaluation_correct else ("✗ wrong" if q else "—")))

    if q and q.gate_counts_by_type:
        top_gates = sorted(q.gate_counts_by_type.items(), key=lambda x: -x[1])[:5]
        gate_str = "  ".join(f"{g}:{n}" for g, n in top_gates)
        print(row("Top gate types", "N/A", gate_str[:W]))

    # Comparison
    if c and q:
        print(section("Comparison"))
        print(row("Theoretical Grover speedup",
                  f"√{report.search_space_size:,}",
                  f"≈{report.theoretical_grover_speedup:,.0f}×"))
        print(row("Actual speedup",
                  f"{report.actual_speedup:,.1f}×", ""))
        print(row("Advantage ratio (actual/theoretical)",
                  f"{report.quantum_advantage_ratio:.3f}", ""))
        classical_oracle = c.configurations_evaluated
        grover_oracle = report.quantum.grover_iterations if q else 0
        print(row("Classical oracle calls", f"{classical_oracle:,}", ""))
        print(row("Quantum oracle calls (est.)", "", f"{grover_oracle:,}"))
        reduction = (1 - grover_oracle / classical_oracle) * 100 if classical_oracle else 0
        print(row("Oracle call reduction", "", f"{reduction:.1f}%"))

    print(f"\n{'═' * 64}\n")
