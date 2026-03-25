"""Tests for nonogram.classical — brute-force solver on small and demo puzzles."""


from nonogram.classical import classical_solve

# ---------------------------------------------------------------------------
# Small known puzzles
# ---------------------------------------------------------------------------


class TestClassicalSolveSmall:
    """Use tiny puzzles where exhaustive search is instantaneous."""

    def test_1x1_filled(self):
        # Single filled cell: row=(1,), col=(1,)
        puzzle = ([(1,)], [(1,)])
        results = classical_solve(puzzle)
        assert results == ["1"]

    def test_1x1_empty(self):
        # Single empty cell: row=(0,), col=(0,)
        puzzle = ([(0,)], [(0,)])
        results = classical_solve(puzzle)
        assert results == ["0"]

    def test_2x2_diagonal(self):
        # Only valid 2x2 with row=(1,),(1,) and col=(1,),(1,) has two solutions.
        puzzle = ([(1,), (1,)], [(1,), (1,)])
        results = classical_solve(puzzle)
        assert len(results) == 2
        assert "1001" in results  # top-left + bottom-right
        assert "0110" in results  # top-right + bottom-left

    def test_2x2_full_row(self):
        # row=(2,),(2,) col=(2,),(2,) → only fully-filled grid
        puzzle = ([(2,), (2,)], [(2,), (2,)])
        results = classical_solve(puzzle)
        assert results == ["1111"]

    def test_2x2_empty_grid(self):
        puzzle = ([(0,), (0,)], [(0,), (0,)])
        results = classical_solve(puzzle)
        assert results == ["0000"]


# ---------------------------------------------------------------------------
# manual_check path
# ---------------------------------------------------------------------------


class TestManualCheck:
    def test_correct_solution_is_accepted(self):
        # 2x2, row=(1,),(1,), col=(1,),(1,) — one of the two solutions
        puzzle = ([(1,), (1,)], [(1,), (1,)])
        results = classical_solve(puzzle, manual_check="1001")
        assert results == ["1001"]

    def test_incorrect_solution_is_rejected(self):
        puzzle = ([(1,), (1,)], [(1,), (1,)])
        results = classical_solve(puzzle, manual_check="1111")
        assert results == []

    def test_empty_grid_manual(self):
        puzzle = ([(0,), (0,)], [(0,), (0,)])
        results = classical_solve(puzzle, manual_check="0000")
        assert results == ["0000"]


# ---------------------------------------------------------------------------
# Demo puzzles — exhaustive search and known-solution validation
# ---------------------------------------------------------------------------


class TestDemoPuzzle:
    """Exhaustive brute-force tests use a 4×4 puzzle (2^16 candidates) that
    completes in < 1 s.  The original 4×6 notebook puzzle (2^24 candidates) is
    validated via the fast *manual_check* path only.
    """

    # 4×4 cross pattern — tractable for exhaustive search
    PUZZLE_4x4 = (
        [(2,), (4,), (4,), (2,)],
        [(2,), (4,), (4,), (2,)],
    )
    EXPECTED_4x4 = "0110111111110110"

    # Original 4×6 notebook puzzle — too large for brute-force in test time
    PUZZLE_4x6 = (
        [(1, 1), (2, 2), (1, 2, 1), (1, 1)],
        [(4,), (1,), (1,), (1,), (1,), (4,)],
    )
    EXPECTED_4x6 = "100001110011101101100001"

    def test_known_solution_found(self):
        results = classical_solve(self.PUZZLE_4x4)
        assert self.EXPECTED_4x4 in results

    def test_unique_solution(self):
        results = classical_solve(self.PUZZLE_4x4)
        assert len(results) == 1

    def test_manual_check_accepts_known_solution(self):
        """Fast path: verifies the 4×6 notebook solution without exhaustive search."""
        results = classical_solve(self.PUZZLE_4x6, manual_check=self.EXPECTED_4x6)
        assert results == [self.EXPECTED_4x6]
