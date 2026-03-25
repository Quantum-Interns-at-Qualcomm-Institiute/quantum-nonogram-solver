"""Tests for classical solver execution count instrumentation."""


from nonogram.classical import ExecutionCounts, classical_solve

SMALL_PUZZLE = ([(1,), (1,)], [(1,), (1,)])  # 2x2


class TestExecutionCounts:
    def test_collect_counts_returns_tuple(self):
        result = classical_solve(SMALL_PUZZLE, collect_counts=True)
        assert isinstance(result, tuple)
        assert len(result) == 2
        solutions, counts = result
        assert isinstance(solutions, list)
        assert isinstance(counts, ExecutionCounts)

    def test_without_collect_counts_returns_list(self):
        result = classical_solve(SMALL_PUZZLE, collect_counts=False)
        assert isinstance(result, list)

    def test_candidates_evaluated(self):
        _, counts = classical_solve(SMALL_PUZZLE, collect_counts=True)
        assert counts.candidates_evaluated == 16  # 2^4

    def test_solutions_found(self):
        _, counts = classical_solve(SMALL_PUZZLE, collect_counts=True)
        assert counts.solutions_found == 2

    def test_clause_evaluations_positive(self):
        _, counts = classical_solve(SMALL_PUZZLE, collect_counts=True)
        assert counts.clause_evaluations > 0

    def test_subclause_evaluations_positive(self):
        _, counts = classical_solve(SMALL_PUZZLE, collect_counts=True)
        assert counts.subclause_evaluations > 0

    def test_literal_evaluations_positive(self):
        _, counts = classical_solve(SMALL_PUZZLE, collect_counts=True)
        assert counts.literal_evaluations > 0

    def test_constraint_checks_equals_clause_evaluations(self):
        _, counts = classical_solve(SMALL_PUZZLE, collect_counts=True)
        assert counts.constraint_checks == counts.clause_evaluations

    def test_early_terminations_occur(self):
        _, counts = classical_solve(SMALL_PUZZLE, collect_counts=True)
        # Most candidates should fail early
        assert counts.early_terminations > 0

    def test_literals_per_candidate(self):
        _, counts = classical_solve(SMALL_PUZZLE, collect_counts=True)
        assert counts.literals_per_candidate > 0
        assert counts.literals_per_candidate == (
            counts.literal_evaluations / counts.candidates_evaluated
        )

    def test_clauses_per_candidate(self):
        _, counts = classical_solve(SMALL_PUZZLE, collect_counts=True)
        assert counts.clauses_per_candidate > 0

    def test_1x1_filled(self):
        puzzle = ([(1,)], [(1,)])
        solutions, counts = classical_solve(puzzle, collect_counts=True)
        assert solutions == ["1"]
        assert counts.candidates_evaluated == 2
        assert counts.solutions_found == 1

    def test_1x1_empty(self):
        puzzle = ([(0,)], [(0,)])
        solutions, counts = classical_solve(puzzle, collect_counts=True)
        assert solutions == ["0"]
        assert counts.solutions_found == 1

    def test_manual_check_with_counts(self):
        solutions, counts = classical_solve(
            SMALL_PUZZLE, manual_check="1001", collect_counts=True
        )
        assert solutions == ["1001"]
        assert counts.candidates_evaluated == 1
        assert counts.solutions_found == 1
