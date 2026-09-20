"""Tests for the full benchmarking harness comparing Grover vs classical brute-force.

These tests validate the integrated benchmark pipeline including execution counts,
static circuit analysis, and constraint density metrics.
"""

import json

from nonogram.metrics import (
    StaticCircuitAnalysis,
    benchmark,
    print_report,
)

SMALL_PUZZLE = ([(1,), (1,)], [(1,), (1,)])  # 2x2


class TestBenchmarkWithExecutionCounts:
    def test_classical_execution_counts_populated(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        assert result.classical is not None
        assert result.classical.clause_evaluations > 0
        assert result.classical.literal_evaluations > 0

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

    def test_static_analysis_present_by_default(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        assert result.static_circuit is not None

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

    def test_constraint_density_present_by_default(self):
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        assert result.constraint_density_metrics is not None

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
        """Early termination means fewer clause checks than candidates x clauses."""
        result = benchmark(SMALL_PUZZLE, run_classical=True, run_quantum=False)
        clauses = len(SMALL_PUZZLE[0]) + len(SMALL_PUZZLE[1])
        ceiling = result.classical.configurations_evaluated * clauses
        assert 0 < result.classical.clause_evaluations < ceiling

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


class TestBenchmarkCLI:
    """tools/benchmark_comparison.py is a CLI nothing imports, so it needs a smoke test."""

    def test_small_run_produces_rows(self, capsys, tmp_path):
        from tools.benchmark_comparison import run_comparison

        out = tmp_path / "results.json"
        results = run_comparison(max_size=2, run_quantum=False, output_json=str(out))

        assert [r["name"] for r in results] == ["1x1", "2x2"]
        assert results[-1]["classical"]["configurations_evaluated"] == 16
        assert json.loads(out.read_text()) == json.loads(json.dumps(results, default=str))
        assert "SCALING SUMMARY" in capsys.readouterr().out

    def test_intractable_sizes_are_skipped(self, capsys):
        from tools.benchmark_comparison import _MAX_VARIABLES, run_comparison

        results = run_comparison(max_size=5, run_quantum=False)
        assert all(r["num_variables"] <= _MAX_VARIABLES for r in results)
        assert "above the" in capsys.readouterr().out
