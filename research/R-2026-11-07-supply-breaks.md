---
id: R-2026-11-07-supply-breaks
title: Supply breaks: what happens after a stock closes above significant overhead supply, and how fast it works it off
date: 2026-11-07
status: mixed           # works | doesnt | mixed | untested | process
kind: setup             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 20 sessions (trades); 5 / 21 / 63 sessions (excess returns)
sample: 2,420 breaks, 404 dates, Jan 2025 – Nov 2026 ($5+, $20M+/day stocks); 2,088 with 63 sessions observed
result: base rate no edge (hold-the-line buy +0.17R, halves +0.44 / −0.11). In top-20% groups: hold-the-line buy +0.48R (t 2.3, n 509, 278 dates), 21d +3.2% vs matched breakouts (t 4.3), 63d +13%; thrust + top group +0.80R (t 2.1). Bottom-half groups −0.27R (t −2.2). Timing: clears happen fast (median 4 sessions, 90% within 13)
halves: top group R +0.72 / +0.26, 21d excess +3.5% / +2.8%; bottom-half group R −0.22 / −0.35
layers: []              # ids from data/layers.json this is evidence for (empty = new idea)
integrated: no          # yes | partly | no | rejected
source: chat Nov 7, 2026 (Adam: "a system for what happens when a stock takes out significant overhead supply and how quickly it works it off"); tools/supply_study/
---
**Idea.** Adam noticed his long candidates (TREX, BBY, MAS, MANH, CRL, PHM) had all just taken out big overhead supply and were "working it
off". Question: what normally happens next, how fast, and what tells the good ones apart.

**How it was tested.** `tools/supply_study/study.py` then `analyze.py`. Supply = (a) ±30-session swing high in our bars, 60+ sessions old,
that price later traded 25%+ under; (b) old swing low that broke 25%+ (support turned supply); (c) multi-year monthly peak / ATH from
data/levels.json that the stock traded 25%+ under. Event = first CLOSE above after 20+ closes under; highest level per stock per day, one
event per stock per 20 sessions. Phases: retest = low within 0.25 ADR of the level; fail = close 0.5 ADR under; clear ("worked off") =
close 2 ADR above with no fail first. Trades enter at the next open: breakout buy, and a hold-the-line buy after the first retest that
closed above the fail line; stop 0.5 ADR under the level (risk floor 0.3 ADR), 20 sessions. Excess returns vs same-date stocks making an
ordinary 60-day closing high in the same $-volume bucket. Group = sub-theme 60-day return percentile (today's lists).

**Result.**
- Base rates: almost every break retests within days (87% within 10 sessions). 62% close 0.5 ADR back under within 21 sessions (median 6
  days), but that line is noise: 53% of those later cleared (63% in top groups). A real failure = 3 closes under AND 1 ADR below: 46%
  within 21 sessions; those lagged −9.2% vs +8.6% for breaks that held (21d excess).
- Speed: work-off is fast or not at all. 46% clear within 63 sessions; median 4 sessions, 75% within 9, 90% within 13. A break still
  undecided after 10 sessions clears later only ~54% (59% in top groups); after 15 sessions top-group names still clear 64%.
- What matters: GROUP. Top-20% groups +0.48R / +3.2% at 21d / +13% at 63d (both halves); bottom-half groups −0.27R; stocks outside our
  themes −2.3% at 21d (t −3.4). Thrust window helps (+0.35R hold-the-line, but halves +0.65 / −0.06); thrust + top group +0.80R.
- Also: gapped through the level +0.54R (halves +0.71 / +0.35); quiet breaks (< 1.5× volume) +1.2% at 21d (both halves) while 3×+ volume
  breaks lagged −2.7% (both halves) even though they failed less; closing 1.5+ ADR above the level cleared 85% but lagged −3.2% at 21d.
  Multi-year levels +1.2% at 21d (t 2.3, both halves) — slightly better than recent swing highs. RS top 20% alone added nothing (same as
  every earlier study). Breakout buy (next open) no edge in any cut that held both halves.

**Caveats.** ~2 years, bull-heavy; 404 dates but overlapping windows; survivorship (delisted names missing); no costs; today's theme lists;
levels.json only covers ~1,100 tickers; the retest definition is loose (most breaks touch within a day, so "hold-the-line buy" ≈ buy day
2–3 if still above the line).

**How it could be used.** A "Supply breaks" card: live breaks in the last ~15 sessions, phase (retesting / working off / cleared / real
fail), sessions since the break vs the 13-session clock, group percentile, and the grade (top group + thrust = best; bottom-half group =
skip). Stop = the real-fail rule (3 closes under and 1 ADR below), not a 0.5-ADR wiggle. Information only until Adam approves.
