"""Tests for the webapp config endpoint and the state the grid routes keep.

Runs against the deployed app through conftest's `client`: a locally assembled one
would not carry the front-door guard, the CORS allowlist or the body-size cap.
"""

from __future__ import annotations

from tools import state as app_state
from tools.config import MAX_CLUES, MAX_GRID


class TestConfigEndpoint:
    def test_config_returns_200(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200

    def test_config_returns_json(self, client):
        resp = client.get("/api/config")
        data = resp.get_json()
        assert "max_clues" in data
        assert "max_grid" in data

    def test_config_values_match_constants(self, client):
        resp = client.get("/api/config")
        data = resp.get_json()
        assert data["max_clues"] == MAX_CLUES
        assert data["max_grid"] == MAX_GRID


class TestGridStateIntegrity:
    """Test that grid state is properly maintained across requests."""

    def test_grid_update_persists(self, client):
        client.post("/api/grid", json={"rows": 3, "cols": 3})
        assert app_state.state["rows"] == 3
        assert app_state.state["cols"] == 3

    def test_grid_with_custom_data(self, client):
        grid = [[True, False], [False, True]]
        resp = client.post("/api/grid", json={"rows": 2, "cols": 2, "grid": grid})
        assert resp.status_code == 200
        assert (app_state.state["rows"], app_state.state["cols"]) == (2, 2)

    def test_randomize_produces_valid_grid(self, client):
        resp = client.post("/api/randomize", json={"rows": 3, "cols": 4})
        data = resp.get_json()
        assert data["rows"] == 3
        assert data["cols"] == 4
        grid = data["grid"]
        assert len(grid) == 3
        assert all(len(row) == 4 for row in grid)
        # All values should be boolean
        assert all(isinstance(cell, bool) for row in grid for cell in row)

    def test_multiple_grid_updates(self, client):
        """Successive grid updates overwrite each other properly."""
        client.post("/api/grid", json={"rows": 2, "cols": 2})
        assert app_state.state["rows"] == 2
        client.post("/api/grid", json={"rows": 5, "cols": 5})
        assert app_state.state["rows"] == 5


class TestPuzzleSaveFormat:
    """Test that saved puzzles have correct JSON structure."""

    def test_save_returns_json_file(self, client):
        payload = {
            "row_clues": [[1], [1]],
            "col_clues": [[1], [1]],
            "name": "test",
        }
        resp = client.post("/api/puzzle/save", json=payload)
        assert resp.status_code == 200
        import json

        data = json.loads(resp.data)
        assert data["name"] == "test"
        assert data["rows"] == 2
        assert data["cols"] == 2
        assert data["row_clues"] == [[1], [1]]
        assert data["col_clues"] == [[1], [1]]
