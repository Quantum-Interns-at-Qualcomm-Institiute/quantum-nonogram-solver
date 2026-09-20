"""
test_hardware_parsing.py
~~~~~~~~~~~~~~~~~~~~~~~~
Tests for the IBM hardware integration:

  test_databin_parsing_logic
      Calls extract_counts with mock DataBins — the same function
      quantum_solve_hardware uses, with no API calls and no circuits.

  test_list_backends_auth
      Authenticates against IBM Quantum Platform using IBM_QUANTUM_TOKEN
      and confirms the backend-listing REST call succeeds.
      Makes exactly ONE API call.  No circuits are run, no compute credits
      are consumed.
"""

import dataclasses

import pytest
from conftest import load_ibm_token

from nonogram.errors import QuantumSolverError
from nonogram.quantum import extract_counts

# Test 1: DataBin parsing logic (ZERO API cost — pure Python mock)


class _FakeBitArray:
    def __init__(self, counts):
        self._counts = counts

    def get_counts(self):
        return dict(self._counts)


@pytest.mark.parametrize(
    "field_name,creg_names",
    [
        ("meas", ["meas"]),
        ("c", ["c"]),
        ("measure", []),
        ("m", []),
    ],
    ids=["named-meas", "named-c", "discovered-measure", "discovered-m"],
)
def test_databin_parsing_logic(field_name, creg_names):
    """extract_counts finds the BitArray whatever the DataBin calls its field.

    The register name comes from the transpiled circuit when the runtime reports one,
    and is discovered from the object otherwise.
    """
    expected = {"0101": 80, "1010": 48}
    data_bin_cls = dataclasses.make_dataclass("DataBin", [(field_name, object)])
    data = data_bin_cls(**{field_name: _FakeBitArray(expected)})

    assert extract_counts(data, creg_names) == expected


def test_databin_without_a_bit_array_reports_what_it_saw():
    """A DataBin no strategy can read raises, and names the fields it inspected."""

    class _Empty:
        pass

    with pytest.raises(QuantumSolverError, match="Could not extract"):
        extract_counts(_Empty(), ["meas"])


# Test 2: list_backends() auth (1 REST call, zero compute cost)


@pytest.mark.hardware
@pytest.mark.skipif(
    load_ibm_token() is None,
    reason="IBM_QUANTUM_TOKEN env var not set and .env not found",
)
def test_list_backends_auth():
    """Verify the IBM Quantum token authenticates and backend listing works.

    Uses ibm_quantum_platform channel (qiskit-ibm-runtime >= 0.30).
    Makes exactly ONE REST call.  No circuits run, no compute credits used.
    """
    pytest.importorskip("qiskit_ibm_runtime", reason="qiskit-ibm-runtime not installed")

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
