"""Tests for constraint density metric computation."""

import pytest

from nonogram.data import constraint_density, valid_line_configs


class TestValidLineConfigs:
    def test_single_cell_filled(self):
        assert valid_line_configs(1, (1,)) == 1

    def test_single_cell_empty(self):
        assert valid_line_configs(1, (0,)) == 1

    def test_two_cells_one_block(self):
        assert valid_line_configs(2, (1,)) == 2

    def test_three_cells_one_block(self):
        assert valid_line_configs(3, (1,)) == 3

    def test_three_cells_two_blocks(self):
        assert valid_line_configs(3, (1, 1)) == 1

    def test_five_cells_two_blocks(self):
        assert valid_line_configs(5, (1, 1)) == 6

    def test_ten_cells_one_block(self):
        assert valid_line_configs(10, (1,)) == 10

    def test_ten_cells_full(self):
        assert valid_line_configs(10, (10,)) == 1

    def test_impossible_clue_raises(self):
        from nonogram.errors import ValidationError
        with pytest.raises(ValidationError):
            valid_line_configs(3, (2, 2))


class TestConstraintDensity:
    def test_basic_structure(self):
        cd = constraint_density([(1,), (1,)], [(1,), (1,)])
        assert "row_configs" in cd
        assert "col_configs" in cd
        assert "total_configs" in cd
        assert "mean_configs" in cd
        assert "min_configs" in cd
        assert "max_configs" in cd
        assert "search_space" in cd
        assert "density_ratio" in cd

    def test_2x2_symmetric(self):
        cd = constraint_density([(1,), (1,)], [(1,), (1,)])
        assert cd["row_configs"] == [2, 2]
        assert cd["col_configs"] == [2, 2]
        assert cd["search_space"] == 16

    def test_total_configs(self):
        cd = constraint_density([(1,), (1,)], [(1,), (1,)])
        assert cd["total_configs"] == 8

    def test_mean_configs(self):
        cd = constraint_density([(1,), (1,)], [(1,), (1,)])
        assert cd["mean_configs"] == pytest.approx(2.0)

    def test_larger_puzzle(self):
        cd = constraint_density(
            [(1, 1), (2,), (1,)],
            [(1,), (2,), (1,)]
        )
        assert cd["search_space"] == 2 ** 9
        assert cd["total_configs"] > 0
        assert cd["min_configs"] >= 1
        assert cd["max_configs"] >= cd["min_configs"]

    def test_fully_constrained_puzzle(self):
        cd = constraint_density([(2,), (2,)], [(2,), (2,)])
        # Each line has exactly 1 valid config (all filled)
        assert cd["row_configs"] == [1, 1]
        assert cd["col_configs"] == [1, 1]
        assert cd["min_configs"] == 1
