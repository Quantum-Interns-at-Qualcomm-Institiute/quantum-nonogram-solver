/**
 * @jest-environment jsdom
 *
 * Unit tests for grid.js — RLE, clue computation, grid sizing, puzzle helpers.
 */
const { setupDOM, loadState, loadGrid } = require('./helpers');

let App;
beforeEach(() => {
  delete window.App;
  setupDOM();
  App = loadState();
  App = loadGrid();
});

// ── rle (run-length encoding) ───────────────────────────────────────────────

describe('rle (via computeRowClues on a 1-row grid)', () => {
  function rle(bits) {
    // rle is not exported directly, but computeRowClues wraps it for rows
    App.state.rows = 1;
    App.state.cols = bits.length;
    App.state.grid = [bits];
    App.recomputeClues();
    return App.state.rowClues[0];
  }

  test('all false returns [0]', () => {
    expect(rle([false, false, false])).toEqual([0]);
  });

  test('all true returns [length]', () => {
    expect(rle([true, true, true])).toEqual([3]);
  });

  test('single true returns [1]', () => {
    expect(rle([true])).toEqual([1]);
  });

  test('alternating returns multiple blocks', () => {
    expect(rle([true, false, true])).toEqual([1, 1]);
  });

  test('leading false is ignored', () => {
    expect(rle([false, true, true])).toEqual([2]);
  });

  test('trailing false is ignored', () => {
    expect(rle([true, true, false])).toEqual([2]);
  });

  test('complex pattern', () => {
    expect(rle([true, true, false, true, false, true])).toEqual([2, 1, 1]);
  });

  test('empty array returns [0]', () => {
    expect(rle([])).toEqual([0]);
  });
});

// ── computeRowClues / computeColClues ───────────────────────────────────────

describe('clue computation', () => {
  test('2x2 all empty', () => {
    App.state.rows = 2; App.state.cols = 2;
    App.state.grid = [[false, false], [false, false]];
    App.recomputeClues();
    expect(App.state.rowClues).toEqual([[0], [0]]);
    expect(App.state.colClues).toEqual([[0], [0]]);
  });

  test('2x2 all filled', () => {
    App.state.rows = 2; App.state.cols = 2;
    App.state.grid = [[true, true], [true, true]];
    App.recomputeClues();
    expect(App.state.rowClues).toEqual([[2], [2]]);
    expect(App.state.colClues).toEqual([[2], [2]]);
  });

  test('2x2 diagonal', () => {
    App.state.rows = 2; App.state.cols = 2;
    App.state.grid = [[true, false], [false, true]];
    App.recomputeClues();
    expect(App.state.rowClues).toEqual([[1], [1]]);
    expect(App.state.colClues).toEqual([[1], [1]]);
  });

  test('3x3 L-shape', () => {
    App.state.rows = 3; App.state.cols = 3;
    App.state.grid = [
      [true, false, false],
      [true, false, false],
      [true, true, true],
    ];
    App.recomputeClues();
    expect(App.state.rowClues).toEqual([[1], [1], [3]]);
    expect(App.state.colClues).toEqual([[3], [1], [1]]);
  });

  test('3x3 checkerboard', () => {
    App.state.rows = 3; App.state.cols = 3;
    App.state.grid = [
      [true, false, true],
      [false, true, false],
      [true, false, true],
    ];
    App.recomputeClues();
    expect(App.state.rowClues).toEqual([[1, 1], [1], [1, 1]]);
    expect(App.state.colClues).toEqual([[1, 1], [1], [1, 1]]);
  });

  test('rectangular 2x3', () => {
    App.state.rows = 2; App.state.cols = 3;
    App.state.grid = [
      [true, true, false],
      [false, true, true],
    ];
    App.recomputeClues();
    expect(App.state.rowClues).toEqual([[2], [2]]);
    expect(App.state.colClues).toEqual([[1], [2], [1]]);
  });
});

// ── getMaxRowLen / getMaxColLen ──────────────────────────────────────────────

describe('max clue lengths', () => {
  test('empty clues return 1', () => {
    App.state.rowClues = [];
    App.state.colClues = [];
    expect(App.getMaxRowLen()).toBe(1);
    expect(App.getMaxColLen()).toBe(1);
  });

  test('single zero clue returns 1', () => {
    App.state.rowClues = [[0]];
    expect(App.getMaxRowLen()).toBe(1);
  });

  test('nonzero clues count correctly', () => {
    App.state.rowClues = [[1, 2], [3]];
    expect(App.getMaxRowLen()).toBe(2); // [1,2] has 2 nonzero values
  });

  test('mixed zero and nonzero', () => {
    App.state.rowClues = [[0], [1, 1, 1]];
    expect(App.getMaxRowLen()).toBe(3);
  });
});

// ── initGrid ────────────────────────────────────────────────────────────────

describe('initGrid', () => {
  test('creates grid with correct dimensions', () => {
    App.state.rows = 4; App.state.cols = 5;
    App.initGrid();
    expect(App.state.grid.length).toBe(4);
    expect(App.state.grid[0].length).toBe(5);
  });

  test('grid is all false', () => {
    App.state.rows = 3; App.state.cols = 3;
    App.initGrid();
    for (const row of App.state.grid) {
      for (const cell of row) {
        expect(cell).toBe(false);
      }
    }
  });

  test('recomputes clues to all zeros', () => {
    App.state.rows = 2; App.state.cols = 2;
    App.initGrid();
    expect(App.state.rowClues).toEqual([[0], [0]]);
    expect(App.state.colClues).toEqual([[0], [0]]);
  });
});

