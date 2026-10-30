"""v3 page (Oct 30, 2026; Adam: "start over on the new dashboard ... go tab by tab and rebuild it. Start with the themes tab,
put it as a sub under the 'Groups' parent, start over with a v3, and take out the AI scorecard").

v3 is rebuilt ONE TAB AT A TIME from the v1 page, keeping v1's content (v2's flaw was missing content). Instead of copying
the 670 KB v1 template, it is generated from breadth/template.html with a few checked text swaps, so every fix to a v1
card reaches v3 the same day. Each swap must match exactly once or the build fails loudly (test_v3_page_builds).

Navigation: parent tabs (row 1) → sub-tabs (row 2, sticky). Only tabs listed in NAV exist on v3; add a tab here once it
has been rebuilt and Adam has approved it.
"""
import json

from . import config
from pathlib import Path

from .site import TEMPLATE, embed

THEMEDASH_JS = Path(__file__).with_name("v3_themedash.js")
ORACLE_JS = Path(__file__).with_name("v3_oracle.js")

# parent key, label, [(sub-tab key = v1 renderer key, label)]
NAV = [
    ("groups", "Groups", [("themes", "Themes"), ("themedash", "Theme Dash"), ("oracle", "Oracle")]),
]

NAV_JS = """const V3_NAV = %s;
const TABS = V3_NAV.flatMap(p => p[2]);
const TAB_ALIAS = { browse: "themes" };
const tabOf = (k) => TAB_ALIAS[k] || k;
const parentOf = (k) => (V3_NAV.find(p => p[2].some(s => s[0] === k)) || V3_NAV[0])[0];"""

NAV_RENDER = r"""  const ptabs = $(`<nav class="ptabs" role="tablist" aria-label="Sections">${V3_NAV.map(([k, l]) => `<button role="tab" data-p="${k}">${l}</button>`).join("")}</nav>`);
  app.append(ptabs);
  const tabs = $(`<nav class="tabs" role="tablist">${TABS.map(([k, l]) => `<button role="tab" data-tab="${k}">${l}</button>`).join("")}</nav>`);
  app.append(tabs);
  ptabs.querySelectorAll("button").forEach(b => b.addEventListener("click", () => {
    const P = V3_NAV.find(p => p[0] === b.dataset.p); const want = lsGet("v3sub-" + P[0], P[2][0][0]);
    const s = P[2].some(x => x[0] === want) ? want : P[2][0][0];
    tabs.querySelector(`button[data-tab="${s}"]`).click(); }));"""

NAV_SHOW = """    tabs.querySelectorAll("button").forEach(b => b.setAttribute("aria-selected", b.dataset.tab === TAB));
    const P = parentOf(TAB); lsSet("v3sub-" + P, TAB);
    ptabs.querySelectorAll("button").forEach(b => b.setAttribute("aria-selected", b.dataset.p === P));
    tabs.querySelectorAll("button").forEach(b => { b.hidden = parentOf(b.dataset.tab) !== P; });"""

