"""A phase oracle that tests each clue with a reversible run-length automaton.

The other two oracles in this package enumerate. ``PhaseOracleGate`` reduces the clue
formula over all ``2^n`` grids and emits one multi-controlled Z per solution, so its size
tracks the solution count. ``clue_oracle`` emits one multi-controlled X per filling a line
allows, so its size tracks ``C(w - sum(b) + 1, k)`` per line and grows exponentially in the
line width ``w``.

This one reads a line a cell at a time. Each clue defines a deterministic automaton over
``sum(b) + k`` states, laid out as the shortest line the clue accepts:

    E = 1^b_1 0 1^b_2 0 ... 0 1^b_k

State ``p`` means ``p`` characters of ``E`` are matched. A cell either advances the state,
leaves it alone, or breaks the clue:

* ``start``  -- the next character is the first ``1`` of a block: a ``1`` advances, a ``0``
  is another leading or separating empty cell and changes nothing.
* ``inside`` -- the next character is a later ``1`` of a block: a ``1`` advances, a ``0``
  ends the block early and breaks the clue.
* ``gap``    -- the next character is the mandatory ``0`` between two blocks: a ``0``
  advances, a ``1`` runs two blocks together and breaks the clue.
* ``done``   -- every block is placed: a ``0`` is a trailing empty cell, a ``1`` is a block
  too many and breaks the clue.

The automaton is not reverse-deterministic: a ``0`` read in a ``gap`` state and a ``0`` read
in the ``start`` state after it both land on the same state, so one bit per cell is needed
to say which happened. The circuit keeps that bit, holds the count of broken rules in a
binary register instead of collapsing it to a flag, and so runs as a permutation on
``(state, count, advance bits)``. The line's flag is raised when the state register is
``done`` and the count register is zero, after which the whole scan runs backwards and
returns the state, count and advance bits to zero. One workspace therefore serves every
line in turn, and only the flags accumulate.

Size is ``O(w)`` gates per cell and ``O(w^2)`` per line, against a pattern count
exponential in ``w``, and every gate carries at most ``O(log w)`` controls. Nothing here
reads a solution: the gate pattern of a line follows from its clue and its width.
"""

from __future__ import annotations

from nonogram.core import var_clauses
from nonogram.errors import ValidationError

#: What the automaton expects of the next cell, per state.
_START, _INSIDE, _GAP, _DONE = "start", "inside", "gap", "done"


def _template(clue: tuple[int, ...]) -> str:
    """The shortest line the clue accepts: each block, separated by one empty cell."""
    blocks = [b for b in clue if b]
    return "0".join("1" * b for b in blocks)


def _state_classes(clue: tuple[int, ...]) -> list[str]:
    """One entry per automaton state, saying what the next cell must be."""
    template = _template(clue)
    classes = []
    for position in range(len(template) + 1):
        if position == len(template):
            classes.append(_DONE)
        elif template[position] == "0":
            classes.append(_GAP)
        elif position == 0 or template[position - 1] == "0":
            classes.append(_START)
        else:
            classes.append(_INSIDE)
    return classes


def _advances(state_class: str, cell: int) -> bool:
    """Whether this cell moves the automaton on one state."""
    return state_class in (_START, _INSIDE) if cell else state_class == _GAP


def _breaks(state_class: str, cell: int) -> bool:
    """Whether this cell contradicts the clue."""
    return state_class in (_GAP, _DONE) if cell else state_class == _INSIDE


def _counter_width(width: int) -> int:
    """Bits that hold a count of broken rules without wrapping back to zero."""
    return max(1, width.bit_length())


def line_states(clue: tuple[int, ...]) -> int:
    """How many states the automaton for this clue has, at most one more than the width."""
    return len(_state_classes(clue))


def line_workspace(width: int, clue: tuple[int, ...]) -> tuple[int, int, int]:
    """``(states, advance bits, counter bits)`` one line of this width and clue needs."""
    return line_states(clue), width, _counter_width(width)


def _scan(width: int, clue: tuple[int, ...]):
    """The forward pass over one line, as a circuit on that line's qubits and workspace.

    Qubit order is the line's cells, then the state register, the advance bits, the counter
    and one qubit the broken-rule condition is written to and taken off again.
    """
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import CSwapGate, MCXGate

    classes = _state_classes(clue)
    states, advance_bits, counter_bits = line_workspace(width, clue)

    cells = list(range(width))
    state = [width + i for i in range(states)]
    advance = [width + states + i for i in range(advance_bits)]
    counter = [width + states + advance_bits + i for i in range(counter_bits)]
    condition = width + states + advance_bits + counter_bits
    qc = QuantumCircuit(condition + 1, name="line scan")

    def rule_gates(cell: int, target: int, test) -> None:
        """One gate per (state, cell value) the test accepts; the states are exclusive."""
        for position, state_class in enumerate(classes):
            for value in (0, 1):
                if test(state_class, value):
                    # Control bit 0 is the cell, bit 1 the state slot.
                    qc.append(MCXGate(2, ctrl_state=value | 0b10), [cell, state[position], target])

    qc.x(state[0])
    for step, cell in enumerate(cells):
        rule_gates(cell, advance[step], _advances)
        rule_gates(cell, condition, _breaks)
        # One more broken rule, as a ripple increment over the counter.
        for bit in range(counter_bits - 1, 0, -1):
            qc.append(MCXGate(bit + 1), [condition, *counter[:bit], counter[bit]])
        qc.cx(condition, counter[0])
        rule_gates(cell, condition, _breaks)
        # The occupied slot moves up one. Running down the register visits it once.
        for position in range(states - 2, -1, -1):
            qc.append(CSwapGate(), [advance[step], state[position], state[position + 1]])
    return qc


