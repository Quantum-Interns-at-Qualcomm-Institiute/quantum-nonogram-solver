"""Route blueprints for the nonogram web app."""

from tools.routes.grid import bp as grid_bp
from tools.routes.hardware import bp as hardware_bp
from tools.routes.puzzle import bp as puzzle_bp
from tools.routes.runs import bp as runs_bp
from tools.routes.solver import bp as solver_bp

ALL_BLUEPRINTS = [grid_bp, solver_bp, puzzle_bp, hardware_bp, runs_bp]
