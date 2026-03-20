/**
 * @jest-environment jsdom
 */
const { setupDOM, loadState } = require('./helpers');

let App;
beforeEach(() => {
  delete window.App;
  setupDOM();
  App = loadState();
});

describe('state initialisation', () => {
  test('state has correct default dimensions', () => {
    expect(App.state.rows).toBe(3);
    expect(App.state.cols).toBe(3);
  });

  test('state has correct default mode', () => {
    expect(App.state.mode).toBe('draw');
  });

  test('grid is empty array', () => {
    expect(App.state.grid).toEqual([]);
  });

  test('clues start empty', () => {
    expect(App.state.rowClues).toEqual([]);
    expect(App.state.colClues).toEqual([]);
  });

  test('busy starts false', () => {
    expect(App.state.busy).toBe(false);
  });

  test('sidebar visible by default', () => {
    expect(App.state.sidebarVisible).toBe(true);
  });

  test('console hidden by default', () => {
    expect(App.state.consoleVisible).toBe(false);
  });

  test('default solution sizes are sm', () => {
    expect(App.state.clSize).toBe('sm');
    expect(App.state.quSize).toBe('sm');
  });

  test('hw not connected by default', () => {
    expect(App.state.hwConnected).toBe(false);
    expect(App.state.hwBackend).toBe('Simulator');
  });

  test('pan starts at origin', () => {
    expect(App.state.pan).toEqual({ tx: 0, ty: 0, scale: 1 });
  });
});

describe('DOM references', () => {
  test('$ helper finds elements by id', () => {
    expect(App.$('sidebar')).not.toBeNull();
    expect(App.$('draw-view')).not.toBeNull();
    expect(App.$('nonexistent')).toBeNull();
  });

  test('key DOM elements are cached', () => {
    expect(App.elSidebar).not.toBeNull();
    expect(App.elDrawView).not.toBeNull();
    expect(App.elCluesView).not.toBeNull();
    expect(App.elBtnBench).not.toBeNull();
    expect(App.elThresholdInput).not.toBeNull();
  });
});

describe('SVG icon constants', () => {
  test('all icons are non-empty strings', () => {
    const icons = [
      'DICE_SVG', 'X_SVG', 'UPLOAD_SVG', 'DOWNLOAD_SVG', 'CLOUD_SVG',
      'PLAY_SVG', 'PLUS_SVG', 'EXPORT_SVG', 'IMPORT_SVG', 'TRASH_SVG',
    ];
    for (const name of icons) {
      expect(typeof App[name]).toBe('string');
      expect(App[name].length).toBeGreaterThan(0);
      expect(App[name]).toContain('<svg');
    }
  });
});
