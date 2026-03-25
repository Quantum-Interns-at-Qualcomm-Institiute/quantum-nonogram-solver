"""
Core SAT encoding and puzzle manipulation for nonogram solving.

This module provides:

  - **Variable indexing**: Map grid cells to boolean variables for SAT formulas
  - **Validation**: Check that puzzle dimensions and clues are consistent
  - **Display**: Render solved grids in ASCII box-drawing format
  - **Grid helpers**: Run-length encode, convert grids to clues, parse clue strings
  - **Boolean SAT encoding**: Convert nonogram puzzles to satisfiability formulas

The SAT formulation is used by both the classical brute-force solver and the
quantum Grover solver. Classical solver receives a CNF clause list; quantum
solver receives a boolean expression string for oracle generation.
"""

import numpy as np

from nonogram.data import possible_d
from nonogram.errors import ValidationError


def var_clauses(n: int, d: int | None = None) -> tuple[list[list[int]], list[list[int]]]:
    """Return (row_vars, col_vars) index lists for an n×d grid.

    Maps each cell in an n×d grid to a boolean variable index (0 to n*d-1).
    Variables are numbered left-to-right, top-to-bottom.

    Parameters
    ----------
    n : int
        Number of rows.
    d : int, optional
        Number of columns. If None, defaults to n (square grid).

    Returns
    -------
    tuple[list[list[int]], list[list[int]]]
        ``(row_vars, col_vars)`` where:
        - ``row_vars[i]`` = list of variable indices for row i
        - ``col_vars[j]`` = list of variable indices for column j

    Example
    -------
    >>> row_vars, col_vars = var_clauses(2, 3)
    >>> row_vars[0]  # row 0, all columns
    [0, 1, 2]
    >>> col_vars[1]  # column 1, all rows
    [1, 4]
    """
    if d is None:
        d = n
    X = np.arange(n * d).reshape((n, d))
    row_vars = [list(X[row, :]) for row in range(n)]
    col_vars = [list(X[:, col]) for col in range(d)]
    return row_vars, col_vars


def validate(rows: int, cols: int, r_clues: list, c_clues: list) -> bool:
    """Validate that puzzle dimensions match clue counts.

    Raises ValueError if the number of row clues does not equal the row count,
    or if the number of column clues does not equal the column count.

    Parameters
    ----------
    rows : int
        Expected number of rows.
    cols : int
        Expected number of columns.
    r_clues : list
        List of row clues (one per row).
    c_clues : list
        List of column clues (one per column).

    Returns
    -------
    bool
        True if validation passes.

    Raises
    ------
    ValidationError
        If clue counts do not match dimensions.
    """
    if len(r_clues) != rows:
        raise ValidationError(
            f"Number of row clues ({len(r_clues)}) does not match row count ({rows})"
        )
    if len(c_clues) != cols:
        raise ValidationError(
            f"Number of col clues ({len(c_clues)}) does not match col count ({cols})"
        )
    return True


def display_nonogram(bit_string: str, n: int, d: int) -> None:
    """Print an ASCII box-drawing representation of the solved grid.

    Uses Unicode box-drawing characters for a clean visual representation.
    Filled cells are shown as '■' and empty cells as '□'.

    Parameters
    ----------
    bit_string : str
        Binary string of length n*d with characters '0' (empty) or '1' (filled).
        Order is row-major: bits 0 to d-1 are row 0, bits d to 2d-1 are row 1, etc.
    n : int
        Number of rows.
    d : int
        Number of columns.

    Raises
    ------
    ValueError
        If bit_string is shorter than n*d.

    Example
    -------
    >>> display_nonogram("1010" "0101", 2, 2)
    ╔══╗
    ║■□║
    ║□■║
    ╚══╝
    """
    if n * d > len(bit_string):
        raise ValidationError(
            f"bit_string length {len(bit_string)} is shorter than grid size {n * d}"
        )

    puzzle_array = np.zeros((n, d))
    for i in range(n):
        for j in range(d):
            puzzle_array[i, j] = int(bit_string[i * d + j])

    print("╔" + "═" * d + "╗")
    for i in range(n):
        row = "║"
        for j in range(d):
            row += "■" if puzzle_array[i, j] else "□"
        row += "║"
        print(row)
    print("╚" + "═" * d + "╝")


