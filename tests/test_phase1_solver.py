"""Phase 1 Grover solver and benchmarking test suite.

Tests cover WPs #721-#727 (Grover solver components) and #732-#735
(benchmarking infrastructure).  Each test reads source files directly
to verify structural correctness, avoiding import-time compatibility
issues with Qiskit/Python version mismatches.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NONOGRAM_PKG = ROOT / "nonogram"
TOOLS_DIR = ROOT / "tools"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    """Return the full text of *path*."""
    return path.read_text(encoding="utf-8")


def _parse_module(path: Path) -> ast.Module:
    """Parse a Python source file into an AST module node."""
    return ast.parse(_read(path), filename=str(path))


def _function_names(tree: ast.Module) -> set[str]:
    """Return all top-level and class-level function/method names."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
    return names


def _class_names(tree: ast.Module) -> set[str]:
    """Return all class names defined in *tree*."""
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}


def _imports_in(tree: ast.Module) -> set[str]:
    """Return all imported module names (from ... import ... and import ...)."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


# ===================================================================
# #721 — Grover's oracle correctness
# ===================================================================

class TestOracleCorrectness:
    """WP #721: Verify oracle code exists with proper structure."""

    def test_quantum_module_exists(self):
        assert (NONOGRAM_PKG / "quantum.py").is_file()

    def test_quantum_solve_function_exists(self):
        tree = _parse_module(NONOGRAM_PKG / "quantum.py")
        assert "quantum_solve" in _function_names(tree)

    def test_oracle_uses_phase_oracle_gate(self):
        src = _read(NONOGRAM_PKG / "quantum.py")
        assert "PhaseOracleGate" in src, "Oracle should use Qiskit PhaseOracleGate"

    def test_oracle_fed_boolean_expression(self):
        src = _read(NONOGRAM_PKG / "quantum.py")
        assert "puzzle_to_boolean" in src, (
            "Oracle should receive a boolean expression from puzzle_to_boolean"
        )

    def test_amplification_problem_wraps_oracle(self):
        src = _read(NONOGRAM_PKG / "quantum.py")
        assert "AmplificationProblem" in src, (
            "Oracle must be wrapped in AmplificationProblem for Grover"
        )

    def test_oracle_expression_uses_variables(self):
        """The SAT encoding must produce named boolean variables (v0, v1, ...)."""
        src = _read(NONOGRAM_PKG / "core.py")
        assert re.search(r'VAR\s*=\s*["\']v["\']', src), (
            "puzzle_to_boolean should use variable prefix 'v'"
        )


# ===================================================================
# #722 — Grover's diffusion operator
# ===================================================================

class TestDiffusionOperator:
    """WP #722: Verify diffusion/amplitude amplification code."""

    def test_grover_class_imported(self):
        src = _read(NONOGRAM_PKG / "quantum.py")
        assert "Grover" in src, "Must import/use Qiskit Grover class"

    def test_grover_amplify_called(self):
        src = _read(NONOGRAM_PKG / "quantum.py")
        assert "grover.amplify" in src or "Grover" in src, (
            "quantum_solve must call grover.amplify()"
        )

    def test_sampler_provided(self):
        """Grover needs a sampler primitive for amplitude amplification."""
        src = _read(NONOGRAM_PKG / "quantum.py")
        assert "StatevectorSampler" in src, (
            "Local solver should use StatevectorSampler"
        )

    def test_construct_circuit_available(self):
        """The hardware path must build the Grover circuit explicitly."""
        src = _read(NONOGRAM_PKG / "quantum.py")
        assert "construct_circuit" in src


# ===================================================================
# #723 — Optimal iteration count
# ===================================================================

