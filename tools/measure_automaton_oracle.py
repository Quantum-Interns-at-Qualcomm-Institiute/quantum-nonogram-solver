"""What the run-length automaton oracle costs beside the oracles that enumerate.

Oracle scope: one oracle transpiled on its own, never a whole Grover circuit, so no
diffuser sits on both sides of a ratio. Every seed is kept and the ratio is reported as the
range the seeds cover, because selecting a seed on one metric and then printing another
describes a circuit nobody compiled.

Three arms per board:

* ``marking``   -- ``PhaseOracleGate`` over the clue formula, one marked grid per solution.
* ``clue``      -- one multi-controlled X per filling each line allows.
* ``automaton`` -- one reversible run-length automaton per line.

Qubit counts travel with the gate counts: the automaton buys its gate count with a
workspace, and a ratio without that beside it says nothing.

Usage:
    python -m tools.measure_automaton_oracle [out.json]
"""

from __future__ import annotations

import itertools
import json
import random
import statistics
import sys
import time
from pathlib import Path

#: Seeds per arm, matching the oracle-scope sweeps the project already reports.
SEEDS = 8
#: Idle qubits lent to synthesis, offered to every arm alike.
SPARE = 2
OPTIMIZATION_LEVEL = 3
TWO_QUBIT_NAMES = ("ecr", "cz", "cx")

#: Shapes measured with every arm, and shapes where only the automaton is affordable.
SHAPES = [(2, 2), (2, 3), (3, 3), (2, 4), (2, 5), (3, 4), (2, 6)]
WIDE_SHAPES = [(2, 7), (2, 8), (2, 9), (2, 10)]


def line_patterns(rows: int, cols: int, row_clues, col_clues) -> int:
    """Fillings the clues allow line by line, which is the minterm oracle's gate count."""
    from nonogram.data import _generate_patterns

    return sum(len(_generate_patterns(cols, clue)) for clue in row_clues) + sum(
        len(_generate_patterns(rows, clue)) for clue in col_clues
    )


#: Grid count past which boards are sampled at a fixed seed rather than enumerated.
ENUMERATE_BELOW = 1 << 13
#: Boards wanted from a sample before the median is taken.
SAMPLE_TARGET = 40
SAMPLE_SEED = 20261009


def _grids(rows: int, cols: int):
    """Every grid of this shape, or a fixed sample of them when there are too many."""
    cells = rows * cols
    if 2**cells < ENUMERATE_BELOW:
        yield from (list(bits) for bits in itertools.product([0, 1], repeat=cells))
        return
    source = random.Random(SAMPLE_SEED)
    for _ in range(40 * ENUMERATE_BELOW):
        yield [source.randint(0, 1) for _ in range(cells)]


