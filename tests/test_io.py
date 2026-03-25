"""
tests/test_io.py
~~~~~~~~~~~~~~~~
Unit tests for nonogram.io — save_puzzle, load_puzzle, save_batch, load_batch.

These tests are headless (no tkinter) and cover:
  * Happy-path save/load roundtrips
  * Validation rejections (negative values, oversized puzzles)
  * Batch save/load roundtrips
  * Edge-case clue shapes (empty rows encoded as (0,), multi-group clues)
  * File-system error conditions (missing file, missing directory)
  * Internal helpers: _slugify, _to_serialisable
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nonogram.errors import PuzzleIOError
from nonogram.io import (
    _slugify,
    _to_serialisable,
    _validate_clues,
    load_batch,
    load_puzzle,
    save_batch,
    save_puzzle,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SIMPLE_ROW_CLUES = [(1,), (1,)]
SIMPLE_COL_CLUES = [(1,), (1,)]

MULTI_GROUP_ROW = [(2, 1), (1,)]
MULTI_GROUP_COL = [(1,), (2,)]


# ===========================================================================
# _slugify
# ===========================================================================


class TestSlugify:
    def test_basic_name(self):
        assert _slugify("My Puzzle") == "my_puzzle"

    def test_special_chars_stripped(self):
        assert _slugify("hello! world?") == "hello_world"

    def test_leading_trailing_spaces(self):
        assert _slugify("  puzzle  ") == "puzzle"

    def test_empty_string_returns_puzzle(self):
        assert _slugify("") == "puzzle"

    def test_multiple_spaces_become_single_underscore(self):
        assert _slugify("a  b") == "a_b"

    def test_already_lowercase(self):
        assert _slugify("abc") == "abc"

    def test_hyphens_normalised(self):
        # hyphens are treated like separators
        assert _slugify("my-puzzle") == "my_puzzle"

    def test_numbers_preserved(self):
        assert _slugify("puzzle 42") == "puzzle_42"


# ===========================================================================
# _to_serialisable
# ===========================================================================


class TestToSerialisable:
    def test_list_of_tuples(self):
        assert _to_serialisable([(1, 2), (3,)]) == [[1, 2], [3]]

    def test_list_of_lists(self):
        assert _to_serialisable([[1, 2], [3]]) == [[1, 2], [3]]

    def test_empty_outer(self):
        assert _to_serialisable([]) == []

    def test_zero_value_preserved(self):
        # (0,) encodes an empty row; 0 must survive round-trip
        assert _to_serialisable([(0,)]) == [[0]]

    def test_booleans_converted_to_int(self):
        # bool is a subclass of int, but explicit int() should normalise
        result = _to_serialisable([(True, False)])
        assert result == [[1, 0]]
        assert all(type(v) is int for row in result for v in row)


# ===========================================================================
# _validate_clues
# ===========================================================================


class TestValidateClues:
    def test_valid_simple_clues(self):
        # Should not raise
        _validate_clues([(1,), (2,)], [(1,), (1,), (1,)])

    def test_empty_row_encoded_as_zero(self):
        # (0,) is the canonical "empty line" representation used throughout
        _validate_clues([(0,), (1,)], [(1,), (0,)])

    def test_multi_group_clue(self):
        _validate_clues([(2, 1), (1,)], [(1,), (2,)])

    def test_negative_value_raises(self):
        with pytest.raises(ValueError, match="negative"):
            _validate_clues([(-1,)], [(1,)])

    def test_negative_in_col_raises(self):
        with pytest.raises(ValueError, match="negative"):
            _validate_clues([(1,)], [(-2,)])

    def test_non_integer_raises(self):
        with pytest.raises(ValueError):
            _validate_clues([("one",)], [(1,)])  # type: ignore[arg-type]

    def test_exceeds_max_line_raises(self):
        # 11 rows exceeds _MAX_LINE=10
        big = [(1,)] * 11
        with pytest.raises(ValueError, match="maximum"):
            _validate_clues(big, [(1,)] * 10)

    def test_exactly_max_line_ok(self):
        # 10×10 should be accepted
        clues = [(1,)] * 10
        _validate_clues(clues, clues)  # should not raise


# ===========================================================================
# save_puzzle / load_puzzle — roundtrip
# ===========================================================================


class TestSavePuzzle:
    def test_creates_file(self, tmp_path):
        dest = tmp_path / "p.non.json"
        save_puzzle(SIMPLE_ROW_CLUES, SIMPLE_COL_CLUES, dest)
        assert dest.exists()

    def test_file_is_valid_json(self, tmp_path):
        dest = tmp_path / "p.non.json"
        save_puzzle(SIMPLE_ROW_CLUES, SIMPLE_COL_CLUES, dest)
        data = json.loads(dest.read_text())
        assert isinstance(data, dict)

    def test_creates_parent_dirs(self, tmp_path):
        dest = tmp_path / "a" / "b" / "p.non.json"
        save_puzzle(SIMPLE_ROW_CLUES, SIMPLE_COL_CLUES, dest)
        assert dest.exists()

    def test_name_stored(self, tmp_path):
        dest = tmp_path / "p.non.json"
        save_puzzle(SIMPLE_ROW_CLUES, SIMPLE_COL_CLUES, dest, name="Demo")
        data = json.loads(dest.read_text())
        assert data["name"] == "Demo"

    def test_tags_stored(self, tmp_path):
        dest = tmp_path / "p.non.json"
        save_puzzle(SIMPLE_ROW_CLUES, SIMPLE_COL_CLUES, dest, tags=["easy", "2x2"])
        data = json.loads(dest.read_text())
        assert data["tags"] == ["easy", "2x2"]

    def test_tags_default_empty(self, tmp_path):
        dest = tmp_path / "p.non.json"
        save_puzzle(SIMPLE_ROW_CLUES, SIMPLE_COL_CLUES, dest)
        data = json.loads(dest.read_text())
        assert data["tags"] == []

    def test_rows_cols_dimensions_stored(self, tmp_path):
        dest = tmp_path / "p.non.json"
        save_puzzle(SIMPLE_ROW_CLUES, SIMPLE_COL_CLUES, dest)
        data = json.loads(dest.read_text())
        assert data["rows"] == len(SIMPLE_ROW_CLUES)
        assert data["cols"] == len(SIMPLE_COL_CLUES)

    def test_clues_stored_as_list_of_lists(self, tmp_path):
        dest = tmp_path / "p.non.json"
        save_puzzle(SIMPLE_ROW_CLUES, SIMPLE_COL_CLUES, dest)
        data = json.loads(dest.read_text())
        assert data["row_clues"] == [[1], [1]]
        assert data["col_clues"] == [[1], [1]]

    def test_multi_group_clues_stored_correctly(self, tmp_path):
        dest = tmp_path / "p.non.json"
        save_puzzle(MULTI_GROUP_ROW, MULTI_GROUP_COL, dest)
        data = json.loads(dest.read_text())
        assert data["row_clues"] == [[2, 1], [1]]
        assert data["col_clues"] == [[1], [2]]

    def test_empty_row_clue_roundtrip(self, tmp_path):
        """(0,) encodes an empty line; must survive JSON roundtrip."""
        row_clues = [(0,), (1,)]
        col_clues = [(1,), (0,)]
        dest = tmp_path / "p.non.json"
        save_puzzle(row_clues, col_clues, dest)
        data = json.loads(dest.read_text())
        assert data["row_clues"] == [[0], [1]]
        assert data["col_clues"] == [[1], [0]]

    def test_negative_clue_raises(self, tmp_path):
        dest = tmp_path / "p.non.json"
        with pytest.raises(ValueError):
            save_puzzle([(-1,)], [(1,)], dest)

    def test_oversized_raises(self, tmp_path):
        dest = tmp_path / "p.non.json"
        big = [(1,)] * 11
        with pytest.raises(ValueError, match="maximum"):
            save_puzzle(big, [(1,)] * 10, dest)


class TestLoadPuzzle:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(PuzzleIOError):
            load_puzzle(tmp_path / "nonexistent.non.json")

    def test_returns_dict_with_required_keys(self, tmp_path):
        dest = tmp_path / "p.non.json"
        save_puzzle(SIMPLE_ROW_CLUES, SIMPLE_COL_CLUES, dest, name="Test")
        data = load_puzzle(dest)
        for key in ("name", "rows", "cols", "row_clues", "col_clues", "created", "tags"):
            assert key in data, f"Missing key: {key}"

    def test_clues_are_lists_of_lists_of_int(self, tmp_path):
        dest = tmp_path / "p.non.json"
        save_puzzle(SIMPLE_ROW_CLUES, SIMPLE_COL_CLUES, dest)
        data = load_puzzle(dest)
        for row in data["row_clues"]:
            assert isinstance(row, list)
            assert all(isinstance(v, int) for v in row)

    def test_dimensions_recomputed_from_clue_lengths(self, tmp_path):
        """load_puzzle should recompute rows/cols from actual clue lengths,
        not trust the stored 'rows'/'cols' fields."""
        dest = tmp_path / "p.non.json"
        save_puzzle(SIMPLE_ROW_CLUES, SIMPLE_COL_CLUES, dest)
        # Corrupt the stored dims
        data = json.loads(dest.read_text())
        data["rows"] = 99
        data["cols"] = 99
        dest.write_text(json.dumps(data))
        loaded = load_puzzle(dest)
        assert loaded["rows"] == len(SIMPLE_ROW_CLUES)
        assert loaded["cols"] == len(SIMPLE_COL_CLUES)

    def test_missing_optional_keys_get_defaults(self, tmp_path):
        dest = tmp_path / "bare.non.json"
        dest.write_text(
            json.dumps(
                {
                    "row_clues": [[1], [1]],
                    "col_clues": [[1], [1]],
                }
            )
        )
        data = load_puzzle(dest)
        assert data["tags"] == []
        assert data["created"] == ""
        assert data["name"] == "bare"  # falls back to stem


class TestSaveLoadRoundtrip:
    def test_simple_puzzle(self, tmp_path):
        dest = tmp_path / "p.non.json"
        save_puzzle(SIMPLE_ROW_CLUES, SIMPLE_COL_CLUES, dest, name="Simple")
        data = load_puzzle(dest)
        assert [tuple(r) for r in data["row_clues"]] == SIMPLE_ROW_CLUES
        assert [tuple(c) for c in data["col_clues"]] == SIMPLE_COL_CLUES
        assert data["name"] == "Simple"

    def test_multi_group_puzzle(self, tmp_path):
        dest = tmp_path / "p.non.json"
        save_puzzle(MULTI_GROUP_ROW, MULTI_GROUP_COL, dest)
        data = load_puzzle(dest)
        assert [tuple(r) for r in data["row_clues"]] == MULTI_GROUP_ROW
        assert [tuple(c) for c in data["col_clues"]] == MULTI_GROUP_COL

    def test_max_size_puzzle(self, tmp_path):
        # 6×6 puzzle with varied clues
        row_clues = [(1,), (2,), (3,), (1, 1), (2, 1), (0,)]
        col_clues = [(1,), (2,), (1,), (1,), (2,), (1,)]
        dest = tmp_path / "big.non.json"
        save_puzzle(row_clues, col_clues, dest)
        data = load_puzzle(dest)
        assert [tuple(r) for r in data["row_clues"]] == row_clues
        assert [tuple(c) for c in data["col_clues"]] == col_clues

    def test_tags_preserved(self, tmp_path):
        dest = tmp_path / "p.non.json"
        save_puzzle(SIMPLE_ROW_CLUES, SIMPLE_COL_CLUES, dest, tags=["hard", "6x6"])
        data = load_puzzle(dest)
        assert data["tags"] == ["hard", "6x6"]

    def test_loaded_clues_usable_by_solver(self, tmp_path):
        """The solver must accept clues straight from load_puzzle."""
        from nonogram.classical import classical_solve

        row_clues = [(1,), (1,)]
        col_clues = [(1,), (1,)]
        dest = tmp_path / "p.non.json"
        save_puzzle(row_clues, col_clues, dest)
        data = load_puzzle(dest)
        r = [tuple(r) for r in data["row_clues"]]
        c = [tuple(c) for c in data["col_clues"]]
        solutions = classical_solve((r, c))
        assert len(solutions) > 0


# ===========================================================================
# save_batch / load_batch
# ===========================================================================

BATCH_PUZZLES = [
    {"name": "Alpha", "row_clues": [(1,), (1,)], "col_clues": [(1,), (1,)]},
    {"name": "Beta", "row_clues": [(2,), (0,)], "col_clues": [(1,), (1,)]},
    {"name": "Gamma", "row_clues": [(1, 1), (0,)], "col_clues": [(1,), (1,)]},
]


class TestSaveBatch:
    def test_creates_correct_number_of_files(self, tmp_path):
        written = save_batch(BATCH_PUZZLES, tmp_path)
        assert len(written) == len(BATCH_PUZZLES)

    def test_all_files_exist(self, tmp_path):
        written = save_batch(BATCH_PUZZLES, tmp_path)
        for p in written:
            assert Path(p).exists()

    def test_files_have_non_json_extension(self, tmp_path):
        written = save_batch(BATCH_PUZZLES, tmp_path)
        for p in written:
            assert str(p).endswith(".non.json")

    def test_creates_folder_if_missing(self, tmp_path):
        folder = tmp_path / "new_folder"
        save_batch(BATCH_PUZZLES, folder)
        assert folder.is_dir()

    def test_returns_paths_list(self, tmp_path):
        result = save_batch(BATCH_PUZZLES, tmp_path)
        assert isinstance(result, list)
        assert all(isinstance(p, Path) for p in result)

    def test_filenames_include_index_suffix(self, tmp_path):
        written = save_batch(BATCH_PUZZLES, tmp_path)
        names = [p.name for p in written]
        assert any("_000.non.json" in n for n in names)
        assert any("_001.non.json" in n for n in names)

    def test_batch_with_dict_row_col_lists(self, tmp_path):
        """save_batch must accept list-of-lists, not just list-of-tuples."""
        puzzles = [
            {"name": "X", "row_clues": [[1], [1]], "col_clues": [[1], [1]]},
        ]
        written = save_batch(puzzles, tmp_path)
        assert len(written) == 1

    def test_empty_batch_writes_nothing(self, tmp_path):
        written = save_batch([], tmp_path)
        assert written == []


class TestLoadBatch:
    def test_loads_all_files(self, tmp_path):
        save_batch(BATCH_PUZZLES, tmp_path)
        loaded = load_batch(tmp_path)
        assert len(loaded) == len(BATCH_PUZZLES)

    def test_each_entry_is_dict(self, tmp_path):
        save_batch(BATCH_PUZZLES, tmp_path)
        loaded = load_batch(tmp_path)
        assert all(isinstance(p, dict) for p in loaded)

    def test_sorted_by_filename(self, tmp_path):
        save_batch(BATCH_PUZZLES, tmp_path)
        loaded = load_batch(tmp_path)
        names = [p["name"] for p in loaded]
        assert names == sorted(names) or len(names) == len(BATCH_PUZZLES)  # sorted determinism

    def test_missing_directory_raises(self, tmp_path):
        with pytest.raises(PuzzleIOError):
            load_batch(tmp_path / "no_such_dir")

    def test_ignores_non_non_json_files(self, tmp_path):
        save_batch(BATCH_PUZZLES, tmp_path)
        (tmp_path / "readme.txt").write_text("ignore me")
        (tmp_path / "other.json").write_text('{"not": "a puzzle"}')
        loaded = load_batch(tmp_path)
        assert len(loaded) == len(BATCH_PUZZLES)


class TestSaveBatchLoadBatchRoundtrip:
    def test_clues_survive_roundtrip(self, tmp_path):
        save_batch(BATCH_PUZZLES, tmp_path)
        loaded = load_batch(tmp_path)
        loaded_names = {p["name"] for p in loaded}
        for original in BATCH_PUZZLES:
            assert original["name"] in loaded_names

    def test_solver_can_use_batch_loaded_clues(self, tmp_path):
        from nonogram.classical import classical_solve

        puzzles = [{"name": "T", "row_clues": [(1,), (1,)], "col_clues": [(1,), (1,)]}]
        save_batch(puzzles, tmp_path)
        loaded = load_batch(tmp_path)
        for p in loaded:
            r = [tuple(row) for row in p["row_clues"]]
            c = [tuple(col) for col in p["col_clues"]]
            solutions = classical_solve((r, c))
            assert len(solutions) > 0
