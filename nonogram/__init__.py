"""
Nonogram solver with classical and quantum backends.

This package provides:

  - **Core SAT encoding**: Convert nonogram puzzles to boolean satisfiability formulas
  - **Classical solver**: Brute-force exhaustive search over 2^(n*d) configurations
  - **Quantum solver**: Grover's algorithm via Qiskit (local or real IBM hardware)
  - **Metrics & benchmarking**: Performance comparison and circuit analysis
  - **Puzzle I/O**: JSON serialization for puzzle persistence

Key concepts
~~~~~~~~~~~~

A nonogram puzzle is defined by row and column clues. Each clue is a list of
contiguous block sizes that must appear in that row/column in that order.

Example::

    puzzle = (
        [(1, 1), (2, 2), (1, 2, 1), (1, 1)],  # row clues
        [(4,),   (1,),   (1,),       (1,),   (1,), (4,)],  # column clues
    )

The solver converts this to a SAT formula and finds all satisfying assignments
using either brute-force (classical) or Grover's algorithm (quantum).

Usage
~~~~~

::

    from nonogram import classical_solve, quantum_solve, benchmark

    puzzle = (
        [(1, 1), (2, 2), (1, 2, 1), (1, 1)],
        [(4,),   (1,),   (1,),       (1,),   (1,), (4,)],
    )

    # Solve classically
    solutions = classical_solve(puzzle)
    print(f"Found {len(solutions)} solution(s)")

    # Benchmark both methods
    report = benchmark(puzzle, run_classical=True, run_quantum=True)
    print_report(report)

    # Save/load puzzles
    from nonogram.io import save_puzzle, load_puzzle
    save_puzzle(puzzle[0], puzzle[1], "my_puzzle.non.json")
    data = load_puzzle("my_puzzle.non.json")
"""

from nonogram.classical import ExecutionCounts, classical_solve
from nonogram.core import (
    display_nonogram,
    grid_to_clues,
    parse_clue,
    puzzle_to_boolean,
    rle,
    validate,
    var_clauses,
)
from nonogram.data import constraint_density, valid_line_configs
from nonogram.errors import (
    ClassicalSolverError,
    HardwareError,
    NonogramError,
    PuzzleIOError,
    QuantumSolverError,
    SolverError,
    ValidationError,
)
from nonogram.io import load_batch, load_puzzle, save_batch, save_puzzle
from nonogram.metrics import (
    ClassicalMetrics,
    ComparisonReport,
    QuantumMetrics,
    StaticCircuitAnalysis,
    analyze_circuit,
    benchmark,
    print_report,
)
from nonogram.quantum import quantum_solve
from nonogram.solver import (
    ClassicalSolver,
    QuantumHardwareSolver,
    QuantumSimulatorSolver,
    Solver,
)

__all__ = [
    "var_clauses",
    "validate",
    "display_nonogram",
    "puzzle_to_boolean",
    "rle",
    "grid_to_clues",
    "parse_clue",
    "classical_solve",
    "ExecutionCounts",
    "quantum_solve",
    "benchmark",
    "print_report",
    "ClassicalMetrics",
    "QuantumMetrics",
    "ComparisonReport",
    "StaticCircuitAnalysis",
    "analyze_circuit",
    "save_puzzle",
    "load_puzzle",
    "save_batch",
    "load_batch",
    "Solver",
    "ClassicalSolver",
    "QuantumSimulatorSolver",
    "QuantumHardwareSolver",
    "NonogramError",
    "ValidationError",
    "SolverError",
    "ClassicalSolverError",
    "QuantumSolverError",
    "HardwareError",
    "PuzzleIOError",
    "valid_line_configs",
    "constraint_density",
]
