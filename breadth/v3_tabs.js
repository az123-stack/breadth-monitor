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
