"""The clue-checking oracle marks what the clues accept, and nothing else."""

from __future__ import annotations

import math

import pytest

from nonogram.classical import classical_solve
from nonogram.clue_oracle import clue_oracle_circuit

pytest.importorskip("qiskit")


def _grover(row_clues, col_clues, iterations):
    """Grover over the clue oracle: flags above the cells, textbook diffuser below."""
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import ZGate

    oracle = clue_oracle_circuit(row_clues, col_clues)
    cells = len(row_clues) * len(col_clues)
    qc = QuantumCircuit(oracle.num_qubits)
    qc.h(range(cells))
    for _ in range(iterations):
        qc.compose(oracle, inplace=True)
        qc.h(range(cells))
        qc.x(range(cells))
        qc.append(ZGate().control(cells - 1), list(range(cells)))
        qc.x(range(cells))
        qc.h(range(cells))
    return qc, cells


# One board per shape, small enough to hold a statevector.
BOARDS = [
    ([(1,), (1,)], [(1,), (1,)]),
    ([(1,), (1,)], [(1,), (0,), (1,)]),
    ([(1,), (3,), (1,)], [(1,), (3,), (1,)]),
]


@pytest.mark.parametrize("row_clues,col_clues", BOARDS)
def test_amplifies_exactly_the_solutions(row_clues, col_clues):
    """After the ideal number of rounds, the solutions carry the textbook probability.

    An oracle that marked the wrong set, or left a flag qubit entangled with the cells,
    would miss this by far more than the tolerance.
    """
    from qiskit.quantum_info import Statevector

    solutions = classical_solve((row_clues, col_clues))
    cells = len(row_clues) * len(col_clues)
    marked = len(solutions)
    rounds = math.floor(math.pi / 4 * math.sqrt(2**cells / marked))

    circuit, _ = _grover(row_clues, col_clues, rounds)
    probabilities = Statevector(circuit).probabilities(range(cells))
    found = sum(probabilities[int(bits[::-1], 2)] for bits in solutions)

    theta = math.asin(math.sqrt(marked / 2**cells))
    assert found == pytest.approx(math.sin((2 * rounds + 1) * theta) ** 2, abs=1e-9)


def test_costs_the_clues_rather_than_the_answers():
    """The gate count is set by the patterns the clues allow, not by the solution count.

    This is the property the answer-marking oracle lacks: its cost rises with the number
    of solutions, because it carries one marked grid per solution. Here the count is one
    multi-controlled X per legal line pattern, twice, plus the phase flip -- a figure that
    can be read off the clues before anyone solves the puzzle.
    """
    from nonogram.data import _generate_patterns

    row_clues, col_clues = [(1,), (1,), (1,)], [(1,), (1,), (1,)]
    assert len(classical_solve((row_clues, col_clues))) > 1

    circuit = clue_oracle_circuit(row_clues, col_clues)
    patterns = sum(len(_generate_patterns(3, clue)) for clue in row_clues + col_clues)
    assert circuit.size() == 2 * patterns + 1


def test_restores_the_flag_qubits():
    """The flags come back down, so the gate is a phase oracle on the cells alone."""
    from qiskit.quantum_info import Statevector

    row_clues, col_clues = BOARDS[0]
    cells = len(row_clues) * len(col_clues)
    circuit = clue_oracle_circuit(row_clues, col_clues)
    state = Statevector.from_int(0, 2**circuit.num_qubits).evolve(circuit)
    # Every flag qubit is back in |0>, so no amplitude sits outside the cell register.
    flags = state.probabilities(range(cells, circuit.num_qubits))
    assert flags[0] == pytest.approx(1.0, abs=1e-12)
