"use strict";
/* =============================================================
   Solver interaction & result rendering (classical, quantum,
   histogram).
   ============================================================= */

(function () {
const { state, $,
        elHistSvg, elHistTip, elQuPlaceholder, elClPlaceholder,
        elQuList, elBtnBench, elThresholdInput,
       } = App;

const MAX_DISPLAY = 30;
let _histGeom = null;

// ── Helpers ────────────────────────────────────────────────────
function clearSolverResults() {
  const clEl = $("cl-canvas");
  Array.from(clEl.children).forEach(c => { if (c.id !== "cl-placeholder") c.remove(); });
  elClPlaceholder.style.display = "";
  elClPlaceholder.textContent = "Running\u2026";

  const quSolPh = $("qu-sol-placeholder");
  elQuList.innerHTML = "";
  if (quSolPh) { elQuList.appendChild(quSolPh); quSolPh.textContent = "Running\u2026"; }

  elHistSvg.innerHTML = "";
  state.histData = null;
  state.trialCounts = null;
  state.trialIdx = 0;
  const oldNav = $("trial-nav");
  if (oldNav) oldNav.remove();
  elQuPlaceholder.style.display = "";

  clearMetrics();
}

// ── Classical result renderer ──────────────────────────────────
function renderClassical({ solutions, rows, cols }) {
  const el = $("cl-canvas");
  Array.from(el.children).forEach(child => {
    if (child.id !== "cl-placeholder") child.remove();
  });

  if (!solutions || solutions.length === 0) {
    elClPlaceholder.style.display = "";
    elClPlaceholder.textContent = solutions
      ? "No solutions found."
      : "Run \u25b6\u00a0Solve to see classical solutions.";
    return;
  }

  elClPlaceholder.style.display = "none";

  solutions.forEach((bs, idx) => {
    const wrap = document.createElement("div");
    wrap.className = "sol-grid-wrap";
    const lbl = document.createElement("div");
    lbl.className = "sol-grid-label";
    lbl.textContent = solutions.length > 1 ? `Solution ${idx + 1}` : "Solution";
    wrap.appendChild(lbl);
    const tbl = document.createElement("table");
    tbl.className = "sol-table sz-" + state.clSize;
    for (let r = 0; r < rows; r++) {
      const tr = tbl.insertRow();
      for (let c = 0; c < cols; c++) {
        const td = tr.insertCell();
        td.className = bs[r * cols + c] === "1" ? "f" : "e";
      }
    }
    wrap.appendChild(tbl);
    el.appendChild(wrap);
  });
}

// ── Quantum histogram & solutions ──────────────────────────────
function computeThreshold(rows, cols) {
  const numVars = rows * cols;
  const baseline = 1.0 / Math.pow(2, numVars);
  return Math.max(3.0 * baseline, 0.005);
}

function renderQuantum(counts, rows, cols) {
  if (!counts || Object.keys(counts).length === 0) {
    drawEmptyHistogram();
    return;
  }
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  let entries = Object.entries(counts).map(([bs, cnt]) =>
    [bs, total > 0 ? cnt / total : 0]);
  entries.sort((a, b) => b[1] - a[1]);
  const totalOutcomes = entries.length;
  entries = entries.slice(0, MAX_DISPLAY);

  // Use the user's saved threshold if available, otherwise compute baseline
  const threshold = state.userThreshold != null
    ? state.userThreshold
    : computeThreshold(rows, cols);

  state.histData = { entries, threshold, rows, cols, totalOutcomes };
  elQuPlaceholder.style.display = "none";

  const pctVal = threshold * 100;
  const pctStr = pctVal.toFixed(pctVal < 1 ? 2 : 1);
  elThresholdInput.value = pctStr;

  drawHistogram(state.histData);
  renderQuantumList();
}

function drawEmptyHistogram() {
  var cs = getComputedStyle(document.documentElement);
  var borderColor = cs.getPropertyValue('--border').trim();
  var textMuted = cs.getPropertyValue('--text-muted').trim();
  var textSecondary = cs.getPropertyValue('--text-secondary').trim();
  const svg    = elHistSvg;
  const parent = svg.parentElement;
  const W = parent.clientWidth  || 400;
  const H = parent.clientHeight || 300;
  const P = { t: 20, r: 12, b: 44, l: 50 };
  const cW = W - P.l - P.r, cH = H - P.t - P.b;
  const GHOST = [0.52, 0.79, 0.61, 0.35, 0.90, 0.44, 0.28, 0.67];
  const n = GHOST.length, slot = cW / n;
  const bW = Math.max(4, Math.min(36, slot * 0.70));
  let s = `<g transform="translate(${P.l},${P.t})">`;
  for (const step of [0, 25, 50, 75, 100]) {
    const y = (cH * (1 - step / 100)).toFixed(1);
    s += `<line x1="0" y1="${y}" x2="${cW}" y2="${y}" stroke="${borderColor}" stroke-width="1"/>`;
    s += `<text x="-4" y="${y}" text-anchor="end" dominant-baseline="middle"
      font-family="Helvetica,Arial,sans-serif" font-size="8" fill="${textMuted}">${step}%</text>`;
  }
  for (let i = 0; i < n; i++) {
    const h  = (GHOST[i] * cH).toFixed(1);
    const bx = (i * slot + (slot - bW) / 2).toFixed(1);
    s += `<rect x="${bx}" y="${(cH - GHOST[i] * cH).toFixed(1)}"
      width="${bW.toFixed(1)}" height="${h}" fill="rgba(0,0,0,0.07)" rx="0"/>`;
  }
  s += `<line x1="0" y1="0" x2="0" y2="${cH}" stroke="${borderColor}" stroke-width="1"/>`;
  s += `<line x1="0" y1="${cH}" x2="${cW}" y2="${cH}" stroke="${borderColor}" stroke-width="1"/>`;
  s += `<text x="${(cW / 2).toFixed(1)}" y="${(cH + P.b - 6).toFixed(1)}"
    text-anchor="middle" font-family="Helvetica,Arial,sans-serif"
    font-size="9" fill="${textSecondary}">Draw cells \u2014 histogram appears automatically</text>`;
  s += `</g>`;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = s;
  elQuPlaceholder.style.display = "none";
}


function fp(p) {
  const v = p * 100;
  if (v === 0)  return "0%";
  if (v < 0.1)  return v.toFixed(3) + "%";
  if (v < 1.0)  return v.toFixed(2) + "%";
  if (v < 10)   return v.toFixed(1) + "%";
  return Math.round(v) + "%";
}


function drawHistogram({ entries, threshold, rows, cols, totalOutcomes }) {
  var cs = getComputedStyle(document.documentElement);
  var borderColor = cs.getPropertyValue('--border').trim();
  var textMuted = cs.getPropertyValue('--text-muted').trim();
  var textSecondary = cs.getPropertyValue('--text-secondary').trim();
  const svg    = elHistSvg;
  const parent = svg.parentElement;
  const W = parent.clientWidth  || 400;
  const H = parent.clientHeight || 300;
  const P = { t: 20, r: 12, b: 44, l: 50 };
  const cW = W - P.l - P.r, cH = H - P.t - P.b;

  const n       = entries.length;
  if (n === 0) { drawEmptyHistogram(); return; }
  const maxProb = entries[0][1];
  const slot    = cW / n;
  const bW      = Math.max(4, Math.min(44, slot * 0.72));

  const C_ABOVE = cs.getPropertyValue('--syntax-keyword').trim() || "#8e44ad";
  const C_BELOW = cs.getPropertyValue('--text-secondary').trim() || "#b0bec5";
  const C_THR = cs.getPropertyValue('--accent').trim() || "#e65100";
  const FONT    = "Helvetica,Arial,sans-serif";

  let s = `<g transform="translate(${P.l},${P.t})">`;

  for (const step of [0, 25, 50, 75, 100]) {
    const p = maxProb * step / 100;
    const y = (cH - (p / maxProb) * cH).toFixed(1);
    s += `<line x1="0" y1="${y}" x2="${cW}" y2="${y}" stroke="${borderColor}" stroke-width="1"/>`;
    s += `<text x="-4" y="${y}" text-anchor="end" dominant-baseline="middle"
      font-family="${FONT}" font-size="8" fill="${textMuted}">${fp(p)}</text>`;
  }

  for (let i = 0; i < n; i++) {
    const [bs, prob] = entries[i];
    const above = prob >= threshold;
    const bH  = Math.max(1, (prob / maxProb) * cH);
    const bx  = (i * slot + (slot - bW) / 2).toFixed(1);
    const by  = (cH - bH).toFixed(1);
    const fill = above ? C_ABOVE : C_BELOW;
    s += `<rect class="hbar" x="${bx}" y="${by}" width="${bW.toFixed(1)}" height="${bH.toFixed(1)}"
      fill="${fill}" rx="0" data-bs="${bs}" data-prob="${prob}" data-above="${above}"/>`;
    if (bH > 16)
      s += `<text x="${(+bx + bW / 2).toFixed(1)}" y="${(+by - 3).toFixed(1)}"
        text-anchor="middle" font-family="${FONT}" font-size="7" fill="${fill}">${fp(prob)}</text>`;
    const lx = (+bx + bW / 2).toFixed(1);
    const fs = Math.max(6, Math.min(9, slot * 0.55)).toFixed(1);
    s += `<text x="${lx}" y="${(cH + 5).toFixed(1)}"
      text-anchor="end" font-family="${FONT}" font-size="${fs}" fill="${textSecondary}"
      transform="rotate(-45,${lx},${(cH + 5).toFixed(1)})">${bs}</text>`;
  }

  if (threshold > 0 && threshold <= maxProb) {
    const ty = (cH - (threshold / maxProb) * cH).toFixed(1);
    s += `<line x1="0" y1="${ty}" x2="${cW}" y2="${ty}"
      stroke="${C_THR}" stroke-width="1.5" stroke-dasharray="6,3"/>`;
    s += `<rect class="thr-drag" x="0" y="${(+ty - 8).toFixed(1)}"
      width="${cW}" height="16" fill="transparent" style="cursor:ns-resize"/>`;
    s += `<text x="${(cW - 2).toFixed(1)}" y="${(+ty - 4).toFixed(1)}"
      text-anchor="end" font-family="${FONT}" font-size="8" font-weight="bold"
      fill="${C_THR}">threshold</text>`;
  }

  s += `<line x1="0" y1="0" x2="0" y2="${cH}" stroke="${textSecondary}" stroke-width="1"/>`;
  s += `<line x1="0" y1="${cH}" x2="${cW}" y2="${cH}" stroke="${textSecondary}" stroke-width="1"/>`;

  const lbl = totalOutcomes > n ? `top ${n} of ${totalOutcomes}` : String(n);
  s += `<text x="${(cW / 2).toFixed(1)}" y="${(cH + P.b - 5).toFixed(1)}"
    text-anchor="middle" font-family="${FONT}" font-size="8" fill="${textSecondary}">
    ${lbl} outcome${n !== 1 ? "s" : ""} \u2014 hover a bar \u00b7 drag threshold line</text>`;

  s += `</g>`;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = s;
  elQuPlaceholder.style.display = "none";

  _histGeom = { P, cH, maxProb, W, H };

  // Threshold drag handler
  const thrDrag = svg.querySelector(".thr-drag");
  if (thrDrag) {
    thrDrag.addEventListener("mousedown", e => {
      e.preventDefault();
      const svgRect = svg.getBoundingClientRect();
      const scaleY  = H / svgRect.height;
      const onMove = me => {
        const svgY   = (me.clientY - svgRect.top) * scaleY;
        const chartY = svgY - P.t;
        const ratio  = Math.max(0, Math.min(1, 1 - chartY / cH));
        const newThr = ratio * maxProb;
        state.histData.threshold = newThr;
        state.userThreshold = newThr;
        const pct = newThr * 100;
        elThresholdInput.value = pct.toFixed(pct < 1 ? 2 : 1);
        drawHistogram(state.histData);
        renderQuantumList();
      };
      const onUp = () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      };
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    });
  }

  // Hover tooltip
  svg.querySelectorAll(".hbar").forEach(rect => {
    rect.addEventListener("mouseenter", e => {
      const bs    = rect.dataset.bs;
      const prob  = parseFloat(rect.dataset.prob);
      const above = rect.dataset.above === "true";
      const { rows: R, cols: C } = state.histData;
      elHistTip.innerHTML = "";
      var tipCs = getComputedStyle(document.documentElement);
      var tipAboveColor = tipCs.getPropertyValue('--syntax-keyword').trim() || "#8e44ad";
      var tipMutedColor = tipCs.getPropertyValue('--text-muted').trim() || "#555";
      var tipBorderColor = tipCs.getPropertyValue('--border').trim() || "#9aabb8";
      var tipFilledColor = tipCs.getPropertyValue('--surface2').trim() || "#2d3e50";
      var tipEmptyColor = tipCs.getPropertyValue('--surface').trim() || "#f0f0ea";
      const head = document.createElement("div");
      head.style.cssText = `text-align:center;font-weight:bold;margin-bottom:4px;
        color:${above ? tipAboveColor : tipMutedColor};font-size:11px;`;
      head.textContent = fp(prob);
      elHistTip.appendChild(head);
      const bsRev = bs.split("").reverse().join("");
      const tbl = document.createElement("table");
      tbl.style.cssText = "border-collapse:collapse;margin:0 auto;";
      for (let r = 0; r < R; r++) {
        const tr = tbl.insertRow();
        for (let c = 0; c < C; c++) {
          const td = tr.insertCell();
          td.style.cssText = `width:10px;height:10px;border:1px solid ${tipBorderColor};
            background:${bsRev[r * C + c] === "1" ? tipFilledColor : tipEmptyColor};`;
        }
      }
      elHistTip.appendChild(tbl);
      const tipW = 96, tipH = 24 + R * 13;
      let sx = e.clientX + 14, sy = e.clientY - tipH - 6;
      if (sx + tipW > window.innerWidth) sx = e.clientX - tipW - 10;
      if (sy < 0) sy = e.clientY + 14;
      elHistTip.style.left = sx + "px";
      elHistTip.style.top  = sy + "px";
      elHistTip.style.display = "block";
    });
    rect.addEventListener("mouseleave", () => { elHistTip.style.display = "none"; });
  });
}

// ── Quantum solutions list renderer ───────────────────────────
function renderQuantumList() {
  elQuList.innerHTML = "";
  const quSolPh = $("qu-sol-placeholder");

  if (!state.histData) {
    if (quSolPh) { elQuList.appendChild(quSolPh); quSolPh.textContent = "Run Benchmark to see solutions."; }
    return;
  }

  const { entries, threshold, rows, cols } = state.histData;
  const above = entries.filter(([, prob]) => prob >= threshold);

  if (above.length === 0) {
    if (quSolPh) { elQuList.appendChild(quSolPh); quSolPh.textContent = "No solutions above threshold."; }
    return;
  }

  above.forEach(([bs, prob]) => {
    const bsGrid = bs.split("").reverse().join("");
    const wrap = document.createElement("div");
    wrap.className = "sol-grid-wrap";

    const lbl = document.createElement("div");
    lbl.className = "sol-grid-label";
    lbl.textContent = (prob * 100).toFixed(1) + "%";
    wrap.appendChild(lbl);

    const tbl = document.createElement("table");
    tbl.className = "sol-table sz-" + state.quSize;
    for (let r = 0; r < rows; r++) {
      const tr = tbl.insertRow();
      for (let c = 0; c < cols; c++) {
        const td = tr.insertCell();
        td.className = bsGrid[r * cols + c] === "1" ? "f" : "e";
      }
    }
    wrap.appendChild(tbl);
    elQuList.appendChild(wrap);
  });
}

// ── Trial navigation (multi-trial histogram) ───────────────────
function renderTrialNav(rows, cols) {
  const counts = state.trialCounts;
  if (!counts || counts.length <= 1) return;

  let nav = $("trial-nav");
  if (!nav) {
    nav = document.createElement("div");
    nav.id = "trial-nav";
    nav.className = "trial-nav";
    const quArea = $("qu-area");
    quArea.parentElement.insertBefore(nav, quArea);
  }

  nav.innerHTML = "";
  const prevBtn = document.createElement("button");
  prevBtn.className = "trial-nav-btn";
  prevBtn.textContent = "◀";
  prevBtn.title = "Previous trial";

  const label = document.createElement("span");
  label.className = "trial-nav-label";
  label.id = "trial-nav-label";
  label.textContent = `Trial ${state.trialIdx + 1} / ${counts.length}`;

  const nextBtn = document.createElement("button");
  nextBtn.className = "trial-nav-btn";
  nextBtn.textContent = "▶";
  nextBtn.title = "Next trial";

  prevBtn.addEventListener("click", () => {
    state.trialIdx = (state.trialIdx - 1 + counts.length) % counts.length;
    renderQuantum(counts[state.trialIdx], rows, cols);
    document.getElementById("trial-nav-label").textContent =
      `Trial ${state.trialIdx + 1} / ${counts.length}`;
  });
  nextBtn.addEventListener("click", () => {
    state.trialIdx = (state.trialIdx + 1) % counts.length;
    renderQuantum(counts[state.trialIdx], rows, cols);
    document.getElementById("trial-nav-label").textContent =
      `Trial ${state.trialIdx + 1} / ${counts.length}`;
  });

  // Tab buttons for each trial
  const tabs = document.createElement("div");
  tabs.className = "trial-tabs";
  counts.forEach((_, i) => {
    const btn = document.createElement("button");
    btn.className = "trial-tab" + (i === state.trialIdx ? " active" : "");
    btn.textContent = i + 1;
    btn.title = `Trial ${i + 1}`;
    btn.addEventListener("click", () => {
      state.trialIdx = i;
      renderQuantum(counts[state.trialIdx], rows, cols);
      document.getElementById("trial-nav-label").textContent =
        `Trial ${state.trialIdx + 1} / ${counts.length}`;
      tabs.querySelectorAll(".trial-tab").forEach((b, j) =>
        b.classList.toggle("active", j === state.trialIdx));
    });
    tabs.appendChild(btn);
  });

  nav.appendChild(prevBtn);
  nav.appendChild(label);
  nav.appendChild(tabs);
  nav.appendChild(nextBtn);
}

// ── Metrics renderer ────────────────────────────────────────────
function clearMetrics() {
  const el = $("metrics-pane");
  el.innerHTML = "";
  el.classList.remove("visible");
}

function renderMetrics(report, cl_times, qu_times) {
  const el = $("metrics-pane");
  el.innerHTML = "";

  const cl = report?.classical;
  const qu = report?.quantum;
  const numVars = report?.num_variables;

  const tbl = document.createElement("table");
  tbl.className = "ui-table-sticky";

  const thead = tbl.createTHead();
  const hr = thead.insertRow();
  for (const h of ["Metric", "Classical", "Quantum"]) {
    const th = document.createElement("th"); th.textContent = h; hr.appendChild(th);
  }

  const tbody = tbl.createTBody();

  function row(label, cv, qv) {
    const tr = tbody.insertRow();
    const tdL = tr.insertCell(); tdL.className = "metric-label"; tdL.textContent = label;
    const tdC = tr.insertCell(); tdC.textContent = cv;
    const tdQ = tr.insertCell(); tdQ.textContent = qv;
  }

  function fmtTime(t) {
    if (t == null) return "\u2014";
    return t < 1 ? (t * 1000).toFixed(1) + " ms" : t.toFixed(3) + " s";
  }
  function fmtAvg(times) {
    if (!times || !times.length) return "\u2014";
    const avg = times.reduce((a, b) => a + b) / times.length;
    let s = fmtTime(avg);
    if (times.length >= 2) {
      const mean = avg;
      const sd = Math.sqrt(times.reduce((a, b) => a + (b - mean) ** 2, 0) / (times.length - 1));
      s += ` \u00b1 ${fmtTime(sd)}`;
    }
    return s;
  }

  row("Variables", numVars ?? "\u2014", numVars ?? "\u2014");
  row("Search space", numVars != null ? (2 ** numVars).toLocaleString() : "\u2014",
      numVars != null ? (2 ** numVars).toLocaleString() : "\u2014");
  row("Solve time", fmtAvg(cl_times), fmtAvg(qu_times));
  row("Solutions found", cl?.solutions_found ?? "\u2014", qu?.solutions_found ?? "\u2014");
  row("Qubits", "\u2014", qu?.num_qubits ?? "\u2014");
  row("Circuit depth", "\u2014", qu?.circuit_depth?.toLocaleString() ?? "\u2014");
  row("Grover iterations", "\u2014", qu?.grover_iterations ?? "\u2014");
  row("Top probability", "\u2014",
      qu?.top_result_probability != null ? (qu.top_result_probability * 100).toFixed(1) + "%" : "\u2014");
  row("Peak memory",
      cl?.peak_memory_kb != null ? cl.peak_memory_kb.toFixed(1) + " KB" : "\u2014",
      qu?.peak_memory_kb != null ? qu.peak_memory_kb.toFixed(1) + " KB" : "\u2014");

  el.appendChild(tbl);
  el.classList.add("visible");
}

// ── Benchmark result renderer ──────────────────────────────────
function renderBenchmark({ report, solutions, qu_counts, qu_counts_per_trial, rows, cols, cl_times, qu_times }) {
  const bestSz = App.getBestSolSize(rows, cols);
  state.clSize = state.quSize = bestSz;
  document.querySelectorAll("#sol-size-toggle .sol-size-btn").forEach(b => {
    b.classList.toggle("active", b.dataset.size === bestSz);
  });

  // Set up per-trial counts and reset to last trial
  state.trialCounts = qu_counts_per_trial || null;
  state.trialIdx = qu_counts_per_trial ? qu_counts_per_trial.length - 1 : 0;

  renderClassical({ solutions, rows, cols });
  renderQuantum(qu_counts, rows, cols);
  if (state.trialCounts) renderTrialNav(rows, cols);
  renderMetrics(report, cl_times, qu_times);
}

// Export to namespace
Object.assign(App, {
  clearSolverResults, renderClassical, renderQuantum,
  renderBenchmark, renderMetrics, renderTrialNav,
  drawEmptyHistogram, drawHistogram, renderQuantumList,
});
})();