// ── getBestSolSize ──────────────────────────────────────────────────────────

describe('getBestSolSize', () => {
  test('small puzzles (<=6 cells) get lg', () => {
    expect(App.getBestSolSize(1, 1)).toBe('lg');
    expect(App.getBestSolSize(2, 3)).toBe('lg');
    expect(App.getBestSolSize(3, 2)).toBe('lg');
  });

  test('medium puzzles (<=16 cells) get md', () => {
    expect(App.getBestSolSize(3, 3)).toBe('md');
    expect(App.getBestSolSize(4, 4)).toBe('md');
  });

  test('large puzzles (>16 cells) get sm', () => {
    expect(App.getBestSolSize(5, 5)).toBe('sm');
    expect(App.getBestSolSize(6, 6)).toBe('sm');
  });
});

// ── Dynamic grid sizing ─────────────────────────────────────────────────────

describe('addRow / addCol / deleteRowsFrom / deleteColsFrom', () => {
  beforeEach(() => {
    // Mock fetch to prevent real network calls
    global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }));
    App.state.rows = 3; App.state.cols = 3;
    App.state.mode = 'draw';
    App.initGrid();
    // Stub rebuildActiveGrid since it needs full DOM
    App.buildGrid = jest.fn();
    App.buildClueGrid = jest.fn();
  });

  afterEach(() => {
    delete global.fetch;
  });

  test('addRow increases row count and grid length', () => {
    App.addRow();
    expect(App.state.rows).toBe(4);
    expect(App.state.grid.length).toBe(4);
    expect(App.state.grid[3].length).toBe(3);
    expect(App.state.grid[3].every(v => v === false)).toBe(true);
  });

  test('addRow respects MAX_GRID limit', () => {
    App.state.rows = 6;
    App.state.grid = Array.from({ length: 6 }, () => Array(3).fill(false));
    App.addRow();
    expect(App.state.rows).toBe(6); // unchanged
  });

  test('addCol increases col count', () => {
    App.addCol();
    expect(App.state.cols).toBe(4);
    expect(App.state.grid[0].length).toBe(4);
    expect(App.state.grid[0][3]).toBe(false);
  });

  test('addCol respects MAX_GRID limit', () => {
    App.state.cols = 6;
    App.addCol();
    expect(App.state.cols).toBe(6);
  });

  test('deleteRowsFrom trims grid', () => {
    App.deleteRowsFrom(2);
    expect(App.state.rows).toBe(2);
    expect(App.state.grid.length).toBe(2);
  });

  test('deleteRowsFrom ignores r < 2', () => {
    App.deleteRowsFrom(1);
    expect(App.state.rows).toBe(3); // unchanged
  });

  test('deleteColsFrom trims columns', () => {
    App.deleteColsFrom(2);
    expect(App.state.cols).toBe(2);
    expect(App.state.grid[0].length).toBe(2);
  });

  test('deleteColsFrom ignores c < 2', () => {
    App.deleteColsFrom(0);
    expect(App.state.cols).toBe(3);
  });

  test('addRow syncs to server', () => {
    App.addRow();
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/grid'),
      expect.objectContaining({ method: 'POST' })
    );
  });
});

// ── getCurrentPuzzle ────────────────────────────────────────────────────────

describe('getCurrentPuzzle', () => {
  test('returns row and col clues', () => {
    App.state.rows = 2; App.state.cols = 2;
    App.state.grid = [[true, false], [false, true]];
    App.state.mode = 'draw';
    const puzzle = App.getCurrentPuzzle();
    expect(puzzle.row_clues).toEqual([[1], [1]]);
    expect(puzzle.col_clues).toEqual([[1], [1]]);
  });
});

// ── makeRowClueContent / makeColClueContent ─────────────────────────────────

describe('clue content rendering', () => {
  test('makeRowClueContent creates correct slots', () => {
    const div = App.makeRowClueContent([1, 2], 3);
    expect(div.className).toBe('row-clue-slots');
    const slots = div.querySelectorAll('.clue-slot');
    expect(slots.length).toBe(3);
    // First slot should be empty (padding), then 1, 2
    expect(slots[0].classList.contains('empty')).toBe(true);
    expect(slots[1].textContent).toBe('1');
    expect(slots[2].textContent).toBe('2');
  });

  test('makeRowClueContent with zero clue', () => {
    const div = App.makeRowClueContent([0], 2);
    const slots = div.querySelectorAll('.clue-slot');
    expect(slots.length).toBe(2);
    // All should be empty since [0] has no nonzero values
    for (const s of slots) expect(s.classList.contains('empty')).toBe(true);
  });

  test('makeColClueContent creates correct slots', () => {
    const div = App.makeColClueContent([3], 2);
    expect(div.className).toBe('col-clue-slots');
    const slots = div.querySelectorAll('.clue-slot');
    expect(slots.length).toBe(2);
    expect(slots[0].classList.contains('empty')).toBe(true);
    expect(slots[1].textContent).toBe('3');
  });
});
