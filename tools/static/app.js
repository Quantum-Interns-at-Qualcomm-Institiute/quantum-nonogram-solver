"use strict";
/* =============================================================
   Nonogram Web App — bootstrap / init
   Loads after: state.js, grid.js, solver.js, ui.js
   ============================================================= */

(function () {
const { state, $,
        elDrawView, elCluesView, elQuArea,
        elHistSvg, elHistTip, elBtnBench, elThresholdInput,
        X_SVG,
       } = App;

// ── Socket.IO ──────────────────────────────────────────────────
const socket = io(API_BASE);

socket.on("status",       ({ msg, level }) => App.setStatus(msg, level));
socket.on("busy",         ({ busy }) => App.setBusy(busy));
socket.on("cl_done",      App.renderClassical);
socket.on("qu_done",      ({ counts, rows, cols }) => App.renderQuantum(counts, rows, cols));
socket.on("bench_done",   App.renderBenchmark);
socket.on("solver_error", ({ message }) => {
  App.setStatus("Error: " + message, "err");
  App.setBusy(false);
});
socket.on("hw_status",    App.applyHwStatus);

// ── Init ───────────────────────────────────────────────────────
function init() {
  App.initGrid();
  App.buildGrid();
  App.setupResizeHandles();
  App.initThemeToggle();

  // ResizeObserver redraws SVG histograms at actual pixel size
  new ResizeObserver(() => {
    if (state.histData) App.drawHistogram(state.histData);
    else                App.drawEmptyHistogram();
  }).observe(elQuArea);

  // Threshold number input
  elThresholdInput.addEventListener("input", () => {
    const pct = parseFloat(elThresholdInput.value);
    if (isNaN(pct)) return;
    const val = Math.max(0, Math.min(1, pct / 100));
    state.userThreshold = val;
    if (state.histData) {
      state.histData.threshold = val;
      App.drawHistogram(state.histData);
      App.renderQuantumList();
    }
  });

  // Tooltip follows cursor
  elHistSvg.addEventListener("mousemove", e => {
    if (elHistTip.style.display === "none") return;
    const tipW = elHistTip.offsetWidth  || 96;
    const tipH = elHistTip.offsetHeight || 60;
    let sx = e.clientX + 14, sy = e.clientY - tipH - 6;
    if (sx + tipW > window.innerWidth)  sx = e.clientX - tipW - 10;
    if (sy < 0)                         sy = e.clientY + 14;
    elHistTip.style.left = sx + "px";
    elHistTip.style.top  = sy + "px";
  });

  // Bench button label
  $("trials-input").addEventListener("input", App.updateBenchBtn);
  App.updateBenchBtn();

  // Solution size toggle
  document.querySelectorAll("#sol-size-toggle .sol-size-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const sz = btn.dataset.size;
      state.clSize = state.quSize = sz;
      document.querySelectorAll("#sol-size-toggle .sol-size-btn")
        .forEach(b => b.classList.toggle("active", b === btn));
      $("cl-canvas").querySelectorAll(".sol-table").forEach(t => { t.className = "sol-table sz-" + sz; });
      $("qu-list").querySelectorAll(".sol-table").forEach(t => { t.className = "sol-table sz-" + sz; });
    });
  });

  // Clear terminal
  $("btn-clear-terminal").innerHTML = X_SVG;
  $("btn-clear-terminal").addEventListener("click", () => {
    $("status-terminal-inner").innerHTML = "";
  });

  requestAnimationFrame(() => {
    App.drawEmptyHistogram();
  });
}

// ── Sidebar toggle ─────────────────────────────────────────────
$("toggle-strip").addEventListener("click", App.toggleSidebar);

// ── Console flyout toggle ───────────────────────────────────────
$("console-toggle-strip").addEventListener("click", () => {
  state.consoleVisible = !state.consoleVisible;
  const consolePanel = $("console-panel");
  if (state.consoleVisible) {
    consolePanel.style.width = "";
    consolePanel.style.flex = "";
    consolePanel.classList.add("visible");
    $("console-edge").classList.add("visible");
    $("console-toggle-label").textContent = "\u25c4 Settings";
    App.fetchRunsInfo();
  } else {
    consolePanel.style.width = "";
    consolePanel.style.flex = "";
    consolePanel.classList.remove("visible");
    $("console-edge").classList.remove("visible");
    $("console-toggle-label").textContent = "\u25ba Settings";
  }
});

