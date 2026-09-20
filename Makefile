# ──────────────────────────────────────────────────────────────────────────────
# Nonogram Solver — project tasks
# ──────────────────────────────────────────────────────────────────────────────
# Requires: conda (miniconda3 or anaconda)
#
# Quick start:
#   make env      # create / update the conda environment from environment.yml
#   make app      # launch the API (Flask)
#   make test     # run the test suite
# ──────────────────────────────────────────────────────────────────────────────

CONDA_BIN   ?= $(shell command -v conda 2>/dev/null || echo conda)
ENV_PREFIX   = $(CURDIR)/.conda
PYTHON       = $(ENV_PREFIX)/bin/python
PIP          = $(ENV_PREFIX)/bin/pip
PYTEST       = $(ENV_PREFIX)/bin/pytest
RUFF         = $(ENV_PREFIX)/bin/ruff

.PHONY: help env install app test test-hardware bench lock lint clean

# ── help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  make env      Create / update the conda environment (.conda/)"
	@echo "  make install  pip install -e . inside the conda environment"
	@echo "  make app      Launch the API (Flask)"
	@echo "  make test     Run pytest (hardware tests deselected)"
	@echo "  make test-hardware  Run the IBM hardware tests (spends credits)"
	@echo "  make bench    Run the Grover vs brute-force comparison"
	@echo "  make lock     Regenerate requirements.lock (needs Docker)"
	@echo "  make lint     Run ruff over the whole repo"
	@echo "  make clean    Remove __pycache__ and .pytest_cache"
	@echo ""

# ── env ───────────────────────────────────────────────────────────────────────
env:
	@echo "→ Creating / updating conda environment at $(ENV_PREFIX) …"
	$(CONDA_BIN) env update \
		--prefix $(ENV_PREFIX) \
		--file environment.yml \
		--prune
	@echo "→ Installing nonogram package in editable mode …"
	$(PIP) install -e . --quiet
	@echo "✓ Environment ready."

# ── install ───────────────────────────────────────────────────────────────────
install:
	$(PIP) install -e . --quiet
	@echo "✓ nonogram package installed (editable)."

# ── app ───────────────────────────────────────────────────────────────────────
app:
	@echo "→ Launching Nonogram Web App …"
	$(PYTHON) tools/webapp.py

# ── test ──────────────────────────────────────────────────────────────────────
# Hardware tests are deselected by pytest.ini; test-hardware asks for them and
# spends real IBM Quantum credits.
test:
	$(PYTEST) tests/ -v

test-hardware:
	$(PYTEST) tests/ -v -s -m hardware

# ── bench ─────────────────────────────────────────────────────────────────────
bench:
	$(PYTHON) tools/benchmark_comparison.py

# ── lock ──────────────────────────────────────────────────────────────────────
# Runs in the image the Dockerfile builds from, so the pins match that platform.
lock:
	docker run --rm -v "$(CURDIR)":/src -w /src python:3.12-slim \
	  sh -c 'pip install --quiet . && pip freeze --exclude-editable | grep -v "^nonogram" > requirements.lock'
	@echo "✓ requirements.lock regenerated."

# ── lint ──────────────────────────────────────────────────────────────────────
lint:
	$(RUFF) check .

# ── clean ─────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -not -path './.conda/*' -exec rm -rf {} + 2>/dev/null || true
	find . -name .DS_Store -delete 2>/dev/null || true
	rm -rf .pytest_cache build *.egg-info nonogram.egg-info
	@echo "✓ Cleaned."
