# Contributing

This project was developed as an internship deliverable at the Qualcomm
Institute, UC San Diego. We welcome issues and pull requests.

## Getting started

```bash
git clone https://github.com/Quantum-Interns-at-Qualcomm-Institiute/quantum-nonogram-solver.git
cd quantum-nonogram-solver
pip install -e "."
```

## Before submitting a PR

1. Run the test suite and ensure all tests pass:
   ```bash
   pytest tests/ -v
   ```

2. Run the linter:
   ```bash
   ruff check .
   ```

3. Format your code:
   ```bash
   ruff format .
   ```
