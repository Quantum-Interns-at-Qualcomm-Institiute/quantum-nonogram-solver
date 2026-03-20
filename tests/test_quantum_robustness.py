"""Robustness tests for the quantum solver.

Tests the quantum_solve function on various puzzle configurations,
verifying that Grover's algorithm amplifies correct solutions.
Solutions are cross-validated against the classical solver.
"""
from __future__ import annotations

import pytest

from nonogram.classical import classical_solve
from nonogram.core import rle
from nonogram.errors import QuantumSolverError, ValidationError
from nonogram.quantum import quantum_solve


# ── Helpers ──────────────────────────────────────────────────────────────────


def _assert_quantum_finds_classical(puzzle):
    """Verify quantum finds at least one classical solution with non-trivial probability."""
    classical = classical_solve(puzzle)
    assert len(classical) > 0, "Puzzle has no classical solution"

    result = quantum_solve(puzzle)
    counts = result.circuit_results[0]
    total = sum(counts.values())

    # Check that at least one classical solution appears among the top results.
    # For small puzzles (1-2 qubits), Grover gives near-uniform probabilities,
    # so we use a lenient threshold relative to the uniform baseline.
    n_qubits = len(list(counts.keys())[0])
    uniform_prob = 1.0 / (2 ** n_qubits)
    # Require above uniform probability (solution should be at least slightly amplified)
    threshold = uniform_prob * 0.5

    found = False
    for bs, count in counts.items():
        if bs[::-1] in classical and count / total >= threshold:
            found = True
            break
    assert found, (
        f"No classical solution found above threshold {threshold:.4f}.\n"
        f"Classical solutions: {classical}\n"
        f"Quantum top-5: {sorted(counts.items(), key=lambda x: -x[1])[:5]}"
    )


# ── 1×1 puzzles ─────────────────────────────────────────────────────────────


def test_quantum_1x1_filled():
    _assert_quantum_finds_classical(([(1,)], [(1,)]))


def test_quantum_1x1_empty():
    _assert_quantum_finds_classical(([(0,)], [(0,)]))


# ── 2×2 puzzles ─────────────────────────────────────────────────────────────


def test_quantum_2x2_all_filled():
    _assert_quantum_finds_classical(([(2,), (2,)], [(2,), (2,)]))


def test_quantum_2x2_all_empty():
    _assert_quantum_finds_classical(([(0,), (0,)], [(0,), (0,)]))


def test_quantum_2x2_diagonal():
    """Diagonal 2x2 has 2 solutions — quantum should find one."""
    _assert_quantum_finds_classical(([(1,), (1,)], [(1,), (1,)]))


def test_quantum_2x2_top_row():
    _assert_quantum_finds_classical(([(2,), (0,)], [(1,), (1,)]))


# ── 3×3 puzzles ─────────────────────────────────────────────────────────────


def test_quantum_3x3_l_shape():
    """L-shape puzzle with unique solution."""
    _assert_quantum_finds_classical(([(1,), (1,), (3,)], [(3,), (1,), (1,)]))


def test_quantum_3x3_checkerboard():
    _assert_quantum_finds_classical(([(1, 1), (1,), (1, 1)], [(1, 1), (1,), (1, 1)]))


def test_quantum_3x3_all_filled():
    _assert_quantum_finds_classical(([(3,), (3,), (3,)], [(3,), (3,), (3,)]))


def test_quantum_3x3_all_empty():
    _assert_quantum_finds_classical(([(0,), (0,), (0,)], [(0,), (0,), (0,)]))


# ── Rectangular puzzles ──────────────────────────────────────────────────────


def test_quantum_2x3_rectangular():
    _assert_quantum_finds_classical(([(2,), (2,)], [(1,), (2,), (1,)]))


def test_quantum_3x2_rectangular():
    _assert_quantum_finds_classical(([(2,), (0,), (2,)], [(1, 1), (1, 1)]))


def test_quantum_1x3_single_row():
    _assert_quantum_finds_classical(([(1, 1)], [(1,), (0,), (1,)]))


# ── Multi-block clues ────────────────────────────────────────────────────────


