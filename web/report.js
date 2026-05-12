// Headline Under The Hood — full report page

// Theme
(function initTheme() {
  const root = document.documentElement;
  const stored = localStorage.getItem("theme");
  if (stored) root.setAttribute("data-theme", stored);
  else if (window.matchMedia("(prefers-color-scheme: dark)").matches) root.setAttribute("data-theme", "dark");
  document.querySelector("#themeToggle").addEventListener("click", () => {
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
  });
})();

const fullReport = document.querySelector("#fullReport");

async function loadReport() {
  const reportId = window.location.pathname.split("/").filter(Boolean).pop();
  const response = await fetch(`/api/reports/${reportId}`);
  if (!response.ok) {
    document.title = "Report not found";
    fullReport.innerHTML = "<section class=\"pane section-pad\"><p class=\"empty\">The requested report could not be loaded.</p></section>";
    return;
  }
  const report = await response.json();
  document.title = `${report.report_type} · Headline Under The Hood`;
  renderReport(report);
}

function renderReport(report) {
  const a = report.analysis;
  if (!a) {
    fullReport.innerHTML = `
      <section class="pane hero">
        <div>
          <div class="eyebrow">
            <span class="chip brand-chip">${escapeHtml(report.source)}</span>
            <span>${formatDate(report.release_date)}</span>
            <span class="chip status pending">Pending</span>
          </div>
          <h1 class="headline">${escapeHtml(report.headline)}</h1>
          <p class="verdict-line"><strong>Analysis is queued.</strong> Return to the board and refresh shortly.</p>
        </div>
      </section>
    `;
    return;
  }

  fullReport.innerHTML = `
    ${renderHero(report, a)}
    ${renderComparison(report, a)}
    ${renderClaimsPane(a)}
    ${renderRevisionWatch(a)}
    ${renderCompositionPane(a)}
    ${renderScorecardPane(a)}
    ${renderWaterfall(a)}
    <div class="row-2">
      ${renderTonePane(a)}
      ${renderProbabilityPane(a)}
    </div>
    ${renderCoveragePane(a)}
    <div class="row-2">
      ${renderComponentsPane(a)}
      ${renderMetricsPane(a)}
    </div>
    <div class="row-2">
      ${renderFactorsPane("Supports the headline", a.supporting_factors, "var(--good)", "pos")}
      ${renderFactorsPane("Under the hood", a.contradicting_factors, "var(--bad)", "neg")}
    </div>
    ${renderCitationsPane(a)}
  `;
}

function renderHero(report, a) {
  const cls = scoreClass(a.score);
  return `
    <section class="pane hero">
      <div>
        <div class="eyebrow">
          <span class="chip brand-chip">${escapeHtml(report.source)}</span>
          <span class="chip">${escapeHtml(shortType(report.report_type))}</span>
          <span>${escapeHtml(report.report_type)}</span>
          <span>·</span>
          <span>${formatDate(report.release_date)}</span>
          <span>·</span>
          <span class="chip status">${escapeHtml(report.status)}</span>
        </div>
        <h1 class="headline">"${escapeHtml(report.headline)}"</h1>
        <p class="verdict-line"><strong>${escapeHtml(a.verdict)}.</strong> ${escapeHtml(a.summary)}</p>
        <div class="meta-row">
          <span><strong style="color:var(--text); font-weight:700">Confidence ${(a.confidence * 100).toFixed(0)}%</strong></span>
          <span class="dot"></span>
          <span>Model: <code>${escapeHtml(a.model_used)}</code></span>
          <span class="dot"></span>
          <span>${a.score_components.length} component${a.score_components.length === 1 ? "" : "s"} against ${a.metrics.length} metric${a.metrics.length === 1 ? "" : "s"}</span>
        </div>
      </div>
      <div>
        ${gauge(a.score, "large")}
        <div style="text-align:center; font-size:10px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin-top:14px;">/ 100 · ${escapeHtml(scoreLabel(a.score).toLowerCase())}</div>
      </div>
    </section>
  `;
}

