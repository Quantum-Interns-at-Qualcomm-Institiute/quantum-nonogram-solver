"""The three solvers: brute force, Grover on the local simulator, Grover on IBM hardware.

Each one exposes ``name`` and ``solve(puzzle)``. ``solve`` returns ``{"solutions": [...]}``
for the classical solver and ``{"counts": {...}}`` for the quantum ones.
"""

from __future__ import annotations

from typing import Any

from nonogram.errors import ClassicalSolverError, HardwareError, QuantumSolverError

Puzzle = tuple[list, list]
"""Type alias for (row_clues, col_clues)."""


class ClassicalSolver:
    """Brute-force exhaustive search solver."""

    @property
    def name(self) -> str:
        return "Classical"

    def solve(self, puzzle: Puzzle) -> dict[str, Any]:
        try:
            from nonogram.classical import classical_solve

            solutions = classical_solve(puzzle)
        except Exception as exc:
            raise ClassicalSolverError(str(exc)) from exc
        return {"solutions": solutions}


class QuantumSimulatorSolver:
    """Grover's algorithm on local statevector simulator."""

    @property
    def name(self) -> str:
        return "Quantum (Simulator)"

    def solve(self, puzzle: Puzzle) -> dict[str, Any]:
        try:
            from nonogram.quantum import quantum_solve

            result = quantum_solve(puzzle)
            counts = result.circuit_results[0]
        except QuantumSolverError:
            raise
        except Exception as exc:
            raise QuantumSolverError(str(exc)) from exc
        return {"counts": counts, "grover_result": result}


class QuantumHardwareSolver:
    """Grover's algorithm on IBM quantum hardware."""

    def __init__(
        self,
        token: str,
        backend_name: str,
        channel: str = "ibm_quantum_platform",
        shots: int = 1024,
    ) -> None:
        self._token = token
        self._backend_name = backend_name
        self._channel = channel
        self._shots = shots

    @property
    def name(self) -> str:
        return f"Quantum (Hardware: {self._backend_name})"

    def solve(self, puzzle: Puzzle) -> dict[str, Any]:
        try:
            from nonogram.quantum import quantum_solve_hardware

            counts, backend_name = quantum_solve_hardware(
                puzzle,
                token=self._token,
                backend_name=self._backend_name,
                channel=self._channel,
                shots=self._shots,
            )
        except (HardwareError, QuantumSolverError):
            raise
        except Exception as exc:
            raise HardwareError(str(exc)) from exc
        return {"counts": counts, "backend_name": backend_name}
