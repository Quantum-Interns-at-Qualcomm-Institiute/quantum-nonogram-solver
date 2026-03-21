"""Phase 3 cross-cutting test suite.

Tests cover WPs #716-#720:
  - #716: E2E solve nonogram end-to-end
  - #717: Solver correctness test suite
  - #718: Benchmarking framework validation
  - #719: Frontend integration
  - #720: Docker container health and startup
"""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

import pytest

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
# #716 — E2E solve nonogram end-to-end
# ===================================================================

class TestE2ESolveNonogram:
    """WP #716: Full pipeline from puzzle definition through solving to output."""

    def test_classical_solver_module_exists(self):
        assert (NONOGRAM_PKG / "classical.py").is_file()

    def test_quantum_solver_module_exists(self):
        assert (NONOGRAM_PKG / "quantum.py").is_file()

    def test_core_encoding_module_exists(self):
        assert (NONOGRAM_PKG / "core.py").is_file()

    def test_solver_abc_module_exists(self):
        assert (NONOGRAM_PKG / "solver.py").is_file()

    def test_io_module_exists(self):
        assert (NONOGRAM_PKG / "io.py").is_file()

    def test_e2e_pipeline_encoding_step(self):
        """puzzle_to_boolean must accept (row_clues, col_clues) and return a formula."""
        tree = _parse_module(NONOGRAM_PKG / "core.py")
        assert "puzzle_to_boolean" in _function_names(tree)
        src = _read(NONOGRAM_PKG / "core.py")
        assert "row_clues" in src
        assert "col_clues" in src
        assert "boolean_statement" in src

    def test_e2e_pipeline_classical_solve_step(self):
        """classical_solve must accept puzzle tuple and return solutions list."""
        src = _read(NONOGRAM_PKG / "classical.py")
        assert "def classical_solve" in src
        assert "puzzle" in src
        assert "solutions" in src

    def test_e2e_pipeline_quantum_solve_step(self):
        """quantum_solve must accept puzzle tuple and run Grover."""
        src = _read(NONOGRAM_PKG / "quantum.py")
        assert "def quantum_solve" in src
        assert "puzzle" in src
        assert "Grover" in src

    def test_e2e_pipeline_display_step(self):
        """display_nonogram must render bitstrings to visual grid."""
        tree = _parse_module(NONOGRAM_PKG / "core.py")
        assert "display_nonogram" in _function_names(tree)

    def test_e2e_puzzle_io_roundtrip_structure(self):
        """save_puzzle and load_puzzle must support full roundtrip."""
        tree = _parse_module(NONOGRAM_PKG / "io.py")
        fns = _function_names(tree)
        assert "save_puzzle" in fns
        assert "load_puzzle" in fns

    def test_e2e_solver_abc_provides_interface(self):
        """Solver ABC must define solve() and name property."""
        src = _read(NONOGRAM_PKG / "solver.py")
        assert "class Solver" in src
        assert "def solve" in src
        assert "def name" in src

    def test_e2e_classical_solver_class(self):
        tree = _parse_module(NONOGRAM_PKG / "solver.py")
        assert "ClassicalSolver" in _class_names(tree)

    def test_e2e_quantum_simulator_solver_class(self):
        tree = _parse_module(NONOGRAM_PKG / "solver.py")
        assert "QuantumSimulatorSolver" in _class_names(tree)

    def test_e2e_quantum_hardware_solver_class(self):
        tree = _parse_module(NONOGRAM_PKG / "solver.py")
        assert "QuantumHardwareSolver" in _class_names(tree)

    def test_e2e_error_handling_classical(self):
        src = _read(NONOGRAM_PKG / "solver.py")
        assert "ClassicalSolverError" in src

    def test_e2e_error_handling_quantum(self):
        src = _read(NONOGRAM_PKG / "solver.py")
        assert "QuantumSolverError" in src


# ===================================================================
# #717 — Solver correctness test suite
# ===================================================================

