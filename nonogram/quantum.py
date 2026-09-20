"""
Quantum solver using Grover's algorithm.

Two execution paths are provided:

  quantum_solve(puzzle)
      Runs entirely locally using Qiskit's StatevectorSampler (exact simulation).
      No IBM account required.

  quantum_solve_hardware(puzzle, token, ...)
      Transpiles the Grover circuit and submits it to a real IBM quantum backend
      (or an IBM cloud simulator) via qiskit-ibm-runtime.
      Requires:  pip install qiskit-ibm-runtime

  list_backends(token, channel)
      Enumerates the backends the account can reach, shortest queue first.

Bitstring note
--------------
Qiskit's little-endian convention means the returned bitstrings must be
*reversed* before interpreting them as row-major grid solutions.
Both functions return counts dicts whose keys need `bs[::-1]` to align with
the nonogram grid (top-left = bit 0).
"""

from __future__ import annotations

from nonogram.core import puzzle_to_boolean
from nonogram.errors import HardwareError, QuantumSolverError

# Local simulator path


def quantum_solve(puzzle: tuple[list, list]):
    """Solve a nonogram using Grover's algorithm on a local statevector simulator.

    Args:
        puzzle: (row_clues, col_clues) tuple.

    Returns:
        Qiskit GroverResult.  Access top-probability bitstrings via
        ``result.circuit_results[0]``.  Reverse each bitstring key to get the
        row-major grid solution.
    """
    from qiskit.circuit.library import PhaseOracleGate
    from qiskit.primitives import StatevectorSampler
    from qiskit_algorithms import AmplificationProblem, Grover

    expression = puzzle_to_boolean(row_clues=puzzle[0], col_clues=puzzle[1])
    oracle = PhaseOracleGate(expression)
    problem = AmplificationProblem(oracle)  # auto-infers is_good_state
    grover = Grover(sampler=StatevectorSampler())
    return grover.amplify(problem)


# Real hardware path (IBM Qiskit Runtime)


# One parameter per hardware-run knob; a config object would only rename them.
def quantum_solve_hardware(  # noqa: PLR0913
    puzzle: tuple[list, list],
    token: str,
    backend_name: str | None = None,
    channel: str = "ibm_quantum_platform",
    shots: int = 1024,
    iterations: int = 1,
    dynamical_decoupling: bool = True,
    twirling: bool = True,
) -> tuple[dict[str, int], str]:
    """Solve a nonogram using Grover's algorithm on real IBM quantum hardware.

    The Grover circuit is constructed, transpiled to the backend's native gate
    set, and submitted via qiskit-ibm-runtime.  The job is synchronous from
    the caller's perspective (``job.result()`` blocks until the IBM job
    completes).

    Grover iteration count guidance
    --------------------------------
    For a puzzle with exactly 1 solution and an n-qubit search space the
    noiseless peak probability after k iterations is:

        P(k) = sin²((2k + 1) · arcsin(1 / √2ⁿ))

    A few reference values for n = 9 (3 × 3 grid, 1 solution / 512 states):

        k = 1 → P ≈  1.7 %   (barely above random ≈ 0.2 %)
        k = 3 → P ≈  9.3 %   ✓ passes the > 5 % hardware threshold
        k = 5 → P ≈ 21.8 %
        k = 9 → P ≈ 55.4 %

    More iterations amplify the signal but also deepen the circuit, making
    hardware noise worse.  ``iterations=3`` is a reasonable default for 9-qubit
    puzzles on current NISQ hardware.

    Args:
        puzzle:               (row_clues, col_clues) tuple.
        token:                IBM Quantum API token.
        backend_name:         Specific backend name (e.g. ``"ibm_brisbane"``).
                              If ``None`` the least-busy operational backend is
                              chosen.
        channel:              Runtime channel.  Use ``"ibm_quantum_platform"``
                              (default, qiskit-ibm-runtime ≥ 0.30) or
                              ``"ibm_cloud"``.
        shots:                Number of measurement shots (default 1024).
        iterations:           Grover iteration count (default 1).  Increase to
                              3 for cleaner signal on 9-qubit (3 × 3) puzzles;
                              lower values keep the circuit shallower.
        dynamical_decoupling: Enable IBM Runtime dynamical-decoupling pulse
                              sequences (default True).  Suppresses idle-qubit
                              decoherence.
        twirling:             Enable Pauli gate + measurement twirling
                              (default True).  Converts coherent errors to
                              depolarising noise, improving result reliability.

    Returns:
        ``(counts_dict, backend_name)`` where *counts_dict* maps bitstring →
        count. Reverse each bitstring key (``bs[::-1]``) to get the row-major grid.

    Raises:
        ImportError:  if ``qiskit-ibm-runtime`` is not installed.
        RuntimeError: on authentication failure or job error.
    """
    from qiskit import transpile as _transpile
    from qiskit.circuit.library import PhaseOracleGate
    from qiskit_algorithms import AmplificationProblem, Grover
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

    # Connect
    service = QiskitRuntimeService(channel=channel, token=token)
    if backend_name:
        backend = service.backend(backend_name)
    else:
        # Prefer real hardware; fall back to the least-busy simulator if none
        # are available.
        try:
            backend = service.least_busy(operational=True, simulator=False)
        except Exception:
            backend = service.least_busy(operational=True)

    # Build Grover circuit
    expression = puzzle_to_boolean(row_clues=puzzle[0], col_clues=puzzle[1])
    oracle = PhaseOracleGate(expression)
    problem = AmplificationProblem(oracle)

    # construct_circuit returns an unmeasured QuantumCircuit; we add measurements.
    grover = Grover(iterations=iterations)
    circuit = grover.construct_circuit(problem, measurement=True)

    # Level 3 minimises gate count: on NISQ hardware every extra gate adds noise.
    transpiled = _transpile(circuit, backend=backend, optimization_level=3)

    # Record the classical register names *before* submission.  IBM's own docs
    # say: "use circuit.cregs to find the name of the classical register."
    # measure_all() always creates one called "meas", but the name is read here
    # from the actual transpiled object so the code never assumes it.
    if not transpiled.cregs:
        raise HardwareError(
            "Transpiled Grover circuit has no classical registers — "
            "measurements were not added correctly."
        )
    creg_names = [cr.name for cr in transpiled.cregs]

    # Submit and wait
    sampler = SamplerV2(backend)
    sampler.options.default_shots = shots

    # Error-mitigation options
    # Dynamical decoupling inserts pulse sequences during idle qubit periods
    # to suppress decoherence — always a win on real hardware.
    if dynamical_decoupling:
        try:
            sampler.options.dynamical_decoupling.enable = True
            # XpXm sequence works well across IBM Eagle/Heron backends.
            sampler.options.dynamical_decoupling.sequence_type = "XpXm"
        except Exception:  # noqa: S110 — best-effort: option not supported by this runtime version
            pass

    # Pauli gate + measurement twirling converts coherent errors into
    # depolarising noise, which is easier to characterise and average away.
    if twirling:
        try:
            sampler.options.twirling.enable_gates = True
            sampler.options.twirling.enable_measure = True
        except Exception:  # noqa: S110 — best-effort: option not supported by this runtime version
            pass

    job = sampler.run([transpiled])
    result = job.result()  # blocks until IBM job is complete

    counts = extract_counts(result[0].data, creg_names)
    return counts, backend.name


