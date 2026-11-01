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
// Oct 31 (Adam: "scroll down and show inflow and outflow of dollars for the top 20 stocks in each of the periods"):
// DATA.themes.rotation.mstocks (rotation.money_stocks) = every liquid US stock ($5+, $20M+/day), top 20 per window by net $ flow
// (dollar volume + on up days, - on down days) or by share of its own trading ($100M+/day). Rows [t, net $M, share %, price %, avg $M/day].
function moneyStocksCard() {
  const M = ((DATA.themes || {}).rotation || {}).mstocks;
  if (!M || !M.windows) return $('<section class="card empty">Stock-level dollar flows appear after the next data run.</section>');
  UI.ms = UI.ms || { dir: lsGet("msDir", "both"), by: lsGet("msBy", "usd") };
  const U = UI.ms, sizeView = U.by === "size";
  const S = {}; (DATA.themes.stocks || []).forEach(r => { S[r.t] = r; });
  const fm = (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}$${Math.abs(v) >= 1000 ? (Math.abs(v) / 1000).toFixed(1) + "B" : Math.round(Math.abs(v)) + "M"}`;
  const lbl = (k) => k === 90 ? "90 days" : k === 30 ? "30 days" : k + " days";
  const card = $(`<section class="card msc"><div class="head"><h2>Stocks: where the dollars went <span class="meta">· top ${M.rules.n} by net dollar flow in each window, as of the ${shortDate(M.date)} close</span></h2>
      <button class="xopen mstv">⬇ TradingView</button></div><div class="filters"></div>
    <p class="meta">Net $ flow = a stock's dollar volume counted <b>+</b> on days it closed up and <b>−</b> on days it closed down, added over the window.
      ${sizeView ? `<b>For its size</b> ranks by net flow as a share of everything the stock traded (stocks trading $${Math.round(M.rules.size_dv / 1e6)}M+ a day), so a mid cap being bought hard ranks next to a mega cap.`
        : "<b>Dollars</b> favours the biggest companies (Apple, Microsoft): they trade so much that a small tilt is billions."}
      Every US stock $${M.rules.min_px}+ trading $${Math.round(M.rules.min_dv / 1e6)}M+ a day. <b>×N</b> = in this top ${M.rules.n} in N of the 5 windows. Click a ticker for details. <b>deal</b> = being acquired, so its flow is the deal.
      Descriptive: net flow alone hasn't tested as a forward signal.</p></section>`);
  const f = card.querySelector(".filters"), save = () => { lsSet("msDir", U.dir); lsSet("msBy", U.by); rerenderPanel(); };
  f.append(chips("Show", [["both", "Inflow and outflow"], ["in", "Inflow"], ["out", "Outflow"]], U, "dir", save));
  f.append(chips("Rank by", [["usd", "Dollars"], ["size", "For its size"]], U, "by", save));
  const sides = U.dir === "both" ? ["in", "out"] : [U.dir];
  sides.forEach(side => {
    const key = side + (sizeView ? "_size" : "");
    const seen = {}; M.windows.forEach(w => (w[key] || []).forEach(r => { seen[r[0]] = (seen[r[0]] || 0) + 1; }));
    const sec = $(`<div class="mssec"><h3 class="${side === "in" ? "up" : "dn"}">${side === "in" ? "Money coming in" : "Money going out"} <span class="meta">· biggest net ${side === "in" ? "inflow" : "outflow"}${sizeView ? " for its size" : " in dollars"}</span></h3><div class="msgrid"></div></div>`);
    const g = sec.querySelector(".msgrid");
    M.windows.forEach(w => {
      const rows = w[key] || [];
      g.append($(`<div class="mscol"><div class="msh"><b>${lbl(w.k)}</b> <span class="meta">since ${shortDate(w.since)}</span></div>
        <table class="grid mst"><thead><tr><th>#</th><th class="l">Stock</th><th>Net $</th><th>Share</th><th>Price</th></tr></thead><tbody>
        ${rows.map((r, i) => { const s = S[r[0]] || {}, nm = (M.names || {})[r[0]] || s.name || "", tip = [nm, s.sub].filter(Boolean).join(" · ") + ` · avg $${Math.round(r[4])}M a day`;
          return `<tr title="${esc(tip)}"><td class="num meta">${i + 1}</td><td class="l"><a href="#" class="tkl" data-t="${esc(r[0])}"><b>${esc(r[0])}</b></a>${(M.deals || {})[r[0]] ? ` <span class="msdeal" title="${esc(M.deals[r[0]])}">deal</span>` : ""}${seen[r[0]] >= 3 ? ` <span class="msx">×${seen[r[0]]}</span>` : ""}<small class="meta msn">${esc(s.sub || nm)}</small></td>
            <td class="num ${r[1] > 0 ? "up" : "dn"}">${fm(r[1])}</td><td class="num">${r[2] > 0 ? "+" : ""}${r[2].toFixed(0)}%</td><td class="num ${r[3] > 0 ? "up" : r[3] < 0 ? "dn" : ""}">${r[3] > 0 ? "+" : ""}${r[3].toFixed(1)}%</td></tr>`; }).join("")}
        </tbody></table></div>`));
    });
    card.append(sec);
  });
  card.querySelector(".mstv").addEventListener("click", () => tsDownload("money-flow-stocks", sides.flatMap(side => M.windows.map(w => ({
    name: `${side === "in" ? "Inflow" : "Outflow"} ${sizeView ? "(for its size) " : ""}${lbl(w.k)}`, ticks: (w[side + (sizeView ? "_size" : "")] || []).map(r => r[0]) })))));
  return card;
}
// Stocks → Leadership (Oct 31, Adam: "a tab for Leadership and add this" = the v1 Breadth tab's Market health card)
function renderLeadership(app) {
  const X = (DATA.themes || {}).leadership;
  app.append(X ? healthCard(X) : $('<div class="card empty">Leadership data appears after the next data run.</div>'));
}