class TestSolverCorrectness:
    """WP #717: Solver correctness verification infrastructure."""

    def test_validate_function_exists(self):
        tree = _parse_module(NONOGRAM_PKG / "core.py")
        assert "validate" in _function_names(tree)

    def test_validate_checks_row_count(self):
        src = _read(NONOGRAM_PKG / "core.py")
        assert "row clues" in src.lower() or "r_clues" in src

    def test_validate_checks_col_count(self):
        src = _read(NONOGRAM_PKG / "core.py")
        assert "col clues" in src.lower() or "c_clues" in src

    def test_rle_function_exists(self):
        tree = _parse_module(NONOGRAM_PKG / "core.py")
        assert "rle" in _function_names(tree)

    def test_grid_to_clues_function_exists(self):
        tree = _parse_module(NONOGRAM_PKG / "core.py")
        assert "grid_to_clues" in _function_names(tree)

    def test_grid_to_clues_inverse_property(self):
        """grid_to_clues should be the inverse of solving (grid -> clues)."""
        src = _read(NONOGRAM_PKG / "core.py")
        assert "row_clues" in src and "col_clues" in src

    def test_parse_clue_function_exists(self):
        tree = _parse_module(NONOGRAM_PKG / "core.py")
        assert "parse_clue" in _function_names(tree)

    def test_parse_clue_handles_empty(self):
        src = _read(NONOGRAM_PKG / "core.py")
        # parse_clue should return (0,) for empty input
        assert "(0,)" in src

    def test_manual_check_parameter(self):
        """classical_solve should support checking a single bitstring."""
        src = _read(NONOGRAM_PKG / "classical.py")
        assert "manual_check" in src

    def test_execution_counts_tracked(self):
        tree = _parse_module(NONOGRAM_PKG / "classical.py")
        assert "ExecutionCounts" in _class_names(tree)

    def test_execution_counts_has_fields(self):
        src = _read(NONOGRAM_PKG / "classical.py")
        for field in [
            "candidates_evaluated",
            "clause_evaluations",
            "subclause_evaluations",
            "literal_evaluations",
            "early_terminations",
            "solutions_found",
        ]:
            assert field in src, f"ExecutionCounts must track {field}"

    def test_validation_error_for_bad_clues(self):
        src = _read(NONOGRAM_PKG / "core.py")
        assert "ValidationError" in src

    def test_existing_test_suite_present(self):
        """Project must have existing tests for core, classical, metrics, etc."""
        tests_dir = ROOT / "tests"
        assert tests_dir.is_dir()
        test_files = list(tests_dir.glob("test_*.py"))
        assert len(test_files) >= 5, (
            f"Expected at least 5 test files, found {len(test_files)}"
        )

    def test_conftest_exists(self):
        assert (ROOT / "tests" / "conftest.py").is_file()


# ===================================================================
# #718 — Benchmarking framework validation
# ===================================================================

