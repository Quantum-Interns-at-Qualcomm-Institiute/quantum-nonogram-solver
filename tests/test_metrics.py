"""Tests for nonogram.metrics.

The quantum solver requires qiskit + tweedledum, so quantum-path tests are
guarded with a skipif marker.  All structural / math tests run without any
quantum dependencies.
"""

import io
import math
import sys

import pytest

from nonogram.metrics import (
    ClassicalMetrics,
    ComparisonReport,
    QuantumMetrics,
    benchmark,
    print_report,
)

# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

SMALL_PUZZLE = ([(1,), (1,)], [(1,), (1,)])  # 2×2, 4 variables
SMALL_SOLUTION = "1001"


def _make_classical() -> ClassicalMetrics:
    return ClassicalMetrics(
        solve_time_s=2.0,
        configurations_evaluated=16,
        solutions_found=2,
        peak_memory_kb=128.0,
    )


def _make_quantum() -> QuantumMetrics:
    return QuantumMetrics(
        solve_time_s=0.5,
        num_qubits=10,
        circuit_depth=250,
        total_gate_count=500,
        two_qubit_gate_count=120,
        gate_counts_by_type={"cx": 120, "h": 80, "t": 200, "tdg": 100},
        grover_iterations=3,
        top_result_probability=0.85,
        oracle_evaluation_correct=True,
        solutions_found=2,
        peak_memory_kb=256.0,
    )


# ---------------------------------------------------------------------------
# ClassicalMetrics
# ---------------------------------------------------------------------------


class TestClassicalMetrics:
    def test_configs_per_second_computed(self):
        cm = _make_classical()
        assert cm.configs_per_second == pytest.approx(16 / 2.0)

    def test_zero_time_gives_inf(self):
        cm = ClassicalMetrics(
            solve_time_s=0.0,
            configurations_evaluated=100,
            solutions_found=1,
            peak_memory_kb=0.0,
        )
        assert math.isinf(cm.configs_per_second)


# ---------------------------------------------------------------------------
# ComparisonReport derived fields
# ---------------------------------------------------------------------------


class TestComparisonReport:
    def _report(self, c=None, q=None, n_vars=4):
        search_space = 2**n_vars
        return ComparisonReport(
            rows=2,
            cols=2,
            num_variables=n_vars,
            search_space_size=search_space,
            boolean_expression_length=200,
            classical=c,
            quantum=q,
        )

    def test_theoretical_speedup_is_sqrt_search_space(self):
        r = self._report(n_vars=4)
        assert r.theoretical_grover_speedup == pytest.approx(math.sqrt(16))

    def test_actual_speedup_computed_correctly(self):
        c = _make_classical()  # 2.0 s
        q = _make_quantum()  # 0.5 s
        r = self._report(c=c, q=q)
        assert r.actual_speedup == pytest.approx(4.0)

    def test_actual_speedup_zero_when_only_classical(self):
        r = self._report(c=_make_classical())
        assert r.actual_speedup == 0.0

    def test_actual_speedup_zero_when_only_quantum(self):
        r = self._report(q=_make_quantum())
        assert r.actual_speedup == 0.0

    def test_quantum_advantage_ratio(self):
        c = _make_classical()  # 2.0 s
        q = _make_quantum()  # 0.5 s  → actual_speedup = 4.0
        r = self._report(c=c, q=q, n_vars=4)
        # theoretical = sqrt(16) = 4.0 → ratio = 4.0/4.0 = 1.0
        assert r.quantum_advantage_ratio == pytest.approx(1.0)

    def test_large_search_space_theoretical_speedup(self):
        r = self._report(n_vars=24)
        assert r.theoretical_grover_speedup == pytest.approx(math.sqrt(2**24))


# ---------------------------------------------------------------------------
# benchmark() — classical-only path (fast, no qiskit)
# ---------------------------------------------------------------------------


class TestBenchmarkClassicalOnly:
    def test_returns_comparison_report(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        assert isinstance(result, ComparisonReport)

    def test_classical_metrics_populated(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        assert result.classical is not None
        assert isinstance(result.classical, ClassicalMetrics)

    def test_quantum_metrics_absent(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        assert result.quantum is None

    def test_search_space_correct(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        assert result.search_space_size == 2**4  # 2×2 puzzle

    def test_solutions_found(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        assert result.classical.solutions_found == 2  # 1001 and 0110

    def test_configurations_evaluated(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        assert result.classical.configurations_evaluated == 16

    def test_solve_time_positive(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        assert result.classical.solve_time_s > 0

    def test_peak_memory_positive(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        assert result.classical.peak_memory_kb > 0

    def test_neither_solver_runs(self):
        result = benchmark(SMALL_PUZZLE, run_classical=False, run_quantum=False)
        assert result.classical is None
        assert result.quantum is None


# ---------------------------------------------------------------------------
# print_report() — output structure tests (no quantum needed)
# ---------------------------------------------------------------------------


class TestPrintReport:
    def _capture_report(self, report: ComparisonReport) -> str:
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            print_report(report)
        finally:
            sys.stdout = old
        return buf.getvalue()

    def test_output_contains_puzzle_dimensions(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        output = self._capture_report(result)
        assert "2×2" in output

    def test_output_contains_search_space(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        output = self._capture_report(result)
        assert "16" in output  # search space = 2^4

    def test_output_contains_solve_time(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        output = self._capture_report(result)
        assert "Solve time" in output

    def test_output_contains_theoretical_speedup(self):
        c = _make_classical()
        q = _make_quantum()
        report = ComparisonReport(
            rows=2,
            cols=2,
            num_variables=4,
            search_space_size=16,
            boolean_expression_length=100,
            classical=c,
            quantum=q,
        )
        output = self._capture_report(report)
        assert "Theoretical Grover speedup" in output

    def test_output_shows_dash_for_missing_quantum(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        output = self._capture_report(result)
        assert "—" in output
