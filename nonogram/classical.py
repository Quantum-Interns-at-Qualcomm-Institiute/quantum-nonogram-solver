"""
Classical brute-force solver for nonogram puzzles.

This module implements an exhaustive search that evaluates all 2^(n*d) possible
grid configurations and returns those that satisfy all row and column constraints.
It is suitable for small puzzles (up to ~20 variables) but becomes impractical
for larger grids due to exponential search space.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nonogram.core import puzzle_to_boolean


@dataclass
class ExecutionCounts:
    """Tracks function execution counts during classical brute-force solving.

    These counts provide fine-grained instrumentation of the brute-force search,
    allowing direct comparison of algorithmic work against quantum oracle calls.
    """

    candidates_evaluated: int = 0
    """Total candidate configurations tested."""

    clause_evaluations: int = 0
    """Total constraint clauses evaluated (one per row/column per candidate)."""

    subclause_evaluations: int = 0
    """Total subclauses evaluated (one per valid pattern per clause)."""

    literal_evaluations: int = 0
    """Total individual literal (variable) evaluations."""

    constraint_checks: int = 0
    """Total constraint checks = clause_evaluations (alias for clarity)."""

    early_terminations: int = 0
    """Candidates rejected before evaluating all clauses (short-circuit)."""

    solutions_found: int = 0
    """Number of satisfying assignments found."""

    @property
    def literals_per_candidate(self) -> float:
        """Average literal evaluations per candidate."""
        if self.candidates_evaluated == 0:
            return 0.0
        return self.literal_evaluations / self.candidates_evaluated

    @property
    def clauses_per_candidate(self) -> float:
        """Average clause evaluations per candidate."""
        if self.candidates_evaluated == 0:
            return 0.0
        return self.clause_evaluations / self.candidates_evaluated


def classical_solve(
    puzzle: tuple[list, list],
    manual_check: str | None = None,
    verbose: bool = False,
    collect_counts: bool = False,
) -> list[str] | tuple[list[str], ExecutionCounts]:
    """Solve a nonogram by exhaustive brute-force search.

    Evaluates all 2^(n*d) possible grid configurations and returns those
    that satisfy all row and column constraints. Useful for small puzzles,
    validation, and benchmarking against quantum solvers.

    Parameters
    ----------
    puzzle : tuple[list, list]
        (row_clues, col_clues) where each clue is a list/tuple of block lengths.
    manual_check : str, optional
        If provided, evaluate only this single bitstring (e.g., for solution validation)
        instead of searching exhaustively. String should be '0'/'1' characters.
    verbose : bool, optional
        If True, print detailed clause and subclause evaluation for debugging.
    collect_counts : bool, optional
        If True, return (solutions, ExecutionCounts) instead of just solutions.

    Returns
    -------
    list[str] or tuple[list[str], ExecutionCounts]
        List of satisfying bitstring assignments, each as a '0'/'1' string.
        Bitstrings are in variable order (reversed relative to row-major grid).
        For visualization, reverse the string before grid reconstruction.
        If collect_counts=True, also returns an ExecutionCounts dataclass.

    Complexity
    ----------
    Time: O(2^(n*d) · C) where n×d is grid size and C is constraint complexity.
    Space: O(C) for constraint storage, O(solutions) for result list.

    Example
    -------
    >>> puzzle = ([(1,), (1,)], [(1,), (1,)])  # 2×2 puzzle
    >>> solutions = classical_solve(puzzle)
    >>> len(solutions)  # Should be 2 (diagonal patterns)
    2
    """
    expression, var_num = puzzle_to_boolean(
        row_clues=puzzle[0], col_clues=puzzle[1], classical=True
    )

    search_space = (manual_check,) if manual_check is not None else range(2**var_num)
    solutions: list[str] = []
    counts = ExecutionCounts() if collect_counts else None

    for candidate in search_space:
        if manual_check is not None:
            configuration = manual_check
        else:
            configuration = bin(candidate)[2:].zfill(var_num)[::-1]

        if counts is not None:
            counts.candidates_evaluated += 1

        expression_value = True
        for clause in expression:
            if counts is not None:
                counts.clause_evaluations += 1
                counts.constraint_checks += 1

            clause_value = False
            if verbose:
                print(f"Clause: {clause}")
            for subclause in clause:
                if counts is not None:
                    counts.subclause_evaluations += 1

                subclause_value = True
                if verbose:
                    print(f"  Subclause: {subclause}")
                for literal in subclause:
                    if counts is not None:
                        counts.literal_evaluations += 1

                    index = abs(literal)
                    config_value = configuration[index - 1 : index]
                    truth_value = config_value == "0"
                    negated = literal < 0
                    literal_value = not truth_value if negated else truth_value
                    subclause_value &= literal_value
                    if verbose:
                        print(
                            f"    literal={literal} index={index} "
                            f"config={config_value} truth={truth_value} "
                            f"negated={negated} value={literal_value} "
                            f"subclause_so_far={subclause_value}"
                        )
                clause_value |= subclause_value
                if verbose:
                    print(f"  clause_value: {clause_value}")
            expression_value &= clause_value
            if not expression_value:
                if counts is not None:
                    counts.early_terminations += 1
                break
            if verbose:
                print(f"expression_value: {expression_value}")

        if expression_value:
            solutions.append(configuration)
            if counts is not None:
                counts.solutions_found += 1

    if collect_counts:
        return solutions, counts
    return solutions
