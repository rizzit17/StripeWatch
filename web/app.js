const TRUCK_FLAG_SVG = `<svg width="34" height="22" viewBox="0 0 34 22" aria-hidden="true"><rect x="1" y="7" width="17" height="9" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1.5"/><path d="M18 9h6l4 4v3H18z" fill="#E4932A" stroke="#1D1B16" stroke-width="1.5"/><circle cx="8" cy="18" r="2.5" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1.5"/><circle cx="24" cy="18" r="2.5" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1.5"/><path d="M6 7V1h6l-1.5 2L12 5H7" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1"/></svg>`;

let curTab = "All", curRoute = "All routes", curSort = "week";
const pct = v => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
const formatINR = v => (v === null || v === undefined) ? "—" : "₹" + Number(v).toLocaleString("en-IN");

async function getJSON(url, opts) {
  try {
    const res = await fetch(url, opts);
    return res.ok ? await res.json() : null;
  } catch (e) { return null; }
}

function setNav(id) {
  document.querySelectorAll(".nav a").forEach(a => a.classList.toggle("active", a.id === id));
}

function setLoading(load) {
  const t = document.getElementById("truck-icon");
  if (t) t.classList.toggle("loading-truck", !!load);
}

// ==========================================
// SCREEN A: Ledger (with Excess spend column)
// ==========================================
async function renderLedger() {
  setNav("nav-ledger");
  const app = document.getElementById("app");
  setLoading(true);
  const [sum, rows] = await Promise.all([
    getJSON("/api/summary"),
    getJSON(`/api/rows?sort_by=${curSort === "excess" ? "excess" : "week"}`)
  ]);
  setLoading(false);

  if (!sum || !rows) {
    app.innerHTML = '<div class="slip"><p>Failed to load ledger data.</p></div>';
    return;
  }

  const routes = ["All routes", ...new Set(rows.map(r => r.route))];
  let list = rows;
  if (curRoute !== "All routes") list = list.filter(r => r.route === curRoute);
  if (curTab === "Flagged") list = list.filter(r => r.verdict === "unexplained");
  else if (curTab === "Justified") list = list.filter(r => r.verdict === "justified");

  const trs = list.map(r => {
    const ok = r.verdict === "justified";
    const st = `<span class="st ${ok ? "ok" : "flag"}" aria-label="${ok ? "JUSTIFIED" : "FLAGGED"}">${ok ? "JUSTIFIED" : "FLAGGED"}</span>`;
    const chip = (ok && r.matched_note_id) ? `<span class="chip">${r.matched_note_id}</span>` : "—";
    const tgt = `#/route/${encodeURIComponent(r.route)}?week=${r.week_of}`;
    const exc = r.excess_inr ? formatINR(r.excess_inr) : "—";
    return `<tr class="r" tabindex="0" onclick="location.hash='${tgt}'" onkeydown="if(event.key==='Enter')location.hash='${tgt}'"><td class="mono">${r.week_of}</td><td><strong>${r.route}</strong></td><td class="mono">${r.c.toFixed(2)}</td><td class="mono">▲ ${pct(r.vs_own_pct)}</td><td class="mono">${pct(r.vs_peer_pct)}</td><td class="mono">${exc}</td><td>${st}</td><td>${chip}</td></tr>`;
  }).join("");

  const card = (n, lbl, cls="") => `<div class="slip"><div class="big num ${cls}">${n}</div><div class="lbl">${lbl}</div></div>`;
  const ths = ["Week of", "Route", "₹/t-km", "vs own", "vs peers", "Excess ₹", "Verdict", "Note"].map(h => `<th scope="col">${h}</th>`).join("");

  app.innerHTML = `
    <h2 class="sr-only">StripeWatch ledger: ${sum.rises} cost rises spotted</h2>
    <section class="summary" aria-label="Overview">
      ${card(sum.rises, "rises spotted")}${card(sum.justified, "justified by a note", "green")}${card(sum.flagged, "need a human look", "red")}
    </section>
    <p class="mono" style="margin: -6px 0 16px; color: var(--ink-soft); font-size: 13px;">Estimated excess on unexplained rises: ₹1.28 lakh (total ₹1,28,126 vs own trailing baseline)</p>
    <div class="filters">
      <label for="route-select">Route</label>
      <select id="route-select" aria-label="Filter by route">
        ${routes.map(rt => `<option value="${rt}" ${curRoute === rt ? "selected" : ""}>${rt}</option>`).join("")}
      </select>
      <span class="sort-toggle">
        <span>Sort by:</span>
        <button id="sort-week" class="${curSort === 'week' ? 'active' : ''}">week</button>
        <button id="sort-excess" class="${curSort === 'excess' ? 'active' : ''}">excess ₹</button>
      </span>
      <span class="tabs" role="tablist" aria-label="Filter verdict">
        ${["All", "Flagged", "Justified"].map(t => `<button role="tab" id="tab-${t.toLowerCase()}" aria-pressed="${curTab === t}">${t}</button>`).join("")}
      </span>
    </div>
    <div class="slip ledger">
      <table aria-label="Ledger">
        <thead><tr>${ths}</tr></thead>
        <tbody>${trs || '<tr><td colspan="8" style="text-align:center;padding:18px;">No matching rows found.</td></tr>'}</tbody>
      </table>
    </div>
    <p class="mono footer">notes: 10 · LLM calls: ${sum.llm_calls} · temp: ${sum.temperature} · ${sum.repro_identical ? "identical on 3 runs ✓" : "reproducible"}</p>
  `;

  document.getElementById("route-select").onchange = e => { curRoute = e.target.value; renderLedger(); };
  document.getElementById("sort-week").onclick = () => { curSort = "week"; renderLedger(); };
  document.getElementById("sort-excess").onclick = () => { curSort = "excess"; renderLedger(); };
  ["All", "Flagged", "Justified"].forEach(t => {
    document.getElementById("tab-" + t.toLowerCase()).onclick = () => { curTab = t; renderLedger(); };
  });
}

