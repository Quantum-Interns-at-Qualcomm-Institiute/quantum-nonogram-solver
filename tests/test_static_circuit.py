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


class TestDepthDescribesGatesNotIterations:
    """The reported depth must count gate layers, not Grover operator applications.

    ``construct_circuit`` appends the Grover operator as one opaque gate per
    iteration, so an unexpanded ``circuit.depth()`` returns k+1 whatever the
    puzzle. These pin the number to the work.
    """

    def test_depth_far_exceeds_the_iteration_count(self):
        analysis = analyze_circuit(SMALL_PUZZLE)
        assert analysis.circuit_depth > analysis.grover_iterations + 1

    def test_entangling_gates_are_counted(self):
        analysis = analyze_circuit(SMALL_PUZZLE)
        assert analysis.two_qubit_gate_count > 0

    def test_depth_per_iteration_is_a_real_cost(self):
        analysis = analyze_circuit(SMALL_PUZZLE)
        assert analysis.depth_per_iteration > 1


class TestIterationCountFollowsTheSolutionCount:
    """More solutions need fewer iterations; the count must not be hardcoded to one."""

    def test_two_solutions_need_fewer_iterations_than_one(self):
        one = analyze_circuit(SMALL_PUZZLE, num_solutions=1)
        two = analyze_circuit(SMALL_PUZZLE, num_solutions=2)
        assert two.grover_iterations < one.grover_iterations

    def test_the_benchmark_uses_the_count_the_classical_pass_found(self):
        from nonogram.classical import classical_solve
        from nonogram.metrics import benchmark

        # A 2x2 with one filled cell per line has two solutions (the diagonals).
        puzzle = ([(1,), (1,)], [(1,), (1,)])
        assert len(classical_solve(puzzle)) == 2

        report = benchmark(puzzle, run_classical=True, run_quantum=True)
        expected = analyze_circuit(puzzle, num_solutions=2).grover_iterations
        assert report.quantum.grover_iterations == expected
