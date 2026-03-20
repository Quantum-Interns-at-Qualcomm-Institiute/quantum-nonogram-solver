"""Edge case and boundary tests for nonogram.core."""

import pytest

from nonogram.core import (
    display_nonogram,
    grid_to_clues,
    parse_clue,
    puzzle_to_boolean,
    rle,
    validate,
    var_clauses,
)
from nonogram.errors import ValidationError


class TestVarClausesEdgeCases:
    def test_1x1_grid(self):
        row_vars, col_vars = var_clauses(1)
        assert row_vars == [[0]]
        assert col_vars == [[0]]

    def test_1x5_single_row(self):
        row_vars, col_vars = var_clauses(1, 5)
        assert len(row_vars) == 1
        assert row_vars[0] == [0, 1, 2, 3, 4]
        assert len(col_vars) == 5
        assert all(len(c) == 1 for c in col_vars)

    def test_5x1_single_column(self):
        row_vars, col_vars = var_clauses(5, 1)
        assert len(row_vars) == 5
        assert all(len(r) == 1 for r in row_vars)
        assert len(col_vars) == 1
        assert col_vars[0] == [0, 1, 2, 3, 4]

    def test_6x6_max_grid(self):
        row_vars, col_vars = var_clauses(6, 6)
        flat = [v for row in row_vars for v in row]
        assert flat == list(range(36))


class TestValidateEdgeCases:
    def test_single_row_col(self):
        assert validate(1, 1, [(1,)], [(1,)]) is True

    def test_zero_clues_raises(self):
        with pytest.raises(ValidationError):
            validate(1, 1, [], [(1,)])

    def test_extra_clues_raises(self):
        with pytest.raises(ValidationError):
            validate(1, 1, [(1,), (1,)], [(1,)])


class TestDisplayNonogramEdgeCases:
    def test_1x1_filled(self, capsys):
        display_nonogram("1", 1, 1)
        output = capsys.readouterr().out
        assert "■" in output

    def test_1x1_empty(self, capsys):
        display_nonogram("0", 1, 1)
        output = capsys.readouterr().out
        assert "□" in output

    def test_longer_bitstring_uses_prefix(self, capsys):
        # Bitstring is longer than needed — only first n*d bits used
        display_nonogram("1100000000", 2, 2)
        output = capsys.readouterr().out
        assert "■" in output


class TestRleEdgeCases:
    def test_empty_list(self):
        assert rle([]) == (0,)

    def test_single_true(self):
        assert rle([True]) == (1,)

    def test_single_false(self):
        assert rle([False]) == (0,)

    def test_alternating(self):
        assert rle([True, False, True, False, True]) == (1, 1, 1)

    def test_all_true(self):
        assert rle([True, True, True, True]) == (4,)

    def test_all_false(self):
        assert rle([False, False, False, False]) == (0,)

    def test_leading_false(self):
        assert rle([False, False, True, True]) == (2,)

    def test_trailing_false(self):
        assert rle([True, True, False, False]) == (2,)


class TestGridToCluesEdgeCases:
    def test_1x1_filled(self):
        row_clues, col_clues = grid_to_clues([[True]])
        assert row_clues == [(1,)]
        assert col_clues == [(1,)]

    def test_1x1_empty(self):
        row_clues, col_clues = grid_to_clues([[False]])
        assert row_clues == [(0,)]
        assert col_clues == [(0,)]

    def test_empty_grid(self):
        row_clues, col_clues = grid_to_clues([])
        assert row_clues == []
        assert col_clues == []


class TestParseClueEdgeCases:
    def test_single_zero(self):
        assert parse_clue("0") == (0,)

    def test_multiple_zeros(self):
        assert parse_clue("0 0 0") == (0,)

    def test_whitespace_only(self):
        assert parse_clue("   ") == (0,)

    def test_non_numeric(self):
        assert parse_clue("abc") == (0,)

    def test_mixed_valid_numbers(self):
        assert parse_clue("3 1 2") == (3, 1, 2)


class TestPuzzleToBooleanEdgeCases:
    def test_1x1_filled_quantum(self):
        result = puzzle_to_boolean([(1,)], [(1,)])
        assert isinstance(result, str)
        assert "v0" in result

    def test_1x1_empty_quantum(self):
        result = puzzle_to_boolean([(0,)], [(0,)])
        assert isinstance(result, str)

    def test_1x1_filled_classical(self):
        clauses, num_vars = puzzle_to_boolean([(1,)], [(1,)], classical=True)
        assert num_vars == 1
        assert len(clauses) == 2  # 1 row + 1 col

    def test_invalid_clue_raises(self):
        # Clue requires more cells than available
        with pytest.raises(ValidationError):
            puzzle_to_boolean([(3,)], [(1,)])  # row needs 3 cells but only 1 col

    def test_rectangular_grid(self):
        result = puzzle_to_boolean([(1,), (1,), (1,)], [(1,), (1,)])
        assert isinstance(result, str)

    def test_classical_clause_structure(self):
        """Each clause should be a list of subclauses (lists of literals)."""
        clauses, num_vars = puzzle_to_boolean([(1,), (1,)], [(1,), (1,)], classical=True)
        for clause in clauses:
            assert isinstance(clause, list)
            for subclause in clause:
                assert isinstance(subclause, list)
                for literal in subclause:
                    # May be numpy int, so check with int() conversion
                    assert int(literal) != 0
                    assert 1 <= abs(int(literal)) <= num_vars
