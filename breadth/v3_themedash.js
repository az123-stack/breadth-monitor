/* ---------- v3 · Groups → Theme Dash (Oct 30, 2026; Adam: Deepvue-style "every ticker in its group, click it and the chart comes up") ----------
   Right: a weekly TradingView chart of the selected ticker (loaded only on click, from TradingView). Left: groups with their tickers as chips.
   Default view = today's 52-week highs vs lows split by group, like Deepvue. Live: during the session a stock counts as a new high when
   the Google price is at or above its 52-week high (hi52), new low at or under lo52; otherwise the official close's flags (nh52 / nl52). */
// Adam, Oct 30: weekly chart opens on the same span as "back to Jan 2024" today = 34 months, kept as a rolling 34-month window
const TD_RANGE = "34M";
function tdState(s) {
  const L = liveActive() ? liveRow(s.t) : null, px = L ? L.price : s.price, chg = L ? L.chg : s.today;
  const hi = L ? (s.hi52 != null && px >= s.hi52) : !!s.nh52, lo = L ? (s.lo52 != null && px <= s.lo52) : !!s.nl52;
  const off = s.hi52 && px ? px / s.hi52 - 1 : s.off_hi;
  return { chg, hi, lo, off, px };
}
function tdChart(box, t) {
  const S = (getT().stocks || []).find(x => x.t === t), tv = ((DATA.themes || {}).tv || {})[t] || t, st = S ? tdState(S) : null;
  const dark = (document.documentElement.getAttribute("data-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark";
  const src = "https://s.tradingview.com/widgetembed/?" + new URLSearchParams({ frameElementId: "tdtv", symbol: tv, interval: "W", range: TD_RANGE, hidesidetoolbar: "1",
    symboledit: "1", saveimage: "0", withdateranges: "1", theme: dark ? "dark" : "light", style: "1", timezone: "America/New_York", locale: "en",
    studies: JSON.stringify(["MAExp@tv-basicstudies", "Volume@tv-basicstudies"]) }).toString();
  box.innerHTML = `<div class="tdch-h"><div><b class="tdch-t">${esc(t)}</b> <span class="meta">${esc(S ? S.name : "")}</span>
      <div class="meta">${S ? `${esc(S.sub || (S.themes || [])[0] || "")} · RS ${S.rsr ?? "–"} · ${st.chg == null ? "" : `<span class="${st.chg > 0 ? "up" : "dn"}">${pct(st.chg)}</span> today · `}${pct(S.d5)} 5D · ${st.off == null ? "–" : (st.off * 100).toFixed(1) + "% off 52-wk high"}` : "Not in our theme lists"}</div></div>
      <div class="tdch-b"><a href="#" class="xopen tkl" data-t="${esc(t)}">Details</a><a class="xopen" target="_blank" rel="noopener" href="https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tv)}">TradingView ↗</a></div></div>
    <iframe class="tdtv" title="${esc(t)} chart" src="${src}" loading="lazy" allowtransparency="true" frameborder="0"></iframe>`;
}
function renderThemeDash(app) {
  if (!DATA.themes) { app.append($('<div class="card empty">Theme data isn\'t available yet. It appears after the next data run.</div>')); return; }
  UI.td = UI.td || { by: lsGet("tdBy", "sub"), show: lsGet("tdShow", "hl"), sort: lsGet("tdSort", "strength"), q: "", sel: lsGet("tdSel", "") };
  const T = getT(), U = UI.td, sub = U.by === "sub";
  app.append(liveBar());
  // every member incl. ADRs (is_stock is false for ADRs too); only ETFs left out (no name, or "ETF / Fund / Trust" in it)
  const SM = Object.fromEntries((T.stocks || []).filter(s => s.name && !/\bETF\b|\bFund\b|\bTrust\b/.test(s.name)).map(s => [s.t, s]));
  const groups = (sub ? T.subthemes : T.themes) || [];
  const all = Object.values(SM).map(s => ({ s, st: tdState(s) }));
  const nH = all.filter(x => x.st.hi).length, nL = all.filter(x => x.st.lo).length;
  const asOf = liveActive() ? "live" : "at the " + shortDate(T.date) + " close";
  // ---- header: highs vs lows bar + controls ----
  const head = $(`<section class="card tdhead"><div class="tdbar" title="Theme stocks making a new 52-week high vs low ${asOf}">
      <div class="tdbh" style="flex:${Math.max(nH, 1)}"><b>${nH}</b> new highs</div><div class="tdbl" style="flex:${Math.max(nL, 1)}"><b>${nL}</b> new lows</div></div>
    <div class="meta tdsub">52-week highs and lows among our ${all.length} theme stocks, ${asOf}. Click any ticker to chart it.</div>
    <div class="filters"></div></section>`);
  const f = head.querySelector(".filters"), save = () => { ["by", "show", "sort"].forEach(k => lsSet("td" + k[0].toUpperCase() + k.slice(1), U[k])); rerenderPanel(); };
  f.append(chips("Group by", [["sub", "Sub-theme"], ["theme", "Theme"]], U, "by", save));
  f.append(chips("Show", [["hl", "New highs vs lows"], ["near", "Within 5% of high"], ["all", "Every stock"]], U, "show", save));
  if (U.show !== "hl") f.append(chips("Sort", [["strength", "Strength"], ["today", "Today"], ["d5", "5D"]], U, "sort", save));
  const qi = $('<input type="search" placeholder="Find a group or ticker">'); qi.value = U.q; f.append(qi);
  app.append(head);
  // ---- body: chart left, groups right ----
  const body = $('<section class="tdbody"><div class="tdgroups"></div><div class="card tdchart"></div></section>');
  app.append(body);
  const chartBox = body.querySelector(".tdchart"), gbox = body.querySelector(".tdgroups");
  const chipHTML = (x) => { const c = x.st.chg, cls = c == null ? "" : c >= 0.03 ? "u2" : c > 0 ? "u1" : c <= -0.03 ? "d2" : c < 0 ? "d1" : "";
    return `<button class="tdchip ${cls}${U.sel === x.s.t ? " on" : ""}" data-t="${esc(x.s.t)}" title="${esc(x.s.name || "")} · ${c == null ? "–" : pct(c)} today · RS ${x.s.rsr ?? "–"}">${x.st.hi ? "▲" : x.st.lo ? "▼" : ""}${esc(x.s.t)}<small>${c == null ? "" : (c > 0 ? "+" : "") + (c * 100).toFixed(1)}</small></button>`; };
  const build = () => {
    const q = U.q.toLowerCase();
    const rows = groups.map(g => {
      let mem = (g.members || []).map(t => SM[t]).filter(Boolean).map(s => ({ s, st: tdState(s) }));
      const hit = !q || g.theme.toLowerCase().includes(q) || mem.some(x => x.s.t.toLowerCase() === q);
      return { g, mem, hit, hi: mem.filter(x => x.st.hi), lo: mem.filter(x => x.st.lo) };
    }).filter(r => r.mem.length && r.hit);
    const avg = (mem, k) => { const v = mem.map(x => k === "today" ? x.st.chg : x.s[k]).filter(v => v != null); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };
    const block = (r, list, kind) => {
      const n = r.mem.length, share = Math.round(list.length / n * 100), td = avg(r.mem, "today");
      const rest = r.mem.filter(x => !list.includes(x)).sort((a, b) => (b.s.rsr ?? 0) - (a.s.rsr ?? 0));
      return `<div class="tdg"><div class="tdg-h"><span class="tdg-n" title="${esc(r.g.theme)}">${esc(r.g.theme)}</span>
        <span class="meta">${kind ? `${list.length} of ${n} · ${share}%` : `${n} stocks`} · str ${r.g.strength == null ? "–" : Math.round(r.g.strength)}${td == null ? "" : ` · <span class="${td > 0 ? "up" : "dn"}">${pct(td)}</span>`}</span></div>
        <div class="tdchips">${list.map(chipHTML).join("")}${rest.length ? `<button class="tdmore" data-l="+${rest.length} more">+${rest.length} more</button><span class="tdrest" hidden>${rest.map(chipHTML).join("")}</span>` : ""}</div></div>`;
    };
    const byRb = (k) => (a, b) => (b[k].length - a[k].length) || (b[k].length / b.mem.length - a[k].length / a.mem.length);
    let html;
    if (U.show === "hl") {
      const H = rows.filter(r => r.hi.length).sort(byRb("hi")), L = rows.filter(r => r.lo.length).sort(byRb("lo"));
      const col = (title, cls, arr, k, n) => `<div class="tdcol"><div class="tdcol-h ${cls}">${title} <span class="meta">${n} stocks · ${arr.length} groups</span></div>
        ${arr.length ? arr.map(r => block(r, r[k].sort((a, b) => (b.s.rsr ?? 0) - (a.s.rsr ?? 0)), k)).join("") : '<div class="meta tdnone">None today.</div>'}</div>`;
      html = `<div class="tdcols">${col("Groups making new highs", "hcol", H, "hi", nH)}${col("Groups making new lows", "lcol", L, "lo", nL)}</div>`;
    } else {
      const key = U.sort === "strength" ? (r) => r.g.strength ?? -1 : (r) => avg(r.mem, U.sort) ?? -9;
      const list = (r) => (U.show === "near" ? r.mem.filter(x => x.st.off != null && x.st.off >= -0.05) : r.mem)
        .sort((a, b) => (b.s.rsr ?? 0) - (a.s.rsr ?? 0));
      const out = rows.map(r => ({ r, l: list(r) })).filter(x => x.l.length).sort((a, b) => key(b.r) - key(a.r));
      html = `<div class="tdgrid">${out.map(x => block(x.r, x.l, U.show === "near" ? "near" : "")).join("") || '<div class="meta tdnone">No groups match.</div>'}</div>`;
    }
    gbox.innerHTML = html;
  };
  const pick = (t, scroll) => {
    U.sel = t; lsSet("tdSel", t);
    gbox.querySelectorAll(".tdchip").forEach(b => b.classList.toggle("on", b.dataset.t === t));
    tdChart(chartBox, t);
    if (scroll && window.matchMedia("(max-width: 900px)").matches) chartBox.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  gbox.addEventListener("click", (e) => {
    const m = e.target.closest(".tdmore"); if (m) { const r = m.nextElementSibling; r.hidden = !r.hidden; m.textContent = r.hidden ? m.dataset.l : "less"; return; }
    const b = e.target.closest(".tdchip"); if (b) pick(b.dataset.t, true); });
  qi.addEventListener("input", (e) => { U.q = e.target.value.trim(); build(); });
  build();
  const first = U.sel && SM[U.sel] ? U.sel : (gbox.querySelector(".tdchip") || {}).dataset?.t;
  if (first) pick(first, false); else chartBox.innerHTML = '<div class="meta" style="padding:16px">Click a ticker to see its chart.</div>';
}
