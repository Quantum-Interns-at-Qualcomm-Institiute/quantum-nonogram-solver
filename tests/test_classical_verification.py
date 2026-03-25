"""Tests verifying classical solver solutions actually satisfy puzzle constraints.

For every solution returned by classical_solve, we independently verify that
the bitstring satisfies all row and column clues by reconstructing the grid
and checking run-length encoding matches the original clues.
"""
from __future__ import annotations

import pytest

from nonogram.classical import classical_solve
from nonogram.core import rle

# ── Helpers ──────────────────────────────────────────────────────────────────


def _verify_solution(bitstring: str, row_clues: list, col_clues: list) -> None:
    """Assert that a bitstring satisfies all row and column clues."""
    n = len(row_clues)
    d = len(col_clues)
    # classical_solve returns bitstrings where character i = variable i,
    # and variables are numbered row-major (v0=cell(0,0), v1=cell(0,1), ...)
    bs = bitstring
    assert len(bs) >= n * d, f"bitstring too short: {len(bs)} < {n * d}"

    for r in range(n):
        row_bits = [bs[r * d + c] == "1" for c in range(d)]
        got = rle(row_bits)
        expect = tuple(row_clues[r])
        assert got == expect, f"Row {r}: expected {expect}, got {got} from {row_bits}"

    for c in range(d):
        col_bits = [bs[r * d + c] == "1" for r in range(n)]
        got = rle(col_bits)
        expect = tuple(col_clues[c])
        assert got == expect, f"Col {c}: expected {expect}, got {got} from {col_bits}"


# ── 1×1 puzzles ─────────────────────────────────────────────────────────────


def test_1x1_filled():
    puzzle = ([(1,)], [(1,)])
    solutions = classical_solve(puzzle)
    assert len(solutions) == 1
    _verify_solution(solutions[0], puzzle[0], puzzle[1])


def test_1x1_empty():
    puzzle = ([(0,)], [(0,)])
    solutions = classical_solve(puzzle)
    assert len(solutions) == 1
    _verify_solution(solutions[0], puzzle[0], puzzle[1])


# ── 2×2 puzzles ─────────────────────────────────────────────────────────────


def test_2x2_all_filled():
    puzzle = ([(2,), (2,)], [(2,), (2,)])
    solutions = classical_solve(puzzle)
    assert len(solutions) == 1
    _verify_solution(solutions[0], puzzle[0], puzzle[1])


def test_2x2_all_empty():
    puzzle = ([(0,), (0,)], [(0,), (0,)])
    solutions = classical_solve(puzzle)
    assert len(solutions) == 1
    _verify_solution(solutions[0], puzzle[0], puzzle[1])


def test_2x2_diagonal():
    """Diagonal puzzle has exactly 2 solutions."""
    puzzle = ([(1,), (1,)], [(1,), (1,)])
    solutions = classical_solve(puzzle)
    assert len(solutions) == 2
    for sol in solutions:
        _verify_solution(sol, puzzle[0], puzzle[1])


def test_2x2_top_row_filled():
    puzzle = ([(2,), (0,)], [(1,), (1,)])
    solutions = classical_solve(puzzle)
    assert len(solutions) == 1
    _verify_solution(solutions[0], puzzle[0], puzzle[1])


# ── 3×3 puzzles ─────────────────────────────────────────────────────────────


def test_3x3_unique_solution():
    """L-shape puzzle: unique solution."""
    # ■□□
    # ■□□
    # ■■■
    puzzle = ([(1,), (1,), (3,)], [(3,), (1,), (1,)])
    solutions = classical_solve(puzzle)
    assert len(solutions) == 1
    _verify_solution(solutions[0], puzzle[0], puzzle[1])


def test_3x3_checkerboard():
    """Checkerboard-like puzzle with alternating clues."""
    # ■□■
    # □■□
    # ■□■
    puzzle = ([(1, 1), (1,), (1, 1)], [(1, 1), (1,), (1, 1)])
    solutions = classical_solve(puzzle)
    assert len(solutions) == 1
    _verify_solution(solutions[0], puzzle[0], puzzle[1])


