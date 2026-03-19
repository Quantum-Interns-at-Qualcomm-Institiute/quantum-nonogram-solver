"use strict";
/* =============================================================
   Grid manipulation — drawing, clues, pan/zoom, resize.
   ============================================================= */

(function () {
const { state, $, elDrawView, elCluesView,
        DICE_SVG, X_SVG, UPLOAD_SVG, DOWNLOAD_SVG, PLUS_SVG,
       } = App;

// ── Grid helpers ───────────────────────────────────────────────
function initGrid() {
  state.grid = Array.from({ length: state.rows }, () =>
    Array(state.cols).fill(false));
  recomputeClues();
}

function recomputeClues() {
  state.rowClues = computeRowClues(state.grid, state.rows, state.cols);
  state.colClues = computeColClues(state.grid, state.rows, state.cols);
}

function rle(bits) {
  const runs = [];
  let count = 0;
  for (const b of bits) {
    if (b) count++;
    else if (count) { runs.push(count); count = 0; }
  }
  if (count) runs.push(count);
  return runs.length ? runs : [0];
}

function computeRowClues(grid, rows, cols) {
  return Array.from({ length: rows }, (_, r) => rle(grid[r]));
}

function computeColClues(grid, rows, cols) {
  return Array.from({ length: cols }, (_, c) =>
    rle(Array.from({ length: rows }, (_, r) => grid[r][c])));
}

// ── Clue slot helpers ──────────────────────────────────────────
function getMaxRowLen() {
  if (!state.rowClues.length) return 1;
  return Math.max(1, ...state.rowClues.map(c => c.filter(v => v > 0).length));
}
function getMaxColLen() {
  if (!state.colClues.length) return 1;
  return Math.max(1, ...state.colClues.map(c => c.filter(v => v > 0).length));
}

function makeRowClueContent(clue, maxLen) {
  const nonzero = clue.filter(v => v > 0);
  const div = document.createElement("div");
  div.className = "row-clue-slots";
  for (let i = 0; i < maxLen; i++) {
    const slot = document.createElement("span");
    const valIdx = i - (maxLen - nonzero.length);
    slot.className = valIdx >= 0 ? "clue-slot" : "clue-slot empty";
    if (valIdx >= 0) slot.textContent = nonzero[valIdx];
    div.appendChild(slot);
  }
  return div;
}

function makeColClueContent(clue, maxLen) {
  const nonzero = clue.filter(v => v > 0);
  const div = document.createElement("div");
  div.className = "col-clue-slots";
  for (let i = 0; i < maxLen; i++) {
    const slot = document.createElement("span");
    const valIdx = i - (maxLen - nonzero.length);
    slot.className = valIdx >= 0 ? "clue-slot" : "clue-slot empty";
    if (valIdx >= 0) slot.textContent = nonzero[valIdx];
    div.appendChild(slot);
  }
  return div;
}

// ── Grid build (Draw mode) ─────────────────────────────────────
function buildGrid() {
  const rows = state.rows, cols = state.cols;
  const maxRowLen = getMaxRowLen();
  const maxColLen = getMaxColLen();

  const tbl = document.createElement("table");
  tbl.className = "nonogram-table";

  // ── Header row: corner + col clues ──
  const hdr = tbl.insertRow();

  const corner = hdr.insertCell();
  corner.className = "corner-cell";
  const cW = Math.max(2, maxRowLen) * 18, cH = Math.max(2, maxColLen) * 18;
  const cornerWrap = document.createElement("div");
  cornerWrap.style.cssText = `position:relative;width:${cW}px;height:${cH}px;`;
  const bW = cW / 2, bH = cH / 2;

  const clearBtn = document.createElement("button");
  clearBtn.className = "corner-clear-btn";
  clearBtn.title = "Clear grid";
  clearBtn.innerHTML = X_SVG;
  clearBtn.style.width = `${bW}px`; clearBtn.style.height = `${bH}px`;
  clearBtn.addEventListener("click", doClear);
  cornerWrap.appendChild(clearBtn);

  const openBtn = document.createElement("button");
  openBtn.className = "corner-open-btn";
  openBtn.title = "Open puzzle";
  openBtn.innerHTML = UPLOAD_SVG;
  openBtn.style.width = `${bW}px`; openBtn.style.height = `${bH}px`;
  openBtn.addEventListener("click", doOpenPuzzle);
  cornerWrap.appendChild(openBtn);

  const saveBtn = document.createElement("button");
  saveBtn.className = "corner-save-btn";
  saveBtn.title = "Save puzzle";
  saveBtn.innerHTML = App.DOWNLOAD_SVG;
  saveBtn.style.width = `${bW}px`; saveBtn.style.height = `${bH}px`;
  saveBtn.addEventListener("click", doSavePuzzle);
  cornerWrap.appendChild(saveBtn);

  const rndBtn = document.createElement("button");
  rndBtn.className = "corner-random-btn";
  rndBtn.title = "Randomize puzzle";
  rndBtn.innerHTML = DICE_SVG;
  rndBtn.style.width = `${bW}px`; rndBtn.style.height = `${bH}px`;
  rndBtn.addEventListener("click", doRandomize);
  cornerWrap.appendChild(rndBtn);
  corner.appendChild(cornerWrap);

  // Column clue cells
  for (let c = 0; c < cols; c++) {
    const td = hdr.insertCell();
    td.className = "col-clue";
    td.id = `cclue-${c}`;
    td.appendChild(makeColClueContent(state.colClues[c], maxColLen));

    if (c >= 2) {
      const delBtn = document.createElement("span");
      delBtn.className = "del-clue-btn";
      delBtn.textContent = "\u00d7";
      delBtn.title = `Delete columns ${c + 1}\u2013${cols}`;
      const _c = c;
      td.addEventListener("mouseenter", () => {
        for (let i = _c; i < state.cols; i++) {
          const el = $(`cclue-${i}`); if (el) el.classList.add("will-delete");
          elDrawView.querySelectorAll(`td.cell[data-c="${i}"]`)
            .forEach(c => c.classList.add("cell-will-delete"));
        }
      });
      td.addEventListener("mouseleave", () => {
        for (let i = 0; i < state.cols; i++) {
          const el = $(`cclue-${i}`); if (el) el.classList.remove("will-delete");
          elDrawView.querySelectorAll(`td.cell[data-c="${i}"]`)
            .forEach(c => c.classList.remove("cell-will-delete"));
        }
      });
      delBtn.addEventListener("click", e => { e.stopPropagation(); deleteColsFrom(_c); });
      td.appendChild(delBtn);
    }
  }

  // Add-col strip
  const addColCell = hdr.insertCell();
  addColCell.className = "add-strip add-col-strip";
  addColCell.rowSpan = rows + 1;
  addColCell.title = "Add column";
  addColCell.innerHTML = PLUS_SVG;
  addColCell.addEventListener("click", addCol);

  // ── Data rows ──
  for (let r = 0; r < rows; r++) {
    const tr = tbl.insertRow();

    const rClue = tr.insertCell();
    rClue.className = "row-clue";
    rClue.id = `rclue-${r}`;
    rClue.appendChild(makeRowClueContent(state.rowClues[r], maxRowLen));

    if (r >= 2) {
      const delBtn = document.createElement("span");
      delBtn.className = "del-clue-btn";
      delBtn.textContent = "\u00d7";
      delBtn.title = `Delete rows ${r + 1}\u2013${rows}`;
      const _r = r;
      rClue.addEventListener("mouseenter", () => {
        for (let i = _r; i < state.rows; i++) {
          const el = $(`rclue-${i}`); if (el) el.classList.add("will-delete");
          elDrawView.querySelectorAll(`td.cell[data-r="${i}"]`)
            .forEach(c => c.classList.add("cell-will-delete"));
        }
      });
      rClue.addEventListener("mouseleave", () => {
        for (let i = 0; i < state.rows; i++) {
          const el = $(`rclue-${i}`); if (el) el.classList.remove("will-delete");
          elDrawView.querySelectorAll(`td.cell[data-r="${i}"]`)
            .forEach(c => c.classList.remove("cell-will-delete"));
        }
      });
      delBtn.addEventListener("click", e => { e.stopPropagation(); deleteRowsFrom(_r); });
      rClue.appendChild(delBtn);
    }

    for (let c = 0; c < cols; c++) {
      const td = tr.insertCell();
      td.className = "cell" + (state.grid[r][c] ? " filled" : "");
      td.dataset.r = r;
      td.dataset.c = c;
    }
  }

  // ── Add-row strip ──
  const addRowTr = tbl.insertRow();
  const addRowCell = addRowTr.insertCell();
  addRowCell.className = "add-strip add-row-strip";
  addRowCell.colSpan = cols + 1;
  addRowCell.innerHTML = PLUS_SVG;
  addRowCell.title = "Add row";
  addRowCell.addEventListener("click", addRow);
  const gapCell = addRowTr.insertCell();
  gapCell.className = "add-strip add-both-strip";
  gapCell.innerHTML = PLUS_SVG;
  gapCell.title = "Add row and column";
  gapCell.addEventListener("click", addRowAndCol);

  tbl.addEventListener("mousedown", onGridMouseDown);
  tbl.addEventListener("mouseover", onGridMouseOver);
  document.addEventListener("mouseup", () => { _dragFill = null; });

  elDrawView.dataset.maxRowLen = maxRowLen;
  elDrawView.dataset.maxColLen = maxColLen;
  elDrawView.innerHTML = "";
  const drawCanvas = document.createElement("div");
  drawCanvas.className = "grid-canvas";
  drawCanvas.appendChild(tbl);
  elDrawView.appendChild(drawCanvas);
  setupGridPanZoom(elDrawView, state.pan);
  centerCanvas(elDrawView, state.pan);
}

// ── Cell interaction ────────────────────────────────────────────
let _dragFill = null;

function onGridMouseDown(e) {
  const td = e.target.closest("td.cell");
  if (!td) return;
  e.preventDefault();
  const r = +td.dataset.r, c = +td.dataset.c;
  _dragFill = !state.grid[r][c];
  toggleCell(r, c, _dragFill);
}

function onGridMouseOver(e) {
  if (_dragFill === null) return;
  const td = e.target.closest("td.cell");
  if (!td) return;
  const r = +td.dataset.r, c = +td.dataset.c;
  if (state.grid[r][c] !== _dragFill) toggleCell(r, c, _dragFill);
}

function toggleCell(r, c, fill) {
  state.grid[r][c] = fill;
  const td = document.querySelector(`td[data-r="${r}"][data-c="${c}"]`);
  if (td) td.className = "cell" + (fill ? " filled" : "");
  recomputeClues();
  updateClueCells();
}

function updateClueCells() {
  const newMaxRowLen = getMaxRowLen();
  const newMaxColLen = getMaxColLen();
  const prevMaxRowLen = parseInt(elDrawView.dataset.maxRowLen || "0");
  const prevMaxColLen = parseInt(elDrawView.dataset.maxColLen || "0");

  if (newMaxRowLen !== prevMaxRowLen || newMaxColLen !== prevMaxColLen) {
    _dragFill = null;
    buildGrid();
    return;
  }

  for (let r = 0; r < state.rows; r++) {
    const el = $(`rclue-${r}`);
    if (!el) continue;
    const slots = el.querySelectorAll(".clue-slot");
    const nonzero = state.rowClues[r].filter(v => v > 0);
    const pad = newMaxRowLen - nonzero.length;
    slots.forEach((slot, i) => {
      if (i < pad) { slot.className = "clue-slot empty"; slot.textContent = ""; }
      else         { slot.className = "clue-slot";       slot.textContent = nonzero[i - pad]; }
    });
  }
  for (let c = 0; c < state.cols; c++) {
    const el = $(`cclue-${c}`);
    if (!el) continue;
    const slots = el.querySelectorAll(".clue-slot");
    const nonzero = state.colClues[c].filter(v => v > 0);
    const pad = newMaxColLen - nonzero.length;
    slots.forEach((slot, i) => {
      if (i < pad) { slot.className = "clue-slot empty"; slot.textContent = ""; }
      else         { slot.className = "clue-slot";       slot.textContent = nonzero[i - pad]; }
    });
  }
}

// ── Dynamic grid sizing ────────────────────────────────────────
function addRow() {
  if (state.rows >= MAX_GRID) return;
  state.rows++;
  state.grid.push(Array(state.cols).fill(false));
  if (state.mode === "clues") { state.rowClues.push([0]); }
  else recomputeClues();
  rebuildActiveGrid();
  syncGridToServer();
}

function addCol() {
  if (state.cols >= MAX_GRID) return;
  state.cols++;
  for (const row of state.grid) row.push(false);
  if (state.mode === "clues") { state.colClues.push([0]); }
  else recomputeClues();
  rebuildActiveGrid();
  syncGridToServer();
}

function deleteRowsFrom(r) {
  if (r < 2) return;
  state.rows = r;
  state.grid.splice(r);
  if (state.mode === "clues") { state.rowClues.splice(r); }
  else recomputeClues();
  rebuildActiveGrid();
  syncGridToServer();
}

function deleteColsFrom(c) {
  if (c < 2) return;
  state.cols = c;
  for (const row of state.grid) row.splice(c);
  if (state.mode === "clues") { state.colClues.splice(c); }
  else recomputeClues();
  rebuildActiveGrid();
  syncGridToServer();
}

function syncGridToServer() {
  fetch(API_BASE + "/api/grid", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rows: state.rows, cols: state.cols, grid: state.grid }),
  });
}

