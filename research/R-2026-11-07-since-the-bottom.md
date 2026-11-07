---
id: R-2026-11-07-since-the-bottom
title: Since the bottom: themes and leaders emerging from an anchor close
date: 2026-11-07
status: untested        # works | doesnt | mixed | untested | process
kind: group             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: open (counts sessions since the anchor)
sample: built Nov 7, 2026; default anchor = the Nov 5, 2026 close (Nov 6 the first session counted); 1 session so far
result: descriptive view only, nothing tested. Nov 6 (1 session): SPY +0.3%, QQQ +1.4%, IWM +1.0%; 53% of 1,065 theme stocks up; top by score Life Science Tools, Oncology / Mid-cap Biotech, China Internet
halves: n/a
layers: []              # ids from data/layers.json this is evidence for (empty = new idea)
integrated: yes         # built as v3 Groups → Since the bottom (info only)
source: chat Nov 7, 2026 (Adam); breadth/emerge.py + renderEmerge in breadth/v3_tabs.js
---
**Idea.** Adam: anchor to a bottom and watch which themes and leaders emerge after it, "using money flow, EMAs etc." A bottom can't be
called, so the anchor is a picker (any of the last 25 closes; default `config.EMERGE_START` = first session counted).

**How it was built.** Python ships compact arrays (closes 45 sessions, $ volume + 50-day base 25 sessions, EMA 9/21/50 seeds, 3-month
closing-high seed) for liquid theme / sub-theme stocks ($5+, $5M+/day, ETFs and deals out); the page computes everything from the chosen
base close, plus live Google prices. Group columns: since / vs SPY, % up, % above 21 EMA (and change since the base), % above 50, up-volume
dollar share, $ volume × normal, new 3-month closing highs, drop into the bottom (from the 20-day closing high) and share won back.
Emergence score 0–100 = rank percentile across groups: 35% vs SPY, 20% up-$ share, 15% % up, 15% % above 21 EMA, 15% new-high share;
groups under 8 stocks shrunk toward 50. Day-by-day table: top 6 / bottom 3 sub-themes each session vs SPY.

**Result.** Not tested. Weights are a guess, not tuned.

**Caveats.** Related evidence: after thrusts plain RS top 30 lagged (connector study) while high-beta RS 80+ names paid only after deep
washouts (SPY −8%+, T2108 ≤ 25); the Oct–Nov 2026 pullback was shallower than that. Theme lists are today's.

**How it could be used.** Test later: after each dashboard thrust, do the top-score groups 5 sessions in beat the average group over the
next 21 / 63 sessions, and do "first to a new 3-month high" stocks beat RS 90+ stocks? If yes, move from info to tested in layers.json.
