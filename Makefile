# ──────────────────────────────────────────────────────────────────────────────
# Nonogram Solver — project tasks
# ──────────────────────────────────────────────────────────────────────────────
# Requires: conda (miniconda3 or anaconda)
#
# Quick start:
#   make env      # create / update the conda environment from environment.yml
#   make kernel   # register the Jupyter kernel so any JupyterLab can see it
#   make lab      # launch JupyterLab in the browser
#   make app      # launch the web app (Flask)
#   make test     # run the test suite
# ──────────────────────────────────────────────────────────────────────────────

CONDA_BIN   ?= $(shell command -v conda 2>/dev/null || echo conda)
ENV_PREFIX   = $(CURDIR)/.conda
PYTHON       = $(ENV_PREFIX)/bin/python
PIP          = $(ENV_PREFIX)/bin/pip
JUPYTER      = $(ENV_PREFIX)/bin/jupyter
PYTEST       = $(ENV_PREFIX)/bin/pytest

KERNEL_NAME  = quantum-nonogram
KERNEL_LABEL = Quantum Nonogram (Python 3.11)

.PHONY: help env install kernel lab app test clean

# ── help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  make env      Create / update the conda environment (.conda/)"
	@echo "  make install  pip install -e . inside the conda environment"
	@echo "  make kernel   Register the Jupyter kernel (user-level, visible everywhere)"
	@echo "  make lab      Launch JupyterLab"
	@echo "  make app      Launch the web app (Flask)"
	@echo "  make test     Run pytest"
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

# ── kernel ────────────────────────────────────────────────────────────────────
# Registers the kernel at the user level (~/.local/share/jupyter/kernels on Linux,
# ~/Library/Jupyter/kernels on macOS) so it appears in every JupyterLab instance.
kernel:
	@echo "→ Registering Jupyter kernel '$(KERNEL_NAME)' …"
	$(PYTHON) -m ipykernel install \
		--user \
		--name "$(KERNEL_NAME)" \
		--display-name "$(KERNEL_LABEL)"
	@echo "✓ Kernel '$(KERNEL_LABEL)' registered."
	@echo "  Spec: $$($(JUPYTER) kernelspec list | grep $(KERNEL_NAME))"

# ── lab ───────────────────────────────────────────────────────────────────────
lab:
	@echo "→ Launching JupyterLab (kernel: $(KERNEL_LABEL)) …"
	$(JUPYTER) lab --notebook-dir=$(CURDIR)/notebooks

# ── app ───────────────────────────────────────────────────────────────────────
app:
	@echo "→ Launching Nonogram Web App …"
	$(PYTHON) tools/webapp.py

# ── test ──────────────────────────────────────────────────────────────────────
test:
	$(PYTEST) tests/ -v

# ── clean ─────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -not -path './.conda/*' -exec rm -rf {} + 2>/dev/null || true
	find . -name .DS_Store -delete 2>/dev/null || true
	rm -rf .pytest_cache build *.egg-info nonogram.egg-info
	@echo "✓ Cleaned."
