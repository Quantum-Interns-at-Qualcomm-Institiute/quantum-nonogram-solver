"""Phase 2 infrastructure test suite.

Tests cover WPs #728-#731:
  - #728: Docker image build reproducibility
  - #729: UI-kit component rendering in solver frontend
  - #730: CI pipeline green path
  - #731: Production readiness checklist
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NONOGRAM_PKG = ROOT / "nonogram"
TOOLS_DIR = ROOT / "tools"
WEBSITE_DIR = ROOT / "website"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_module(path: Path) -> ast.Module:
    return ast.parse(_read(path), filename=str(path))


def _function_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
    return names


def _class_names(tree: ast.Module) -> set[str]:
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}


# ===================================================================
# #728 — Docker image build reproducibility
# ===================================================================

class TestDockerBuildReproducibility:
    """WP #728: Docker image builds are reproducible and well-structured."""

    def test_dockerfile_exists(self):
        assert (ROOT / "Dockerfile").is_file()

    def test_docker_compose_exists(self):
        assert (ROOT / "docker-compose.yml").is_file()

    def test_dockerfile_uses_pinned_base_image(self):
        src = _read(ROOT / "Dockerfile")
        assert re.search(r"FROM python:\d+\.\d+", src), (
            "Dockerfile should pin the Python base image version"
        )

    def test_dockerfile_copies_source_code(self):
        src = _read(ROOT / "Dockerfile")
        assert "COPY nonogram/" in src, "Dockerfile must copy nonogram package"
        assert "COPY tools/" in src, "Dockerfile must copy tools package"
        assert "COPY pyproject.toml" in src, "Dockerfile must copy pyproject.toml"

    def test_dockerfile_installs_package(self):
        src = _read(ROOT / "Dockerfile")
        assert "pip install" in src

    def test_dockerfile_no_cache_dir(self):
        """Reproducibility: pip install should use --no-cache-dir."""
        src = _read(ROOT / "Dockerfile")
        assert "--no-cache-dir" in src

    def test_dockerfile_exposes_port(self):
        src = _read(ROOT / "Dockerfile")
        assert re.search(r"EXPOSE\s+\d+", src)

    def test_dockerfile_has_cmd(self):
        src = _read(ROOT / "Dockerfile")
        assert "CMD" in src

    def test_docker_compose_defines_service(self):
        src = _read(ROOT / "docker-compose.yml")
        assert "nonogram" in src, "docker-compose must define 'nonogram' service"

    def test_docker_compose_maps_port(self):
        src = _read(ROOT / "docker-compose.yml")
        assert "5055" in src, "docker-compose must map port 5055"

    def test_dockerfile_generates_ssl_certs(self):
        src = _read(ROOT / "Dockerfile")
        assert "openssl" in src, "Dockerfile should generate dev SSL certs"
        assert "cert.pem" in src
        assert "key.pem" in src

    def test_dockerfile_sets_workdir(self):
        src = _read(ROOT / "Dockerfile")
        assert "WORKDIR" in src


# ===================================================================
# #729 — UI-kit component rendering in solver frontend
# ===================================================================

