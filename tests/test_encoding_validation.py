"""Tests for SAT encoding in nonogram.core.puzzle_to_boolean.

Validates boolean expression generation, classical clause output, variable
indexing, parenthesis balancing, and error handling for invalid clues.
"""

from itertools import product

import pytest

from nonogram.core import puzzle_to_boolean
from nonogram.errors import ValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _eval_boolean_expr(expr: str, assignment: dict[int, bool]) -> bool:
    """Evaluate a puzzle_to_boolean expression with the given variable assignment.

    Replaces each ``vN`` with ``True``/``False`` and evaluates using Python
    boolean operators (``~`` -> ``not``, ``&`` -> ``and``, ``|`` -> ``or``).
    """
    s = expr
    # Replace longest variable names first to avoid v1 matching in v10.
    for idx in sorted(assignment, reverse=True):
        s = s.replace(f"v{idx}", str(assignment[idx]))
    s = s.replace("~", " not ").replace("&", " and ").replace("|", " or ")
    return bool(eval(s))  # noqa: S307


def _bitstring_to_assignment(bits: str) -> dict[int, bool]:
    """Convert a binary string to a variable assignment dict."""
    return {i: (b == "1") for i, b in enumerate(bits)}


def _all_bitstrings(length: int):
    """Yield all binary strings of the given length."""
    for combo in product("01", repeat=length):
        yield "".join(combo)


# ---------------------------------------------------------------------------
# 1x1 puzzles
# ---------------------------------------------------------------------------


class TestOneByOne:
    """Test 1x1 puzzles: filled and empty."""

    def test_filled_cell(self):
        expr = puzzle_to_boolean([(1,)], [(1,)])
        assert isinstance(expr, str)
        assert "v0" in expr
        # The only valid assignment is v0=True.
        assert _eval_boolean_expr(expr, {0: True})
        assert not _eval_boolean_expr(expr, {0: False})

    def test_empty_cell(self):
        expr = puzzle_to_boolean([(0,)], [(0,)])
        assert isinstance(expr, str)
        # The only valid assignment is v0=False.
        assert _eval_boolean_expr(expr, {0: False})
        assert not _eval_boolean_expr(expr, {0: True})


# ---------------------------------------------------------------------------
# 2x2 puzzles with known solutions
# ---------------------------------------------------------------------------


class TestTwoByTwo:
    """Test 2x2 puzzles; verify boolean expression is valid Python-evaluable."""

    def test_full_grid(self):
        """All cells filled: row clues (2,), (2,) and col clues (2,), (2,)."""
        expr = puzzle_to_boolean([(2,), (2,)], [(2,), (2,)])
        # Only '1111' should satisfy.
        assert _eval_boolean_expr(expr, _bitstring_to_assignment("1111"))
        for bits in _all_bitstrings(4):
            if bits != "1111":
                assert not _eval_boolean_expr(expr, _bitstring_to_assignment(bits))

    def test_identity_diagonal(self):
        """Top-left and bottom-right filled: rows (1,), (1,); cols (1,), (1,)."""
        expr = puzzle_to_boolean([(1,), (1,)], [(1,), (1,)])
        satisfying = set()
        for bits in _all_bitstrings(4):
            if _eval_boolean_expr(expr, _bitstring_to_assignment(bits)):
                satisfying.add(bits)
        # Two valid grids: 1001 and 0110.
        assert satisfying == {"1001", "0110"}

    def test_expression_is_evaluable(self):
        """Confirm that eval does not raise on a 2x2 expression."""
        expr = puzzle_to_boolean([(1,), (1,)], [(1,), (1,)])
        # Should not raise for any assignment.
        for bits in _all_bitstrings(4):
            _eval_boolean_expr(expr, _bitstring_to_assignment(bits))


# ---------------------------------------------------------------------------
# 3x3 puzzles — constraint group count
# ---------------------------------------------------------------------------


class TestThreeByThree:
    """Test 3x3 puzzles; verify constraint group count (n + d groups)."""

    def test_constraint_group_count(self):
        """The top-level expression should have n + d AND-joined groups."""
        row_clues = [(1,), (1,), (1,)]
        col_clues = [(1,), (1,), (1,)]
        expr = puzzle_to_boolean(row_clues, col_clues)
        # Groups are separated by & at the top level. Each group is wrapped
        # in parentheses. Count the outermost groups by splitting on ')&(' or
        # by counting top-level '&' operators.
        # The expression structure is: (group1)&(group2)&...&(groupN)
        # A reliable way: count top-level & separators.
        n = len(row_clues)
        d = len(col_clues)
        expected_groups = n + d
        # Parse depth to count top-level AND groups.
        depth = 0
        top_level_ands = 0
        for ch in expr:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "&" and depth == 0:
                top_level_ands += 1
        assert top_level_ands == expected_groups - 1

    def test_3x3_all_filled(self):
        """3x3 all-filled grid has exactly one solution."""
        expr = puzzle_to_boolean([(3,), (3,), (3,)], [(3,), (3,), (3,)])
        assert _eval_boolean_expr(expr, _bitstring_to_assignment("111111111"))


