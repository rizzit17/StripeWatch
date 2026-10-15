const TRUCK_SVG='<svg width="28" height="18" viewBox="0 0 28 18" aria-hidden="true"><rect x="1" y="5" width="14" height="8" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1.2"/><path d="M15 7h5l3 3v3h-8z" fill="#E4932A" stroke="#1D1B16" stroke-width="1.2"/><circle cx="6" cy="14" r="2" fill="#1D1B16"/><circle cx="19" cy="14" r="2" fill="#1D1B16"/></svg>';let curTab="All",curRoute="All routes",curSort="week",curReviewFilter="All",gLedgerIndex=-1,gTourStep=0,gValidateMatrix=null,gPendingG=!1,gPendingGTimer=null;const byId=e=>document.getElementById(e),qsa=e=>document.querySelectorAll(e),pct=e=>`${e>0?"+":""}${Number(e).toFixed(1)}%`,formatINR=e=>e==null?"\u2014":"\u20B9"+Number(e).toLocaleString("en-IN"),esc=e=>String(e||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"),slipId=e=>"slip-"+e.route.replace(/\W/g,"_")+"-"+e.week_of,stHtml=(e,t)=>`<span class="st ${e?"ok":"flag"}">${t||(e?"JUSTIFIED":"FLAGGED")}</span>`,enc=encodeURIComponent,dec=decodeURIComponent;function mapStaticUrl(e){if(!window.STATIC_DEMO)return e;if(e.startsWith("/api/route/"))return`data/route_${enc(dec(e.slice(11).split("?")[0]))}.json`;const t={rows:1,summary:1,calendar:1,notes:1,weeks:1,review:1},o=e.replace("/api/","");return t[o]?`data/${o}.json`:e}async function getJSON(e,t){try{const o=await fetch(mapStaticUrl(e),t);return o.ok?await o.json():null}catch{return null}}function setNav(e){qsa(".nav a").forEach(t=>t.classList.toggle("active",t.id===e))}function setLoading(e){const t=byId("truck-icon");t&&t.classList.toggle("loading-truck",!!e)}async function getReviews(){if(window.STATIC_DEMO)try{const o=localStorage.getItem("stripewatch_review");if(o){const n=JSON.parse(o);return{reviews:n.reviews||n,items:[]}}}catch{}const e=await getJSON("/api/review"),t={};return Array.isArray(e)?(e.forEach(o=>{t[`${o.route}|${o.week_of}`]={status:o.review_status,note:o.review_note}}),{reviews:t,items:e}):e||{reviews:{},items:[]}}async function putReview(e,t,o,n){if(window.STATIC_DEMO)try{const r=await getReviews();return r.reviews||(r.reviews={}),r.reviews[`${e}|${t}`]={status:o,note:n,updated_at:new Date().toISOString()},localStorage.setItem("stripewatch_review",JSON.stringify(r)),{ok:!0}}catch{return{ok:!1}}return await getJSON(`/api/review/${enc(e)}/${t}`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({status:o,note:n})})}async function downloadReviewCSV(){const e=document.createElement("a");if(e.download="review_export.csv",!window.STATIC_DEMO){e.href="/api/review/export.csv",e.click();return}const[t,o]=await Promise.all([getReviews(),getJSON("/api/rows")]),n=t.reviews||{};let r=`route,week_of,verdict,matched_note_id,review_status,review_note
`;(o||[]).forEach(l=>{const c=n[`${l.route}|${l.week_of}`]||{};r+=`"${l.route}","${l.week_of}","${l.verdict}","${l.matched_note_id||""}","${c.status||"open"}","${(c.note||"").replace(/"/g,'""')}"
`}),e.href=URL.createObjectURL(new Blob([r],{type:"text/csv"})),e.click()}function renderHighlightedHtml(e,t,o,n){if(!e)return"";const r=[];if((n?o||[]:t||[]).forEach(a=>{const d=e.indexOf(a);d!==-1&&r.push({start:d,end:d+a.length,type:n?"negating":"evidence"})}),!r.length)return esc(e);r.sort((a,d)=>a.start-d.start);let c="",p=0;for(const a of r)if(a.start>=p){c+=esc(e.slice(p,a.start));const d=esc(e.slice(a.start,a.end));c+=a.type==="negating"?`<mark class="negating">${d}<span class="rej-badge">why rejected</span></mark>`:`<mark class="evidence">${d}</mark>`,p=a.end}return c+esc(e.slice(p))}function renderPaperTrailHtml(e,t){if(!e||!e.length)return"";const o=t?`<div class="mono sub" style="margin-bottom:6px;">Paper trail for ${t}:</div>`:"",n=e.map(r=>{const l=r.index||r.ticket||r[0]||"",c=r.name||r[1]||"",p=(r.detail||r[2]||"").replace(/\+\+/g,"+"),a=r.stamp||r[3]||"";return`<div class="pt-ticket"><span class="pt-title">${l?l+". ":""}${c}</span><div class="pt-detail mono">${esc(p)}</div><span class="pt-stamp ${a.toLowerCase()}">${a}</span></div>`}).join("");return`<div class="pt-strip-wrap">${o}<div class="pt-strip">${n}</div></div>`}function renderOverview(){setNav("nav-overview");const e='<svg width="40" height="40" viewBox="0 0 32 32" role="img" aria-label="Logo"><rect width="32" height="32" rx="5" fill="#1D1B16"/><rect x="5" y="11" width="12" height="9" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1.2"/><path d="M17 13h5l3 3v4h-8z" fill="#E4932A" stroke="#1D1B16" stroke-width="1.2"/><circle cx="10" cy="21" r="2.2" fill="#1D1B16"/><circle cx="21" cy="21" r="2.2" fill="#1D1B16"/></svg>',t=[["728","ROUTE-WEEKS","104w \xB7 7 routes",""],["19","ANOMALIES","Exceeding baselines","tiger"],["3","JUSTIFIED","N001 flood, N002 Diwali","green"],["16","FLAGGED","Unexplained rate creep","red"]],o=[["Delhi-Jaipur","Short\xB7260km"],["Mumbai-Pune","Short\xB7150km"],["Ahmedabad-Mumbai","Med\xB7530km"],["Chennai-Bangalore","Med\xB7350km"],["Kolkata-Bhubaneswar","Med\xB7440km"],["Delhi-Chennai","Long\xB72200km"],["Mumbai-Delhi","Long\xB71400km"]];byId("app").innerHTML=`
    <div class="slip" style="margin-bottom:16px;border-left:5px solid var(--tiger);">
      <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;">
        <div style="flex-shrink:0;">${e}</div>
        <div style="flex:1;min-width:240px;">
          <div style="display:flex;gap:8px;margin-bottom:4px;"><span class="mono tag" style="background:var(--highlight);font-weight:600;">FREIGHT TIGER AI CASE STUDY</span><span class="mono tag">ZERO HALLUCINATION</span></div>
          <div class="big" style="font-size:26px;line-height:1.15;margin-bottom:4px;">StripeWatch</div>
          <p style="font-size:13px;line-height:1.4;margin:0 0 10px;color:var(--ink-soft);">Autonomous freight cost watchdog with deterministic 5-gate RAG. Genuine operational disruptions justified; ungrounded rate creep flagged.</p>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            ${[["#/ledger","Live Ledger \u2192","primary"],["#/calendar","Calendar Heatmap"],["#/fool","Try to Fool It"],["#/ask","Ask Watchdog"]].map(n=>`<a href="${n[0]}" class="cta-btn ${n[2]||""}">${n[1]}</a>`).join("")}
            <button onclick="startTour()" class="cta-btn">Take Tour</button>
          </div>
        </div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:16px;">
      ${t.map(n=>`<div class="slip" style="padding:10px 14px;"><div class="big num ${n[3]}" style="font-size:28px;">${n[0]}</div><div class="lbl" style="font-size:11px;font-weight:600;color:var(--ink-soft);">${n[1]}</div><p style="font-size:11px;margin:2px 0 0;color:var(--ink-soft);">${n[2]}</p></div>`).join("")}
    </div>
    <div class="slip" style="margin-bottom:16px;">
      <div class="row" style="margin-bottom:8px;border-bottom:1.5px solid var(--rule);padding-bottom:4px;"><span class="big" style="font-size:15px;">Core Watchdog Rules</span><span class="mono tag">DETERMINISTIC</span></div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;">
        ${[["01. RATIO-OF-SUMS","c = \u03A3 cost / \u03A3 (t-km)"],["02. ZERO LOOK-AHEAD","Prior 8w shift(1) + peers"],["03. 5-GATE AUDIT","Route \xB7 Window \xB7 Effect \xB7 Size"],["04. HONEST ABSTENTION","16 of 19 flagged unexplained"]].map(n=>`<div style="padding:6px 10px;background:var(--paper);border:1px solid var(--rule);border-radius:3px;"><strong class="mono" style="font-size:11px;color:var(--tiger);">${n[0]}</strong><p style="font-size:12px;margin:2px 0 0;">${n[1]}</p></div>`).join("")}
      </div>
    </div>
    <div class="slip" style="margin-bottom:16px;">
      <div class="row" style="margin-bottom:4px;"><span class="big" style="font-size:14px;">7 Freight Corridors</span><span class="mono" style="font-size:11px;color:var(--ink-soft);">104 WEEKS \xB7 2024\u20132025</span></div>
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;">
        ${o.map(n=>`<a href="#/route/${n[0]}" class="chip plain" style="padding:3px 7px;text-decoration:none;color:var(--ink);"><strong>${n[0]}</strong> <span class="mono" style="color:var(--ink-soft);">(${n[1]})</span></a>`).join("")}
      </div>
    </div>
  `}async function renderLedger(){setNav("nav-ledger"),setLoading(!0);const[e,t,o]=await Promise.all([getJSON("/api/summary"),getJSON(`/api/rows?sort_by=${curSort==="excess"?"excess":"week"}`),getReviews()]);if(setLoading(!1),!e||!t){byId("app").innerHTML='<div class="slip"><p>Failed to load ledger data.</p></div>';return}const n=o.reviews||{},r=["All routes",...new Set(t.map(s=>s.route))];let l=t;curRoute!=="All routes"&&(l=l.filter(s=>s.route===curRoute)),curTab==="Flagged"?l=l.filter(s=>s.verdict==="unexplained"):curTab==="Justified"&&(l=l.filter(s=>s.verdict==="justified")),curReviewFilter!=="All"&&(l=l.filter(s=>(n[`${s.route}|${s.week_of}`]?.status||"open").toLowerCase()===curReviewFilter.toLowerCase()));let c=0;t.filter(s=>s.verdict==="unexplained").forEach(s=>{(n[`${s.route}|${s.week_of}`]?.status||"open").toLowerCase()!=="open"&&c++});const p=l.map((s,_)=>{const u=s.verdict==="justified",f=u&&s.matched_note_id?`<span class="chip">${s.matched_note_id}</span>`:"\u2014",m=`#/route/${enc(s.route)}?week=${s.week_of}`,E=s.excess_inr?formatINR(s.excess_inr):"\u2014",y=n[`${s.route}|${s.week_of}`]?.status||"open",h=`<button class="btn-review ${y}" onclick="event.stopPropagation();window.cycleReview('${s.route}','${s.week_of}')" title="Cycle review status">${y.toUpperCase()}</button>`;return`<tr class="r" id="ledger-row-${_}" tabindex="0" onclick="location.hash='${m}'" onkeydown="if(event.key==='Enter')location.hash='${m}'"><td class="mono">${s.week_of}</td><td><strong>${s.route}</strong></td><td class="mono">${s.c.toFixed(2)}</td><td class="mono">\u25B2 ${pct(s.vs_own_pct)}</td><td class="mono">${pct(s.vs_peer_pct)}</td><td class="mono">${E}</td><td>${stHtml(u)}</td><td>${f}</td><td style="text-align:center;">${h}</td></tr>`}).join(""),a=(s,_,u="")=>`<div class="slip"><div class="big num ${u}">${s}</div><div class="lbl">${_}</div></div>`,d=["Week of","Route","\u20B9/t-km","vs own","vs peers","Excess \u20B9","Verdict","Note","Review"].map(s=>`<th scope="col">${s}</th>`).join(""),$=e.abstention?`Left ${e.abstention.unexplained} of ${e.abstention.total} unexplained on purpose: only ${e.abstention.usable_notes} of ${e.abstention.total_notes} notes can justify a rise.`:"Left 16 of 19 unexplained on purpose: only 3 of 10 notes can justify a rise.",k=window.STATIC_DEMO?'<div class="static-banner">Static demo: snapshot of committed results. No API keys, no live model.</div>':"";byId("app").innerHTML=`
    ${k}
    <h2 class="sr-only">StripeWatch ledger: ${e.rises} cost rises spotted</h2>
    <section class="summary" aria-label="Overview" id="tour-summary-strip">
      ${a(e.rises,"rises spotted")}${a(e.justified,"justified by a note","green")}${a(e.flagged,"need a human look","red")}
    </section>
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin:-4px 0 16px;font-size:12px;color:var(--ink-soft);">
      <span>${$} \xB7 Est. excess: <strong style="color:var(--ink);">\u20B91.28 lakh</strong></span>
      <span><strong>${c}/16</strong> reviewed \xB7 <a href="javascript:window.exportReviewsCSV()" style="color:var(--ink);text-decoration:underline;">Export CSV</a></span>
    </div>
    <div class="filters">
      <label for="route-select">Route</label>
      <select id="route-select">${r.map(s=>`<option value="${s}" ${curRoute===s?"selected":""}>${s}</option>`).join("")}</select>
      <span class="sort-toggle">
        <span>Sort:</span>
        <button id="sort-week" class="${curSort==="week"?"active":""}">week</button>
        <button id="sort-excess" class="${curSort==="excess"?"active":""}">excess \u20B9</button>
      </span>
      <select id="rev-select" style="width:130px;" aria-label="Review filter">
        ${["All","Open","Confirmed","Dismissed"].map(s=>`<option value="${s}" ${curReviewFilter===s?"selected":""}>Review: ${s}</option>`).join("")}
      </select>
      <span class="tabs" role="tablist" style="margin-left:auto;">
        ${["All","Flagged","Justified"].map(s=>`<button role="tab" id="tab-${s.toLowerCase()}" aria-pressed="${curTab===s}">${s}</button>`).join("")}
      </span>
      <button class="btn-print-only" onclick="window.printSummary()" style="padding:4px 9px;">Print summary</button>
    </div>
    <div class="slip ledger" id="tour-ledger-table">
      <table aria-label="Ledger">
        <thead><tr>${d}</tr></thead>
        <tbody>${p||'<tr><td colspan="9" style="text-align:center;padding:18px;">No matching rows found.</td></tr>'}</tbody>
      </table>
    </div>
    <p class="mono footer" id="tour-footer">notes: 10 \xB7 LLM calls: ${e.llm_calls} \xB7 temp: ${e.temperature} \xB7 ${e.repro_identical?"identical on 3 runs \u2713":"reproducible"}</p>
  `,byId("route-select").onchange=s=>{curRoute=s.target.value,renderLedger()},byId("sort-week").onclick=()=>{curSort="week",renderLedger()},byId("sort-excess").onclick=()=>{curSort="excess",renderLedger()},byId("rev-select").onchange=s=>{curReviewFilter=s.target.value,renderLedger()},["All","Flagged","Justified"].forEach(s=>{byId("tab-"+s.toLowerCase()).onclick=()=>{curTab=s,renderLedger()}})}window.cycleReview=async(e,t)=>{const o=await getReviews(),n=(o.reviews?.[`${e}|${t}`]?.status||"open").toLowerCase(),r=n==="open"?"confirmed":n==="confirmed"?"dismissed":"open",l=o.reviews?.[`${e}|${t}`]?.note||"";await putReview(e,t,r,l),renderLedger()},window.exportReviewsCSV=()=>{downloadReviewCSV()},window.printSummary=()=>{document.body.dataset.print="summary",window.print()},window.addEventListener("afterprint",()=>{delete document.body.dataset.print});async function renderRoute(e,t){setNav("nav-routes"),setLoading(!0);const[o,n]=await Promise.all([getJSON(`/api/route/${enc(e)}`),getReviews()]);if(setLoading(!1),!o){byId("app").innerHTML=`<div class="slip"><p>Route '${esc(e)}' not found.</p><a href="#/ledger">\u2190 Back to Ledger</a></div>`;return}const{route_type:r,series:l,candidates:c,attribution:p}=o,a=n.reviews||{},d=l,$=d.length,k=Math.max(...d.map(i=>Math.max(i.c,i.own_avg||0)),1),s=Math.ceil(k*2)/2,_=s-.5,u=s-1,f=i=>Math.max(20,Math.min(140,30+(s-i)/(s-u||1)*100)),m=i=>60+i*(540/Math.max(1,$-1));let E="",y="",h="",C="";const L={};c.forEach(i=>{L[i.week_of]=i}),d.forEach((i,v)=>{const g=m(v),w=f(i.c);E+=(v===0?"M ":" L ")+`${g.toFixed(1)} ${w.toFixed(1)}`,i.own_avg!==null&&(y+=(y?" L ":"M ")+`${g.toFixed(1)} ${f(i.own_avg).toFixed(1)}`);const x=L[i.week_of];if(x){const b=x.verdict==="justified";h+=`<circle cx="${g.toFixed(1)}" cy="${w.toFixed(1)}" r="6" fill="${b?"#FFFDF7":"#C8452D"}" ${b?'stroke="#2E7A5B" stroke-width="2.5"':""} tabindex="0" aria-label="${b?"Justified":"Flagged"}: ${i.week_of}"><title>${i.week_of}: \u20B9${i.c.toFixed(2)}/t-km</title></circle>`}i.creep_tag&&(C+=`<polygon points="${g.toFixed(1)},145 ${(g-3).toFixed(1)},151 ${(g+3).toFixed(1)},151" fill="#E4932A"><title>${i.week_of}: peer gap sustained 4 weeks</title></polygon>`)});const j=[30,80,130].map((i,v)=>`<line x1="40" y1="${i}" x2="620" y2="${i}" stroke="#D9D0BC" stroke-dasharray="2 4"/><text x="4" y="${i+4}">${[s,_,u][v].toFixed(2)}</text>`).join("");let T=0;if(t){const i=d.findIndex(v=>v.week_of===t);i!==-1&&(T=i)}else if(c.length>0){const i=d.findIndex(v=>v.week_of===c[0].week_of);i!==-1&&(T=i)}const N=c.map(i=>{const v=i.verdict==="justified",g=i.evidence_packet?.note,w=v&&g?`<div class="cited"><span class="chip plain">${g.id}</span> ${renderHighlightedHtml(g.text||g.rationale,g.evidence_spans,null,!1)}</div>`:'<p style="color:var(--ink-soft);font-size:13px;margin:6px 0;">No matching note found. Looks unexplained, worth a human look.</p>',x=i.evidence_packet?.near_misses||[],b=!v&&x.length?`<div class="rejected" style="margin-bottom:10px;"><strong>Closest notes I rejected:</strong><br>${x.map(F=>`<span class="chip plain">${F.id}</span> ${renderHighlightedHtml(F.raw_text||F.why_not,null,F.negating_spans||[F.why_not],!0)}`).join("<br>")}</div>`:"",S=slipId(i),R=i.excess_inr?` \xB7 <span class="mono">excess: ${formatINR(i.excess_inr)}</span>`:"",O=a[`${i.route}|${i.week_of}`]||{status:"open",note:""};return`
      <div class="slip" id="${S}" data-slip-id="${S}">
        <div class="row">
          <span class="mono slip-date">week of ${i.week_of}</span>
          <div style="display:flex;align-items:center;gap:8px;">${stHtml(v)}<button class="btn-print-only" onclick="window.printDocket('${S}')" style="padding:2px 6px;">Print docket</button></div>
        </div>
        <p style="margin:4px 0 8px;"><span class="mono" style="font-weight:600;">${i.c.toFixed(2)} \u20B9/t-km</span> \xB7 ${pct(i.vs_own_pct)} vs own \xB7 ${pct(i.vs_peer_pct)} vs peers${R}</p>
        ${w}
        <details class="slip-audit" style="margin-top:10px;border-top:1px dotted var(--rule);padding-top:8px;">
          <summary class="mono" style="cursor:pointer;font-size:12px;color:var(--ink-soft);user-select:none;">\u25B8 5-gate audit trail & review notes</summary>
          <div style="margin-top:10px;">
            ${b}
            ${renderPaperTrailHtml(i.tickets,i.evaluated_note_id)}
            <div class="review-box" style="margin-top:10px;">
              <label class="review-label" for="rev-note-${S}">Your review note (stored on this computer):</label>
              <textarea class="review-textarea" id="rev-note-${S}" maxlength="280" placeholder="Optional audit comment...">${esc(O.note)}</textarea>
              <div class="char-counter" id="char-cnt-${S}">${(O.note||"").length} / 280</div>
            </div>
          </div>
        </details>
      </div>
    `}).join("");let D="";p&&p.length>0&&(D=`
      <div class="slip" style="margin-bottom:16px;">
        <div class="row"><span class="big" style="font-size:16px;">Where the rise sits</span><span class="mono tag">DATA ONLY</span></div>
        <p style="font-size:12px;color:var(--ink-soft);margin-bottom:8px;">Transporter vs route concentration.</p>
        ${p.map(i=>`
          <div style="border-bottom:1px dotted var(--rule);padding:6px 0;">
            <div style="display:flex;justify-content:space-between;"><span class="mono" style="font-weight:600;">${i.start} to ${i.end}</span><span class="mono tag">${i.verdict}</span></div>
            <p style="font-size:12px;margin:2px 0;color:var(--ink-soft);">${i.transporter?.verdict?`<strong>Transporter:</strong> ${esc(i.transporter.verdict)}`:""}</p>
          </div>
        `).join("")}
      </div>
    `);const I=d[0].week_of,z=d[d.length-1].week_of;byId("app").innerHTML=`
    <div style="margin-bottom:12px;"><a href="#/ledger" style="color:var(--ink-soft);text-decoration:none;font-size:13px;">\u2190 Back to Ledger</a></div>
    <div class="route-head"><span class="big title">${esc(e)}</span><span class="mono tag">${r.toUpperCase()}</span><span class="mono range">${I} to ${z}</span></div>
    <div class="slip chart" id="tour-route-chart">
      <svg id="route-svg" width="100%" height="190" viewBox="0 0 640 190" role="img" aria-label="Chart" font-family="'JetBrains Mono',monospace" font-size="11" fill="#6B665A">
        ${j}
        <path d="${y}" stroke="#6B665A" stroke-width="1.2" stroke-dasharray="5 4" fill="none"/>
        <path d="${E}" stroke="#1D1B16" stroke-width="1.8" fill="none"/>
        ${h}
        ${C}
        <line id="scrub-line" x1="${m(T).toFixed(1)}" y1="20" x2="${m(T).toFixed(1)}" y2="150" stroke="#E4932A" stroke-width="1.5" stroke-dasharray="3 3"/>
        <g id="truck-scrubber" class="truck-marker" transform="translate(${(m(T)-14).toFixed(1)}, 148)" role="slider" tabindex="0" aria-valuemin="0" aria-valuemax="${$-1}" aria-valuenow="${T}" aria-valuetext="week of ${d[T].week_of}">
          ${TRUCK_SVG}
        </g>
        <text x="60" y="176">${I}</text>
        <text x="310" y="176" text-anchor="middle">${d[Math.floor($/2)].week_of}</text>
        <text x="600" y="176" text-anchor="end">${z}</text>
      </svg>
      <div class="mono legend">
        <span>\u2501 weekly \u20B9/t-km</span><span>\u2505 own 8w avg</span><span class="g">\u25EF justified</span><span class="r">\u25CF flagged</span><span style="color:var(--tiger);">\u25B2 peer gap</span><span style="color:var(--ink);font-weight:600;">\u{1F69A} drag truck</span>
      </div>
      <div id="live-week-slip" class="live-week-slip"></div>
    </div>
    ${D}
    <div class="slips">${N||'<div class="slip"><p>No cost rise candidates on this route.</p></div>'}</div>
  `;function M(i){const v=d[i],g=L[v.week_of],w=byId("scrub-line"),x=byId("truck-scrubber"),b=byId("live-week-slip");if(!v||!w||!x||!b)return;const S=m(i);w.setAttribute("x1",S.toFixed(1)),w.setAttribute("x2",S.toFixed(1)),x.setAttribute("transform",`translate(${(S-14).toFixed(1)}, 148)`),x.setAttribute("aria-valuenow",i);let R="Normal this week";v.own_avg===null?R="First week":g&&(R=stHtml(g.verdict==="justified",g.verdict==="justified"?`JUSTIFIED (${g.matched_note_id})`:"FLAGGED"));const O=v.excess_inr?` \xB7 excess: <strong>${formatINR(v.excess_inr)}</strong>`:"",F=g?` \xB7 <a href="#${slipId(g)}" style="color:var(--ink);text-decoration:underline;">Scroll to slip \u2193</a>`:"";b.innerHTML=`
      <div class="row">
        <div>
          <span class="mono" style="font-size:14px;font-weight:600;">Week of ${v.week_of}</span>
          <div style="font-size:12px;color:var(--ink-soft);margin-top:2px;">
            <span>Cost: <strong>\u20B9${v.c.toFixed(2)}/t-km</strong></span> \xB7 
            <span>Own: <strong>${v.own_avg?`\u20B9${v.own_avg.toFixed(2)}`:"\u2014"}</strong> (${pct(v.vs_own_pct)})</span> \xB7 
            <span>Peers: <strong>${v.peer_avg?`\u20B9${v.peer_avg.toFixed(2)}`:"\u2014"}</strong> (${pct(v.vs_peer_pct)})</span>${O}
          </div>
        </div>
        <div>${R}${F}</div>
      </div>
    `}M(T);const A=byId("truck-scrubber");if(A){A.onkeydown=w=>{let x=parseInt(A.getAttribute("aria-valuenow")||"0");const b=w.shiftKey?4:1;if(w.key==="ArrowLeft")x=Math.max(0,x-b);else if(w.key==="ArrowRight")x=Math.min($-1,x+b);else if(w.key==="Home")x=0;else if(w.key==="End")x=$-1;else return;M(x),w.preventDefault()};let i=!1;const v=byId("route-svg"),g=w=>{if(!i)return;const x=v.getBoundingClientRect(),b=w.clientX||w.touches&&w.touches[0].clientX;if(b===void 0)return;const S=Math.max(0,Math.min(1,(b-x.left-60)/(x.width-100)));M(Math.max(0,Math.min($-1,Math.round(S*($-1)))))};A.onpointerdown=w=>{i=!0,A.setPointerCapture(w.pointerId)},A.onpointermove=g,A.onpointerup=w=>{i=!1;try{A.releasePointerCapture(w.pointerId)}catch{}}}c.forEach(i=>{const v=slipId(i),g=byId(`rev-note-${v}`),w=byId(`char-cnt-${v}`);g&&w&&(g.oninput=()=>{w.textContent=`${g.value.length} / 280`},g.onblur=async()=>{const x=a[`${i.route}|${i.week_of}`]?.status||"open";await putReview(i.route,i.week_of,x,g.value.trim())})})}window.printDocket=e=>{document.body.dataset.print="docket",window.print()};async function renderCalendar(){setNav("nav-calendar"),setLoading(!0);const e=await getJSON("/api/calendar");if(setLoading(!1),!e){byId("app").innerHTML='<div class="slip"><p>Failed to load calendar data.</p></div>';return}const t=e.route_groups||e.groups||[],o=e.cells||[],n=6,r=18,l=216,c=38,p={};o.forEach(u=>{p[`${u.route}|${u.week_of}`]=u});const a=[...new Set(o.map(u=>u.week_of))].sort(),d=[];t.forEach(u=>(u.routes||[]).forEach(f=>d.push({route:f,type:u.type})));let $="",k="",s='<text x="12" y="22" class="mono" font-size="9" font-weight="600" fill="#8C8270">CORRIDOR</text><text x="156" y="22" class="mono" font-size="9" font-weight="600" fill="#8C8270">TIER</text><line x1="204" y1="10" x2="204" y2="196" stroke="#D9D0BC" stroke-dasharray="2 3"/>';a.forEach((u,f)=>{const m=f===a.length-1;(f%8===0&&a.length-1-f>=8||m)&&(s+=`<text x="${l+f*7+(m?n:0)}" y="22" class="mono" font-size="9.5" fill="#6B665A" ${m?'text-anchor="end"':""}>${u.slice(2,7)}</text>`)}),d.forEach((u,f)=>{const m=c+f*22;k+=`<text x="12" y="${m+13}" font-size="11.5" font-weight="600" fill="var(--ink)">${u.route}</text><text x="156" y="${m+13}" class="mono" font-size="9" fill="#8C8270" letter-spacing="0.05em">${u.type}</text>`,a.forEach((E,y)=>{const h=p[`${u.route}|${E}`];if(!h)return;const C=l+y*7;let L="var(--rule)",j="none",T="0",N="",D="",I="";if(!h.is_evaluable)L="transparent",j="var(--rule)",T="1",N='stroke-dasharray="2"';else if(h.is_candidate){const M=h.verdict==="justified";L=M?"var(--slip)":"var(--stamp-red)",j=M?"var(--stamp-green)":"none",T=M?"2":"0",I=`${M?"Justified":"Flagged"}: ${h.route} week ${h.week_of}`,D=`tabindex="0" aria-label="${I}" onclick="location.hash='#/route/${enc(h.route)}?week=${h.week_of}'" onkeydown="if(event.key==='Enter')location.hash='#/route/${enc(h.route)}?week=${h.week_of}'"`}const z=h.creep_tag?`<rect x="${C}" y="${m+19}" width="${n}" height="2" fill="var(--tiger-soft)"/>`:"";$+=`<rect class="cal-cell" x="${C}" y="${m}" width="${n}" height="${r}" rx="1" fill="${L}" stroke="${j}" stroke-width="${T}" ${N} ${D}><title>${h.route} (${h.week_of}): \u20B9${h.c.toFixed(2)}/t-km ${h.is_candidate?"["+h.verdict.toUpperCase()+"]":""}</title></rect>${z}`})});const _=[["var(--rule)","Normal",""],["transparent","First week","border:1px dashed var(--rule);"],["var(--stamp-red)","Flagged","","r"],["var(--slip)","Justified","border:2px solid var(--stamp-green);","g"],["var(--tiger-soft)","Peer gap 4w",""]].map(u=>`<div class="cal-legend-item"><span class="cal-legend-swatch" style="background:${u[0]};${u[2]}"></span><span class="${u[3]||""}">${u[1]}</span></div>`).join("");byId("app").innerHTML=`
    <div class="big" style="font-size:24px;margin-bottom:6px;">Lorry Calendar Heatmap</div>
    <p style="font-size:13px;color:var(--ink-soft);margin-bottom:14px;">104-week cross-corridor timeline. Red blocks spot candidate anomalies; green rings spot justified events.</p>
    <div class="cal-container" id="tour-cal-chart">
      <svg width="100%" height="236" viewBox="0 0 960 236" role="img" aria-label="Heatmap">
        ${s}${k}${$}
      </svg>
      <div class="cal-legend">${_}</div>
    </div>
    <div class="slip" style="margin-top:16px;">
      <p class="mono" style="margin:0;font-size:13px;">${e.summary_sentence||""}</p>
    </div>
  `}async function renderNotes(){setNav("nav-notes"),setLoading(!0);const e=await getJSON("/api/notes");if(setLoading(!1),!e){byId("app").innerHTML='<div class="slip"><p>Failed to load notes.</p></div>';return}const t=e.map(o=>{let n="flag",r="CAN'T JUSTIFY";const l=o.effect==="raises"&&o.scope!=="NONE";l&&(n=o.scope==="ALL"?"warn":"ok",r=o.scope==="ALL"?"CAN JUSTIFY (CAPPED)":"CAN JUSTIFY");const c=`${o.start||o.date} to ${o.end||(l?"ongoing":"normal")}`,p=o.text||o.note||o.rationale||"",a=renderHighlightedHtml(p,o.evidence_spans,o.negating_spans,!l);return`
      <div class="slip">
        <div class="row">
          <div><span class="chip">${o.id}</span> <strong style="margin-left:6px;font-size:13px;">${esc(o.applies_to)}</strong></div>
          <span class="st ${n}">${r}</span>
        </div>
        <p style="font-size:12px;color:var(--ink-soft);margin:4px 0 8px;">Scope: <strong>${o.scope}</strong> \xB7 Effect: <strong>${o.effect}</strong> \xB7 Window: <strong>${c}</strong></p>
        <p class="cited" style="font-size:12px;margin:6px 0;">"${a}"</p>
        <p class="rejected" style="font-size:12px;color:var(--ink);"><strong>Rationale:</strong> ${esc(o.rationale||"\u2014")}</p>
      </div>
    `}).join("");byId("app").innerHTML=`
    <div class="big" style="font-size:24px;margin-bottom:6px;">Context Notes Register</div>
    <div class="slip" style="margin-bottom:16px;background:var(--highlight);border:1.5px dashed var(--ink);">
      <p style="margin:0;font-size:13px;line-height:1.5;"><strong>Ground truth:</strong> 3 of 10 notes can ever justify a cost rise. The other 7 say costs were normal, apply elsewhere, or mark reopening.</p>
    </div>
    <div class="slips">${t}</div>
  `}async function renderFool(){setNav("nav-fool"),setLoading(!0);const[e,t]=await Promise.all([getJSON("/api/notes"),getJSON("/api/weeks")]);if(setLoading(!1),!e||!t){byId("app").innerHTML='<div class="slip"><p>Failed to load validation data.</p></div>';return}const o=[...new Set(t.map(a=>a.route))],n=[["1. Flood expired","Chennai-Bangalore","2025-03-10","N001"],["2. Reopening","Chennai-Bangalore","2025-03-17","N009"],["3. Normal report","Mumbai-Pune","2025-09-15","N006"],["4. Wrong corridor","Mumbai-Pune","2025-09-15","N001"],["5. Magnitude cap","Mumbai-Delhi","2025-05-12","N003"],["6. Peer gap","Mumbai-Pune","2025-06-23","N003"],["7. Out of scope","Delhi-Jaipur","2024-11-11","N004"],["8. Festival ok","Ahmedabad-Mumbai","2025-01-20","N002"]],r='style="width:100%;padding:6px;border:1.5px solid var(--ink);border-radius:3px;background:var(--slip);font-size:13px;"';byId("app").innerHTML=`
    <div class="big" style="font-size:24px;margin-bottom:6px;">Try to Fool the Validator</div>
    <p style="font-size:13px;color:var(--ink-soft);margin-bottom:14px;">Test 5-stage deterministic validation against any route, week, and note.</p>
    <div class="slip" style="margin-bottom:16px;" id="tour-fool-box">
      <span class="mono" style="font-size:12px;font-weight:600;">Adversarial attack presets:</span>
      <div class="presets">
        ${n.map((a,d)=>`<button class="preset-btn" id="preset-${d}" onclick="window.loadPreset(${d}, '${a[1]}','${a[2]}','${a[3]}')">${a[0]}</button>`).join("")}
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:12px;align-items:end;margin-top:12px;">
        <div>
          <label style="font-size:12px;color:var(--ink-soft);display:block;margin-bottom:4px;" for="fool-route">Route</label>
          <select id="fool-route" ${r}>${o.map(a=>`<option value="${a}">${a}</option>`).join("")}</select>
        </div>
        <div>
          <label style="font-size:12px;color:var(--ink-soft);display:block;margin-bottom:4px;" for="fool-week">Week of (Monday)</label>
          <select id="fool-week" ${r}></select>
        </div>
        <div>
          <label style="font-size:12px;color:var(--ink-soft);display:block;margin-bottom:4px;" for="fool-note">Context Note</label>
          <select id="fool-note" ${r}>${e.map(a=>`<option value="${a.id}">${a.id}: ${a.applies_to} (${a.effect})</option>`).join("")}</select>
        </div>
        <div>
          <button id="fool-run-btn" style="width:100%;padding:7px;background:var(--ink);color:var(--slip);border:0;border-radius:3px;font-weight:600;cursor:pointer;">Run Check</button>
        </div>
      </div>
    </div>
    <div id="fool-result"></div>
  `;function l(){const a=byId("fool-route"),d=byId("fool-week");if(!a||!d)return;const $=t.filter(k=>k.route===a.value);d.innerHTML=$.map(k=>`<option value="${k.week_of}">${k.week_of} (${k.c.toFixed(2)} \u20B9/t-km${k.is_candidate?" \xB7 ANOMALY":""})</option>`).join("")}const c=byId("fool-route");c&&(c.onchange=l),l(),window.loadPreset=(a,d,$,k)=>{qsa(".preset-btn").forEach((f,m)=>f.classList.toggle("active",m===a));const s=byId("fool-route"),_=byId("fool-week"),u=byId("fool-note");s&&(s.value=d,l()),_&&(_.value=$),u&&(u.value=k),window.runFoolValidation()};const p=byId("fool-run-btn");p&&(p.onclick=()=>{qsa(".preset-btn").forEach(a=>a.classList.remove("active")),window.runFoolValidation()}),window.loadPreset(0,n[0][1],n[0][2],n[0][3])}window.runFoolValidation=async()=>{const e=byId("fool-route"),t=byId("fool-week"),o=byId("fool-note"),n=byId("fool-result");if(!e||!t||!o||!n)return;const r=e.value,l=t.value,c=o.value;n.innerHTML='<div class="slip"><p class="mono" style="color:var(--ink-soft);">Executing 5-step validator...</p></div>';let p=null;if(window.STATIC_DEMO&&(gValidateMatrix||(gValidateMatrix=await getJSON("data/validate_matrix.json")),gValidateMatrix)){const f=gValidateMatrix.matrix[`${r}|${l}|${c}`];if(f){const[m,E]=f,y=[1,2,4,8,16].map(h=>!!(m&h));p={row:{c:3.5,vs_own_pct:22,vs_peer_pct:25},checks:{effect_is_cost_rise:y[0],route_in_scope:y[1],window_overlaps:y[2],magnitude_ok:y[3],not_peer_outlier_for_universal:y[4]},justified:!!(m&32),why_not:gValidateMatrix.why_reasons[E]||""}}}if(p||(p=await getJSON("/api/validate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({route:r,week_of:l,note_id:c})})),!p){n.innerHTML='<div class="slip"><p>Failed to validate candidate against note.</p></div>';return}const a=p.justified,d=f=>`<span class="st ${f?"pass":"fail"}">${f?"PASS":"FAIL"}</span>`,$=p.row.vs_own_pct!=null?`+${p.row.vs_own_pct.toFixed(1)}%`:"N/A",k=p.row.vs_peer_pct!=null?`+${p.row.vs_peer_pct.toFixed(1)}%`:"N/A",s=p.checks,_=[["1. Effect raises cost",s.effect_is_cost_rise,"cost rise check"],["2. Route in scope",s.route_in_scope,"corridor check"],["3. Window overlaps",s.window_overlaps,"date overlap"],["4. Magnitude within tolerance",s.magnitude_ok,"magnitude check"],["5. Universal not peer outlier",s.not_peer_outlier_for_universal,"peer gap check"]],u=[[1,"Spotted",`vs own: ${$}`,"SPOTTED"],[2,"Searched",`tested note ${c}`,"SEARCHED"],..._.map((f,m)=>[m+3,f[0].split(". ")[1],f[2],f[1]?"PASS":"FAIL"])];n.innerHTML=`
    <div class="slip">
      <div class="row" style="margin-bottom:12px;border-bottom:1.5px solid var(--rule);padding-bottom:10px;">
        <div>
          <span class="big" style="font-size:18px;">Validator Verdict: ${esc(r)} (${l}) + ${c}</span>
          <div style="font-size:12px;color:var(--ink-soft);margin-top:4px;">
            <span>Cost: <strong>\u20B9${p.row.c.toFixed(2)}/t-km</strong></span> \xB7 
            <span>vs own: <strong>${$}</strong></span> \xB7 
            <span>vs peer: <strong>${k}</strong></span>
          </div>
        </div>
        ${stHtml(a)}
      </div>
      <div style="margin-bottom:14px;padding:8px 12px;border:1px solid var(--rule);border-radius:3px;">
        <span class="mono" style="font-size:11px;font-weight:600;color:var(--ink-soft);display:block;margin-bottom:6px;text-transform:uppercase;">5-Step Gate Evaluation</span>
        ${_.map(f=>`<div class="check-item"><div><strong>${f[0]}</strong></div>${d(f[1])}</div>`).join("")}
      </div>
      ${renderPaperTrailHtml(u,c)}
      <div style="background:${a?"var(--highlight)":"var(--slip)"};border:1.5px solid var(--ink);border-radius:3px;padding:10px 14px;margin-top:12px;">
        <strong>Plain-English Verdict Reason:</strong>
        <p style="margin:4px 0 0;font-size:13px;line-height:1.5;">${esc(a?`Cost rise on ${r} for ${l} is justified by ${c}.`:p.why_not)}</p>
      </div>
    </div>
  `};function renderAsk(){setNav("nav-ask");const e=["Why did Chennai-Bangalore get pricier in March?","What happened on Ahmedabad-Mumbai in Jan 2025?","Which routes have no explanation?","Is Mumbai-Pune still rising?"];byId("app").innerHTML=`
    <div class="big ask-title">Ask about a route or month</div>
    <form id="ask-form" class="slip askbox" onsubmit="event.preventDefault();window.onAskSubmit();">
      <input id="ask-input" aria-label="Your question" placeholder="${e[0]}" autofocus>
      <button type="submit" id="ask-btn">Ask</button>
    </form>
    <div class="examples" aria-label="Examples">${e.map(t=>`<button class="ex" onclick="window.fillAsk('${t}')">${t}</button>`).join("")}</div>
    <div id="ask-result"></div>
  `}window.fillAsk=e=>{const t=byId("ask-input");t&&(t.value=e,window.onAskSubmit())};function renderMarkdown(e){return e?esc(e).replace(/\*\*(.*?)\*\*/g,"<strong>$1</strong>").replace(/\*(.*?)\*/g,"<em>$1</em>").split(`