CSS = """
/* v3 (Oct 30 2026): parent tabs → sub-tabs */
.ptabs { display: flex; gap: 6px; margin: 0 0 6px; overflow-x: auto; scrollbar-width: none; }
.ptabs::-webkit-scrollbar { display: none; }
.ptabs button { flex: none; background: none; border: 1px solid var(--border); border-radius: 999px; padding: 6px 16px; font: inherit;
  font-size: 14px; font-weight: 600; color: var(--text-secondary); cursor: pointer; }
.ptabs button[aria-selected="true"] { background: var(--text-primary); border-color: var(--text-primary); color: var(--surface-0); }
.v3tag { font-size: 11px; font-weight: 700; letter-spacing: .04em; padding: 2px 7px; border-radius: 999px; vertical-align: middle;
  border: 1px solid var(--border); color: var(--text-secondary); margin-left: 6px; }
.xopen.revflag { display: none; }
/* wider on desktop (Adam, Oct 30: "the entire thing looks narrow") */
.wrap { max-width: min(1760px, 96vw); }
/* light / dark switch */
.modesw { display: inline-flex; border: 1px solid var(--border); border-radius: 999px; overflow: hidden; }
.modesw button { background: none; border: 0; padding: 6px 12px; font: inherit; font-size: 13px; font-weight: 600; color: var(--text-secondary); cursor: pointer; }
.modesw button[aria-pressed="true"] { background: var(--text-primary); color: var(--surface-0); }
/* compact long / short side cards */
.pulse.p3 { margin-bottom: 12px; }
.pside3 { padding: 10px 14px; }
.pside3 .head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.pside3 .kicker { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; color: var(--text-muted); }
.pside3 .p3v { font-family: "JetBrains Mono", ui-monospace, monospace; font-size: 20px; font-weight: 800; }
.pside3 .p3v small { font-size: 12px; color: var(--text-muted); font-weight: 600; }
.pside3 .p3lbl { font-size: 13px; font-weight: 600; }
.pside3 .p3m { flex: 1 1 80px; min-width: 60px; margin: 0; height: 6px; }
.pside3 .p3spark { flex: none; }
.p3parts { display: flex; flex-wrap: wrap; gap: 4px 6px; margin-top: 8px; }
.p3chip { font-size: 12px; padding: 2px 8px; border-radius: 999px; border: 1px solid var(--border); color: var(--text-secondary); white-space: nowrap; cursor: help; }
.p3chip b { font-family: "JetBrains Mono", ui-monospace, monospace; margin-right: 3px; color: var(--text-primary); }
.p3chip.full { border-color: var(--good); } .p3chip.part { border-color: var(--warning); }
.p3chip .meta { margin-left: 3px; }
/* Theme Dash */
.tdhead { padding: 12px 14px; margin-bottom: 12px; }
.tdbar { display: flex; height: 26px; border-radius: 6px; overflow: hidden; font-size: 12.5px; font-weight: 600; }
.tdbar > div { display: flex; align-items: center; padding: 0 10px; white-space: nowrap; min-width: 90px; color: #fff; }
.tdbar .tdbh { background: var(--good); } .tdbar .tdbl { background: var(--critical); justify-content: flex-end; }
.tdbar b { margin-right: 4px; font-family: "JetBrains Mono", ui-monospace, monospace; }
.tdsub { margin: 6px 0 8px; }
.tdhead .filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.tdbody { display: grid; grid-template-columns: minmax(380px, 44%) 1fr; gap: 12px; align-items: start; }
.tdchart { position: sticky; top: 52px; padding: 10px; display: flex; flex-direction: column; height: calc(100vh - 70px); min-height: 420px; }
.tdch-h { display: flex; justify-content: space-between; gap: 8px; align-items: flex-start; margin-bottom: 8px; }
.tdch-t { font-size: 18px; } .tdch-b { display: flex; gap: 6px; flex: none; } .tdch-b .xopen { text-decoration: none; }
.tdtv { flex: 1; width: 100%; border: 0; border-radius: 8px; background: var(--surface-0); }
.tdcols { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.tdcol-h { font-weight: 700; font-size: 13.5px; padding: 0 0 6px; margin-bottom: 6px; border-bottom: 2px solid var(--border); }
.tdcol-h.hcol { border-color: var(--good); } .tdcol-h.lcol { border-color: var(--critical); }
.tdgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 8px 14px; }
.tdg { padding: 6px 0 8px; border-bottom: 1px solid var(--grid); }
.tdg-h { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; margin-bottom: 4px; }
.tdg-n { font-weight: 600; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tdg-h .meta { font-size: 11.5px; white-space: nowrap; }
.tdchips { display: flex; flex-wrap: wrap; gap: 4px; }
.tdchip { font: inherit; font-size: 12px; font-weight: 600; padding: 2px 7px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface-0);
  color: var(--text-primary); cursor: pointer; display: inline-flex; gap: 4px; align-items: baseline; }
.tdchip small { font-family: "JetBrains Mono", ui-monospace, monospace; font-size: 10.5px; font-weight: 500; color: var(--text-secondary); }
.tdchip.u1 { background: color-mix(in srgb, var(--good) 12%, var(--surface-0)); } .tdchip.u2 { background: color-mix(in srgb, var(--good) 28%, var(--surface-0)); }
.tdchip.d1 { background: color-mix(in srgb, var(--critical) 12%, var(--surface-0)); } .tdchip.d2 { background: color-mix(in srgb, var(--critical) 28%, var(--surface-0)); }
.tdchip:hover { border-color: var(--text-muted); } .tdchip.on { outline: 2px solid var(--s1); outline-offset: 1px; }
.tdnone { padding: 8px 0; }
@media (max-width: 520px) { .tdch-h { flex-wrap: wrap; } }
/* Oracle */
.orhead { padding: 12px 14px; margin-bottom: 12px; } .orhead h2 { font-size: 16px; margin: 0 0 8px; }
.orhead .filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; } .orsub, .orov { margin-top: 8px; }
.orgrid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 12px; }
.orchart { padding: 10px 12px; position: relative; }
.orch-h { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 6px; } .orch-h .meta { font-size: 11.5px; }
.orsvg { width: 100%; height: 260px; display: block; overflow: visible; }
.oraxis { position: absolute; left: 14px; right: 12px; top: 38px; height: 260px; pointer-events: none; }
.oraxis span { position: absolute; left: 0; transform: translateY(-50%); font-size: 10.5px; color: var(--text-muted); background: var(--surface-1); padding: 0 3px; border-radius: 3px; }
.orgridl { stroke: var(--grid); stroke-width: 1; vector-effect: non-scaling-stroke; }
.orzero { stroke: var(--text-muted); stroke-width: 1; stroke-dasharray: 2 3; vector-effect: non-scaling-stroke; }
.orl { fill: none; stroke-width: 1.4; opacity: .55; vector-effect: non-scaling-stroke; cursor: pointer; transition: opacity .12s; }
.orl.dim { opacity: .12; } .orl.on { opacity: 1; stroke-width: 3; }
.orspy { fill: none; stroke: var(--text-secondary); stroke-width: 1.6; stroke-dasharray: 5 4; vector-effect: non-scaling-stroke; pointer-events: none; }
.ormed { fill: none; stroke: var(--text-primary); stroke-width: 2.6; vector-effect: non-scaling-stroke; pointer-events: none; }
.orrank { display: flex; flex-wrap: wrap; gap: 4px 10px; margin-top: 8px; font-size: 12px; }
.orrank span { cursor: pointer; display: inline-flex; align-items: center; gap: 4px; padding: 1px 4px; border-radius: 4px; }
.orrank span.on, .ortable tr.on td { background: color-mix(in srgb, var(--s1) 14%, transparent); }
.orrank i, .orsw { display: inline-block; width: 10px; height: 3px; border-radius: 2px; vertical-align: middle; margin-right: 6px; }
.ortable .head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.ortable td.orsel { font-weight: 700; } .ortable tr[data-t] { cursor: pointer; } .orspyrow td { border-top: 2px solid var(--border); }
@media (max-width: 900px) { .orgrid { grid-template-columns: 1fr; } .orsvg, .oraxis { height: 200px; } }
@media (max-width: 900px) { .tdbody { grid-template-columns: 1fr; } .tdchart { position: static; height: 420px; min-height: 0; } .tdcols { grid-template-columns: 1fr; } }
@media (max-width: 520px) { .p3chip .meta { display: none; } .p3chip { font-size: 11.5px; padding: 1px 7px; } .pside3 .p3lbl { flex-basis: 100%; order: 5; } }
</style>"""

