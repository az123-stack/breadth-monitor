---
id: R-2026-10-28-old-pivots
title: Old pivots: touch-and-reject / pop-and-fail at big historical levels
date: 2026-10-28
status: mixed           # works | doesnt | mixed | untested | process
kind: setup             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 5 / 21 sessions
sample: 1,305 first returns to a big old pivot, 923 stocks, 339 dates (2025-03-19 to 2026-10-26); 919 pops through; 463 second attempts
result: Pops through old pivots fall back under in 10d 62% vs 64% for matched ordinary breakouts (no extra failure); touch → 2-ADR sell-off in 5d 16% vs 19% matched; 21d vs matched -1.0% (t -1.0). Pockets: old broken support -3.3% (t -1.9), run-up >50% in 21d -7.0% (t -1.7)
halves: overall 21d -0.26 / -1.80%; broken support -3.59 / -3.09%; run-up >50% -4.19 / -9.75%; heavy-volume pops fail less (48% vs 54%, t -2.4)
layers: []              # ids from data/layers.json this is evidence for (empty = new idea)
integrated: no          # yes | partly | no | rejected
source: chat Oct 28 2026 (Adam: CDNA into ~72.5, FRSH through 13.41); tools/pivot_study/
---
**Idea.** Adam noticed that when price reaches a big historical pivot (an old high or old breakdown level), it either touches
it and sells off, or pops through and then sells off. His guess: a liquidity / trapped-holders effect. Examples: CDNA rallying
into its 2025 breakdown area (~$72.5), FRSH breaking over its Dec 2025 pivot (~13.4).

**How it was tested.** Daily bars ~Oct 2024–Oct 2026, split-adjusted; common stocks, $5+, $20M+/day 50-day dollar volume.
Big old pivot = a swing high (highest high within ±30 sessions, "peak") or swing low ("floor", old support) that price later
traded 25%+ below, at least 60 sessions old. Event = the first day the high comes back within 1% of the level after 10 closes
under 97% of it (first return only; one event per stock per 20 sessions). Entry next open; 5 / 21 / 63-session returns.
Controls on the same dates: (a) clear-skies 20-day-high breakouts within 3% of their own 2-year high; (b) the main yardstick,
matched rally days = stocks making a 20-day high on the same date in the same run-up bucket (21-day return <20 / 20–50 / >50%)
and touch-day volume bucket (<1x / 1–2x / >2x the 50-day average). Date-paired differences, t over dates, both halves.
"Sell-off" = low reaches 2 ADRs under the touch-day close within 5 sessions. "Pop and fail" = first close above the level within
10 sessions of the touch, then a close back under it within the next 10 (control: close back under its prior 20-day high).
Independent recompute from raw parquet: pop fall-back 61.4% (929) vs 61.8%; touch 21d mean +0.41% vs +0.40%.

**Result.**
- The pattern is real but not special to old pivots: 62% of pops through an old pivot close back under within 10 sessions, but
  so do 64% of ordinary breakouts with the same run-up and volume. Old pivots don't fail more.
- Touch-and-sell-off: a 2-ADR drop within 5 sessions after the touch happened 16% of the time vs 19% for matched rally days.
  Touches after a slow approach (run-up <20%) actually sold off LESS (13.6% vs 20.3%, t -3.9, both halves).
- Forward returns vs matched rallies: 5d +0.02% (t 0.0), 21d -1.0% (t -1.0, halves -0.3 / -1.8). Raw vs clear-skies breakouts it
  looked worse (21d -1.6%, t -1.7), but most of that was the run-up, not the level.
- Liquidity guess: not supported. Heavy-volume (>2x) pops through an old pivot failed LESS often (48% vs 54%, t -2.4); quiet
  (<1x volume) approaches did best at 21d (+2.9% vs matched, t 1.6). Big volume at the level reads as absorption, not exhaustion.
- Second attempts after a failed first touch (FRSH-style): no edge (21d +0.4% vs matched, t 0.4; 70% vs 68% fall back).
- Pockets worth watching (t < 2, both halves agree):
  - Old broken SUPPORT (floor) levels: 21d -3.3% vs matched (t -1.9, halves -3.6 / -3.1, 152 dates). Former support acting
    as resistance is the stickier kind of level. CDNA's ~72.5 area is this type (a breakdown level).
  - Run-up >50% in 21 days into the pivot: 21d -11.0% vs matched -6.1% (extra -7.0%, t -1.7, 87 dates), but the names are
    mostly microcap pumps (SMX, STI, SPHL, INKT...), and parabolic runs fall back with or without a pivot.

**Caveats.** ~2 years of mostly bull market; pivots older than the data (pre-Oct 2024) can't be seen, so "big historical"
means up to ~1.5 years. Gap edges (like CDNA's exact ~72.5 breakdown gap) aren't swing points and weren't tested. Survivors
only, no costs. Fall-back rates depend on the 10-session window; the controls use the same window.

**How it could be used.** Don't treat an old pivot as a reason to skip a breakout: it behaves like any breakout (the normal
low-of-day stop and 3–5 day trim handle the ~60% that fall back). Information only, if anything: a small "old broken support
overhead" flag on setups whose next 5% up contains a former floor, and a caution when a stock arrives after a 50%+ month.
Re-test when a longer history (5 years incl. 2022) is available.
