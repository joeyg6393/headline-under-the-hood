// Headline Under The Hood — dashboard

const state = {
  reports: [],
  selectedId: null,
  filters: { search: "", source: "all", type: "all" },
  presets: [],
};

const els = {
  reportFeed: document.querySelector("#reportFeed"),
  detailPanel: document.querySelector("#detailPanel"),
  reportForm: document.querySelector("#reportForm"),
  refreshButton: document.querySelector("#refreshButton"),
  demoButton: document.querySelector("#demoButton"),
  seedButton: document.querySelector("#seedButton"),
  sheetStatus: document.querySelector("#sheetStatus"),
  releaseDate: document.querySelector("#reportForm").elements.release_date,
  reportText: document.querySelector("#reportForm").elements.report_text,
  searchInput: document.querySelector("#searchInput"),
  sourceSeg: document.querySelector("#sourceSeg"),
  typeFilter: document.querySelector("#typeFilter"),
  feedCount: document.querySelector("#feedCount"),
  statTotal: document.querySelector("#statTotal"),
  statAverage: document.querySelector("#statAverage"),
  statRisk: document.querySelector("#statRisk"),
  statLatest: document.querySelector("#statLatest"),
  statLatestSub: document.querySelector("#statLatestSub"),
  statTypes: document.querySelector("#statTypes"),
  statTypesSub: document.querySelector("#statTypesSub"),
  sparkTotal: document.querySelector("#sparkTotal"),
  sparkAvg: document.querySelector("#sparkAvg"),
  sparkRisk: document.querySelector("#sparkRisk"),
  presetButtons: document.querySelector("#presetButtons"),
  reportTypeOptions: document.querySelector("#reportTypeOptions"),
  heatmap: document.querySelector("#heatmap"),
  themeToggle: document.querySelector("#themeToggle"),
  overflowBtn: document.querySelector("#overflowBtn"),
  overflowMenu: document.querySelector("#overflowMenu"),
  openSheetBtn: document.querySelector("#openSheet"),
  fab: document.querySelector("#fab"),
  sheet: document.querySelector("#sheet"),
  sheetBackdrop: document.querySelector("#sheetBackdrop"),
};

// Form defaults
els.releaseDate.value = new Date().toISOString().slice(0, 10);
els.reportText.value = [
  "Total nonfarm payroll employment increased by 150,000 in April.",
  "Employment continued to trend up in health care and government employment.",
  "The change in total nonfarm payroll employment for February was revised down by 35,000 and the change for March was revised down by 22,000.",
  "The number of persons employed part time for economic reasons increased by 42,000.",
  "Multiple jobholders also increased by 25,000 over the month.",
  "Government employment increased by 38,000.",
  "The labor force participation rate was little changed, and the household survey showed civilian employment was roughly flat."
].join(" ");

// Theme
(function initTheme() {
  const root = document.documentElement;
  const stored = localStorage.getItem("theme");
  if (stored) root.setAttribute("data-theme", stored);
  else if (window.matchMedia("(prefers-color-scheme: dark)").matches) root.setAttribute("data-theme", "dark");
  els.themeToggle.addEventListener("click", () => {
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
  });
})();

// Overflow menu
els.overflowBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  const open = els.overflowMenu.dataset.open === "true";
  els.overflowMenu.dataset.open = open ? "false" : "true";
});
document.addEventListener("click", () => els.overflowMenu.dataset.open = "false");

// Sheet
function openSheet() { els.sheet.dataset.open = "true"; els.sheetBackdrop.dataset.open = "true"; }
function closeSheet() { els.sheet.dataset.open = "false"; els.sheetBackdrop.dataset.open = "false"; }
els.openSheetBtn.addEventListener("click", openSheet);
els.fab.addEventListener("click", openSheet);
els.sheetBackdrop.addEventListener("click", closeSheet);

// API
async function loadReports() {
  els.reportFeed.innerHTML = "<p class=\"empty\">Loading release board...</p>";
  const response = await fetch("/api/reports");
  state.reports = await response.json();
  state.reports.sort((a, b) => b.release_date.localeCompare(a.release_date) || b.id - a.id);
  if (!state.selectedId && state.reports.length) state.selectedId = state.reports[0].id;
  render();
}
async function loadPresets() {
  const response = await fetch("/api/report-presets");
  state.presets = response.ok ? await response.json() : [];
  renderPresets();
}

