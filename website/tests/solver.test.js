/**
 * @jest-environment jsdom
 *
 * Unit tests for solver.js — threshold computation, probability formatting,
 * classical/quantum result rendering, and benchmark integration.
 */
const { setupDOM, loadState, loadGrid, loadSolver } = require('./helpers');

let App;
beforeEach(() => {
  delete window.App;
  setupDOM();
  // Add solver-specific DOM elements
  document.body.innerHTML += `
    <div id="qu-sol-placeholder">Run to see.</div>
    <div id="trial-nav"></div>
    <div id="cl-metrics"></div>
    <div id="qu-metrics"></div>
  `;
  App = loadState();
  loadGrid();
  App = loadSolver();
});

// ── computeThreshold ────────────────────────────────────────────────────────

describe('computeThreshold (exported indirectly via renderQuantum)', () => {
  // computeThreshold is not directly exported, but we can test its behaviour
  // by checking how renderQuantum sets state.histData.threshold

  function getThreshold(rows, cols) {
    // Build fake counts with enough entries
    const counts = {};
    const n = rows * cols;
    for (let i = 0; i < Math.min(10, Math.pow(2, n)); i++) {
      counts[i.toString(2).padStart(n, '0')] = 1;
    }
    App.renderQuantum(counts, rows, cols);
    return App.state.histData.threshold;
  }

  test('1x1 puzzle threshold', () => {
    const t = getThreshold(1, 1);
    // 1 qubit: baseline = 0.5, 3x = 1.5, clamped to max(1.5, 0.005) = 1.5
    expect(t).toBeGreaterThan(0);
  });

  test('2x2 puzzle threshold', () => {
    const t = getThreshold(2, 2);
    // 4 qubits: baseline = 1/16, 3x = 0.1875
    expect(t).toBeCloseTo(0.1875, 3);
  });

  test('3x3 puzzle threshold', () => {
    const t = getThreshold(3, 3);
    // 9 qubits: baseline = 1/512, 3x = ~0.00586
    expect(t).toBeCloseTo(3 / 512, 4);
  });

  test('threshold respects user override', () => {
    App.state.userThreshold = 0.25;
    const counts = { '0000': 5, '1111': 5 };
    App.renderQuantum(counts, 2, 2);
    expect(App.state.histData.threshold).toBe(0.25);
    App.state.userThreshold = null; // cleanup
  });
});

// ── fp (probability formatting) ─────────────────────────────────────────────

describe('fp (probability formatting)', () => {
  // fp is not exported but we can test through histogram rendering indirectly.
  // For direct testing, we check the threshold display in the input.
  // Let's test the output format expectations:

  test('threshold input shows correct percentage', () => {
    const counts = {};
    for (let i = 0; i < 16; i++) counts[i.toString(2).padStart(4, '0')] = 1;
    App.renderQuantum(counts, 2, 2);
    // Threshold for 2x2 = 0.1875 = 18.75%
    const val = parseFloat(App.elThresholdInput.value);
    expect(val).toBeCloseTo(18.75, 0);
  });
});

// ── renderClassical ─────────────────────────────────────────────────────────

describe('renderClassical', () => {
  test('shows placeholder when no solutions', () => {
    App.renderClassical({ solutions: [], rows: 2, cols: 2 });
    const ph = document.getElementById('cl-placeholder');
    expect(ph.style.display).not.toBe('none');
    expect(ph.textContent).toContain('No solutions');
  });

  test('shows placeholder when solutions is null', () => {
    App.renderClassical({ solutions: null, rows: 2, cols: 2 });
    const ph = document.getElementById('cl-placeholder');
    expect(ph.style.display).not.toBe('none');
  });

  test('renders solution grids', () => {
    App.renderClassical({ solutions: ['1111'], rows: 2, cols: 2 });
    const ph = document.getElementById('cl-placeholder');
    expect(ph.style.display).toBe('none');

    const grids = document.querySelectorAll('#cl-canvas .sol-grid-wrap');
    expect(grids.length).toBe(1);
    const cells = grids[0].querySelectorAll('td');
    expect(cells.length).toBe(4); // 2x2
    // All filled
    for (const td of cells) expect(td.className).toBe('f');
  });

  test('renders multiple solutions with labels', () => {
    App.renderClassical({ solutions: ['1001', '0110'], rows: 2, cols: 2 });
    const labels = document.querySelectorAll('#cl-canvas .sol-grid-label');
    expect(labels.length).toBe(2);
    expect(labels[0].textContent).toBe('Solution 1');
    expect(labels[1].textContent).toBe('Solution 2');
  });

  test('single solution has no number', () => {
    App.renderClassical({ solutions: ['1111'], rows: 2, cols: 2 });
    const label = document.querySelector('#cl-canvas .sol-grid-label');
    expect(label.textContent).toBe('Solution');
  });

  test('renders correct filled/empty cells', () => {
    App.renderClassical({ solutions: ['1010'], rows: 2, cols: 2 });
    const cells = document.querySelectorAll('#cl-canvas .sol-grid-wrap td');
    expect(cells[0].className).toBe('f'); // 1
    expect(cells[1].className).toBe('e'); // 0
    expect(cells[2].className).toBe('f'); // 1
    expect(cells[3].className).toBe('e'); // 0
  });

  test('uses current solution size class', () => {
    App.state.clSize = 'lg';
    App.renderClassical({ solutions: ['1111'], rows: 2, cols: 2 });
    const tbl = document.querySelector('#cl-canvas .sol-table');
    expect(tbl.className).toBe('sol-table sz-lg');
  });
});

