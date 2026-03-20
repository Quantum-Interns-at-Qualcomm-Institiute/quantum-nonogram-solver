"""
Classical brute-force solver for nonogram puzzles.

This module implements an exhaustive search that evaluates all 2^(n*d) possible
grid configurations and returns those that satisfy all row and column constraints.
It is suitable for small puzzles (up to ~20 variables) but becomes impractical
for larger grids due to exponential search space.
"""

from nonogram.core import puzzle_to_boolean


def classical_solve(
    puzzle: tuple[list, list],
    manual_check: str | None = None,
    verbose: bool = False,
) -> list[str]:
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

    Returns
    -------
    list[str]
        List of satisfying bitstring assignments, each as a '0'/'1' string.
        Bitstrings are in variable order (reversed relative to row-major grid).
        For visualization, reverse the string before grid reconstruction.

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

    for candidate in search_space:
        if manual_check is not None:
            configuration = manual_check
        else:
            configuration = bin(candidate)[2:].zfill(var_num)[::-1]

        expression_value = True
        for clause in expression:
            clause_value = False
            if verbose:
                print(f"Clause: {clause}")
            for subclause in clause:
                subclause_value = True
                if verbose:
                    print(f"  Subclause: {subclause}")
                for literal in subclause:
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
            if verbose:
                print(f"expression_value: {expression_value}")

        if expression_value:
            solutions.append(configuration)

    return solutions