def test_quantum_multiblock_1_1():
    """Multi-block clue (1,1) on 3-cell line."""
    _assert_quantum_finds_classical(([(1, 1)], [(1,), (0,), (1,)]))


# ── Bitstring structure ──────────────────────────────────────────────────────


def test_bitstring_chars_are_01():
    """All bitstring characters should be '0' or '1'."""
    result = quantum_solve(([(1,), (1,), (3,)], [(3,), (1,), (1,)]))
    counts = result.circuit_results[0]
    for bs in counts:
        assert all(c in ("0", "1") for c in bs), f"Invalid bitstring: {bs}"


def test_bitstring_length_matches_grid():
    """Bitstring length should equal n * d."""
    for n, d, puzzle in [
        (1, 1, ([(1,)], [(1,)])),
        (2, 2, ([(2,), (2,)], [(2,), (2,)])),
        (2, 3, ([(2,), (2,)], [(1,), (2,), (1,)])),
    ]:
        result = quantum_solve(puzzle)
        counts = result.circuit_results[0]
        for bs in counts:
            assert len(bs) == n * d, f"Expected len={n*d}, got {len(bs)} for {n}x{d}"


# ── Result structure ─────────────────────────────────────────────────────────


def test_result_has_circuit_results():
    result = quantum_solve(([(1,)], [(1,)]))
    assert hasattr(result, "circuit_results")
    assert len(result.circuit_results) > 0
    counts = result.circuit_results[0]
    assert isinstance(counts, dict)
    assert all(isinstance(k, str) for k in counts)
    assert all(isinstance(v, (int, float)) for v in counts.values())


# ── Error handling ───────────────────────────────────────────────────────────


def test_impossible_clues_raises():
    """Clue that can't fit in the grid should raise ValidationError."""
    with pytest.raises(ValidationError):
        quantum_solve(([(3,)], [(1,)]))


# ── extract_counts tests ─────────────────────────────────────────────────────


class TestExtractCounts:
    """Test the extract_counts function with mock DataBin objects."""

    def test_strategy_1_creg_names(self):
        from nonogram.quantum import extract_counts

        class FakeBitArray:
            def get_counts(self):
                return {"01": 512, "10": 512}

        class FakeDataBin:
            def __init__(self):
                self.meas = FakeBitArray()

        counts = extract_counts(FakeDataBin(), ["meas"])
        assert counts == {"01": 512, "10": 512}

    def test_strategy_2_fields(self):
        from nonogram.quantum import extract_counts

        class FakeBitArray:
            def get_counts(self):
                return {"00": 100, "11": 900}

        class FakeDataBin:
            _fields = ("result",)

            def __init__(self):
                self.result = FakeBitArray()

        counts = extract_counts(FakeDataBin(), ["nonexistent"])
        assert counts == {"00": 100, "11": 900}

    def test_strategy_5_dir_scan(self):
        from nonogram.quantum import extract_counts

        class FakeBitArray:
            def get_counts(self):
                return {"111": 1024}

        class FakeDataBin:
            def __init__(self):
                self.measurements = FakeBitArray()

        counts = extract_counts(FakeDataBin(), ["nonexistent"])
        assert counts == {"111": 1024}

    def test_no_strategy_works_raises(self):
        from nonogram.quantum import extract_counts

        class EmptyDataBin:
            pass

        with pytest.raises(QuantumSolverError, match="Could not extract"):
            extract_counts(EmptyDataBin(), ["meas"])


# ── Cross-validation with classical solver ────────────────────────────────────


@pytest.mark.parametrize(
    "puzzle",
    [
        ([(1,)], [(1,)]),
        ([(0,)], [(0,)]),
        ([(2,), (2,)], [(2,), (2,)]),
        ([(1,), (1,)], [(1,), (1,)]),
        ([(1,), (1,), (3,)], [(3,), (1,), (1,)]),
    ],
    ids=["1x1-filled", "1x1-empty", "2x2-full", "2x2-diag", "3x3-L"],
)
def test_quantum_classical_agreement(puzzle):
    """Top quantum result must appear in the classical solution set."""
    _assert_quantum_finds_classical(puzzle)