class TestUIKitComponents:
    """WP #729: Frontend uses UI-kit components and renders correctly."""

    def test_website_index_exists(self):
        assert (WEBSITE_DIR / "index.html").is_file()

    def test_ui_kit_css_linked(self):
        src = _read(WEBSITE_DIR / "index.html")
        assert "ui-kit.css" in src, "Frontend must link ui-kit.css"

    def test_ui_kit_js_loaded(self):
        src = _read(WEBSITE_DIR / "index.html")
        assert "ui-kit.js" in src, "Frontend must load ui-kit.js"

    def test_theme_bootstrap_loaded(self):
        src = _read(WEBSITE_DIR / "index.html")
        assert "theme-bootstrap.js" in src, (
            "theme-bootstrap.js must be loaded for theming"
        )

    def test_service_config_loaded(self):
        src = _read(WEBSITE_DIR / "index.html")
        assert "service-config.js" in src, (
            "service-config.js must be loaded for backend URL resolution"
        )

    def test_site_nav_loaded(self):
        src = _read(WEBSITE_DIR / "index.html")
        assert "site-nav.js" in src, "site-nav.js must be loaded for navigation"

    def test_icons_loaded(self):
        src = _read(WEBSITE_DIR / "index.html")
        assert "icons.js" in src, "icons.js must be loaded for UI icons"

    def test_data_theme_attribute(self):
        src = _read(WEBSITE_DIR / "index.html")
        assert "data-theme" in src, "HTML element should have data-theme attribute"

    def test_frontend_css_exists(self):
        assert (WEBSITE_DIR / "static" / "style.css").is_file()

    def test_frontend_app_js_exists(self):
        assert (WEBSITE_DIR / "static" / "app.js").is_file()

    def test_frontend_has_solver_controls(self):
        src = _read(WEBSITE_DIR / "index.html")
        assert "btn-bench" in src, "Must have benchmark button"
        assert "trials-input" in src, "Must have trials input"

    def test_frontend_has_grid_views(self):
        src = _read(WEBSITE_DIR / "index.html")
        assert "draw-view" in src, "Must have draw view"
        assert "clues-view" in src, "Must have clues view"

    def test_frontend_has_solution_panels(self):
        src = _read(WEBSITE_DIR / "index.html")
        assert "cl-half" in src, "Must have classical solution panel"
        assert "qu-half" in src, "Must have quantum solution panel"

    def test_frontend_has_histogram(self):
        src = _read(WEBSITE_DIR / "index.html")
        assert "qu-histogram" in src, "Must have quantum histogram SVG"

    def test_frontend_has_settings_panel(self):
        src = _read(WEBSITE_DIR / "index.html")
        assert "console-panel" in src, "Must have settings panel"

    def test_frontend_has_theme_toggle(self):
        src = _read(WEBSITE_DIR / "index.html")
        assert "theme-toggle" in src, "Must have theme toggle button"

    def test_socket_io_loaded(self):
        src = _read(WEBSITE_DIR / "index.html")
        assert "socket.io" in src, "Socket.IO client must be loaded"

    def test_meta_nav_label(self):
        src = _read(WEBSITE_DIR / "index.html")
        assert "site-nav-label" in src, "Must have site-nav-label meta tag"

    def test_meta_backend_service(self):
        src = _read(WEBSITE_DIR / "index.html")
        assert "site-backend-service" in src, (
            "Must have site-backend-service meta tag"
        )

    def test_js_test_suite_exists(self):
        assert (WEBSITE_DIR / "tests").is_dir(), "Frontend must have a tests directory"


# ===================================================================
# #730 — CI pipeline green path
# ===================================================================

class TestCIPipelineGreenPath:
    """WP #730: CI workflow is valid and covers necessary steps."""

    def test_ci_workflow_exists(self):
        ci_path = ROOT / ".github" / "workflows" / "tests.yml"
        assert ci_path.is_file(), "CI workflow file must exist"

    def test_ci_triggers_on_push_and_pr(self):
        src = _read(ROOT / ".github" / "workflows" / "tests.yml")
        assert "push" in src, "CI must trigger on push"
        assert "pull_request" in src, "CI must trigger on pull_request"

    def test_ci_targets_main_branch(self):
        src = _read(ROOT / ".github" / "workflows" / "tests.yml")
        assert "main" in src, "CI must target main branch"

    def test_ci_has_python_matrix(self):
        src = _read(ROOT / ".github" / "workflows" / "tests.yml")
        assert "matrix" in src, "CI must use a Python version matrix"
        assert "python-version" in src

    def test_ci_tests_python_310(self):
        src = _read(ROOT / ".github" / "workflows" / "tests.yml")
        assert "3.10" in src, "CI must test Python 3.10"

    def test_ci_tests_python_312(self):
        src = _read(ROOT / ".github" / "workflows" / "tests.yml")
        assert "3.12" in src, "CI must test Python 3.12"

    def test_ci_runs_pytest(self):
        src = _read(ROOT / ".github" / "workflows" / "tests.yml")
        assert "pytest" in src, "CI must run pytest"

    def test_ci_runs_linter(self):
        src = _read(ROOT / ".github" / "workflows" / "tests.yml")
        assert "ruff" in src, "CI must run ruff linter"

    def test_ci_installs_dependencies(self):
        src = _read(ROOT / ".github" / "workflows" / "tests.yml")
        assert "pip install" in src

    def test_ci_uses_checkout_action(self):
        src = _read(ROOT / ".github" / "workflows" / "tests.yml")
        assert "actions/checkout" in src

    def test_ci_uses_setup_python_action(self):
        src = _read(ROOT / ".github" / "workflows" / "tests.yml")
        assert "actions/setup-python" in src

    def test_ci_docker_build_job(self):
        src = _read(ROOT / ".github" / "workflows" / "tests.yml")
        assert "docker" in src.lower(), "CI should have a Docker build job"
        assert "docker build" in src

    def test_ci_skips_slow_tests(self):
        src = _read(ROOT / ".github" / "workflows" / "tests.yml")
        assert "not slow" in src, "CI should skip slow-marked tests"

    def test_pytest_ini_defines_slow_marker(self):
        src = _read(ROOT / "pytest.ini")
        assert "slow" in src, "pytest.ini must define the 'slow' marker"