def extract_counts(data, creg_names: list[str]) -> dict[str, int]:
    """Extract measurement counts from a Qiskit DataBin.

    The BitArray is found by name where the transpiled circuit reports one, and by
    scanning the DataBin's public attributes where it does not.

    Parameters
    ----------
    data
        The ``.data`` attribute from a Qiskit Runtime PubResult.
    creg_names : list[str]
        Classical register names from the transpiled circuit.

    Returns
    -------
    dict[str, int]
        Bitstring-to-count mapping.

    Raises
    ------
    QuantumSolverError
        If no attribute yields a BitArray with ``.get_counts()``.
    """

    def _bit_array(attr_name: str):
        candidate = getattr(data, attr_name, None)
        return candidate if hasattr(candidate, "get_counts") else None

    names = [*creg_names, *getattr(data, "_fields", ()), *_public_attrs(data)]
    for name in names:
        found = _bit_array(name)
        if found is not None:
            return found.get_counts()

    raise QuantumSolverError(
        f"Could not extract measurement counts from DataBin.\n"
        f"Circuit classical registers:  {creg_names}\n"
        f"DataBin public attributes:    {_public_attrs(data)[:30]}"
    )


def _public_attrs(data) -> list[str]:
    return [a for a in dir(data) if not a.startswith("_")]


# Backend enumeration helper (used by the GUI settings dialog)


def list_backends(
    token: str,
    channel: str = "ibm_quantum_platform",
) -> list[tuple[str, int, int]]:
    """Return available IBM backends sorted by queue length.

    Args:
        token:   IBM Quantum API token.
        channel: ``"ibm_quantum_platform"`` (default) or ``"ibm_cloud"``.

    Returns:
        List of ``(name, num_qubits, pending_jobs)`` sorted shortest queue first.
        *pending_jobs* is ``-1`` when the status cannot be retrieved.
    """
    from qiskit_ibm_runtime import QiskitRuntimeService

    service = QiskitRuntimeService(channel=channel, token=token)
    backends = service.backends(operational=True)

    info: list[tuple[str, int, int]] = []
    for b in backends:
        try:
            pending = b.status().pending_jobs
        except Exception:
            pending = -1
        info.append((b.name, b.num_qubits, pending))

    return sorted(info, key=lambda x: x[2])