function rebuildActiveGrid() {
  if (state.mode === "clues") App.buildClueGrid();
  else buildGrid();
}

function addRowAndCol() {
  if (state.rows >= MAX_GRID && state.cols >= MAX_GRID) return;
  if (state.rows < MAX_GRID) {
    state.rows++;
    state.grid.push(Array(state.cols).fill(false));
    if (state.mode === "clues") state.rowClues.push([0]);
    else recomputeClues();
  }
  if (state.cols < MAX_GRID) {
    state.cols++;
    for (const row of state.grid) row.push(false);
    if (state.mode === "clues") state.colClues.push([0]);
    else recomputeClues();
  }
  rebuildActiveGrid();
  syncGridToServer();
}

// ── Pan / zoom ─────────────────────────────────────────────────
function applyPan(pan) {
  const t = `translate(${pan.tx}px,${pan.ty}px) scale(${pan.scale})`;
  [elDrawView, elCluesView].forEach(v => {
    const c = v.querySelector(".grid-canvas");
    if (c) c.style.transform = t;
  });
}

function centerCanvas(viewEl, pan) {
  requestAnimationFrame(() => {
    const canvas = viewEl.querySelector(".grid-canvas");
    if (!canvas) return;
    pan.scale = 1;
    pan.tx = Math.max(8, (viewEl.offsetWidth  - canvas.offsetWidth)  / 2);
    pan.ty = Math.max(8, (viewEl.offsetHeight - canvas.offsetHeight) / 2);
    applyPan(pan);
  });
}

