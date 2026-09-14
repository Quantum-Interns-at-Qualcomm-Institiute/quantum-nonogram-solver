"""Noiseless Grover success probabilities for the puzzles the README documents."""

import re
from pathlib import Path

import pytest

from nonogram.classical import classical_solve
from nonogram.quantum import grover_success_probability

PUZZLES = {
    "2×2 all-2s": ([(2,), (2,)], [(2,), (2,)]),
    "3×3 all-3s": ([(3,), (3,), (3,)], [(3,), (3,), (3,)]),
}
# Percentages to one decimal place, as the README table shows them.
EXPECTED = {
    "2×2 all-2s": {1: 47.3, 3: 96.1, 5: 12.5, 9: 99.2},
    "3×3 all-3s": {1: 1.7, 3: 9.3, 5: 21.8, 9: 55.4},
}
README = Path(__file__).resolve().parent.parent / "README.md"


def search_space(puzzle: tuple[list, list]) -> tuple[int, int]:
    rows, cols = puzzle
    return len(classical_solve(puzzle)), 2 ** (len(rows) * len(cols))


@pytest.mark.parametrize("name", PUZZLES)
def test_documented_puzzles_have_one_solution(name):
    n_solutions, _ = search_space(PUZZLES[name])
    assert n_solutions == 1


@pytest.mark.parametrize(("name", "k"), [(n, k) for n in EXPECTED for k in EXPECTED[n]])
def test_probability_matches_documented_value(name, k):
    n_solutions, n_states = search_space(PUZZLES[name])
    percent = 100 * grover_success_probability(k, n_solutions, n_states)
    assert round(percent, 1) == EXPECTED[name][k]


def test_probability_is_periodic_in_iterations():
    # Past the optimum (k ≈ 3 for 16 states) the amplitude rotates away again.
    assert grover_success_probability(5, 1, 16) < grover_success_probability(3, 1, 16)


@pytest.mark.parametrize("name", EXPECTED)
def test_readme_table_matches_formula(name):
    row = next(line for line in README.read_text().splitlines() if line.startswith(f"| {name} "))
    documented = [float(v) for v in re.findall(r"(\d+\.\d)%", row)]
    assert documented == list(EXPECTED[name].values())