// ==========================================
// SCREEN B: Route Page (Attribution + Creep)
// ==========================================
async function renderRoute(route, targetWk) {
  setNav("nav-routes");
  const app = document.getElementById("app");
  setLoading(true);
  const data = await getJSON(`/api/route/${encodeURIComponent(route)}`);
  setLoading(false);

  if (!data) {
    app.innerHTML = `<div class="slip"><p>Route '${route}' not found.</p><a href="#/">← Back to Ledger</a></div>`;
    return;
  }

  const { route_type, series, candidates, attribution } = data;
  let pts = series;
  if (series.length > 20 && candidates.length > 0) {
    const sel = targetWk || candidates[0].week_of;
    const idx = series.findIndex(s => s.week_of === sel);
    if (idx !== -1) pts = series.slice(Math.max(0, idx - 4), Math.min(series.length, Math.max(0, idx - 4) + 16));
  }

  const n = pts.length;
  const allVals = pts.flatMap(s => [s.c, s.own_avg]).filter(v => v !== null && v !== undefined);
  const maxVal = Math.max(...allVals, 1.0);
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
    
    // Anomaly dots
    const cRow = candMap[p.week_of];
    if (cRow) {
      const ok = cRow.verdict === "justified";
      dots += `<circle cx="${x.toFixed(1)}" cy="${yW.toFixed(1)}" r="6" fill="${ok ? "#FFFDF7" : "#C8452D"}" ${ok ? 'stroke="#2E7A5B" stroke-width="2.5"' : ''} tabindex="0" aria-label="${ok ? 'Justified' : 'Flagged'}: ${p.week_of}"><title>${p.week_of} (${ok ? 'JUSTIFIED' : 'FLAGGED'}): ₹${p.c.toFixed(2)}/t-km ${ok ? `(${cRow.matched_note_id})` : `(+${cRow.vs_own_pct.toFixed(1)}%)`}</title></circle>`;
    }
    
    // Creep early warning tick mark
    if (p.creep_tag) {
      creepTicks += `<polygon points="${x.toFixed(1)},145 ${(x-3).toFixed(1)},151 ${(x+3).toFixed(1)},151" fill="#E4932A"><title>${p.week_of}: peer gap sustained 4 weeks (rolling gap: +${p.peer_gap_4w}%)</title></polygon>`;
    }
  });

  const gridHtml = [30, 80, 130].map((y, idx) => `<line x1="40" y1="${y}" x2="620" y2="${y}" stroke="#D9D0BC" stroke-dasharray="2 4"/><text x="4" y="${y+4}">${[yTop, yMid, yBot][idx].toFixed(2)}</text>`).join("");

  const slips = candidates.map(c => {
    const ok = c.verdict === "justified";
    const st = `<span class="st ${ok ? "ok" : "flag"}" aria-label="${ok ? "JUSTIFIED" : "FLAGGED"}">${ok ? "JUSTIFIED" : "FLAGGED"}</span>`;
    let body = ok && c.evidence_packet?.note 
      ? `<p class="cited"><span class="chip plain">${c.evidence_packet.note.id}</span> ${c.evidence_packet.note.rationale || c.evidence_packet.note.text}</p>`
      : '<p>No matching note found. Looks unexplained, worth a human look.</p>';
    const nms = c.evidence_packet?.near_misses || [];
    if (!ok && nms.length) {
      body += `<p class="rejected">Closest notes I rejected:<br>${nms.map(m => `<span class="chip plain">${m.id}</span> ${m.why_not}`).join('<br>')}</p>`;
    }
    const excStr = c.excess_inr ? ` · <span class="mono">excess: ${formatINR(c.excess_inr)}</span>` : "";
    return `<div class="slip"><div class="row"><span class="mono">week of ${c.week_of}</span>${st}</div><p><span class="mono">${c.c.toFixed(2)} ₹/t-km</span> · ${pct(c.vs_own_pct)} vs own · ${pct(c.vs_peer_pct)} vs peers${excStr}</p>${body}</div>`;
  }).join("");

  // Attribution slip
  let attrSlip = "";
  if (attribution && attribution.length > 0) {
    const attrItems = attribution.map(ep => {
      return `
        <div style="border-bottom: 1px dotted var(--rule); padding: 8px 0;">
          <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
            <span class="mono" style="font-weight:600;">Episode: ${ep.start} to ${ep.end} (${ep.weeks_count} candidate weeks)</span>
            <span class="mono tag">${ep.verdict}</span>
          </div>
          <p style="font-size:12px; margin:2px 0; color:var(--ink-soft);">${ep.transporter?.verdict ? `<strong>Transporter:</strong> ${ep.transporter.verdict}` : ''}</p>
        </div>
      `;
    }).join("");
    attrSlip = `
      <div class="slip" style="margin-bottom:16px;">
        <div class="row"><span class="big" style="font-size:16px;">Where the rise sits (Attribution check)</span><span class="mono tag">DATA ONLY · NO CAUSES INVENTED</span></div>
        <p style="font-size:12px; color:var(--ink-soft); margin-bottom:10px;">Shows whether an episode of cost rises was concentrated in specific transporters or spread route-wide.</p>
        ${attrItems}
      </div>
    `;
  }

  const rStart = pts[0].week_of, rEnd = pts[pts.length - 1].week_of;
  app.innerHTML = `
    <div style="margin-bottom:12px;"><a href="#/" style="color:var(--ink-soft);text-decoration:none;font-size:13px;">← Back to Ledger</a></div>
    <div class="route-head"><span class="big title">${route}</span><span class="mono tag">${route_type.toUpperCase()}</span><span class="mono range">${rStart} to ${rEnd}</span></div>
    <div class="slip chart">
      <svg width="100%" height="190" viewBox="0 0 640 190" role="img" aria-label="Freight cost chart for ${route}" font-family="'JetBrains Mono',monospace" font-size="11" fill="#6B665A">
        ${gridHtml}
        <path d="${oPath}" stroke="#6B665A" stroke-width="1.2" stroke-dasharray="5 4" fill="none"/>
        <path d="${wPath}" stroke="#1D1B16" stroke-width="1.8" fill="none"/>
        ${dots}
        ${creepTicks}
        <text x="60" y="170">${rStart}</text>
        <text x="310" y="170" text-anchor="middle">${pts[Math.floor(n/2)].week_of}</text>
        <text x="600" y="170" text-anchor="end">${rEnd}</text>
      </svg>
      <div class="mono legend">
        <span>━ weekly ₹/t-km</span>
        <span>┅ own 8-week average</span>
        <span class="g">◯ justified</span>
        <span class="r">● flagged</span>
        <span style="color:var(--tiger);">▲ peer gap sustained 4w</span>
      </div>
      <details style="margin-top:8px;"><summary>Data table</summary><table style="width:100%;font-size:11px;margin-top:8px;"><tr><th>Week</th><th>₹/t-km</th><th>Own avg</th><th>Excess ₹</th><th>Verdict</th></tr>${pts.map(p => `<tr><td>${p.week_of}</td><td>${p.c.toFixed(2)}</td><td>${p.own_avg ? p.own_avg.toFixed(2) : "—"}</td><td>${formatINR(p.excess_inr)}</td><td>${candMap[p.week_of]?.verdict || "normal"}</td></tr>`).join("")}</table></details>
    </div>
    ${attrSlip}
    <div class="slips">${slips || '<div class="slip"><p>No cost rise candidates on this route.</p></div>'}</div>
  `;
}

