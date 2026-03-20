"""
test_hardware_2x2.py
~~~~~~~~~~~~~~~~~~~~
Run the 2×2 all-2s nonogram on real IBM quantum hardware.

Puzzle
------
Row clues:    (2,) (2,)
Column clues: (2,) (2,)
Unique solution: all 4 cells filled  →  "1111"

Why 2×2 instead of 3×3 for hardware?
--------------------------------------
The PhaseOracleGate compiles the nonogram constraint into a general quantum
circuit via boolean synthesis.  Circuit depth scales with oracle complexity:

    2×2 all-2s  →  depth ≈  142   (tractable on NISQ hardware)
    3×3 all-3s  →  depth ≈ 2900   (far beyond NISQ coherence limits)

A depth-142 circuit stays well within the coherence window of IBM Eagle/Heron
devices, so the quantum signal survives.

Grover iteration count (k=1 for 2×2 with 1 solution / 16 states)
------------------------------------------------------------------
Noiseless peak probability P(k) = sin²((2k+1)·arcsin(1/√16)):

    k = 1 → P ≈ 47.3 %   ✓ strong signal, shallow circuit
    k = 2 → P ≈ 90.8 %   (depth doubles; still feasible)

We use k=1 (depth ≈ 142, noiseless target 47.3 %).  Even with NISQ noise
the peak should remain far above the 6.25 % random baseline (1/16).

API calls: 1 circuit submission (+ 1 REST call to find least-busy backend)
Shots:     1024

Run:  pytest tests/test_hardware_2x2.py -v -s
"""
import pytest

from conftest import load_ibm_token


@pytest.mark.skipif(
    load_ibm_token() is None,
    reason="IBM_QUANTUM_TOKEN env var not set and .env not found",
)
def test_hardware_2x2_all_twos():
    """Submit 2×2 all-2s Grover circuit to IBM hardware and verify a clear signal.

    Uses PhaseOracleGate (same code path as the general solver) with 1 Grover
    iteration.  Transpiled circuit depth ≈ 142 — well within NISQ limits.
    Noiseless peak probability ≈ 47.3 %.
    """
    pytest.importorskip("qiskit_ibm_runtime", reason="qiskit-ibm-runtime not installed")

    token = load_ibm_token()
    assert token

    from nonogram.quantum import quantum_solve_hardware

    row_clues = [(2,), (2,)]
    col_clues  = [(2,), (2,)]

    GROVER_ITERS = 1
    SHOTS        = 1024

    print(f"\nSubmitting 2×2 all-2s puzzle to IBM quantum hardware "
          f"({SHOTS} shots, {GROVER_ITERS} Grover iteration, least-busy backend)…")
    print("Error mitigation: dynamical decoupling + Pauli twirling enabled.")
    print("Transpiled circuit depth: ~142 gates.")
    print("Waiting for IBM queue — this may take a few minutes.")

    counts, backend_name = quantum_solve_hardware(
        (row_clues, col_clues),
        token=token,
        channel="ibm_quantum_platform",
        shots=SHOTS,
        iterations=GROVER_ITERS,
        dynamical_decoupling=True,
        twirling=True,
    )

    print(f"\nBackend:           {backend_name}")
    total = sum(counts.values())
    print(f"Total shots:       {total}")
    print(f"Unique bitstrings: {len(counts)}")

    top5 = sorted(counts.items(), key=lambda x: -x[1])[:5]
    print("\nTop 5 results:")
    print(f"  {'IBM bitstring':<12}  {'Row-major grid':<12}  {'Count':>6}  {'Prob':>7}")
    for bs, cnt in top5:
        grid = bs[::-1]   # reverse Qiskit little-endian → row-major
        print(f"  {bs:<12}  {grid:<12}  {cnt:>6}  {cnt/total:>6.2%}")

    expected   = "1" * 4
    top_ibm_bs = top5[0][0]
    top_grid   = top_ibm_bs[::-1]
    top_prob   = top5[0][1] / total

    # Check whether the all-ones state was measured
    all_ones_ibm = "1" * 4
    if all_ones_ibm in counts:
        p_correct = counts[all_ones_ibm] / total
        print(f"\nAll-ones state probability: {p_correct:.2%}  "
              f"(noiseless target: ~47.3 %,  random baseline: ~6.25 %)")
    else:
        p_correct = 0.0
        print("\nAll-ones state: not observed in this run.")

    print(f"Top result (row-major):     {top_grid}")
    print(f"Top result probability:     {top_prob:.2%}")

    # ── Primary assertion: the top bitstring should stand well above noise ──
    # Random chance for 4 qubits = 1/16 = 6.25 %.
    # Noiseless target with k=1 Grover iteration ≈ 47.3 %.
    # We require > 15 % — modest enough to tolerate noise but unambiguously
    # above random chance.
    assert top_prob > 0.15, (
        f"Top probability {top_prob:.2%} does not rise above background noise — "
        "expected > 15 % (noiseless target: ~47.3 %, random baseline: ~6.25 %)"
    )

    # ── Secondary assertion: the correct solution should be the top result ──
    # (or at least show a strong non-trivial probability)
    if top_grid == expected:
        print(f"\n✓  CORRECT — all-ones state '{expected}' is the top result "
              f"at {top_prob:.2%}.")
    else:
        # Correct answer may be the 2nd-best due to noise; check it's present
        # with at least 10 % probability.
        assert p_correct > 0.10, (
            f"All-ones state probability {p_correct:.2%} is too low — "
            "quantum signal not visible for the correct solution"
        )
        print(f"\n⚠  Top result '{top_grid}' differs from expected '{expected}' "
              "— hardware noise shifted the peak.")
        print(f"   All-ones state still present at {p_correct:.2%}  ✓")
