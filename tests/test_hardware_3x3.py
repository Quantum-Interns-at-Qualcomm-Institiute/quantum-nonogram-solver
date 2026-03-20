"""
test_hardware_3x3.py
~~~~~~~~~~~~~~~~~~~~
Run the 3×3 all-3s nonogram on real IBM quantum hardware.

Puzzle
------
Row clues:    (3,) (3,) (3,)
Column clues: (3,) (3,) (3,)
Unique solution: all 9 cells filled  →  "111111111"

NISQ hardware limitation — why the 3×3 result is near-uniform noise
---------------------------------------------------------------------
The PhaseOracleGate for the 9-variable boolean expression compiles via
general boolean synthesis to a circuit with depth ≈ 2 900 (ibm_torino).
Current IBM Eagle/Heron devices have effective coherence depths of ~100–200
gate layers; any circuit deeper than that produces near-uniform noise.

    2×2 all-2s  →  depth ≈  142   (quantum signal visible on hardware)
    3×3 all-3s  →  depth ≈ 2 900  (circuit drowned in decoherence noise)

This test therefore does NOT assert quantum correctness (that the all-ones
state is the highest-probability outcome).  Instead it verifies the full
hardware pipeline end-to-end:

  1. Authentication with IBM Quantum Platform
  2. Least-busy backend selection
  3. PhaseOracleGate → Grover circuit construction
  4. Transpilation to native gate set
  5. SamplerV2 job submission (with DD + twirling options)
  6. Job completion and DataBin count extraction
  7. Bitstring reversal to row-major convention

For a genuine quantum result on hardware use test_hardware_2x2.py, which
uses the 2×2 all-2s puzzle (depth ≈ 142, noiseless peak ≈ 47 %).

API calls: 1 circuit submission (+ 1 REST call to find least-busy backend)
Shots:     512  (enough to verify the pipeline returns valid counts)

Run:  pytest tests/test_hardware_3x3.py -v -s
"""

import pytest
from conftest import load_ibm_token


@pytest.mark.skipif(
    load_ibm_token() is None,
    reason="IBM_QUANTUM_TOKEN env var not set and .env not found",
)
def test_hardware_3x3_pipeline():
    """Verify the full hardware pipeline runs for the 3×3 all-3s puzzle.

    The assertion is intentionally weak: we only check that the IBM job
    returned non-empty counts — not that the quantum result is correct.
    (See module docstring for why quantum correctness is not achievable
    on current NISQ hardware for a depth-≈-2900 circuit.)
    """
    pytest.importorskip("qiskit_ibm_runtime", reason="qiskit-ibm-runtime not installed")

    token = load_ibm_token()
    assert token

    from nonogram.quantum import quantum_solve_hardware

    row_clues = [(3,), (3,), (3,)]
    col_clues = [(3,), (3,), (3,)]

    SHOTS = 512  # minimal shots to verify the pipeline

    print("\nSubmitting 3×3 all-3s puzzle to IBM quantum hardware (pipeline test)…")
    print("Note: circuit depth ≈ 2 900 — result will be near-uniform noise.")
    print("This test only verifies the hardware pipeline, not quantum correctness.")
    print("Waiting for IBM queue — this may take several minutes.")

    counts, backend_name = quantum_solve_hardware(
        (row_clues, col_clues),
        token=token,
        channel="ibm_quantum_platform",
        shots=SHOTS,
        iterations=1,  # keep circuit as shallow as possible
        dynamical_decoupling=True,
        twirling=True,
    )

    total = sum(counts.values())
    unique = len(counts)

    print(f"\nBackend:           {backend_name}")
    print(f"Total shots:       {total}")
    print(f"Unique bitstrings: {unique}  (expected ~512 for 9-qubit uniform noise)")

    top3 = sorted(counts.items(), key=lambda x: -x[1])[:3]
    print("\nTop 3 results:")
    print(f"  {'IBM bitstring':<14}  {'Row-major grid':<14}  {'Count':>6}  {'Prob':>7}")
    for bs, cnt in top3:
        grid = bs[::-1]
        print(f"  {bs:<14}  {grid:<14}  {cnt:>6}  {cnt / total:>6.2%}")

    # ── Pipeline assertions ──────────────────────────────────────────────
    # The job ran, returned counts, and the bitstrings are the right length.
    assert total > 0, "No shots returned — job may have failed silently"
    assert all(len(bs) == 9 for bs in counts), (
        f"Unexpected bitstring length: {[len(b) for b in list(counts)[:3]]}"
    )
    assert unique > 0, "Empty counts dict returned"

    print(f"\n✓  Pipeline complete — {total} shots returned from {backend_name}")
    print("   (Near-uniform distribution expected for this circuit depth.)")
    print("   For a genuine quantum result, run test_hardware_2x2.py instead.")