// ── Mode switch ────────────────────────────────────────────────
document.querySelectorAll(".mode-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const mode = btn.dataset.mode;
    if (mode === state.mode) return;
    state.mode = mode;
    document.querySelectorAll(".mode-btn").forEach(b =>
      b.classList.toggle("active", b.dataset.mode === mode));
    if (mode === "draw") {
      elCluesView.style.display = "none";
      elDrawView.style.display = "";
      App.setStatus("Draw mode \u2014 click cells to fill/empty.");
    } else {
      App.buildClueGrid();
      elDrawView.style.display = "none";
      elCluesView.style.display = "";
      App.setStatus("Clues mode \u2014 enter clues, solutions update automatically.");
    }
  });
});

// ── Benchmark button ───────────────────────────────────────────
elBtnBench.addEventListener("click", () => {
  if (state.busy) return;
  App.clearSolverResults();
  const puzzle = App.getCurrentPuzzle();
  const trials = Math.max(1, parseInt($("trials-input").value, 10) || 1);
  fetch(API_BASE + "/api/benchmark", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...puzzle, trials }),
  });
});

// ── File input handler ─────────────────────────────────────────
$("file-input").addEventListener("change", async e => {
  const file = e.target.files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(API_BASE + "/api/puzzle/load", { method: "POST", body: form });
  if (!res.ok) { App.setStatus("Load failed.", "err"); return; }
  const data = await res.json();
  state.rows = data.rows; state.cols = data.cols;
  state.rowClues = data.row_clues;
  state.colClues = data.col_clues;
  state.grid = Array.from({ length: data.rows }, () =>
    Array(data.cols).fill(false));
  state.mode = "draw";
  document.querySelectorAll(".mode-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.mode === "draw"));
  elCluesView.style.display = "none";
  elDrawView.style.display = "";
  App.buildGrid();
  App.setStatus(`Loaded: ${file.name}`);
  e.target.value = "";
});

// ── IBM Hardware panel ─────────────────────────────────────────
$("hw-fetch-backends").addEventListener("click", async () => {
  const token = $("hw-token").value.trim();
  const channel = document.querySelector('input[name="hw-channel"]:checked').value;
  if (!token) { App.setStatus("Please enter an API token.", "warn"); return; }
  const btn = $("hw-fetch-backends");
  btn.textContent = "Fetching\u2026"; btn.disabled = true;
  try {
    const res = await fetch(API_BASE + "/api/hw/backends", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, channel }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    const sel = $("hw-backend-select");
    sel.innerHTML = data.backends.map(b =>
      `<option value="${b.name}">${b.name} (${b.qubits} qubits, ${b.pending} pending)</option>`
    ).join("");
    $("hw-backends-wrap").style.display = "";
  } catch (err) {
    App.setStatus("Failed to fetch backends: " + err.message, "err");
  } finally {
    btn.textContent = "Fetch Backends"; btn.disabled = false;
  }
});

$("hw-connect").addEventListener("click", async () => {
  const token = $("hw-token").value.trim();
  const channel = document.querySelector('input[name="hw-channel"]:checked').value;
  const backend = $("hw-backend-select").value;
  const shots = parseInt($("hw-shots").value, 10) || 1024;
  if (!token || !backend) { App.setStatus("Please provide token and backend.", "warn"); return; }
  await fetch(API_BASE + "/api/hw/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, channel, backend_name: backend, shots }),
  });
});

$("hw-disconnect").addEventListener("click", async () => {
  await fetch(API_BASE + "/api/hw/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ disconnect: true }),
  });
});

// ── Runs cache box ─────────────────────────────────────────────
$("btn-delete-runs").addEventListener("click", async () => {
  if (state.busy) return;
  if (!confirm(`Delete all saved run files from the cache?`)) return;
  const btn = $("btn-delete-runs");
  btn.disabled = true;
  try {
    const r = await fetch(API_BASE + "/api/runs/delete", { method: "POST" });
    const d = await r.json();
    if (d.ok) {
      App.setStatus(`Deleted ${d.deleted} cached run${d.deleted !== 1 ? "s" : ""}.`, "ok");
      App.fetchRunsInfo();
    } else {
      App.setStatus("Delete failed: " + (d.error || "unknown error"), "err");
    }
  } catch(err) { App.setStatus("Delete error: " + err.message, "err"); }
  finally { btn.disabled = state.busy; }
});

// ── Bootstrap ──────────────────────────────────────────────────
init();
})();
