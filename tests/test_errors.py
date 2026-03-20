"""Tests for nonogram.errors — exception hierarchy."""

from nonogram.errors import (
    ClassicalSolverError,
    HardwareError,
    NonogramError,
    PuzzleIOError,
    QuantumSolverError,
    SolverError,
    ValidationError,
)


class TestHierarchy:
    def test_validation_error_is_value_error(self):
        assert issubclass(ValidationError, ValueError)
        assert issubclass(ValidationError, NonogramError)

    def test_solver_hierarchy(self):
        assert issubclass(ClassicalSolverError, SolverError)
        assert issubclass(QuantumSolverError, SolverError)
        assert issubclass(HardwareError, QuantumSolverError)
        assert issubclass(SolverError, NonogramError)

    def test_puzzle_io_error_is_os_error(self):
        assert issubclass(PuzzleIOError, OSError)
        assert issubclass(PuzzleIOError, NonogramError)

    def test_catch_all_with_nonogram_error(self):
        """All custom exceptions are catchable via NonogramError."""
        for exc_cls in (ValidationError, ClassicalSolverError,
                        QuantumSolverError, HardwareError, PuzzleIOError):
            try:
                raise exc_cls("test")
            except NonogramError:
                pass  # expected
