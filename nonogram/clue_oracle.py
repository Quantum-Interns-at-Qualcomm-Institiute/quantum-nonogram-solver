"""A phase oracle that tests the clues, rather than one that holds the answers.

``puzzle_to_boolean`` hands Qiskit a formula, and ``PhaseOracleGate`` reduces it over the
full 2^n truth table into one multi-controlled Z per satisfying grid. The resulting
circuit costs what it costs because it already knows the answers: its gate count tracks
the solution count, and no part of it reads a clue.

This builds the other kind. One flag qubit per line, raised by one multi-controlled X per
pattern that line's clue allows; a phase flip conditioned on every flag; then the same
pattern gates again to lower the flags. Legal patterns for one line are mutually
exclusive, so toggling a flag once per matching pattern is an OR. Nothing here depends on
which grids satisfy the whole puzzle, and the circuit is built from the clues in
milliseconds rather than from an enumeration of the grid space.

It costs more — at 3x3 about four times the gates of the answer-marking form — which is
the point: it is what an oracle that does not hold the answer actually costs.
"""

from __future__ import annotations

from nonogram.data import _generate_patterns


def _lines(
    row_clues: list[tuple[int, ...]], col_clues: list[tuple[int, ...]]
) -> list[tuple[list[int], tuple[int, ...]]]:
    """Every row and column, as the cell indices it covers and the clue it must match."""
    rows, cols = len(row_clues), len(col_clues)
    lines: list[tuple[list[int], tuple[int, ...]]] = []
    for r in range(rows):
        lines.append(([r * cols + c for c in range(cols)], tuple(row_clues[r])))
    for c in range(cols):
        lines.append(([r * cols + c for r in range(rows)], tuple(col_clues[c])))
    return lines


def clue_oracle_circuit(row_clues: list[tuple[int, ...]], col_clues: list[tuple[int, ...]]):
    """The oracle as a circuit over cell qubits followed by one flag qubit per line.

    Parameters
    ----------
    row_clues, col_clues : list[tuple[int, ...]]
        Block lengths per line, as ``puzzle_to_boolean`` takes them.

    Returns
    -------
    qiskit.QuantumCircuit
        ``rows * cols`` cell qubits, then ``rows + cols`` flag qubits. The flags come back
        as they were found, so the gate is a phase oracle on the cell register alone.
    """
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import MCXGate, ZGate

    rows, cols = len(row_clues), len(col_clues)
    cells = rows * cols
    lines = _lines(row_clues, col_clues)
    qc = QuantumCircuit(cells + len(lines), name="clue oracle")

    def mark() -> None:
        for flag, (qubits, clue) in enumerate(lines):
            for pattern in _generate_patterns(len(qubits), clue):
                # _generate_patterns and ctrl_state both put the leftmost cell in bit 0.
                qc.append(MCXGate(len(qubits), ctrl_state=pattern), qubits + [cells + flag])

    mark()
    qc.append(ZGate().control(len(lines) - 1), [cells + i for i in range(len(lines))])
    mark()
    return qc


def clue_oracle_gate(row_clues: list[tuple[int, ...]], col_clues: list[tuple[int, ...]]):
    """The same oracle as a single gate, for composing into a Grover operator."""
    return clue_oracle_circuit(row_clues, col_clues).to_gate(label="clue oracle")
