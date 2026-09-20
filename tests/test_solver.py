"""The three solvers keep the shape their callers expect: a name and a solve()."""

from nonogram.solver import ClassicalSolver, QuantumSimulatorSolver


class TestClassicalSolverInterface:
    def test_name(self):
        solver = ClassicalSolver()
        assert solver.name == "Classical"

    def test_solve_returns_solutions_key(self):
        solver = ClassicalSolver()
        puzzle = ([(1,)], [(1,)])
        result = solver.solve(puzzle)
        assert "solutions" in result
        assert result["solutions"] == ["1"]

    def test_solve_2x2(self):
        solver = ClassicalSolver()
        puzzle = ([(2,), (2,)], [(2,), (2,)])
        result = solver.solve(puzzle)
        assert result["solutions"] == ["1111"]

    def test_solve_empty_grid(self):
        solver = ClassicalSolver()
        puzzle = ([(0,), (0,)], [(0,), (0,)])
        result = solver.solve(puzzle)
        assert result["solutions"] == ["0000"]


class TestQuantumSimulatorSolverInterface:
    def test_name(self):
        solver = QuantumSimulatorSolver()
        assert solver.name == "Quantum (Simulator)"

    def test_solve_returns_counts_key(self):
        solver = QuantumSimulatorSolver()
        puzzle = ([(1,)], [(1,)])
        result = solver.solve(puzzle)
        assert set(result) == {"counts"}

    def test_solve_finds_correct_solution(self):
        solver = QuantumSimulatorSolver()
        puzzle = ([(2,), (2,)], [(2,), (2,)])
        result = solver.solve(puzzle)
        counts = result["counts"]
        top = max(counts, key=counts.__getitem__)
        assert top[::-1] == "1111"