// ── renderQuantum ───────────────────────────────────────────────────────────

describe('renderQuantum', () => {
  test('empty counts shows placeholder', () => {
    App.renderQuantum({}, 2, 2);
    // Should call drawEmptyHistogram (placeholder visible)
    expect(App.state.histData).toBeNull();
  });

  test('null counts shows placeholder', () => {
    App.renderQuantum(null, 2, 2);
    expect(App.state.histData).toBeNull();
  });

  test('valid counts sets histData', () => {
    const counts = { '0000': 10, '1111': 90 };
    App.renderQuantum(counts, 2, 2);
    expect(App.state.histData).not.toBeNull();
    expect(App.state.histData.entries.length).toBe(2);
    expect(App.state.histData.rows).toBe(2);
    expect(App.state.histData.cols).toBe(2);
  });

  test('entries are sorted by probability descending', () => {
    const counts = { '00': 10, '01': 50, '10': 30, '11': 10 };
    App.renderQuantum(counts, 1, 2);
    const entries = App.state.histData.entries;
    expect(entries[0][0]).toBe('01'); // highest
    expect(entries[1][0]).toBe('10');
  });

  test('entries capped at MAX_DISPLAY (30)', () => {
    const counts = {};
    for (let i = 0; i < 50; i++) counts[i.toString(2).padStart(6, '0')] = 1;
    App.renderQuantum(counts, 2, 3);
    expect(App.state.histData.entries.length).toBe(30);
  });
});

// ── clearSolverResults ──────────────────────────────────────────────────────

describe('clearSolverResults', () => {
  test('resets histData and trial state', () => {
    App.state.histData = { entries: [], threshold: 0.1 };
    App.state.trialCounts = [{}];
    App.state.trialIdx = 2;
    App.clearSolverResults();
    expect(App.state.histData).toBeNull();
    expect(App.state.trialCounts).toBeNull();
    expect(App.state.trialIdx).toBe(0);
  });
});

// ── renderBenchmark ─────────────────────────────────────────────────────────

describe('renderBenchmark', () => {
  test('processes benchmark payload', () => {
    App.renderBenchmark({
      report: {},
      solutions: ['1111'],
      qu_counts: { '0000': 5, '1111': 95 },
      qu_counts_per_trial: null,
      rows: 2,
      cols: 2,
      cl_times: [0.001],
      qu_times: [0.1],
    });
    // After rendering, classical solution should be visible
    const grids = document.querySelectorAll('#cl-canvas .sol-grid-wrap');
    expect(grids.length).toBe(1);
    // Quantum data should be set
    expect(App.state.histData).not.toBeNull();
  });

  test('handles multi-trial benchmark', () => {
    const perTrial = [
      { '00': 5, '11': 95 },
      { '00': 3, '11': 97 },
    ];
    App.renderBenchmark({
      report: {},
      solutions: ['1111'],
      qu_counts: { '00': 4, '11': 96 },
      qu_counts_per_trial: perTrial,
      rows: 2,
      cols: 2,
      cl_times: [0.001, 0.001],
      qu_times: [0.1, 0.1],
    });
    expect(App.state.trialCounts).toEqual(perTrial);
    expect(App.state.trialIdx).toBe(1); // last trial
  });
});
