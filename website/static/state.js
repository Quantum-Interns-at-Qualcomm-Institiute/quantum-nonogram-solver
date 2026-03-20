"use strict";
/* =============================================================
   State & DOM references — shared across all modules.
   ============================================================= */

window.App = window.App || {};

// ── State ──────────────────────────────────────────────────────
const state = {
  rows: 3, cols: 3,
  grid: [],            // 2-D bool array [row][col]
  mode: "draw",        // "draw" | "clues"
  sidebarVisible: true,
  consoleVisible: false,
  rowClues: [],        // list of int[] (draw-mode derived or user-entered)
  colClues: [],
  busy: false,
  histData: null,      // {entries, threshold, rows, cols}
  userThreshold: null, // user-set threshold value (preserved across runs)
  trialCounts: null,   // array of per-trial count dicts (multi-trial benchmark)
  trialIdx: 0,         // currently displayed trial index
  clSize: "sm",        // solution grid size for classical: "sm"|"md"|"lg"
  quSize: "sm",        // solution grid size for quantum
  hwConnected: false,
  hwBackend: "Simulator",
  pan: { tx: 0, ty: 0, scale: 1 }, // shared pan/zoom for both draw + clues
};

// ── Helpers ────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

// ── DOM references ─────────────────────────────────────────────
const elSidebar       = $("sidebar");
const elToggleLabel   = $("toggle-label");
const elDrawView      = $("draw-view");
const elCluesView     = $("clues-view");
const elHwIndicator   = $("hw-status-indicator");
const elHistSvg       = $("qu-histogram");
const elHistTip       = $("qu-tooltip");
const elQuPlaceholder = $("qu-placeholder");
const elClPlaceholder = $("cl-placeholder");
const elQuArea        = $("qu-area");
const elQuList        = $("qu-list");
const elBtnBench      = $("btn-bench");
const elThresholdInput = $("threshold-input");

// ── SVG icon constants ──────────────────────────────────────────
const DICE_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" width="13" height="13" fill="currentColor" aria-hidden="true">
  <rect x="1.5" y="1.5" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.5"/>
  <circle cx="6"  cy="5.5" r="1.5"/>
  <circle cx="6"  cy="10"  r="1.5"/>
  <circle cx="6"  cy="14.5" r="1.5"/>
  <circle cx="14" cy="5.5" r="1.5"/>
  <circle cx="14" cy="10"  r="1.5"/>
  <circle cx="14" cy="14.5" r="1.5"/>
</svg>`;
const X_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" width="9" height="9" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><line x1="2" y1="2" x2="8" y2="8"/><line x1="8" y1="2" x2="2" y2="8"/></svg>`;
const UPLOAD_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 12" width="9" height="11" fill="currentColor" aria-hidden="true"><polygon points="5,1 9,5 7,5 7,9 3,9 3,5 1,5"/><rect x="1" y="10" width="8" height="1.5"/></svg>`;
const DOWNLOAD_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 12" width="9" height="11" fill="currentColor" aria-hidden="true"><polygon points="5,10 9,6 7,6 7,2 3,2 3,6 1,6"/><rect x="1" y="10.5" width="8" height="1.5"/></svg>`;
const CLOUD_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 12" width="14" height="10" fill="currentColor" aria-hidden="true"><path d="M14.5 4.9A4 4 0 007.4 2.5a3 3 0 00-5 2A3 3 0 002.5 11H14a3 3 0 00.5-6.1z"/></svg>`;
const PLAY_SVG    = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" width="9" height="9" fill="currentColor" aria-hidden="true"><polygon points="2,1 9,5 2,9"/></svg>`;
const PLUS_SVG    = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" width="8" height="8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><line x1="5" y1="1" x2="5" y2="9"/><line x1="1" y1="5" x2="9" y2="5"/></svg>`;
const EXPORT_SVG  = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12" width="10" height="10" fill="currentColor" aria-hidden="true"><path d="M2 9h8v1.5H2zm3.3-1.6V2h1.4v5.4l2-2 1 1L6 9 2.3 6.4l1-1z"/></svg>`;
const IMPORT_SVG  = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12" width="10" height="10" fill="currentColor" aria-hidden="true"><path d="M2 9h8v1.5H2zM5.3 2v5.4L3.3 5.4l-1 1L6 9l3.7-2.6-1-1-2 2V2z"/></svg>`;
const TRASH_SVG   = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 12" width="9" height="11" fill="currentColor" aria-hidden="true"><rect x="1" y="3" width="8" height="8"/><rect x="3" y="1" width="4" height="1.5"/><line x1="0" y1="3" x2="10" y2="3" stroke="currentColor" stroke-width="1"/></svg>`;

// Export to namespace
Object.assign(App, {
  state, $,
  elSidebar, elToggleLabel, elDrawView, elCluesView,
  elHwIndicator, elHistSvg, elHistTip,
  elQuPlaceholder, elClPlaceholder, elQuArea, elQuList,
  elBtnBench, elThresholdInput,
  DICE_SVG, X_SVG, UPLOAD_SVG, DOWNLOAD_SVG, CLOUD_SVG,
  PLAY_SVG, PLUS_SVG, EXPORT_SVG, IMPORT_SVG, TRASH_SVG,
});
