---
id: R-2026-11-04-daily-vs-weekly-dips
title: Daily vs weekly EMA dips after a run into overhead supply (trade warehouse step 1)
date: 2026-11-04
status: doesnt          # works | doesnt | mixed | untested | process
kind: setup             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: Adam's management (half at day 4, break-even, trail 10 EMA, cap 40)
sample: 2,075 leader pullback episodes (RS 80+, $10+, $20M+/day, daily + weekly uptrend at the leg high), starts Sep 5 2025 – Jul 6 2026; cell (hit old supply + top-third extension) 110 episodes, 84 informative, 42 per half, 4 market groups
result: H1 (waiting for the weekly dip beats the daily dip after a stretched run into old supply) — effect −0.027R (cluster t −0.21, perm p 0.61, bootstrap [−0.10, +0.11]); in the cell BOTH entries lost (D −0.19R / W −0.32R a trade). Label: doesn't work (pre-registered).
halves: effect −0.23 / +0.17R (disagree); negative under every extension cut-off tried (−0.02 to −0.15R)
layers: [lifecycle, polished]
integrated: no          # yes | partly | no | rejected
source: chat Nov 4, 2026 (Adam's VEEV weekly chart: "trade the pullback into the daily EMAs or the weekly EMAs, and when to do either?"); tools/warehouse/PLAN.md v3.1 (graded 55% → 78% → 85% by an independent reviewer before building), build.py, study.py, results.txt; independent recompute 60/60 trades match
---
**Idea.** After a leader runs hard into old overhead supply (VEEV into its 2020–21 peaks), skip the daily 9/21 dip and wait for the weekly
9/21 dip, because supply needs time to work off.

**How it was tested.** Pre-registered plan, graded by an independent reviewer before any outcome was computed. Unit = the pullback episode
(leg high → new high / weekly-21 break / 40 sessions); three policies scored on every episode (buy the first daily dip, wait for the weekly
dip, daily then weekly re-entry), missed trades = 0R. Same trigger (break of the dip-day high within 3 sessions), stop (dip-day low ≤ 1 ADR)
and Adam's management for both. Supply = point-in-time old peaks (Yahoo monthly bars, all neighbours complete before the month; daily swing
highs before the current leg); extension = leg-high distance over the weekly 21 EMA in weekly ranges. Power gate checked before outcomes.

**Result.** H1 fails: waiting for the weekly dip was not better in the VEEV-type cell (−0.03R, both entries negative there). Exploratory,
NOT proven (each a lead for a pre-registered follow-up):
- Extension at the leg high is the strongest thing seen: top third (≥ 2.5 weekly ranges over the weekly 21) → daily dips −0.10R, weekly
  dips −0.27R a trade; the rest +0.05R / +0.06R.
- Little room to the next old peak (< 5% above the leg high): daily dips −0.25R a trade vs weekly dips +0.15R (≈ 110 / 75 trades) — Adam's
  instinct, but on `room`, not on the pre-registered hit-supply rule.
- Market state: strong breadth +0.10R (D) / +0.16R (W) a trade; post-thrust daily dips +0.14R.
- Plain dips overall ≈ 0R (D +0.00R, W −0.03R a trade): the edge is in context, not the dip.
- Exit: a fixed 20-session hold made more than Adam's management on daily dips (+0.08R vs +0.00R per episode) — the 10-EMA trail after day 4
  may cut winners.

**Caveats.** ~10 months of starts, 4 market pullback groups; survivorship; today's theme lists; 320 of 1,241 tickers' Yahoo history
disagreed > 2% with our bars and only had daily-swing supply; monthly peaks approximate supply (no volume-at-price); no costs.

**How it could be used.** Don't build a "wait for the weekly" rule. Candidates for the scorecard's next pre-registered tests: extension
at the leg high as a penalty, room-to-supply, breadth state, and exit choice (10-EMA trail vs fixed hold). Re-run ≈ May 2027.