# ---------------------------------------------------------------------------
# Classical mode — clause count and variable count
# ---------------------------------------------------------------------------


class TestClassicalOutput:
    """Test classical=True returns correct clause count and variable count."""

    def test_clause_count_2x2(self):
        clauses, num_vars = puzzle_to_boolean(
            [(1,), (1,)], [(1,), (1,)], classical=True
        )
        assert num_vars == 4
        # One constraint group per row + per column = 2 + 2 = 4.
        assert len(clauses) == 4

    def test_clause_count_2x3(self):
        clauses, num_vars = puzzle_to_boolean(
            [(1,), (1,)], [(1,), (1,), (0,)], classical=True
        )
        assert num_vars == 6
        assert len(clauses) == 2 + 3

    def test_clause_count_3x3(self):
        clauses, num_vars = puzzle_to_boolean(
            [(1,), (1,), (1,)], [(1,), (1,), (1,)], classical=True
        )
        assert num_vars == 9
        assert len(clauses) == 6

    def test_var_count_rectangular(self):
        _, num_vars = puzzle_to_boolean(
            [(1,), (1,), (1,)], [(1,), (1,)], classical=True
        )
        assert num_vars == 6


# ---------------------------------------------------------------------------
# Classical literal range
# ---------------------------------------------------------------------------


class TestClassicalLiteralRange:
    """Test that classical literals are in [-num_vars, -1] union [1, num_vars]."""

    @pytest.mark.parametrize(
        "row_clues, col_clues",
        [
            ([(1,)], [(1,)]),
            ([(1,), (1,)], [(1,), (1,)]),
            ([(2,), (0,)], [(1,), (1,)]),
            ([(1,), (1,), (1,)], [(1,), (1,), (1,)]),
        ],
    )
    def test_literals_in_valid_range(self, row_clues, col_clues):
        clauses, num_vars = puzzle_to_boolean(row_clues, col_clues, classical=True)
        valid_range = set(range(-num_vars, 0)) | set(range(1, num_vars + 1))
        for constraint_group in clauses:
            for clause in constraint_group:
                for lit in clause:
                    assert lit in valid_range, (
                        f"Literal {lit} out of range for num_vars={num_vars}"
                    )

    def test_no_zero_literal(self):
        """Zero is never a valid DIMACS-style literal."""
        clauses, _ = puzzle_to_boolean(
            [(1,), (1,)], [(1,), (1,)], classical=True
        )
        for constraint_group in clauses:
            for clause in constraint_group:
                assert 0 not in clause


# ---------------------------------------------------------------------------
# Balanced parentheses
# ---------------------------------------------------------------------------


class TestBalancedParentheses:
    """Test that boolean expressions have balanced parentheses."""

    @pytest.mark.parametrize(
        "row_clues, col_clues",
        [
            ([(1,)], [(1,)]),
            ([(0,)], [(0,)]),
            ([(1,), (1,)], [(1,), (1,)]),
            ([(2,), (0,)], [(1,), (1,)]),
            ([(1,), (1,), (1,)], [(1,), (1,), (1,)]),
            ([(1, 1)], [(1,), (0,), (1,)]),
        ],
    )
    def test_parentheses_balanced(self, row_clues, col_clues):
        expr = puzzle_to_boolean(row_clues, col_clues)
        depth = 0
        for ch in expr:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            assert depth >= 0, "Closing paren before matching open paren"
        assert depth == 0, f"Unbalanced parentheses: {depth} unclosed"


# ---------------------------------------------------------------------------
# ValidationError for impossible clues
# ---------------------------------------------------------------------------


