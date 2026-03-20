"""Tests for nonogram.core — Boolean SAT encoding, variable indexing, and validation."""

import io
import sys

import pytest

from nonogram.core import display_nonogram, puzzle_to_boolean, validate, var_clauses


# ---------------------------------------------------------------------------
# var_clauses
# ---------------------------------------------------------------------------

class TestVarClauses:
    def test_square_shape(self):
        row_vars, col_vars = var_clauses(3)
        assert len(row_vars) == 3
        assert len(col_vars) == 3
        assert all(len(r) == 3 for r in row_vars)
        assert all(len(c) == 3 for c in col_vars)

    def test_rectangular_shape(self):
        row_vars, col_vars = var_clauses(2, 4)
        assert len(row_vars) == 2
        assert all(len(r) == 4 for r in row_vars)
        assert len(col_vars) == 4
        assert all(len(c) == 2 for c in col_vars)

    def test_variable_indices_sequential(self):
        row_vars, _ = var_clauses(2, 3)
        flat = [v for row in row_vars for v in row]
        assert flat == list(range(6))

    def test_column_contains_correct_rows(self):
        row_vars, col_vars = var_clauses(3, 4)
        # col_vars[c][r] should equal row_vars[r][c]
        for c in range(4):
            for r in range(3):
                assert col_vars[c][r] == row_vars[r][c]

    def test_default_d_equals_n(self):
        row_vars_sq, _ = var_clauses(4)
        row_vars_rect, _ = var_clauses(4, 4)
        assert row_vars_sq == row_vars_rect


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

class TestValidate:
    def test_valid_input(self):
        assert validate(2, 3, [(1,), (1,)], [(1,), (1,), (1,)]) is True

    def test_wrong_row_clue_count(self):
        with pytest.raises(ValueError, match="row clues"):
            validate(3, 2, [(1,), (1,)], [(1,), (1,)])

    def test_wrong_col_clue_count(self):
        with pytest.raises(ValueError, match="col clues"):
            validate(2, 3, [(1,), (1,)], [(1,), (1,)])


# ---------------------------------------------------------------------------
# display_nonogram
# ---------------------------------------------------------------------------

class TestDisplayNonogram:
    def _capture(self, bit_string, n, d):
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            display_nonogram(bit_string, n, d)
        finally:
            sys.stdout = old
        return buf.getvalue()

    def test_output_has_correct_line_count(self):
        output = self._capture("1001", 2, 2)
        lines = output.strip().split("\n")
        assert len(lines) == 4  # top border + 2 rows + bottom border

    def test_filled_cell_uses_block(self):
        output = self._capture("1000", 2, 2)
        assert "■" in output

    def test_empty_cell_uses_square(self):
        output = self._capture("0111", 2, 2)
        assert "□" in output

    def test_raises_on_short_bitstring(self):
        with pytest.raises(ValueError):
            display_nonogram("10", 2, 3)


# ---------------------------------------------------------------------------
# puzzle_to_boolean
# ---------------------------------------------------------------------------

class TestPuzzleToBooleanQuantum:
    """Tests for the default (quantum/string) output."""

    def test_returns_nonempty_string(self):
        row_clues = [(1,), (1,)]
        col_clues = [(1,), (1,)]
        result = puzzle_to_boolean(row_clues, col_clues)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_string_contains_variable_names(self):
        row_clues = [(1,), (1,)]
        col_clues = [(1,), (1,)]
        result = puzzle_to_boolean(row_clues, col_clues)
        assert "v0" in result

    def test_string_uses_boolean_operators(self):
        row_clues = [(1,), (1,)]
        col_clues = [(1,), (1,)]
        result = puzzle_to_boolean(row_clues, col_clues)
        assert "&" in result
        assert "|" in result


class TestPuzzleToBooleanClassical:
    """Tests for the classical=True output."""

    def test_returns_tuple(self):
        row_clues = [(1,), (1,)]
        col_clues = [(1,), (1,)]
        result = puzzle_to_boolean(row_clues, col_clues, classical=True)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_var_num_equals_grid_cells(self):
        row_clues = [(1,), (1,)]
        col_clues = [(1,), (1,), (1,)]
        _, var_num = puzzle_to_boolean(row_clues, col_clues, classical=True)
        assert var_num == 2 * 3

    def test_clause_count_equals_rows_plus_cols(self):
        row_clues = [(1,), (1,)]
        col_clues = [(1,), (1,), (1,)]
        clauses, _ = puzzle_to_boolean(row_clues, col_clues, classical=True)
        assert len(clauses) == len(row_clues) + len(col_clues)
