"""Measure what a Grover circuit costs on real hardware, for every small board.

Run offline and commit the result; the website reads it as a static asset, so a
visitor gets a hardware figure with no backend and no account.

Why the table is small
----------------------
The cost is set by the grid and by how many solutions the puzzle has, not by which
puzzle it is. ``PhaseOracleGate`` synthesises one multi-controlled term per solution,
so two 3x3 boards with one solution each differ only in which qubits get an X — a
one-qubit gate, which costs nothing to speak of. Measured over all 445 solvable 3x3
boards, the two-qubit count within a solution class is identical and the depth varies
by a tenth of a percent. So one row per (rows, cols, solutions) says everything 445
rows would, and the row carries the observed spread so the claim can be checked.

Usage:
    python -m tools.build_depth_table > depth-table.json
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

MAX_SIDE = 3
#: Transpiler seeds tried per row; the shallowest is kept and the spread recorded. A seed
#: picks between near-tied layouts, so the results cluster, and eight missed the clusters.
SEEDS = 24
#: Representatives measured per class, to record the spread rather than assume it.
SAMPLES = 3
OPTIMIZATION_LEVEL = 3
#: Spare qubits offered to the synthesis pass: two gave the shallowest circuit of the
#: settings tried, and the device has over a hundred idle.
ANCILLAS = 2


def line_clue(cells: list[int]) -> tuple[int, ...]:
    """The clue describing one line of filled and empty cells."""
    out: list[int] = []
    run = 0
    for cell in cells:
        if cell:
            run += 1
        elif run:
            out.append(run)
            run = 0
    if run:
        out.append(run)
    return tuple(out) if out else (0,)


def clues_of(bits: list[int], rows: int, cols: int):
    """The row and column clues a filled grid produces."""
    grid = [bits[r * cols : (r + 1) * cols] for r in range(rows)]
    row_clues = [line_clue(row) for row in grid]
    col_clues = [line_clue([grid[r][c] for r in range(rows)]) for c in range(cols)]
    return row_clues, col_clues


def solvable_puzzles(rows: int, cols: int):
    """Every distinct solvable puzzle of this shape, grouped by solution count."""
    from nonogram.classical import classical_solve

    seen: set = set()
    by_solutions: dict[int, list] = {}
    for bits in itertools.product([0, 1], repeat=rows * cols):
        row_clues, col_clues = clues_of(list(bits), rows, cols)
        key = (tuple(row_clues), tuple(col_clues))
        if key in seen:
            continue
        seen.add(key)
        count = len(classical_solve((row_clues, col_clues)))
        by_solutions.setdefault(count, []).append((row_clues, col_clues))
    return by_solutions


def measure_clue_oracle(puzzle, iterations: int, backend, ancillas: int = 2):
    """The same board, through an oracle that tests the clues instead of holding answers.

    ``PhaseOracleGate`` reduces the clue formula over its whole truth table and emits one
    marked grid per solution, so what the main figures measure is an answer-marker. This
    builds the oracle from the clues directly — one flag per line, one gate per pattern the
    clue allows — which is what an oracle nobody has solved the puzzle for costs.
    """
    from qiskit import QuantumCircuit, transpile
    from qiskit.circuit.library import ZGate

    from nonogram.clue_oracle import clue_oracle_circuit

    oracle = clue_oracle_circuit(puzzle[0], puzzle[1])
    cells = len(puzzle[0]) * len(puzzle[1])
    circuit = QuantumCircuit(oracle.num_qubits + ancillas, cells)
    circuit.h(range(cells))
    for _ in range(iterations):
        circuit.compose(oracle, qubits=range(oracle.num_qubits), inplace=True)
        circuit.h(range(cells))
        circuit.x(range(cells))
        circuit.append(ZGate().control(cells - 1), list(range(cells)))
        circuit.x(range(cells))
        circuit.h(range(cells))
    circuit.measure(range(cells), range(cells))

    runs = []
    for seed in range(SEEDS):
        flat = transpile(
            circuit,
            backend=backend,
            optimization_level=OPTIMIZATION_LEVEL,
            seed_transpiler=seed,
        )
        ops = flat.count_ops()
        two_qubit = sum(v for gate, v in ops.items() if gate in ("ecr", "cz", "cx"))
        runs.append((flat.depth(), sum(ops.values()), two_qubit, oracle.num_qubits + ancillas))
    return runs


def measure(puzzle, iterations: int, backend, ancillas: int = 0):
    """Transpile one puzzle at several seeds and keep the shallowest result.

    A multi-controlled gate costs six times less when synthesis has a spare qubit to
    borrow, and the device has a hundred idle ones. ``ancillas`` adds that many qubits to
    the circuit, which is all Qiskit needs to pick the cheaper decomposition: every gate
    still acts on the same nine, so the two runs compile the same circuit.
    """
    from qiskit import QuantumCircuit, transpile
    from qiskit.circuit.library import PhaseOracleGate
    from qiskit_algorithms import AmplificationProblem, Grover

    from nonogram.core import puzzle_to_boolean

    oracle = PhaseOracleGate(puzzle_to_boolean(row_clues=puzzle[0], col_clues=puzzle[1]))
    circuit = Grover(iterations=iterations).construct_circuit(
        AmplificationProblem(oracle), measurement=True
    )
    if ancillas:
        wide = QuantumCircuit(circuit.num_qubits + ancillas, circuit.num_clbits)
        wide.compose(
            circuit,
            qubits=range(circuit.num_qubits),
            clbits=range(circuit.num_clbits),
            inplace=True,
        )
        circuit = wide

    runs = []
    for seed in range(SEEDS):
        flat = transpile(
            circuit,
            backend=backend,
            optimization_level=OPTIMIZATION_LEVEL,
            seed_transpiler=seed,
        )
        ops = flat.count_ops()
        two_qubit = sum(v for gate, v in ops.items() if gate in ("ecr", "cz", "cx"))
        runs.append((flat.depth(), sum(ops.values()), two_qubit))
    return runs


def build() -> dict:
    import qiskit
    from qiskit_algorithms import Grover
    from qiskit_ibm_runtime.fake_provider import FakeTorino

    backend = FakeTorino()
    rows_out = []
    runs_out = []

    def spread(runs, index):
        """The range one metric took across every run of this arm."""
        values = [r[index] for r in runs]
        return [min(values), max(values)]

    def shallowest_of(runs):
        """The run with the fewest layers, reported whole.

        Depth and gate count disagree between layouts, so a figure assembled metric by
        metric would describe no circuit that exists.
        """
        return min(runs, key=lambda r: r[0])

    for rows in range(1, MAX_SIDE + 1):
        for cols in range(1, MAX_SIDE + 1):
            qubits = rows * cols
            for count, puzzles in sorted(solvable_puzzles(rows, cols).items()):
                if count == 0:
                    continue
                iterations = Grover.optimal_num_iterations(
                    num_solutions=count, num_qubits=qubits
                )
                # Spare qubits to borrow. The floor keeps a one-qubit board from being
                # padded past what a decomposition of that size can use.
                spare = max(0, min(ANCILLAS, qubits - 2))
                # Every seed of every representative board, flattened.
                per_board = [
                    measure(p, iterations, backend, spare) for p in puzzles[:SAMPLES]
                ]
                measured = [run for board in per_board for run in board]
                shallowest = shallowest_of(measured)
                # The same circuit with nothing to borrow, so the two decompositions can
                # be read against each other.
                bare_runs = measure(puzzles[0], iterations, backend, 0)
                bare = shallowest_of(bare_runs)
                # The honest oracle varies board to board, so it is measured over the same
                # representatives rather than one of them.
                clue_per_board = [
                    measure_clue_oracle(p, iterations, backend) for p in puzzles[:SAMPLES]
                ]
                clue = [run for board in clue_per_board for run in board]
                shallowest_clue = shallowest_of(clue)
                print(
                    f"{rows}x{cols} M={count:<2} k={iterations:<3} "
                    f"depth={shallowest[0]:,} of {spread(measured, 0)} "
                    f"bare={bare[0]:,} clue={shallowest_clue[0]:,}",
                    file=sys.stderr,
                )
                runs_out.append(
                    {
                        "rows": rows,
                        "cols": cols,
                        "solutions": count,
                        "iterations": iterations,
                        "seeds": SEEDS,
                        "boards_measured": len(puzzles[:SAMPLES]),
                        "columns": ["depth", "gates", "two_qubit"],
                        "marker": [list(r[:3]) for r in measured],
                        "marker_noaux": [list(r[:3]) for r in bare_runs],
                        "clue": [list(r[:3]) for r in clue],
                    }
                )
                rows_out.append(
                    {
                        "rows": rows,
                        "cols": cols,
                        "solutions": count,
                        "iterations": iterations,
                        "boards": len(puzzles),
                        "ancillas": spare,
                        "depth": shallowest[0],
                        "gates": shallowest[1],
                        "two_qubit": shallowest[2],
                        "depth_range": spread(measured, 0),
                        "two_qubit_range": spread(measured, 2),
                        "depth_noaux": bare[0],
                        "gates_noaux": bare[1],
                        "two_qubit_noaux": bare[2],
                        "depth_noaux_range": spread(bare_runs, 0),
                        "two_qubit_noaux_range": spread(bare_runs, 2),
                        "depth_clue": shallowest_clue[0],
                        "gates_clue": shallowest_clue[1],
                        "two_qubit_clue": shallowest_clue[2],
                        "qubits_clue": shallowest_clue[3],
                        "depth_clue_range": spread(clue, 0),
                        "two_qubit_clue_range": spread(clue, 2),
                    }
                )

    # Measured over the rows deep enough for the figure to mean anything: a
    # nine-layer circuit swings a whole percent on one gate.
    spreads = [
        (r["depth_range"][1] - r["depth_range"][0]) / r["depth_range"][0]
        for r in rows_out
        if r["depth_range"][0] > 100
    ]
    return {
        "target": backend.name,
        "qiskit": qiskit.__version__,
        "optimization_level": OPTIMIZATION_LEVEL,
        "seeds": SEEDS,
        "ancillas": ANCILLAS,
        "note": (
            "Each figure is one transpiled circuit: the shallowest of the seeds tried, "
            "reported whole, because depth and gate count disagree between layouts. The "
            "_range fields give what that metric took across every run of its arm, seeds "
            "and representative boards together. The main figures give synthesis the spare "
            "qubits a real device has; the _noaux figures are the same circuit compiled "
            "with none; the _clue figures replace Qiskit's answer-marking oracle with one "
            "built from the clues, over one flag qubit per line."
        ),
        "spread_floor": 100,
        "worst_spread": round(max(spreads) if spreads else 0.0, 5),
        "rows": rows_out,
    }, {
        "target": backend.name,
        "qiskit": qiskit.__version__,
        "optimization_level": OPTIMIZATION_LEVEL,
        "seeds": SEEDS,
        "note": (
            "Every run behind the summary table: one entry per (grid size, solution "
            "count), each arm listing [depth, gates, two_qubit] per seed per board. Kept "
            "out of the summary so the page does not ship the whole sweep to a reader."
        ),
        "rows": runs_out,
    }


if __name__ == "__main__":
    summary, runs = build()
    json.dump(summary, sys.stdout, indent=1)
    sys.stdout.write("\n")
    # Nothing on the page reads the raw sweep, so it sits beside the summary.
    runs_path = Path(sys.argv[1] if len(sys.argv) > 1 else "depth-table-runs.json")
    with runs_path.open("w") as handle:
        json.dump(runs, handle, indent=1)
    print(f"wrote {runs_path}", file=sys.stderr)