// ==========================================
// SCREEN C: Notes Page (Feature 3)
// ==========================================
async function renderNotes() {
  setNav("nav-notes");
  const app = document.getElementById("app");
  setLoading(true);
  const notes = await getJSON("/api/notes");
  setLoading(false);

  if (!notes) {
    app.innerHTML = '<div class="slip"><p>Failed to load notes.</p></div>';
    return;
  }

  const slips = notes.map(n => {
    let stampCls = "flag", stampTxt = "CAN'T JUSTIFY";
    if (n.effect === "raises") {
      if (n.scope === "ALL") {
        stampCls = "warn";
        stampTxt = "CAN JUSTIFY (CAPPED)";
      } else {
        stampCls = "ok";
        stampTxt = "CAN JUSTIFY";
      }
    }
    const st = `<span class="st ${stampCls}">${stampTxt}</span>`;
    const win = `${n.start || n.date} to ${n.end || (n.effect === 'raises' ? 'ongoing' : 'normal')}`;
    return `
      <div class="slip">
        <div class="row">
          <div><span class="chip">${n.id}</span> <strong style="margin-left:6px;font-size:13px;">${n.applies_to}</strong></div>
          ${st}
        </div>
        <p style="font-size:12px;color:var(--ink-soft);margin:4px 0 8px;">Scope: <strong>${n.scope}</strong> · Effect: <strong>${n.effect}</strong> · Window: <strong>${win}</strong></p>
        <p class="cited" style="font-size:12px;margin:6px 0;">"${n.text}"</p>
        <p class="rejected" style="font-size:12px;color:var(--ink);"><strong>Rationale:</strong> ${n.rationale || "—"}</p>
      </div>
    `;
  }).join("");

  app.innerHTML = `
    <div class="big" style="font-size:24px;margin-bottom:6px;">Context Notes Register</div>
    <div class="slip" style="margin-bottom:16px;background:var(--highlight);border:1px dashed var(--ink);">
      <p style="margin:0;font-size:13px;line-height:1.5;"><strong>Ground truth principle:</strong> 3 of 10 notes can ever justify a cost rise. The other 7 are close in wording but say costs weren't affected, apply elsewhere, or mark the end of a disruption.</p>
    </div>
    <div class="slips">${slips}</div>
  `;
}

