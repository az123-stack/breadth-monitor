/* ---------- v3 · Groups → Oracle (Oct 30, 2026; Adam: "3 charts 180D / 60D / 15D side by side; Cohorts pills 180D / 60D / 15 day /
   5 day = the strongest stocks over that period, shown across all 3 charts") ----------
   DATA.themes.oracle (breadth/oracle.py): cohorts {d180, d60, d15, d5: [tickers, best first]}, rows {t: {name, sub, rsr, r: [180,60,15,5 returns],
   c: last 181 closes}}, spy (181 closes), dates. Each chart rebases every line to 0% at its window start. Live: today's Google price is added as
   the last point (cohorts stay as of the last close). */
const OR_COH = [["d180", "180D", 0], ["d60", "60D", 1], ["d30", "30D", 2], ["d15", "15 day", 3], ["d5", "5 day", 4], ["d1", "Today", 5]];   // 30D added Oct 31 (Adam); Today Nov 4
// Nov 4 (Adam: "get the intraday / premarket data into the oracle"): before the open the Oracle reads Yahoo pre-market quotes (docs/premarket.json,
// same rows as the Pre-market tab, via ROWS_OVERRIDE); in the session it reads the live Google sheet. Today's price is the last point on every
// chart, the Today column shows the move, and the "Today" cohort ranks stocks / sub-themes by it. Thin pre-market quotes (< 3 active 5-min bars)
// stay out of the Today ranking. Outside both, "Today" = the last session's move.
function orSession() {
  if (liveActive()) return "live";
  if (typeof PM !== "undefined" && PM && PM.date === etToday() && PM.rows && Object.keys(PM.rows).length) return "pre";   // before Google shows today's session
  return null;
}
function renderOracle(app) {
  const c = nyClock(); if (typeof PM !== "undefined" && !PM && !PM_ERR && c.mins < 0 && c.mins > -330) fetchPM();
  const S = orSession();
  if (S !== "pre") return renderOracleBody(app, S);
  ROWS_OVERRIDE = pmRows();
  try { return renderOracleBody(app, S); } finally { ROWS_OVERRIDE = null; }
}
function orSessionBar(S) {
  if (S !== "pre") return liveBar();
  const clk = nyClock(), asof = (PM.asof || "").slice(11, 16), n = Object.keys(PM.rows || {}).length;
  const el = $(`<div class="livebar"><span class="dot ${clk.mins < 0 ? "on" : "off"}"></span><span><b>Pre-market</b> · Yahoo quotes as of <b>${asof} ET</b> (${n.toLocaleString()} tickers) · refreshed about every 10 min until the open${clk.mins >= 0 ? " · the live Google prices take over once the sheet shows today's session" : ""}</span><button>Refresh</button></div>`);
  el.querySelector("button").addEventListener("click", () => fetchPM());
  return el;
}
// Oct 31 (Adam: "a filter for groups like Defense IT / IT Services starting to accelerate … catch runners like Cloud Communications"):
// rows / subs carry ac = {a accelerating, st strong 60D, stage early|running, start, on20, v [180, 60, 15] vs SPY} from oracle.acc_tag
const OR_FLT = [["all", "All"], ["acc", "▲ Accelerating vs SPY"], ["acc_early", "▲ Accelerating · early"], ["strong", "Strong 60D vs SPY"]];
const orPass = (ac, f) => f === "all" || (!!ac && (f === "acc" ? ac.a : f === "acc_early" ? ac.a && ac.stage === "early" : ac.st));
function orAccCell(ac) {
  if (!ac) return '<td class="l meta">–</td>';
  const v = ac.v || [], tag = ac.a ? `<span class="oracc ${ac.stage}">▲ Accelerating · ${ac.stage}${ac.start ? " · since " + shortDate(ac.start) : ""}</span>` : ac.st ? '<span class="oracc st">Strong 60D</span>' : "";
  return `<td class="l orvs" data-v="${ac.a ? 2 : ac.st ? 1 : 0}${(v[1] ?? 0).toFixed(3)}">${tag}<small class="meta">180 ${pct(v[0], 0)} · 60 ${pct(v[1], 0)} · 15 ${pct(v[2], 0)}</small></td>`;
}
// ---- buckets: Adam's own named lists of sub-themes (Oct 31). {order: [names], m: {name: [sub-themes]}}, saved in this browser ----
const OR_BK_DEF = () => ({ order: ["Emerging", "Mature"], m: { Emerging: [], Mature: [] } });
function orBuckets() {
  try { const b = JSON.parse(lsGet("orBuckets", "") || "null"); if (b && Array.isArray(b.order) && b.m) { b.order = b.order.filter(n => Array.isArray(b.m[n])); return b; } } catch (e) {}
  return OR_BK_DEF();
}
const orBucketsSave = (b) => lsSet("orBuckets", JSON.stringify(b));
function orToggleBucket(name, g) {
  const b = orBuckets(); if (!b.m[name]) return; const i = b.m[name].indexOf(g);
  if (i >= 0) b.m[name].splice(i, 1); else b.m[name].push(g); orBucketsSave(b);
}
// pills that put a sub-theme in / out of each bucket (click doesn't select the row)
const orBkPills = (g, B) => B.order.map(n => `<button class="orbkp${B.m[n].includes(g) ? " on" : ""}" data-g="${esc(g)}" data-b="${esc(n)}" title="${B.m[n].includes(g) ? "Take out of" : "Put in"} ${esc(n)}">${B.m[n].includes(g) ? "✓ " : "+ "}${esc(n)}</button>`).join("");
const orBkTags = (g, B) => B.order.filter(n => B.m[n].includes(g)).map(n => `<span class="orbkt">${esc(n)}</span>`).join("");
const OR_TOP = 15;   // Adam, Oct 30: top 7 → "lets try top 15"
const OR_PAL = ["#2f6fdf", "#e0702b", "#2e9d5b", "#c23b6e", "#7b5bd6", "#c49a1a", "#1f9bb0", "#8c564b", "#d64545", "#5a6b7d", "#0f8a7e", "#b5568f", "#6b8e23", "#d4813a", "#4b6cb7"];
function oracleLine(vals, w, h, lo, hi) {
  const n = vals.length - 1, span = hi - lo || 1;
  return vals.map((v, i) => v == null ? null : `${(i / n * w).toFixed(1)},${(h - (v - lo) / span * h).toFixed(1)}`).filter(Boolean).join(" ");
}
function renderOracleBody(app, S) {
  const O = (DATA.themes || {}).oracle;
  if (!O) { app.append($('<div class="card empty">Oracle data appears after the next data run.</div>')); return; }
  UI.or = UI.or || { side: lsGet("orSide", "strong"), coh: lsGet("orCoh", "d5"), view: lsGet("orView", "stocks"), hl: null, log: lsGet("orLog", "0") === "1", sub: lsGet("orSub", ""), pg: 0, flt: lsGet("orFlt", "all"), bk: lsGet("orBk", "") };
  const U = UI.or, live = !!S, subs = U.view === "subs" && O.subs;
  app.append(orSessionBar(S));
  const weakSide = U.side === "weak" && O.wcohorts;   // strongest (best return first) or weakest (worst return first)
  // ---- today's move (live / pre-market / last session) and the Today cohort ----
  const oneDay = (c) => c && c.length > 1 && c[c.length - 2] ? c[c.length - 1] / c[c.length - 2] - 1 : null;
  const sessRow = (t) => { const L = liveRow(t); return L && L.chg != null && (S !== "pre" || (L.bars || 0) >= 3) ? L : null; };
  const liveMove = (g) => { const v = (O.subs[g].members || []).map(sessRow).filter(Boolean).map(L => L.chg); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };
  const todayOf = (t, sub) => { if (live) { if (sub) { const m = liveMove(t); if (m != null) return m; } else { const L = sessRow(t); if (L) return L.chg; } return null; }
    return oneDay((sub ? O.subs : O.rows)[t].c); };
  const todayRank = (sub) => { const src = sub ? O.subs : O.rows;
    return Object.keys(src).filter(t => sub || src[t].lq).map(t => [t, todayOf(t, sub)]).filter(x => x[1] != null).sort((a, b) => b[1] - a[1]).map(x => x[0]); };
  const T1 = U.coh === "d1" ? todayRank(subs) : null;
  const withToday = (C, rev) => T1 ? Object.assign({}, C, { d1: (rev ? T1.slice().reverse() : T1).slice(0, 30) }) : C;
  const COH = withToday(subs ? (weakSide ? O.wscohorts : O.scohorts) : (weakSide ? O.wcohorts : O.cohorts), weakSide);
  // Adam, Oct 31: "run through all the sub-themes 15 at a time" → sub-theme view pages through the full ranking (O.sall), 15 per page
  // stocks page too when a filter is on (O.rall = every liquid stock ranked); filters keep the cohort's order
  // Oct 31 (Adam: "I need the ability to find a specific sub-theme in here"): a search box finds sub-themes (name, group, or a ticker they hold)
  // or stocks (ticker / company); a search looks through every name in the ranking and ignores the Filter row
  const q = (U.q || "").trim().toLowerCase();
  const qHit = (k) => { if (!q) return true; if (subs) { const g = O.subs[k]; return k.toLowerCase().includes(q) || (g.group || "").toLowerCase().includes(q) || (g.members || []).some(t => t.toLowerCase() === q); }
    const r = O.rows[k]; return k.toLowerCase().startsWith(q) || (r.name || "").toLowerCase().includes(q) || (q.length >= 3 && (r.sub || "").toLowerCase().includes(q)); };
  // Oct 31 (Adam: "bucket a list of sub-themes … a list of emerging, show only those, then pick the ones I think are mature"): his own named
  // lists of sub-themes, kept in this browser (localStorage orBuckets); a bucket narrows both views (stocks view = stocks whose sub-theme is in it)
  const B = orBuckets(), bk = U.bk && B.m[U.bk] ? U.bk : "", bkSet = bk && !q ? new Set(B.m[bk]) : null;
  const bkHit = (k) => !bkSet || bkSet.has(subs ? k : (O.rows[k] || {}).sub);
  const fl = q ? "all" : (OR_FLT.some(x => x[0] === U.flt) ? U.flt : "all"), RK0 = subs ? O.sall : (fl !== "all" || q || bkSet ? O.rall : null);
  const RK = RK0 && T1 ? Object.assign({}, RK0, { d1: T1 }) : RK0;
  const ALL = RK && RK[U.coh] ? (weakSide ? RK[U.coh].slice().reverse() : RK[U.coh]).filter(g => (subs ? O.subs : O.rows)[g] && orPass((subs ? O.subs : O.rows)[g].ac, fl) && qHit(g) && bkHit(g)) : null;
  const npg = ALL ? Math.ceil(ALL.length / OR_TOP) : 1, pg = Math.min(U.pg || 0, npg - 1), off = pg * OR_TOP;
  const SRC = subs ? O.subs : O.rows, list = (ALL ? ALL.slice(off, off + OR_TOP) : (COH[U.coh] || []).slice(0, OR_TOP)).filter(t => SRC[t]);
  const fName0 = { acc: "accelerating vs SPY", acc_early: "accelerating vs SPY, early", strong: "strong 60D vs SPY" }[fl] || "";
  const fName = [bkSet ? `in your “${esc(bk)}” bucket` : "", fName0].filter(Boolean).join(", ");
  const rankTxt = !ALL ? "" : q ? `matching “${esc(U.q.trim())}”: ${ALL.length ? `${off + 1}–${off + list.length} of ${ALL.length}` : "none"}` : (fl !== "all" || bkSet) ? `${fName}: ${ALL.length ? `${off + 1}–${off + list.length} of ${ALL.length}` : "none today"}` : pg ? `ranked ${off + 1}–${off + list.length} of ${ALL.length}` : "";
  const col = (i) => OR_PAL[i % OR_PAL.length];
  // live: a stock gets today's price; a sub-theme gets the average live move of its members on top of its last index value
  const series = (t) => { const c = SRC[t].c.slice(); if (live) { if (subs) { const m = liveMove(t); if (m != null) c.push(c[c.length - 1] * (1 + m)); } else { const L = liveRow(t); if (L && L.price) c.push(L.price); } } return c; };
  const spyS = (() => { const c = O.spy.slice(); if (live) { const L = liveRow("SPY"); if (L && L.price) c.push(L.price); } return c; })();
  const cname = (OR_COH.find(c => c[0] === U.coh) || OR_COH[3])[1];
  const srcName = S === "pre" ? `pre-market move (Yahoo, ${(PM.asof || "").slice(11, 16)} ET)` : S === "live" ? "live move today (Google sheet)" : `move on the ${shortDate(O.date)} close (last session)`;
  // ---- controls ----
  const what = subs ? "sub-themes" : "stocks";
  const head = $(`<section class="card orhead"><div class="orttl"><h2>Oracle <span class="meta">· ${rankTxt ? `${what} ${rankTxt} (${weakSide ? "weakest" : "strongest"} first)` : `the ${OR_TOP} ${weakSide ? "weakest" : "strongest"} ${what}`} of the ${esc(cname)} cohort, drawn over 180, 60 and 15 sessions</span></h2></div>
    <div class="filters"></div>
    <div class="meta orsub">${subs ? "Cohort = sub-themes (3+ stocks with data) ranked by the return of their equal-weight index over that period" : `Cohort = our ${O.universe} liquid theme stocks ($5+, $10M+ a day, ADRs included) ranked by their return over that period`}${weakSide ? " (worst first)" : ""}, ${U.coh === "d1" ? `<b>Today</b> = ranked by the ${srcName}${subs ? " (average of the members)" : ""}${S === "pre" ? "; quotes with fewer than 3 active 5-minute bars are left out" : ""}` : `as of the ${shortDate(O.date)} close`}.
    Each chart starts every line at 0% at the left edge. <b>Bold</b> = the cohort's median, dashed = SPY. Hover or tap a ticker to follow it across all three charts.${S === "pre" ? " Today's pre-market price is the last point." : live ? " Today's live price is the last point." : ""}</div></section>`);
  const f = head.querySelector(".filters"), save = () => { lsSet("orSide", U.side); lsSet("orCoh", U.coh); lsSet("orView", U.view); lsSet("orLog", U.log ? "1" : "0"); U.hl = null; U.pg = 0; rerenderPanel(); };
  f.append(chips("Side", [["strong", "Strongest"], ["weak", "Weakest"]], U, "side", save));
  f.append(chips("View", [["stocks", "Stocks"], ["subs", "Sub-themes"]], U, "view", save));
  f.append(chips("Cohorts", OR_COH.map(c => [c[0], c[1]]), U, "coh", save));
  const cnt = (k) => Object.values(subs ? O.subs : O.rows).filter(r => (subs || r.lq) && orPass(r.ac, k)).length;
  f.append(chips("Filter", OR_FLT.map(([k, l]) => [k, k === "all" ? l : `${l} <small>${cnt(k)}</small>`]), U, "flt", () => { lsSet("orFlt", U.flt); save(); }));
  // ---- bucket bar ----
  const bst = { bk };
  const bkBar = $(`<div class="orbkbar"></div>`);
  bkBar.append(chips("Bucket", [["", "All sub-themes"], ...B.order.map(n => [n, `${esc(n)} <small>${B.m[n].length}</small>`])], bst, "bk", () => { U.bk = bst.bk; lsSet("orBk", U.bk); save(); }));
  const bkCtl = $(`<span class="orbkctl"><input type="text" class="orbknew" placeholder="New bucket name" maxlength="30" aria-label="New bucket name"><button class="xopen orbkadd">+ Add bucket</button>
    ${bk ? `<button class="xopen orbkren">Rename “${esc(bk)}”</button><button class="xopen orbkdel">Delete “${esc(bk)}”</button>` : ""}<button class="xopen orbkbak">Backup / restore</button></span>`);
  bkBar.append(bkCtl);
  const nb = bkCtl.querySelector(".orbknew");
  const addBk = () => { const n = nb.value.trim().replace(/\s+/g, " "); if (!n) { nb.focus(); return; } const b = orBuckets();
    if (!b.m[n]) { b.m[n] = []; b.order.push(n); orBucketsSave(b); } U.bk = n; lsSet("orBk", n); save(); };
  bkCtl.querySelector(".orbkadd").addEventListener("click", addBk);
  nb.addEventListener("keydown", (e) => { if (e.key === "Enter") addBk(); });
  if (bk) {
    bkCtl.querySelector(".orbkren").addEventListener("click", () => { const n = nb.value.trim().replace(/\s+/g, " ");
      if (!n) { nb.placeholder = "Type the new name here, then Rename"; nb.focus(); return; } const b = orBuckets(); if (b.m[n]) { nb.value = ""; nb.placeholder = "That name is taken"; return; }
      b.m[n] = b.m[bk]; delete b.m[bk]; b.order = b.order.map(x => x === bk ? n : x); orBucketsSave(b); U.bk = n; lsSet("orBk", n); save(); });
    const del = bkCtl.querySelector(".orbkdel");
    del.addEventListener("click", () => { if (!del.dataset.sure) { del.dataset.sure = "1"; del.textContent = `Click again to delete “${bk}” (${B.m[bk].length} sub-themes)`; return; }
      const b = orBuckets(); delete b.m[bk]; b.order = b.order.filter(x => x !== bk); orBucketsSave(b); U.bk = ""; lsSet("orBk", ""); save(); });
  }
  bkCtl.querySelector(".orbkbak").addEventListener("click", () => { if (bkBar.querySelector(".orbkbox")) { bkBar.querySelector(".orbkbox").remove(); return; }
    const box = $(`<div class="orbkbox meta">Your buckets are saved in this browser only. To move them to another computer or phone: copy this text, open the page there,
      click Backup / restore, paste it in and click Restore.<textarea rows="4" spellcheck="false"></textarea><button class="xopen orbkcopy">Copy</button> <button class="xopen orbkrest">Restore from the text above</button> <span class="orbkmsg"></span></div>`);
    const ta = box.querySelector("textarea"), msg = box.querySelector(".orbkmsg"); ta.value = JSON.stringify(orBuckets());
    box.querySelector(".orbkcopy").addEventListener("click", () => { ta.select(); try { navigator.clipboard.writeText(ta.value); } catch (e) { document.execCommand("copy"); } msg.textContent = "Copied."; });
    box.querySelector(".orbkrest").addEventListener("click", () => { try { const b = JSON.parse(ta.value);
        if (!b || !Array.isArray(b.order) || !b.m || b.order.some(n => !Array.isArray(b.m[n]))) throw 0;
        orBucketsSave({ order: b.order, m: Object.fromEntries(b.order.map(n => [n, b.m[n].filter(x => typeof x === "string")])) }); U.bk = ""; lsSet("orBk", ""); save();
      } catch (e) { msg.textContent = "That text isn't a bucket backup. Copy it again from the other device."; } });
    bkBar.append(box); });
  const qi = $(`<input type="search" class="orq" placeholder="${subs ? "Find a sub-theme (or a ticker it holds)" : "Find a ticker or company"}" aria-label="Find">`); qi.value = U.q || "";
  let qt = null;
  qi.addEventListener("input", () => { clearTimeout(qt); qt = setTimeout(() => { U.q = qi.value; U.pg = 0; U.hl = null; U.sub = "";
    rerenderPanel(); const n = PQ(".orq"); if (n) { n.focus(); n.setSelectionRange(n.value.length, n.value.length); } }, 250); });
  f.append(qi);
  f.after(bkBar);
  const sst = { s: U.log ? "log" : "lin" }; f.append(chips("Scale", [["lin", "% scale"], ["log", "Log scale"]], sst, "s", () => { U.log = sst.s === "log"; save(); }));
  if (q && !ALL.length) { const tk = subs && O.rows[U.q.trim().toUpperCase()];
    head.append($(`<div class="meta oraccnote">${tk ? `${esc(U.q.trim().toUpperCase())}'s sub-theme (${esc(tk.sub || "none")}) has fewer than 3 stocks with data, so it isn't drawn as a group. Switch View to <b>Stocks</b> to find ${esc(U.q.trim().toUpperCase())} itself.`
      : `Nothing matches “${esc(U.q.trim())}” in the ${subs ? "sub-themes" : "liquid theme stocks"}. Clear the box to see the full list.`}</div>`)); }
  if (fl !== "all") head.append($(`<div class="meta oraccnote"><b>Accelerating vs SPY</b> = its line against SPY is rising faster over the last 15 sessions than over 60,
    and faster over 60 than over 180, with 60 sessions at least +10% vs SPY. <b>Early</b> = less than +25% vs SPY over 180 sessions (the run is young), <b>running</b> = already more.
    <b>Strong 60D</b> = +10% vs SPY over 60 sessions, accelerating or not. Tested on sub-themes Jul 2025–Oct 2026: accelerating groups beat the average group by +4.9% over the next
    40 sessions (t 4.3, both halves), early +5.1%, running +6.7%. But groups simply strong on 60D did as well (+5.7%); the speed-up on top added nothing (−0.8 pts, not significant).
    The average is carried by a few big runners (Cloud Communications fired Mar 6 at the start of its run, Memory Aug 2025, Custom Silicon Apr 2026); the median episode ≈ flat. A watch list, not a buy signal.</div>`));
  if (bkSet && !ALL.length) head.append($(`<div class="meta oraccnote">${B.m[bk].length ? `None of the ${B.m[bk].length} sub-themes in your “${esc(bk)}” bucket pass the Filter row. Set Filter to All.`
    : `Your “${esc(bk)}” bucket is empty. Pick <b>All sub-themes</b> under Bucket, switch View to <b>Sub-themes</b>, and click <b>+ ${esc(bk)}</b> on the rows you want in it.`}</div>`));
  if (ALL && npg > 1) {   // page through every sub-theme, 15 at a time
    const goPg = (n) => { U.pg = Math.max(0, Math.min(npg - 1, n)); U.sub = ""; U.hl = null; rerenderPanel(); };
    const pst = { p: String(pg) };
    const pager = $(`<div class="orpager"><button class="xopen orprev"${pg ? "" : " disabled"}>◀ Prev 15</button><span class="orpgs"></span><button class="xopen ornext"${pg < npg - 1 ? "" : " disabled"}>Next 15 ▶</button>
      <span class="meta">${ALL.length} ${what} · showing ${off + 1}–${off + list.length}</span></div>`);
    if (npg <= 12) pager.querySelector(".orpgs").append(chips("Ranks", Array.from({ length: npg }, (_, k) => [String(k), `${k * OR_TOP + 1}–${Math.min(ALL.length, (k + 1) * OR_TOP)}`]), pst, "p", () => goPg(+pst.p)));
    else pager.querySelector(".orpgs").textContent = `page ${pg + 1} of ${npg}`;
    pager.querySelector(".orprev").addEventListener("click", () => goPg(pg - 1));
    pager.querySelector(".ornext").addEventListener("click", () => goPg(pg + 1));
    head.append(pager);
  }
  // overlap line
  const coh = COH;
  if (!pg && fl === "all" && !q && !bkSet) head.append($(`<div class="meta orov">Of these ${OR_TOP}, also in the top ${OR_TOP} of: ${OR_COH.filter(c => c[0] !== U.coh && coh[c[0]]).map(c => `<b>${c[1]}</b> ${(coh[c[0]] || []).filter(x => list.includes(x)).length}`).join(" · ")}</div>`));
  app.append(head);
  // ---- three charts (drawn for any list of keys: the cohort, or a picked sub-theme's stocks) ----
  const W = 400, H = 230;
  const drawGrid = (keys, seriesFn, label, short) => {
    const grid = $('<section class="orgrid"></section>');
    O.windows.forEach((win) => {
      const cut = (c) => c.slice(-(win + 1 + (c.length - O.spy.length)));
      const base = (c) => { const s = cut(c), b = s.find(v => v != null); return s.map(v => v == null || !b ? null : (U.log ? Math.log(v / b) : v / b - 1)); };
      const lines = keys.map((t, i) => ({ t, i, v: base(seriesFn(t)) }));
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
      // time axis (Adam, Oct 31: "the months on the bottom axis, just a baseline of time"): the first session of each month on the
      // 180-session chart, dates every 10 / 5 sessions on the 60 / 15-session ones; x matches oracleLine (index ÷ points − 1)
      const wd = O.dates.slice(-(win + 1)), npts = Math.max(...lines.map(l => l.v.length), spy.length) - 1 || 1;
      const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const step = win > 60 ? 0 : win > 30 ? 10 : 5;   // 180: months · 60: every 10 sessions · 15: every 5
      const xt = !step
        ? wd.map((d, i) => i && d.slice(5, 7) !== wd[i - 1].slice(5, 7) ? { i, l: MON[+d.slice(5, 7) - 1] + (d.slice(5, 7) === "01" ? " " + d.slice(2, 4) : "") } : null).filter(Boolean)
        : wd.map((d, i) => i && i % step === 0 ? { i, l: shortDate(d) } : null).filter(Boolean);
      const xpos = (i) => i / npts * W;
      grid.append($(`<div class="card orchart"><div class="orch-h"><b>${win} sessions</b><span class="meta">since ${shortDate(d0)} · median ${pct(fmtY(end({ v: med })))} · SPY ${pct(fmtY(end({ v: spy })))}</span></div>
        <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" class="orsvg" role="img" aria-label="${esc(label)} over ${win} sessions">
          ${xt.map(k => `<line x1="${xpos(k.i).toFixed(1)}" x2="${xpos(k.i).toFixed(1)}" y1="0" y2="${H}" class="orgridl"/>`).join("")}
          ${ticks.map(k => `<line x1="0" x2="${W}" y1="${k.y.toFixed(1)}" y2="${k.y.toFixed(1)}" class="orgridl"/>`).join("")}
          <line x1="0" x2="${W}" y1="${y0.toFixed(1)}" y2="${y0.toFixed(1)}" class="orzero"/>
          ${lines.map(l => `<polyline data-t="${esc(l.t)}" class="orl" points="${oracleLine(l.v, W, H, L0, H0)}" stroke="${col(l.i)}"/>`).join("")}
          <polyline class="orspy" points="${oracleLine(spy, W, H, L0, H0)}"/>
          <polyline class="ormed" points="${oracleLine(med, W, H, L0, H0)}"/>
        </svg>
        <div class="orxaxis">${xt.map(k => `<span style="left:${(xpos(k.i) / W * 100).toFixed(2)}%">${k.l}</span>`).join("")}</div>
        <div class="oraxis">${ticks.map(k => `<span style="top:${(k.y / H * 100).toFixed(1)}%">${k.l}</span>`).join("")}</div>
        <div class="orrank">${ranked.map(l => `<span data-t="${esc(l.t)}"><i style="background:${col(l.i)}"></i>${esc(short && l.t.length > 22 ? l.t.slice(0, 21) + "…" : l.t)} ${pct(fmtY(end(l)), 0)}</span>`).join("")}</div></div>`));
    });
    return grid;
  };
  app.append(drawGrid(list, series, cname + " cohort", subs));
  // ---- table of the cohort ----
  // Today (Adam, Oct 31: "make sure today is one of the periods"): the live move while the sheet is newer than our close, else the last
  // session's move from the closes; ADR = 20-day average daily range % (stock tables)
  const spyToday = () => { if (live) { const L = liveRow("SPY"); if (L && L.chg != null) return L.chg; } return oneDay(O.spy); };
  // same look as the period columns (plain number, shaded cell, one-line header); the date sits in the header's tooltip
  const todayCell = (v) => `<td class="num ${tint(v, 0.03)}${U.coh === "d1" ? " orsel" : ""}">${pct(v, 1)}</td>`;
  const todayTh = `<th title="${S === "pre" ? "Pre-market move (Yahoo quotes)" : live ? "Live move from the Google sheet" : "Move on the " + shortDate(O.date) + " close (last session)"}">${S === "pre" ? "Pre-mkt" : "Today"}</th>`;
  const adrCell = (r) => `<td class="num">${r.adr == null ? "–" : r.adr.toFixed(1) + "%"}</td>`;
  const adrTh = '<th title="Average daily range over the last 20 sessions">ADR 20D</th>';
  const retCells = (r) => r.map((v, k) => `<td class="num ${tint(v, [0.6, 0.3, 0.2, 0.12, 0.06][k])}${OR_COH[k][0] === U.coh ? " orsel" : ""}">${pct(v, 0)}</td>`).join("");
  const tbl = $(`<section class="card ortable"><div class="head"><h2>${esc(cname)} cohort · ${what}${rankTxt ? " " + rankTxt : ""} <span class="meta">· ${weakSide ? "weakest" : "strongest"} first${subs ? " · equal-weight index of each sub-theme · click a row to see its stocks below" : " · click a ticker for details"}</span></h2>
      <button class="xopen ortv">⬇ TradingView</button></div>
    <div class="scroll"><table class="grid"><thead><tr><th>#</th><th class="l">${subs ? "Sub-theme" : "Ticker"}</th><th class="l">${subs ? "Stocks (best 180D first)" : "Sub-theme"}</th><th>${subs ? "Strength" : "RS"}</th>${subs ? "" : adrTh}<th>180D</th><th>60D</th><th>30D</th><th>15D</th><th>5D</th>${todayTh}<th class="l">Vs SPY</th>${subs ? '<th class="l">Buckets</th>' : ""}</tr></thead><tbody>
    ${list.map((t, i) => { const r = SRC[t];
      if (subs) {
        return `<tr data-t="${esc(t)}"><td class="num">${off + i + 1}</td><td class="l"><i class="orsw" style="background:${col(i)}"></i><b>${esc(t)}</b><small class="meta" style="display:block">${esc(r.group || "")} · ${r.n} stocks</small></td>
          <td class="l orsubs">${r.members.slice(0, 12).map(x => `<a href="#" class="tkl" data-t="${esc(x)}">${esc(x)}</a>`).join(" ")}${r.members.length > 12 ? ` <span class="meta">+${r.members.length - 12}</span>` : ""}</td><td class="num">${r.strength == null ? "–" : Math.round(r.strength)}</td>${retCells(r.r)}${todayCell(todayOf(t, true))}${orAccCell(r.ac)}
          <td class="l orbkc">${orBkPills(t, B)}</td></tr>`; }
      return `<tr data-t="${esc(t)}"><td class="num">${off + i + 1}</td><td class="l"><i class="orsw" style="background:${col(i)}"></i><a href="#" class="tkl" data-t="${esc(t)}"><b>${esc(t)}</b></a><small class="meta" style="display:block">${esc(r.name || "")}</small></td>
        <td class="l">${esc(r.sub || "–")}${r.sub ? orBkTags(r.sub, B) : ""}</td><td class="num">${r.rsr ?? "–"}</td>${adrCell(r)}${retCells(r.r)}${todayCell(todayOf(t, false))}${orAccCell(r.ac)}</tr>`; }).join("")}
    <tr class="orspyrow"><td></td><td class="l"><b>SPY</b></td><td class="l meta">benchmark</td><td></td>${subs ? "" : "<td></td>"}${(O.spy_r || []).map(v => `<td class="num">${pct(v, 1)}</td>`).join("")}${todayCell(spyToday())}<td></td>${subs ? "<td></td>" : ""}</tr>
    </tbody></table></div></section>`);
  app.append(tbl);
  // ---- a picked sub-theme's stocks (Adam, Oct 30: "select a sub-theme and have its stocks show below") ----
  if (subs) {
    const allSubs = Object.keys(O.subs).sort();
    if (!U.sub || !O.subs[U.sub]) U.sub = list[0];
    const g = O.subs[U.sub], mem = (g ? g.members : []).filter(t => O.rows[t]);
    const stockSeries = (t) => { const c = O.rows[t].c.slice(); if (live) { const L = liveRow(t); if (L && L.price) c.push(L.price); } return c; };
    const sec = $(`<section class="card orpick"><div class="head"><h2>Stocks in <span class="orpickname"></span> <span class="meta">· ${mem.length} stocks, best 180D first · pick another sub-theme from the list or click one in the table above</span></h2>
        <div class="orpickctl"><select aria-label="Pick a sub-theme">${allSubs.map(x => `<option${x === U.sub ? " selected" : ""}>${esc(x)}</option>`).join("")}</select><button class="xopen orpicktv">⬇ TradingView</button></div></div>
        ${U.sub ? `<div class="orbkc orpickbk"><span class="meta">Buckets:</span> ${orBkPills(U.sub, B)}</div>` : ""}</section>`);
    sec.querySelector(".orpickname").textContent = U.sub || "";
    app.append(sec);
    if (mem.length) {
      app.append(drawGrid(mem, stockSeries, U.sub + " stocks", false));
      app.append($(`<section class="card ortable orpicktable"><div class="scroll"><table class="grid"><thead><tr><th>#</th><th class="l">Ticker</th><th>RS</th>${adrTh}<th>180D</th><th>60D</th><th>30D</th><th>15D</th><th>5D</th>${todayTh}<th class="l">Vs SPY</th></tr></thead><tbody>
        ${mem.map((t, i) => { const r = O.rows[t];
          return `<tr data-t="${esc(t)}"><td class="num">${i + 1}</td><td class="l"><i class="orsw" style="background:${col(i)}"></i><a href="#" class="tkl" data-t="${esc(t)}"><b>${esc(t)}</b></a><small class="meta" style="display:block">${esc(r.name || "")}</small></td>
            <td class="num">${r.rsr ?? "–"}</td>${adrCell(r)}${retCells(r.r)}${todayCell(todayOf(t, false))}${orAccCell(r.ac)}</tr>`; }).join("")}
        </tbody></table></div></section>`));
    }
    sec.querySelector("select").addEventListener("change", (e) => { U.sub = e.target.value; lsSet("orSub", U.sub); U.hl = null; rerenderPanel(); });
    sec.querySelector(".orpicktv").addEventListener("click", () => tsDownload("oracle-" + (U.sub || "").replace(/[^a-z0-9]+/gi, "-").toLowerCase(), [{ name: "Oracle - " + U.sub, ticks: mem }]));
    tbl.querySelectorAll("tr[data-t]").forEach(tr => tr.addEventListener("click", (ev) => { if (ev.target.closest("a.tkl")) return; U.sub = tr.dataset.t; lsSet("orSub", U.sub); U.hl = null; rerenderPanel();
      setTimeout(() => { const c = PQ(".orpick"); if (c) c.scrollIntoView({ behavior: "smooth", block: "start" }); }, 60); }));
  }
  app.querySelectorAll(".orbkp").forEach(b => b.addEventListener("click", (ev) => { ev.stopPropagation(); orToggleBucket(b.dataset.b, b.dataset.g); rerenderPanel(); }));
  tbl.querySelector(".ortv").addEventListener("click", () => tsDownload("oracle-" + cname.replace(/\s+/g, "").toLowerCase(),
    subs ? list.map(g => ({ name: "Oracle - " + (weakSide ? "weakest " : "") + cname + " - " + g, ticks: O.subs[g].members })) : [{ name: "Oracle - " + (weakSide ? "weakest " : "") + cname + " cohort", ticks: list }]));
  // ---- highlight a ticker across all charts ----
  // dims only inside a chart grid that actually has the hovered / picked line, so the other grid stays fully drawn
  const hl = (t) => { app.querySelectorAll(".orgrid").forEach(g => { const has = !!t && [...g.querySelectorAll(".orl")].some(p => p.dataset.t === t);
      g.querySelectorAll(".orl").forEach(p => { p.classList.toggle("on", has && p.dataset.t === t); p.classList.toggle("dim", has && p.dataset.t !== t); });
      g.querySelectorAll(".orl.on").forEach(p => p.parentNode.appendChild(p)); });
    app.querySelectorAll(".orrank span, .ortable tr[data-t]").forEach(e => e.classList.toggle("on", !!t && e.dataset.t === t)); };
  app.querySelectorAll(".orl, .orrank span, .ortable tr[data-t]").forEach(e => {
    e.addEventListener("mouseenter", () => hl(e.dataset.t)); e.addEventListener("mouseleave", () => hl(U.hl));
    if (subs && e.matches(".ortable:not(.orpicktable) tr[data-t]")) return;   // a sub-theme row click picks it (handled above)
    e.addEventListener("click", (ev) => { if (ev.target.closest("a.tkl")) return; U.hl = U.hl === e.dataset.t ? null : e.dataset.t; hl(U.hl); }); });
  if (U.hl) hl(U.hl);
}