function renderComparison(report, a) {
  const supports = (a.supporting_factors || []).slice(0, 6);
  const contradicts = (a.contradicting_factors || []).slice(0, 6);
  const positiveComponents = (a.score_components || []).filter((c) => c.points > 0);
  const negativeComponents = (a.score_components || []).filter((c) => c.points < 0);

  const leftPieces = [
    ...positiveComponents.slice(0, 3).map((c) => ({
      ico: "✓", cls: "match",
      label: c.label,
      val: `+${c.points}`,
    })),
    ...negativeComponents.slice(0, 2).map((c) => ({
      ico: "!", cls: c.points <= -10 ? "miss" : "warn",
      label: omissionLabel(c.label),
      val: `${c.points}`,
    })),
  ];

  const rightPieces = (a.metrics || []).filter((m) => ["contradicting", "negative"].includes(m.direction)).slice(0, 4).map((m) => ({
    ico: "!", cls: "miss",
    label: m.name,
    val: m.value,
  }));
  const supportingMetrics = (a.metrics || []).filter((m) => ["supporting", "positive"].includes(m.direction)).slice(0, 3 - rightPieces.length).map((m) => ({
    ico: "✓", cls: "match",
    label: m.name,
    val: m.value,
  }));
  const rightAll = [...supportingMetrics, ...rightPieces];

  // Build the right body — concat citations into one quoted excerpt with marks
  const citations = a.citations || [];
  const rightBody = citations.length
    ? citations.slice(0, 3).map((c) => escapeHtml(c.excerpt)).join(" ")
    : (contradicts[0] ? escapeHtml(contradicts[0]) : "No release excerpts captured.");

  return `
    <section class="pane compare">
      <h2>What the headline said vs. what the release actually says</h2>
      <p class="sub">The deterministic scorer parses the headline into atomic claims, matches each against the release text, and weights matches, omissions, and contradictions.</p>
      <div class="compare-grid">
        <div class="quote-card left">
          <div class="label">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M12 20l9-14H3z"/></svg>
            The headline
          </div>
          <p class="body">"${escapeHtml(report.headline)}"</p>
          ${supports.length ? `<p class="body" style="font-size:12.5px; color:var(--text-2);">${escapeHtml(supports[0])}</p>` : ""}
          <div class="pieces">
            ${leftPieces.map(renderPiece).join("") || "<p class=\"empty compact\">No structured claims detected.</p>"}
          </div>
        </div>
        <div class="quote-card right">
          <div class="label">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/></svg>
            The actual ${escapeHtml(report.source)} release
          </div>
          <p class="body">${rightBody}</p>
          <div class="pieces">
            ${rightAll.map(renderPiece).join("") || "<p class=\"empty compact\">No structured metrics extracted.</p>"}
          </div>
        </div>
      </div>
      <div class="ai-footer">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5z"/><path d="M19 13l.7 2.3L22 16l-2.3.7L19 19l-.7-2.3L16 16l2.3-.7z"/></svg>
        <span>The deterministic scorer owns the score and math; ${escapeHtml(a.model_used)} produces the supporting prose.</span>
      </div>
    </section>
  `;
}

function omissionLabel(label) {
  // Soften phrasing for "miss" pieces on the headline side
  const l = label.toLowerCase();
  if (l.includes("revis"))   return "No mention of revisions";
  if (l.includes("part-time") || l.includes("part time"))   return "No mention of part-time spike";
  if (l.includes("multiple jobholder")) return "No mention of multiple jobholders";
  if (l.includes("government")) return "No mention of government share";
  if (l.includes("household"))  return "No mention of household-survey divergence";
  if (l.includes("shelter"))    return "No mention of shelter cost driver";
  if (l.includes("energy"))     return "No mention of energy contribution";
  if (l.includes("control"))    return "No mention of control-group detail";
  if (l.includes("inventory"))  return "No mention of inventory drawdown";
  return label;
}