// ==========================================
// SCREEN D: "Try to fool it" Console (Feature 1)
// ==========================================
async function renderFool() {
  setNav("nav-fool");
  const app = document.getElementById("app");
  setLoading(true);
  const [notes, weeks] = await Promise.all([getJSON("/api/notes"), getJSON("/api/weeks")]);
  setLoading(false);

  if (!notes || !weeks) {
    app.innerHTML = '<div class="slip"><p>Failed to load validation data.</p></div>';
    return;
  }

  const routes = [...new Set(weeks.map(w => w.route))];
  const presets = [
    { label: "1. Chennai flood expired (03-10 + N001)", route: "Chennai-Bangalore", week: "2025-03-10", note: "N001" },
    { label: "2. Reopening note (03-17 + N009)", route: "Chennai-Bangalore", week: "2025-03-17", note: "N009" },
    { label: "3. No disruption report (09-15 + N006)", route: "Mumbai-Pune", week: "2025-09-15", note: "N006" },
    { label: "4. Wrong corridor (Mumbai-Pune + N001)", route: "Mumbai-Pune", week: "2025-09-15", note: "N001" },
    { label: "5. Magnitude cap exceeded (05-12 + N003)", route: "Mumbai-Delhi", week: "2025-05-12", note: "N003" },
    { label: "6. Nationwide peer gap (06-23 + N003)", route: "Mumbai-Pune", week: "2025-06-23", note: "N003" },
    { label: "7. Out of scope note (Delhi-Jaipur + N004)", route: "Delhi-Jaipur", week: "2024-11-11", note: "N004" },
    { label: "8. Festival accepted control (01-20 + N002)", route: "Ahmedabad-Mumbai", week: "2025-01-20", note: "N002" }
  ];

  app.innerHTML = `
    <div class="big" style="font-size:24px;margin-bottom:6px;">Try to Fool the Validator</div>
    <p style="font-size:13px;color:var(--ink-soft);margin-bottom:14px;">Test our 5-stage deterministic validation guardrail against any route, calendar week, and context note.</p>
    
    <div class="slip" style="margin-bottom:16px;">
      <span class="mono" style="font-size:12px;font-weight:600;">Adversarial attack presets:</span>
      <div class="presets">
        ${presets.map((p, idx) => `<button class="preset-btn" onclick="window.loadPreset('${p.route}','${p.week}','${p.note}')">${p.label}</button>`).join("")}
      </div>
      
      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:12px;align-items:end;margin-top:12px;">
        <div>
          <label style="font-size:12px;color:var(--ink-soft);display:block;margin-bottom:4px;" for="fool-route">Route</label>
          <select id="fool-route" style="width:100%;padding:6px;border:1.5px solid var(--ink);border-radius:3px;background:var(--slip);font-size:13px;">
            ${routes.map(r => `<option value="${r}">${r}</option>`).join("")}
          </select>
        </div>
        <div>
          <label style="font-size:12px;color:var(--ink-soft);display:block;margin-bottom:4px;" for="fool-week">Week of (Monday)</label>
          <select id="fool-week" style="width:100%;padding:6px;border:1.5px solid var(--ink);border-radius:3px;background:var(--slip);font-size:13px;"></select>
        </div>
        <div>
          <label style="font-size:12px;color:var(--ink-soft);display:block;margin-bottom:4px;" for="fool-note">Context Note</label>
          <select id="fool-note" style="width:100%;padding:6px;border:1.5px solid var(--ink);border-radius:3px;background:var(--slip);font-size:13px;">
            ${notes.map(n => `<option value="${n.id}">${n.id}: ${n.applies_to} (${n.effect})</option>`).join("")}
          </select>
        </div>
        <div>
          <button id="fool-run-btn" style="width:100%;padding:7px;background:var(--ink);color:var(--slip);border:0;border-radius:3px;font-weight:600;cursor:pointer;">Run Check</button>
        </div>
      </div>
    </div>
    
    <div id="fool-result"></div>
  `;

  const routeSelect = document.getElementById("fool-route");
  const weekSelect = document.getElementById("fool-week");

  function updateWeeks() {
    const selRoute = routeSelect.value;
    const rWeeks = weeks.filter(w => w.route === selRoute);
    weekSelect.innerHTML = rWeeks.map(w => `<option value="${w.week_of}">${w.week_of} (${w.c.toFixed(2)} ₹/t-km${w.is_candidate ? ' · ANOMALY' : ''})</option>`).join("");
  }

  routeSelect.onchange = updateWeeks;
  updateWeeks();

  window.loadPreset = (rt, wk, nid) => {
    routeSelect.value = rt;
    updateWeeks();
    weekSelect.value = wk;
    document.getElementById("fool-note").value = nid;
    window.runFoolValidation();
  };

  document.getElementById("fool-run-btn").onclick = () => window.runFoolValidation();
}

