/**
 * Test helpers — loads nonogram frontend modules into jsdom.
 *
 * The nonogram frontend uses script-tag globals (window.App, API_BASE, etc.)
 * so we eval them in order after setting up the required DOM structure.
 */
const fs = require('fs');
const path = require('path');

const STATIC = path.resolve(__dirname, '..', 'static');
const UIKIT  = path.resolve(__dirname, '..', '..', 'lib', 'ui-kit', 'v1.1');

/** Minimal DOM structure matching nonogram/index.html. */
function setupDOM() {
  document.body.innerHTML = `
    <aside id="sidebar"></aside>
    <span id="toggle-label"></span>
    <div id="draw-view"></div>
    <div id="clues-view" style="display:none"></div>
    <span id="hw-status-indicator"></span>
    <svg id="qu-histogram"></svg>
    <div id="qu-tooltip" style="display:none"></div>
    <div id="qu-placeholder"></div>
    <div id="cl-placeholder"></div>
    <div id="qu-area"></div>
    <div id="qu-list"></div>
    <button id="btn-bench"></button>
    <input id="threshold-input" type="number" value="0.50">
    <input id="file-input" type="file" style="display:none">
    <input id="trials-input" type="number" value="1">
    <div id="sol-size-toggle">
      <button class="sol-size-btn active" data-size="sm">S</button>
      <button class="sol-size-btn" data-size="md">M</button>
      <button class="sol-size-btn" data-size="lg">L</button>
    </div>
    <div id="console-panel"></div>
    <div id="console-edge"></div>
    <span id="console-toggle-label"></span>
    <div id="status-terminal-inner"></div>
    <button id="btn-clear-terminal"></button>
    <div id="cl-canvas"></div>
    <div id="qu-canvas"></div>
    <div id="toggle-strip"></div>
    <div id="console-toggle-strip"></div>
    <button class="mode-btn active" data-mode="draw"></button>
    <button class="mode-btn" data-mode="clues"></button>
    <div id="hw-token"></div>
    <div id="hw-backend-select"></div>
    <div id="hw-backends-wrap" style="display:none"></div>
    <div id="hw-shots"></div>
    <button id="hw-fetch-backends"></button>
    <button id="hw-connect"></button>
    <button id="hw-disconnect"></button>
    <button id="btn-delete-runs"></button>
    <div id="navbar-backend-connect"></div>
    <div id="metrics-pane"></div>
    <div id="bench-bar"></div>
  `;
}

/** Load state.js — sets up window.App with state + DOM refs. */
function loadState() {
  // Define globals that index.html provides
  window.MAX_CLUES = 3;
  window.MAX_GRID = 6;
  window.API_BASE = 'https://localhost:5055';
  window.App = window.App || {};

  const code = fs.readFileSync(path.join(STATIC, 'state.js'), 'utf-8');
  eval(code);
  return window.App;
}

/** Load grid.js — requires state.js loaded first. */
function loadGrid() {
  const code = fs.readFileSync(path.join(STATIC, 'grid.js'), 'utf-8');
  eval(code);
  return window.App;
}

/** Load solver.js — requires state.js loaded first. */
function loadSolver() {
  const code = fs.readFileSync(path.join(STATIC, 'solver.js'), 'utf-8');
  eval(code);
  return window.App;
}

/** Load ui.js — requires state.js loaded first. */
function loadUI() {
  const code = fs.readFileSync(path.join(STATIC, 'ui.js'), 'utf-8');
  eval(code);
  return window.App;
}

/** Load ServiceConfig from ui-kit. */
function loadServiceConfig() {
  const code = fs.readFileSync(path.join(UIKIT, 'service-config.js'), 'utf-8');
  eval(code);
  return window.ServiceConfig;
}

/** Full load: DOM + all modules (except app.js which needs Socket.IO). */
function loadAll() {
  setupDOM();
  loadServiceConfig();
  loadState();
  loadGrid();
  // solver.js and ui.js require more DOM and would fail in some tests
  return window.App;
}

module.exports = {
  setupDOM, loadState, loadGrid, loadSolver, loadUI,
  loadServiceConfig, loadAll, STATIC, UIKIT,
};