# ===================================================================
# #731 — Production readiness checklist
# ===================================================================

class TestProductionReadiness:
    """WP #731: Production readiness checklist items."""

    def test_pyproject_toml_exists(self):
        assert (ROOT / "pyproject.toml").is_file()

    def test_pyproject_defines_project_name(self):
        src = _read(ROOT / "pyproject.toml")
        assert 'name = "nonogram"' in src

    def test_pyproject_defines_version(self):
        src = _read(ROOT / "pyproject.toml")
        assert "version" in src

    def test_pyproject_requires_python(self):
        src = _read(ROOT / "pyproject.toml")
        assert "requires-python" in src

    def test_pyproject_lists_dependencies(self):
        src = _read(ROOT / "pyproject.toml")
        assert "dependencies" in src
        assert "flask" in src.lower()
        assert "qiskit" in src.lower()
        assert "numpy" in src.lower()

    def test_pyproject_configures_ruff(self):
        src = _read(ROOT / "pyproject.toml")
        assert "[tool.ruff]" in src

    def test_license_file_exists(self):
        assert (ROOT / "LICENSE").is_file()

    def test_readme_exists(self):
        assert (ROOT / "README.md").is_file()

    def test_makefile_exists(self):
        assert (ROOT / "Makefile").is_file()

    def test_makefile_has_test_target(self):
        src = _read(ROOT / "Makefile")
        assert "test:" in src or "test :" in src

    def test_makefile_has_app_target(self):
        src = _read(ROOT / "Makefile")
        assert "app:" in src or "app :" in src

    def test_error_hierarchy_exists(self):
        assert (NONOGRAM_PKG / "errors.py").is_file()

    def test_custom_exceptions_defined(self):
        tree = _parse_module(NONOGRAM_PKG / "errors.py")
        classes = _class_names(tree)
        assert "NonogramError" in classes
        assert "ValidationError" in classes
        assert "SolverError" in classes
        assert "QuantumSolverError" in classes
        assert "HardwareError" in classes
        assert "PuzzleIOError" in classes

    def test_package_exports_all(self):
        src = _read(NONOGRAM_PKG / "__init__.py")
        assert "__all__" in src, "Package must define __all__"

    def test_package_exports_key_symbols(self):
        src = _read(NONOGRAM_PKG / "__init__.py")
        for sym in [
            "classical_solve", "quantum_solve", "benchmark",
            "Solver", "ClassicalSolver", "QuantumSimulatorSolver",
            "validate", "puzzle_to_boolean",
        ]:
            assert sym in src, f"Package must export {sym}"

    def test_webapp_configures_cors(self):
        src = _read(TOOLS_DIR / "webapp.py")
        assert "CORS" in src, "Webapp must configure CORS"

    def test_webapp_has_api_config_endpoint(self):
        src = _read(TOOLS_DIR / "webapp.py")
        assert "/api/config" in src

    def test_webapp_ssl_context_support(self):
        src = _read(TOOLS_DIR / "webapp.py")
        assert "ssl_context" in src or "_get_ssl_context" in src

    def test_environment_yml_exists(self):
        assert (ROOT / "environment.yml").is_file()

    def test_contributing_md_exists(self):
        assert (ROOT / "CONTRIBUTING.md").is_file()
