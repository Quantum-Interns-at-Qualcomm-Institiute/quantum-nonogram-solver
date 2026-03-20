"""Tests for nonogram.quantum — Grover solver on local simulator."""

from nonogram.quantum import quantum_solve


class TestQuantumSolveSmall:
    """Run quantum solver on tiny puzzles where simulation is fast."""

    def test_1x1_filled(self):
        puzzle = ([(1,)], [(1,)])
        result = quantum_solve(puzzle)
        counts = result.circuit_results[0]
        # 1-qubit Grover has near-50/50 probabilities, so just verify
        # the correct answer ("1") appears with non-trivial probability
        total = sum(counts.values())
        assert "1" in counts
        assert counts["1"] / total > 0.3

    def test_1x1_empty(self):
        puzzle = ([(0,)], [(0,)])
        result = quantum_solve(puzzle)
        counts = result.circuit_results[0]
        total = sum(counts.values())
        assert "0" in counts
        assert counts["0"] / total > 0.3

    def test_2x2_all_filled(self):
        puzzle = ([(2,), (2,)], [(2,), (2,)])
        result = quantum_solve(puzzle)
        counts = result.circuit_results[0]
        top = max(counts, key=counts.__getitem__)
        # Reversed bitstring should be "1111"
        assert top[::-1] == "1111"

    def test_2x2_all_empty(self):
        puzzle = ([(0,), (0,)], [(0,), (0,)])
        result = quantum_solve(puzzle)
        counts = result.circuit_results[0]
        top = max(counts, key=counts.__getitem__)
        assert top[::-1] == "0000"

    def test_2x2_diagonal_finds_valid_solution(self):
        """2x2 with row=(1,),(1,), col=(1,),(1,) has two solutions."""
        puzzle = ([(1,), (1,)], [(1,), (1,)])
        result = quantum_solve(puzzle)
        counts = result.circuit_results[0]
        top = max(counts, key=counts.__getitem__)
        reversed_top = top[::-1]
        assert reversed_top in ("1001", "0110")

    def test_quantum_returns_grover_result(self):
        puzzle = ([(1,)], [(1,)])
        result = quantum_solve(puzzle)
        assert hasattr(result, "circuit_results")
        assert len(result.circuit_results) > 0

    def test_3x3_unique_solution(self):
        """3x3 puzzle with known unique solution."""
        # A 3x3 L-shape:
        # 1 0 0
        # 1 0 0
        # 1 1 1
        puzzle = (
            [(1,), (1,), (3,)],
            [(3,), (1,), (1,)],
        )
        result = quantum_solve(puzzle)
        counts = result.circuit_results[0]
        top = max(counts, key=counts.__getitem__)
        reversed_top = top[::-1]
        assert reversed_top == "100100111"


class TestQuantumSolveValidation:
    """Verify quantum solver results are consistent with classical solver."""

    def test_quantum_classical_agreement_2x2(self):
        """Quantum and classical solvers agree on 2x2 puzzles."""
        from nonogram.classical import classical_solve

        puzzle = ([(2,), (1,)], [(1,), (2,)])
        classical_solutions = classical_solve(puzzle)
        assert len(classical_solutions) > 0

        result = quantum_solve(puzzle)
        counts = result.circuit_results[0]
        top = max(counts, key=counts.__getitem__)
        reversed_top = top[::-1]
        assert reversed_top in classical_solutions
