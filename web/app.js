const TRUCK_FLAG_SVG = `<svg width="34" height="22" viewBox="0 0 34 22" aria-hidden="true"><rect x="1" y="7" width="17" height="9" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1.5"/><path d="M18 9h6l4 4v3H18z" fill="#E4932A" stroke="#1D1B16" stroke-width="1.5"/><circle cx="8" cy="18" r="2.5" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1.5"/><circle cx="24" cy="18" r="2.5" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1.5"/><path d="M6 7V1h6l-1.5 2L12 5H7" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1"/></svg>`;

let curTab = "All", curRoute = "All routes";
const pct = v => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;

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

// Screen A: Ledger
async function renderLedger() {
  setNav("nav-ledger");
  const app = document.getElementById("app");
  setLoading(true);
  const [sum, rows] = await Promise.all([getJSON("/api/summary"), getJSON("/api/rows")]);
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
    return `<tr class="r" tabindex="0" onclick="location.hash='${tgt}'" onkeydown="if(event.key==='Enter')location.hash='${tgt}'"><td class="mono">${r.week_of}</td><td><strong>${r.route}</strong></td><td class="mono">${r.c.toFixed(2)}</td><td class="mono">▲ ${pct(r.vs_own_pct)}</td><td class="mono">${pct(r.vs_peer_pct)}</td><td>${st}</td><td>${chip}</td></tr>`;
  }).join("");

  const card = (n, lbl, cls="") => `<div class="slip"><div class="big num ${cls}">${n}</div><div class="lbl">${lbl}</div></div>`;
  const ths = ["Week of", "Route", "₹/t-km", "vs own", "vs peers", "Verdict", "Note"].map(h => `<th scope="col">${h}</th>`).join("");

  app.innerHTML = `
    <h2 class="sr-only">StripeWatch ledger: ${sum.rises} cost rises spotted</h2>
    <section class="summary" aria-label="Overview">
      ${card(sum.rises, "rises spotted")}${card(sum.justified, "justified by a note", "green")}${card(sum.flagged, "need a human look", "red")}
    </section>
    <div class="filters">
      <label for="route-select">Route</label>
      <select id="route-select" aria-label="Filter by route">
        ${routes.map(rt => `<option value="${rt}" ${curRoute === rt ? "selected" : ""}>${rt}</option>`).join("")}
      </select>
      <span class="tabs" role="tablist" aria-label="Filter verdict">
        ${["All", "Flagged", "Justified"].map(t => `<button role="tab" id="tab-${t.toLowerCase()}" aria-pressed="${curTab === t}">${t}</button>`).join("")}
      </span>
    </div>
    <div class="slip ledger">
      <table aria-label="Ledger">
        <thead><tr>${ths}</tr></thead>
        <tbody>${trs || '<tr><td colspan="7" style="text-align:center;padding:18px;">No matching rows found.</td></tr>'}</tbody>
      </table>
    </div>
    <p class="mono footer">notes: 10 · LLM calls: ${sum.llm_calls} · temp: ${sum.temperature} · ${sum.repro_identical ? "identical on 3 runs ✓" : "reproducible"}</p>
  `;

  document.getElementById("route-select").onchange = e => { curRoute = e.target.value; renderLedger(); };
  ["All", "Flagged", "Justified"].forEach(t => {
    document.getElementById("tab-" + t.toLowerCase()).onclick = () => { curTab = t; renderLedger(); };
  });
}

// Screen B: Route Page
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

  const { route_type, series, candidates } = data;
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

  let wPath = "", oPath = "", dots = "";
  const candMap = {};
  candidates.forEach(c => { candMap[c.week_of] = c; });

  pts.forEach((p, i) => {
    const x = getX(i), yW = getY(p.c);
    wPath += (i === 0 ? "M " : " L ") + `${x.toFixed(1)} ${yW.toFixed(1)}`;
    if (p.own_avg !== null) oPath += (!oPath ? "M " : " L ") + `${x.toFixed(1)} ${getY(p.own_avg).toFixed(1)}`;
    const cRow = candMap[p.week_of];
    if (cRow) {
      const ok = cRow.verdict === "justified";
      dots += `<circle cx="${x.toFixed(1)}" cy="${yW.toFixed(1)}" r="6" fill="${ok ? "#FFFDF7" : "#C8452D"}" ${ok ? 'stroke="#2E7A5B" stroke-width="2.5"' : ''} tabindex="0" aria-label="${ok ? 'Justified' : 'Flagged'}: ${p.week_of}"><title>${p.week_of} (${ok ? 'JUSTIFIED' : 'FLAGGED'}): ₹${p.c.toFixed(2)}/t-km ${ok ? `(${cRow.matched_note_id})` : `(+${cRow.vs_own_pct.toFixed(1)}%)`}</title></circle>`;
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
    return `<div class="slip"><div class="row"><span class="mono">week of ${c.week_of}</span>${st}</div><p><span class="mono">${c.c.toFixed(2)} ₹/t-km</span> · ${pct(c.vs_own_pct)} vs own · ${pct(c.vs_peer_pct)} vs peers</p>${body}</div>`;
  }).join("");

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
        <text x="60" y="170">${rStart}</text>
        <text x="310" y="170" text-anchor="middle">${pts[Math.floor(n/2)].week_of}</text>
        <text x="600" y="170" text-anchor="end">${rEnd}</text>
      </svg>
      <div class="mono legend"><span>━ weekly ₹/t-km</span><span>┅ own 8-week average</span><span class="g">◯ justified</span><span class="r">● flagged</span></div>
      <details style="margin-top:8px;"><summary>Data table</summary><table style="width:100%;font-size:11px;margin-top:8px;"><tr><th>Week</th><th>₹/t-km</th><th>Own avg</th><th>Verdict</th></tr>${pts.map(p => `<tr><td>${p.week_of}</td><td>${p.c.toFixed(2)}</td><td>${p.own_avg ? p.own_avg.toFixed(2) : "—"}</td><td>${candMap[p.week_of]?.verdict || "normal"}</td></tr>`).join("")}</table></details>
    </div>
    <div class="slips">${slips || '<div class="slip"><p>No cost rise candidates on this route.</p></div>'}</div>
  `;
}

// Screen C: Ask
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
  let s = md
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Bold: **text** or __text__
  s = s.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/__(.*?)__/g, "<strong>$1</strong>");

  // Italics: *text* (excluding already matched bold)
  s = s.replace(/(^|[^\*])\*(?!\s)([^\*]+?)\*(?!\*)/g, "$1<em>$2</em>");

  const lines = s.split("\n");
  let inList = false;
  const out = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      continue;
    }

    const listMatch = trimmed.match(/^[\*\-]\s+(.*)$/);
    if (listMatch) {
      if (!inList) {
        out.push('<ul class="ask-list">');
        inList = true;
      }
      out.push(`<li>${listMatch[1]}</li>`);
    } else {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
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
  } else {
    renderLedger();
  }
}

window.addEventListener("hashchange", router);
window.addEventListener("DOMContentLoaded", router);
