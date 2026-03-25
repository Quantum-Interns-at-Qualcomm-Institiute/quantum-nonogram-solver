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
from itertools import combinations

from nonogram.core import puzzle_to_boolean

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

    clause_evaluations: int = 0
    """Total constraint clause evaluations across all candidates."""

    subclause_evaluations: int = 0
    """Total subclause evaluations (valid pattern checks)."""

    literal_evaluations: int = 0
    """Total individual literal evaluations."""

    constraint_checks: int = 0
    """Total constraint checks (alias for clause_evaluations)."""

    early_terminations: int = 0
    """Candidates rejected before evaluating all clauses."""

    configs_per_second: float = field(init=False)
    """Throughput: configurations evaluated per second."""

    early_termination_rate: float = field(init=False)
    """Fraction of candidates rejected early (0–1)."""

    avg_clauses_per_candidate: float = field(init=False)
    """Average clause evaluations per candidate (lower = more pruning)."""

    def __post_init__(self) -> None:
        self.configs_per_second = (
            self.configurations_evaluated / self.solve_time_s
            if self.solve_time_s > 0
            else float("inf")
        )
        self.early_termination_rate = (
            self.early_terminations / self.configurations_evaluated
            if self.configurations_evaluated > 0
            else 0.0
        )
        self.avg_clauses_per_candidate = (
            self.clause_evaluations / self.configurations_evaluated
            if self.configurations_evaluated > 0
            else 0.0
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

    background_probability: float = 0.0
    """Uniform random probability = 1/2^n (baseline for comparison)."""

    signal_to_noise: float = 0.0
    """Ratio of top result probability to background probability."""

    distribution_entropy: float = 0.0
    """Shannon entropy of the measurement distribution (bits)."""


@dataclass
class StaticCircuitAnalysis:
    """Static quantum circuit properties extracted without simulation.

    Provides gate counts, circuit depth, and two-qubit gate density metrics
    that characterize the circuit's resource requirements without needing
    to run a simulator. This eliminates simulator runtime as a bottleneck
    and gives perfectly reproducible measurements.
    """

    num_qubits: int
    """Total qubits in the Grover circuit (problem + ancilla)."""

    circuit_depth: int
    """Critical-path length (number of gate layers)."""

    total_gate_count: int
    """Total number of gates."""

    two_qubit_gate_count: int
    """Number of 2+-qubit (entangling) gates."""

    gate_counts_by_type: dict[str, int]
    """Per-gate-type breakdown."""

    grover_iterations: int
    """Number of Grover operator applications."""

    problem_qubits: int = 0
    """Number of qubits encoding the problem variables (n×d)."""

    two_qubit_gate_density: float = field(init=False)
    """Fraction of gates that are 2+-qubit entangling gates (0–1)."""

    depth_per_iteration: float = field(init=False)
    """Circuit depth per Grover iteration."""

    gates_per_qubit: float = field(init=False)
    """Average gates per qubit."""

    ancilla_qubits: int = field(init=False)
    """Number of ancilla qubits (total − problem)."""

    ancilla_ratio: float = field(init=False)
    """Fraction of qubits used as ancilla (0–1)."""

    def __post_init__(self) -> None:
        self.two_qubit_gate_density = (
            self.two_qubit_gate_count / self.total_gate_count
            if self.total_gate_count > 0
            else 0.0
        )
        self.depth_per_iteration = (
            self.circuit_depth / self.grover_iterations
            if self.grover_iterations > 0
            else self.circuit_depth
        )
        self.gates_per_qubit = (
            self.total_gate_count / self.num_qubits
            if self.num_qubits > 0
            else 0.0
        )
        self.ancilla_qubits = max(0, self.num_qubits - self.problem_qubits)
        self.ancilla_ratio = (
            self.ancilla_qubits / self.num_qubits
            if self.num_qubits > 0
            else 0.0
        )


@dataclass
class SolutionSpaceMetrics:
    """Characterizes the structure and distribution of solutions in the search space."""

    solutions_found: int
    """Total number of valid solutions."""

    search_space_size: int
    """Total search space (2^n)."""

    solution_density: float = field(init=False)
    """Fraction of search space that is a valid solution."""

    hamming_distances: list[int] = field(default_factory=list)
    """Pairwise Hamming distances between all solution pairs."""

    mean_hamming: float = 0.0
    """Mean inter-solution Hamming distance."""

    min_hamming: int = 0
    """Minimum inter-solution Hamming distance."""

    max_hamming: int = 0
    """Maximum inter-solution Hamming distance."""

    def __post_init__(self) -> None:
        self.solution_density = (
            self.solutions_found / self.search_space_size
            if self.search_space_size > 0
            else 0.0
        )
        if self.hamming_distances:
            self.mean_hamming = sum(self.hamming_distances) / len(self.hamming_distances)
            self.min_hamming = min(self.hamming_distances)
            self.max_hamming = max(self.hamming_distances)


@dataclass
class HardwareRequirements:
    """Estimated hardware requirements for running the circuit on real quantum hardware."""

    circuit_depth: int
    """Circuit depth (gate layers)."""

    total_gate_count: int
    """Total gates in the circuit."""

    estimated_coherence_us: float = field(init=False)
    """Estimated minimum coherence time needed (microseconds), assuming ~50ns/gate."""

    max_gate_error_rate: float = field(init=False)
    """Rough upper bound on tolerable per-gate error rate (1/total_gates)."""

    break_even_search_space: int = 0
    """Search space size where quantum oracle calls < classical constraint checks."""

    def __post_init__(self) -> None:
        gate_time_ns = 50  # typical single-gate time on superconducting hardware
        self.estimated_coherence_us = self.circuit_depth * gate_time_ns / 1000
        self.max_gate_error_rate = (
            1.0 / self.total_gate_count if self.total_gate_count > 0 else 1.0
        )


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

    # --- static analysis (None if not computed) ---
    static_circuit: StaticCircuitAnalysis | None = None

    # --- constraint density (None if not computed) ---
    constraint_density_metrics: dict | None = None

    # --- new metric categories ---
    solution_space: SolutionSpaceMetrics | None = None
    hardware_requirements: HardwareRequirements | None = None

    encoding_time_s: float = 0.0
    """Wall-clock seconds to convert puzzle to boolean expression (SAT encoding overhead)."""

    circuit_construction_time_s: float = 0.0
    """Wall-clock seconds to construct the quantum circuit (before simulation)."""

    confidence_runs_95: float = 0.0
    """Estimated runs needed for 95% probability of finding all solutions."""

    confidence_runs_99: float = 0.0
    """Estimated runs needed for 99% probability of finding all solutions."""

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
# Static circuit analysis
# ---------------------------------------------------------------------------


def analyze_circuit(puzzle: tuple[list, list]) -> StaticCircuitAnalysis:
    """Build the Grover circuit for *puzzle* and extract static metrics.

    This constructs the circuit and measures gate counts, depth, and
    two-qubit gate density without running any simulation. Results are
    perfectly reproducible and free of simulator overhead.

    Parameters
    ----------
    puzzle : tuple[list, list]
        (row_clues, col_clues) tuple.

    Returns
    -------
    StaticCircuitAnalysis
        Circuit properties including gate counts and density metrics.
    """
    from qiskit.circuit.library import PhaseOracleGate
    from qiskit_algorithms import AmplificationProblem, Grover

    expression = puzzle_to_boolean(row_clues=puzzle[0], col_clues=puzzle[1])
    oracle = PhaseOracleGate(expression)
    problem = AmplificationProblem(oracle)

    iterations_used = Grover.optimal_num_iterations(
        num_solutions=1, num_qubits=oracle.num_qubits
    )
    grover = Grover(iterations=iterations_used)
    circuit = grover.construct_circuit(problem, measurement=False)

    ops = circuit.count_ops()
    two_qubit = circuit.num_nonlocal_gates()

    num_problem = len(puzzle[0]) * len(puzzle[1])
    return StaticCircuitAnalysis(
        num_qubits=circuit.num_qubits,
        circuit_depth=circuit.depth(),
        total_gate_count=sum(ops.values()),
        two_qubit_gate_count=two_qubit,
        gate_counts_by_type=dict(ops),
        grover_iterations=iterations_used,
        problem_qubits=num_problem,
    )


# ---------------------------------------------------------------------------
# New metric helpers
# ---------------------------------------------------------------------------


def _hamming_distance(a: str, b: str) -> int:
    """Count differing bits between two equal-length bitstrings."""
    return sum(x != y for x, y in zip(a, b))


def compute_solution_space_metrics(
    solutions: list[str], num_variables: int
) -> SolutionSpaceMetrics:
    """Compute solution space structure from a list of solution bitstrings."""
    search_space = 2**num_variables
    distances = [
        _hamming_distance(a, b) for a, b in combinations(solutions, 2)
    ] if len(solutions) >= 2 else []

    return SolutionSpaceMetrics(
        solutions_found=len(solutions),
        search_space_size=search_space,
        hamming_distances=distances,
    )


def estimate_hardware_requirements(
    static: StaticCircuitAnalysis,
    classical_constraint_checks: int = 0,
) -> HardwareRequirements:
    """Estimate hardware requirements from static circuit analysis."""
    # Break-even: find N where sqrt(N) iterations < classical constraint checks
    break_even = 0
    if classical_constraint_checks > 0 and static.grover_iterations > 0:
        # Grover oracle calls scale as sqrt(N); classical as N
        # Break-even when sqrt(N) = classical_checks → N = classical_checks^2
        break_even = classical_constraint_checks ** 2

    return HardwareRequirements(
        circuit_depth=static.circuit_depth,
        total_gate_count=static.total_gate_count,
        break_even_search_space=break_even,
    )


def compute_confidence_runs(
    num_solutions: int, top_probability: float
) -> tuple[float, float]:
    """Estimate runs needed for 95% and 99% confidence of finding all solutions.

    Uses the coupon collector approximation: E[runs] ≈ n × H_n / p
    where n = number of solutions, H_n = nth harmonic number, p = success probability.
    """
    if num_solutions <= 0 or top_probability <= 0:
        return 0.0, 0.0

    # Harmonic number H_n
    h_n = sum(1.0 / k for k in range(1, num_solutions + 1))
    expected = num_solutions * h_n / top_probability

    # For P(all found) ≥ 1-δ, multiply expected by ln(1/δ) factor
    runs_95 = expected * math.log(1 / 0.05) if num_solutions > 1 else math.log(1 / 0.05) / top_probability
    runs_99 = expected * math.log(1 / 0.01) if num_solutions > 1 else math.log(1 / 0.01) / top_probability

    return runs_95, runs_99


def _distribution_entropy(counts: dict[str, int | float]) -> float:
    """Compute Shannon entropy (in bits) of a probability distribution."""
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    entropy = 0.0
    for v in counts.values():
        p = v / total
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------


def benchmark(
    puzzle: tuple[list, list],
    run_classical: bool = True,
    run_quantum: bool = True,
    static_analysis: bool = True,
    compute_constraint_density: bool = True,
) -> ComparisonReport:
    """Run one or both solvers on *puzzle* and collect comparison metrics.

    Args:
        puzzle: (row_clues, col_clues) tuple.
        run_classical: Whether to run the classical brute-force solver.
            Set False to skip if the puzzle is too large (> ~20 variables).
        run_quantum: Whether to run the quantum Grover solver.
            Requires qiskit and tweedledum.
        static_analysis: Whether to compute static circuit analysis
            (gate counts, depth, density) without running the simulator.
        compute_constraint_density: Whether to compute constraint density
            metrics from the clue structure.

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
    search_space = 2**num_vars

    # Build the boolean expression once — measure encoding time separately
    t_enc = time.perf_counter()
    expression = puzzle_to_boolean(row_clues, col_clues, classical=False)
    encoding_time = time.perf_counter() - t_enc
    expr_len = len(expression)

    classical_metrics: ClassicalMetrics | None = None
    quantum_metrics: QuantumMetrics | None = None
    static_circuit: StaticCircuitAnalysis | None = None
    density_metrics: dict | None = None
    solution_space: SolutionSpaceMetrics | None = None
    hw_reqs: HardwareRequirements | None = None
    circuit_construction_time = 0.0
    conf_95 = 0.0
    conf_99 = 0.0
    classical_solutions_bs: list[str] = []

    # --- Classical ---
    if run_classical:
        from nonogram.classical import classical_solve

        tracemalloc.start()
        t0 = time.perf_counter()
        solutions, exec_counts = classical_solve(puzzle, collect_counts=True)
        elapsed = time.perf_counter() - t0
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        classical_solutions_bs = solutions  # list of bitstrings

        classical_metrics = ClassicalMetrics(
            solve_time_s=elapsed,
            configurations_evaluated=search_space,
            solutions_found=len(solutions),
            peak_memory_kb=peak / 1024,
            clause_evaluations=exec_counts.clause_evaluations,
            subclause_evaluations=exec_counts.subclause_evaluations,
            literal_evaluations=exec_counts.literal_evaluations,
            constraint_checks=exec_counts.constraint_checks,
            early_terminations=exec_counts.early_terminations,
        )

    # --- Quantum ---
    if run_quantum:
        from qiskit.circuit.library import PhaseOracleGate
        from qiskit.primitives import StatevectorSampler
        from qiskit_algorithms import AmplificationProblem, Grover

        # Measure circuit construction time separately
        t_circ = time.perf_counter()
        oracle = PhaseOracleGate(expression)
        problem = AmplificationProblem(oracle)
        grover = Grover(sampler=StatevectorSampler())

        iterations_used = Grover.optimal_num_iterations(
            num_solutions=1, num_qubits=oracle.num_qubits
        )
        circuit = grover.construct_circuit(problem, power=iterations_used, measurement=False)
        circuit_construction_time = time.perf_counter() - t_circ

        ops = circuit.count_ops()
        two_qubit = circuit.num_nonlocal_gates()

        tracemalloc.start()
        t0 = time.perf_counter()
        result = grover.amplify(problem)
        elapsed = time.perf_counter() - t0
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        top_counts = result.circuit_results[0]
        total_counts = sum(top_counts.values())
        top_prob = max(top_counts.values()) / total_counts if total_counts else 0
        top_bitstring = max(top_counts, key=top_counts.__getitem__)
        bool_expr = oracle.boolean_expression
        oracle_correct = bool_expr.simulate(top_bitstring[::-1])
        valid_solutions = sum(1 for bs in top_counts if bool_expr.simulate(bs[::-1]))

        # Probability distribution statistics
        background_prob = 1.0 / search_space if search_space > 0 else 0
        snr = top_prob / background_prob if background_prob > 0 else 0
        entropy = _distribution_entropy(top_counts)

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
            background_probability=background_prob,
            signal_to_noise=snr,
            distribution_entropy=entropy,
        )

        # Confidence runs estimation
        if valid_solutions > 0 and top_prob > 0:
            conf_95, conf_99 = compute_confidence_runs(valid_solutions, top_prob)

    # --- Static circuit analysis ---
    if static_analysis:
        static_circuit = analyze_circuit(puzzle)

    # --- Constraint density ---
    if compute_constraint_density:
        from nonogram.data import constraint_density

        density_metrics = constraint_density(row_clues, col_clues)

    # --- Solution space metrics ---
    if classical_solutions_bs:
        solution_space = compute_solution_space_metrics(classical_solutions_bs, num_vars)

    # --- Hardware requirements ---
    if static_circuit:
        cl_checks = classical_metrics.constraint_checks if classical_metrics else 0
        hw_reqs = estimate_hardware_requirements(static_circuit, cl_checks)

    return ComparisonReport(
        rows=n,
        cols=d,
        num_variables=num_vars,
        search_space_size=search_space,
        boolean_expression_length=expr_len,
        classical=classical_metrics,
        quantum=quantum_metrics,
        static_circuit=static_circuit,
        constraint_density_metrics=density_metrics,
        solution_space=solution_space,
        hardware_requirements=hw_reqs,
        encoding_time_s=encoding_time,
        circuit_construction_time_s=circuit_construction_time,
        confidence_runs_95=conf_95,
        confidence_runs_99=conf_99,
    )


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------


def print_report(report: ComparisonReport) -> None:
    """Print a formatted side-by-side comparison of the benchmark results."""
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
    print(
        row(
            "Solve time (s)",
            fmt(c and c.solve_time_s, ".4f", " s"),
            fmt(q and q.solve_time_s, ".4f", " s"),
        )
    )
    print(
        row(
            "Peak memory (KB)",
            fmt(c and c.peak_memory_kb, ",.1f", " KB"),
            fmt(q and q.peak_memory_kb, ",.1f", " KB"),
        )
    )
    print(
        row("Solutions found", fmt(c and c.solutions_found, "d"), fmt(q and q.solutions_found, "d"))
    )

    # Classical-specific
    print(row("Configs evaluated", fmt(c and c.configurations_evaluated, ",d"), "N/A"))
    print(row("Throughput (configs/s)", fmt(c and c.configs_per_second, ",.0f"), "N/A"))

    # Classical execution counts
    if c and c.clause_evaluations > 0:
        print(row("Clause evaluations", f"{c.clause_evaluations:,}", "N/A"))
        print(row("Subclause evaluations", f"{c.subclause_evaluations:,}", "N/A"))
        print(row("Literal evaluations", f"{c.literal_evaluations:,}", "N/A"))
        print(row("Early terminations", f"{c.early_terminations:,}", "N/A"))

    # Quantum-specific
    print(row("Qubits", "N/A", fmt(q and q.num_qubits, "d")))
    print(row("Circuit depth", "N/A", fmt(q and q.circuit_depth, ",d")))
    print(row("Total gates", "N/A", fmt(q and q.total_gate_count, ",d")))
    print(row("2-qubit (entangling) gates", "N/A", fmt(q and q.two_qubit_gate_count, ",d")))
    print(row("Grover iterations", "N/A", fmt(q and q.grover_iterations, "d")))
    print(row("Top-state probability", "N/A", fmt(q and q.top_result_probability, ".2%")))
    print(
        row(
            "Oracle validation",
            "N/A",
            "correct" if q and q.oracle_evaluation_correct else ("wrong" if q else "—"),
        )
    )

    if q and q.gate_counts_by_type:
        top_gates = sorted(q.gate_counts_by_type.items(), key=lambda x: -x[1])[:5]
        gate_str = "  ".join(f"{g}:{n}" for g, n in top_gates)
        print(row("Top gate types", "N/A", gate_str[:W]))

    # Static circuit analysis
    sc = report.static_circuit
    if sc:
        print(section("Static Circuit Analysis"))
        print(row("Qubits", "", str(sc.num_qubits)))
        print(row("Circuit depth", "", f"{sc.circuit_depth:,}"))
        print(row("Total gates", "", f"{sc.total_gate_count:,}"))
        print(row("2-qubit gates", "", f"{sc.two_qubit_gate_count:,}"))
        print(row("2-qubit gate density", "", f"{sc.two_qubit_gate_density:.2%}"))
        print(row("Depth per iteration", "", f"{sc.depth_per_iteration:,.1f}"))
        print(row("Gates per qubit", "", f"{sc.gates_per_qubit:,.1f}"))
        print(row("Grover iterations", "", str(sc.grover_iterations)))

    # Constraint density
    cd = report.constraint_density_metrics
    if cd:
        print(section("Constraint Density"))
        print(row("Row configs", str(cd["row_configs"]), ""))
        print(row("Col configs", str(cd["col_configs"]), ""))
        print(row("Total configs", f"{cd['total_configs']:,}", ""))
        print(row("Mean configs/line", f"{cd['mean_configs']:.1f}", ""))
        print(row("Min configs", str(cd["min_configs"]), ""))
        print(row("Max configs", str(cd["max_configs"]), ""))
        print(row("Density ratio", f"{cd['density_ratio']:.4f}", ""))

    # Comparison
    if c and q:
        print(section("Comparison"))
        print(
            row(
                "Theoretical Grover speedup",
                f"sqrt({report.search_space_size:,})",
                f"~{report.theoretical_grover_speedup:,.0f}x",
            )
        )
        print(row("Actual speedup", f"{report.actual_speedup:,.1f}x", ""))
        print(
            row("Advantage ratio (actual/theoretical)", f"{report.quantum_advantage_ratio:.3f}", "")
        )
        classical_oracle = c.configurations_evaluated
        grover_oracle = report.quantum.grover_iterations if q else 0
        print(row("Classical oracle calls", f"{classical_oracle:,}", ""))
        print(row("Quantum oracle calls (est.)", "", f"{grover_oracle:,}"))
        reduction = (1 - grover_oracle / classical_oracle) * 100 if classical_oracle else 0
        print(row("Oracle call reduction", "", f"{reduction:.1f}%"))

        # Execution count comparison
        if c.constraint_checks > 0:
            print(row("Classical constraint checks", f"{c.constraint_checks:,}", ""))
            print(row("Quantum oracle calls", "", f"{grover_oracle:,}"))
            check_reduction = (
                (1 - grover_oracle / c.constraint_checks) * 100
                if c.constraint_checks
                else 0
            )
            print(row("Constraint check reduction", "", f"{check_reduction:.1f}%"))

    print(f"\n{'═' * 64}\n")