function renderPiece(p) {
  return `
    <div class="piece ${p.cls}">
      <span class="ico">${escapeHtml(p.ico)}</span>
      <span>${escapeHtml(p.label)}</span>
      <span class="val">${escapeHtml(p.val)}</span>
    </div>
  `;
}

// Scorecard tiles
function renderScorecardPane(a) {
  const tiles = scorecardTiles(a);
  return `
    <section class="pane scorecard">
      <h2>Scorecard · the numbers behind the verdict</h2>
      <div class="tiles">
        ${tiles.map(renderTile).join("")}
      </div>
    </section>
  `;
}

function renderTile(t) {
  const cls = directionClass(t.direction);
  return `
    <div class="tile ${cls}">
      <span class="k">${escapeHtml(t.name)}</span>
      <span class="v">${escapeHtml(t.value)}</span>
    </div>
  `;
}

function scorecardTiles(a) {
  if (!a) {
    return [
      { name: "Status", value: "Pending" }, { name: "Score", value: "--" },
      { name: "Headline", value: "--" }, { name: "Reported", value: "--" },
      { name: "Estimate", value: "--" }, { name: "Key read", value: "--" },
    ];
  }
  const get = (keys) => keys.map((k) => a.metrics.find((m) => m.key === k)).find(Boolean);
  const headline = get(["headline_payroll_claim", "headline_release_read"]);
  const reported = get(["reported_payroll_gain", "reported_release_read"]);
  const estimate = get(["consensus_estimate", "consensus_percent_estimate"]);
  const keyRead = get(["revision_adjusted_headline", "prior_revisions", "core_inflation", "control_group", "new_orders", "government_share", "price_index"]);
  const caveat = get(["multiple_jobholders", "part_time_economic", "household_employment", "shelter_costs", "energy_prices", "temporary_help", "employment_index"]) || (a.metrics || []).find((m) => ["contradicting", "negative"].includes(m.direction));
  return [
    { name: "Score", value: String(a.score), direction: scoreDir(a.score) },
    tileFromMetric("Headline", headline),
    tileFromMetric("Reported", reported),
    tileFromMetric("Estimate", estimate),
    tileFromMetric("Key read", keyRead),
    tileFromMetric("Caveat", caveat),
  ];
}
function tileFromMetric(name, m) {
  if (!m) return { name, value: "--", direction: "" };
  return { name, value: m.value, direction: m.direction };
}
function scoreDir(s) {
  if (s >= 75) return "positive";
  if (s >= 45) return "neutral";
  return "negative";
}

// Waterfall
function renderWaterfall(a) {
  const components = a.score_components || [];
  // Total of components might not equal score directly — fill with a "baseline" residual
  const componentsSum = components.reduce((s, c) => s + (c.points || 0), 0);
  const baseline = a.score - componentsSum;
  const steps = [{ name: "Start", delta: 100, kind: "start" }];
  if (baseline !== 0) {
    steps.push({ name: "Baseline", delta: baseline, kind: baseline > 0 ? "pos" : "neg" });
  }
  for (const c of components) {
    steps.push({ name: shorten(c.label), delta: c.points, kind: c.points >= 0 ? "pos" : "neg" });
  }
  steps.push({ name: "Final", delta: a.score, kind: "end" });

  // Compute running and bar segments
  const wfRows = [];
  let running = 0;
  const max = 100;
  const pct = (v) => (v / max) * 100;
  for (const s of steps) {
    let bar = "";
    let deltaTxt = "";
    let deltaCls = "";
    if (s.kind === "start") {
      running = s.delta;
      bar = `<div class="seg start" style="left:0; width:${pct(running)}%"></div>`;
      deltaTxt = "100";
    } else if (s.kind === "end") {
      bar = `<div class="seg end" style="left:0; width:${pct(s.delta)}%"></div>`;
      deltaTxt = `= ${s.delta}`;
      deltaCls = scoreClass(s.delta) === "s-good" ? "pos" : scoreClass(s.delta) === "s-bad" ? "neg" : "";
    } else {
      const prev = running;
      running = Math.max(0, Math.min(100, prev + s.delta));
      const lo = Math.min(prev, running);
      const hi = Math.max(prev, running);
      bar = `<div class="seg ${s.delta >= 0 ? "pos" : "neg"}" style="left:${pct(lo)}%; width:${pct(hi - lo)}%"></div>`;
      deltaTxt = (s.delta > 0 ? "+" : "") + s.delta;
      deltaCls = s.delta >= 0 ? "pos" : "neg";
    }
    wfRows.push(`
      <div class="wf-row ${s.kind}">
        <span class="name">${escapeHtml(s.name)}</span>
        <div class="wf-bar">${bar}</div>
        <span class="delta ${deltaCls}">${escapeHtml(deltaTxt)}</span>
      </div>
    `);
  }

  return `
    <section class="pane waterfall">
      <h2>How the score got built · 100 → ${a.score}</h2>
      <p class="sub">Every component starts from a perfect 100 and earns or loses points based on how the headline lines up with the release text.</p>
      <div class="wf-grid">${wfRows.join("")}</div>
    </section>
  `;
}