function setupGridPanZoom(viewEl, pan) {
  if (viewEl._panCleanup) viewEl._panCleanup();

  let dragging = false, startX = 0, startY = 0, startTx = 0, startTy = 0, didDrag = false;

  function onDown(e) {
    if (e.button === 1 || e.altKey) {
      e.preventDefault();
    } else if (e.button === 0) {
      const t = e.target;
      const isCell = t.classList.contains("filled") || t.classList.contains("empty") ||
                     t.classList.contains("cell-unknown") || t.closest(".slot-num-input");
      if (isCell) return;
    } else { return; }
    dragging = true; didDrag = false;
    startX = e.clientX; startY = e.clientY;
    startTx = pan.tx; startTy = pan.ty;
    viewEl.style.cursor = "grabbing";
  }
  function onMove(e) {
    if (!dragging) return;
    const dx = e.clientX - startX, dy = e.clientY - startY;
    if (Math.abs(dx) + Math.abs(dy) > 2) didDrag = true;
    if (!didDrag) return;
    pan.tx = startTx + dx;
    pan.ty = startTy + dy;
    applyPan(pan);
  }
  function onUp() {
    if (!dragging) return;
    dragging = false;
    viewEl.style.cursor = "";
  }
  function onWheel(e) {
    e.preventDefault();
    const rect = viewEl.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
    const newScale = Math.max(0.3, Math.min(5, pan.scale * factor));
    pan.tx = mx - (mx - pan.tx) * (newScale / pan.scale);
    pan.ty = my - (my - pan.ty) * (newScale / pan.scale);
    pan.scale = newScale;
    applyPan(pan);
  }

  viewEl.addEventListener("mousedown", onDown);
  window.addEventListener("mousemove", onMove);
  window.addEventListener("mouseup", onUp);
  viewEl.addEventListener("wheel", onWheel, { passive: false });

  viewEl._panCleanup = () => {
    viewEl.removeEventListener("mousedown", onDown);
    window.removeEventListener("mousemove", onMove);
    window.removeEventListener("mouseup", onUp);
    viewEl.removeEventListener("wheel", onWheel);
  };
}

