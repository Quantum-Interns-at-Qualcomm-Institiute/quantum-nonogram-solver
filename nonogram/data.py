"""
Precomputed lookup table for nonogram constraint satisfiability.

This module provides a lookup table ``possible_d`` that maps nonogram clues
to all valid bitstring configurations. It is used by the SAT encoding in
``nonogram.core.puzzle_to_boolean`` to quickly enumerate the valid patterns
for each row and column constraint.

**Data format:**
  - Key: ``"length/clue_1;clue_2;...;"`` (e.g., ``"4/1;2;"`` for a 4-cell line with clues 1 and 2)
  - Value: List of valid bitstring configurations as integers (bit index 0 = leftmost cell)

**Coverage:** Line lengths 1–10 (supports up to 10×10 nonogram puzzles)

**Example:**

    >>> from nonogram.data import possible_d
    >>> possible_d["3/1;1;"]  # 3-cell line with blocks of 1, 1
    [0b101]  # only one valid pattern: filled, empty, filled

The lookup table is precomputed at module load time for O(1) constraint lookup
during SAT formula generation, avoiding expensive runtime pattern generation.
"""

from nonogram.errors import ValidationError


def _generate_patterns(line_len: int, clue: tuple[int, ...]) -> list[int]:
    """Generate all valid bitstring patterns for a line of given length and clue.

    Uses recursive placement: for each block in the clue, try all valid starting
    positions, then recurse for the remaining blocks in the remaining space.

    Parameters
    ----------
    line_len : int
        Number of cells in the line.
    clue : tuple[int, ...]
        Block lengths for this line. (0,) means all empty.

    Returns
    -------
    list[int]
        Valid bitstring patterns as integers (bit index 0 = leftmost cell).
    """
    if clue == (0,) or not clue:
        return [0]

    results: list[int] = []

    def _place(block_idx: int, start: int, pattern: int) -> None:
        if block_idx == len(clue):
            results.append(pattern)
            return

        block_len = clue[block_idx]
        remaining_blocks = clue[block_idx + 1 :]
        min_remaining = sum(remaining_blocks) + len(remaining_blocks)

        for pos in range(start, line_len - block_len - min_remaining + 1):
            bits = 0
            for b in range(block_len):
                bits |= 1 << pos + b
            _place(block_idx + 1, pos + block_len + 1, pattern | bits)

    _place(0, 0, 0)
    return results


def _generate_all_clues(line_len: int) -> list[tuple[int, ...]]:
    """Generate all valid clue combinations for a line of given length.

    A valid clue for a line of length L is any sequence of positive integers
    (b1, b2, ..., bk) such that sum(bi) + (k-1) <= L, plus the empty clue (0,).
    """
    clues: list[tuple[int, ...]] = [(0,)]

    def _recurse(remaining: int, current: list[int]) -> None:
        if current:
            clues.append(tuple(current))
        for block in range(1, remaining + 1):
            current.append(block)
            new_remaining = remaining - block - 1
            if new_remaining >= 0:
                _recurse(new_remaining, current)
            elif new_remaining == -1:
                clues.append(tuple(current))
            current.pop()

    _recurse(line_len, [])
    return clues


def _build_lookup_table(max_line_len: int = 10) -> dict[str, list[int]]:
    """Build the complete lookup table for line lengths 1 through max_line_len."""
    table: dict[str, list[int]] = {}
    for length in range(1, max_line_len + 1):
        for clue in _generate_all_clues(length):
            key = f"{length}/{';'.join(map(str, clue))};"
            patterns = _generate_patterns(length, clue)
            if patterns:
                table[key] = patterns
    return table


def valid_line_configs(line_len: int, clue: tuple[int, ...]) -> int:
    """Return the number of valid configurations for a single line constraint.

    Parameters
    ----------
    line_len : int
        Number of cells in the line.
    clue : tuple[int, ...]
        Block lengths for this line.

    Returns
    -------
    int
        Number of valid bitstring patterns that satisfy the clue.

    Raises
    ------
    ValidationError
        If the clue is not compatible with the line length.
    """
    key = f"{line_len}/{';'.join(map(str, clue))};"
    if key in possible_d:
        return len(possible_d[key])
    min_cells = sum(clue) + len(clue) - 1 if clue != (0,) else 0
    if min_cells > line_len:
        raise ValidationError(
            f"Clue {list(clue)} requires at least {min_cells} cells "
            f"but the line is only {line_len} long."
        )
    patterns = _generate_patterns(line_len, clue)
    return len(patterns)


def constraint_density(
    row_clues: list[tuple[int, ...]],
    col_clues: list[tuple[int, ...]],
) -> dict:
    """Compute constraint density metrics from a puzzle's clue structure.

    For each row and column clue, computes the number of valid line
    configurations. Aggregates into overall constraint density metrics that
    characterize puzzle difficulty.

    Parameters
    ----------
    row_clues : list[tuple[int, ...]]
        List of row clues.
    col_clues : list[tuple[int, ...]]
        List of column clues.

    Returns
    -------
    dict
        Constraint density metrics:
        - row_configs: list of valid config counts per row
        - col_configs: list of valid config counts per column
        - total_configs: sum of all valid configs
        - mean_configs: average valid configs per line
        - min_configs: minimum valid configs across all lines
        - max_configs: maximum valid configs across all lines
        - search_space: 2^(rows*cols) total possible configurations
        - density_ratio: total_configs / (num_lines * search_space_per_line)
    """
    n = len(row_clues)
    d = len(col_clues)

    row_configs = [valid_line_configs(d, clue) for clue in row_clues]
    col_configs = [valid_line_configs(n, clue) for clue in col_clues]

    all_configs = row_configs + col_configs
    total = sum(all_configs)
    num_lines = n + d

    return {
        "row_configs": row_configs,
        "col_configs": col_configs,
        "total_configs": total,
        "mean_configs": total / num_lines if num_lines else 0,
        "min_configs": min(all_configs) if all_configs else 0,
        "max_configs": max(all_configs) if all_configs else 0,
        "search_space": 2 ** (n * d),
        "density_ratio": total / (num_lines * (2 ** max(n, d))) if num_lines else 0,
    }


possible_d: dict[str, list[int]] = _build_lookup_table(10)