window.runFoolValidation = async () => {
  const rt = document.getElementById("fool-route").value;
  const wk = document.getElementById("fool-week").value;
  const nid = document.getElementById("fool-note").value;
  const resBox = document.getElementById("fool-result");

  resBox.innerHTML = '<div class="slip"><p class="mono" style="color:var(--ink-soft);">Executing 5-step validator...</p></div>';
  setLoading(true);
  const resp = await getJSON("/api/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ route: rt, week_of: wk, note_id: nid })
  });
  setLoading(false);

  if (!resp) {
    resBox.innerHTML = '<div class="slip"><p>Failed to validate candidate against note.</p></div>';
    return;
  }

  const ok = resp.justified;
  const st = `<span class="st ${ok ? "ok" : "flag"}" style="font-size:12px;padding:4px 8px;">${ok ? "JUSTIFIED" : "REJECTED"}</span>`;
  const badge = val => `<span class="st ${val ? "pass" : "fail"}">${val ? "PASS" : "FAIL"}</span>`;

  const checkRows = [
    { name: "1. Effect describes cost rise", pass: resp.checks.effect_is_cost_rise, desc: `Effect: '${resp.note.effect}'` },
    { name: "2. Route in scope", pass: resp.checks.route_in_scope, desc: `Note scope: '${resp.note.scope}'` },
    { name: "3. Disruption window overlaps week", pass: resp.checks.window_overlaps, desc: `Window: ${resp.note.start} to ${resp.note.end || 'ongoing'}` },
    { name: "4. Magnitude within tolerance", pass: resp.checks.magnitude_ok, desc: `Rise: +${resp.row.vs_own_pct || 0}% vs mag: ~${resp.note.mag_max || 'N/A'}%` },
    { name: "5. Universal note is not peer outlier", pass: resp.checks.not_peer_outlier_for_universal, desc: `Peer gap: +${resp.row.vs_peer_pct || 0}%` }
  ];

  resBox.innerHTML = `
    <div class="slip">
      <div class="row" style="margin-bottom:12px;">
        <div>
          <span class="big" style="font-size:18px;">Validator Verdict: ${rt} (${wk}) + ${nid}</span>
          ${resp.note_comment ? `<p style="font-size:12px;color:var(--ink-soft);margin:2px 0;">${resp.note_comment}</p>` : ''}
        </div>
        ${st}
      </div>

      <div style="margin-bottom:14px;background:var(--slip);border:1px solid var(--rule);border-radius:3px;padding:8px 12px;">
        ${checkRows.map(c => `
          <div class="check-item">
            <div>
              <strong>${c.name}</strong>
              <span style="color:var(--ink-soft);margin-left:8px;font-size:12px;">(${c.desc})</span>
            </div>
            ${badge(c.pass)}
          </div>
        `).join("")}
      </div>

      <div style="background:${ok ? 'var(--highlight)' : 'var(--slip)'};border:1.5px solid var(--ink);border-radius:3px;padding:10px 14px;">
        <strong>Plain-English Verdict Reason:</strong>
        <p style="margin:4px 0 0;font-size:13px;line-height:1.5;">${ok ? `Cost rise on ${rt} for ${wk} is justified by ${nid} (${resp.note.start} to ${resp.note.end || 'ongoing'}).` : resp.why_not}</p>
      </div>
    </div>
  `;
};