`).map(o=>o.startsWith("- ")||o.startsWith("* ")?`<li>${o.slice(2)}</li>`:o.trim()?`<p>${o}</p>`:"").join(""):""}window.onAskSubmit=async()=>{const e=byId("ask-input"),t=byId("ask-btn"),o=byId("ask-result");if(!e||!e.value.trim())return;const n=e.value.trim();t.disabled=!0,setLoading(!0),o.innerHTML='<div class="slip answer"><p class="mono" style="color:var(--ink-soft);">Looking through the rows\u2026</p></div>';const r=await getJSON("/api/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:n})});if(!r){o.innerHTML='<div class="slip answer"><p>Unable to connect to analysis server. Please ensure the backend is running with <code>python -m stripewatch serve</code>.</p></div>';return}if(r.empty)o.innerHTML=`<div class="empty">${TRUCK_SVG}<span>No note found. I'd rather say so than guess.</span></div>`;else{const l=r.based_on_rows?.length?`<div class="mono based"><span class="k">Based on rows:</span> ${r.based_on_rows.map(c=>`<a href="#/route/${enc(c.route)}?week=${c.week_of}">${c.week_of}</a>${c.note_id?` <span class="chip">${c.note_id}</span>`:""}`).join(" \xB7 ")}</div>`:"";o.innerHTML=`<div class="slip answer">${renderMarkdown(r.answer)}${l}</div>`}};const TOUR_STEPS=[["tour-summary-strip","#/ledger","19 rises spotted. 3 explained by a note."],["tour-ledger-table","#/ledger","Each row is one route-week. Click one to see evidence."],["tour-route-chart","#/route/Ahmedabad-Mumbai?week=2025-01-20","Green rings = justified. Red dots = unexplained. Drag truck to scrub."],["live-week-slip","#/route/Ahmedabad-Mumbai?week=2025-01-20","Every verdict passes 5 checks: route, window, and effect."],["tour-fool-box","#/fool","Pick any note and week. See exactly why it fails."],["tour-footer","#/ledger","Same numbers on 3 runs. The model only writes wording."]];window.startTour=()=>{gTourStep=0,runTourStep()};function runTourStep(){const e=TOUR_STEPS[gTourStep];if(!e)return window.closeTour();location.hash!==e[1]?(location.hash=e[1],setTimeout(renderCoachMark,350)):renderCoachMark()}function renderCoachMark(){const e=byId("tour-overlay")||document.body.appendChild(Object.assign(document.createElement("div"),{id:"tour-overlay",className:"tour-overlay"})),t=TOUR_STEPS[gTourStep],o=byId(t[0]),n=o?o.getBoundingClientRect():{top:120,left:40,width:300,height:100},r=byId("coach-mark")||document.body.appendChild(Object.assign(document.createElement("div"),{id:"coach-mark",className:"coach-mark"}));r.style.top=`${Math.min(window.innerHeight-180,Math.max(20,n.top+window.scrollY+n.height/2))}px`,r.style.left=`${Math.min(window.innerWidth-340,Math.max(20,n.left+20))}px`,r.innerHTML=`
    <div class="coach-step">STEP ${gTourStep+1} OF 6</div>
    <div>${t[2]}</div>
    <div class="coach-actions">
      <button onclick="window.closeTour()">Skip</button>
      <div>
        ${gTourStep>0?'<button onclick="window.prevTourStep()">Back</button>':""}
        <button class="btn-next" onclick="window.nextTourStep()">${gTourStep===5?"Done":"Next"}</button>
      </div>
    </div>
  `}window.nextTourStep=()=>{gTourStep++,gTourStep>=TOUR_STEPS.length?window.closeTour():runTourStep()},window.prevTourStep=()=>{gTourStep>0&&(gTourStep--,runTourStep())},window.closeTour=()=>{byId("tour-overlay")?.remove(),byId("coach-mark")?.remove();try{localStorage.setItem("stripewatch_tour_done","1")}catch{}},window.addEventListener("keydown",e=>{if(!["INPUT","TEXTAREA","SELECT"].includes(e.target.tagName)&&!(e.ctrlKey||e.metaKey||e.altKey)){if(e.key==="Escape"){window.closeTour();const t=byId("shortcuts-dialog");t&&t.open&&t.close();return}if(e.key==="?"){const t=byId("shortcuts-dialog");t&&(t.open?t.close():t.showModal()),e.preventDefault();return}if(e.key==="/"){location.hash="#/ask",setTimeout(()=>{const t=byId("ask-input");t&&t.focus()},150),e.preventDefault();return}if(e.key==="g"){gPendingG=!0,clearTimeout(gPendingGTimer),gPendingGTimer=setTimeout(()=>{gPendingG=!1},1e3);return}if(gPendingG){gPendingG=!1,clearTimeout(gPendingGTimer);const t={o:"#/",l:"#/ledger",c:"#/calendar",r:"#/route/Ahmedabad-Mumbai",n:"#/notes",f:"#/fool",a:"#/ask"};if(t[e.key]){location.hash=t[e.key],e.preventDefault();return}}if(e.key==="j"||e.key==="k"){const t=qsa("tr.r");if(t.length){gLedgerIndex=e.key==="j"?Math.min(t.length-1,gLedgerIndex+1):Math.max(0,gLedgerIndex-1);const o=t[gLedgerIndex];o&&(o.focus(),o.scrollIntoView({block:"nearest"})),e.preventDefault()}}}});function router(){const e=location.hash||"#/";if(e.startsWith("#/route/")){const[t,o]=e.replace("#/route/","").split("?");renderRoute(dec(t),new URLSearchParams(o||"").get("week"))}else e.startsWith("#/ledger")?renderLedger():e.startsWith("#/calendar")?renderCalendar():e.startsWith("#/ask")?renderAsk():e.startsWith("#/notes")?renderNotes():e.startsWith("#/fool")?renderFool():renderOverview()}window.addEventListener("hashchange",router),window.addEventListener("DOMContentLoaded",()=>{router(),new URLSearchParams(window.location.search).get("tour")==="1"&&setTimeout(window.startTour,400)});
