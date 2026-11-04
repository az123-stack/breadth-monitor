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