# ── Grid helpers (relocated from tools/_widgets.py) ───────────────────────────


def rle(bits: list[bool]) -> tuple[int, ...]:
    """Run-length encode boolean sequence, returning lengths of contiguous True runs.

    This is the inverse operation of the lookup table generation in ``nonogram.data``.
    It converts a binary row/column state to the nonogram clue format (space-separated
    block lengths).

    Parameters
    ----------
    bits : list[bool]
        Boolean sequence representing filled (True) and empty (False) cells.

    Returns
    -------
    tuple[int, ...]
        Lengths of contiguous True groups, in order. Returns (0,) if all bits are False.

    Example
    -------
    >>> rle([True, False, True, True])
    (1, 2)
    >>> rle([False, False, False])
    (0,)
    >>> rle([True, True, True])
    (3,)
    """
    groups: list[int] = []
    count = 0
    for b in bits:
        if b:
            count += 1
        elif count:
            groups.append(count)
            count = 0
    if count:
        groups.append(count)
    return tuple(groups) if groups else (0,)


def grid_to_clues(
    grid: list[list[bool]],
) -> tuple[list[tuple[int, ...]], list[tuple[int, ...]]]:
    """Compute row and column clues from a filled-cell grid.

    This function is the inverse of the solver: given a completed grid, it extracts
    the nonogram clues (block lengths) for each row and column. Useful for
    exporting user-drawn puzzles or validating solved grids.

    Parameters
    ----------
    grid : list[list[bool]]
        2D grid where True = filled cell, False = empty cell.
        Shape: (rows, cols).

    Returns
    -------
    tuple[list[tuple[int, ...]], list[tuple[int, ...]]]
        ``(row_clues, col_clues)`` where each clue is a tuple of contiguous
        block lengths (run-length encoded via :func:`rle`).

    Example
    -------
    >>> grid = [[True, False, True], [False, True, True]]
    >>> row_clues, col_clues = grid_to_clues(grid)
    >>> row_clues
    [(1, 1), (2,)]
    >>> col_clues
    [(1,), (1, 1), (1,)]
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    row_clues = [rle(grid[r]) for r in range(rows)]
    col_clues = [rle([grid[r][c] for r in range(rows)]) for c in range(cols)]
    return row_clues, col_clues


def parse_clue(text: str) -> tuple[int, ...]:
    """Parse a space-separated clue string into a tuple of block lengths.

    Parses user input or file data into the tuple format expected by solvers.
    Gracefully handles empty input and malformed values (returns (0,) for each).

    Parameters
    ----------
    text : str
        Space-separated integers, e.g., ``"1 2 3"`` or ``"2"``.
        Whitespace is trimmed. Empty strings return (0,).

    Returns
    -------
    tuple[int, ...]
        Block lengths, or (0,) if input is empty or all values are invalid.

    Example
    -------
    >>> parse_clue("1 2 3")
    (1, 2, 3)
    >>> parse_clue("")
    (0,)
    >>> parse_clue("  2   1  ")
    (2, 1)
    """
    parts = text.strip().split()
    if not parts:
        return (0,)
    try:
        nums = tuple(int(p) for p in parts)
    except ValueError:
        return (0,)
    return nums if any(n > 0 for n in nums) else (0,)


# ── Boolean SAT encoding ─────────────────────────────────────────────────────


def puzzle_to_boolean(
    row_clues: list[tuple[int, ...]],
    col_clues: list[tuple[int, ...]],
    classical: bool = False,
):
    """Convert a nonogram puzzle to a boolean satisfiability formula.

    Encodes all row and column constraints as a CNF (Conjunctive Normal Form)
    or boolean expression. Each constraint is a disjunction of all valid
    patterns for that row/column, and all constraints must be satisfied.

    Parameters
    ----------
    row_clues : list[tuple[int, ...]]
        List of clue tuples, one per row. Each clue is a tuple of block lengths.
    col_clues : list[tuple[int, ...]]
        List of clue tuples, one per column. Each clue is a tuple of block lengths.
    classical : bool, optional
        If False (default), return a boolean expression string (for quantum oracle).
        If True, return a CNF clause list (for classical SAT solver).

    Returns
    -------
    str or tuple[list, int]
        - If ``classical=False``: boolean expression string with variables v0, v1, ...
          and operators ~, &, | (suitable for Qiskit's PhaseOracleGate)
        - If ``classical=True``: (clause_list, var_num) where each clause is a DNF
          subclause (list of literals as signed integers)

    Notes
    -----
    - Variables are indexed 0 to (n*d - 1) in left-to-right, top-to-bottom order.
    - Bitstring bit index 0 corresponds to the leftmost cell.
    - Constraint lookup uses the ``nonogram.data.possible_d`` precomputed table.

    Example
    -------
    >>> expr = puzzle_to_boolean([(1,)], [(1,)], classical=False)
    >>> # Returns a boolean string like "(v0)&(v0)"
    >>> clauses, vars = puzzle_to_boolean([(1,)], [(1,)], classical=True)
    >>> # Returns (clause_list, 1) where clause_list encodes the constraints
    """
    AND = "&"
    OR = "|"
    VAR = "v"
    NOT = "~"
    END = ";"

    n = len(row_clues)
    d = len(col_clues)

    boolean_statement = ""
    classical_statement: list = []
    r_v, _ = var_clauses(n, d)

    def _literal(bit_set: bool, var_idx: int) -> str:
        prefix = "" if bit_set else NOT
        return f"{prefix}{VAR}{var_idx}{AND}"

    def _classical_literal(bit_set: bool, var_idx: int) -> int:
        return (-1 if bit_set else 1) * (1 + var_idx)

    def _encode_constraint(
        clue: tuple[int, ...],
        line_len: int,
        var_indices: list[int],
        label: str,
    ) -> tuple[str, list]:
        """Encode one row or column constraint into boolean + classical forms.

        Parameters
        ----------
        clue : tuple[int, ...]
            Block lengths for this line.
        line_len : int
            Length of the perpendicular dimension (used for lookup key).
        var_indices : list[int]
            Variable indices for each cell in this line.
        label : str
            Human-readable label for error messages (e.g. "Row 1", "Column 3").
        """
        key = f"{line_len}/{END.join(map(str, clue))}{END}"
        if key not in possible_d:
            min_cells = sum(clue) + len(clue) - 1
            raise ValidationError(
                f"{label} clue {list(clue)} requires at least {min_cells} cells "
                f"but the line is only {line_len} long."
            )
        bitstrings = possible_d[key]
        bool_clauses = []
        cl_clauses = []
        for bitstring in bitstrings:
            clause = ""
            cl_clause = []
            for pos, var_idx in enumerate(var_indices):
                bit_set = bool(bitstring & (1 << pos))
                clause += _literal(bit_set, var_idx)
                cl_clause.append(_classical_literal(bit_set, var_idx))
            bool_clauses.append(f"({clause[:-1]})")
            cl_clauses.append(cl_clause)
        bool_expr = f"({OR.join(bool_clauses)}){AND}"
        return bool_expr, cl_clauses

    # --- row constraints ---
    for r_idx, r_clue in enumerate(row_clues):
        var_indices = [r_v[r_idx][c] for c in range(d)]
        bool_expr, cl_clauses = _encode_constraint(r_clue, d, var_indices, f"Row {r_idx + 1}")
        boolean_statement += bool_expr
        classical_statement.append(cl_clauses)

    # --- column constraints ---
    for c_idx, c_clue in enumerate(col_clues):
        var_indices = [r_v[r][c_idx] for r in range(n)]
        bool_expr, cl_clauses = _encode_constraint(c_clue, n, var_indices, f"Column {c_idx + 1}")
        boolean_statement += bool_expr
        classical_statement.append(cl_clauses)

    boolean_statement = boolean_statement[:-1]  # strip trailing "&"

    if classical:
        return classical_statement, n * d
    return boolean_statement
