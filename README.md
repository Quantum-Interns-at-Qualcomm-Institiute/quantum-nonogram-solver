# Quantum Nonogram Solver

Solves [nonogram](https://en.wikipedia.org/wiki/Nonogram) (Picross) puzzles two ways — by brute-force SAT search and by Grover's algorithm in Qiskit — and reports solve time, circuit depth and gate counts for both. Grover circuits run on the local statevector simulator or on IBM hardware through Qiskit Runtime. The repo holds a Python library, a JSON API over Flask and Socket.IO, and a demo notebook. The browser UI that calls this API lives in the website repo.

```
Example: 4×6 puzzle              Solution:
Row clues:  (1,1), (2,2),        ╔══════╗
            (1,2,1), (1,1)       ║■□□□□■║
Col clues:  (4),(1),(1),         ║■■□□■■║
            (1),(1),(4)          ║■□■■□■║
                                 ║■□□□□■║
                                 ╚══════╝
```

## Results on hardware

The 2×2 all-2s puzzle on `ibm_torino`, one Grover iteration, measured the correct `1111` state at 32.3%. The noiseless peak for one iteration on four qubits is 47.3%, and a uniform guess is 6.25%.

Circuit depth is what limits this. `PhaseOracleGate` compiles the nonogram constraint through general boolean synthesis, and depth grows fast:

| Puzzle | Qubits | Transpiled depth | What happens on hardware |
|--------|--------|-----------------|--------------------------|
| 2×2 | 4 | ~142 | the solution state stands out from the noise |
| 3×3 | 9 | ~2,900 | noise dominates; the run only tests the pipeline |
| 4×4 and up | 16+ | >10,000 | nothing usable comes back |

Noiseless peak probability after k iterations is P(k) = sin²((2k+1)·arcsin(1/√2ⁿ)):

| Grid | k=1 | k=3 | k=5 |
|------|-----|-----|-----|
| 2×2 (n=4) | 47.3% | 96.1% | 12.5% |
| 3×3 (n=9) | 1.7% | 9.3% | 21.8% |

## Setup

```bash
make env          # conda environment + editable pip install
```

Or by hand:

```bash
conda env create --prefix .conda --file environment.yml
pip install -e .
```

`python tools/webapp.py` starts the API on `http://localhost:8080`; set `PORT` to move it. `make app` does the same, `make lab` starts JupyterLab with the demo notebook, and `make test` runs the suite.

## The API

`GET /api` lists every endpoint and every Socket.IO event, so the surface is discoverable with curl alone:

```bash
export SECRET=dev-secret
ORIGIN_SECRET=$SECRET PORT=8080 python tools/webapp.py &
curl -s localhost:8080/health
curl -s -H "X-Origin-Secret: $SECRET" localhost:8080/api | python -m json.tool

curl -s -X POST localhost:8080/api/solve/classical/sync \
  -H "X-Origin-Secret: $SECRET" -H 'Content-Type: application/json' \
  -d '{"row_clues": [[2],[2]], "col_clues": [[2],[2]]}'
```

Every solve has an asynchronous form that answers `{"ok": true}` and delivers the result over Socket.IO (`cl_done`, `qu_done`, `bench_done`), and a `/sync` form that returns it in the HTTP response. Errors share one envelope: `{"error": {"code": "<slug>", "message": "<human>"}}`.

Two things guard the service. Every route but `/health` needs the gateway's `X-Origin-Secret`, and with `ORIGIN_SECRET` unset the API refuses to serve at all unless you pass `NONOGRAM_ALLOW_INSECURE=1` for local work. Solves are capped at 20 grid cells, because both solvers are exponential in area, and one solve runs at a time — a second request gets a 409 while the first is running.

## Deployment

The `Dockerfile` runs gunicorn with a single threaded worker, since server state is per-process, and `railway.json` points Railway's health check at `/health`. TLS is the platform edge's job. Set `ORIGIN_SECRET` and, for hardware runs, `IBM_QUANTUM_TOKEN` as deployment secrets.

```bash
docker build -t nonogram .
docker run -p 8080:8080 -e ORIGIN_SECRET=dev-secret nonogram
```

## Solving from Python

```python
from nonogram import classical_solve, quantum_solve, display_nonogram

puzzle = (
    [(1, 1), (2, 2), (1, 2, 1), (1, 1)],   # row clues
    [(4,),   (1,),   (1,),   (1,),  (1,),  (4,)],   # col clues
)

for bs in classical_solve(puzzle):
    display_nonogram(bs, n=4, d=6)

result = quantum_solve(puzzle)
```

`nonogram/solver.py` holds the three solvers; `ClassicalSolver().solve(puzzle)` returns `{"solutions": [...]}` and `QuantumSimulatorSolver().solve(puzzle)` returns `{"counts": {...}}`. `ValidationError` is also a `ValueError` and `PuzzleIOError` is also an `OSError`, so ordinary `except` clauses still catch them.

## How it works

Each cell of the `n×d` grid becomes a Boolean variable. Each clue expands into the set of bitstrings that satisfy it, looked up from `data.py`; a line's constraint is the disjunction of those, and the puzzle's constraint is the conjunction over every row and column.

The classical solver walks all 2^(n·d) candidates and evaluates the clause list, so it is O(2^(n·d)). The quantum solver hands the same expression to Qiskit's `PhaseOracleGate`, wraps it in an `AmplificationProblem` and runs `Grover.amplify()`, which takes O(√2^(n·d)) oracle queries.

| Puzzle | Variables | Search space | Classical time |
|--------|-----------|-------------|---------------|
| 2×2 | 4 | 16 | < 1 ms |
| 3×3 | 9 | 512 | ~50 ms |
| 4×4 | 16 | 65,536 | ~2 s |
| 4×6 | 24 | 16.7 M | ~18 min |
| 6×6 | 36 | 68.7 B | days |
| 10×10 | 100 | ~1.27×10³⁰ | not run |

## Running on IBM hardware

Install `qiskit-ibm-runtime` and set `IBM_QUANTUM_TOKEN` in the environment, or put `IBM_QUANTUM_TOKEN=...` in a `.env` file at the repo root. The server holds the token: `/api/hw/backends` and `/api/hw/config` never accept one from a caller, so nobody else can spend the account's credits. With no token configured those routes answer 503 and the solver stays on the local simulator. From Python:

```python
from nonogram.quantum import quantum_solve_hardware, list_backends

backends = list_backends(token="...", channel="ibm_quantum_platform")
for name, qubits, pending in backends:
    print(f"{name:26s}  {qubits:3d}q  queue: {pending}")

counts, backend_name = quantum_solve_hardware(
    puzzle=([(2,), (2,)], [(2,), (2,)]),
    token="...",
    channel="ibm_quantum_platform",
    shots=1024,
    iterations=1,
    dynamical_decoupling=True,   # suppress idle-qubit decoherence
    twirling=True,               # Pauli gate + measurement twirling
)

# Qiskit returns little-endian bitstrings; reverse for row-major order
for bs, count in sorted(counts.items(), key=lambda x: -x[1])[:5]:
    print(f"{bs[::-1]}  {count:4d}  ({count/sum(counts.values()):.1%})")
```

## Benchmarking

```python
from nonogram import benchmark, print_report

report = benchmark(([(2,), (2,)], [(2,), (2,)]), run_classical=True, run_quantum=True)
print_report(report)
```

The report carries both solve times, the theoretical and measured speedup, qubit count, circuit depth, gate counts, peak memory and whether the solution checks out.

## Puzzle files

```json
{
  "name": "My Puzzle",
  "rows": 4,
  "cols": 6,
  "row_clues": [[1, 1], [2, 2], [1, 2, 1], [1, 1]],
  "col_clues": [[4], [1], [1], [1], [1], [4]],
  "created": "2026-03-11T12:00:00+00:00",
  "tags": []
}
```

`save_puzzle` and `load_puzzle` read and write these.

## Testing

```bash
make test                                     # everything that runs offline
make test-hardware                            # the IBM tests; spends credits
pytest tests/test_hardware_2x2.py -v -s -m hardware   # one circuit
```

Three tests reach IBM: `test_list_backends_auth` (one REST call), `test_hardware_2x2.py` and `test_hardware_3x3.py` (one circuit each). They carry the `hardware` marker and `pytest.ini` deselects it, so a token in your environment is not on its own enough to spend credits. Everything else runs offline.

## Limitations

- The `possible_d` lookup table in `data.py` covers line lengths 1–10, so puzzles top out at 10×10.
- Simulating Grover is exponential. Puzzles above roughly 3×3 take minutes to hours locally.
- Boolean synthesis produces circuits too deep for current hardware above 2×2, so there is no speedup to show on a real machine.
- Qiskit returns little-endian bitstrings. Reverse each key (`bs[::-1]`) to read it as a row-major grid.

## License

MIT.