def _line_block(width: int, clue: tuple[int, ...]):
    """One line's flag, computed and the workspace cleared again.

    Qubit order is the line's cells, its flag, then the workspace ``_scan`` takes. The block
    is its own inverse, so applying it a second time lowers the flag.
    """
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import MCXGate

    if len(_template(clue)) > width:
        shortest = len(_template(clue))
        raise ValidationError(
            f"clue {list(clue)} needs at least {shortest} cells but the line is {width} long."
        )

    states, advance_bits, counter_bits = line_workspace(width, clue)
    scan = _scan(width, clue)
    qc = QuantumCircuit(scan.num_qubits + 1, name="line automaton")

    # The flag sits between the cells and the workspace.
    scan_qubits = [*range(width), *range(width + 1, qc.num_qubits)]
    state_end = width + 1 + states - 1
    counter = [width + 1 + states + advance_bits + i for i in range(counter_bits)]

    qc.compose(scan, qubits=scan_qubits, inplace=True)
    # The clue holds when every block is placed and the broken-rule count is zero: control
    # bit 0 is the last state slot, the rest are the counter's bits at zero.
    qc.append(MCXGate(1 + counter_bits, ctrl_state=1), [state_end, *counter, width])
    qc.compose(scan.inverse(), qubits=scan_qubits, inplace=True)
    return qc


def _lines(
    row_clues: list[tuple[int, ...]], col_clues: list[tuple[int, ...]]
) -> list[tuple[list[int], tuple[int, ...]]]:
    """Every row and column, as the cell indices it covers and the clue it must match."""
    row_vars, col_vars = var_clauses(len(row_clues), len(col_clues))
    return [(row_vars[r], tuple(clue)) for r, clue in enumerate(row_clues)] + [
        (col_vars[c], tuple(clue)) for c, clue in enumerate(col_clues)
    ]


def automaton_oracle_layout(
    row_clues: list[tuple[int, ...]], col_clues: list[tuple[int, ...]]
) -> dict[str, list[int]]:
    """Which qubits hold the cells, the flags and each part of the shared workspace."""
    lines = _lines(row_clues, col_clues)
    cells = len(row_clues) * len(col_clues)
    sizes = [line_workspace(len(qubits), clue) for qubits, clue in lines]
    states = max(size[0] for size in sizes)
    advance_bits = max(size[1] for size in sizes)
    counter_bits = max(size[2] for size in sizes)

    start = cells + len(lines)
    layout = {
        "cells": list(range(cells)),
        "flags": list(range(cells, start)),
        "state": list(range(start, start + states)),
        "advance": list(range(start + states, start + states + advance_bits)),
        "counter": list(
            range(
                start + states + advance_bits,
                start + states + advance_bits + counter_bits,
            )
        ),
    }
    layout["condition"] = [start + states + advance_bits + counter_bits]
    return layout


def automaton_oracle_circuit(
    row_clues: list[tuple[int, ...]], col_clues: list[tuple[int, ...]]
):
    """The oracle as a circuit over the cell qubits, one flag per line and one workspace.

    Parameters
    ----------
    row_clues, col_clues : list[tuple[int, ...]]
        Block lengths per line, as ``puzzle_to_boolean`` takes them.

    Returns
    -------
    qiskit.QuantumCircuit
        ``rows * cols`` cell qubits, then one flag per line, then the workspace every line
        reuses. Flags and workspace come back as they were found, so the gate is a phase
        oracle on the cell register alone.

    Raises
    ------
    ValidationError
        If a clue needs more cells than its line has.
    """
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import ZGate

    layout = automaton_oracle_layout(row_clues, col_clues)
    lines = _lines(row_clues, col_clues)
    qc = QuantumCircuit(layout["condition"][0] + 1, name="automaton oracle")

    def mark() -> None:
        for flag, (qubits, clue) in zip(layout["flags"], lines):
            states, advance_bits, counter_bits = line_workspace(len(qubits), clue)
            qc.compose(
                _line_block(len(qubits), clue),
                qubits=[
                    *qubits,
                    flag,
                    *layout["state"][:states],
                    *layout["advance"][:advance_bits],
                    *layout["counter"][:counter_bits],
                    *layout["condition"],
                ],
                inplace=True,
            )

    mark()
    qc.append(ZGate().control(len(lines) - 1), layout["flags"])
    mark()
    return qc


def automaton_oracle_gate(
    row_clues: list[tuple[int, ...]], col_clues: list[tuple[int, ...]]
):
    """The same oracle as a single gate, for composing into a Grover operator."""
    return automaton_oracle_circuit(row_clues, col_clues).to_gate(label="automaton oracle")
