"use strict";
/* =============================================================
   UI controls — sidebar, theme, mode switch, hardware settings,
   status/busy, resize handles, clue grid, runs cache.
   ============================================================= */

(function () {
const { state, $,
        elSidebar, elToggleLabel, elDrawView, elCluesView,
        elHwIndicator, elBtnBench, elThresholdInput,
        X_SVG, UPLOAD_SVG, DOWNLOAD_SVG, PLUS_SVG, PLAY_SVG,
       } = App;

// ── Status and busy helpers ────────────────────────────────────
function setStatus(msg, level) {
  const terminal = $("status-terminal");
  const inner    = $("status-terminal-inner");
  if (!inner) return;
  const ts  = new Date().toTimeString().slice(0, 8);
  const line = document.createElement("div");
  line.className = "log-entry";
  const tsEl = document.createElement("span");
  tsEl.className   = "log-time";
  tsEl.textContent = ts;
  const msgEl = document.createElement("span");
  msgEl.className  = "log-msg" + (level === "ok" ? " log-ok" : level === "err" ? " log-err" : level === "warn" ? " log-warn" : "");
  msgEl.textContent = msg;
  line.appendChild(tsEl);
  line.appendChild(msgEl);
  inner.appendChild(line);
  terminal.scrollTop = terminal.scrollHeight;
}

function setBusy(busy) {
  state.busy = busy;
  elBtnBench.disabled = busy;
  if (busy) {
    elBtnBench.innerHTML = `<span class="ui-spinner ui-spinner-xs"></span> Running\u2026`;
  } else {
    updateBenchBtn();
  }
  document.querySelectorAll(".icon-btn").forEach(b => b.disabled = busy);
  document.querySelectorAll(".corner-random-btn, .corner-clear-btn, .corner-open-btn, .corner-save-btn")
    .forEach(b => b.disabled = busy);
  const delBtn = $("btn-delete-runs");
  if (delBtn) delBtn.disabled = busy;
}

// ── Hardware status ────────────────────────────────────────────
function applyHwStatus({ connected, backend_name }) {
  state.hwConnected = connected;
  state.hwBackend   = backend_name || "Simulator";
  if (elHwIndicator) {
    elHwIndicator.textContent = connected ? `Connected: ${state.hwBackend}` : "Disconnected";
    elHwIndicator.className   = connected ? "hw-status-on" : "hw-status-off";
  }
  updateBenchBtn();
}

function updateBenchBtn() {
  const t = Math.max(1, parseInt($("trials-input").value, 10) || 1);
  const hw = state.hwConnected ? state.hwBackend : "Simulator";
  elBtnBench.innerHTML = `${PLAY_SVG} Run on ${hw}`;
}

// ── Theme cycling ───────────────────────────────────────────────
// To add a new theme: append an entry here AND add a [data-theme="id"] block
// in style.css.  The cycle order follows this array: 0→1→0→…
const THEMES = [
  {
    id: "dark",
    nextLabel: "Light mode",
    // Sun icon — clicking will switch TO light
    icon: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`,
  },
  {
    id: "light",
    nextLabel: "Dark mode",
    // Moon icon — clicking will switch TO dark
    icon: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`,
  },
];

function initThemeToggle() {
  const btn = document.getElementById("theme-toggle");
  if (!btn) return;

  // Restore stored theme (validate against known IDs to avoid stale values)
  const stored = localStorage.getItem("theme");
  if (stored && THEMES.some(t => t.id === stored)) {
    document.documentElement.setAttribute("data-theme", stored);
  }

  function currentIdx() {
    const id = document.documentElement.getAttribute("data-theme") || "dark";
    const i = THEMES.findIndex(t => t.id === id);
    return i >= 0 ? i : 0;
  }

  function update() {
    const theme = THEMES[currentIdx()];
    btn.innerHTML = theme.icon;
    const lbl = document.getElementById("theme-mode-label");
    if (lbl) lbl.textContent = theme.nextLabel;
  }

  update();
  btn.addEventListener("click", () => {
    const nextIdx = (currentIdx() + 1) % THEMES.length;
    const nextId = THEMES[nextIdx].id;
    document.documentElement.setAttribute("data-theme", nextId);
    localStorage.setItem("theme", nextId);
    update();
  });
}

// ── Sidebar toggle ─────────────────────────────────────────────
function toggleSidebar() {
  state.sidebarVisible = !state.sidebarVisible;
  if (state.sidebarVisible) {
    elSidebar.style.width = "";
    elSidebar.style.flex = "";
    elSidebar.classList.remove("hidden");
    elToggleLabel.textContent = "\u25c4 Editor";
  } else {
    elSidebar.style.width = "";
    elSidebar.style.flex = "";
    elSidebar.classList.add("hidden");
    elToggleLabel.textContent = "\u25ba Editor";
  }
}

// ── Clue grid (Clues mode) ─────────────────────────────────────
function getClueSlotCounts() {
  const rowDepth = state.rowClues.length
    ? Math.max(0, ...state.rowClues.map(c => c.filter(v => v > 0).length))
    : 0;
  const colDepth = state.colClues.length
    ? Math.max(0, ...state.colClues.map(c => c.filter(v => v > 0).length))
    : 0;
  return { rowSlots: rowDepth + 1, colSlots: colDepth + 1 };
}

function makeEditableSlot(val, onChange) {
  const wrap = document.createElement("div");
  wrap.className = "clue-slot-editable";
  const inp = document.createElement("input");
  inp.type = "text";
  inp.inputMode = "text";
  inp.pattern = "[0-9]*";
  inp.className = "slot-num-input";
  inp.value = val > 0 ? val : "";
  inp.placeholder = "";
  inp.addEventListener("input", onChange);
  wrap.appendChild(inp);
  return wrap;
}

function readRowSlots(r) {
  const cell = elCluesView.querySelector(`[data-rclue="${r}"]`);
  if (!cell) return [0];
  const vals = Array.from(cell.querySelectorAll(".slot-num-input"))
    .map(i => parseInt(i.value) || 0).filter(v => v > 0);
  return vals.length ? vals : [0];
}

function readColSlots(c) {
  const cell = elCluesView.querySelector(`[data-cclue="${c}"]`);
  if (!cell) return [0];
  const vals = Array.from(cell.querySelectorAll(".slot-num-input"))
    .map(i => parseInt(i.value) || 0).filter(v => v > 0);
  return vals.length ? vals : [0];
}

function onRowSlotChange(r) {
  state.rowClues[r] = readRowSlots(r);
  checkClueSlotRebuild();
}

function onColSlotChange(c) {
  state.colClues[c] = readColSlots(c);
  checkClueSlotRebuild();
}

function checkClueSlotRebuild() {
  if (state.mode !== "clues") return;
  const { rowSlots, colSlots } = getClueSlotCounts();
  const prevRow = parseInt(elCluesView.dataset.rowSlots || "0");
  const prevCol = parseInt(elCluesView.dataset.colSlots || "0");
  if (rowSlots !== prevRow || colSlots !== prevCol) buildClueGrid();
}

function doClearClues() {
  state.rowClues = Array.from({ length: state.rows }, () => [0]);
  state.colClues = Array.from({ length: state.cols }, () => [0]);
  buildClueGrid();
  setStatus("Clues cleared.");
}

function buildClueGrid() {
  const rows = state.rows, cols = state.cols;
  const { rowSlots, colSlots } = getClueSlotCounts();

  const tbl = document.createElement("table");
  tbl.className = "nonogram-table";

  const hdr = tbl.insertRow();

  const corner = hdr.insertCell();
  corner.className = "corner-cell";
  const cW = Math.max(2, rowSlots) * 18, cH = Math.max(2, colSlots) * 18;
  const cornerWrap = document.createElement("div");
  cornerWrap.style.cssText = `position:relative;width:${cW}px;height:${cH}px;`;
  const bW = cW / 2, bH = cH / 2;

  const clearBtn = document.createElement("button");
  clearBtn.className = "corner-clear-btn";
  clearBtn.title = "Clear all clues";
  clearBtn.innerHTML = X_SVG;
  clearBtn.style.width = `${bW}px`; clearBtn.style.height = `${bH}px`;
  clearBtn.addEventListener("click", doClearClues);
  cornerWrap.appendChild(clearBtn);

  const openBtn = document.createElement("button");
  openBtn.className = "corner-open-btn";
  openBtn.title = "Open puzzle";
  openBtn.innerHTML = UPLOAD_SVG;
  openBtn.style.width = `${bW}px`; openBtn.style.height = `${bH}px`;
  openBtn.addEventListener("click", App.doOpenPuzzle);
  cornerWrap.appendChild(openBtn);

  const saveBtn = document.createElement("button");
  saveBtn.className = "corner-save-btn";
  saveBtn.title = "Save puzzle";
  saveBtn.innerHTML = DOWNLOAD_SVG;
  saveBtn.style.width = `${bW}px`; saveBtn.style.height = `${bH}px`;
  saveBtn.addEventListener("click", App.doSavePuzzle);
  cornerWrap.appendChild(saveBtn);

  corner.appendChild(cornerWrap);

  for (let c = 0; c < cols; c++) {
    const td = hdr.insertCell();
    td.className = "col-clue";
    td.id = `qcclue-${c}`;
    td.dataset.cclue = c;
    const slotsDiv = document.createElement("div");
    slotsDiv.className = "col-clue-slots";
    const existing = state.colClues[c].filter(v => v > 0);
    const innerLen = colSlots - 1;
    const colPad   = innerLen - existing.length;
    for (let s = 0; s < colSlots; s++) {
      let val = 0;
      if (s > 0) {
        const valIdx = (s - 1) - colPad;
        val = valIdx >= 0 ? (existing[valIdx] || 0) : 0;
      }
      const _c = c;
      slotsDiv.appendChild(makeEditableSlot(val, () => onColSlotChange(_c)));
    }
    td.appendChild(slotsDiv);
  }

  const addColCell = hdr.insertCell();
  addColCell.className = "add-strip add-col-strip";
  addColCell.rowSpan = rows + 1;
  addColCell.title = "Add column";
  addColCell.innerHTML = PLUS_SVG;
  addColCell.addEventListener("click", App.addCol);

  for (let r = 0; r < rows; r++) {
    const tr = tbl.insertRow();

    const rClue = tr.insertCell();
    rClue.className = "row-clue";
    rClue.id = `qrclue-${r}`;
    rClue.dataset.rclue = r;
    const slotsDiv = document.createElement("div");
    slotsDiv.className = "row-clue-slots";
    const existing = state.rowClues[r].filter(v => v > 0);
    const innerLen = rowSlots - 1;
    const rowPad   = innerLen - existing.length;
    for (let s = 0; s < rowSlots; s++) {
      let val = 0;
      if (s > 0) {
        const valIdx = (s - 1) - rowPad;
        val = valIdx >= 0 ? (existing[valIdx] || 0) : 0;
      }
      const _r = r;
      slotsDiv.appendChild(makeEditableSlot(val, () => onRowSlotChange(_r)));
    }
    rClue.appendChild(slotsDiv);

    for (let c = 0; c < cols; c++) {
      const td = tr.insertCell();
      td.className = "cell-unknown";
      td.dataset.r = r;
      td.dataset.c = c;
      td.textContent = "?";
    }
  }

  const addRowTr = tbl.insertRow();
  const addRowCell = addRowTr.insertCell();
  addRowCell.className = "add-strip add-row-strip";
  addRowCell.colSpan = cols + 1;
  addRowCell.innerHTML = PLUS_SVG;
  addRowCell.title = "Add row";
  addRowCell.addEventListener("click", App.addRow);
  const cqGapCell = addRowTr.insertCell();
  cqGapCell.className = "add-strip add-both-strip";
  cqGapCell.innerHTML = PLUS_SVG;
  cqGapCell.title = "Add row and column";
  cqGapCell.addEventListener("click", () => {
    App.addRow(); App.addCol(); // handled by addRowAndCol via grid.js but sequential here
  });

  let _lastDelCell = null;
  tbl.addEventListener("mouseover", e => {
    const td = e.target.closest("td.cell-unknown");
    if (td === _lastDelCell) return;
    _lastDelCell = td;
    App.clearClueDeletePreview();
    if (td) App.showClueDeletePreview(+td.dataset.r, +td.dataset.c);
  });
  tbl.addEventListener("mouseleave", () => { App.clearClueDeletePreview(); _lastDelCell = null; });
  tbl.addEventListener("click", e => {
    const td = e.target.closest("td.cell-unknown");
    if (!td) return;
    const r = +td.dataset.r, c = +td.dataset.c;
    let changed = false;
    if (r >= 2 && r < state.rows) {
      state.rows = r; state.grid.splice(r); state.rowClues.splice(r); changed = true;
    }
    if (c >= 2 && c < state.cols) {
      state.cols = c;
      for (const row of state.grid) row.splice(c);
      state.colClues.splice(c); changed = true;
    }
    if (changed) { App.rebuildActiveGrid(); App.syncGridToServer(); }
  });

  elCluesView.dataset.rowSlots = rowSlots;
  elCluesView.dataset.colSlots = colSlots;
  elCluesView.innerHTML = "";
  const cluesCanvas = document.createElement("div");
  cluesCanvas.className = "grid-canvas";
  cluesCanvas.appendChild(tbl);
  elCluesView.appendChild(cluesCanvas);
  App.setupGridPanZoom(elCluesView, state.pan);
  App.applyPan(state.pan);
}

// ── Resizable pane handles ─────────────────────────────────────
function setupResizeHandles() {
  // Editor sidebar width
  makeDraggable($("sidebar-edge"),
    () => elSidebar.offsetWidth,
    w => {
      elSidebar.style.flex = "none";
      elSidebar.style.width = Math.max(180, w) + "px";
    });

  // Classical / Quantum solution split
  makeDraggableH($("cq-handle"),
    () => $("cl-half").offsetHeight,
    h => {
      $("cl-half").style.flex = "none";
      $("cl-half").style.height = Math.max(80, h) + "px";
      if (state.histData) App.drawHistogram(state.histData);
    });

  // Quantum solutions list / Histogram split
  makeDraggableH($("qh-handle"),
    () => $("qu-list").offsetHeight,
    h => {
      $("qu-list").style.flex = "none";
      $("qu-list").style.height = Math.max(40, h) + "px";
    });

  // Settings panel width
  makeDraggableInverse($("console-edge"),
    () => $("console-panel").offsetWidth,
    w => {
      $("console-panel").style.flex = "none";
      $("console-panel").style.width = Math.max(180, w) + "px";
    });

}

function makeDraggable(handle, getSize, setSize) {
  if (!handle) return;
  handle.addEventListener("mousedown", e => {
    e.preventDefault();
    const startX = e.clientX, startW = getSize();
    handle.classList.add("dragging");
    const onMove = me => setSize(startW + me.clientX - startX);
    const onUp = () => {
      handle.classList.remove("dragging");
      document.removeEventListener("mousemove", onMove);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp, { once: true });
  });
}

function makeDraggableInverse(handle, getSize, setSize) {
  if (!handle) return;
  handle.addEventListener("mousedown", e => {
    e.preventDefault();
    const startX = e.clientX, startW = getSize();
    handle.classList.add("dragging");
    const onMove = me => setSize(startW - (me.clientX - startX));
    const onUp = () => {
      handle.classList.remove("dragging");
      document.removeEventListener("mousemove", onMove);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp, { once: true });
  });
}

function makeDraggableH(handle, getSize, setSize) {
  if (!handle) return;
  handle.addEventListener("mousedown", e => {
    e.preventDefault();
    const startY = e.clientY, startH = getSize();
    handle.classList.add("dragging");
    const onMove = me => setSize(startH + me.clientY - startY);
    const onUp = () => {
      handle.classList.remove("dragging");
      document.removeEventListener("mousemove", onMove);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp, { once: true });
  });
}

// ── Runs cache box ─────────────────────────────────────────────
async function fetchRunsInfo() {
  const box = $("runs-cache-box");
  if (!box) return;
  try {
    const r = await fetch(API_BASE + "/api/runs/info");
    const d = await r.json();
    const kb = (d.total_bytes / 1024).toFixed(1);
    const newestStr = d.newest
      ? new Date(d.newest).toLocaleString(undefined, { month:"short", day:"numeric", hour:"2-digit", minute:"2-digit" })
      : "\u2014";
    $("runs-cache-count").textContent = `${d.count} run${d.count !== 1 ? "s" : ""}`;
    $("runs-cache-size").textContent = `${kb} KB`;
    $("runs-cache-latest").textContent = `latest: ${newestStr}`;
    $("btn-delete-runs").disabled = state.busy || d.count === 0;
  } catch { /* non-fatal */ }
}

// Export to namespace
Object.assign(App, {
  setStatus, setBusy, applyHwStatus, updateBenchBtn,
  initThemeToggle, toggleSidebar,
  buildClueGrid, setupResizeHandles, fetchRunsInfo,
});
})();
