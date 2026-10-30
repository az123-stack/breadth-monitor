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
from .site import TEMPLATE, embed

# parent key, label, [(sub-tab key = v1 renderer key, label)]
NAV = [
    ("groups", "Groups", [("themes", "Themes")]),
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
</style>"""

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
        if new is None:
            new = NAV_JS % json.dumps([[k, l, [list(s) for s in subs]] for k, l, subs in NAV])
        html = html.replace(old, new, 1)
    return html


def build(data):
    out = config.DOCS_DIR / "v3"
    out.mkdir(parents=True, exist_ok=True)
    html = page(TEMPLATE.read_text()).replace("/*__DATA__*/null", embed(data), 1)
    (out / "index.html").write_text(html)
    return out / "index.html"
