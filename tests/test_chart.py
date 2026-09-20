"""Tests for tools.chart — report serialization and chart rendering."""

import base64

import pytest

from nonogram.metrics import ClassicalMetrics, ComparisonReport, QuantumMetrics
from tools.chart import (
    measurement_rows,
    render_chart_b64,
    render_histogram_b64,
    report_to_dict,
)


def _make_report(include_classical=True, include_quantum=True):
    """Create a ComparisonReport for testing."""
    cl = (
        ClassicalMetrics(
            solve_time_s=0.001,
            configurations_evaluated=16,
            solutions_found=1,
            peak_memory_kb=10.0,
        )
        if include_classical
        else None
    )
    qu = (
        QuantumMetrics(
            solve_time_s=0.5,
            num_qubits=8,
            circuit_depth=100,
            total_gate_count=500,
            two_qubit_gate_count=200,
            gate_counts_by_type={"cx": 200, "h": 100, "t": 200},
            grover_iterations=3,
            top_result_probability=0.85,
            oracle_evaluation_correct=True,
            solutions_found=1,
            peak_memory_kb=50.0,
        )
        if include_quantum
        else None
    )
    return ComparisonReport(
        rows=2,
        cols=2,
        num_variables=4,
        search_space_size=16,
        boolean_expression_length=100,
        classical=cl,
        quantum=qu,
    )


class TestReportToDict:
    def test_full_report(self):
        report = _make_report()
        d = report_to_dict(report)
        assert d["num_variables"] == 4
        assert d["search_space_size"] == 16
        assert d["classical"]["solve_time_s"] == 0.001
        assert d["quantum"]["num_qubits"] == 8

    def test_classical_only(self):
        report = _make_report(include_quantum=False)
        d = report_to_dict(report)
        assert d["classical"] is not None
        assert d["quantum"] is None

    def test_quantum_only(self):
        report = _make_report(include_classical=False)
        d = report_to_dict(report)
        assert d["classical"] is None
        assert d["quantum"] is not None

    def test_all_keys_present(self):
        report = _make_report()
        d = report_to_dict(report)
        expected_keys = {
            "num_variables",
            "search_space_size",
            "boolean_expression_length",
            "theoretical_grover_speedup",
            "actual_speedup",
            "quantum_advantage_ratio",
            "encoding_time_s",
            "circuit_construction_time_s",
            "confidence_runs_95",
            "confidence_runs_99",
            "classical",
            "quantum",
            "static_circuit",
            "constraint_density",
            "solution_space",
            "hardware_requirements",
        }
        assert set(d.keys()) == expected_keys


class TestRenderChart:
    def test_renders_nonempty_base64(self):
        report = _make_report()
        b64 = render_chart_b64(report, [0.001], [0.5])
        assert base64.b64decode(b64)[:4] == b"\x89PNG"

    def test_classical_only_chart(self):
        report = _make_report(include_quantum=False)
        b64 = render_chart_b64(report, [0.001], [])
        assert len(b64) > 0

    def test_quantum_only_chart(self):
        report = _make_report(include_classical=False)
        b64 = render_chart_b64(report, [], [0.5])
        assert len(b64) > 0

    def test_multiple_trial_times(self):
        report = _make_report()
        b64 = render_chart_b64(report, [0.001, 0.002, 0.003], [0.5, 0.6, 0.4])
        assert len(b64) > 0


class TestMeasurementRows:
    COUNTS = {"1001": 500, "0110": 400, "0000": 60, "1111": 64}

    def test_ranked_most_likely_first(self):
        rows = measurement_rows(self.COUNTS)
        assert [r["count"] for r in rows] == [500, 400, 64, 60]

    def test_grid_is_the_reversed_bitstring(self):
        """Qiskit is little-endian; the grid reading is what a caller draws."""
        rows = measurement_rows({"1000": 10})
        assert rows[0] == {
            "bitstring": "1000",
            "grid": "0001",
            "count": 10,
            "probability": 1.0,
        }

    def test_probabilities_are_shares_of_the_total(self):
        rows = measurement_rows(self.COUNTS)
        assert sum(r["probability"] for r in rows) == pytest.approx(1.0)

    def test_top_n_truncates(self):
        assert len(measurement_rows(self.COUNTS, top_n=2)) == 2

    def test_empty_counts(self):
        assert measurement_rows({}) == []


class TestRenderHistogram:
    def test_renders_a_png(self):
        b64 = render_histogram_b64({"1001": 500, "0110": 400})
        assert base64.b64decode(b64)[:4] == b"\x89PNG"

    def test_empty_counts_render_nothing(self):
        assert render_histogram_b64({}) == ""
