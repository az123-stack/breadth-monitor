/* ---------- v3 · small tabs built from v1 cards (Oct 31, 2026) ----------
   Stocks → Setups (Adam: "setups as a sub tab, and we might need a sub tab under that; I want the lined-up buys setups"):
   a third row of tabs (V3_SETUPS) under Setups; only Lined-up buys for now — add [key, label, render] entries as setups move over.
   Groups → Rotation (Adam: "the where-is-the-money-going card, nothing else from that old tab for now"). */
const V3_SETUPS = [
  ["lineup", "Lined-up buys", (app) => {
    const T = DATA.themes || {};
    app.append(liveBar());
    const c = lineupCard(T);
    app.append(c.children.length ? c : $('<div class="card empty">No lined-up buys today: no BUY / ready group has a liquid RS 70+ uptrend stock near its 9/21 EMAs. The list refills after each data run.</div>'));
  }],
];
function renderStockSetups(app) {
  if (!DATA.themes) { app.append($('<div class="card empty">Setups appear after the next data run.</div>')); return; }
  UI.ss = UI.ss || { k: lsGet("v3setup", V3_SETUPS[0][0]) };
  if (!V3_SETUPS.some(x => x[0] === UI.ss.k)) UI.ss.k = V3_SETUPS[0][0];
  const bar = $(`<nav class="tabs3" role="tablist" aria-label="Setup type">${V3_SETUPS.map(([k, l]) => `<button role="tab" data-k="${k}" aria-selected="${k === UI.ss.k}">${l}</button>`).join("")}</nav>`);
  bar.querySelectorAll("button").forEach(b => b.addEventListener("click", () => { UI.ss.k = b.dataset.k; lsSet("v3setup", UI.ss.k); rerenderPanel(); }));
  app.append(bar);
  V3_SETUPS.find(x => x[0] === UI.ss.k)[2](app);
}
function renderGroupRotation(app) {
  if (!DATA.themes) { app.append($('<div class="card empty">Theme data isn\'t available yet. It appears after the next data run.</div>')); return; }
  app.append(moneyTodayCard());
  app.append(moneyStocksCard());
}
// Oct 31 (Adam: "show inflow and outflow of dollars for the top 20 stocks in each of the periods"; then: "a single table like the
// sub-themes rotation table, with the ability to select the time frame"): DATA.themes.rotation.mstocks (rotation.money_stocks) = every
// liquid US stock ($5+, $20M+/day), top 20 per window by net $ flow (dollar volume + on up days, − on down days) or by share of its own
// trading ($100M+/day). Rows [t, net $M, share %, price %, avg $M/day, up days, $ volume vs the 50 sessions before]; window spy = SPY %.
function moneyStocksCard() {
  const M = ((DATA.themes || {}).rotation || {}).mstocks;
  if (!M || !M.windows) return $('<section class="card empty">Stock-level dollar flows appear after the next data run.</section>');
  UI.ms = UI.ms || { win: lsGet("msWin", "30"), dir: lsGet("msDir1", "in"), by: lsGet("msBy", "usd") };
  const U = UI.ms, sizeView = U.by === "size";
  if (!M.windows.some(w => String(w.k) === U.win)) U.win = String(M.windows[M.windows.length - 1].k);
  // each side holds the top 20 by dollars + the top 20 by share; Rank by only sets the order (and which column the # follows)
  const W = M.windows.find(w => String(w.k) === U.win), key = U.dir, sgn = U.dir === "in" ? -1 : 1;
  const val = (r) => sizeView ? r[2] : r[1], ord = (a, b) => U.dir === "in" ? val(b) - val(a) : val(a) - val(b);
  const rows = (W[key] || []).slice().sort(ord);
  const S = {}; (DATA.themes.stocks || []).forEach(r => { S[r.t] = r; });
  const topOf = (w) => (w[key] || []).slice().sort(ord).slice(0, M.rules.n);
  const seen = {}; M.windows.forEach(w => topOf(w).forEach(r => { (seen[r[0]] = seen[r[0]] || []).push(w.k); }));
  const fm = (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}$${Math.abs(v) >= 1000 ? (Math.abs(v) / 1000).toFixed(1) + "B" : Math.round(Math.abs(v)) + "M"}`;
  const sg = (v, d = 1) => v == null ? "–" : `${v > 0 ? "+" : ""}${v.toFixed(d)}`;
  const inSide = U.dir === "in";
  const card = $(`<section class="card msc"><div class="head"><h2>Stocks: where the dollars went · last ${W.k} sessions <span class="meta">· ${rows.length} stocks: the top ${M.rules.n} by net dollar ${inSide ? "inflow" : "outflow"} plus the top ${M.rules.n} for their size, ranked ${sizeView ? "for their size" : "by dollars"}, ${shortDate(W.since)} – ${shortDate(M.date)} close</span></h2>
      <button class="xopen mstv">⬇ TradingView</button></div><div class="filters"></div>
    <p class="meta">Net $ flow = a stock's dollar volume counted <b>+</b> on days it closed up and <b>−</b> on days it closed down, added over the window.
      The table holds both lists: the biggest in dollars (giants like Apple and Microsoft trade so much that a small tilt is billions) and the biggest
      for their size (net flow as a share of everything the stock traded, stocks trading $${Math.round(M.rules.size_dv / 1e6)}M+ a day, so a mid cap being bought hard shows up).
      <b>Rank by</b> sets the order and the #; clicking a column header re-sorts the same rows.
      Every US stock $${M.rules.min_px}+ trading $${Math.round(M.rules.min_dv / 1e6)}M+ a day, no ETFs. SPY ${sg(W.spy)}% over the window. Click a ticker for details; click a column header to sort.
      <b>deal</b> = being acquired, so its flow is the deal. Describes where money went; net flow alone hasn't tested as a forward signal.</p>
    <div class="scroll msscroll"><table class="grid mst1"><thead><tr><th>#</th><th class="l">Stock</th><th class="l">Sub-theme</th><th>Change<small>${W.k} sessions</small></th><th>vs SPY</th>
      <th>Up days<small>of ${W.k}</small></th><th>$ volume<small>vs normal</small></th><th>Net $ flow<small>up − down $ volume</small></th><th>Share<small>of its trading</small></th>
      <th>Avg $ a day</th><th>RS</th><th class="l">Also top ${M.rules.n} ${sizeView ? "for size" : "in $"} in</th></tr></thead><tbody>
    ${rows.map((r, i) => { const [t, n, sh, rt, adv, up, vr] = r, st = S[t] || {}, nm = (M.names || {})[t] || st.name || "", deal = (M.deals || {})[t];
      const also = (seen[t] || []).filter(k => k !== W.k);
      return `<tr><td class="num meta">${i + 1}</td><td class="l"><a href="#" class="tkl" data-t="${esc(t)}"><b>${esc(t)}</b></a>${deal ? ` <span class="msdeal" title="${esc(deal)}">deal</span>` : ""}<small class="meta msn">${esc(nm)}</small></td>
        <td class="l">${esc(st.sub || "–")}</td><td class="num ${rt > 0 ? "up" : rt < 0 ? "dn" : ""}">${sg(rt)}%</td><td class="num ${rt - W.spy > 0 ? "up" : "dn"}">${sg(rt - W.spy)} pts</td>
        <td class="num">${up ?? "–"}/${W.k}</td><td class="num${vr != null && vr >= 1.25 ? " msbig" : ""}">${vr == null ? "–" : vr.toFixed(2) + "×"}</td>
        <td class="num ${n > 0 ? "up" : "dn"}">${fm(n)}</td><td class="num ${sh > 0 ? "up" : "dn"}">${sg(sh, 0)}%</td><td class="num">${fm(adv).replace("+", "")}</td>
        <td class="num">${st.rsr != null ? Math.round(st.rsr) : "–"}</td><td class="l meta">${also.length ? also.map(k => k + "d").join(" · ") : "–"}</td></tr>`; }).join("")}
    </tbody></table></div></section>`);
  const f = card.querySelector(".filters"), save = () => { Object.keys(AUTOSORT).forEach(k => { if (k.includes("where the dollars went")) delete AUTOSORT[k]; }); lsSet("msWin", U.win); lsSet("msDir1", U.dir); lsSet("msBy", U.by); rerenderPanel(); };
  f.append(chips("Window", M.windows.map(w => [String(w.k), w.k + " days"]), U, "win", save));
  f.append(chips("Show", [["in", "Money coming in"], ["out", "Money going out"]], U, "dir", save));
  f.append(chips("Rank by", [["usd", "Dollars"], ["size", "For its size"]], U, "by", save));
  card.querySelector(".mstv").addEventListener("click", () => tsDownload("money-flow-stocks", [{
    name: `${inSide ? "Money in" : "Money out"} ${W.k} days${sizeView ? " (for its size)" : ""}`, ticks: rows.map(r => r[0]) }]));
  return card;
}
// Stocks → Leadership (Oct 31, Adam: "a tab for Leadership and add this" = the v1 Breadth tab's Market health card)
function renderLeadership(app) {
  const X = (DATA.themes || {}).leadership;
  app.append(X ? healthCard(X) : $('<div class="card empty">Leadership data appears after the next data run.</div>'));
}
// Nov 4 (Adam, Nov 1: "NTRA is super strong and not even in our universe … these can't get missed"): Stocks → Strongest =
// DATA.themes.unseen (breadth/unseen.py): EVERY liquid RS 90+ stock (+ Oracle top 20 on 60D / 180D), not a top-N, deal / pinned buyout
// stocks left out, each tagged with the lists it IS on. "On no list" = RS 95+ or Oracle top 20 and on none of the pick / setup lists;
// "New this week" = RS crossed 95 or entered the Oracle top 20 in the last 5 sessions. Descriptive only.
function renderStrongest(app) {
  const X = (DATA.themes || {}).unseen;
  if (!X || !X.rows) { app.append($('<div class="card empty">The strongest-stocks table appears after the next data run.</div>')); return; }
  app.append(liveBar());
  UI.sg = UI.sg || { show: lsGet("sgShow", "all"), hi: lsGet("sgHi", "any"), q: "" };
  const U = UI.sg, live = liveActive(), uns = new Set(X.unseen || []);
  const newUnseen = X.rows.filter(r => (X.new_unseen || []).includes(r.t));
  if (newUnseen.length || uns.size) {
    app.append($(`<section class="card regcard"><div class="kicker">New leaders you haven't seen</div>
      ${newUnseen.length ? `<p style="margin:6px 0">${newUnseen.map(r => `<a href="#" class="tkl" data-t="${esc(r.t)}"><b>${esc(r.t)}</b></a> <span class="meta">${esc(r.sub || r.name)} · ${esc(r.new.join("; "))}</span>`).join("<br>")}</p>`
        : `<p class="meta" style="margin:6px 0">No new leader this week is missing from the lists.</p>`}
      <p class="meta" style="margin:6px 0 0">${uns.size} strong stock${uns.size === 1 ? " is" : "s are"} on none of the pick or setup lists right now (RS 95+ or Oracle top 20 on 60D / 180D). Pick <b>On no list</b> below to see them all.</p></section>`));
  }
  const HI = { any: 9, h5: 0.05, h10: 0.10, h15: 0.15 };
  const q = (U.q || "").trim().toLowerCase();
  const rows = X.rows.filter(r => (U.show === "all" || (U.show === "rs95" && (r.rsr || 0) >= 95) || (U.show === "unseen" && uns.has(r.t)) || (U.show === "new" && r.new.length))
    && (r.off_hi == null || -r.off_hi <= HI[U.hi]) && (!q || r.t.toLowerCase().startsWith(q) || (r.name || "").toLowerCase().includes(q) || (q.length >= 3 && (r.sub || "").toLowerCase().includes(q))));
  const todayOf = (r) => { if (live) { const L = liveRow(r.t); if (L && L.chg != null) return L.chg; } return null; };
  const card = $(`<section class="card ortable sgcard"><div class="head"><h2>Strongest stocks <span class="meta">· ${rows.length} of ${X.rows.length} · every liquid stock with RS 90+ ($10+, $20M+ a day) plus the Oracle top 20 on 60 / 180 sessions, no top-N cut · buyout stocks pinned at a deal price left out · ${shortDate(X.date)} close</span></h2>
    <button class="xopen sgtv">⬇ TradingView</button></div><div class="filters" style="display:flex;flex-wrap:wrap;gap:8px;margin:6px 0"></div>
    <div class="scroll"><table class="grid"><thead><tr><th>#</th><th class="l">Ticker</th><th class="l">Sub-theme</th><th title="RS Rating and its change over 5 sessions">RS</th><th title="Average daily range, 20 sessions">ADR</th><th>Off high</th>
      ${live ? "<th>Today</th>" : ""}<th>5D</th><th>20D</th><th>60D</th><th>180D</th><th title="Average dollar volume a day">$ / day</th><th class="l">Why it's here</th><th class="l">On these lists</th></tr></thead><tbody>
    ${rows.map((r, i) => `<tr${uns.has(r.t) ? ' class="sgun"' : ""}><td class="num">${i + 1}</td><td class="l"><a href="#" class="tkl" data-t="${esc(r.t)}"><b>${esc(r.t)}</b></a>${r.star ? ' <span title="RS line at a 1-year high">★</span>' : ""}${r.new.length ? ' <span class="oracc" title="' + esc(r.new.join("; ")) + '">new</span>' : ""}<small class="meta" style="display:block">${esc(r.name || "")}</small></td>
      <td class="l">${esc(r.sub || "–")}</td><td class="num" data-v="${r.rsr ?? 0}">${r.rsr ?? "–"}${r.rsr5 ? `<small class="meta"> ${r.rsr5 > 0 ? "+" : ""}${r.rsr5}</small>` : ""}</td>
      <td class="num">${r.adr == null ? "–" : r.adr.toFixed(1) + "%"}</td><td class="num">${pct(r.off_hi, 1)}</td>${live ? `<td class="num ${tint(todayOf(r), 0.03)}">${pct(todayOf(r), 1)}</td>` : ""}
      <td class="num ${tint(r.d5, 0.06)}">${pct(r.d5, 0)}</td><td class="num ${tint(r.d20, 0.12)}">${pct(r.d20, 0)}</td><td class="num ${tint(r.d60, 0.3)}">${pct(r.d60, 0)}</td><td class="num ${tint(r.r180, 0.6)}">${pct(r.r180, 0)}</td>
      <td class="num">${r.dvol == null ? "–" : "$" + Math.round(r.dvol) + "M"}</td><td class="l meta">${esc(r.why.join(" · ") || "RS 90+")}</td>
      <td class="l">${r.on.length ? r.on.map(x => `<span class="p3chip">${esc(x)}</span>`).join(" ") : '<b class="sgno">on no list</b>'}</td></tr>`).join("")}
    </tbody></table></div>
    <p class="meta" style="margin:8px 0 0">Lists checked: ${esc((X.rules.lists || []).join(", "))}. A row with <b>on no list</b> is strong but no list on the page shows it. Descriptive only: strength isn't a buy point, check the chart.</p></section>`);
  const f = card.querySelector(".filters"), save = () => { lsSet("sgShow", U.show); lsSet("sgHi", U.hi); rerenderPanel(); };
  const cnt = (k) => X.rows.filter(r => k === "rs95" ? (r.rsr || 0) >= 95 : k === "unseen" ? uns.has(r.t) : r.new.length).length;
  f.append(chips("Show", [["all", "All"], ["rs95", `RS 95+ <small>${cnt("rs95")}</small>`], ["unseen", `On no list <small>${cnt("unseen")}</small>`], ["new", `New this week <small>${cnt("new")}</small>`]], U, "show", save));
  f.append(chips("Near the high", [["any", "Any"], ["h5", "Within 5%"], ["h10", "Within 10%"], ["h15", "Within 15%"]], U, "hi", save));
  const qi = $(`<input type="search" class="orq" placeholder="Find a ticker, company or sub-theme" aria-label="Find">`); qi.value = U.q || ""; let qt = null;
  qi.addEventListener("input", () => { clearTimeout(qt); qt = setTimeout(() => { U.q = qi.value; rerenderPanel(); const n = document.querySelector(".sgcard .orq"); if (n) { n.focus(); n.setSelectionRange(n.value.length, n.value.length); } }, 250); });
  f.append(qi);
  card.querySelector(".sgtv").addEventListener("click", () => tsDownload("strongest-stocks", [{ name: "Strongest stocks", ticks: rows.map(r => r.t) }]));
  app.append(card);
}
// Nov 4 (Adam: "everywhere on the breadth page make it known it's a day behind"): breadth is end-of-day (Massive's free plan posts
// each session after midnight ET), so v3 puts a banner on top and a "through <date> close" tag on every card and chart.
// The macro strip is left untagged (it has its own "closes through" date from Yahoo).
function renderBreadthV3(app) {
  renderBreadth(app);
  const rows = DATA.rows || [], last = rows[rows.length - 1]; if (!last) return;
  const today = etToday(), clk = nyClock();
  const behind = last.date < today;
  const when = clk.open ? "Today's session is still trading; it gets added after midnight ET." : "Today's session gets added after midnight ET.";
  const msg = behind ? `<b>A day behind:</b> every number and chart on this tab is through the <b>${longDate(last.date)} close</b>. ${when} For today, use <b>Intraday</b> (live) or <b>Pre-market</b>.`
    : `<b>End of day:</b> numbers are through today's close (${longDate(last.date)}).`;
  const ban = $(`<div class="eodban">${msg}</div>`);
  const first = app.querySelector(".card"); if (first) first.before(ban); else app.prepend(ban);
  const tag = `<small class="eodtag" title="Breadth is end-of-day: through the ${longDate(last.date)} close">${behind ? "⏱ " : ""}through ${shortDate(last.date)} close</small>`;
  app.querySelectorAll(".card").forEach(c => {
    if (c.classList.contains("mstrip")) return;
    const el = cardTitle(c)[0] || c.querySelector(".kicker, h2, h3"); if (el && !el.querySelector(".eodtag")) el.insertAdjacentHTML("beforeend", " " + tag);
  });
}
// Nov 4 (Adam: "sub-themes pop and then I forget about them because they're not exploding anymore, but that's exactly when I need to be
// grabbing them … had relative strength but then pulled back"): Groups → Pop watch = DATA.themes.popwatch (breadth/popwatch.py). Every
// sub-theme that popped (the Runners rule on the official close) stays on the list for 25 sessions; state running / pulling back / gave it
// back; its RS 70+ uptrend members carry Lined-up-style fields, so lineupState tags them live (into the 9/21 EMAs, near, over the trigger).
function popSpark(r) {
  const v = (r.line || []).filter(x => x != null); if (v.length < 3) return "";
  const w = 120, h = 30, lo = Math.min(...v), hi = Math.max(...v), sp = hi - lo || 1, n = v.length - 1;
  const pts = v.map((x, i) => `${(i / n * w).toFixed(1)},${(h - 2 - (x - lo) / sp * (h - 4)).toFixed(1)}`).join(" ");
  const kx = (r.line_k / n * w).toFixed(1);
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-label="group index around the pop"><line x1="${kx}" x2="${kx}" y1="0" y2="${h}" class="orgridl"/><polyline points="${pts}" fill="none" stroke="var(--s1)" stroke-width="1.6"/></svg>`;
}
function renderPopWatch(app) {
  const X = (DATA.themes || {}).popwatch;
  if (!X || !X.rows) { app.append($('<div class="card empty">Pop watch appears after the next data run.</div>')); return; }
  app.append(liveBar());
  UI.pw = UI.pw || { st: lsGet("pwState", "pulling_back"), rs: lsGet("pwRs", "all") };
  const U = UI.pw, live = liveActive(), E = X.evidence || {};
  const STN = { running: ["Still running", "sow-breakout"], pulling_back: ["Pulling back", "sow-nuzzle"], gave_back: ["Gave it back", "sow-extended"] };
  const liveMove = (g) => { const v = g.names.length ? g.names : []; const L = (((DATA.themes.oracle || {}).subs || {})[g.g] || {}).members || v.map(x => x.t);
    const ch = L.map(t => liveRow(t)).filter(r => r && r.chg != null).map(r => r.chg); return live && ch.length ? ch.reduce((a, b) => a + b, 0) / ch.length : null; };
  const rows = X.rows.filter(r => (U.st === "all" || r.state === U.st) && (U.rs === "all" || (r.rel || 0) >= 0));
  const cnt = (k) => X.rows.filter(r => k === "all" || r.state === k).length;
  const head = $(`<section class="card orhead"><h2>Pop watch <span class="meta">· sub-themes that popped in the last ${X.days} sessions, kept here while they cool off · ${shortDate(X.date)} close</span></h2>
    <div class="filters"></div>
    <div class="meta orsub"><b>Pop</b> = the same rule as the live Runners alert, on the close: 75%+ of the group up, the average member up 1.25+ of its own daily ranges,
    3+ points better than SPY, on 1.2× normal dollar volume. <b>Pulling back</b> = off its post-pop high but still above the pop day's open. <b>Vs SPY since</b> = how the group did
    against SPY after the pop day closed (above 0 = it held its relative strength). Names = its RS 70+ uptrend stocks; a tag shows when one is into the 9/21 EMAs, the Lined-up buys entry.</div>
    ${E.after_pop ? `<div class="meta oraccnote"><b>What the test says</b> (${E.from} to ${E.to}, ${E.pops} pops, Lined-up trigger rule: buy the break of the dip-day high, stop the dip low ≤ 1 ADR, 20 sessions):
      first 9/21 dips 3–${X.days} sessions after a pop made <b>${num(E.after_pop.R, 2)}R</b> a trade (n ${E.after_pop.n}), the same as dips in groups with no pop (${num(E.no_pop.R, 2)}R, n ${E.no_pop.n});
      groups still beating SPY since the pop ${num(E.held_rs.R, 2)}R vs ${num(E.lost_rs.R, 2)}R (t ${E.t_held ?? "–"}, not significant). So the pop doesn't add an edge of its own, but it doesn't hurt:
      this list is a memory so a strong group's pullback isn't missed, and the dip entry is the same tested setup as Lined-up buys. Both halves: ${num(E.after_pop.h1, 2)}R / ${num(E.after_pop.h2, 2)}R (2nd half lost, like every dip setup).</div>` : ""}
    ${(X.live_today || []).length ? `<div class="oraccnote"><b>Popping today (live alert, joins the list tonight):</b> ${X.live_today.map(r => `<b>${esc(r.g)}</b> <span class="meta">${pct(r.avg, 1)} · ${esc(r.top)}</span>`).join(" · ")}</div>` : ""}</section>`);
  const f = head.querySelector(".filters"), save = () => { lsSet("pwState", U.st); lsSet("pwRs", U.rs); rerenderPanel(); };
  f.append(chips("State", [["pulling_back", `Pulling back <small>${cnt("pulling_back")}</small>`], ["running", `Still running <small>${cnt("running")}</small>`], ["gave_back", `Gave it back <small>${cnt("gave_back")}</small>`], ["all", `All <small>${cnt("all")}</small>`]], U, "st", save));
  f.append(chips("Relative strength", [["all", "Any"], ["held", "Still beating SPY since the pop"]], U, "rs", save));
  app.append(head);
  const tagFor = (n) => { const s = lineupState(n); return s.zone ? `${s.over ? '<span class="tg sow-breakout">Over the trigger</span>' : '<span class="tg sow-nuzzle">Into the 9/21</span>'} ${lineupLocTag(s)}` : s.near ? '<span class="tg">Near the EMAs</span>' : lineupLocTag(s); };
  const card = $(`<section class="card ortable"><div class="head"><h2>${rows.length} group${rows.length === 1 ? "" : "s"} <span class="meta">· best vs SPY since the pop first · click a ticker for details</span></h2><button class="xopen pwtv">⬇ TradingView</button></div>
    <div class="scroll"><table class="grid"><thead><tr><th class="l">Sub-theme</th><th>Popped</th><th>Pop day</th><th class="l">State</th><th title="Group index vs its high since the pop">Off post-pop high</th><th>Vs SPY since</th>
    <th>Strength</th>${live ? "<th>Today</th>" : ""}<th class="l">Around the pop</th><th class="l">Its leaders (RS 70+ uptrend) · where they sit vs the 9/21 EMAs</th></tr></thead><tbody>
    ${rows.map(r => { const [sl, sc] = STN[r.state]; const lm = liveMove(r);
      return `<tr><td class="l"><b>${esc(r.g)}</b><small class="meta" style="display:block">${r.n} stocks${r.pops > 1 ? ` · popped ${r.pops}× in ${X.days} sessions` : ""}</small></td>
      <td class="num" data-v="${-r.ago}">${shortDate(r.pop)}<small class="meta" style="display:block">${r.ago ? r.ago + " sessions ago" : "last session"}</small></td>
      <td class="num g2">${pct(r.pop_r, 1)}</td><td class="l"><span class="tg ${sc}">${sl}</span></td>
      <td class="num">${pct(r.off_pk, 1)}${r.off_adr != null ? `<small class="meta" style="display:block">${Math.abs(r.off_adr).toFixed(1)} ADR</small>` : ""}</td>
      <td class="num ${tint(r.rel, 0.04)}">${pct(r.rel, 1)}</td><td class="num">${r.strength == null ? "–" : Math.round(r.strength)}</td>${live ? `<td class="num ${tint(lm, 0.02)}">${pct(lm, 1)}</td>` : ""}
      <td class="l">${popSpark(r)}</td>
      <td class="l">${r.names.length ? r.names.slice(0, 8).map(n => `<div class="pwn"><a href="#" class="tkl" data-t="${esc(n.t)}"><b>${esc(n.t)}</b></a> <small class="meta">RS ${n.rs ?? "–"} · ${pct(n.since, 0)} since</small> ${tagFor(n)}</div>`).join("") : '<span class="meta">no RS 70+ uptrend member right now</span>'}</td></tr>`; }).join("")}
    </tbody></table></div></section>`);
  card.querySelector(".pwtv").addEventListener("click", () => tsDownload("pop-watch", rows.map(r => ({ name: "Pop watch - " + r.g, ticks: r.names.map(n => n.t) }))));
  app.append(card);
}