def test_3x3_all_filled():
    puzzle = ([(3,), (3,), (3,)], [(3,), (3,), (3,)])
    solutions = classical_solve(puzzle)
    assert len(solutions) == 1
    _verify_solution(solutions[0], puzzle[0], puzzle[1])


def test_3x3_multiple_solutions():
    """Puzzle with multiple valid solutions — verify all satisfy constraints."""
    # Row clues (1,) (1,) (1,) — one block of 1 in each row
    # Col clues (1,) (1,) (1,) — one block of 1 in each column
    # This is a permutation matrix — exactly 6 solutions (3! = 6 not all valid)
    puzzle = ([(1,), (1,), (1,)], [(1,), (1,), (1,)])
    solutions = classical_solve(puzzle)
    assert len(solutions) >= 2, "Should have multiple solutions"
    for sol in solutions:
        _verify_solution(sol, puzzle[0], puzzle[1])


# ── Rectangular puzzles ──────────────────────────────────────────────────────


def test_2x3_rectangular():
    """2 rows, 3 columns — two valid solutions."""
    puzzle = ([(2,), (2,)], [(1,), (2,), (1,)])
    solutions = classical_solve(puzzle)
    assert len(solutions) == 2
    for sol in solutions:
        _verify_solution(sol, puzzle[0], puzzle[1])


def test_3x2_rectangular():
    """3 rows, 2 columns."""
    # ■■
    # □□
    # ■■
    puzzle = ([(2,), (0,), (2,)], [(1, 1), (1, 1)])
    solutions = classical_solve(puzzle)
    assert len(solutions) == 1
    _verify_solution(solutions[0], puzzle[0], puzzle[1])


# ── No-solution puzzles ──────────────────────────────────────────────────────


def test_impossible_puzzle_returns_empty():
    """Contradictory clues should yield no solutions."""
    # Row says all filled, column says all empty
    puzzle = ([(2,), (2,)], [(0,), (0,)])
    solutions = classical_solve(puzzle)
    assert solutions == []


# ── manual_check path ────────────────────────────────────────────────────────


def test_manual_check_valid_solution():
    """manual_check with a known-valid bitstring returns it."""
    puzzle = ([(1,)], [(1,)])
    # variable 0 = cell (0,0), reversed bitstring "1"
    solutions = classical_solve(puzzle, manual_check="1")
    assert solutions == ["1"]


def test_manual_check_invalid_solution():
    """manual_check with an invalid bitstring returns empty."""
    puzzle = ([(1,)], [(1,)])
    solutions = classical_solve(puzzle, manual_check="0")
    assert solutions == []


# ── Edge case: fully determined by one constraint ────────────────────────────


def test_single_row_single_col():
    """1×N grid is fully determined by the single row clue."""
    # 1×3 grid: row clue (1,1), col clues (1,)(0,)(1,)
    puzzle = ([(1, 1)], [(1,), (0,), (1,)])
    solutions = classical_solve(puzzle)
    assert len(solutions) == 1
    _verify_solution(solutions[0], puzzle[0], puzzle[1])


# ── All solutions of every size satisfy constraints ──────────────────────────


@pytest.mark.parametrize(
    "row_clues,col_clues",
    [
        ([(1,)], [(1,)]),
        ([(0,)], [(0,)]),
        ([(2,), (0,)], [(1,), (1,)]),
        ([(1, 1), (1,), (1, 1)], [(1, 1), (1,), (1, 1)]),
    ],
    ids=["1x1-filled", "1x1-empty", "2x2-mixed", "3x3-checker"],
)
def test_all_solutions_satisfy_constraints(row_clues, col_clues):
    """Every solution from the classical solver must satisfy all clues."""
    puzzle = (row_clues, col_clues)
    solutions = classical_solve(puzzle)
    for sol in solutions:
        _verify_solution(sol, row_clues, col_clues)