// ==========================================
// SCREEN E: Ask
// ==========================================
function renderAsk() {
  setNav("nav-ask");
  const app = document.getElementById("app");
  const exs = [
    "Why did Chennai-Bangalore get pricier in March?",
    "What happened on Ahmedabad-Mumbai in Jan 2025?",
    "Which routes have no explanation?",
    "Is Mumbai-Pune still rising?"
  ];
  app.innerHTML = `
    <div class="big ask-title">Ask about a route or month</div>
    <form id="ask-form" class="slip askbox" onsubmit="event.preventDefault();window.onAskSubmit();">
      <input id="ask-input" aria-label="Your question" placeholder="Why did Chennai-Bangalore get pricier in March?" autofocus>
      <button type="submit" id="ask-btn">Ask</button>
    </form>
    <div class="examples" aria-label="Examples">${exs.map(q => `<button class="ex" onclick="window.fillAsk('${q}')">${q}</button>`).join("")}</div>
    <div id="ask-result"></div>
  `;
}

window.fillAsk = q => {
  const inp = document.getElementById("ask-input");
  if (inp) { inp.value = q; window.onAskSubmit(); }
};

function renderMarkdown(md) {
  if (!md) return "";
  let s = md.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  s = s.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/__(.*?)__/g, "<strong>$1</strong>");
  s = s.replace(/(^|[^\*])\*(?!\s)([^\*]+?)\*(?!\*)/g, "$1<em>$2</em>");

  const lines = s.split("\n");
  let inList = false;
  const out = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      if (inList) { out.push("</ul>"); inList = false; }
      continue;
    }
    const listMatch = trimmed.match(/^[\*\-]\s+(.*)$/);
    if (listMatch) {
      if (!inList) { out.push('<ul class="ask-list">'); inList = true; }
      out.push(`<li>${listMatch[1]}</li>`);
    } else {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push(`<p>${trimmed}</p>`);
    }
  }
  if (inList) out.push("</ul>");
  return out.join("");
}

