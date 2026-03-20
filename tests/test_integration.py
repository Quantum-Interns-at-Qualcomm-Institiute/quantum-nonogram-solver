"""End-to-end integration tests: full solve pipeline verification.

These tests exercise the complete path from puzzle definition through
SAT encoding, solving (both classical and quantum), and result validation.
"""

from nonogram.classical import classical_solve
from nonogram.core import grid_to_clues, puzzle_to_boolean, validate
from nonogram.metrics import benchmark
from nonogram.quantum import quantum_solve


class TestFullPipelineClassical:
    """Test the full classical pipeline: define puzzle → encode → solve → verify."""

    def test_2x2_roundtrip(self):
        """Define a 2x2 grid, extract clues, solve, verify solution matches."""
        # Define a grid: top-left filled, rest empty
        grid = [[True, False], [False, False]]
        row_clues, col_clues = grid_to_clues(grid)

        assert row_clues == [(1,), (0,)]
        assert col_clues == [(1,), (0,)]

        puzzle = (row_clues, col_clues)
        validate(2, 2, row_clues, col_clues)

        solutions = classical_solve(puzzle)
        # The expected bitstring (variable order, reversed)
        assert len(solutions) == 1
        sol = solutions[0]
        # Verify the solution bitstring represents the original grid
        assert sol[0] == "1"  # (0,0) = True
        assert sol[1] == "0"  # (0,1) = False
        assert sol[2] == "0"  # (1,0) = False
        assert sol[3] == "0"  # (1,1) = False

    def test_3x3_checkerboard_no_solution(self):
        """A clue set that has no valid 3x3 solution."""
        # row clues say 2 filled per row, col clues say 1 per col
        # 3 rows × 2 filled = 6 total, but 3 cols × 1 = 3 total → impossible
        puzzle = ([(2,), (2,), (2,)], [(1,), (1,), (1,)])
        solutions = classical_solve(puzzle)
        assert len(solutions) == 0

    def test_3x3_full_grid(self):
        puzzle = ([(3,), (3,), (3,)], [(3,), (3,), (3,)])
        solutions = classical_solve(puzzle)
        assert len(solutions) == 1
        assert solutions[0] == "111111111"


class TestFullPipelineQuantum:
    """Test the full quantum pipeline on small puzzles."""

    def test_2x2_quantum_classical_agree(self):
        """Both solvers find the same solution for a 2x2 unique puzzle."""
        puzzle = ([(2,), (2,)], [(2,), (2,)])
        classical_solutions = classical_solve(puzzle)
        assert len(classical_solutions) == 1

        result = quantum_solve(puzzle)
        counts = result.circuit_results[0]
        top = max(counts, key=counts.__getitem__)
        # Quantum bitstrings need reversal for row-major order
        assert top[::-1] in classical_solutions

    def test_2x2_multi_solution_quantum(self):
        """Quantum solver finds one of the valid solutions for a multi-solution puzzle."""
        puzzle = ([(1,), (1,)], [(1,), (1,)])
        classical_solutions = classical_solve(puzzle)
        assert len(classical_solutions) == 2

        result = quantum_solve(puzzle)
        counts = result.circuit_results[0]
        top = max(counts, key=counts.__getitem__)
        assert top[::-1] in classical_solutions


class TestBenchmarkIntegration:
    """Test the benchmark function produces valid reports."""

    def test_benchmark_both_solvers(self):
        # Use 2x2 unique-solution puzzle (1x1 is degenerate for Grover)
        puzzle = ([(2,), (2,)], [(2,), (2,)])
        report = benchmark(puzzle, run_classical=True, run_quantum=True)
        assert report.classical is not None
        assert report.quantum is not None
        assert report.classical.solutions_found == 1
        assert report.quantum.oracle_evaluation_correct is True
        assert report.actual_speedup > 0

    def test_benchmark_classical_only(self):
        puzzle = ([(2,), (2,)], [(2,), (2,)])
        report = benchmark(puzzle, run_classical=True, run_quantum=False)
        assert report.classical is not None
        assert report.quantum is None

    def test_benchmark_quantum_only(self):
        puzzle = ([(2,), (2,)], [(2,), (2,)])
        report = benchmark(puzzle, run_classical=False, run_quantum=True)
        assert report.classical is None
        assert report.quantum is not None

    def test_benchmark_2x2(self):
        puzzle = ([(2,), (2,)], [(2,), (2,)])
        report = benchmark(puzzle, run_classical=True, run_quantum=True)
        assert report.rows == 2
        assert report.cols == 2
        assert report.num_variables == 4
        assert report.search_space_size == 16
        assert report.classical.solutions_found == 1
        assert report.quantum.solutions_found >= 1


class TestSATEncodingIntegration:
    """Verify SAT encoding correctness through solve results."""

    def test_boolean_expression_accepted_by_oracle(self):
        """The boolean expression should be valid input for PhaseOracleGate."""
        from qiskit.circuit.library import PhaseOracleGate

        puzzle = ([(1,), (1,)], [(1,), (1,)])
        expr = puzzle_to_boolean(puzzle[0], puzzle[1])
        # This should not raise
        oracle = PhaseOracleGate(expr)
        assert oracle.num_qubits >= 4  # at least 4 problem qubits for 2x2

    def test_classical_encoding_all_solutions_valid(self):
        """Every solution from classical solver should satisfy all constraints."""
        puzzle = ([(1,), (1,)], [(1,), (1,)])
        solutions = classical_solve(puzzle)

        # Verify each solution satisfies the constraints by re-checking
        for sol in solutions:
            # Reconstruct grid from bitstring
            grid = [[sol[i * 2 + j] == "1" for j in range(2)] for i in range(2)]
            row_clues, col_clues = grid_to_clues(grid)
            # Check row clues match
            for actual, expected in zip(row_clues, puzzle[0]):
                assert actual == expected
            # Check col clues match
            for actual, expected in zip(col_clues, puzzle[1]):
                assert actual == expected