def one_solution_board(rows: int, cols: int):
    """A board of this shape with one solution, median in how many fillings its clues allow.

    The extremes of that range are the two boards a comparison should not rest on: the
    board whose every line is determined is the cheapest an enumerating oracle can get, and
    the loosest board the dearest. Taking the median keeps the choice out of the result.
    Shapes with too many grids to enumerate are sampled at a fixed seed instead, so the
    board a shape resolves to is the same on every run.
    """
    from nonogram.classical import classical_solve

    from tools.build_depth_table import clues_of

    seen: set = set()
    candidates = []
    for bits in _grids(rows, cols):
        row_clues, col_clues = clues_of(bits, rows, cols)
        key = (tuple(row_clues), tuple(col_clues))
        if key in seen:
            continue
        seen.add(key)
        if len(classical_solve((row_clues, col_clues))) != 1:
            continue
        candidates.append((line_patterns(rows, cols, row_clues, col_clues), row_clues, col_clues))
        if 2 ** (rows * cols) >= ENUMERATE_BELOW and len(candidates) >= SAMPLE_TARGET:
            break
    if not candidates:
        raise RuntimeError(f"no one-solution board at {rows}x{cols}")
    candidates.sort(key=lambda item: (item[0], str(item[1]), str(item[2])))
    patterns, row_clues, col_clues = candidates[len(candidates) // 2]
    return row_clues, col_clues, patterns, len(candidates)


def padded(circuit, spare: int = SPARE):
    """One oracle on its own qubits, plus idle ones for synthesis to borrow."""
    from qiskit import QuantumCircuit

    wide = QuantumCircuit(circuit.num_qubits + spare)
    wide.compose(circuit, qubits=range(circuit.num_qubits), inplace=True)
    return wide


def transpile_runs(circuit) -> list[dict]:
    """Every seed, kept whole."""
    from qiskit import transpile
    from qiskit_ibm_runtime.fake_provider import FakeTorino

    backend = FakeTorino()
    runs = []
    for seed in range(SEEDS):
        flat = transpile(
            padded(circuit),
            backend=backend,
            optimization_level=OPTIMIZATION_LEVEL,
            seed_transpiler=seed,
        )
        ops = flat.count_ops()
        runs.append(
            {
                "seed": seed,
                "two_qubit": sum(v for gate, v in ops.items() if gate in TWO_QUBIT_NAMES),
                "depth": flat.depth(),
                "gates": sum(ops.values()),
            }
        )
    return runs


def arms(row_clues, col_clues, include_marking: bool) -> dict:
    """Each oracle for this board, as a circuit over its own qubits."""
    from qiskit.circuit.library import PhaseOracleGate

    from nonogram.automaton_oracle import automaton_oracle_circuit
    from nonogram.clue_oracle import clue_oracle_circuit
    from nonogram.core import puzzle_to_boolean

    out = {
        "automaton": lambda: automaton_oracle_circuit(row_clues, col_clues),
        "clue": lambda: clue_oracle_circuit(row_clues, col_clues),
    }
    if include_marking:
        def marking():
            from qiskit import QuantumCircuit

            gate = PhaseOracleGate(puzzle_to_boolean(row_clues=row_clues, col_clues=col_clues))
            qc = QuantumCircuit(gate.num_qubits)
            qc.append(gate, range(gate.num_qubits))
            return qc

        out["marking"] = marking
    return out


def summarise(runs: list[dict], qubits: int, build_seconds: float) -> dict:
    """Per-metric medians and the span the seeds cover, with the qubit count beside them."""
    out = {
        "logical_qubits": qubits,
        "build_seconds": round(build_seconds, 3),
        "seeds": len(runs),
        "runs": runs,
    }
    for field in ("two_qubit", "depth", "gates"):
        values = sorted(r[field] for r in runs)
        out[field + "_median"] = statistics.median(values)
        out[field + "_range"] = [values[0], values[-1]]
    return out


def measure_board(rows: int, cols: int, include_marking: bool) -> dict:
    """One board through every arm this shape can afford."""
    row_clues, col_clues, patterns, boards = one_solution_board(rows, cols)
    record = {
        "rows": rows,
        "cols": cols,
        "cells": rows * cols,
        "solutions": 1,
        "longest_line": max(rows, cols),
        "patterns": patterns,
        "one_solution_boards": boards,
        "row_clues": [list(c) for c in row_clues],
        "col_clues": [list(c) for c in col_clues],
    }
    for name, build in arms(row_clues, col_clues, include_marking).items():
        started = time.time()
        circuit = build()
        built = time.time() - started
        record[name] = summarise(transpile_runs(circuit), circuit.num_qubits, built)
        print(
            f"{rows}x{cols} {name:<9} qubits={record[name]['logical_qubits']:<3} "
            f"2q median={record[name]['two_qubit_median']:,} "
            f"range={record[name]['two_qubit_range']}",
            file=sys.stderr,
        )

    for other in ("automaton", "clue"):
        for against in ("marking", "clue"):
            if other == against or against not in record or other not in record:
                continue
            per_seed = sorted(
                record[other]["runs"][i]["two_qubit"] / record[against]["runs"][i]["two_qubit"]
                for i in range(SEEDS)
            )
            record[f"two_qubit_ratio_{other}_over_{against}"] = {
                "median_of_medians": round(
                    record[other]["two_qubit_median"] / record[against]["two_qubit_median"], 3
                ),
                "per_seed_range": [round(per_seed[0], 3), round(per_seed[-1], 3)],
                "qubit_ratio": round(
                    record[other]["logical_qubits"] / record[against]["logical_qubits"], 3
                ),
            }
    return record


def build() -> dict:
    import qiskit
    from qiskit_ibm_runtime.fake_provider import FakeTorino

    boards = [measure_board(rows, cols, True) for rows, cols in SHAPES]
    boards += [measure_board(rows, cols, False) for rows, cols in WIDE_SHAPES]
    return {
        "target": FakeTorino().name,
        "qiskit": qiskit.__version__,
        "optimization_level": OPTIMIZATION_LEVEL,
        "seeds": SEEDS,
        "spare": SPARE,
        "scope": "oracle",
        "note": (
            "One oracle transpiled alone at every seed, with two idle qubits offered to "
            "synthesis in every arm. Medians are per metric; ratios carry the span of the "
            "per-seed ratios and the qubit ratio beside them. The marking arm is left out "
            "of the widest shapes, where reducing its formula over the whole grid space "
            "costs more than the measurement is worth."
        ),
        "boards": boards,
    }


if __name__ == "__main__":
    data = build()
    destination = Path(sys.argv[1] if len(sys.argv) > 1 else "automaton-oracle-cost.json")
    destination.write_text(json.dumps(data, indent=1) + "\n")
    print(f"wrote {destination}", file=sys.stderr)