window.onAskSubmit = async () => {
  const inp = document.getElementById("ask-input"), btn = document.getElementById("ask-btn"), resBox = document.getElementById("ask-result");
  if (!inp || !inp.value.trim()) return;
  const q = inp.value.trim();
  btn.disabled = true; setLoading(true);
  resBox.innerHTML = '<div class="slip answer"><p class="mono" style="color:var(--ink-soft);">Looking through the rows…</p></div>';
  const resp = await getJSON("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: q }) });
  btn.disabled = false; setLoading(false);
  if (!resp) { resBox.innerHTML = '<div class="slip"><p>Failed to contact server.</p></div>'; return; }
  if (resp.empty) {
    resBox.innerHTML = `<div class="empty">${TRUCK_FLAG_SVG}<span>No note found. I'd rather say so than guess.</span></div>`;
  } else {
    const based = resp.based_on_rows?.length
      ? `<div class="mono based"><span class="k">Based on rows:</span> ${resp.based_on_rows.map(r => `<a href="#/route/${encodeURIComponent(r.route)}?week=${r.week_of}">${r.week_of}</a>${r.note_id ? ` <span class="chip">${r.note_id}</span>` : ""}`).join(" · ")}</div>`
      : "";
    resBox.innerHTML = `<div class="slip answer">${renderMarkdown(resp.answer)}${based}</div>`;
  }
};

function router() {
  const hash = window.location.hash || "#/";
  if (hash.startsWith("#/route/")) {
    const [rt, q] = hash.replace("#/route/", "").split("?");
    renderRoute(decodeURIComponent(rt), new URLSearchParams(q || "").get("week"));
  } else if (hash.startsWith("#/ask")) {
    renderAsk();
  } else if (hash.startsWith("#/notes")) {
    renderNotes();
  } else if (hash.startsWith("#/fool")) {
    renderFool();
  } else {
    renderLedger();
  }
}

window.addEventListener("hashchange", router);
window.addEventListener("DOMContentLoaded", router);
