# Quantum Nonogram Solver

Solves [nonogram](https://en.wikipedia.org/wiki/Nonogram) (Picross) puzzles two ways — by brute-force SAT search and by Grover's algorithm in Qiskit — and reports solve time, circuit depth and gate counts for both. Grover circuits run on the local statevector simulator or on IBM hardware through Qiskit Runtime. The repo holds a Python library and a JSON API over Flask and Socket.IO. The browser UI that calls this API lives in the website repo.

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

The 2×2 all-2s puzzle on `ibm_torino`, one Grover iteration, measured the correct `1111` state at 32.3%. The noiseless peak for one iteration on four qubits is 47.3%, and a uniform guess is 6.25%. That figure comes from a single 1,024-shot run whose counts and job ID were never archived; the hardware tests now write each run's counts, job ID, backend and transpiled depth to `runs/hardware/`, which is gitignored.

Circuit depth is what limits this. `PhaseOracleGate` compiles the nonogram constraint through general boolean synthesis, and depth grows fast:

| Puzzle | Qubits | Transpiled depth | What happens on hardware |
|--------|--------|-----------------|--------------------------|
| 2×2 | 4 | ~142 | the solution state stands out from the noise |
| 3×3 | 9 | ~2,900 | noise dominates; the run only tests the pipeline |
| 4×4 and up | 16+ | >10,000 | nothing usable comes back |

For M solutions among N = 2ⁿ states, the noiseless probability of measuring a solution after k iterations is P(k) = sin²((2k+1)·arcsin(√(M/N))) (Boyer, Brassard, Høyer & Tapp, [quant-ph/9605034](https://arxiv.org/abs/quant-ph/9605034)). `nonogram.quantum.grover_success_probability` computes it, and `classical_solve` confirms both puzzles below have exactly one solution:

| Grid | k=1 | k=3 | k=5 | k=9 |
|------|-----|-----|-----|-----|
| 2×2 all-2s (N=16) | 47.3% | 96.1% | 12.5% | 99.2% |
| 3×3 all-3s (N=512) | 1.7% | 9.3% | 21.8% | 55.4% |

P(k) is periodic: for the 2×2 grid it peaks near k=3 and has fallen again by k=5, so more iterations are not automatically better.

## Setup

```bash
make env          # conda environment + editable pip install
```

Or by hand:

```bash
conda env create --prefix .conda --file environment.yml
pip install -e .
```

`python tools/webapp.py` starts the API on `http://localhost:8080`; set `PORT` to move it. `make app` does the same, `make test` runs the suite and `make bench` runs the size-by-size comparison.

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

A quantum result carries the raw `counts` and an `outcomes` list — the same distribution ranked by probability, with each bitstring already reversed into row-major order, which is what a histogram is drawn from:

```json
{"outcomes": [{"bitstring": "1001", "grid": "1001", "count": 500, "probability": 0.49}]}
```

Add `"chart": true` to a quantum request and the response also carries `chart_img`, a base64 PNG of that distribution, for callers that would rather not draw it.

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

`benchmark()` runs both solvers on one puzzle and captures:

| Metric | Classical | Quantum |
|---|---|---|
| Wall-clock solve time | ✓ | ✓ |
| Peak memory | ✓ | ✓ |
| Solutions found | ✓ | ✓ |
| Configurations evaluated | 2^(n·d) | — |
| Throughput (configs/s) | ✓ | — |
| Clause, subclause and literal evaluations | ✓ | — |
| Qubits, circuit depth, gate counts | — | ✓ |
| Grover iterations | — | ✓ |
| Top-state measurement probability | — | ✓ |
| Theoretical Grover speedup √N | derived | derived |
| Actual speedup (time ratio) | derived | derived |
| Oracle call reduction | derived | derived |

`print_report(report)` prints all of it; `tools/chart.report_to_dict(report)` is the same data as JSON, which is what the API returns. The classical side is exponential in grid area, so benchmark small: a 2×3 answers instantly, the 4×6 demo puzzle takes about 18 minutes.

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