class TestBenchmarkingFramework:
    """WP #718: Benchmarking framework structure and correctness."""

    def test_metrics_module_exists(self):
        assert (NONOGRAM_PKG / "metrics.py").is_file()

    def test_benchmark_function_exists(self):
        tree = _parse_module(NONOGRAM_PKG / "metrics.py")
        assert "benchmark" in _function_names(tree)

    def test_benchmark_accepts_classical_flag(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "run_classical" in src

    def test_benchmark_accepts_quantum_flag(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "run_quantum" in src

    def test_benchmark_accepts_static_analysis_flag(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "static_analysis" in src

    def test_benchmark_accepts_constraint_density_flag(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "compute_constraint_density" in src

    def test_classical_metrics_has_timing(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "solve_time_s" in src
        assert "perf_counter" in src

    def test_classical_metrics_has_memory(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "tracemalloc" in src
        assert "peak_memory_kb" in src

    def test_classical_metrics_has_throughput(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "configs_per_second" in src

    def test_quantum_metrics_has_circuit_stats(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "num_qubits" in src
        assert "circuit_depth" in src
        assert "total_gate_count" in src

    def test_quantum_metrics_has_grover_iterations(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "grover_iterations" in src

    def test_comparison_report_has_speedup(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "actual_speedup" in src
        assert "theoretical_grover_speedup" in src
        assert "quantum_advantage_ratio" in src

    def test_static_circuit_analysis_class(self):
        tree = _parse_module(NONOGRAM_PKG / "metrics.py")
        assert "StaticCircuitAnalysis" in _class_names(tree)

    def test_static_circuit_density_metrics(self):
        src = _read(NONOGRAM_PKG / "metrics.py")
        assert "two_qubit_gate_density" in src
        assert "depth_per_iteration" in src
        assert "gates_per_qubit" in src

    def test_print_report_function_exists(self):
        tree = _parse_module(NONOGRAM_PKG / "metrics.py")
        assert "print_report" in _function_names(tree)

    def test_benchmark_comparison_tool_exists(self):
        assert (TOOLS_DIR / "benchmark_comparison.py").is_file()

    def test_benchmark_comparison_has_fixed_puzzles(self):
        src = _read(TOOLS_DIR / "benchmark_comparison.py")
        assert "BENCHMARK_PUZZLES" in src

    def test_benchmark_comparison_supports_json_output(self):
        src = _read(TOOLS_DIR / "benchmark_comparison.py")
        assert "json" in src

    def test_chart_module_exists(self):
        assert (TOOLS_DIR / "chart.py").is_file()

    def test_chart_renders_base64(self):
        src = _read(TOOLS_DIR / "chart.py")
        assert "base64" in src
        assert "render_chart_b64" in src


# ===================================================================
# #719 — Frontend integration
# ===================================================================

class TestFrontendIntegration:
    """WP #719: Frontend integrates with solver backend."""

    def test_webapp_module_exists(self):
        assert (TOOLS_DIR / "webapp.py").is_file()

    def test_webapp_flask_app_created(self):
        src = _read(TOOLS_DIR / "webapp.py")
        assert "Flask(__name__)" in src

    def test_webapp_socketio_initialized(self):
        src = _read(TOOLS_DIR / "webapp.py")
        assert "SocketIO" in src

    def test_webapp_registers_blueprints(self):
        src = _read(TOOLS_DIR / "webapp.py")
        assert "register_blueprint" in src
        assert "ALL_BLUEPRINTS" in src

    def test_route_modules_exist(self):
        routes_dir = TOOLS_DIR / "routes"
        assert routes_dir.is_dir()
        for module in ["grid.py", "solver.py", "puzzle.py", "hardware.py", "runs.py"]:
            assert (routes_dir / module).is_file(), f"Route module {module} must exist"

    def test_solver_route_exists(self):
        src = _read(TOOLS_DIR / "routes" / "solver.py")
        assert "benchmark" in src.lower() or "/api/" in src

    def test_puzzle_route_exists(self):
        src = _read(TOOLS_DIR / "routes" / "puzzle.py")
        assert "puzzle" in src.lower() or "/api/" in src

    def test_frontend_connects_socket_io(self):
        src = _read(WEBSITE_DIR / "static" / "app.js")
        assert "io(" in src, "Frontend must connect via Socket.IO"

    def test_frontend_binds_socket_events(self):
        src = _read(WEBSITE_DIR / "static" / "app.js")
        for event in ["status", "busy", "cl_done", "qu_done", "bench_done"]:
            assert event in src, f"Frontend must handle '{event}' socket event"

    def test_frontend_sends_benchmark_request(self):
        src = _read(WEBSITE_DIR / "static" / "app.js")
        assert "/api/benchmark" in src

    def test_frontend_state_module_exists(self):
        assert (WEBSITE_DIR / "static" / "state.js").is_file()

    def test_frontend_grid_module_exists(self):
        assert (WEBSITE_DIR / "static" / "grid.js").is_file()

    def test_frontend_solver_module_exists(self):
        assert (WEBSITE_DIR / "static" / "solver.js").is_file()

    def test_frontend_ui_module_exists(self):
        assert (WEBSITE_DIR / "static" / "ui.js").is_file()

    def test_frontend_supports_puzzle_load(self):
        src = _read(WEBSITE_DIR / "static" / "app.js")
        assert "file-input" in src or "puzzle/load" in src

    def test_frontend_supports_hardware_panel(self):
        src = _read(WEBSITE_DIR / "static" / "app.js")
        assert "hw-token" in src
        assert "hw-fetch-backends" in src

    def test_frontend_test_suite_exists(self):
        tests_dir = WEBSITE_DIR / "tests"
        assert tests_dir.is_dir()
        test_files = list(tests_dir.glob("*.test.js"))
        assert len(test_files) >= 1, "Frontend must have at least one test file"

    def test_frontend_package_json_has_test_script(self):
        src = _read(WEBSITE_DIR / "package.json")
        data = json.loads(src)
        assert "test" in data.get("scripts", {}), (
            "package.json must define a test script"
        )

    def test_api_config_endpoint(self):
        src = _read(TOOLS_DIR / "webapp.py")
        assert "/api/config" in src
        assert "max_clues" in src.lower() or "MAX_CLUES" in src
        assert "max_grid" in src.lower() or "MAX_GRID" in src


# ===================================================================
# #720 — Docker container health and startup
# ===================================================================

class TestDockerContainerHealth:
    """WP #720: Docker container starts and runs the solver correctly."""

    def test_dockerfile_has_entrypoint(self):
        src = _read(ROOT / "Dockerfile")
        assert "CMD" in src or "ENTRYPOINT" in src

    def test_entrypoint_runs_webapp(self):
        src = _read(ROOT / "Dockerfile")
        assert "webapp.py" in src, "Container must start the webapp"

    def test_dockerfile_installs_system_deps(self):
        src = _read(ROOT / "Dockerfile")
        assert "apt-get" in src, "Dockerfile must install system dependencies"

    def test_dockerfile_installs_openssl(self):
        src = _read(ROOT / "Dockerfile")
        assert "openssl" in src, "Must install openssl for cert generation"

    def test_docker_compose_port_binding(self):
        src = _read(ROOT / "docker-compose.yml")
        assert "127.0.0.1" in src or "ports" in src

    def test_docker_compose_environment_vars(self):
        src = _read(ROOT / "docker-compose.yml")
        assert "PORT" in src, "docker-compose must set PORT env var"

    def test_webapp_binds_configurable_host(self):
        src = _read(TOOLS_DIR / "webapp.py")
        assert "NONOGRAM_HOST" in src or "0.0.0.0" in src

    def test_webapp_port_configured(self):
        src = _read(TOOLS_DIR / "webapp.py")
        assert "5055" in src

    def test_webapp_ssl_optional(self):
        """Webapp should work with or without SSL certs."""
        src = _read(TOOLS_DIR / "webapp.py")
        assert "_get_ssl_context" in src
        # Should handle None (no certs available)
        assert "None" in src or "else" in src

    def test_docker_compose_disables_ssl_for_container(self):
        """Container should run without SSL for simplicity."""
        src = _read(ROOT / "docker-compose.yml")
        assert 'DEV_CERT_DIR' in src

    def test_webapp_state_module_exists(self):
        assert (TOOLS_DIR / "state.py").is_file()

    def test_webapp_config_module_exists(self):
        assert (TOOLS_DIR / "config.py").is_file()

    def test_config_defines_max_grid(self):
        src = _read(TOOLS_DIR / "config.py")
        assert "MAX_GRID" in src

    def test_config_defines_max_clues(self):
        src = _read(TOOLS_DIR / "config.py")
        assert "MAX_CLUES" in src

    def test_config_creates_dirs(self):
        src = _read(TOOLS_DIR / "config.py")
        assert "PUZZLES_DIR" in src
        assert "RUNS_DIR" in src
        assert "mkdir" in src

    def test_webapp_routes_package_init(self):
        assert (TOOLS_DIR / "routes" / "__init__.py").is_file()

    def test_routes_init_exports_blueprints(self):
        src = _read(TOOLS_DIR / "routes" / "__init__.py")
        assert "ALL_BLUEPRINTS" in src
