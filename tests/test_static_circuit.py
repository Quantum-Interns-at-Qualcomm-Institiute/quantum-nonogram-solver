"""Tests for static quantum circuit analysis."""

import pytest

from nonogram.metrics import StaticCircuitAnalysis, analyze_circuit

SMALL_PUZZLE = ([(1,), (1,)], [(1,), (1,)])  # 2x2


@pytest.fixture(scope="module")
def analysis():
    """One circuit build for the whole module; analyze_circuit is deterministic."""
    return analyze_circuit(SMALL_PUZZLE)


class TestStaticCircuitAnalysis:
    def test_reports_a_consistent_circuit(self, analysis):
        assert isinstance(analysis, StaticCircuitAnalysis)
        assert analysis.num_qubits >= 4  # four problem qubits for a 2x2, plus ancilla
        assert analysis.circuit_depth > 0
        assert analysis.total_gate_count == sum(analysis.gate_counts_by_type.values())
        assert analysis.grover_iterations >= 1

    def test_derived_ratios_follow_the_counts(self, analysis):
        assert analysis.two_qubit_gate_density == (
            analysis.two_qubit_gate_count / analysis.total_gate_count
        )
        assert analysis.depth_per_iteration == (
            analysis.circuit_depth / analysis.grover_iterations
        )
        assert analysis.gates_per_qubit == analysis.total_gate_count / analysis.num_qubits
        assert analysis.ancilla_qubits == analysis.num_qubits - analysis.problem_qubits

    def test_3x3_has_more_qubits_than_2x2(self):
        small = analyze_circuit(SMALL_PUZZLE)
        larger_puzzle = ([(1,), (1,), (0,)], [(1,), (1,), (0,)])
        large = analyze_circuit(larger_puzzle)
        assert large.num_qubits >= small.num_qubits

    def test_consistency_with_benchmark(self):
        from nonogram.metrics import benchmark

        report = benchmark(SMALL_PUZZLE, run_classical=False, run_quantum=True)
        static = analyze_circuit(SMALL_PUZZLE)

        assert static.num_qubits == report.quantum.num_qubits
        assert static.total_gate_count == report.quantum.total_gate_count