function shorten(label) {
  return label.length > 28 ? label.slice(0, 26) + "…" : label;
}

// Components pane
function renderComponentsPane(a) {
  return `
    <section class="pane section-pad">
      <h2 class="section-title">Concrete math · score components</h2>
      <div class="components">
        ${a.score_components.length ? a.score_components.map(renderComponent).join("") : "<p class=\"empty compact\">No score components yet.</p>"}
      </div>
    </section>
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

// Metrics pane
function renderMetricsPane(a) {
  return `
    <section class="pane section-pad">
      <h2 class="section-title">Metric tape · all values pulled from the release</h2>
      <div class="metrics">
        ${a.metrics.length ? a.metrics.map(renderMetric).join("") : "<p class=\"empty compact\">No metrics extracted.</p>"}
      </div>
    </section>
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

// Factors pane
function renderFactorsPane(title, items, color, kindCls) {
  return `
    <section class="pane section-pad">
      <h2 class="section-title" style="color:${color}">${escapeHtml(title)}</h2>
      ${items && items.length ? `<ul class="factors">${items.map((i) => `<li class="${kindCls}">${escapeHtml(i)}</li>`).join("")}</ul>` : "<p class=\"empty compact\">None detected.</p>"}
    </section>
  `;
}

// Citations
function renderCitationsPane(a) {
  if (!a.citations || !a.citations.length) {
    return `<section class="pane section-pad"><h2 class="section-title">Citations</h2><p class="empty compact">No citations captured.</p></section>`;
  }
  return `
    <section class="pane section-pad">
      <h2 class="section-title">Citations · what the model is reading</h2>
      <div class="citations">
        ${a.citations.map(renderCitation).join("")}
      </div>
    </section>
  `;
}

function renderCitation(c) {
  return `
    <div class="citation">
      <div class="src">${escapeHtml(c.label)}</div>
      <blockquote>${escapeHtml(c.excerpt)}</blockquote>
    </div>
  `;
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
  if (d === "neutral") return "neu";
  return "";
}
function shortType(type) {
  const m = {
    "Nonfarm Payrolls": "NFP", "Consumer Price Index": "CPI", "Producer Price Index": "PPI",
    "PCE Price Index": "PCE", "ADP Employment": "ADP", "Gross Domestic Product": "GDP",
    "Initial Jobless Claims": "Claims", "Fed Rate Decision": "FOMC",
    "Retail Sales": "Retail", "ISM Manufacturing": "ISM-M", "ISM Services": "ISM-S",
  };
  return m[type] || type;
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



// ===== Structured comparison v2 panes =====

function renderClaimsPane(a) {
  const claims = a.headline_claims || [];
  if (!claims.length) return "";
  return `
    <section class="pane section-pad">
      <h2 class="section-title">Headline claims · how each piece holds up</h2>
      <div class="claims-table">
        ${claims.map(renderClaimRow).join("")}
      </div>
    </section>
  `;
}

function renderClaimRow(c) {
  const verdict = c.verdict || "unsupported";
  const verdictLabel = verdict.replace(/_/g, " ");
  return `
    <div class="claim-row ${escapeHtml(verdict)}">
      <span class="claim-kind">${escapeHtml(c.kind || "claim")}</span>
      <div class="claim-text">
        <strong>${escapeHtml(c.text || "")}</strong>
        ${c.value ? ` · <code style="font-family:var(--mono);font-size:11.5px;color:var(--text-2)">${escapeHtml(c.value)}${c.unit ? " " + escapeHtml(c.unit) : ""}</code>` : ""}
        ${c.note ? `<div class="note">${escapeHtml(c.note)}</div>` : ""}
      </div>
      <span class="claim-verdict ${escapeHtml(verdict)}">${escapeHtml(verdictLabel)}</span>
    </div>
  `;
}

function renderCompositionPane(a) {
  const slices = a.composition || [];
  if (!slices.length) return "";
  // Keep order, ensure visible widths sum to 100%
  return `
    <section class="pane section-pad">
      <h2 class="section-title">What the headline number is made of</h2>
      <div class="composition-wrap">
        <div class="composition-bar" role="img" aria-label="Composition stacked bar">
          ${slices.map(renderCompSlice).join("")}
        </div>
        <div class="comp-legend">
          ${slices.map(renderCompLegend).join("")}
        </div>
      </div>
    </section>
  `;
}

function renderCompSlice(s) {
  const w = Math.max(0, Math.min(100, Number(s.share_pct) || 0));
  const cls = directionClass(s.direction) || (s.direction || "neutral");
  return `<div class="comp-slice ${escapeHtml(cls)}" style="width:${w}%" title="${escapeHtml(s.label)} ${w}%">${w >= 8 ? `${w}%` : ""}</div>`;
}

function renderCompLegend(s) {
  const w = Math.max(0, Math.min(100, Number(s.share_pct) || 0));
  const cls = directionClass(s.direction) || (s.direction || "neutral");
  const flag = w >= 25 ? `<span class="comp-flag">>25%</span>` : "";
  return `
    <div class="comp-legend-item">
      <span class="dot comp-slice ${escapeHtml(cls)}"></span>
      <span>${escapeHtml(s.label)}${flag}</span>
      <span class="pct">${w}%</span>
    </div>
  `;
}

function renderRevisionWatch(a) {
  const r = a.revision_adjustment;
  if (!r) return "";
  const dir = r.direction || "neutral";
  const arrow = dir === "negative"
    ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 12h14M13 18l6-6-6-6"/></svg>`
    : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 12h14M13 18l6-6-6-6"/></svg>`;
  const periods = (r.periods_revised || []).join(", ");
  return `
    <section class="pane section-pad">
      <h2 class="section-title">Revision watch</h2>
      <div class="rev-watch">
        <div class="rev-cell headline">
          <span class="k">Headline</span>
          <span class="v">${escapeHtml(r.headline_value)}</span>
        </div>
        <div class="rev-arrow">
          ${arrow}
          <span class="delta ${escapeHtml(dir)}">${escapeHtml(r.revision_total)}</span>
          ${periods ? `<span style="color:var(--muted)">${escapeHtml(periods)}</span>` : ""}
        </div>
        <div class="rev-cell adjusted ${escapeHtml(dir)}">
          <span class="k">After revisions</span>
          <span class="v">${escapeHtml(r.adjusted_value)}</span>
        </div>
      </div>
      ${r.note ? `<p class="rev-note">${escapeHtml(r.note)}</p>` : ""}
    </section>
  `;
}

function renderTonePane(a) {
  const t = a.tone;
  if (!t) return `
    <section class="pane section-pad">
      <h2 class="section-title">Tone vs. data</h2>
      <p class="empty compact">Available when the LLM augmenter is enabled (set OPENAI_API_KEY).</p>
    </section>
  `;
  const hi = Math.round((t.headline_intensity || 0) * 100);
  const di = Math.round((t.data_intensity || 0) * 100);
  const gap = Math.round((t.gap || 0) * 100);
  const gapText = gap > 15
    ? `Tone <strong>exceeds</strong> the data by ${gap} pts — likely overstates.`
    : gap < -15
    ? `Tone <strong>undersells</strong> the data by ${Math.abs(gap)} pts — buries the lede.`
    : `Tone tracks the data within ${Math.abs(gap)} pts.`;
  return `
    <section class="pane section-pad">
      <h2 class="section-title">Tone vs. data</h2>
      <div class="tone-wrap">
        <div class="tone-row headline">
          <span class="label">Headline</span>
          <div class="tone-bar"><div class="fill" style="width:${hi}%"></div></div>
          <span class="pct">${hi}%</span>
        </div>
        <div class="tone-row data">
          <span class="label">Data</span>
          <div class="tone-bar"><div class="fill" style="width:${di}%"></div></div>
          <span class="pct">${di}%</span>
        </div>
        <div class="tone-gap">${gapText}</div>
        ${(t.loaded_words || []).length ? `<div class="tone-words">${(t.loaded_words || []).map((w) => `<span class="word">${escapeHtml(w)}</span>`).join("")}</div>` : ""}
        ${t.note ? `<p class="rev-note">${escapeHtml(t.note)}</p>` : ""}
      </div>
    </section>
  `;
}

function renderProbabilityPane(a) {
  const p = a.verdict_probability;
  if (!p) return `
    <section class="pane section-pad">
      <h2 class="section-title">Probability of accurate summary</h2>
      <p class="empty compact">Available when the LLM augmenter is enabled (set OPENAI_API_KEY).</p>
    </section>
  `;
  const main = Math.round((p.accurate_summary_p || 0) * 100);
  const lo = Math.round((p.ci_low || 0) * 100);
  const hi = Math.round((p.ci_high || 0) * 100);
  const ciW = Math.max(1, hi - lo);
  return `
    <section class="pane section-pad">
      <h2 class="section-title">Probability of accurate summary</h2>
      <div class="prob-wrap">
        <div class="prob-track">
          <div class="prob-ci" style="left:${lo}%; width:${ciW}%"></div>
          <div class="prob-marker" style="left:calc(${main}% - 1.5px)">
            <span class="lbl">P = ${main}%</span>
          </div>
        </div>
        <div class="prob-axis">
          <span>0%</span><span>50%</span><span>100%</span>
        </div>
        ${Object.keys(p.components || {}).length ? `
          <div class="prob-components">
            ${Object.entries(p.components).map(([k, v]) => `
              <div class="prob-comp">
                <span class="name">${escapeHtml(k.replace(/_/g, " "))}</span>
                <span class="val">${Math.round(Number(v) * 100)}%</span>
              </div>
            `).join("")}
          </div>
        ` : ""}
        ${p.note ? `<p class="prob-note">${escapeHtml(p.note)}</p>` : ""}
      </div>
    </section>
  `;
}

function renderCoveragePane(a) {
  const gaps = a.coverage_gaps || [];
  if (!gaps.length) return "";
  return `
    <section class="pane section-pad">
      <h2 class="section-title">What the release emphasizes that the headline doesn't</h2>
      <div class="coverage-list">
        ${gaps.map(renderCoverageRow).join("")}
      </div>
    </section>
  `;
}

function renderCoverageRow(g) {
  const w = Math.max(0, Math.min(100, Number(g.release_emphasis_pct) || 0));
  return `
    <div class="coverage-row">
      <div>
        <div class="topic">${escapeHtml(g.topic)}</div>
        ${g.note ? `<div class="note">${escapeHtml(g.note)}</div>` : ""}
      </div>
      <div class="coverage-meter">
        <span style="color:var(--muted)">in release</span>
        <div class="bar"><div class="fill" style="width:${w}%"></div></div>
        <span class="pct">${w}%</span>
        <span style="color:var(--muted); margin-left:6px">${g.in_headline ? "✓ in headline" : "✗ not in headline"}</span>
      </div>
    </div>
  `;
}


loadReport();