// Filtering
function filteredReports() {
  const search = state.filters.search.toLowerCase();
  return state.reports.filter((report) => {
    const haystack = [report.headline, report.source, report.report_type, report.release_date].join(" ").toLowerCase();
    return (
      (!search || haystack.includes(search)) &&
      (state.filters.source === "all" || report.source === state.filters.source) &&
      (state.filters.type === "all" || report.report_type === state.filters.type)
    );
  });
}

// Render orchestrator
function render() {
  renderStats();
  renderSourceSeg();
  renderTypeFilter();
  renderHeatmap();
  renderFeed();
  renderDetail();
}

// Stats
function renderStats() {
  const analyzed = state.reports.filter((r) => r.analysis);
  const avg = analyzed.length
    ? Math.round(analyzed.reduce((s, r) => s + r.analysis.score, 0) / analyzed.length)
    : null;
  const risk = analyzed.filter((r) => r.analysis.score < 75).length;
  const types = unique(state.reports.map((r) => r.report_type));
  els.statTotal.textContent = String(state.reports.length);
  els.statAverage.textContent = avg === null ? "--" : String(avg);
  els.statRisk.textContent = String(risk);
  els.statLatest.textContent = state.reports[0]?.release_date || "--";
  els.statLatestSub.textContent = state.reports[0]
    ? `${state.reports[0].report_type} · ${state.reports[0].source}` : "";
  els.statTypes.textContent = String(types.length);
  els.statTypesSub.textContent = types.slice(0, 4).map(shortType).join(" · ");

  // Sparklines from per-week aggregates of release_date over last 8 weeks
  const weekly = bucketByWeek(state.reports, 8);
  drawSpark(els.sparkTotal, weekly.map((b) => b.count));
  drawSpark(els.sparkAvg, weekly.map((b) => b.avgScore));
  drawSpark(els.sparkRisk, weekly.map((b) => b.risk));
}

function bucketByWeek(reports, weeks) {
  const today = new Date();
  const buckets = Array.from({ length: weeks }, (_, i) => {
    const start = new Date(today);
    start.setDate(today.getDate() - (weeks - 1 - i) * 7);
    return { startMs: start.getTime() - 7 * 86400000, endMs: start.getTime(), count: 0, scoreSum: 0, scored: 0, risk: 0 };
  });
  for (const r of reports) {
    const t = new Date(r.release_date + "T00:00:00").getTime();
    for (const b of buckets) {
      if (t > b.startMs && t <= b.endMs) {
        b.count += 1;
        if (r.analysis) {
          b.scoreSum += r.analysis.score;
          b.scored += 1;
          if (r.analysis.score < 75) b.risk += 1;
        }
        break;
      }
    }
  }
  return buckets.map((b) => ({ count: b.count, avgScore: b.scored ? b.scoreSum / b.scored : null, risk: b.risk }));
}

function drawSpark(svg, values) {
  if (!svg || !values || !values.length) { svg.innerHTML = ""; return; }
  const cleaned = values.map((v) => (v == null ? null : Number(v)));
  const present = cleaned.filter((v) => v != null);
  if (present.length < 2) { svg.innerHTML = ""; return; }
  const min = Math.min(...present);
  const max = Math.max(...present);
  const span = max - min || 1;
  const w = 100, h = 18, pad = 1;
  const pts = cleaned.map((v, i) => {
    const x = (i / (cleaned.length - 1)) * w;
    const y = v == null ? null : h - pad - ((v - min) / span) * (h - 2 * pad);
    return [x, y];
  }).filter((p) => p[1] != null).map((p) => p.join(",")).join(" ");
  svg.innerHTML = `<polyline fill="none" stroke="currentColor" stroke-width="1.5" points="${pts}" />`;
}

// Source segmented filter
function renderSourceSeg() {
  const sources = unique(state.reports.map((r) => r.source));
  const values = ["all", ...sources];
  els.sourceSeg.innerHTML = values.map((v) =>
    `<button type="button" data-src="${escapeHtml(v)}" aria-pressed="${state.filters.source === v}">${v === "all" ? "All" : escapeHtml(v)}</button>`
  ).join("");
}

// Type select
function renderTypeFilter() {
  const types = unique(state.reports.map((r) => r.report_type));
  setOptions(els.typeFilter, ["all", ...types], state.filters.type, "All releases");
  els.reportTypeOptions.innerHTML = types.map((t) => `<option value="${escapeHtml(t)}"></option>`).join("");
}

