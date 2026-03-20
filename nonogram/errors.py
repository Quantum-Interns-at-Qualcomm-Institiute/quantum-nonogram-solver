"""Custom exception hierarchy for nonogram solvers.

Hierarchy
---------
::

    NonogramError
    ├── ValidationError       — invalid clues, dimensions, or input data
    ├── SolverError           — base for all solve-time failures
    │   ├── ClassicalSolverError
    │   └── QuantumSolverError
    │       └── HardwareError — IBM backend connection / job failures
    └── PuzzleIOError         — serialization / file I/O failures
"""

from __future__ import annotations


class NonogramError(Exception):
    """Root exception for the nonogram package."""


class ValidationError(NonogramError, ValueError):
    """Invalid puzzle clues, dimensions, or input data."""


class SolverError(NonogramError):
    """A solver failed to produce a result."""


class ClassicalSolverError(SolverError):
    """Classical (brute-force) solver failure."""


class QuantumSolverError(SolverError):
    """Quantum solver failure (simulator or hardware)."""


class HardwareError(QuantumSolverError):
    """IBM quantum backend connection, transpilation, or job failure."""


class PuzzleIOError(NonogramError, OSError):
    """Puzzle file read/write failure."""
