"""Tests for the full benchmarking harness comparing Grover vs classical brute-force.

These tests validate the integrated benchmark pipeline including execution counts,
static circuit analysis, and constraint density metrics.
"""

import math

import pytest

from nonogram.metrics import (
    ClassicalMetrics,
    ComparisonReport,
    StaticCircuitAnalysis,
    benchmark,
    print_report,
)


SMALL_PUZZLE = ([(1,), (1,)], [(1,), (1,)])  # 2x2
MEDIUM_PUZZLE = ([(1,), (1,), (0,)], [(1,), (1,), (0,)])  # 3x3


class TestBenchmarkWithExecutionCounts:
    def test_classical_execution_counts_populated(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        assert result.classical is not None
        assert result.classical.clause_evaluations > 0
        assert result.classical.literal_evaluations > 0
        assert result.classical.constraint_checks > 0

    def test_early_terminations_tracked(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        assert result.classical.early_terminations > 0


class TestBenchmarkWithStaticAnalysis:
    def test_static_analysis_present(self):
        result = benchmark(
            SMALL_PUZZLE,
            run_classical=False,
            run_quantum=False,
            static_analysis=True,
        )
        assert result.static_circuit is not None
        assert isinstance(result.static_circuit, StaticCircuitAnalysis)

    def test_static_analysis_absent_by_default(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        assert result.static_circuit is None

    def test_static_analysis_has_metrics(self):
        result = benchmark(
            SMALL_PUZZLE,
            run_classical=False,
            run_quantum=False,
            static_analysis=True,
        )
        sc = result.static_circuit
        assert sc.num_qubits > 0
        assert sc.circuit_depth > 0
        assert sc.total_gate_count > 0
        assert 0.0 <= sc.two_qubit_gate_density <= 1.0


class TestBenchmarkWithConstraintDensity:
    def test_constraint_density_present(self):
        result = benchmark(
            SMALL_PUZZLE,
            run_classical=False,
            run_quantum=False,
            compute_constraint_density=True,
        )
        assert result.constraint_density_metrics is not None

    def test_constraint_density_absent_by_default(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        assert result.constraint_density_metrics is None

    def test_constraint_density_has_expected_keys(self):
        result = benchmark(
            SMALL_PUZZLE,
            run_classical=False,
            run_quantum=False,
            compute_constraint_density=True,
        )
        cd = result.constraint_density_metrics
        assert "row_configs" in cd
        assert "col_configs" in cd
        assert "total_configs" in cd
        assert "mean_configs" in cd
        assert "search_space" in cd


class TestFullBenchmarkPipeline:
    def test_all_features_together(self):
        result = benchmark(
            SMALL_PUZZLE,
            run_classical=True,
            run_quantum=True,
            static_analysis=True,
            compute_constraint_density=True,
        )
        assert result.classical is not None
        assert result.quantum is not None
        assert result.static_circuit is not None
        assert result.constraint_density_metrics is not None

    def test_classical_constraint_checks_consistent(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        # Constraint checks should be less than or equal to
        # candidates * total_clauses (since early termination occurs)
        assert result.classical.constraint_checks <= (
            result.classical.configurations_evaluated * 100
        )

    def test_print_report_with_all_sections(self):
        import io
        import sys

        result = benchmark(
            SMALL_PUZZLE,
            run_classical=True,
            run_quantum=True,
            static_analysis=True,
            compute_constraint_density=True,
        )
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            print_report(result)
        finally:
            sys.stdout = old
        output = buf.getvalue()
        assert "Static Circuit Analysis" in output
        assert "Constraint Density" in output
        assert "Clause evaluations" in output