// Calendar heatmap (49 cells = 7 weeks * 7 days, ending today)
function renderHeatmap() {
  const today = new Date();
  const start = new Date(today);
  start.setDate(today.getDate() - 48);
  // Score by date
  const dayMap = new Map();
  for (const r of state.reports) {
    const k = r.release_date;
    const e = dayMap.get(k) || { count: 0, scoreSum: 0, scored: 0 };
    e.count += 1;
    if (r.analysis) { e.scoreSum += r.analysis.score; e.scored += 1; }
    dayMap.set(k, e);
  }
  const cells = [];
  for (let i = 0; i < 49; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    const k = d.toISOString().slice(0, 10);
    const e = dayMap.get(k);
    let bucket = "";
    if (e && e.count) {
      const avg = e.scored ? e.scoreSum / e.scored : null;
      if (avg == null) bucket = "2";
      else if (avg < 45) bucket = "1";
      else if (avg < 65) bucket = "2";
      else if (avg < 85) bucket = "3";
      else bucket = "4";
    }
    const title = e ? `${k}: ${e.count} report${e.count > 1 ? "s" : ""}${e.scored ? `, avg ${(e.scoreSum / e.scored).toFixed(0)}` : ""}` : k;
    cells.push(`<div class="cell" data-score="${bucket}" title="${title}"></div>`);
  }
  els.heatmap.innerHTML = cells.join("");
}

// Feed
function renderFeed() {
  const reports = filteredReports();
  els.feedCount.textContent = `${reports.length} ${reports.length === 1 ? "report" : "reports"}`;
  if (!reports.length) {
    els.reportFeed.innerHTML = "<p class=\"empty\">No reports match the current filters.</p>";
    return;
  }
  els.reportFeed.innerHTML = reports.map(renderReportCard).join("");
}

function renderReportCard(report) {
  const analysis = report.analysis;
  const selected = state.selectedId === report.id;
  const score = analysis ? analysis.score : null;
  const cls = scoreClass(score);
  const verdictTag = analysis ? scoreLabel(score) : "Pending";
  const ribbons = cardRibbons(analysis);
  return `
    <button class="card" data-report-id="${report.id}" aria-current="${selected}" type="button">
      <div class="card-score">
        ${gauge(score, "")}
        <span class="verdict-tag ${cls}">${escapeHtml(verdictTag)}</span>
      </div>
      <div class="card-body">
        <div class="card-meta">
          <span class="chip brand-chip">${escapeHtml(report.source)}</span>
          <span class="chip">${escapeHtml(shortType(report.report_type))}</span>
          <span>${formatDate(report.release_date)}</span>
        </div>
        <div class="card-headline">${escapeHtml(report.headline)}</div>
        <div class="card-blurb">${escapeHtml(reportBlurb(report))}</div>
        <div class="card-footer">${ribbons.map(renderRibbon).join("")}</div>
      </div>
    </button>
  `;
}

function cardRibbons(analysis) {
  if (!analysis) return [];
  const get = (keys) => keys.map((k) => analysis.metrics.find((m) => m.key === k)).find(Boolean);
  const reported = get(["reported_payroll_gain", "reported_release_read", "headline_release_read"]);
  const estimate = get(["consensus_estimate", "consensus_percent_estimate"]);
  const risk = analysis.metrics.find((m) => ["contradicting", "negative"].includes(m.direction));
  const out = [];
  if (reported) out.push({ k: "act", v: reported.value, d: reported.direction });
  if (estimate) out.push({ k: "est", v: estimate.value, d: estimate.direction });
  if (risk && risk !== reported && risk !== estimate) out.push({ k: shortMetricKey(risk.key), v: risk.value, d: risk.direction });
  return out.slice(0, 3);
}

function shortMetricKey(key) {
  const map = {
    prior_revisions: "rev",
    multiple_jobholders: "mjh",
    part_time_economic: "pt",
    household_employment: "hh",
    government_share: "gov",
    core_inflation: "core",
    shelter_costs: "shel",
    energy_prices: "engy",
    control_group: "ctrl",
    new_orders: "ord",
    employment_index: "emp",
    price_index: "px",
  };
  return map[key] || key.split("_")[0];
}

