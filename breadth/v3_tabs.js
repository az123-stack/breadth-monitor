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
}
// Stocks → Leadership (Oct 31, Adam: "a tab for Leadership and add this" = the v1 Breadth tab's Market health card)
function renderLeadership(app) {
  const X = (DATA.themes || {}).leadership;
  app.append(X ? healthCard(X) : $('<div class="card empty">Leadership data appears after the next data run.</div>'));
}
