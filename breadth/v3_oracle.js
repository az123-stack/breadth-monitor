/* ---------- v3 · Groups → Oracle (Oct 30, 2026; Adam: "3 charts 180D / 60D / 15D side by side; Cohorts pills 180D / 60D / 15 day /
   5 day = the strongest stocks over that period, shown across all 3 charts") ----------
   DATA.themes.oracle (breadth/oracle.py): cohorts {d180, d60, d15, d5: [tickers, best first]}, rows {t: {name, sub, rsr, r: [180,60,15,5 returns],
   c: last 181 closes}}, spy (181 closes), dates. Each chart rebases every line to 0% at its window start. Live: today's Google price is added as
   the last point (cohorts stay as of the last close). */
const OR_COH = [["d180", "180D", 0], ["d60", "60D", 1], ["d15", "15 day", 2], ["d5", "5 day", 3]];
const OR_PAL = ["#2f6fdf", "#e0702b", "#2e9d5b", "#c23b6e", "#7b5bd6", "#c49a1a", "#1f9bb0", "#8c564b", "#d64545", "#5a6b7d"];
function oracleLine(vals, w, h, lo, hi) {
  const n = vals.length - 1, span = hi - lo || 1;
  return vals.map((v, i) => v == null ? null : `${(i / n * w).toFixed(1)},${(h - (v - lo) / span * h).toFixed(1)}`).filter(Boolean).join(" ");
}
function renderOracle(app) {
  const O = (DATA.themes || {}).oracle;
  if (!O) { app.append($('<div class="card empty">Oracle data appears after the next data run.</div>')); return; }
  UI.or = UI.or || { coh: lsGet("orCoh", "d5"), view: lsGet("orView", "stocks"), hl: null, log: lsGet("orLog", "0") === "1" };
  const U = UI.or, live = liveActive(), subs = U.view === "subs" && O.subs;
  app.append(liveBar());
  const SRC = subs ? O.subs : O.rows, list = ((subs ? O.scohorts : O.cohorts)[U.coh] || []).slice(0, 7).filter(t => SRC[t]);
  const col = (i) => OR_PAL[i % OR_PAL.length];
  // live: a stock gets today's price; a sub-theme gets the average live move of its members on top of its last index value
  const liveMove = (g) => { const v = (O.subs[g].members || []).map(t => liveRow(t)).filter(L => L && L.chg != null).map(L => L.chg); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };
  const series = (t) => { const c = SRC[t].c.slice(); if (live) { if (subs) { const m = liveMove(t); if (m != null) c.push(c[c.length - 1] * (1 + m)); } else { const L = liveRow(t); if (L && L.price) c.push(L.price); } } return c; };
  const spyS = (() => { const c = O.spy.slice(); if (live) { const L = liveRow("SPY"); if (L && L.price) c.push(L.price); } return c; })();
  const cname = (OR_COH.find(c => c[0] === U.coh) || OR_COH[3])[1];
  // ---- controls ----
  const what = subs ? "sub-themes" : "stocks";
  const head = $(`<section class="card orhead"><div class="orttl"><h2>Oracle <span class="meta">· the 7 strongest ${what} of the ${esc(cname)} cohort, drawn over 180, 60 and 15 sessions</span></h2></div>
    <div class="filters"></div>
    <div class="meta orsub">${subs ? "Cohort = sub-themes (3+ stocks with data) ranked by the return of their equal-weight index over that period" : `Cohort = our ${O.universe} liquid theme stocks ($5+, $10M+ a day, ADRs included) ranked by their return over that period`}, as of the ${shortDate(O.date)} close.
    Each chart starts every line at 0% at the left edge. <b>Bold</b> = the cohort's median, dashed = SPY. Hover or tap a ticker to follow it across all three charts.${live ? " Today's live price is the last point." : ""}</div></section>`);
  const f = head.querySelector(".filters"), save = () => { lsSet("orCoh", U.coh); lsSet("orView", U.view); lsSet("orLog", U.log ? "1" : "0"); U.hl = null; rerenderPanel(); };
  f.append(chips("View", [["stocks", "Stocks"], ["subs", "Sub-themes"]], U, "view", save));
  f.append(chips("Cohorts", OR_COH.map(c => [c[0], c[1]]), U, "coh", save));
  const sst = { s: U.log ? "log" : "lin" }; f.append(chips("Scale", [["lin", "% scale"], ["log", "Log scale"]], sst, "s", () => { U.log = sst.s === "log"; save(); }));
  // overlap line
  const coh = subs ? O.scohorts : O.cohorts;
  head.append($(`<div class="meta orov">Of these 7, also in the top 7 of: ${OR_COH.filter(c => c[0] !== U.coh).map(c => `<b>${c[1]}</b> ${(coh[c[0]] || []).filter(x => list.includes(x)).length}`).join(" · ")}</div>`));
  app.append(head);
  // ---- three charts ----
  const grid = $('<section class="orgrid"></section>');
  const W = 400, H = 230;
  O.windows.forEach((win) => {
    const cut = (c) => c.slice(-(win + 1 + (c.length - O.spy.length)));
    const base = (c) => { const s = cut(c), b = s.find(v => v != null); return s.map(v => v == null || !b ? null : (U.log ? Math.log(v / b) : v / b - 1)); };
    const lines = list.map((t, i) => ({ t, i, v: base(series(t)) }));
    const spy = base(spyS);
    const med = spy.map((_, k) => { const xs = lines.map(l => l.v[k]).filter(v => v != null).sort((a, b) => a - b); return xs.length ? xs[Math.floor(xs.length / 2)] : null; });
    const all = [...lines.flatMap(l => l.v), ...spy].filter(v => v != null);
    const lo = Math.min(0, ...all), hi = Math.max(0, ...all), pad = (hi - lo) * 0.06; const L0 = lo - pad, H0 = hi + pad;
    const y0 = H - (0 - L0) / (H0 - L0) * H;
    const fmtY = (v) => U.log ? (Math.exp(v) - 1) : v;
    const ticks = [L0 + (H0 - L0) * 0.1, (L0 + H0) / 2, H0 - (H0 - L0) * 0.1].map(v => ({ y: H - (v - L0) / (H0 - L0) * H, l: pct(fmtY(v), 0) }));
    const end = (l) => l.v[l.v.length - 1];
    const ranked = lines.slice().sort((a, b) => (end(b) ?? -9) - (end(a) ?? -9));
    const d0 = O.dates[O.dates.length - 1 - win];
    const card = $(`<div class="card orchart"><div class="orch-h"><b>${win} sessions</b><span class="meta">since ${shortDate(d0)} · median ${pct(fmtY(end({ v: med })))} · SPY ${pct(fmtY(end({ v: spy })))}</span></div>
      <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" class="orsvg" role="img" aria-label="${esc(cname)} cohort over ${win} sessions">
        ${ticks.map(k => `<line x1="0" x2="${W}" y1="${k.y.toFixed(1)}" y2="${k.y.toFixed(1)}" class="orgridl"/>`).join("")}
        <line x1="0" x2="${W}" y1="${y0.toFixed(1)}" y2="${y0.toFixed(1)}" class="orzero"/>
        ${lines.map(l => `<polyline data-t="${esc(l.t)}" class="orl" points="${oracleLine(l.v, W, H, L0, H0)}" stroke="${col(l.i)}"/>`).join("")}
        <polyline class="orspy" points="${oracleLine(spy, W, H, L0, H0)}"/>
        <polyline class="ormed" points="${oracleLine(med, W, H, L0, H0)}"/>
      </svg>
      <div class="oraxis">${ticks.map(k => `<span style="top:${(k.y / H * 100).toFixed(1)}%">${k.l}</span>`).join("")}</div>
      <div class="orrank">${ranked.map(l => `<span data-t="${esc(l.t)}"><i style="background:${col(l.i)}"></i>${esc(subs && l.t.length > 22 ? l.t.slice(0, 21) + "…" : l.t)} ${pct(fmtY(end(l)), 0)}</span>`).join("")}</div></div>`);
    grid.append(card);
  });
  app.append(grid);
  // ---- table of the cohort ----
  const retCells = (r) => r.map((v, k) => `<td class="num ${tint(v, [0.6, 0.3, 0.12, 0.06][k])}${OR_COH[k][0] === U.coh ? " orsel" : ""}">${pct(v, 0)}</td>`).join("");
  const tbl = $(`<section class="card ortable"><div class="head"><h2>${esc(cname)} cohort · ${what} <span class="meta">· strongest first${subs ? " · equal-weight index of each sub-theme" : " · click a ticker for details"}</span></h2>
      <button class="xopen ortv">⬇ TradingView</button></div>
    <div class="scroll"><table class="grid"><thead><tr><th>#</th><th class="l">${subs ? "Sub-theme" : "Ticker"}</th><th class="l">${subs ? "Stocks (best 180D first)" : "Sub-theme"}</th><th>${subs ? "Strength" : "RS"}</th><th>180D</th><th>60D</th><th>15D</th><th>5D</th>${live ? "<th>Today</th>" : ""}</tr></thead><tbody>
    ${list.map((t, i) => { const r = SRC[t];
      if (subs) { const m = live ? liveMove(t) : null;
        return `<tr data-t="${esc(t)}"><td class="num">${i + 1}</td><td class="l"><i class="orsw" style="background:${col(i)}"></i><b>${esc(t)}</b><small class="meta" style="display:block">${esc(r.group || "")} · ${r.n} stocks</small></td>
          <td class="l orsubs">${r.members.map(x => `<a href="#" class="tkl" data-t="${esc(x)}">${esc(x)}</a>`).join(" ")}</td><td class="num">${r.strength == null ? "–" : Math.round(r.strength)}</td>${retCells(r.r)}
          ${live ? `<td class="num">${m == null ? "–" : `<span class="${m > 0 ? "up" : "dn"}">${pct(m)}</span>`}</td>` : ""}</tr>`; }
      const L = live ? liveRow(t) : null;
      return `<tr data-t="${esc(t)}"><td class="num">${i + 1}</td><td class="l"><i class="orsw" style="background:${col(i)}"></i><a href="#" class="tkl" data-t="${esc(t)}"><b>${esc(t)}</b></a><small class="meta" style="display:block">${esc(r.name || "")}</small></td>
        <td class="l">${esc(r.sub || "–")}</td><td class="num">${r.rsr ?? "–"}</td>${retCells(r.r)}
        ${live ? `<td class="num">${L && L.chg != null ? `<span class="${L.chg > 0 ? "up" : "dn"}">${pct(L.chg)}</span>` : "–"}</td>` : ""}</tr>`; }).join("")}
    <tr class="orspyrow"><td></td><td class="l"><b>SPY</b></td><td class="l meta">benchmark</td><td></td>${(O.spy_r || []).map(v => `<td class="num">${pct(v, 1)}</td>`).join("")}${live ? "<td></td>" : ""}</tr>
    </tbody></table></div></section>`);
  app.append(tbl);
  tbl.querySelector(".ortv").addEventListener("click", () => tsDownload("oracle-" + cname.replace(/\s+/g, "").toLowerCase(),
    subs ? list.map(g => ({ name: "Oracle - " + cname + " - " + g, ticks: O.subs[g].members })) : [{ name: "Oracle - " + cname + " cohort", ticks: list }]));
  // ---- highlight a ticker across all charts ----
  const hl = (t) => { app.querySelectorAll(".orl").forEach(p => { p.classList.toggle("on", p.dataset.t === t); p.classList.toggle("dim", !!t && p.dataset.t !== t); });
    app.querySelectorAll(".orrank span, .ortable tr[data-t]").forEach(e => e.classList.toggle("on", e.dataset.t === t));
    app.querySelectorAll(".orl.on").forEach(p => p.parentNode.appendChild(p)); };
  app.querySelectorAll(".orl, .orrank span, .ortable tr[data-t]").forEach(e => {
    e.addEventListener("mouseenter", () => hl(e.dataset.t)); e.addEventListener("mouseleave", () => hl(U.hl));
    e.addEventListener("click", (ev) => { if (ev.target.closest("a.tkl")) return; U.hl = U.hl === e.dataset.t ? null : e.dataset.t; hl(U.hl); }); });
  if (U.hl) hl(U.hl);
}