PULSE_V3 = r"""function pulseCard(T) {   // v3: compact long / short sides (Adam, Oct 30: "take up much less space heightwise")
  const P = T.pulse, H = T.pulse_hist || [];
  const side = (kind) => {
    const v = P[kind], label = P[kind + "_label"], parts = P[kind + "_parts"];
    const col = kind === "long" ? (v >= 6 ? "var(--good)" : v >= 4 ? "var(--warning)" : "var(--critical)")
                                : (v >= 6 ? "var(--critical)" : v >= 4 ? "var(--warning)" : "var(--text-muted)");
    const vals = H.map(h => h[kind]), w = 110, h = 24, n = Math.max(vals.length - 1, 1);
    const pts = vals.map((x, i) => `${(i / n * w).toFixed(1)},${(h - 2 - x / 10 * (h - 4)).toFixed(1)}`).join(" ");
    const spark = vals.length > 2 ? `<svg class="p3spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-label="${kind} score, last ${vals.length} days"><title>Last ${vals.length} trading days</title><polyline points="${pts}" fill="none" stroke="${col}" stroke-width="1.8"/></svg>` : "";
    const chip = (p) => `<span class="p3chip ${p.pts >= p.max ? "full" : p.pts > 0 ? "part" : ""}" title="${esc(p.value)} · ${esc(p.note)}"><b>${p.pts}/${p.max}</b>${esc(p.name)}<span class="meta">${esc(p.value)}</span></span>`;
    return `<div class="card pside3"><div class="head"><span class="kicker">${kind === "long" ? "Long side" : "Short side"}</span>
      <b class="p3v" style="color:${col}">${v}<small>/10</small></b><span class="p3lbl">${esc(label)}</span>
      <div class="meter p3m"><i style="width:${v * 10}%;background:${col}"></i></div>${spark}</div>
      <div class="p3parts">${parts.map(chip).join("")}</div></div>`;
  };
  return $(`<section class="pulse p3">${side("long")}${side("short")}</section>`);
}
function pulseCardV1(T) {"""