// ── Puzzle I/O ──────────────────────────────────────────────────
function getCurrentPuzzle() {
  if (state.mode === "draw") recomputeClues();
  return {
    row_clues: state.rowClues,
    col_clues: state.colClues,
  };
}

function doClear() {
  state.grid = Array.from({ length: state.rows }, () =>
    Array(state.cols).fill(false));
  recomputeClues();
  buildGrid();
  syncGridToServer();
  App.setStatus("Grid cleared.");
}

async function doRandomize() {
  const rows = state.rows, cols = state.cols;
  try {
    const res = await fetch(API_BASE + "/api/randomize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows, cols }),
    });
    if (!res.ok) { App.setStatus("Randomize failed.", "err"); return; }
    const data = await res.json();
    state.rows = data.rows; state.cols = data.cols; state.grid = data.grid;
    recomputeClues();
    rebuildActiveGrid();
    syncGridToServer();
    const filled = state.grid.flat().filter(Boolean).length;
    App.setStatus(`Randomized ${rows}\u00d7${cols} puzzle (${filled} filled).`);
  } catch (err) {
    App.setStatus("Randomize error: " + err.message, "err");
  }
}

function doOpenPuzzle() { $("file-input").click(); }

async function doSavePuzzle() {
  const puzzle = getCurrentPuzzle();
  const res = await fetch(API_BASE + "/api/puzzle/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      row_clues: puzzle.row_clues,
      col_clues: puzzle.col_clues,
    }),
  });
  if (!res.ok) { App.setStatus("Save failed.", "err"); return; }
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") || "";
  const m = cd.match(/filename="?([^"]+)"?/);
  const fname = m ? m[1] : "puzzle.non.json";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = fname; a.click();
  URL.revokeObjectURL(url);
  App.setStatus(`Saved: ${fname}`);
}