class TestValidationErrorOnImpossibleClues:
    """Test that ValidationError is raised for clues that exceed grid dimensions."""

    def test_row_clue_too_large(self):
        """Clue (3,) cannot fit in a 2-cell row."""
        with pytest.raises(ValidationError):
            puzzle_to_boolean([(3,)], [(1,), (1,)])

    def test_col_clue_too_large(self):
        """Clue (3,) cannot fit in a 2-row column."""
        with pytest.raises(ValidationError):
            puzzle_to_boolean([(1,), (1,)], [(3,)])

    def test_multi_block_clue_too_large(self):
        """Clue (1,1) needs 3 cells minimum; won't fit in a 2-cell line."""
        with pytest.raises(ValidationError):
            puzzle_to_boolean([(1, 1)], [(1,), (1,)])

    def test_error_is_value_error_subclass(self):
        """ValidationError should also be catchable as ValueError."""
        with pytest.raises(ValueError):
            puzzle_to_boolean([(3,)], [(1,), (1,)])


# ---------------------------------------------------------------------------
# Rectangular grids
# ---------------------------------------------------------------------------


class TestRectangularGrids:
    """Test non-square grids (2x3, 3x2)."""

    def test_2x3_variable_count(self):
        _, num_vars = puzzle_to_boolean(
            [(1,), (1,)], [(1,), (0,), (1,)], classical=True
        )
        assert num_vars == 6

    def test_3x2_variable_count(self):
        _, num_vars = puzzle_to_boolean(
            [(1,), (1,), (0,)], [(1,), (1,)], classical=True
        )
        assert num_vars == 6

    def test_2x3_expression_has_correct_vars(self):
        """A 2x3 grid should reference variables v0 through v5."""
        expr = puzzle_to_boolean([(1,), (1,)], [(1,), (0,), (1,)])
        for i in range(6):
            assert f"v{i}" in expr

    def test_3x2_solution_evaluation(self):
        """3x2 grid: rows (2,), (0,), (1,); cols (1,), (1,1).
        Row 0: [1,1], Row 1: [0,0], Row 2: [0,1].
        Bitstring: 110001.
        """
        row_clues = [(2,), (0,), (1,)]
        col_clues = [(1,), (1, 1)]
        expr = puzzle_to_boolean(row_clues, col_clues)
        # Valid solution: row0=11, row1=00, row2=01 -> "110001"
        assert _eval_boolean_expr(expr, _bitstring_to_assignment("110001"))


# ---------------------------------------------------------------------------
# Multi-block clues
# ---------------------------------------------------------------------------


class TestMultiBlockClues:
    """Test multi-block clues like (1,1) on a 3-cell line."""

    def test_1_1_on_3_cell_line(self):
        """Row clue (1,1) on 3 cells has exactly one pattern: 101."""
        # 1x3 grid: single row with clue (1,1), column clues derived.
        # Columns: col0=1, col1=0, col2=1
        row_clues = [(1, 1)]
        col_clues = [(1,), (0,), (1,)]
        expr = puzzle_to_boolean(row_clues, col_clues)
        assert _eval_boolean_expr(expr, _bitstring_to_assignment("101"))
        assert not _eval_boolean_expr(expr, _bitstring_to_assignment("110"))
        assert not _eval_boolean_expr(expr, _bitstring_to_assignment("011"))

    def test_1_1_on_4_cell_line(self):
        """Row clue (1,1) on 4 cells has multiple valid patterns."""
        # Use a single-row 1x4 grid.
        row_clues = [(1, 1)]
        col_clues = [(1,), (0,), (1,), (0,)]
        expr = puzzle_to_boolean(row_clues, col_clues)
        # Valid row patterns for (1,1) on 4 cells: 1010, 0101, 1001
        # But column constraints also restrict: col0=(1,), col1=(0,), col2=(1,), col3=(0,)
        # Only 1010 satisfies all column constraints.
        assert _eval_boolean_expr(expr, _bitstring_to_assignment("1010"))

    def test_multi_block_classical_clause_structure(self):
        """Classical clauses for a multi-block clue should have multiple subclauses."""
        clauses, num_vars = puzzle_to_boolean(
            [(1, 1), (0,)], [(1,), (0,), (1,)], classical=True
        )
        # Row 0 constraint for clue (1,1) on 3 cells: 1 pattern (101)
        row0_clauses = clauses[0]
        assert len(row0_clauses) == 1  # only one valid pattern
        assert len(row0_clauses[0]) == 3  # 3 literals per clause


# ---------------------------------------------------------------------------
# Boolean expression evaluates correctly for known solutions
# ---------------------------------------------------------------------------


