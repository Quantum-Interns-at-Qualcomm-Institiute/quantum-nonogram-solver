"""Tests for tools.chart — report serialization and chart rendering."""

from nonogram.metrics import ClassicalMetrics, ComparisonReport, QuantumMetrics
from tools.chart import render_chart_b64, report_to_dict


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
        assert len(b64) > 0
        # Should be valid base64
        import base64

        decoded = base64.b64decode(b64)
        # PNG starts with these bytes
        assert decoded[:4] == b"\x89PNG"

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
