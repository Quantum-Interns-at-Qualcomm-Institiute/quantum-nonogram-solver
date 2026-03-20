"""Tests for static quantum circuit analysis."""

import pytest

from nonogram.metrics import StaticCircuitAnalysis, analyze_circuit


SMALL_PUZZLE = ([(1,), (1,)], [(1,), (1,)])  # 2x2


class TestStaticCircuitAnalysis:
    def test_returns_analysis(self):
        result = analyze_circuit(SMALL_PUZZLE)
        assert isinstance(result, StaticCircuitAnalysis)

    def test_num_qubits_positive(self):
        result = analyze_circuit(SMALL_PUZZLE)
        assert result.num_qubits > 0

    def test_circuit_depth_positive(self):
        result = analyze_circuit(SMALL_PUZZLE)
        assert result.circuit_depth > 0

    def test_total_gate_count_positive(self):
        result = analyze_circuit(SMALL_PUZZLE)
        assert result.total_gate_count > 0

    def test_gate_counts_by_type_populated(self):
        result = analyze_circuit(SMALL_PUZZLE)
        assert len(result.gate_counts_by_type) > 0

    def test_two_qubit_gate_density_range(self):
        result = analyze_circuit(SMALL_PUZZLE)
        assert 0.0 <= result.two_qubit_gate_density <= 1.0

    def test_depth_per_iteration_positive(self):
        result = analyze_circuit(SMALL_PUZZLE)
        assert result.depth_per_iteration > 0

    def test_gates_per_qubit_positive(self):
        result = analyze_circuit(SMALL_PUZZLE)
        assert result.gates_per_qubit > 0

    def test_grover_iterations_positive(self):
        result = analyze_circuit(SMALL_PUZZLE)
        assert result.grover_iterations >= 1

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