function renderRibbon(r) {
  const cls = r.d === "supporting" || r.d === "positive" ? "up"
            : r.d === "contradicting" || r.d === "negative" ? "dn"
            : "neu";
  return `<span class="ribbon ${cls}"><span style="opacity:.7">${escapeHtml(r.k)}</span> ${escapeHtml(r.v)}</span>`;
}

// Detail panel
function renderDetail() {
  const report = state.reports.find((r) => r.id === state.selectedId) || state.reports[0];
  if (!report) {
    els.detailPanel.innerHTML = "<p class=\"empty\">Select or submit a report to inspect the math.</p>";
    return;
  }
  const analysis = report.analysis;
  if (!analysis) {
    els.detailPanel.innerHTML = `
      <div class="detail-head">
        <span class="detail-eyebrow">${escapeHtml(report.source)} · ${formatDate(report.release_date)}</span>
        <h2 class="detail-headline">${escapeHtml(report.report_type)}</h2>
      </div>
      <p class="empty">Analysis is pending. Refresh shortly.</p>
    `;
    return;
  }
  const cls = scoreClass(analysis.score);
  els.detailPanel.innerHTML = `
    <div class="detail-head">
      <span class="detail-eyebrow">${escapeHtml(report.source)} · ${formatDate(report.release_date)}</span>
      <h2 class="detail-headline">${escapeHtml(report.headline)}</h2>
    </div>
    <div class="verdict-block">
      ${gauge(analysis.score, "")}
      <div>
        <h3>${escapeHtml(analysis.verdict)}</h3>
        <p>${escapeHtml(analysis.summary)}</p>
        <div class="meta">Confidence ${(analysis.confidence * 100).toFixed(0)}% · ${escapeHtml(analysis.model_used)}</div>
      </div>
    </div>
    <div class="section">
      <h4>Concrete math</h4>
      <div class="components">
        ${analysis.score_components.length ? analysis.score_components.map(renderComponent).join("") : "<p class=\"empty compact\">No score components yet.</p>"}
      </div>
    </div>
    <div class="section">
      <h4>Metric tape</h4>
      <div class="metrics">
        ${analysis.metrics.map(renderMetric).join("")}
      </div>
    </div>
    <div class="section">
      <a class="btn-primary" href="/reports/${report.id}" style="width:100%; justify-content:center;">View full analysis</a>
    </div>
  `;
}

function renderComponent(c) {
  const dir = c.points > 0 ? "pos" : c.points < 0 ? "neg" : "";
  const sign = c.points > 0 ? "+" : "";
  return `
    <div class="component ${dir}">
      <span class="label">${escapeHtml(c.label)}</span>
      <span class="pts">${sign}${c.points}</span>
      ${c.math ? `<code class="math">${escapeHtml(c.math)}</code>` : ""}
      ${c.evidence ? `<p class="ev">${escapeHtml(c.evidence)}</p>` : ""}
    </div>
  `;
}

function renderMetric(m) {
  const cls = directionClass(m.direction);
  return `
    <div class="metric ${cls}">
      <div>
        <div class="name">${escapeHtml(m.name)}</div>
        <div class="desc">${escapeHtml(m.interpretation || "")}</div>
      </div>
      <div style="text-align:right">
        <div class="value">${escapeHtml(m.value)}</div>
        <div class="source">${escapeHtml(m.math || m.source || m.unit || "")}</div>
      </div>
    </div>
  `;
}

// Presets
function renderPresets() {
  if (!state.presets.length) { els.presetButtons.innerHTML = ""; return; }
  els.presetButtons.innerHTML = state.presets.slice(0, 8).map((preset, i) =>
    `<button type="button" data-preset-index="${i}">${escapeHtml(shortType(preset.report_type))}</button>`
  ).join("");
}

// Gauge SVG
function gauge(score, sizeClass) {
  const cls = scoreClass(score);
  const value = score == null ? 0 : Math.max(0, Math.min(100, Number(score)));
  const display = score == null ? "--" : String(score);
  return `
    <div class="gauge ${cls} ${sizeClass}" aria-label="Score ${display} of 100">
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle class="track" cx="50" cy="50" r="42"/>
        <line class="tick" x1="50" y1="4" x2="50" y2="10" transform="rotate(162 50 50)"/>
        <line class="tick" x1="50" y1="4" x2="50" y2="10" transform="rotate(270 50 50)"/>
        <circle class="fill" cx="50" cy="50" r="42" pathLength="100" stroke-dasharray="${value} 100"/>
      </svg>
      <div class="num">${display}</div>
    </div>
  `;
}

