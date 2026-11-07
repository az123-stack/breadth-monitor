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
  qi.addEventListener("input", () => { clearTimeout(qt); qt = setTimeout(() => { U.q = qi.value; rerenderPanel(); const n = PQ(".sgcard .orq"); if (n) { n.focus(); n.setSelectionRange(n.value.length, n.value.length); } }, 250); });
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
  UI.pw = UI.pw || { st: lsGet("pwState", "pulling_back"), rs: lsGet("pwRs", "all"), by: lsGet("pwBy", "pull") };
  const U = UI.pw, live = liveActive(), E = X.evidence || {};
  const STN = { running: ["Still running", "sow-breakout"], pulling_back: ["Pulling back", "sow-nuzzle"], gave_back: ["Gave it back", "sow-extended"] };
  const liveMove = (g) => { const v = g.names.length ? g.names : []; const L = (((DATA.themes.oracle || {}).subs || {})[g.g] || {}).members || v.map(x => x.t);
    const ch = L.map(t => liveRow(t)).filter(r => r && r.chg != null).map(r => r.chg); return live && ch.length ? ch.reduce((a, b) => a + b, 0) / ch.length : null; };
  // Nov 4 (Adam's strategy: "sort by the greatest deviation from off post-pop high" — CROs hot two weeks ago, cooled, cheap now)
  const SORTS = { pull: (a, b) => (a.off_adr ?? 0) - (b.off_adr ?? 0), rel: (a, b) => (b.rel ?? -9) - (a.rel ?? -9), new: (a, b) => a.ago - b.ago };
  const rows = X.rows.filter(r => (U.st === "all" || r.state === U.st) && (U.rs === "all" || (r.rel || 0) >= 0)).sort(SORTS[U.by] || SORTS.pull);
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
  const f = head.querySelector(".filters"), save = () => { lsSet("pwState", U.st); lsSet("pwRs", U.rs); lsSet("pwBy", U.by); try { delete AUTOSORT[Object.keys(AUTOSORT).find(k => k.includes("Pop watch")) || ""]; } catch (e) {} rerenderPanel(); };
  f.append(chips("State", [["pulling_back", `Pulling back <small>${cnt("pulling_back")}</small>`], ["running", `Still running <small>${cnt("running")}</small>`], ["gave_back", `Gave it back <small>${cnt("gave_back")}</small>`], ["all", `All <small>${cnt("all")}</small>`]], U, "st", save));
  f.append(chips("Sort", [["pull", "Most pulled back (in ADRs)"], ["rel", "Best vs SPY since the pop"], ["new", "Newest pop"]], U, "by", save));
  f.append(chips("Relative strength", [["all", "Any"], ["held", "Still beating SPY since the pop"]], U, "rs", save));
  app.append(head);
  const tagFor = (n) => { const s = lineupState(n); return s.zone ? `${s.over ? '<span class="tg sow-breakout">Over the trigger</span>' : '<span class="tg sow-nuzzle">Into the 9/21</span>'} ${lineupLocTag(s)}` : s.near ? '<span class="tg">Near the EMAs</span>' : lineupLocTag(s); };
  const card = $(`<section class="card ortable"><div class="head"><h2>${rows.length} group${rows.length === 1 ? "" : "s"} <span class="meta">· ${{ pull: "most pulled back first (distance off the post-pop high in the group's own daily ranges)", rel: "best vs SPY since the pop first", new: "newest pop first" }[U.by] || ""} · click a ticker for details</span></h2><button class="xopen pwtv">⬇ TradingView</button></div>
    <div class="scroll"><table class="grid"><thead><tr><th class="l">Sub-theme</th><th>Popped</th><th>Pop day</th><th class="l">State</th><th title="Group index vs its high since the pop">Off post-pop high</th><th>Vs SPY since</th>
    <th>Strength</th>${live ? "<th>Today</th>" : ""}<th class="l">Around the pop</th><th class="l">Its leaders (RS 70+ uptrend) · where they sit vs the 9/21 EMAs</th></tr></thead><tbody>
    ${rows.map(r => { const [sl, sc] = STN[r.state]; const lm = liveMove(r);
      return `<tr><td class="l"><b>${esc(r.g)}</b><small class="meta" style="display:block">${r.n} stocks${r.pops > 1 ? ` · popped ${r.pops}× in ${X.days} sessions` : ""}</small></td>
      <td class="num" data-v="${-r.ago}">${shortDate(r.pop)}<small class="meta" style="display:block">${r.ago ? r.ago + " sessions ago" : "last session"}</small></td>
      <td class="num g2">${pct(r.pop_r, 1)}</td><td class="l"><span class="tg ${sc}">${sl}</span></td>
      <td class="num" data-v="${r.off_adr ?? 0}">${pct(r.off_pk, 1)}${r.off_adr != null ? `<small class="meta" style="display:block">${Math.abs(r.off_adr).toFixed(1)} ADR</small>` : ""}</td>
      <td class="num ${tint(r.rel, 0.04)}">${pct(r.rel, 1)}</td><td class="num">${r.strength == null ? "–" : Math.round(r.strength)}</td>${live ? `<td class="num ${tint(lm, 0.02)}">${pct(lm, 1)}</td>` : ""}
      <td class="l">${popSpark(r)}</td>
      <td class="l">${r.names.length ? r.names.slice(0, 8).map(n => `<div class="pwn"><a href="#" class="tkl" data-t="${esc(n.t)}"><b>${esc(n.t)}</b></a> <small class="meta">RS ${n.rs ?? "–"} · ${pct(n.since, 0)} since</small> ${tagFor(n)}</div>`).join("") : '<span class="meta">no RS 70+ uptrend member right now</span>'}</td></tr>`; }).join("")}
    </tbody></table></div></section>`);
  card.querySelector(".pwtv").addEventListener("click", () => tsDownload("pop-watch", rows.map(r => ({ name: "Pop watch - " + r.g, ticks: r.names.map(n => n.t) }))));
  app.append(card);
}
// Nov 4 (Adam: "a place to see just the best sub-themes by RS over different time periods"): Groups → RS ranks = every sub-theme (or theme)
// with the median RS (1–99) of its stocks for each RS period side by side (live during the session), plus its rank on each period.
// Click a period column (or the Rank by chip) to rank by it. Descriptive.
function renderRsRanks(app) {
  const T = getT();
  if (!T || !T.stocks) { app.append($('<div class="card empty">Appears after the next data run.</div>')); return; }
  app.append(liveBar());
  UI.rr = UI.rr || { view: lsGet("rrView", "sub"), by: lsGet("rrBy", "rs5d"), min: lsGet("rrMin", "4"), q: "" };
  const U = UI.rr, P = Object.keys(RS_PER), SR = Object.fromEntries(T.stocks.map(s => [s.t, s]));
  if (!RS_PER[U.by]) U.by = "rs5d";
  const med = (v) => { v = v.filter(x => x != null).sort((a, b) => a - b); if (!v.length) return null; const m = v.length >> 1; return v.length % 2 ? v[m] : Math.round((v[m - 1] + v[m]) / 2); };
  const groups = (U.view === "sub" ? T.subthemes || [] : T.themes || []).map(g => {
    const mem = (g.members || []).filter(t => SR[t] && SR[t].is_stock !== false);
    const r = { name: g.theme, group: g.group || "", n: mem.length, strength: g.strength, members: mem };
    P.forEach(k => { r[k] = med(mem.map(t => SR[t][k])); });
    return r;
  }).filter(r => r.n >= +U.min);
  P.forEach(k => { const o = groups.filter(r => r[k] != null).sort((a, b) => b[k] - a[k]); o.forEach((r, i) => { r[k + "_rk"] = i + 1; }); });
  const q = (U.q || "").trim().toLowerCase();
  const rows = groups.filter(r => !q || r.name.toLowerCase().includes(q) || r.group.toLowerCase().includes(q) || r.members.some(t => t.toLowerCase() === q))
    .sort((a, b) => (b[U.by] ?? -1) - (a[U.by] ?? -1));
  const lab = (k) => RS_PER[k][0].replace(" (RS Rating)", "");
  const card = $(`<section class="card ortable rrcard"><div class="head"><h2>RS ranks · ${U.view === "sub" ? "sub-themes" : "themes"} <span class="meta">· median RS (1–99) of each group's stocks for every period, ranked by <b>${esc(lab(U.by))}</b> · ${rows.length} groups${liveActive() ? " · live" : ` · ${shortDate(T.date)} close`}</span></h2>
    <button class="xopen rrtv">⬇ TradingView</button></div>
    <div class="filters" style="display:flex;flex-wrap:wrap;gap:8px;margin:6px 0"></div>
    <div class="meta" style="margin:0 0 6px">RS for a period = where a stock's return over that period ranks against every liquid stock (99 = top 1%). The group number is the middle stock's,
      so one runner can't carry it. The small number under each value is the group's rank on that period. Reading across a row shows whether a group is getting stronger (short periods higher than long) or fading.</div>
    <div class="scroll"><table class="grid"><thead><tr><th>#</th><th class="l">${U.view === "sub" ? "Sub-theme" : "Theme"}</th><th>Stocks</th><th>Strength</th>
      ${P.map(k => `<th class="rrh${k === U.by ? " orsel" : ""}" data-k="${k}" style="cursor:pointer" title="Rank by ${esc(lab(k))}">RS<small>${esc(lab(k))}</small></th>`).join("")}<th class="l">Top stocks on ${esc(lab(U.by))}</th></tr></thead><tbody>
    ${rows.map((r, i) => `<tr><td class="num">${i + 1}</td><td class="l"><b>${esc(r.name)}</b>${r.group ? `<small class="meta" style="display:block">${esc(r.group)}</small>` : ""}</td><td class="num">${r.n}</td>
      <td class="num">${r.strength == null ? "–" : Math.round(r.strength)}</td>
      ${P.map(k => `<td class="num ${rsTint(r[k])}${k === U.by ? " orsel" : ""}" data-v="${r[k] ?? -1}">${r[k] ?? "–"}<small class="meta" style="display:block">#${r[k + "_rk"] ?? "–"}</small></td>`).join("")}
      <td class="l">${r.members.slice().sort((a, b) => (SR[b][U.by] ?? -1) - (SR[a][U.by] ?? -1)).slice(0, 5).map(t => `<a href="#" class="tkl" data-t="${esc(t)}">${esc(t)}</a> <small class="meta">${SR[t][U.by] ?? "–"}</small>`).join(" · ")}</td></tr>`).join("")}
    </tbody></table></div></section>`);
  const f = card.querySelector(".filters"), save = () => { lsSet("rrView", U.view); lsSet("rrBy", U.by); lsSet("rrMin", U.min); rerenderPanel(); };
  f.append(chips("View", [["sub", "Sub-themes"], ["theme", "Themes"]], U, "view", save));
  f.append(chips("Rank by", P.map(k => [k, esc(lab(k))]), U, "by", save));
  f.append(chips("Size", [["3", "3+ stocks"], ["4", "4+ stocks"], ["6", "6+ stocks"]], U, "min", save));
  const qi = $(`<input type="search" class="orq" placeholder="Find a group or ticker" aria-label="Find">`); qi.value = U.q || ""; let qt = null;
  qi.addEventListener("input", () => { clearTimeout(qt); qt = setTimeout(() => { U.q = qi.value; rerenderPanel(); const n = PQ(".rrcard .orq"); if (n) { n.focus(); n.setSelectionRange(n.value.length, n.value.length); } }, 250); });
  f.append(qi);
  card.querySelectorAll(".rrh").forEach(th => th.addEventListener("click", (e) => { e.stopPropagation(); U.by = th.dataset.k; save(); }));
  card.querySelector("table").dataset.ownSort = "1";
  card.querySelector(".rrtv").addEventListener("click", () => tsDownload("rs-ranks-" + U.by, rows.slice(0, 15).map(r => ({ name: "RS " + lab(U.by) + " - " + r.name, ticks: r.members.slice().sort((a, b) => (SR[b][U.by] ?? -1) - (SR[a][U.by] ?? -1)) }))));
  app.append(card);
}
// Nov 5 (Adam, after a Lance Breitstein transcript on in-play stocks: "Let's have In Play under the stocks tab"): Stocks → In Play =
// DATA.themes.inplay (breadth/inplay.py): every liquid stock with news (gap ≥ max(3%, 1 ADR) on 2.5x vol), a fresh breakout / breakdown
// on 1.5x vol, a 2-ADR range day on 2x vol, or an IPO (< 120 sessions) in the last 5 sessions. Live session: adds "today" from the Google
// sheet (move ≥ 2 ADRs, or gap ≥ max(3%, 1 ADR) with paced volume ≥ 2x) using `pool` [adr, v50, sub]; before the open: Yahoo gaps.
const IP_KIND = { earnings: "Earnings", news: "News gap", breakout: "52-wk high", base: "Base breakout", breakdown: "Breakdown", range: "Range day", ipo: "IPO", today: "Today" };
function renderInPlay(app) {
  const c = nyClock(); if (typeof PM !== "undefined" && !PM && !PM_ERR && c.mins < 0 && c.mins > -330) fetchPM();
  const S = liveActive() ? "live" : (typeof PM !== "undefined" && PM && PM.date === etToday() ? "pre" : null);
  if (S !== "pre") return renderInPlayBody(app, S);
  ROWS_OVERRIDE = pmRows();
  try { return renderInPlayBody(app, S); } finally { ROWS_OVERRIDE = null; }
}
function renderInPlayBody(app, S) {
  const X = (DATA.themes || {}).inplay;
  if (!X || !X.rows) { app.append($('<div class="card empty">The In Play list appears after the next data run.</div>')); return; }
  app.append(S === "pre" ? orSessionBar("pre") : liveBar());
  UI.ip = UI.ip || { why: lsGet("ipWhy", "all"), dir: lsGet("ipDir", "all"), when: lsGet("ipWhen", "5"), rs: lsGet("ipRs", "any"), sort: lsGet("ipSort", "best"), q: "" };
  const U = UI.ip, clk = nyClock(), pace = S === "live" ? volPace(Math.min(390, clk.mins)) : null;
  // today's read per stock (live: Google; pre: Yahoo)
  const todayOf = (t) => {
    if (!S) return null;
    const L = liveRow(t), P = X.pool[t]; if (!L) return null;
    const adr = P ? P[0] : null, v50 = P ? P[1] : null;
    const rv = S === "live" && pace && v50 && L.volume ? L.volume / (v50 * pace) : null;
    const gap = S === "pre" ? L.chg : L.gap;   // before the open the whole move is the gap
    const mvA = adr ? Math.abs(L.chg) / adr : null, gapBig = gap != null && adr && Math.abs(gap) >= Math.max(0.03, adr);
    const pmOk = S !== "pre" || (L.bars == null || L.bars >= 6);
    const hot = pmOk && ((mvA != null && mvA >= 2) || (gapBig && (S === "pre" || (rv != null && rv >= 2))));
    return { chg: L.chg, gap, rv, mvA, hot };
  };
  const byT = new Map(X.rows.map(r => [r.t, r]));
  const TOPG = new Set(X.top_groups || []);
  const L0 = (t) => { const L = liveRow(t); return L && L.price != null ? L.price : null; };
  const stockBy = new Map((DATA.themes.stocks || []).map(x => [x.t, x]));
  const live = [];
  if (S) Object.keys(X.pool).forEach(t => {
    const d = todayOf(t); if (!d || !d.hot) return;
    const why = { k: "today", ago: -1, txt: `${pct(d.chg, 1)}${d.gap != null && S === "live" ? ` (gap ${pct(d.gap, 1)})` : ""}${d.mvA != null ? ` = ${d.mvA.toFixed(1)} ADRs` : ""}${d.rv ? ` on ${d.rv.toFixed(1)}x paced vol` : ""}` };
    const r0 = byT.get(t);
    const spikeNow = (d.gap != null && d.gap >= 0.10) || (d.chg != null && d.chg >= 0.20);
    if (r0) { const rw = r0.rank_why || [], add = spikeNow && !rw.includes("-Spike");
      live.push({ ...r0, why: [why, ...r0.why], kinds: ["today", ...r0.kinds], ago: -1, _t: d, rank: (r0.rank || 0) - (add ? 1 : 0), rank_why: add ? [...rw, "-Spike"] : rw }); }
    else { const s = stockBy.get(t) || {}, P = X.pool[t], sub = s.sub || P[2], px = L0(t), off = P[3] && px ? px / P[3] - 1 : null, rk = [];
      if (sub && TOPG.has(sub)) rk.push("+Leading group");
      if (off != null && off >= -0.15) rk.push("+Near 52-wk high");
      if (spikeNow) rk.push("-Spike");
      if (P[0] > 0.10) rk.push("-ADR > 10%");
      if (off != null && off <= -0.30) rk.push("-30%+ off high");
      live.push({ t, name: s.name || "", sub, rs: s.rsr != null ? Math.round(s.rsr) : null, adr: P[0] * 100, why: [why], kinds: ["today"], ago: -1, score: 0, on: [], _t: d, dir: d.chg > 0 ? "up" : "down",
        rank: rk.reduce((n, x) => n + (x[0] === "+" ? 1 : -1), 0), rank_why: rk }); }
  });
  const liveSet = new Set(live.map(r => r.t));
  let rows = [...live.sort((a, b) => Math.abs(b._t.mvA || 0) - Math.abs(a._t.mvA || 0)), ...X.rows.filter(r => !liveSet.has(r.t))];
  // Nov 7 (Adam: "score the in play so it's sorted with the best at the top"): Best first = ranking score (inplay.RANK), then newest
  if (U.sort !== "new") rows.sort((a, b) => (b.rank || 0) - (a.rank || 0) || a.ago - b.ago || (b.score || 0) - (a.score || 0) || (b.rs || 0) - (a.rs || 0));
  else rows.sort((a, b) => a.ago - b.ago || (b.score || 0) - (a.score || 0));
  const q = (U.q || "").trim().toLowerCase();
  const whySet = new Set(String(U.why).split(","));
  const RSMIN = { any: 0, r70: 70, r80: 80, r90: 90 };
  const pass = (r, skip) => (skip === "why" || whySet.has("all") || r.kinds.some(k => whySet.has(k === "earnings" ? "news" : k)))
    && (skip === "dir" || U.dir === "all" || (r._t ? (r._t.chg > 0 ? "up" : "down") : r.dir) === U.dir)
    && (skip === "when" || U.when === "5" || r.ago <= (U.when === "today" ? -1 : 0))
    && (r.rs == null ? U.rs === "any" : r.rs >= RSMIN[U.rs])
    && (!q || r.t.toLowerCase().startsWith(q) || (r.name || "").toLowerCase().includes(q) || (q.length >= 3 && (r.sub || "").toLowerCase().includes(q)));
  const shown = rows.filter(r => pass(r));
  // Nov 7, 2026 (speed): draw the top IP_PAGE rows; "Show all" draws the rest (738 rows took ~1.5 s to lay out)
  const IP_PAGE = 120, drawn = U.all || q ? shown : shown.slice(0, IP_PAGE);
  const cnt = (k) => rows.filter(r => pass(r, "why") && r.kinds.some(x => (x === "earnings" ? "news" : x) === k)).length;
  const dayLbl = (w) => w.ago < 0 ? (S === "pre" ? "pre-mkt" : "today") : w.ago === 0 ? shortDate(X.date) : shortDate(w.date);
  const whyCell = (r) => r.why.slice(0, 3).map(w => `<span class="p3chip ipk-${w.k}" title="${esc(w.txt)}">${esc(w.k === "today" && S === "pre" ? "Pre-market" : IP_KIND[w.k])}</span> <small class="meta">${esc(dayLbl(w))}: ${esc(w.txt)}</small>`).join("<br>") + (r.why.length > 3 ? `<br><small class="meta">+${r.why.length - 3} more</small>` : "");
  const card = $(`<section class="card ortable ipcard"><div class="head"><h2>In Play <span class="meta">· ${shown.length} of ${rows.length} · something is happening: news, a breakout / breakdown, a big-range day or a new listing in the last 5 sessions${S ? (S === "pre" ? " + pre-market gaps" : " + today, live") : ""} · $5+, $10M+ a day · through ${shortDate(X.date)} close</span></h2>
    <button class="xopen iptv">⬇ TradingView</button></div><div class="filters" style="display:flex;flex-wrap:wrap;gap:8px;margin:6px 0"></div>
    <div class="scroll"><table class="grid"><thead><tr><th>#</th><th class="l">Ticker</th><th title="Ranking score: +1 leading group, +1 within 15% of the 52-wk high; −1 spike, −1 ADR over 10%, −1 30%+ off the high">Score</th><th class="l">Sub-theme</th><th class="l">Why it's in play</th><th title="RS Rating">RS</th><th title="Average daily range, 20 sessions">ADR</th>
      ${S ? `<th>${S === "pre" ? "Pre-mkt" : "Today"}</th>${S === "live" ? '<th title="Volume so far vs the 50-day average, paced for the time of day">Rel vol<small> paced</small></th>' : ""}` : ""}
      <th title="Last official session">${shortDate(X.date)}</th><th>5D</th><th title="Biggest volume vs the 50-day average in the 5 sessions">Max rel vol</th><th>Off high</th><th title="Average dollar volume a day">$ / day</th><th class="l">Next earnings</th><th class="l">On these lists</th></tr></thead><tbody>
    ${drawn.map((r, i) => { const d = r._t || (S ? todayOf(r.t) : null); return `<tr><td class="num">${i + 1}</td><td class="l"><a href="#" class="tkl" data-t="${esc(r.t)}"><b>${esc(r.t)}</b></a><small class="meta" style="display:block">${esc(r.name || "")}</small></td>
      <td class="l" data-v="${r.rank ?? -9}" style="white-space:nowrap"><b class="${(r.rank || 0) > 0 ? "up" : (r.rank || 0) < 0 ? "dn" : ""}">${(r.rank || 0) > 0 ? "+" : ""}${r.rank ?? 0}</b>${(r.rank_why || []).map(x => `<small class="meta" style="display:block;color:${x[0] === "+" ? "var(--pos)" : "var(--neg)"}">${esc(x.slice(1))}</small>`).join("")}</td>
      <td class="l">${esc(r.sub || "–")}</td><td class="l">${whyCell(r)}</td><td class="num">${r.rs ?? "–"}</td><td class="num">${r.adr == null ? "–" : (+r.adr).toFixed(1) + "%"}</td>
      ${S ? `<td class="num ${tint(d && d.chg, 0.04)}">${d ? pct(d.chg, 1) : "–"}</td>${S === "live" ? `<td class="num">${d && d.rv ? d.rv.toFixed(1) + "×" : "–"}</td>` : ""}` : ""}
      <td class="num ${tint(r.d1, 0.04)}">${pct(r.d1, 1)}</td><td class="num ${tint(r.d5, 0.08)}">${pct(r.d5, 1)}</td><td class="num">${r.rvmax == null ? "–" : r.rvmax.toFixed(1) + "×"}</td>
      <td class="num">${pct(r.off_hi, 1)}</td><td class="num">${r.dvol == null ? "–" : "$" + Math.round(r.dvol) + "M"}</td><td class="l">${r.earn_next ? shortDate(r.earn_next) : ""}</td>
      <td class="l">${(r.on || []).map(x => `<span class="p3chip">${esc(x)}</span>`).join(" ")}</td></tr>`; }).join("") || `<tr><td class="l meta" colspan="15">Nothing matches these filters.</td></tr>`}
    </tbody></table></div>
    ${drawn.length < shown.length ? `<p style="margin:8px 0 0"><button class="xopen ipall">Show all ${shown.length} (top ${drawn.length} shown; sorting a column sorts the rows shown)</button></p>` : ""}
    <p class="meta" style="margin:8px 0 0"><b>The three reasons</b> (Lance Breitstein's "broken slot machines"): <b>news</b> = a gap of at least 3% and 1 ADR on 2.5× normal volume (Earnings when the catalyst agent has a report that day); <b>technical</b> = a fresh close above the 52-week high, or out of a tight base (40 sessions within 6 ADRs), on 1.5× volume, breakdowns mirrored; <b>volatility</b> = a day's range of 2+ ADRs on 2× volume, or a listing under 120 sessions old.${S === "live" ? " <b>Today</b> = moving 2+ ADRs, or gapping ≥ 3% and 1 ADR with paced volume ≥ 2×." : S === "pre" ? " <b>Pre-market</b> = moving 2+ ADRs, or a gap ≥ 3% and 1 ADR, on steady trading (6+ active 5-minute bars)." : ""}
    <b>Score</b> (Best first): +1 its sub-theme is in the top third on 63-day return, +1 within 15% of the 52-week high; −1 a spike in the last 5 sessions (gap 10%+, day +20%+ or 20× volume), −1 ADR over 10%, −1 30%+ below the high. Built only from traits that held in both halves of the last year (in-play stocks, next open → 10 sessions): +2 did +1.2% vs SPY (56% up), −3 did −18.9% (22% up). A sorting aid, not yet a proven buy signal (card R-2026-11-07-inplay-score). <b>Where to look, not a buy signal:</b> on our data, more action alone hasn't been a swing edge (record-volume up days lagged SPY about 5% over 10 sessions; EPs without a catalyst check lost). Use it to pick which charts to open, then apply your setups. A test of "same setup, in play vs not" is queued.</p></section>`);
  const f = card.querySelector(".filters");
  const ipall = card.querySelector(".ipall"); if (ipall) ipall.addEventListener("click", () => { U.all = true; rerenderPanel(); });
  const save = () => { lsSet("ipWhy", U.why); lsSet("ipDir", U.dir); lsSet("ipWhen", U.when); lsSet("ipRs", U.rs); lsSet("ipSort", U.sort); rerenderPanel(); };
  f.append(chipsMulti("Why", [["all", "All"], ...(S ? [["today", `${S === "pre" ? "Pre-market" : "Today"} <small>${cnt("today")}</small>`]] : []), ["news", `News gap <small>${cnt("news")}</small>`], ["breakout", `52-wk high <small>${cnt("breakout")}</small>`], ["base", `Base breakout <small>${cnt("base")}</small>`], ["breakdown", `Breakdown <small>${cnt("breakdown")}</small>`], ["range", `Range day <small>${cnt("range")}</small>`], ["ipo", `IPO <small>${cnt("ipo")}</small>`]], U, "why", save));
  f.append(chips("Direction", [["all", "Both"], ["up", "Up"], ["down", "Down"]], U, "dir", save));
  f.append(chips("When", [["5", "Last 5 sessions"], ["last", `${shortDate(X.date)} or later`], ...(S ? [["today", S === "pre" ? "Pre-market only" : "Today only"]] : [])], U, "when", save));
  f.append(chips("RS", [["any", "Any RS"], ["r70", "70+"], ["r80", "80+"], ["r90", "90+"]], U, "rs", save));
  f.append(chips("Sort", [["best", "Best first"], ["new", "Newest first"]], U, "sort", save));
  const qi = $(`<input type="search" class="orq" placeholder="Find a ticker, company or sub-theme" aria-label="Find">`); qi.value = U.q || ""; let qt = null;
  qi.addEventListener("input", () => { clearTimeout(qt); qt = setTimeout(() => { U.q = qi.value; rerenderPanel(); const n = PQ(".ipcard .orq"); if (n) { n.focus(); n.setSelectionRange(n.value.length, n.value.length); } }, 250); });
  f.append(qi);
  card.querySelector(".iptv").addEventListener("click", () => tsDownload("in-play", [{ name: "In play", ticks: shown.map(r => r.t) }]));
  app.append(card);
}
// Nov 5 (Adam: "a separate tab for AI Revenue Setups where we look for all these stocks coming back into EMAs"): Stocks → AI Revenue =
// DATA.themes.airev (breadth/airev.py): AI Monetizers pool (verified AI revenue line) + the two AI software themes + rewarded software / IT
// reports in the last 20 sessions, each run through the Lined-up buys test (`lineupState`: in the 9/21 EMAs → buy over yesterday's high,
// stop the dip low, max 1 ADR), live from the Google sheet during the session.
const AIR_SRC = { verified: ["Verified AI revenue", "sow-breakout"], theme: ["AI theme", "sow-riding"], services: ["AI services (indirect)", "sow-pop"], report: ["Rewarded report", "sow-nuzzle"] };
function renderAIRev(app) {
  const X = (DATA.themes || {}).airev;
  if (!X || !X.rows) { app.append($('<div class="card empty">The AI Revenue list appears after the next data run.</div>')); return; }
  app.append(liveBar());
  UI.air = UI.air || { show: lsGet("airShow", "ema"), src: lsGet("airSrc", "all"), kind: lsGet("airKind", "all"), trend: lsGet("airTrend", "up"), rs: lsGet("airRs", "any"), grp: lsGet("airGrp", "any") };
  const U = UI.air, live = liveActive();
  const RK = { over: 0, zone: 1, near: 2 };
  const all = X.rows.map(r => {
    const s = lineupState(r), L = live ? liveRow(r.t) : null;
    const rep = L && L.gap != null && r.adr && Math.abs(L.gap) >= Math.max(0.03, r.adr) ? L.gap : null;
    return { ...s, repToday: rep };
  });
  const srcSet = new Set(String(U.src).split(","));
  const RSMIN = { any: 0, r70: 70, r80: 80 };
  const pass = (r, skip) => (skip === "show" || U.show === "all" || (U.show === "ema" ? (r.st === "over" || r.st === "zone") : r.st != null))
    && (srcSet.has("all") || r.src.some(k => srcSet.has(k))) && (U.kind === "all" || r.kind === U.kind)
    && (U.trend === "all" || r.up) && ((r.rs || 0) >= RSMIN[U.rs]) && (U.grp === "any" || r.signal === "buy");
  const rows = all.filter(r => pass(r)).sort((a, b) => ((RK[a.st] ?? 9) - (RK[b.st] ?? 9)) || ((b.precise ? 1 : 0) - (a.precise ? 1 : 0)) || ((b.rs || 0) - (a.rs || 0)));
  const cnt = (v) => all.filter(r => { const o = U.show; U.show = v; const ok = pass(r); U.show = o; return ok; }).length;
  const stTag = (r) => r.st === "over" ? '<span class="tg sow-breakout"><b>Over the trigger</b></span>' : r.st === "zone" ? '<span class="tg sow-nuzzle">In the EMAs</span>'
    : r.st === "near" ? '<span class="tg sow-riding">Near (1 ADR above)</span>' : '<span class="meta">not in the EMAs</span>';
  const why = (r) => r.src.map(k => `<span class="tg ${AIR_SRC[k][1]}" title="${esc(k === "verified" ? r.ai_note : k === "report" && r.report ? "rewarded report " + r.report.date : "")}">${AIR_SRC[k][0]}</span>`).join(" ")
    + (r.src.includes("verified") && r.ai_in === false ? ` <small class="meta" title="${esc(r.ai_why)}">market says not yet</small>` : "")
    + (r.repToday != null ? ` <span class="tg ${r.repToday > 0 ? "sow-breakout" : "sow-extended"}">gap ${pct(r.repToday, 1)} today</span>` : "");
  const card = $(`<section class="card ortable aircard"><div class="head"><h2>AI Revenue setups <span class="meta">· ${rows.length} of ${all.length} · companies showing AI revenue, pulling back into their 9 / 21 EMAs · ${live ? "live" : shortDate(X.date) + " close"}</span></h2>
    <button class="xopen airtv">⬇ TradingView</button></div><div class="filters" style="display:flex;flex-wrap:wrap;gap:8px;margin:6px 0"></div>
    <div class="scroll"><table class="grid"><thead><tr><th>#</th><th class="l">Ticker</th><th class="l">Why it's here</th><th class="l">Setup</th><th title="Buy over yesterday's high">Buy over</th><th title="Dip low, max 1 ADR under the trigger">Stop</th><th>Risk</th><th title="ADRs from price to the trigger">To trigger</th>
      ${live ? "<th>Today</th>" : ""}<th>RS</th><th>5D</th><th>Off high</th><th class="l">Group (lifecycle)</th><th class="l">Last report</th><th class="l">Next earnings</th></tr></thead><tbody>
    ${rows.map((r, i) => `<tr><td class="num">${i + 1}</td><td class="l"><a href="#" class="tkl" data-t="${esc(r.t)}"><b>${esc(r.t)}</b></a>${r.up ? "" : ' <small class="meta" title="21 EMA not above a rising 50">no uptrend</small>'}<small class="meta" style="display:block">${esc(r.name || "")}</small></td>
      <td class="l">${why(r)}${r.ai_note ? `<small class="meta" style="display:block;max-width:340px">${esc(r.ai_note)}</small>` : ""}</td>
      <td class="l">${stTag(r)}${r.d9 != null ? " " + lineupLocTag(r) : ""}</td>
      <td class="num">${r.trig ? "$" + r.trig.toFixed(2) : "–"}</td><td class="num">${r.stop ? "$" + r.stop.toFixed(2) : "–"}</td><td class="num">${r.risk == null ? "–" : (r.risk * 100).toFixed(1) + "%"}</td>
      <td class="num">${r.toTrig == null ? "–" : r.toTrig.toFixed(1)}</td>${live ? `<td class="num ${tint(r.chg, 0.03)}">${pct(r.chg, 1)}</td>` : ""}
      <td class="num">${r.rs ?? "–"}</td><td class="num ${tint(r.d5, 0.06)}">${pct(r.d5, 1)}</td><td class="num">${pct(r.off_hi, 1)}</td>
      <td class="l">${esc(r.g || "–")}<small class="meta" style="display:block">${r.signal === "buy" ? "<b>BUY</b> · " : ""}${esc(r.stage || "")}${r.pop ? ` · popped ${r.pop.ago} sessions ago` : ""}</small></td>
      <td class="l">${r.report ? `${shortDate(r.report.date)} <span class="${r.report.move > 0 ? "up" : "dn"}">${pct(r.report.move, 1)}</span><small class="meta"> · since ${pct(r.report.since, 0)}</small>` : ""}</td>
      <td class="l">${r.earn ? shortDate(r.earn) : ""}</td></tr>`).join("") || `<tr><td class="l meta" colspan="15">Nothing matches these filters.</td></tr>`}
    </tbody></table></div>
    <p class="meta" style="margin:8px 0 0"><b>Who's on it:</b> <b>Verified AI revenue</b> = the AI Monetizers pool (a company that reports an AI revenue number; "market says not yet" = its last big report was sold) · <b>AI theme</b> = Enterprise AI SaaS / AI Monetizers theme members · <b>AI services (indirect)</b> = consultants and IT services firms paid to build and run AI for clients (IT Services & Consulting, India IT Services, Defense IT) · <b>Rewarded report</b> = a software or IT services stock that gapped up 3%+ on 2.5× volume after a report in the last 20 sessions (the AI angle isn't checked: read the report). <b>The setup</b> is the Lined-up buys rule: a dip into the 9 / 21 EMAs, buy over yesterday's high, stop at the dip low (max 1 ADR). Its tested edge comes from the GROUP filter: in lifecycle <b>BUY</b> groups +0.85R a trade vs +0.11R elsewhere; "AI revenue" on its own isn't tested yet. Today's reporters join the list after tonight's close.</p></section>`);
  const f = card.querySelector(".filters");
  const save = () => { ["show", "src", "kind", "trend", "rs", "grp"].forEach(k => lsSet("air" + k[0].toUpperCase() + k.slice(1), U[k])); rerenderPanel(); };
  f.append(chips("Show", [["ema", `In the EMAs <small>${cnt("ema")}</small>`], ["near", `+ near <small>${cnt("near")}</small>`], ["all", `All <small>${cnt("all")}</small>`]], U, "show", save));
  f.append(chips("AI revenue", [["all", "Direct + indirect"], ["direct", "Direct (sells AI)"], ["indirect", "Indirect (builds AI for clients)"]], U, "kind", save));
  f.append(chipsMulti("Source", [["all", "All"], ["verified", "Verified AI revenue"], ["theme", "AI theme"], ["services", "AI services"], ["report", "Rewarded report"]], U, "src", save));
  f.append(chips("Trend", [["up", "Uptrend only"], ["all", "Any"]], U, "trend", save));
  f.append(chips("RS", [["any", "Any RS"], ["r70", "70+"], ["r80", "80+"]], U, "rs", save));
  f.append(chips("Group", [["any", "Any group"], ["buy", "BUY groups (tested)"]], U, "grp", save));
  card.querySelector(".airtv").addEventListener("click", () => tsDownload("ai-revenue-setups", [{ name: "AI revenue setups", ticks: rows.map(r => r.t) }]));
  app.append(card);
  // Nov 5 (Adam couldn't find ACN: it was 1 ADR over its 9 EMA, so the "In the EMAs" view hid it): every other name on the list that passes the
  // filters is shown below, closest to its EMAs first, so nothing disappears.
  if (U.show !== "all") {
    const shown = new Set(rows.map(r => r.t));
    const wait = all.filter(r => !shown.has(r.t) && pass(r, "show")).sort((a, b) => { const k = (r) => r.d9 == null ? 99 : Math.min(Math.abs(r.d9), Math.abs(r.d21)); return k(a) - k(b); });
    if (wait.length) app.append($(`<section class="card ortable aircard"><div class="head"><h2>On the list · waiting for a pullback <span class="meta">· ${wait.length} · not in the 9 / 21 EMAs right now, closest first</span></h2></div>
      <div class="scroll"><table class="grid"><thead><tr><th class="l">Ticker</th><th class="l">Why it's here</th><th class="l">Where it is</th><th title="ADRs above (+) or below (−) the 9 EMA">vs 9 EMA</th><th title="ADRs vs the 21 EMA">vs 21 EMA</th>${live ? "<th>Today</th>" : ""}<th>RS</th><th>5D</th><th>Off high</th><th class="l">Group (lifecycle)</th><th class="l">Last report</th><th class="l">Next earnings</th></tr></thead><tbody>
      ${wait.map(r => `<tr><td class="l"><a href="#" class="tkl" data-t="${esc(r.t)}"><b>${esc(r.t)}</b></a><small class="meta" style="display:block">${esc(r.name || "")}</small></td><td class="l">${why(r)}</td>
        <td class="l">${r.d9 != null ? lineupLocTag(r) : ""}</td><td class="num">${r.d9 == null ? "–" : (r.d9 >= 0 ? "+" : "") + r.d9.toFixed(1)}</td><td class="num">${r.d21 == null ? "–" : (r.d21 >= 0 ? "+" : "") + r.d21.toFixed(1)}</td>
        ${live ? `<td class="num ${tint(r.chg, 0.03)}">${pct(r.chg, 1)}</td>` : ""}<td class="num">${r.rs ?? "–"}</td><td class="num ${tint(r.d5, 0.06)}">${pct(r.d5, 1)}</td><td class="num">${pct(r.off_hi, 1)}</td>
        <td class="l">${esc(r.g || "–")}<small class="meta" style="display:block">${r.signal === "buy" ? "<b>BUY</b> · " : ""}${esc(r.stage || "")}</small></td>
        <td class="l">${r.report ? `${shortDate(r.report.date)} <span class="${r.report.move > 0 ? "up" : "dn"}">${pct(r.report.move, 1)}</span>` : ""}</td><td class="l">${r.earn ? shortDate(r.earn) : ""}</td></tr>`).join("")}
      </tbody></table></div><p class="meta" style="margin:8px 0 0">A name moves to the table above when it pulls back into its 9 / 21 EMAs. Above its 9 EMA = extended, wait; under its 21 = the pullback went too deep for this setup.</p></section>`));
  }
}
// Nov 7, 2026 (Adam: "a tab dedicated to analyzing the themes that emerge starting from the beginning of the day 11/6 … money flow, EMAs etc.
// This date may change, but I want to anchor to a bottom where themes and/or leaders begin to emerge"): Groups → Since the bottom.
// breadth/emerge.py ships compact arrays; everything is computed here so the start date is a picker (last 25 sessions) and live prices
// extend it. Descriptive only — nothing is backtested and nothing moves the picks.
function emergeCalc(X, si) {
  const P = X.pre, D = X.days, a = si - 1, live = liveActive();
  const benchR = (b) => { const c = (X.bench || {})[b]; if (!c) return null; const lr = live ? liveRow(b) : null; return (lr ? lr.price : c[c.length - 1]) / c[a] - 1; };
  const spyR = benchR(X.bench.SPY ? "SPY" : Object.keys(X.bench)[0]);
  const S = {};
  for (const [t, x] of Object.entries(X.rows)) {
    const c = x.c, lr = live ? liveRow(t) : null;
    const cs = lr ? [...c, lr.price] : c, L = cs.length - 1;
    const dvAt = (i) => i < c.length ? x.dv[i - P] : (lr && lr.volume ? lr.price * lr.volume / 1e6 : null);
    if (!c[a] || !cs[L]) continue;
    const r = cs[L] / c[a] - 1;
    let pre = 0; for (let i = Math.max(0, a - 19); i <= a; i++) pre = Math.max(pre, c[i]);
    const dd = c[a] / pre - 1, rec = pre > c[a] * 1.003 ? (cs[L] - c[a]) / (pre - c[a]) : null;
    let [e9, e21, e50] = x.e, at = {};
    const K = [2 / 10, 2 / 22, 2 / 51];
    for (let i = P; i <= L; i++) {
      if (e9 != null) e9 += K[0] * (cs[i] - e9); if (e21 != null) e21 += K[1] * (cs[i] - e21); if (e50 != null) e50 += K[2] * (cs[i] - e50);
      if (i === a) at.a = { e9, e21, e50 }; if (i === L) at.L = { e9, e21, e50 };
    }
    if (a === P - 1) at.a = { e9: x.e[0], e21: x.e[1], e50: x.e[2] };
    let net = 0, tot = 0, upd$ = 0, nd = 0, upn = 0, hi = x.hs || 0, nh = null;
    for (let i = 0; i <= a; i++) hi = Math.max(hi, c[i]);
    for (let i = a + 1; i <= L; i++) {
      const sg = cs[i] > cs[i - 1] ? 1 : cs[i] < cs[i - 1] ? -1 : 0; if (sg > 0) upn++;
      if (nh == null && cs[i] > hi) nh = i; hi = Math.max(hi, cs[i]);
      const d = dvAt(i); if (d == null) continue; net += d * sg; tot += d; if (sg > 0) upd$ += d; nd++;
    }
    const bi = Math.min(Math.max(a + 1 - P, 0), x.b50.length - 1), base = x.b50[bi];
    S[t] = { t, x, r, rel: spyR == null ? null : (1 + r) / (1 + spyR) - 1, dd, rec, pre,
      a21: at.a && at.a.e21 != null ? c[a] > at.a.e21 : null, n21: at.L && at.L.e21 != null ? cs[L] > at.L.e21 : null,
      n50: at.L && at.L.e50 != null ? cs[L] > at.L.e50 : null, n9: at.L && at.L.e9 != null ? cs[L] > at.L.e9 : null,
      net, tot, up$: upd$, nd, base, pace: base && nd ? tot / nd / base : null, ups: (L - a) ? upn / (L - a) : null,
      nh, nhDate: nh == null ? null : (nh < D.length ? D[nh] : "today"), today: lr ? lr.chg : null, cs };
  }
  const nsess = Object.values(S)[0] ? Object.values(S)[0].cs.length - 1 - a : 0;
  const mean = (v) => v.length ? v.reduce((p, q) => p + q, 0) / v.length : null;
  const med = (v) => { v = v.filter(z => z != null && isFinite(z)).sort((p, q) => p - q); if (!v.length) return null; const m = v.length >> 1; return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2; };
  const share = (v) => { v = v.filter(z => z != null); return v.length ? v.filter(Boolean).length / v.length : null; };
  const group = (name, mem, parent) => {
    const m = mem.map(t => S[t]).filter(Boolean); if (m.length < 3) return null;
    const r = mean(m.map(s => Math.max(-0.5, Math.min(1, s.r))));
    const tot = m.reduce((p, s) => p + s.tot, 0), bas = m.reduce((p, s) => p + (s.base || 0) * s.nd, 0);
    const L0 = m[0].cs.length - 1, spark = [];
    for (let i = Math.max(0, a - 10); i <= L0; i++) spark.push(mean(m.map(s => s.cs[i] / s.x.c[a])));
    const td = m.map(s => s.today).filter(z => z != null);
    return { name, parent, n: m.length, r, rel: spyR == null ? null : (1 + r) / (1 + spyR) - 1, up: share(m.map(s => s.r > 0)),
      n21: share(m.map(s => s.n21)), a21: share(m.map(s => s.a21)), n50: share(m.map(s => s.n50)),
      net: m.reduce((p, s) => p + s.net, 0), pace: bas ? tot / bas : null, up$: tot ? m.reduce((p, s) => p + s.up$, 0) / tot : null,
      nh: m.filter(s => s.nh != null).length, dd: med(m.map(s => s.dd)), rec: med(m.map(s => s.rec)), spark, sk: Math.min(10, a),
      lead: m.slice().sort((p, q) => q.r - p.r).slice(0, 4), today: td.length ? mean(td) : null, members: m.map(s => s.t) };
  };
  const mk = (src, par) => Object.entries(src).map(([g, mem]) => group(g, mem, par ? (X.parent[g] || "") : "")).filter(Boolean);
  const score = (G) => {
    const pr = (k) => { const v = G.map(g => g[k] ?? -9).slice().sort((p, q) => p - q); return (x) => v.length > 1 ? v.filter(z => z < (x ?? -9)).length / (v.length - 1) : 0.5; };
    const W = [["rel", 0.35], ["up", 0.15], ["n21", 0.15], ["up$", 0.2], ["nhs", 0.15]];
    G.forEach(g => { g.nhs = g.nh / g.n; });
    const F = W.map(([k, w]) => [k, w, pr(k)]);
    G.forEach(g => { const raw = 100 * F.reduce((p, [k, w, f]) => p + w * f(g[k]), 0); g.score = Math.round(50 + (raw - 50) * Math.min(1, g.n / 8)); });   // groups under 8 stocks shrunk toward 50
    return G;
  };
  const all = Object.values(S);
  // day by day: each session's best and worst sub-themes vs SPY (equal-weight member move that day)
  const spyC = X.bench.SPY || []; const lsp = live ? liveRow("SPY") : null; const spyCs = lsp ? [...spyC, lsp.price] : spyC;
  const daily = [];
  for (let i = a + 1; i < spyCs.length; i++) {
    const sr = spyCs[i] / spyCs[i - 1] - 1;
    const g = Object.entries(X.subs).map(([n, mem]) => { const v = mem.map(t => S[t]).filter(s => s && s.cs[i] != null && s.cs[i - 1]).map(s => s.cs[i] / s.cs[i - 1] - 1); return v.length >= 3 ? { n, v: mean(v) - sr, up: v.filter(z => z > 0).length / v.length } : null; }).filter(Boolean).sort((p, q) => q.v - p.v);
    const st = all.filter(s => s.cs[i] != null && s.cs[i - 1]).map(s => ({ t: s.t, v: s.cs[i] / s.cs[i - 1] - 1 }));
    daily.push({ d: i < D.length ? D[i] : "today", spy: sr, top: g.slice(0, 6), bot: g.slice(-3).reverse(), up: st.length ? st.filter(z => z.v > 0).length / st.length : null });
  }
  return { S, all, subs: score(mk(X.subs, true)), themes: score(mk(X.themes, false)), spyR, bench: Object.fromEntries(Object.keys(X.bench).map(b => [b, benchR(b)])),
    nsess, a, daily, mkt: { up: share(all.map(s => s.r > 0)), n21: share(all.map(s => s.n21)), a21: share(all.map(s => s.a21)), nh: all.filter(s => s.nh != null).length, n: all.length } };
}
function emSpark(g) {
  const v = g.spark.filter(z => z != null); if (v.length < 3) return "";
  const w = 110, h = 28, lo = Math.min(1, ...v), hi = Math.max(1, ...v), sp = hi - lo || 1, n = v.length - 1;
  const y = (z) => (h - 2 - (z - lo) / sp * (h - 4)).toFixed(1), kx = (g.sk / n * w).toFixed(1);
  const pts = v.map((z, i) => `${(i / n * w).toFixed(1)},${y(z)}`).join(" ");
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-label="group index, base = 1"><line x1="0" x2="${w}" y1="${y(1)}" y2="${y(1)}" class="orgridl"/><line x1="${kx}" x2="${kx}" y1="0" y2="${h}" class="orgridl"/><polyline points="${pts}" fill="none" stroke="var(--s1)" stroke-width="1.6"/></svg>`;
}
function renderEmerge(app) {
  const X = (DATA.themes || {}).emerge;
  if (!X || !X.rows) { app.append($('<div class="card empty">Since the bottom appears after the next data run.</div>')); return; }
  app.append(liveBar());
  const D = X.days, picks = D.slice(X.pre);
  UI.em = UI.em || { st: lsGet("emStart", X.start), view: lsGet("emView", "sub"), by: lsGet("emBy", "score"), sc: lsGet("emScope", "top"), rs: lsGet("emRs", "all"), sb: lsGet("emSort", "r"), sel: "", all: false };
  const U = UI.em;
  if (!picks.includes(U.st)) U.st = picks.includes(X.start) ? X.start : picks[picks.length - 1];
  const si = D.indexOf(U.st), Z = emergeCalc(X, si), live = liveActive();
  const save = () => { lsSet("emStart", U.st); lsSet("emView", U.view); lsSet("emBy", U.by); lsSet("emScope", U.sc); lsSet("emRs", U.rs); lsSet("emSort", U.sb); try { Object.keys(AUTOSORT).filter(k => k.includes("Since the bottom")).forEach(k => delete AUTOSORT[k]); } catch (e) {} rerenderPanel(); };
  const pp = (v) => v == null ? "–" : Math.round(v * 100) + "%";
  const xx = (v) => v == null ? "–" : v.toFixed(2) + "×";
  const ses = Z.nsess, M = Z.mkt;
  const head = $(`<section class="card orhead"><h2>Since the bottom <span class="meta">· since the ${shortDate(D[si - 1])} close (${shortDate(U.st)} is the first session counted) · ${ses} session${ses === 1 ? "" : "s"}${live ? " incl. today live" : ""} · data to ${shortDate(X.date)}</span></h2>
    <div class="filters"><div class="chips" role="group" aria-label="Start"><span class="meta" style="align-self:center">Since the close of</span> <select class="emstart" aria-label="Base close (the bottom)">${picks.slice().reverse().map(d => `<option value="${d}"${d === U.st ? " selected" : ""}>${shortDate(D[D.indexOf(d) - 1])}${d === X.default_start ? " (default)" : ""}</option>`).join("")}</select>
      ${U.st !== X.start ? `<button class="emreset">Back to ${shortDate(D[D.indexOf(X.start) - 1])}</button>` : ""}</div></div>
    <div class="meta orsub">Market since the base: ${Object.entries(Z.bench).map(([b, v]) => `<b>${b}</b> <span class="${tint(v, 0.02)}">${pct(v, 1)}</span>`).join(" · ")} ·
      ${pp(M.up)} of ${M.n} theme stocks up · above their 21 EMA <b>${pp(M.n21)}</b> now vs ${pp(M.a21)} at the base · <b>${M.nh}</b> at a new 3-month closing high.</div>
    <div class="meta orsub">Pick the close you think was the bottom; everything below re-counts from the next session on. <b>Emergence score</b> (0–100, ranks the groups against each other) =
      35% vs SPY since the base · 20% share of dollar volume on up days · 15% share of members up · 15% share above their 21 EMA · 15% share at a new 3-month closing high.
      It's a lens, not a tested signal: past studies here found plain RS leaders lagged after thrusts, while high-beta names paid only after deep washouts (SPY −8%+, T2108 ≤ 25). Watch who keeps scoring as the sessions add up.</div></section>`);
  const f = head.querySelector(".filters");
  head.querySelector(".emstart").addEventListener("change", (e) => { U.st = e.target.value; U.sel = ""; save(); });
  const rb = head.querySelector(".emreset"); if (rb) rb.addEventListener("click", () => { U.st = X.start; save(); });
  f.append(chips("View", [["sub", "Sub-themes"], ["theme", "Themes"]], U, "view", () => { U.sel = ""; save(); }));
  f.append(chips("Sort", [["score", "Emergence score"], ["rel", "Vs SPY"], ["flow", "Up-volume share"], ["nh", "New highs"], ["held", "Held up best into the bottom"]], U, "by", save));
  app.append(head);
  const SORT = { score: (p, q) => q.score - p.score, rel: (p, q) => (q.rel ?? -9) - (p.rel ?? -9), flow: (p, q) => (q.up$ ?? -9) - (p.up$ ?? -9), nh: (p, q) => q.nhs - p.nhs || q.rel - p.rel, held: (p, q) => (q.dd ?? -9) - (p.dd ?? -9) };
  const G = (U.view === "sub" ? Z.subs : Z.themes).slice().sort(SORT[U.by] || SORT.score);
  const rank = Object.fromEntries((U.view === "sub" ? Z.subs : Z.themes).slice().sort(SORT.score).map((g, i) => [g.name, i + 1]));
  const gtab = $(`<section class="card ortable"><div class="head"><h2>${G.length} ${U.view === "sub" ? "sub-themes" : "themes"} <span class="meta">· click a name to list its stocks below · hover a header for what it means</span></h2><button class="xopen emgtv">⬇ TradingView (top 10 groups)</button></div>
    <div class="scroll"><table class="grid"><thead><tr><th>#</th><th class="l">${U.view === "sub" ? "Sub-theme" : "Theme"}</th><th title="0–100 vs the other groups (see the note above)">Score</th><th title="Equal-weight member move since the base close">Since</th><th>Vs SPY</th>
      <th title="Share of members up since the base">Up</th><th title="Share above their 21 EMA now (and the change since the base)">Above 21 EMA</th><th title="Share above their 50 EMA now">Above 50</th>
      <th title="Share of the group's dollar volume traded on up days since the base">Up-$ share</th><th title="Average daily dollar volume since the base vs the 50 days before">$ vol × normal</th>
      <th title="Members at a new 3-month closing high since the base">New highs</th><th title="Median drop from the 20-day closing high into the base close (closer to 0 = held up)">Into the bottom</th>
      <th title="Median share of that drop won back since">Won back</th>${live ? "<th>Today</th>" : ""}<th class="l">Base → now</th><th class="l">Leading stocks since the base</th></tr></thead><tbody>
    ${G.map(g => `<tr${g.name === U.sel ? ' class="sel"' : ""}><td class="num">${rank[g.name]}</td><td class="l"><a href="#" class="emg" data-g="${esc(g.name)}"><b>${esc(g.name)}</b></a><small class="meta" style="display:block">${g.n} stocks${g.parent ? " · " + esc(g.parent) : ""}</small></td>
      <td class="num"><b>${g.score}</b></td><td class="num ${tint(g.r, 0.03)}">${pct(g.r, 1)}</td><td class="num ${tint(g.rel, 0.02)}">${pct(g.rel, 1)}</td><td class="num">${pp(g.up)}</td>
      <td class="num" data-v="${g.n21 ?? 0}">${pp(g.n21)}<small class="meta" style="display:block">${g.a21 == null ? "" : (g.n21 - g.a21 >= 0 ? "+" : "") + Math.round((g.n21 - g.a21) * 100) + " pts"}</small></td>
      <td class="num">${pp(g.n50)}</td><td class="num ${g.up$ == null ? "" : tint(g.up$ - 0.5, 0.15)}">${pp(g.up$)}</td><td class="num">${xx(g.pace)}</td>
      <td class="num" data-v="${g.nhs}">${g.nh}<small class="meta"> / ${g.n}</small></td><td class="num ${tint(g.dd, 0.08)}">${pct(g.dd, 1)}</td><td class="num">${g.rec == null ? "–" : Math.round(g.rec * 100) + "%"}</td>
      ${live ? `<td class="num ${tint(g.today, 0.02)}">${pct(g.today, 1)}</td>` : ""}<td class="l">${emSpark(g)}</td>
      <td class="l">${g.lead.map(s => `<a href="#" class="tkl" data-t="${esc(s.t)}"><b>${esc(s.t)}</b></a> <small class="meta">${pct(s.r, 0)}</small>`).join(" · ")}</td></tr>`).join("")}
    </tbody></table></div></section>`);
  gtab.querySelectorAll(".emg").forEach(el => el.addEventListener("click", (e) => { e.preventDefault(); U.sel = U.sel === el.dataset.g ? "" : el.dataset.g; if (U.sel) U.sc = "sel"; else if (U.sc === "sel") U.sc = "top"; save(); }));
  gtab.querySelector(".emgtv").addEventListener("click", () => tsDownload("since-the-bottom-groups", G.slice(0, 10).map(g => ({ name: shortDate(U.st) + " - " + g.name, ticks: g.lead.map(s => s.t).concat(g.members.filter(t => !g.lead.some(s => s.t === t))).slice(0, 12) }))));
  app.append(gtab);
  // stocks
  const top10 = new Set((U.view === "sub" ? Z.subs : Z.themes).slice().sort(SORT.score).slice(0, 10).flatMap(g => g.members));
  const selG = U.sel ? G.find(g => g.name === U.sel) : null;
  if (U.sc === "sel" && !selG) U.sc = "top";
  let rows = Z.all.filter(s => U.sc === "all" || (U.sc === "top" ? top10.has(s.t) : selG.members.includes(s.t)));
  if (U.rs === "80") rows = rows.filter(s => (s.x.rs || 0) >= 80);
  if (U.rs === "nh") rows = rows.filter(s => s.nh != null);
  if (U.rs === "rc") rows = rows.filter(s => s.n21 && s.a21 === false);
  const SS = { r: (p, q) => q.r - p.r, first: (p, q) => (p.nh ?? 999) - (q.nh ?? 999) || q.r - p.r, held: (p, q) => q.dd - p.dd, flow: (p, q) => (q.up$ / (q.tot || 1)) - (p.up$ / (p.tot || 1)) || q.r - p.r, pace: (p, q) => (q.pace ?? 0) - (p.pace ?? 0) };
  rows.sort(SS[U.sb] || SS.r);
  const shown = U.all ? rows : rows.slice(0, 80);
  const tag21 = (s) => s.n21 == null ? "–" : s.n21 && s.a21 === false ? '<span class="tg sow-breakout">Reclaimed</span>' : s.n21 ? '<span class="tg">Held above</span>' : s.a21 ? '<span class="tg sow-extended">Lost it</span>' : '<span class="meta">Below</span>';
  const scard = $(`<section class="card ortable"><div class="head"><h2>Stocks <span class="meta">· ${rows.length} ${U.sc === "sel" ? "in " + esc(U.sel) : U.sc === "top" ? "in the top 10 groups by score" : "theme stocks"}</span></h2><button class="xopen emstv">⬇ TradingView</button></div>
    <div class="filters"></div>
    <div class="scroll"><table class="grid"><thead><tr><th class="l">Stock</th><th class="l">Sub-theme</th><th>RS</th><th>Since</th><th>Vs SPY</th><th title="Drop from the 20-day closing high into the base close">Into the bottom</th><th title="Share of that drop won back">Won back</th>
      <th class="l" title="Close vs the 21 EMA now, compared with the base">21 EMA</th><th title="Share of its dollar volume since the base traded on up days">Up-$ share</th><th title="Average $ volume since the base vs its 50-day average">$ vol × normal</th>
      <th title="First session it closed at a new 3-month high after the base">New 3-mo high</th>${live ? "<th>Today</th>" : ""}</tr></thead><tbody>
    ${shown.map(s => `<tr><td class="l"><a href="#" class="tkl" data-t="${esc(s.t)}"><b>${esc(s.t)}</b></a><small class="meta" style="display:block">${esc(s.x.nm)}</small></td><td class="l"><small>${esc(s.x.sub || "–")}</small></td>
      <td class="num">${s.x.rs ?? "–"}</td><td class="num ${tint(s.r, 0.04)}">${pct(s.r, 1)}</td><td class="num ${tint(s.rel, 0.03)}">${pct(s.rel, 1)}</td><td class="num ${tint(s.dd, 0.1)}">${pct(s.dd, 1)}</td>
      <td class="num" data-v="${s.rec ?? -9}">${s.rec == null ? "–" : s.rec > 3 ? "300%+" : Math.round(s.rec * 100) + "%"}</td><td class="l">${tag21(s)}</td><td class="num">${s.tot ? pp(s.up$ / s.tot) : "–"}</td><td class="num">${xx(s.pace)}</td>
      <td class="num" data-v="${s.nh == null ? 0 : 999 - s.nh}">${s.nhDate ? (s.nhDate === "today" ? "today" : shortDate(s.nhDate)) : "–"}</td>${live ? `<td class="num ${tint(s.today, 0.03)}">${pct(s.today, 1)}</td>` : ""}</tr>`).join("")}
    </tbody></table></div>${rows.length > shown.length ? `<button class="xopen emall" style="margin:8px 0">Show all ${rows.length}</button>` : ""}</section>`);
  const f2 = scard.querySelector(".filters");
  f2.append(chips("Which", [["top", "Top 10 groups"], ...(selG ? [["sel", esc(U.sel)]] : []), ["all", "All theme stocks"]], U, "sc", save));
  f2.append(chips("Only", [["all", "Any"], ["80", "RS 80+"], ["nh", "Made a new 3-month high"], ["rc", "Reclaimed the 21 EMA"]], U, "rs", save));
  f2.append(chips("Sort", [["r", "Most up since"], ["first", "First to a new high"], ["flow", "Up-volume share"], ["pace", "$ volume × normal"], ["held", "Held up best"]], U, "sb", save));
  const ab = scard.querySelector(".emall"); if (ab) ab.addEventListener("click", () => { U.all = true; rerenderPanel(); });
  scard.querySelector(".emstv").addEventListener("click", () => tsDownload("since-the-bottom-stocks", [{ name: "Since " + shortDate(U.st), ticks: rows.slice(0, 120).map(s => s.t) }]));
  app.append(scard);
  // day by day
  const dcard = $(`<section class="card"><h2>Day by day <span class="meta">· which sub-themes led each session since the base (equal-weight member move minus SPY's) — the order groups show up in is the emergence story</span></h2>
    <div class="scroll"><table class="grid"><thead><tr><th class="l">Session</th><th>SPY</th><th title="Share of theme stocks up that day">Stocks up</th><th class="l">Led</th><th class="l">Lagged</th></tr></thead><tbody>
    ${Z.daily.slice().reverse().map(d => `<tr><td class="l"><b>${d.d === "today" ? "Today (live)" : shortDate(d.d)}</b></td><td class="num ${tint(d.spy, 0.01)}">${pct(d.spy, 1)}</td><td class="num">${pp(d.up)}</td>
      <td class="l">${d.top.map(g => `${esc(g.n)} <small class="g2">${num(g.v * 100, 1)}</small>`).join(" · ")}</td><td class="l"><small>${d.bot.map(g => `${esc(g.n)} <span class="r2">${num(g.v * 100, 1)}</span>`).join(" · ")}</small></td></tr>`).join("")}
    </tbody></table></div></section>`);
  app.append(dcard);
}