MODE_BTN_OLD = '<button class="xopen themebtn" title="Light / dark / follow the device">Theme: <span class="themelbl"></span></button>'
MODE_BTN_NEW = '<div class="modesw" role="group" aria-label="Light or dark mode"><button data-m="light">☀ Light</button><button data-m="dark">☾ Dark</button></div>'
MODE_JS_OLD = '  { const MODES = ["auto", "light", "dark"], lbl = app.querySelector(".themelbl");\n    const apply = (m) => { if (m === "auto") document.documentElement.removeAttribute("data-theme"); else document.documentElement.setAttribute("data-theme", m); lbl.textContent = m[0].toUpperCase() + m.slice(1); };\n    let m = lsGet("theme", "auto"); apply(m);\n    app.querySelector(".themebtn").addEventListener("click", () => { m = MODES[(MODES.indexOf(m) + 1) % 3]; lsSet("theme", m); apply(m); }); }'
MODE_JS_NEW = r"""  { const sw = app.querySelector(".modesw");   // v3: plain Light / Dark switch; first visit follows the device
    const apply = (m) => { document.documentElement.setAttribute("data-theme", m); sw.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", b.dataset.m === m)); };
    let m = lsGet("theme", "auto"); if (m !== "light" && m !== "dark") { try { m = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; } catch (e) { m = "light"; } }
    apply(m);
    sw.addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; lsSet("theme", b.dataset.m); apply(b.dataset.m); }); }"""

# (what v1 says, what v3 says instead, why)
SWAPS = [
    ('const TABS = [["readout", "Read-out"], ["breadth", "Breadth"], ["premarket", "Pre-market"], ["intraday", "Intraday"], ["themes", "Themes"],\n'
     '  ["rotation", "Rotation"], ["biotech", "Biotech"], ["setups", "Setups"], ["stocks", "Stocks"], ["stories", "Trade Stories"]];\n'
     'const TAB_ALIAS = { best: "setups", trades: "setups", launch: "setups", browse: "themes" };\n'
     'const tabOf = (k) => TAB_ALIAS[k] || k;',
     None, "v3 navigation (filled in by build)"),
    ('let TAB = "readout";', 'let TAB = TABS[0][0];', "default tab = first rebuilt tab"),
    ('  const tabs = $(`<nav class="tabs" role="tablist">${TABS.map(([k, l]) => `<button role="tab" data-tab="${k}">${l}</button>`).join("")}</nav>`);\n'
     '  app.append(tabs);', NAV_RENDER, "parent row + sub-tab row"),
    ('    tabs.querySelectorAll("button").forEach(b => b.setAttribute("aria-selected", b.dataset.tab === TAB));',
     NAV_SHOW, "highlight parent, show only its sub-tabs"),
    ('  app.append(aiScoreCard(getT()));\n', '', "AI scorecard removed from the Themes tab (Adam, Oct 30)"),
    ('<title>Market Monitor</title>', '<title>Market Monitor v3</title>', "title"),
    ('<div><h1>Market Monitor</h1>', '<div><h1>Market Monitor <span class="v3tag">v3</span></h1>', "header badge"),
    ('function pulseCard(T) {', PULSE_V3, "compact long / short cards (v1 version kept as pulseCardV1)"),
    (MODE_BTN_OLD, MODE_BTN_NEW, "Light / Dark switch in the header"),
    (MODE_JS_OLD, MODE_JS_NEW, "Light / Dark switch behaviour"),
    ('  const R = { themes: renderThemesTab,', '  const R = { themedash: renderThemeDash, oracle: renderOracle, themes: renderThemesTab,', "Theme Dash renderer"),
    ('function renderTab(panel) {', None, "Theme Dash code (v3_themedash.js) before renderTab"),
    ('</style>', CSS, "v3 styles (first </style> only)"),
]


def page(template_text):
    html = template_text
    for old, new, why in SWAPS:
        n = html.count(old)
        if old == "</style>":
            n = 1 if n >= 1 else 0
        if n != 1:
            raise ValueError(f"v3 build: expected the v1 template to contain this exactly once ({why}); found {n}")
        if new is None and old.startswith("function renderTab"):
            new = THEMEDASH_JS.read_text() + "\n" + ORACLE_JS.read_text() + "\n" + old
        elif new is None:
            new = NAV_JS % json.dumps([[k, l, [list(s) for s in subs]] for k, l, subs in NAV])
        html = html.replace(old, new, 1)
    return html


def build(data):
    out = config.DOCS_DIR / "v3"
    out.mkdir(parents=True, exist_ok=True)
    html = page(TEMPLATE.read_text()).replace("/*__DATA__*/null", embed(data), 1)
    (out / "index.html").write_text(html)
    return out / "index.html"