// Helpers
function scoreClass(s) {
  if (s == null) return "";
  if (s >= 75) return "s-good";
  if (s >= 45) return "s-mid";
  return "s-bad";
}
function scoreLabel(s) {
  if (s == null) return "Pending";
  if (s >= 75) return "Strong";
  if (s >= 45) return "Mixed";
  return "Weak";
}
function directionClass(d) {
  if (d === "supporting" || d === "positive" || d === "pos") return "pos";
  if (d === "contradicting" || d === "negative" || d === "neg") return "neg";
  return "";
}
function reportBlurb(report) {
  const a = report.analysis;
  if (!a) return "Analysis is queued; refresh shortly.";
  return a.summary || a.verdict || "";
}
function shortType(type) {
  const m = {
    "Nonfarm Payrolls": "NFP",
    "Consumer Price Index": "CPI",
    "Producer Price Index": "PPI",
    "PCE Price Index": "PCE",
    "ADP Employment": "ADP",
    "Gross Domestic Product": "GDP",
    "Initial Jobless Claims": "Claims",
    "Fed Rate Decision": "FOMC",
    "Retail Sales": "Retail",
    "ISM Manufacturing": "ISM-M",
    "ISM Services": "ISM-S",
  };
  return m[type] || type;
}
function setOptions(select, values, selected, allLabel) {
  select.innerHTML = values.map((v) =>
    `<option value="${escapeHtml(v)}">${v === "all" ? allLabel : escapeHtml(v)}</option>`
  ).join("");
  select.value = values.includes(selected) ? selected : "all";
}
function unique(values) {
  return [...new Set(values.filter(Boolean))].sort().reverse();
}
function formatDate(date) {
  const [y, m, d] = date.split("-");
  return `${m}/${d}/${y}`;
}
function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

// Events
els.reportForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  els.sheetStatus.textContent = "Submitting…";
  const payload = Object.fromEntries(new FormData(els.reportForm).entries());
  const response = await fetch("/api/reports", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
  });
  if (!response.ok) { els.sheetStatus.textContent = "Failed"; return; }
  const report = await response.json();
  state.selectedId = report.id;
  els.sheetStatus.textContent = "Submitted";
  await loadReports();
  setTimeout(closeSheet, 600);
});

els.refreshButton.addEventListener("click", loadReports);
els.demoButton.addEventListener("click", async () => {
  els.sheetStatus.textContent = "Running demo…";
  const r = await fetch("/api/reports/demo", { method: "POST" });
  const report = await r.json();
  state.selectedId = report.id;
  await loadReports();
});
els.seedButton.addEventListener("click", async () => {
  els.sheetStatus.textContent = "Seeding…";
  const r = await fetch("/api/reports/demo-set", { method: "POST" });
  const reports = await r.json();
  state.selectedId = reports[0]?.id || state.selectedId;
  await loadReports();
});

els.searchInput.addEventListener("input", (e) => {
  state.filters.search = e.target.value;
  renderFeed();
});
els.sourceSeg.addEventListener("click", (e) => {
  const b = e.target.closest("button[data-src]");
  if (!b) return;
  state.filters.source = b.dataset.src;
  renderSourceSeg();
  renderFeed();
});
els.typeFilter.addEventListener("change", (e) => {
  state.filters.type = e.target.value;
  renderFeed();
});
els.reportFeed.addEventListener("click", (e) => {
  const card = e.target.closest("[data-report-id]");
  if (!card) return;
  state.selectedId = Number(card.dataset.reportId);
  document.querySelectorAll(".card").forEach((c) => c.setAttribute("aria-current", "false"));
  card.setAttribute("aria-current", "true");
  renderDetail();
});
els.presetButtons.addEventListener("click", (e) => {
  const b = e.target.closest("[data-preset-index]");
  if (!b) return;
  const p = state.presets[Number(b.dataset.presetIndex)];
  if (!p) return;
  els.reportForm.elements.source.value = p.source;
  els.reportForm.elements.report_type.value = p.report_type;
  els.reportForm.elements.headline.value = p.headline;
  els.reportForm.elements.report_text.value = p.report_text;
});

loadPresets();
loadReports();