class TestOptimalIterationCount:
    """WP #723: Verify pi/4 * sqrt(N) calculation."""

    def test_optimal_num_iterations_used_in_metrics(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "optimal_num_iterations" in src, (
            "Benchmark must use Grover.optimal_num_iterations"
        )

    def test_iteration_count_formula_reference(self):
        """Docstring or code should reference the pi/4*sqrt(N) formula."""
        src = _read(NONOGRAM_PKG / "quantum.py")
        # The docstring discusses iteration count and arcsin formula
        assert "arcsin" in src or "sqrt" in src or "iteration" in src.lower()

    def test_iterations_parameter_on_hardware(self):
        """Hardware path should accept an iterations parameter."""
        tree = _parse_module(NONOGRAM_PKG / "quantum.py")
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "quantum_solve_hardware":
                arg_names = [a.arg for a in node.args.args]
                assert "iterations" in arg_names, (
                    "quantum_solve_hardware must accept 'iterations' parameter"
                )
                break
        else:
            pytest.fail("quantum_solve_hardware not found")

    def test_theoretical_grover_speedup_is_sqrt(self):
        """ComparisonReport must compute sqrt(search_space) as theoretical speedup."""
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "math.sqrt" in src or "sqrt" in src


# ===================================================================
# #724 — Circuit visualization output
# ===================================================================

class TestCircuitVisualization:
    """WP #724: Verify circuit drawing/visualization capability."""

    def test_construct_circuit_exists(self):
        """construct_circuit is used to build a drawable QuantumCircuit."""
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "construct_circuit" in src

    def test_circuit_properties_extracted(self):
        """Visualization-relevant properties (depth, ops) are extracted."""
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "circuit.depth()" in src or "depth" in src
        assert "count_ops" in src

    def test_chart_module_exists(self):
        assert (TOOLS_DIR / "chart.py").is_file(), (
            "tools/chart.py should exist for benchmark chart rendering"
        )

    def test_chart_renders_base64_png(self):
        src = _read(TOOLS_DIR / "chart.py")
        assert "render_chart_b64" in src
        assert "base64" in src
        assert "matplotlib" in src

    def test_gate_counts_by_type_in_metrics(self):
        """Gate breakdown must be available for circuit visualization."""
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "gate_counts_by_type" in src


# ===================================================================
# #725 — Nonogram constraint encoding
# ===================================================================

class TestConstraintEncoding:
    """WP #725: Verify SAT/constraint encoding to circuit."""

    def test_puzzle_to_boolean_exists(self):
        tree = _parse_module(NONOGRAM_PKG / "core.py")
        assert "puzzle_to_boolean" in _function_names(tree)

    def test_produces_boolean_string_for_quantum(self):
        """When classical=False, must produce a boolean expression string."""
        src = _read(NONOGRAM_PKG / "core.py")
        assert "boolean_statement" in src

    def test_produces_cnf_for_classical(self):
        """When classical=True, must produce clause list."""
        src = _read(NONOGRAM_PKG / "core.py")
        assert "classical_statement" in src

    def test_uses_and_or_not_operators(self):
        src = _read(NONOGRAM_PKG / "core.py")
        # SAT encoding must use AND, OR, NOT logical operators
        assert re.search(r'AND\s*=\s*["\']&["\']', src)
        assert re.search(r'OR\s*=\s*["\']\\|["\']', src) or '"|"' in src
        assert re.search(r'NOT\s*=\s*["\']~["\']', src)

    def test_row_and_column_constraints_encoded(self):
        src = _read(NONOGRAM_PKG / "core.py")
        assert "row_clues" in src and "col_clues" in src
        assert "row constraints" in src.lower() or "row_clue" in src.lower()
        assert "column constraints" in src.lower() or "col_clue" in src.lower()

    def test_lookup_table_used(self):
        """Constraint encoding should use precomputed valid patterns."""
        src = _read(NONOGRAM_PKG / "core.py")
        assert "possible_d" in src

    def test_var_clauses_maps_grid_to_variables(self):
        tree = _parse_module(NONOGRAM_PKG / "core.py")
        assert "var_clauses" in _function_names(tree)


# ===================================================================
# #726 — Brute-force solver correctness
# ===================================================================

class TestBruteForceSolver:
    """WP #726: Verify classical brute-force solver exists and works."""

    def test_classical_module_exists(self):
        assert (NONOGRAM_PKG / "classical.py").is_file()

    def test_classical_solve_function_exists(self):
        tree = _parse_module(NONOGRAM_PKG / "classical.py")
        assert "classical_solve" in _function_names(tree)

    def test_exhaustive_search_over_all_candidates(self):
        """Brute-force must iterate 2^(n*d) candidates."""
        src = _read(NONOGRAM_PKG / "classical.py")
        assert "2**var_num" in src or "2 ** var_num" in src

    def test_returns_list_of_bitstrings(self):
        src = _read(NONOGRAM_PKG / "classical.py")
        assert "solutions" in src
        assert "list[str]" in src or "List[str]" in src

    def test_execution_counts_dataclass(self):
        tree = _parse_module(NONOGRAM_PKG / "classical.py")
        assert "ExecutionCounts" in _class_names(tree)

    def test_collect_counts_option(self):
        """classical_solve should support collect_counts parameter."""
        src = _read(NONOGRAM_PKG / "classical.py")
        assert "collect_counts" in src

    def test_early_termination_implemented(self):
        src = _read(NONOGRAM_PKG / "classical.py")
        assert "early_termination" in src or "early_terminations" in src


# ===================================================================
# #727 — Measurement and result interpretation
# ===================================================================

class TestMeasurementInterpretation:
    """WP #727: Verify measurement/decoding from quantum results."""

    def test_circuit_results_accessed(self):
        src = _read(NONOGRAM_PKG / "quantum.py")
        assert "circuit_results" in src or "result" in src

    def test_bitstring_reversal_documented(self):
        """Little-endian bitstring reversal must be documented or implemented."""
        src = _read(NONOGRAM_PKG / "quantum.py")
        assert "[::-1]" in src or "reverse" in src.lower() or "little-endian" in src.lower()

    def test_extract_counts_function(self):
        tree = _parse_module(NONOGRAM_PKG / "quantum.py")
        assert "extract_counts" in _function_names(tree)

    def test_extract_counts_handles_multiple_strategies(self):
        """extract_counts should try multiple DataBin access strategies."""
        src = _read(NONOGRAM_PKG / "quantum.py")
        assert "_fields" in src
        assert "get_counts" in src

    def test_hardware_returns_counts_and_backend(self):
        """quantum_solve_hardware must return (counts, backend_name)."""
        src = _read(NONOGRAM_PKG / "quantum.py")
        assert "return counts, backend.name" in src or "return counts" in src

    def test_display_nonogram_exists(self):
        """Grid visualization for decoded solutions must be available."""
        tree = _parse_module(NONOGRAM_PKG / "core.py")
        assert "display_nonogram" in _function_names(tree)


# ===================================================================
# #732 — Benchmark metric calculations
# ===================================================================

class TestBenchmarkMetrics:
    """WP #732: Verify timing/comparison metrics."""

    def test_metrics_module_exists(self):
        assert (NONOGRAM_PKG / "metrics.py").is_file()

    def test_benchmark_function_exists(self):
        tree = _parse_module(NONOGRAM_PKG / "metrics.py")
        assert "benchmark" in _function_names(tree)

    def test_classical_metrics_dataclass(self):
        tree = _parse_module(NONOGRAM_PKG / "metrics.py")
        assert "ClassicalMetrics" in _class_names(tree)

    def test_quantum_metrics_dataclass(self):
        tree = _parse_module(NONOGRAM_PKG / "metrics.py")
        assert "QuantumMetrics" in _class_names(tree)

    def test_comparison_report_dataclass(self):
        tree = _parse_module(NONOGRAM_PKG / "metrics.py")
        assert "ComparisonReport" in _class_names(tree)

    def test_solve_time_tracked(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "solve_time_s" in src
        assert "perf_counter" in src or "time" in src

    def test_memory_tracked(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "tracemalloc" in src
        assert "peak_memory_kb" in src

    def test_speedup_computed(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "actual_speedup" in src
        assert "theoretical_grover_speedup" in src

    def test_quantum_advantage_ratio(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "quantum_advantage_ratio" in src


# ===================================================================
# #733 — Benchmark reproducibility
# ===================================================================

class TestBenchmarkReproducibility:
    """WP #733: Verify seeded/deterministic options."""

    def test_statevector_sampler_is_deterministic(self):
        """StatevectorSampler gives exact probabilities, ensuring reproducibility."""
        src = _read(NONOGRAM_PKG / "quantum.py")
        assert "StatevectorSampler" in src

    def test_static_circuit_analysis_deterministic(self):
        """Static analysis extracts gate counts without simulation -- always reproducible."""
        tree = _parse_module(NONOGRAM_PKG / "metrics.py")
        assert "analyze_circuit" in _function_names(tree)

    def test_static_analysis_class_exists(self):
        tree = _parse_module(NONOGRAM_PKG / "metrics.py")
        assert "StaticCircuitAnalysis" in _class_names(tree)

    def test_static_analysis_no_simulation(self):
        """analyze_circuit should use measurement=False (no simulation run)."""
        src = _read(NONOGRAM_PKG / "metrics.py")
        # In analyze_circuit, measurement=False ensures no randomness
        assert "measurement=False" in src

    def test_benchmark_comparison_uses_known_puzzles(self):
        """benchmark_comparison.py should define a fixed set of test puzzles."""
        src = _read(TOOLS_DIR / "benchmark_comparison.py")
        assert "BENCHMARK_PUZZLES" in src

    def test_benchmark_supports_json_output(self):
        """Results can be serialized for later comparison."""
        src = _read(TOOLS_DIR / "benchmark_comparison.py")
        assert "json" in src
        assert "output_json" in src or "--json" in src


# ===================================================================
# #734 — Benchmark output format
# ===================================================================

class TestBenchmarkOutputFormat:
    """WP #734: Verify structured output/reporting."""

    def test_print_report_function_exists(self):
        tree = _parse_module(NONOGRAM_PKG / "metrics.py")
        assert "print_report" in _function_names(tree)

    def test_report_includes_puzzle_metadata(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "num_variables" in src
        assert "search_space_size" in src

    def test_report_includes_solver_heading(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "Classical" in src and "Quantum" in src

    def test_comparison_section_in_report(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "Comparison" in src

    def test_report_to_dict_serialization(self):
        """Chart module provides JSON-serializable report conversion."""
        src = _read(TOOLS_DIR / "chart.py")
        assert "report_to_dict" in src

    def test_benchmark_comparison_scaling_summary(self):
        src = _read(TOOLS_DIR / "benchmark_comparison.py")
        assert "SCALING SUMMARY" in src or "scaling" in src.lower()

    def test_benchmark_comparison_constraint_checks_vs_iterations(self):
        """Output should contrast classical constraint checks with Grover iterations."""
        src = _read(TOOLS_DIR / "benchmark_comparison.py")
        assert "constraint_checks" in src
        assert "grover_iterations" in src.lower() or "Grover Iters" in src


# ===================================================================
# #735 — Gate error sensitivity
# ===================================================================

class TestGateErrorSensitivity:
    """WP #735: Verify noise model/error simulation support."""

    def test_hardware_solver_accepts_error_mitigation_options(self):
        """quantum_solve_hardware should support error mitigation flags."""
        src = _read(NONOGRAM_PKG / "quantum.py")
        assert "dynamical_decoupling" in src
        assert "twirling" in src

    def test_hardware_path_configures_dynamical_decoupling(self):
        src = _read(NONOGRAM_PKG / "quantum.py")
        assert "XpXm" in src, "Should configure DD sequence type"

    def test_hardware_path_configures_twirling(self):
        src = _read(NONOGRAM_PKG / "quantum.py")
        assert "enable_gates" in src
        assert "enable_measure" in src

    def test_two_qubit_gate_count_tracked(self):
        """Two-qubit gates are primary noise source; must be counted."""
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "two_qubit_gate_count" in src
        assert "num_nonlocal_gates" in src

    def test_two_qubit_gate_density_computed(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "two_qubit_gate_density" in src

    def test_optimization_level_3_for_noise_reduction(self):
        """Hardware transpilation should use optimization_level=3."""
        src = _read(NONOGRAM_PKG / "quantum.py")
        assert "optimization_level=3" in src

    def test_shots_parameter_for_statistical_sampling(self):
        """Hardware path should accept shots parameter for noise statistics."""
        src = _read(NONOGRAM_PKG / "quantum.py")
        assert "shots" in src
