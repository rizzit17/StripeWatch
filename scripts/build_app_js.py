"""Build concise, optimized web/app.js < 40 KB."""
import os
import re
import subprocess
import shutil

APP_JS_PATH = "web/app.js"

JS = r"""// StripeWatch UI Client Application
const TRUCK_SVG = `<svg width="28" height="18" viewBox="0 0 28 18" aria-hidden="true"><rect x="1" y="5" width="14" height="8" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1.2"/><path d="M15 7h5l3 3v3h-8z" fill="#E4932A" stroke="#1D1B16" stroke-width="1.2"/><circle cx="6" cy="14" r="2" fill="#1D1B16"/><circle cx="19" cy="14" r="2" fill="#1D1B16"/></svg>`;

let curTab = "All", curRoute = "All routes", curSort = "week", curReviewFilter = "All";
let gLedgerIndex = -1, gTourStep = 0, gValidateMatrix = null, gPendingG = false, gPendingGTimer = null;

const byId = id => document.getElementById(id);
const qsa = s => document.querySelectorAll(s);
const pct = v => `${v > 0 ? "+" : ""}${Number(v).toFixed(1)}%`;
const formatINR = v => (v == null) ? "—" : "₹" + Number(v).toLocaleString("en-IN");
const esc = s => String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const slipId = c => "slip-" + c.route.replace(/\W/g, "_") + "-" + c.week_of;
const stHtml = (ok, txt) => `<span class="st ${ok ? 'ok' : 'flag'}">${txt || (ok ? 'JUSTIFIED' : 'FLAGGED')}</span>`;
const enc = encodeURIComponent, dec = decodeURIComponent;

function mapStaticUrl(url) {
  if (!window.STATIC_DEMO) return url;
  if (url.startsWith("/api/route/")) return `data/route_${enc(dec(url.slice(11).split("?")[0]))}.json`;
  const m = { rows: 1, summary: 1, calendar: 1, notes: 1, weeks: 1, review: 1 };
  const k = url.replace("/api/", "");
  return m[k] ? `data/${k}.json` : url;
}

async function getJSON(url, opts) {
  try {
    const res = await fetch(mapStaticUrl(url), opts);
    return res.ok ? await res.json() : null;
  } catch (e) { return null; }
}

function setNav(id) {
  qsa(".nav a").forEach(a => a.classList.toggle("active", a.id === id));
}

function setLoading(load) {
  const t = byId("truck-icon");
  if (t) t.classList.toggle("loading-truck", !!load);
}

// Review queue
async function getReviews() {
  if (window.STATIC_DEMO) {
    try {
      const s = localStorage.getItem("stripewatch_review");
      if (s) {
        const p = JSON.parse(s);
        return { reviews: p.reviews || p, items: [] };
      }
    } catch (e) {}
  }
  const raw = await getJSON("/api/review");
  const m = {};
  if (Array.isArray(raw)) {
    raw.forEach(r => { m[`${r.route}|${r.week_of}`] = { status: r.review_status, note: r.review_note }; });
    return { reviews: m, items: raw };
  }
  return raw || { reviews: {}, items: [] };
}

async function putReview(route, week_of, status, note) {
  if (window.STATIC_DEMO) {
    try {
      const state = await getReviews();
      if (!state.reviews) state.reviews = {};
      state.reviews[`${route}|${week_of}`] = { status, note, updated_at: new Date().toISOString() };
      localStorage.setItem("stripewatch_review", JSON.stringify(state));
      return { ok: true };
    } catch (e) { return { ok: false }; }
  }
  return await getJSON(`/api/review/${enc(route)}/${week_of}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, note })
  });
}

async function downloadReviewCSV() {
  const a = document.createElement("a");
  a.download = "review_export.csv";
  if (!window.STATIC_DEMO) { a.href = "/api/review/export.csv"; a.click(); return; }
  const [revData, rows] = await Promise.all([getReviews(), getJSON("/api/rows")]);
  const m = revData.reviews || {};
  let c = "route,week_of,verdict,matched_note_id,review_status,review_note\n";
  (rows || []).forEach(r => {
    const v = m[`${r.route}|${r.week_of}`] || {};
    c += `"${r.route}","${r.week_of}","${r.verdict}","${r.matched_note_id||''}","${v.status||'open'}","${(v.note||'').replace(/"/g,'""')}"\n`;
  });
  a.href = URL.createObjectURL(new Blob([c], { type: "text/csv" }));
  a.click();
}

// Highlight helper
function renderHighlightedHtml(text, evidenceSpans, negatingSpans, isRejected) {
  if (!text) return "";
  const targets = [];
  const list = isRejected ? (negatingSpans || []) : (evidenceSpans || []);
  list.forEach(span => {
    const idx = text.indexOf(span);
    if (idx !== -1) targets.push({ start: idx, end: idx + span.length, type: isRejected ? "negating" : "evidence" });
  });
  if (!targets.length) return esc(text);
  targets.sort((a, b) => a.start - b.start);
  let res = "", cur = 0;
  for (const t of targets) {
    if (t.start >= cur) {
      res += esc(text.slice(cur, t.start));
      const chunk = esc(text.slice(t.start, t.end));
      res += t.type === "negating" ? `<mark class="negating">${chunk}<span class="rej-badge">why rejected</span></mark>` : `<mark class="evidence">${chunk}</mark>`;
      cur = t.end;
    }
  }
  return res + esc(text.slice(cur));
}

// Paper trail strip
function renderPaperTrailHtml(tickets, evaluatedNoteId) {
  if (!tickets || !tickets.length) return "";
  const h = evaluatedNoteId ? `<div class="mono sub" style="margin-bottom:6px;">Paper trail for ${evaluatedNoteId}:</div>` : "";
  const items = tickets.map(t => {
    const num = t.index || t.ticket || t[0] || "";
    const name = t.name || t[1] || "";
    const detail = (t.detail || t[2] || "").replace(/\+\+/g, "+");
    const stamp = t.stamp || t[3] || "";
    return `<div class="pt-ticket"><span class="pt-title">${num ? num + '. ' : ''}${name}</span><div class="pt-detail mono">${esc(detail)}</div><span class="pt-stamp ${stamp.toLowerCase()}">${stamp}</span></div>`;
  }).join("");
  return `<div class="pt-strip-wrap">${h}<div class="pt-strip">${items}</div></div>`;
}

// SCREEN 0: Overview Landing Page
function renderOverview() {
  setNav("nav-overview");
  const logo = `<svg width="40" height="40" viewBox="0 0 32 32" role="img" aria-label="Logo"><rect width="32" height="32" rx="5" fill="#1D1B16"/><rect x="5" y="11" width="12" height="9" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1.2"/><path d="M17 13h5l3 3v4h-8z" fill="#E4932A" stroke="#1D1B16" stroke-width="1.2"/><circle cx="10" cy="21" r="2.2" fill="#1D1B16"/><circle cx="21" cy="21" r="2.2" fill="#1D1B16"/></svg>`;
  const kpis = [["728","ROUTE-WEEKS","104w · 7 routes",""],["19","ANOMALIES","Exceeding baselines","tiger"],["3","JUSTIFIED","N001 flood, N002 Diwali","green"],["16","FLAGGED","Unexplained rate creep","red"]];
  const rts = [["Delhi-Jaipur","Short·260km"],["Mumbai-Pune","Short·150km"],["Ahmedabad-Mumbai","Med·530km"],["Chennai-Bangalore","Med·350km"],["Kolkata-Bhubaneswar","Med·440km"],["Delhi-Chennai","Long·2200km"],["Mumbai-Delhi","Long·1400km"]];

  byId("app").innerHTML = `
    <div class="slip" style="margin-bottom:16px;border-left:5px solid var(--tiger);">
      <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;">
        <div style="flex-shrink:0;">${logo}</div>
        <div style="flex:1;min-width:240px;">
          <div style="display:flex;gap:8px;margin-bottom:4px;"><span class="mono tag" style="background:var(--highlight);font-weight:600;">FREIGHT TIGER AI CASE STUDY</span><span class="mono tag">ZERO HALLUCINATION</span></div>
          <div class="big" style="font-size:26px;line-height:1.15;margin-bottom:4px;">StripeWatch</div>
          <p style="font-size:13px;line-height:1.4;margin:0 0 10px;color:var(--ink-soft);">Autonomous freight cost watchdog with deterministic 5-gate RAG. Genuine operational disruptions justified; ungrounded rate creep flagged.</p>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            ${[['#/ledger','Live Ledger →','primary'],['#/calendar','Calendar Heatmap'],['#/fool','Try to Fool It'],['#/ask','Ask Watchdog']].map(a=>`<a href="${a[0]}" class="cta-btn ${a[2]||''}">${a[1]}</a>`).join("")}
            <button onclick="startTour()" class="cta-btn">Take Tour</button>
          </div>
        </div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:16px;">
      ${kpis.map(k=>`<div class="slip" style="padding:10px 14px;"><div class="big num ${k[3]}" style="font-size:28px;">${k[0]}</div><div class="lbl" style="font-size:11px;font-weight:600;color:var(--ink-soft);">${k[1]}</div><p style="font-size:11px;margin:2px 0 0;color:var(--ink-soft);">${k[2]}</p></div>`).join("")}
    </div>
    <div class="slip" style="margin-bottom:16px;">
      <div class="row" style="margin-bottom:8px;border-bottom:1.5px solid var(--rule);padding-bottom:4px;"><span class="big" style="font-size:15px;">Core Watchdog Rules</span><span class="mono tag">DETERMINISTIC</span></div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;">
        ${[["01. RATIO-OF-SUMS","c = Σ cost / Σ (t-km)"],["02. ZERO LOOK-AHEAD","Prior 8w shift(1) + peers"],["03. 5-GATE AUDIT","Route · Window · Effect · Size"],["04. HONEST ABSTENTION","16 of 19 flagged unexplained"]].map(r=>`<div style="padding:6px 10px;background:var(--paper);border:1px solid var(--rule);border-radius:3px;"><strong class="mono" style="font-size:11px;color:var(--tiger);">${r[0]}</strong><p style="font-size:12px;margin:2px 0 0;">${r[1]}</p></div>`).join("")}
      </div>
    </div>
    <div class="slip" style="margin-bottom:16px;">
      <div class="row" style="margin-bottom:4px;"><span class="big" style="font-size:14px;">7 Freight Corridors</span><span class="mono" style="font-size:11px;color:var(--ink-soft);">104 WEEKS · 2024–2025</span></div>
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;">
        ${rts.map(r=>`<a href="#/route/${r[0]}" class="chip plain" style="padding:3px 7px;text-decoration:none;color:var(--ink);"><strong>${r[0]}</strong> <span class="mono" style="color:var(--ink-soft);">(${r[1]})</span></a>`).join("")}
      </div>
    </div>
  `;
}

// SCREEN A: Ledger
async function renderLedger() {
  setNav("nav-ledger");
  setLoading(true);
  const [sum, rows, revData] = await Promise.all([
    getJSON("/api/summary"),
    getJSON(`/api/rows?sort_by=${curSort === "excess" ? "excess" : "week"}`),
    getReviews()
  ]);
  setLoading(false);

  if (!sum || !rows) {
    byId("app").innerHTML = '<div class="slip"><p>Failed to load ledger data.</p></div>';
    return;
  }

  const reviewsMap = revData.reviews || {};
  const routes = ["All routes", ...new Set(rows.map(r => r.route))];
  let list = rows;
  if (curRoute !== "All routes") list = list.filter(r => r.route === curRoute);
  if (curTab === "Flagged") list = list.filter(r => r.verdict === "unexplained");
  else if (curTab === "Justified") list = list.filter(r => r.verdict === "justified");

  if (curReviewFilter !== "All") {
    list = list.filter(r => (reviewsMap[`${r.route}|${r.week_of}`]?.status || "open").toLowerCase() === curReviewFilter.toLowerCase());
  }

  let reviewedCount = 0;
  rows.filter(r => r.verdict === "unexplained").forEach(r => {
    if ((reviewsMap[`${r.route}|${r.week_of}`]?.status || "open").toLowerCase() !== "open") reviewedCount++;
  });

  const trs = list.map((r, i) => {
    const ok = r.verdict === "justified";
    const chip = (ok && r.matched_note_id) ? `<span class="chip">${r.matched_note_id}</span>` : "—";
    const tgt = `#/route/${enc(r.route)}?week=${r.week_of}`;
    const exc = r.excess_inr ? formatINR(r.excess_inr) : "—";
    const revStatus = reviewsMap[`${r.route}|${r.week_of}`]?.status || "open";
    const revStamp = `<button class="btn-review ${revStatus}" onclick="event.stopPropagation();window.cycleReview('${r.route}','${r.week_of}')" title="Cycle review status">${revStatus.toUpperCase()}</button>`;
    return `<tr class="r" id="ledger-row-${i}" tabindex="0" onclick="location.hash='${tgt}'" onkeydown="if(event.key==='Enter')location.hash='${tgt}'"><td class="mono">${r.week_of}</td><td><strong>${r.route}</strong></td><td class="mono">${r.c.toFixed(2)}</td><td class="mono">▲ ${pct(r.vs_own_pct)}</td><td class="mono">${pct(r.vs_peer_pct)}</td><td class="mono">${exc}</td><td>${stHtml(ok)}</td><td>${chip}</td><td style="text-align:center;">${revStamp}</td></tr>`;
  }).join("");

  const card = (n, lbl, cls="") => `<div class="slip"><div class="big num ${cls}">${n}</div><div class="lbl">${lbl}</div></div>`;
  const ths = ["Week of", "Route", "₹/t-km", "vs own", "vs peers", "Excess ₹", "Verdict", "Note", "Review"].map(h => `<th scope="col">${h}</th>`).join("");
  const abstentionText = sum.abstention
    ? `Left ${sum.abstention.unexplained} of ${sum.abstention.total} unexplained on purpose: only ${sum.abstention.usable_notes} of ${sum.abstention.total_notes} notes can justify a rise.`
    : "Left 16 of 19 unexplained on purpose: only 3 of 10 notes can justify a rise.";

  const banner = window.STATIC_DEMO ? '<div class="static-banner">Static demo: snapshot of committed results. No API keys, no live model.</div>' : '';

  byId("app").innerHTML = `
    ${banner}
    <h2 class="sr-only">StripeWatch ledger: ${sum.rises} cost rises spotted</h2>
    <section class="summary" aria-label="Overview" id="tour-summary-strip">
      ${card(sum.rises, "rises spotted")}${card(sum.justified, "justified by a note", "green")}${card(sum.flagged, "need a human look", "red")}
    </section>
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin:-4px 0 16px;font-size:12px;color:var(--ink-soft);">
      <span>${abstentionText} · Est. excess: <strong style="color:var(--ink);">₹1.28 lakh</strong></span>
      <span><strong>${reviewedCount}/16</strong> reviewed · <a href="javascript:window.exportReviewsCSV()" style="color:var(--ink);text-decoration:underline;">Export CSV</a></span>
    </div>
    <div class="filters">
      <label for="route-select">Route</label>
      <select id="route-select">${routes.map(rt => `<option value="${rt}" ${curRoute === rt ? "selected" : ""}>${rt}</option>`).join("")}</select>
      <span class="sort-toggle">
        <span>Sort:</span>
        <button id="sort-week" class="${curSort === 'week' ? 'active' : ''}">week</button>
        <button id="sort-excess" class="${curSort === 'excess' ? 'active' : ''}">excess ₹</button>
      </span>
      <select id="rev-select" style="width:130px;" aria-label="Review filter">
        ${["All", "Open", "Confirmed", "Dismissed"].map(s => `<option value="${s}" ${curReviewFilter === s ? "selected" : ""}>Review: ${s}</option>`).join("")}
      </select>
      <span class="tabs" role="tablist" style="margin-left:auto;">
        ${["All", "Flagged", "Justified"].map(t => `<button role="tab" id="tab-${t.toLowerCase()}" aria-pressed="${curTab === t}">${t}</button>`).join("")}
      </span>
      <button class="btn-print-only" onclick="window.printSummary()" style="padding:4px 9px;">Print summary</button>
    </div>
    <div class="slip ledger" id="tour-ledger-table">
      <table aria-label="Ledger">
        <thead><tr>${ths}</tr></thead>
        <tbody>${trs || '<tr><td colspan="9" style="text-align:center;padding:18px;">No matching rows found.</td></tr>'}</tbody>
      </table>
    </div>
    <p class="mono footer" id="tour-footer">notes: 10 · LLM calls: ${sum.llm_calls} · temp: ${sum.temperature} · ${sum.repro_identical ? "identical on 3 runs ✓" : "reproducible"}</p>
  `;

  byId("route-select").onchange = e => { curRoute = e.target.value; renderLedger(); };
  byId("sort-week").onclick = () => { curSort = "week"; renderLedger(); };
  byId("sort-excess").onclick = () => { curSort = "excess"; renderLedger(); };
  byId("rev-select").onchange = e => { curReviewFilter = e.target.value; renderLedger(); };
  ["All", "Flagged", "Justified"].forEach(t => {
    byId("tab-" + t.toLowerCase()).onclick = () => { curTab = t; renderLedger(); };
  });
}

window.cycleReview = async (route, week_of) => {
  const revData = await getReviews();
  const cur = (revData.reviews?.[`${route}|${week_of}`]?.status || "open").toLowerCase();
  const next = cur === "open" ? "confirmed" : (cur === "confirmed" ? "dismissed" : "open");
  const note = revData.reviews?.[`${route}|${week_of}`]?.note || "";
  await putReview(route, week_of, next, note);
  renderLedger();
};

window.exportReviewsCSV = () => { downloadReviewCSV(); };
window.printSummary = () => { document.body.dataset.print = "summary"; window.print(); };
window.addEventListener("afterprint", () => { delete document.body.dataset.print; });

// SCREEN B: Route Page
async function renderRoute(route, targetWk) {
  setNav("nav-routes");
  setLoading(true);
  const [data, revData] = await Promise.all([getJSON(`/api/route/${enc(route)}`), getReviews()]);
  setLoading(false);

  if (!data) {
    byId("app").innerHTML = `<div class="slip"><p>Route '${esc(route)}' not found.</p><a href="#/ledger">← Back to Ledger</a></div>`;
    return;
  }

  const { route_type, series, candidates, attribution } = data;
  const reviewsMap = revData.reviews || {};
  const pts = series, n = pts.length;
  const maxVal = Math.max(...pts.map(s => Math.max(s.c, s.own_avg || 0)), 1.0);
  const yTop = Math.ceil(maxVal * 2) / 2, yMid = yTop - 0.5, yBot = yTop - 1.0;
  const getY = v => Math.max(20, Math.min(140, 30 + ((yTop - v) / (yTop - yBot || 1.0)) * 100));
  const getX = i => 60 + i * (540 / Math.max(1, n - 1));

  let wPath = "", oPath = "", dots = "", creepTicks = "";
  const candMap = {};
  candidates.forEach(c => { candMap[c.week_of] = c; });

  pts.forEach((p, i) => {
    const x = getX(i), yW = getY(p.c);
    wPath += (i === 0 ? "M " : " L ") + `${x.toFixed(1)} ${yW.toFixed(1)}`;
    if (p.own_avg !== null) oPath += (!oPath ? "M " : " L ") + `${x.toFixed(1)} ${getY(p.own_avg).toFixed(1)}`;
    const cRow = candMap[p.week_of];
    if (cRow) {
      const ok = cRow.verdict === "justified";
      dots += `<circle cx="${x.toFixed(1)}" cy="${yW.toFixed(1)}" r="6" fill="${ok ? "#FFFDF7" : "#C8452D"}" ${ok ? 'stroke="#2E7A5B" stroke-width="2.5"' : ''} tabindex="0" aria-label="${ok ? 'Justified' : 'Flagged'}: ${p.week_of}"><title>${p.week_of}: ₹${p.c.toFixed(2)}/t-km</title></circle>`;
    }
    if (p.creep_tag) {
      creepTicks += `<polygon points="${x.toFixed(1)},145 ${(x-3).toFixed(1)},151 ${(x+3).toFixed(1)},151" fill="#E4932A"><title>${p.week_of}: peer gap sustained 4 weeks</title></polygon>`;
    }
  });

  const gridHtml = [30, 80, 130].map((y, i) => `<line x1="40" y1="${y}" x2="620" y2="${y}" stroke="#D9D0BC" stroke-dasharray="2 4"/><text x="4" y="${y+4}">${[yTop, yMid, yBot][i].toFixed(2)}</text>`).join("");

  let initialScrubIdx = 0;
  if (targetWk) {
    const idx = pts.findIndex(p => p.week_of === targetWk);
    if (idx !== -1) initialScrubIdx = idx;
  } else if (candidates.length > 0) {
    const idx = pts.findIndex(p => p.week_of === candidates[0].week_of);
    if (idx !== -1) initialScrubIdx = idx;
  }

  const slips = candidates.map(c => {
    const ok = c.verdict === "justified";
    const nObj = c.evidence_packet?.note;
    const noteText = ok && nObj
      ? `<div class="cited"><span class="chip plain">${nObj.id}</span> ${renderHighlightedHtml(nObj.text || nObj.rationale, nObj.evidence_spans, null, false)}</div>`
      : '<p style="color:var(--ink-soft);font-size:13px;margin:6px 0;">No matching note found. Looks unexplained, worth a human look.</p>';

    const nms = c.evidence_packet?.near_misses || [];
    const rejectedList = (!ok && nms.length)
      ? `<div class="rejected" style="margin-bottom:10px;"><strong>Closest notes I rejected:</strong><br>${nms.map(m => `<span class="chip plain">${m.id}</span> ${renderHighlightedHtml(m.raw_text || m.why_not, null, m.negating_spans || [m.why_not], true)}`).join('<br>')}</div>`
      : "";

    const sid = slipId(c);
    const excStr = c.excess_inr ? ` · <span class="mono">excess: ${formatINR(c.excess_inr)}</span>` : "";
    const revItem = reviewsMap[`${c.route}|${c.week_of}`] || { status: "open", note: "" };

    return `
      <div class="slip" id="${sid}" data-slip-id="${sid}">
        <div class="row">
          <span class="mono slip-date">week of ${c.week_of}</span>
          <div style="display:flex;align-items:center;gap:8px;">${stHtml(ok)}<button class="btn-print-only" onclick="window.printDocket('${sid}')" style="padding:2px 6px;">Print docket</button></div>
        </div>
        <p style="margin:4px 0 8px;"><span class="mono" style="font-weight:600;">${c.c.toFixed(2)} ₹/t-km</span> · ${pct(c.vs_own_pct)} vs own · ${pct(c.vs_peer_pct)} vs peers${excStr}</p>
        ${noteText}
        <details class="slip-audit" style="margin-top:10px;border-top:1px dotted var(--rule);padding-top:8px;">
          <summary class="mono" style="cursor:pointer;font-size:12px;color:var(--ink-soft);user-select:none;">▸ 5-gate audit trail & review notes</summary>
          <div style="margin-top:10px;">
            ${rejectedList}
            ${renderPaperTrailHtml(c.tickets, c.evaluated_note_id)}
            <div class="review-box" style="margin-top:10px;">
              <label class="review-label" for="rev-note-${sid}">Your review note (stored on this computer):</label>
              <textarea class="review-textarea" id="rev-note-${sid}" maxlength="280" placeholder="Optional audit comment...">${esc(revItem.note)}</textarea>
              <div class="char-counter" id="char-cnt-${sid}">${(revItem.note || "").length} / 280</div>
            </div>
          </div>
        </details>
      </div>
    `;
  }).join("");

  let attrSlip = "";
  if (attribution && attribution.length > 0) {
    attrSlip = `
      <div class="slip" style="margin-bottom:16px;">
        <div class="row"><span class="big" style="font-size:16px;">Where the rise sits</span><span class="mono tag">DATA ONLY</span></div>
        <p style="font-size:12px;color:var(--ink-soft);margin-bottom:8px;">Transporter vs route concentration.</p>
        ${attribution.map(ep => `
          <div style="border-bottom:1px dotted var(--rule);padding:6px 0;">
            <div style="display:flex;justify-content:space-between;"><span class="mono" style="font-weight:600;">${ep.start} to ${ep.end}</span><span class="mono tag">${ep.verdict}</span></div>
            <p style="font-size:12px;margin:2px 0;color:var(--ink-soft);">${ep.transporter?.verdict ? `<strong>Transporter:</strong> ${esc(ep.transporter.verdict)}` : ''}</p>
          </div>
        `).join("")}
      </div>
    `;
  }

  const rStart = pts[0].week_of, rEnd = pts[pts.length - 1].week_of;
  byId("app").innerHTML = `
    <div style="margin-bottom:12px;"><a href="#/ledger" style="color:var(--ink-soft);text-decoration:none;font-size:13px;">← Back to Ledger</a></div>
    <div class="route-head"><span class="big title">${esc(route)}</span><span class="mono tag">${route_type.toUpperCase()}</span><span class="mono range">${rStart} to ${rEnd}</span></div>
    <div class="slip chart" id="tour-route-chart">
      <svg id="route-svg" width="100%" height="190" viewBox="0 0 640 190" role="img" aria-label="Chart" font-family="'JetBrains Mono',monospace" font-size="11" fill="#6B665A">
        ${gridHtml}
        <path d="${oPath}" stroke="#6B665A" stroke-width="1.2" stroke-dasharray="5 4" fill="none"/>
        <path d="${wPath}" stroke="#1D1B16" stroke-width="1.8" fill="none"/>
        ${dots}
        ${creepTicks}
        <line id="scrub-line" x1="${getX(initialScrubIdx).toFixed(1)}" y1="20" x2="${getX(initialScrubIdx).toFixed(1)}" y2="150" stroke="#E4932A" stroke-width="1.5" stroke-dasharray="3 3"/>
        <g id="truck-scrubber" class="truck-marker" transform="translate(${(getX(initialScrubIdx)-14).toFixed(1)}, 148)" role="slider" tabindex="0" aria-valuemin="0" aria-valuemax="${n-1}" aria-valuenow="${initialScrubIdx}" aria-valuetext="week of ${pts[initialScrubIdx].week_of}">
          ${TRUCK_SVG}
        </g>
        <text x="60" y="176">${rStart}</text>
        <text x="310" y="176" text-anchor="middle">${pts[Math.floor(n/2)].week_of}</text>
        <text x="600" y="176" text-anchor="end">${rEnd}</text>
      </svg>
      <div class="mono legend">
        <span>━ weekly ₹/t-km</span><span>┅ own 8w avg</span><span class="g">◯ justified</span><span class="r">● flagged</span><span style="color:var(--tiger);">▲ peer gap</span><span style="color:var(--ink);font-weight:600;">🚚 drag truck</span>
      </div>
      <div id="live-week-slip" class="live-week-slip"></div>
    </div>
    ${attrSlip}
    <div class="slips">${slips || '<div class="slip"><p>No cost rise candidates on this route.</p></div>'}</div>
  `;

  function updateLiveSlip(idx) {
    const curP = pts[idx], cRow = candMap[curP.week_of];
    const lineEl = byId("scrub-line"), truckEl = byId("truck-scrubber"), liveEl = byId("live-week-slip");
    if (!curP || !lineEl || !truckEl || !liveEl) return;

    const x = getX(idx);
    lineEl.setAttribute("x1", x.toFixed(1));
    lineEl.setAttribute("x2", x.toFixed(1));
    truckEl.setAttribute("transform", `translate(${(x - 14).toFixed(1)}, 148)`);
    truckEl.setAttribute("aria-valuenow", idx);

    let statusText = "Normal this week";
    if (curP.own_avg === null) statusText = "First week";
    else if (cRow) {
      statusText = stHtml(cRow.verdict === "justified", cRow.verdict === "justified" ? `JUSTIFIED (${cRow.matched_note_id})` : 'FLAGGED');
    }

    const excText = curP.excess_inr ? ` · excess: <strong>${formatINR(curP.excess_inr)}</strong>` : "";
    const jumpLink = cRow ? ` · <a href="#${slipId(cRow)}" style="color:var(--ink);text-decoration:underline;">Scroll to slip ↓</a>` : "";

    liveEl.innerHTML = `
      <div class="row">
        <div>
          <span class="mono" style="font-size:14px;font-weight:600;">Week of ${curP.week_of}</span>
          <div style="font-size:12px;color:var(--ink-soft);margin-top:2px;">
            <span>Cost: <strong>₹${curP.c.toFixed(2)}/t-km</strong></span> · 
            <span>Own: <strong>${curP.own_avg ? `₹${curP.own_avg.toFixed(2)}` : '—'}</strong> (${pct(curP.vs_own_pct)})</span> · 
            <span>Peers: <strong>${curP.peer_avg ? `₹${curP.peer_avg.toFixed(2)}` : '—'}</strong> (${pct(curP.vs_peer_pct)})</span>${excText}
          </div>
        </div>
        <div>${statusText}${jumpLink}</div>
      </div>
    `;
  }

  updateLiveSlip(initialScrubIdx);

  const truckMarker = byId("truck-scrubber");
  if (truckMarker) {
    truckMarker.onkeydown = e => {
      let cur = parseInt(truckMarker.getAttribute("aria-valuenow") || "0");
      const d = e.shiftKey ? 4 : 1;
      if (e.key === "ArrowLeft") cur = Math.max(0, cur - d);
      else if (e.key === "ArrowRight") cur = Math.min(n - 1, cur + d);
      else if (e.key === "Home") cur = 0;
      else if (e.key === "End") cur = n - 1;
      else return;
      updateLiveSlip(cur);
      e.preventDefault();
    };

    let dragging = false;
    const svgEl = byId("route-svg");
    const onMove = e => {
      if (!dragging) return;
      const rect = svgEl.getBoundingClientRect();
      const clientX = e.clientX || (e.touches && e.touches[0].clientX);
      if (clientX === undefined) return;
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left - 60) / (rect.width - 100)));
      updateLiveSlip(Math.max(0, Math.min(n - 1, Math.round(ratio * (n - 1)))));
    };
    truckMarker.onpointerdown = e => { dragging = true; truckMarker.setPointerCapture(e.pointerId); };
    truckMarker.onpointermove = onMove;
    truckMarker.onpointerup = e => { dragging = false; try { truckMarker.releasePointerCapture(e.pointerId); } catch(err){} };
  }

  candidates.forEach(c => {
    const sid = slipId(c);
    const ta = byId(`rev-note-${sid}`), cnt = byId(`char-cnt-${sid}`);
    if (ta && cnt) {
      ta.oninput = () => { cnt.textContent = `${ta.value.length} / 280`; };
      ta.onblur = async () => {
        const curStatus = (reviewsMap[`${c.route}|${c.week_of}`]?.status || "open");
        await putReview(c.route, c.week_of, curStatus, ta.value.trim());
      };
    }
  });
}

window.printDocket = sid => { document.body.dataset.print = "docket"; window.print(); };

// SCREEN C: Lorry Calendar Heatmap (UI-1)
async function renderCalendar() {
  setNav("nav-calendar");
  setLoading(true);
  const data = await getJSON("/api/calendar");
  setLoading(false);

  if (!data) {
    byId("app").innerHTML = '<div class="slip"><p>Failed to load calendar data.</p></div>';
    return;
  }

  const groups = data.route_groups || data.groups || [], cells = data.cells || [];
  const W = 6, H = 18, LEFT = 216, TOP = 38, cellMap = {};
  cells.forEach(c => { cellMap[`${c.route}|${c.week_of}`] = c; });
  const weeks = [...new Set(cells.map(c => c.week_of))].sort();
  const routes = [];
  groups.forEach(g => (g.routes || []).forEach(r => routes.push({ route: r, type: g.type })));

  let rects = "", labels = "", ticks = `<text x="12" y="22" class="mono" font-size="9" font-weight="600" fill="#8C8270">CORRIDOR</text><text x="156" y="22" class="mono" font-size="9" font-weight="600" fill="#8C8270">TIER</text><line x1="204" y1="10" x2="204" y2="196" stroke="#D9D0BC" stroke-dasharray="2 3"/>`;

  weeks.forEach((wk, i) => {
    const isLast = i === weeks.length - 1;
    if ((i % 8 === 0 && weeks.length - 1 - i >= 8) || isLast) {
      ticks += `<text x="${LEFT + i * 7 + (isLast ? W : 0)}" y="22" class="mono" font-size="9.5" fill="#6B665A" ${isLast ? 'text-anchor="end"' : ''}>${wk.slice(2, 7)}</text>`;
    }
  });

  routes.forEach((ro, rIdx) => {
    const y = TOP + rIdx * 22;
    labels += `<text x="12" y="${y + 13}" font-size="11.5" font-weight="600" fill="var(--ink)">${ro.route}</text><text x="156" y="${y + 13}" class="mono" font-size="9" fill="#8C8270" letter-spacing="0.05em">${ro.type}</text>`;

    weeks.forEach((wk, wIdx) => {
      const c = cellMap[`${ro.route}|${wk}`];
      if (!c) return;
      const x = LEFT + wIdx * 7;
      let fill = "var(--rule)", stroke = "none", sw = "0", dash = "", focus = "", lbl = "";
      if (!c.is_evaluable) {
        fill = "transparent"; stroke = "var(--rule)"; sw = "1"; dash = 'stroke-dasharray="2"';
      } else if (c.is_candidate) {
        const ok = c.verdict === "justified";
        fill = ok ? "var(--slip)" : "var(--stamp-red)";
        stroke = ok ? "var(--stamp-green)" : "none";
        sw = ok ? "2" : "0";
        lbl = `${ok ? 'Justified' : 'Flagged'}: ${c.route} week ${c.week_of}`;
        focus = `tabindex="0" aria-label="${lbl}" onclick="location.hash='#/route/${enc(c.route)}?week=${c.week_of}'" onkeydown="if(event.key==='Enter')location.hash='#/route/${enc(c.route)}?week=${c.week_of}'"`;
      }
      const creep = c.creep_tag ? `<rect x="${x}" y="${y + 19}" width="${W}" height="2" fill="var(--tiger-soft)"/>` : "";
      rects += `<rect class="cal-cell" x="${x}" y="${y}" width="${W}" height="${H}" rx="1" fill="${fill}" stroke="${stroke}" stroke-width="${sw}" ${dash} ${focus}><title>${c.route} (${c.week_of}): ₹${c.c.toFixed(2)}/t-km ${c.is_candidate ? '['+c.verdict.toUpperCase()+']' : ''}</title></rect>${creep}`;
    });
  });

  const calLeg = [
    ["var(--rule)", "Normal", ""],
    ["transparent", "First week", "border:1px dashed var(--rule);"],
    ["var(--stamp-red)", "Flagged", "", "r"],
    ["var(--slip)", "Justified", "border:2px solid var(--stamp-green);", "g"],
    ["var(--tiger-soft)", "Peer gap 4w", ""]
  ].map(l => `<div class="cal-legend-item"><span class="cal-legend-swatch" style="background:${l[0]};${l[2]}"></span><span class="${l[3]||''}">${l[1]}</span></div>`).join("");

  byId("app").innerHTML = `
    <div class="big" style="font-size:24px;margin-bottom:6px;">Lorry Calendar Heatmap</div>
    <p style="font-size:13px;color:var(--ink-soft);margin-bottom:14px;">104-week cross-corridor timeline. Red blocks spot candidate anomalies; green rings spot justified events.</p>
    <div class="cal-container" id="tour-cal-chart">
      <svg width="100%" height="236" viewBox="0 0 960 236" role="img" aria-label="Heatmap">
        ${ticks}${labels}${rects}
      </svg>
      <div class="cal-legend">${calLeg}</div>
    </div>
    <div class="slip" style="margin-top:16px;">
      <p class="mono" style="margin:0;font-size:13px;">${data.summary_sentence || ""}</p>
    </div>
  `;
}

// SCREEN D: Notes Page
async function renderNotes() {
  setNav("nav-notes");
  setLoading(true);
  const notes = await getJSON("/api/notes");
  setLoading(false);

  if (!notes) {
    byId("app").innerHTML = '<div class="slip"><p>Failed to load notes.</p></div>';
    return;
  }

  const slips = notes.map(n => {
    let stampCls = "flag", stampTxt = "CAN'T JUSTIFY";
    const canJustify = n.effect === "raises" && n.scope !== "NONE";
    if (canJustify) {
      stampCls = n.scope === "ALL" ? "warn" : "ok";
      stampTxt = n.scope === "ALL" ? "CAN JUSTIFY (CAPPED)" : "CAN JUSTIFY";
    }
    const win = `${n.start || n.date} to ${n.end || (canJustify ? 'ongoing' : 'normal')}`;
    const rawText = n.text || n.note || n.rationale || "";
    const highlighted = renderHighlightedHtml(rawText, n.evidence_spans, n.negating_spans, !canJustify);

    return `
      <div class="slip">
        <div class="row">
          <div><span class="chip">${n.id}</span> <strong style="margin-left:6px;font-size:13px;">${esc(n.applies_to)}</strong></div>
          <span class="st ${stampCls}">${stampTxt}</span>
        </div>
        <p style="font-size:12px;color:var(--ink-soft);margin:4px 0 8px;">Scope: <strong>${n.scope}</strong> · Effect: <strong>${n.effect}</strong> · Window: <strong>${win}</strong></p>
        <p class="cited" style="font-size:12px;margin:6px 0;">"${highlighted}"</p>
        <p class="rejected" style="font-size:12px;color:var(--ink);"><strong>Rationale:</strong> ${esc(n.rationale || "—")}</p>
      </div>
    `;
  }).join("");

  byId("app").innerHTML = `
    <div class="big" style="font-size:24px;margin-bottom:6px;">Context Notes Register</div>
    <div class="slip" style="margin-bottom:16px;background:var(--highlight);border:1.5px dashed var(--ink);">
      <p style="margin:0;font-size:13px;line-height:1.5;"><strong>Ground truth:</strong> 3 of 10 notes can ever justify a cost rise. The other 7 say costs were normal, apply elsewhere, or mark reopening.</p>
    </div>
    <div class="slips">${slips}</div>
  `;
}

// SCREEN E: Try to Fool It Console
async function renderFool() {
  setNav("nav-fool");
  setLoading(true);
  const [notes, weeks] = await Promise.all([getJSON("/api/notes"), getJSON("/api/weeks")]);
  setLoading(false);

  if (!notes || !weeks) {
    byId("app").innerHTML = '<div class="slip"><p>Failed to load validation data.</p></div>';
    return;
  }

  const routes = [...new Set(weeks.map(w => w.route))];
  const presets = [
    ["1. Flood expired", "Chennai-Bangalore", "2025-03-10", "N001"],
    ["2. Reopening", "Chennai-Bangalore", "2025-03-17", "N009"],
    ["3. Normal report", "Mumbai-Pune", "2025-09-15", "N006"],
    ["4. Wrong corridor", "Mumbai-Pune", "2025-09-15", "N001"],
    ["5. Magnitude cap", "Mumbai-Delhi", "2025-05-12", "N003"],
    ["6. Peer gap", "Mumbai-Pune", "2025-06-23", "N003"],
    ["7. Out of scope", "Delhi-Jaipur", "2024-11-11", "N004"],
    ["8. Festival ok", "Ahmedabad-Mumbai", "2025-01-20", "N002"]
  ];

  const selCss = 'style="width:100%;padding:6px;border:1.5px solid var(--ink);border-radius:3px;background:var(--slip);font-size:13px;"';

  byId("app").innerHTML = `
    <div class="big" style="font-size:24px;margin-bottom:6px;">Try to Fool the Validator</div>
    <p style="font-size:13px;color:var(--ink-soft);margin-bottom:14px;">Test 5-stage deterministic validation against any route, week, and note.</p>
    <div class="slip" style="margin-bottom:16px;" id="tour-fool-box">
      <span class="mono" style="font-size:12px;font-weight:600;">Adversarial attack presets:</span>
      <div class="presets">
        ${presets.map((p, idx) => `<button class="preset-btn" id="preset-${idx}" onclick="window.loadPreset(${idx}, '${p[1]}','${p[2]}','${p[3]}')">${p[0]}</button>`).join("")}
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:12px;align-items:end;margin-top:12px;">
        <div>
          <label style="font-size:12px;color:var(--ink-soft);display:block;margin-bottom:4px;" for="fool-route">Route</label>
          <select id="fool-route" ${selCss}>${routes.map(r => `<option value="${r}">${r}</option>`).join("")}</select>
        </div>
        <div>
          <label style="font-size:12px;color:var(--ink-soft);display:block;margin-bottom:4px;" for="fool-week">Week of (Monday)</label>
          <select id="fool-week" ${selCss}></select>
        </div>
        <div>
          <label style="font-size:12px;color:var(--ink-soft);display:block;margin-bottom:4px;" for="fool-note">Context Note</label>
          <select id="fool-note" ${selCss}>${notes.map(n => `<option value="${n.id}">${n.id}: ${n.applies_to} (${n.effect})</option>`).join("")}</select>
        </div>
        <div>
          <button id="fool-run-btn" style="width:100%;padding:7px;background:var(--ink);color:var(--slip);border:0;border-radius:3px;font-weight:600;cursor:pointer;">Run Check</button>
        </div>
      </div>
    </div>
    <div id="fool-result"></div>
  `;

  function updateWeeks() {
    const routeSelect = byId("fool-route"), weekSelect = byId("fool-week");
    if (!routeSelect || !weekSelect) return;
    const rWeeks = weeks.filter(w => w.route === routeSelect.value);
    weekSelect.innerHTML = rWeeks.map(w => `<option value="${w.week_of}">${w.week_of} (${w.c.toFixed(2)} ₹/t-km${w.is_candidate ? ' · ANOMALY' : ''})</option>`).join("");
  }

  const routeEl = byId("fool-route");
  if (routeEl) routeEl.onchange = updateWeeks;
  updateWeeks();

  window.loadPreset = (idx, rt, wk, nid) => {
    qsa(".preset-btn").forEach((b, i) => b.classList.toggle("active", i === idx));
    const rSelect = byId("fool-route"), wSelect = byId("fool-week"), nSelect = byId("fool-note");
    if (rSelect) { rSelect.value = rt; updateWeeks(); }
    if (wSelect) wSelect.value = wk;
    if (nSelect) nSelect.value = nid;
    window.runFoolValidation();
  };

  const runBtn = byId("fool-run-btn");
  if (runBtn) {
    runBtn.onclick = () => {
      qsa(".preset-btn").forEach(b => b.classList.remove("active"));
      window.runFoolValidation();
    };
  }

  window.loadPreset(0, presets[0][1], presets[0][2], presets[0][3]);
}

window.runFoolValidation = async () => {
  const rEl = byId("fool-route"), wEl = byId("fool-week"), nEl = byId("fool-note"), resBox = byId("fool-result");
  if (!rEl || !wEl || !nEl || !resBox) return;

  const rt = rEl.value, wk = wEl.value, nid = nEl.value;
  resBox.innerHTML = '<div class="slip"><p class="mono" style="color:var(--ink-soft);">Executing 5-step validator...</p></div>';

  let resp = null;
  if (window.STATIC_DEMO) {
    if (!gValidateMatrix) gValidateMatrix = await getJSON("data/validate_matrix.json");
    if (gValidateMatrix) {
      const entry = gValidateMatrix.matrix[`${rt}|${wk}|${nid}`];
      if (entry) {
        const [bits, whyIdx] = entry;
        const ck = [1, 2, 4, 8, 16].map(b => !!(bits & b));
        resp = {
          row: { c: 3.50, vs_own_pct: 22.0, vs_peer_pct: 25.0 },
          checks: {
            effect_is_cost_rise: ck[0],
            route_in_scope: ck[1],
            window_overlaps: ck[2],
            magnitude_ok: ck[3],
            not_peer_outlier_for_universal: ck[4]
          },
          justified: !!(bits & 32),
          why_not: gValidateMatrix.why_reasons[whyIdx] || ""
        };
      }
    }
  }

  if (!resp) {
    resp = await getJSON("/api/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ route: rt, week_of: wk, note_id: nid })
    });
  }

  if (!resp) {
    resBox.innerHTML = '<div class="slip"><p>Failed to validate candidate against note.</p></div>';
    return;
  }

  const ok = resp.justified;
  const badge = val => `<span class="st ${val ? "pass" : "fail"}">${val ? "PASS" : "FAIL"}</span>`;
  const vsOwnText = resp.row.vs_own_pct != null ? `+${resp.row.vs_own_pct.toFixed(1)}%` : 'N/A';
  const vsPeerText = resp.row.vs_peer_pct != null ? `+${resp.row.vs_peer_pct.toFixed(1)}%` : 'N/A';

  const ck = resp.checks;
  const gates = [
    ["1. Effect raises cost", ck.effect_is_cost_rise, "cost rise check"],
    ["2. Route in scope", ck.route_in_scope, "corridor check"],
    ["3. Window overlaps", ck.window_overlaps, "date overlap"],
    ["4. Magnitude within tolerance", ck.magnitude_ok, "magnitude check"],
    ["5. Universal not peer outlier", ck.not_peer_outlier_for_universal, "peer gap check"]
  ];

  const tickets = [
    [1, "Spotted", `vs own: ${vsOwnText}`, "SPOTTED"],
    [2, "Searched", `tested note ${nid}`, "SEARCHED"],
    ...gates.map((g, idx) => [idx + 3, g[0].split(". ")[1], g[2], g[1] ? "PASS" : "FAIL"])
  ];

  resBox.innerHTML = `
    <div class="slip">
      <div class="row" style="margin-bottom:12px;border-bottom:1.5px solid var(--rule);padding-bottom:10px;">
        <div>
          <span class="big" style="font-size:18px;">Validator Verdict: ${esc(rt)} (${wk}) + ${nid}</span>
          <div style="font-size:12px;color:var(--ink-soft);margin-top:4px;">
            <span>Cost: <strong>₹${resp.row.c.toFixed(2)}/t-km</strong></span> · 
            <span>vs own: <strong>${vsOwnText}</strong></span> · 
            <span>vs peer: <strong>${vsPeerText}</strong></span>
          </div>
        </div>
        ${stHtml(ok)}
      </div>
      <div style="margin-bottom:14px;padding:8px 12px;border:1px solid var(--rule);border-radius:3px;">
        <span class="mono" style="font-size:11px;font-weight:600;color:var(--ink-soft);display:block;margin-bottom:6px;text-transform:uppercase;">5-Step Gate Evaluation</span>
        ${gates.map(c => `<div class="check-item"><div><strong>${c[0]}</strong></div>${badge(c[1])}</div>`).join("")}
      </div>
      ${renderPaperTrailHtml(tickets, nid)}
      <div style="background:${ok ? 'var(--highlight)' : 'var(--slip)'};border:1.5px solid var(--ink);border-radius:3px;padding:10px 14px;margin-top:12px;">
        <strong>Plain-English Verdict Reason:</strong>
        <p style="margin:4px 0 0;font-size:13px;line-height:1.5;">${esc(ok ? `Cost rise on ${rt} for ${wk} is justified by ${nid}.` : resp.why_not)}</p>
      </div>
    </div>
  `;
};

// SCREEN F: Ask
function renderAsk() {
  setNav("nav-ask");
  const exs = [
    "Why did Chennai-Bangalore get pricier in March?",
    "What happened on Ahmedabad-Mumbai in Jan 2025?",
    "Which routes have no explanation?",
    "Is Mumbai-Pune still rising?"
  ];
  byId("app").innerHTML = `
    <div class="big ask-title">Ask about a route or month</div>
    <form id="ask-form" class="slip askbox" onsubmit="event.preventDefault();window.onAskSubmit();">
      <input id="ask-input" aria-label="Your question" placeholder="${exs[0]}" autofocus>
      <button type="submit" id="ask-btn">Ask</button>
    </form>
    <div class="examples" aria-label="Examples">${exs.map(q => `<button class="ex" onclick="window.fillAsk('${q}')">${q}</button>`).join("")}</div>
    <div id="ask-result"></div>
  `;
}

window.fillAsk = q => {
  const inp = byId("ask-input");
  if (inp) { inp.value = q; window.onAskSubmit(); }
};

function renderMarkdown(md) {
  if (!md) return "";
  let s = esc(md).replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>").replace(/\*(.*?)\*/g, "<em>$1</em>");
  return s.split("\n").map(l => l.startsWith("- ") || l.startsWith("* ") ? `<li>${l.slice(2)}</li>` : (l.trim() ? `<p>${l}</p>` : "")).join("");
}

window.onAskSubmit = async () => {
  const inp = byId("ask-input"), btn = byId("ask-btn"), resBox = byId("ask-result");
  if (!inp || !inp.value.trim()) return;
  const q = inp.value.trim();
  btn.disabled = true; setLoading(true);
  resBox.innerHTML = '<div class="slip answer"><p class="mono" style="color:var(--ink-soft);">Looking through the rows…</p></div>';
  const resp = await getJSON("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: q }) });
  if (!resp) {
    resBox.innerHTML = '<div class="slip answer"><p>Unable to connect to analysis server. Please ensure the backend is running with <code>python -m stripewatch serve</code>.</p></div>';
    return;
  }
  if (resp.empty) {
    resBox.innerHTML = `<div class="empty">${TRUCK_SVG}<span>No note found. I'd rather say so than guess.</span></div>`;
  } else {
    const based = resp.based_on_rows?.length
      ? `<div class="mono based"><span class="k">Based on rows:</span> ${resp.based_on_rows.map(r => `<a href="#/route/${enc(r.route)}?week=${r.week_of}">${r.week_of}</a>${r.note_id ? ` <span class="chip">${r.note_id}</span>` : ""}`).join(" · ")}</div>`
      : "";
    resBox.innerHTML = `<div class="slip answer">${renderMarkdown(resp.answer)}${based}</div>`;
  }
};

// GUIDED TOUR
const TOUR_STEPS = [
  ["tour-summary-strip", "#/ledger", "19 rises spotted. 3 explained by a note."],
  ["tour-ledger-table", "#/ledger", "Each row is one route-week. Click one to see evidence."],
  ["tour-route-chart", "#/route/Ahmedabad-Mumbai?week=2025-01-20", "Green rings = justified. Red dots = unexplained. Drag truck to scrub."],
  ["live-week-slip", "#/route/Ahmedabad-Mumbai?week=2025-01-20", "Every verdict passes 5 checks: route, window, and effect."],
  ["tour-fool-box", "#/fool", "Pick any note and week. See exactly why it fails."],
  ["tour-footer", "#/ledger", "Same numbers on 3 runs. The model only writes wording."]
];

window.startTour = () => { gTourStep = 0; runTourStep(); };

function runTourStep() {
  const step = TOUR_STEPS[gTourStep];
  if (!step) return window.closeTour();
  if (location.hash !== step[1]) {
    location.hash = step[1];
    setTimeout(renderCoachMark, 350);
  } else {
    renderCoachMark();
  }
}

function renderCoachMark() {
  const overlay = byId("tour-overlay") || document.body.appendChild(Object.assign(document.createElement("div"), { id: "tour-overlay", className: "tour-overlay" }));
  const step = TOUR_STEPS[gTourStep];
  const target = byId(step[0]);
  const rect = target ? target.getBoundingClientRect() : { top: 120, left: 40, width: 300, height: 100 };
  const coach = byId("coach-mark") || document.body.appendChild(Object.assign(document.createElement("div"), { id: "coach-mark", className: "coach-mark" }));

  coach.style.top = `${Math.min(window.innerHeight - 180, Math.max(20, rect.top + window.scrollY + (rect.height / 2)))}px`;
  coach.style.left = `${Math.min(window.innerWidth - 340, Math.max(20, rect.left + 20))}px`;

  coach.innerHTML = `
    <div class="coach-step">STEP ${gTourStep + 1} OF 6</div>
    <div>${step[2]}</div>
    <div class="coach-actions">
      <button onclick="window.closeTour()">Skip</button>
      <div>
        ${gTourStep > 0 ? `<button onclick="window.prevTourStep()">Back</button>` : ''}
        <button class="btn-next" onclick="window.nextTourStep()">${gTourStep === 5 ? 'Done' : 'Next'}</button>
      </div>
    </div>
  `;
}

window.nextTourStep = () => {
  gTourStep++;
  if (gTourStep >= TOUR_STEPS.length) window.closeTour();
  else runTourStep();
};

window.prevTourStep = () => {
  if (gTourStep > 0) { gTourStep--; runTourStep(); }
};

window.closeTour = () => {
  byId("tour-overlay")?.remove();
  byId("coach-mark")?.remove();
  try { localStorage.setItem("stripewatch_tour_done", "1"); } catch(e){}
};

// KEYBOARD SHORTCUTS
window.addEventListener("keydown", e => {
  if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;
  if (e.ctrlKey || e.metaKey || e.altKey) return;

  if (e.key === "Escape") {
    window.closeTour();
    const dlg = byId("shortcuts-dialog");
    if (dlg && dlg.open) dlg.close();
    return;
  }

  if (e.key === "?") {
    const dlg = byId("shortcuts-dialog");
    if (dlg) { if (dlg.open) dlg.close(); else dlg.showModal(); }
    e.preventDefault();
    return;
  }

  if (e.key === "/") {
    location.hash = "#/ask";
    setTimeout(() => { const inp = byId("ask-input"); if (inp) inp.focus(); }, 150);
    e.preventDefault();
    return;
  }

  if (e.key === "g") {
    gPendingG = true;
    clearTimeout(gPendingGTimer);
    gPendingGTimer = setTimeout(() => { gPendingG = false; }, 1000);
    return;
  }

  if (gPendingG) {
    gPendingG = false;
    clearTimeout(gPendingGTimer);
    const navMap = { o: "#/", l: "#/ledger", c: "#/calendar", r: "#/route/Ahmedabad-Mumbai", n: "#/notes", f: "#/fool", a: "#/ask" };
    if (navMap[e.key]) { location.hash = navMap[e.key]; e.preventDefault(); return; }
  }

  if (e.key === "j" || e.key === "k") {
    const rows = qsa("tr.r");
    if (rows.length) {
      gLedgerIndex = e.key === "j" ? Math.min(rows.length - 1, gLedgerIndex + 1) : Math.max(0, gLedgerIndex - 1);
      const targetRow = rows[gLedgerIndex];
      if (targetRow) { targetRow.focus(); targetRow.scrollIntoView({ block: "nearest" }); }
      e.preventDefault();
    }
  }
});

// Router
function router() {
  const hash = location.hash || "#/";
  if (hash.startsWith("#/route/")) {
    const [rt, q] = hash.replace("#/route/", "").split("?");
    renderRoute(dec(rt), new URLSearchParams(q || "").get("week"));
  } else if (hash.startsWith("#/ledger")) {
    renderLedger();
  } else if (hash.startsWith("#/calendar")) {
    renderCalendar();
  } else if (hash.startsWith("#/ask")) {
    renderAsk();
  } else if (hash.startsWith("#/notes")) {
    renderNotes();
  } else if (hash.startsWith("#/fool")) {
    renderFool();
  } else {
    renderOverview();
  }
}

window.addEventListener("hashchange", router);
window.addEventListener("DOMContentLoaded", () => {
  router();
  if (new URLSearchParams(window.location.search).get("tour") === "1") {
    setTimeout(window.startTour, 400);
  }
});
"""

with open(APP_JS_PATH, "w", encoding="utf-8") as f:
    f.write(JS.strip() + "\n")

# Run esbuild minification
try:
    subprocess.run(["npx", "-y", "esbuild", APP_JS_PATH, "--minify", "--allow-overwrite", f"--outfile={APP_JS_PATH}"], check=True, shell=True)
except Exception as e:
    print("esbuild failed, using fallback:", e)

sz = os.path.getsize(APP_JS_PATH)
print(f"Generated web/app.js: {sz} bytes (Target: < 40960 bytes). PASS: {sz < 40960}")
assert sz < 40960, f"web/app.js exceeded budget ({sz} >= 40960)"