class TestKnownSolutionEvaluation:
    """Test that boolean expressions accept valid solutions and reject invalid ones."""

    def test_2x2_diagonal_solutions(self):
        """2x2 identity: rows (1,),(1,); cols (1,),(1,)."""
        expr = puzzle_to_boolean([(1,), (1,)], [(1,), (1,)])
        valid = {"1001", "0110"}
        for bits in _all_bitstrings(4):
            result = _eval_boolean_expr(expr, _bitstring_to_assignment(bits))
            if bits in valid:
                assert result, f"Expected {bits} to satisfy the expression"
            else:
                assert not result, f"Expected {bits} to NOT satisfy the expression"

    def test_1x3_single_block(self):
        """1x3 row clue (2,); col clues (1,), (1,), (0,)."""
        row_clues = [(2,)]
        col_clues = [(1,), (1,), (0,)]
        expr = puzzle_to_boolean(row_clues, col_clues)
        # Only valid: 110
        assert _eval_boolean_expr(expr, _bitstring_to_assignment("110"))
        assert not _eval_boolean_expr(expr, _bitstring_to_assignment("011"))
        assert not _eval_boolean_expr(expr, _bitstring_to_assignment("101"))

    def test_3x3_unique_solution(self):
        """A 3x3 puzzle with a unique solution."""
        # Grid:  1 0 1
        #        0 1 0
        #        1 0 1
        row_clues = [(1, 1), (1,), (1, 1)]
        col_clues = [(1, 1), (1,), (1, 1)]
        expr = puzzle_to_boolean(row_clues, col_clues)
        solution = "101010101"
        assert _eval_boolean_expr(expr, _bitstring_to_assignment(solution))


# ---------------------------------------------------------------------------
# Classical clause list correctly rejects invalid bitstrings
# ---------------------------------------------------------------------------


class TestClassicalRejection:
    """Test that the classical clause list rejects invalid bitstrings."""

    @staticmethod
    def _check_classical(clauses, num_vars, bitstring: str) -> bool:
        """Check if a bitstring satisfies all classical constraint groups.

        Each constraint group is a list of clauses (DNF per line).
        A constraint group is satisfied if at least one clause is satisfied.
        A clause is satisfied if all its literals are satisfied.
        A positive literal ``k`` is satisfied when bit ``k-1`` is 0 (not set).
        A negative literal ``-k`` is satisfied when bit ``k-1`` is 1 (set).
        """
        bits = [int(b) for b in bitstring]
        for group in clauses:
            group_sat = False
            for clause in group:
                clause_sat = True
                for lit in clause:
                    var_idx = abs(lit) - 1
                    # _classical_literal: bit_set -> -(1+idx), not bit_set -> +(1+idx)
                    # So negative literal means cell is set, positive means cell is not set.
                    if lit < 0:
                        if bits[var_idx] != 1:
                            clause_sat = False
                            break
                    else:
                        if bits[var_idx] != 0:
                            clause_sat = False
                            break
                if clause_sat:
                    group_sat = True
                    break
            if not group_sat:
                return False
        return True

    def test_classical_accepts_valid_2x2(self):
        clauses, num_vars = puzzle_to_boolean(
            [(1,), (1,)], [(1,), (1,)], classical=True
        )
        assert self._check_classical(clauses, num_vars, "1001")
        assert self._check_classical(clauses, num_vars, "0110")

    def test_classical_rejects_invalid_2x2(self):
        clauses, num_vars = puzzle_to_boolean(
            [(1,), (1,)], [(1,), (1,)], classical=True
        )
        # All-filled violates (1,) row constraint (needs exactly 1 filled).
        assert not self._check_classical(clauses, num_vars, "1111")
        # All-empty violates (1,) row constraint.
        assert not self._check_classical(clauses, num_vars, "0000")

    def test_classical_exhaustive_1x1(self):
        clauses, num_vars = puzzle_to_boolean([(1,)], [(1,)], classical=True)
        assert self._check_classical(clauses, num_vars, "1")
        assert not self._check_classical(clauses, num_vars, "0")

    def test_classical_and_boolean_agree(self):
        """Classical and boolean modes should accept the same bitstrings."""
        row_clues = [(1,), (1,)]
        col_clues = [(1,), (1,)]
        expr = puzzle_to_boolean(row_clues, col_clues)
        clauses, num_vars = puzzle_to_boolean(row_clues, col_clues, classical=True)
        for bits in _all_bitstrings(4):
            bool_result = _eval_boolean_expr(expr, _bitstring_to_assignment(bits))
            cl_result = self._check_classical(clauses, num_vars, bits)
            assert bool_result == cl_result, (
                f"Mismatch for bitstring {bits}: "
                f"boolean={bool_result}, classical={cl_result}"
            )
