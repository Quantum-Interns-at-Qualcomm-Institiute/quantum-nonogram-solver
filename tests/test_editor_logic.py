"""
tests/test_editor_logic.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for the *pure* puzzle-logic functions in nonogram/core.py.

Covers:
  * rle              — run-length encoding of a boolean row/column
  * grid_to_clues    — derives row + column clues from a 2-D grid
"""

from __future__ import annotations

import pytest

from nonogram.core import rle as _rle, grid_to_clues


# ===========================================================================
# _rle — run-length encode a boolean sequence
# ===========================================================================

class TestRle:
    # --- basic correctness ---

    def test_all_false_returns_empty_clue(self):
        """An entirely empty row should have no filled groups."""
        result = _rle([False, False, False])
        # (0,) is the conventional "empty" sentinel used in this project
        assert result == (0,)

    def test_single_true(self):
        assert _rle([True]) == (1,)

    def test_single_false(self):
        assert _rle([False]) == (0,)

    def test_all_true(self):
        assert _rle([True, True, True]) == (3,)

    def test_two_groups(self):
        # T F T  →  group of 1, gap, group of 1
        assert _rle([True, False, True]) == (1, 1)

    def test_two_groups_unequal(self):
        # TT F T  →  2, 1
        assert _rle([True, True, False, True]) == (2, 1)

    def test_leading_false(self):
        # F T T  →  group of 2 starting at index 1
        assert _rle([False, True, True]) == (2,)

    def test_trailing_false(self):
        # T T F  →  group of 2
        assert _rle([True, True, False]) == (2,)

    def test_multiple_groups(self):
        # T F T F T  →  1, 1, 1
        assert _rle([True, False, True, False, True]) == (1, 1, 1)

    def test_large_single_run(self):
        assert _rle([True] * 6) == (6,)

    def test_longer_multi_group(self):
        # TT F TTT  →  2, 3
        assert _rle([True, True, False, True, True, True]) == (2, 3)

    # --- return-type contract ---

    def test_returns_tuple(self):
        assert isinstance(_rle([True, False]), tuple)

    def test_group_values_are_ints(self):
        result = _rle([True, True, False, True])
        assert all(isinstance(v, int) for v in result)

    # --- edge cases ---

    def test_single_element_true(self):
        assert _rle([True]) == (1,)

    def test_two_elements_both_true(self):
        assert _rle([True, True]) == (2,)

    def test_two_elements_both_false(self):
        assert _rle([False, False]) == (0,)


# ===========================================================================
# grid_to_clues — derive row and column clues from a 2-D boolean grid
# ===========================================================================

def _grid(rows: list[list[bool]]) -> list[list[bool]]:
    """Convenience: just return the nested list unchanged."""
    return rows


class TestGridToClues:
    # --- shape ---

    def test_returns_two_lists(self):
        grid = [[False, False], [False, False]]
        row_clues, col_clues = grid_to_clues(grid)
        assert isinstance(row_clues, list)
        assert isinstance(col_clues, list)

    def test_row_clue_count_equals_row_count(self):
        grid = [[False] * 3 for _ in range(4)]
        row_clues, _ = grid_to_clues(grid)
        assert len(row_clues) == 4

    def test_col_clue_count_equals_col_count(self):
        grid = [[False] * 5 for _ in range(2)]
        _, col_clues = grid_to_clues(grid)
        assert len(col_clues) == 5

    # --- empty grid ---

    def test_empty_grid_all_zero_clues(self):
        grid = [[False, False], [False, False]]
        row_clues, col_clues = grid_to_clues(grid)
        assert all(c == (0,) for c in row_clues)
        assert all(c == (0,) for c in col_clues)

    # --- fully filled grid ---

    def test_full_grid_row_clues_equal_col_count(self):
        n, d = 3, 4
        grid = [[True] * d for _ in range(n)]
        row_clues, col_clues = grid_to_clues(grid)
        assert all(c == (d,) for c in row_clues)
        assert all(c == (n,) for c in col_clues)

    # --- known patterns ---

    def test_diagonal_2x2(self):
        grid = [
            [True,  False],
            [False, True],
        ]
        row_clues, col_clues = grid_to_clues(grid)
        assert row_clues == [(1,), (1,)]
        assert col_clues == [(1,), (1,)]

    def test_first_row_filled(self):
        grid = [
            [True, True, True],
            [False, False, False],
        ]
        row_clues, col_clues = grid_to_clues(grid)
        assert row_clues[0] == (3,)
        assert row_clues[1] == (0,)   # empty row
        assert all(c == (1,) for c in col_clues)

    def test_checkerboard_3x3(self):
        #  T F T
        #  F T F
        #  T F T
        grid = [
            [True,  False, True],
            [False, True,  False],
            [True,  False, True],
        ]
        row_clues, col_clues = grid_to_clues(grid)
        # each row: two isolated cells → (1, 1) for rows 0 and 2; single cell for row 1
        assert row_clues[0] == (1, 1)
        assert row_clues[1] == (1,)
        assert row_clues[2] == (1, 1)
        # col 0: T F T → (1, 1); col 1: F T F → (1,); col 2: T F T → (1, 1)
        assert col_clues[0] == (1, 1)
        assert col_clues[1] == (1,)
        assert col_clues[2] == (1, 1)

    def test_multi_group_row(self):
        # Row: T T F T  →  (2, 1)
        grid = [[True, True, False, True]]
        row_clues, _ = grid_to_clues(grid)
        assert row_clues[0] == (2, 1)

    def test_multi_group_column(self):
        # Col: T T F T  →  (2, 1)  (4-row grid, single column)
        grid = [[True], [True], [False], [True]]
        _, col_clues = grid_to_clues(grid)
        assert col_clues[0] == (2, 1)

    # --- clue usability ---

    def test_clues_can_be_passed_directly_to_solver(self):
        """grid_to_clues output must feed straight into classical_solve."""
        from nonogram.classical import classical_solve

        grid = [
            [True,  False],
            [False, True],
        ]
        row_clues, col_clues = grid_to_clues(grid)
        solutions = classical_solve((row_clues, col_clues))
        assert len(solutions) > 0

    def test_clues_can_be_saved_and_reloaded(self, tmp_path):
        """grid_to_clues output must survive a save/load roundtrip via io."""
        from nonogram.io import load_puzzle, save_puzzle

        grid = [
            [True, True, False],
            [False, True, True],
        ]
        row_clues, col_clues = grid_to_clues(grid)
        dest = tmp_path / "roundtrip.non.json"
        save_puzzle(row_clues, col_clues, dest, name="Roundtrip")
        data = load_puzzle(dest)
        r = [tuple(r) for r in data["row_clues"]]
        c = [tuple(c) for c in data["col_clues"]]
        assert r == row_clues
        assert c == col_clues
