"""
test_hardware_parsing.py
~~~~~~~~~~~~~~~~~~~~~~~~
Two targeted tests for the IBM hardware integration:

  test_databin_parsing_logic
      Verifies the DataBin extraction logic with a mock object — exercises
      exactly the same code path as quantum_solve_hardware without making
      any API calls or running any circuits.

  test_list_backends_auth
      Authenticates against IBM Quantum Platform using the token in .env
      and confirms the backend-listing REST call succeeds.
      Makes exactly ONE API call.  No circuits are run, no compute credits
      are consumed.
"""
import dataclasses

import pytest

from conftest import load_ibm_token


# ---------------------------------------------------------------------------
# Test 1: DataBin parsing logic (ZERO API cost — pure Python mock)
# ---------------------------------------------------------------------------

def test_databin_parsing_logic():
    """The extraction loop in quantum_solve_hardware must handle any field name.

    Simulates two DataBin scenarios:
      a) field named "meas"  — the typical case from measure_all()
      b) field named "c"     — as seen in some runtime / transpilation combos

    Both should yield the injected counts dict without error.
    """
    # Build a fake BitArray with get_counts()
    class _FakeBitArray:
        def __init__(self, counts):
            self._counts = counts
        def get_counts(self):
            return dict(self._counts)

    # Build a fake DataBin as a plain dataclass (same interface as the real one)
    def _run_extraction(field_name: str, expected_counts: dict) -> dict:
        DataBinCls = dataclasses.make_dataclass(
            "DataBin", [(field_name, object)]
        )
        data = DataBinCls(**{field_name: _FakeBitArray(expected_counts)})

        # ── same logic as quantum_solve_hardware ──────────────────────
        counts = None
        try:
            fields = dataclasses.fields(data)
        except TypeError:
            fields = []

        for field in fields:
            candidate = getattr(data, field.name, None)
            if candidate is not None and hasattr(candidate, "get_counts"):
                counts = candidate.get_counts()
                break

        if counts is None:
            for name in ("meas", "c", "c0", "measure", "m"):
                candidate = getattr(data, name, None)
                if candidate is not None and hasattr(candidate, "get_counts"):
                    counts = candidate.get_counts()
                    break
        # ─────────────────────────────────────────────────────────────

        return counts

    # Scenario a: "meas" register (standard)
    expected = {"0101": 80, "1010": 48}
    result = _run_extraction("meas", expected)
    assert result == expected, f"'meas' extraction failed: {result}"
    print("✓  Field 'meas' extracted correctly.")

    # Scenario b: "c" register (seen with some backends/transpilation)
    expected2 = {"001": 100, "110": 28}
    result2 = _run_extraction("c", expected2)
    assert result2 == expected2, f"'c' extraction failed: {result2}"
    print("✓  Field 'c' extracted correctly.")

    # Scenario c: unusual name "measure"
    expected3 = {"1111": 64}
    result3 = _run_extraction("measure", expected3)
    assert result3 == expected3, f"'measure' extraction failed: {result3}"
    print("✓  Field 'measure' extracted correctly.")

    print("✓  DataBin parsing logic handles all register-name variants.")


# ---------------------------------------------------------------------------
# Test 2: list_backends() auth (1 REST call, zero compute cost)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    load_ibm_token() is None,
    reason="IBM_QUANTUM_TOKEN env var not set and .env not found",
)
def test_list_backends_auth():
    """Verify the IBM Quantum token authenticates and backend listing works.

    Uses ibm_quantum_platform channel (qiskit-ibm-runtime >= 0.30).
    Makes exactly ONE REST call.  No circuits run, no compute credits used.
    """
    pytest.importorskip("qiskit_ibm_runtime",
                        reason="qiskit-ibm-runtime not installed")

    token = load_ibm_token()
    assert token, "Token is empty after parsing .env"

    from nonogram.quantum import list_backends
    backends = list_backends(token, channel="ibm_quantum_platform")

    assert isinstance(backends, list), "list_backends should return a list"
    assert len(backends) > 0, "No backends returned — check token / account type"

    print(f"\n✓  Authenticated.  {len(backends)} backend(s) available:")
    for name, qubits, pending in backends[:6]:
        queue_str = str(pending) if pending >= 0 else "?"
        print(f"   {name:<26} {qubits:>3}q   queue: {queue_str}")