function getBestSolSize(rows, cols) {
  const cells = rows * cols;
  if (cells <= 6)  return "lg";
  if (cells <= 16) return "md";
  return "sm";
}

// ── Clue delete preview helpers (for clues mode) ───────────────
function showClueDeletePreview(r, c) {
  const willRow = r >= 2;
  const willCol = c >= 2;
  if (!willRow && !willCol) return;
  if (willRow) {
    for (let dr = r; dr < state.rows; dr++)
      elCluesView.querySelectorAll(`[data-r="${dr}"].cell-unknown`)
        .forEach(el => { el.classList.add("will-delete"); el.textContent = "\u00d7"; });
  }
  if (willCol) {
    for (let dc = c; dc < state.cols; dc++)
      elCluesView.querySelectorAll(`[data-c="${dc}"].cell-unknown`)
        .forEach(el => { el.classList.add("will-delete"); el.textContent = "\u00d7"; });
  }
  const hov = elCluesView.querySelector(`[data-r="${r}"][data-c="${c}"].cell-unknown`);
  if (hov) hov.classList.add("delete-trigger");
}

function clearClueDeletePreview() {
  elCluesView.querySelectorAll(".cell-unknown.will-delete, .cell-unknown.delete-trigger")
    .forEach(el => { el.classList.remove("will-delete", "delete-trigger"); el.textContent = "?"; });
}

// Export to namespace
Object.assign(App, {
  initGrid, recomputeClues, buildGrid, rebuildActiveGrid,
  syncGridToServer, getCurrentPuzzle,
  doClear, doRandomize, doOpenPuzzle, doSavePuzzle,
  getBestSolSize, applyPan, centerCanvas, setupGridPanZoom,
  showClueDeletePreview, clearClueDeletePreview,
  getMaxRowLen, getMaxColLen, makeRowClueContent, makeColClueContent,
  addRow, addCol, deleteRowsFrom, deleteColsFrom,
});
})();
