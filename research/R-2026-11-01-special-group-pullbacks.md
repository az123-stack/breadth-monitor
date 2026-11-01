---
id: R-2026-11-01-special-group-pullbacks
title: Special groups (top Strength + big 5-day jump): chase or wait for the 8 / 21 EMA?
date: 2026-11-01
status: mixed           # works | doesnt | mixed | untested | process
kind: setup             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 5 / 20 sessions (R trade: next open, stop 1 ADR, 20 sessions)
sample: Mar 26, 2025 – Oct 30, 2026; RS 85+ members, $5+, $20M+/day; special 617 stock signals (131 dates, 56 groups), strong-steady 2,420, ordinary 2,932; 6 post-thrust windows
result: "special" adds nothing over plain strong groups (21-EMA pullback post-thrust +0.48R both, special t 1.8 / steady t 4.1); 21-EMA pullback beat chasing the same stock +0.37R (t 2.6) outside / +0.60R (t 2.5) inside thrust windows, both halves; 8-EMA entry no better than chasing (−0.05 to −0.27R); outside thrust windows special groups lost vs all stocks over 20d (chase −0.9 pts, 21 EMA −1.4 pts)
halves: 21 EMA minus chase (special) +0.55 / +0.19R outside, +0.86 / +0.29R post-thrust; strong-steady 21-EMA post-thrust +0.48 / +0.48R
layers: [theme_strength, emaprob, polished, oracle_accel]
integrated: no          # yes | partly | no | rejected
source: chat Nov 1, 2026 (Adam: Immunology & Inflammation and Defense IT look special but extended — buy them on a pullback this week); tools/special_pullback/study.py + analyze.py
---
**Idea.** A sub-theme already top-tier on Theme Strength that also jumped a lot in 5 sessions (Immunology & Inflammation 66 → 89,
Defense IT 78 → 92 on Oct 30) is "doing something special". Its leaders are extended on the day it shows up. Wait for a pullback to
the 8 or 21 EMA within 10 sessions instead of chasing.

**How it was tested.** Dashboard Strength recomputed for every session with `strength.group_inputs_many` / `strength_scores`
(matches the live page: 88.8 / 91.7 / 92.8 on Oct 30). Special = Strength ≥ 85 and +15 or more over 5 sessions; strong-steady =
≥ 85 and < +5; ordinary = 50–75. First fire per group per 10 sessions. Stocks = members with RS ≥ 85, $5+, $20M+/day on the signal
day. Chase = buy next open. Pullback = first session in the next 10 whose low comes within 0.25 ADR of the EMA with the close no more
than 0.5 ADR under it; buy next open. Outcome = 5/20-session return minus the average tradeable stock, and R (stop 1 ADR under
entry, else close after 20 sessions, cap 10). Per-date t-stats; halves split at the median signal date. R recomputed independently
from raw bars on 150 random trades (exact match).

**Result.**
| Group / entry | All R | Post-thrust R | Not post-thrust R | 20d vs all stocks (post / not) |
|---|---|---|---|---|
| Special, chase | +0.34 | +0.75 (t 2.6) | +0.12 | +8.0 / −0.9 pts |
| Special, 8 EMA | +0.20 | +0.41 | +0.09 | +5.4 / −0.6 |
| Special, 21 EMA | +0.20 | +0.48 (t 1.8) | +0.06 | +5.7 / −1.4 |
| Strong-steady, 21 EMA | +0.27 | +0.48 (t 4.1, halves +0.48/+0.48) | +0.14 | +6.8 / +0.7 |
| Ordinary, 21 EMA | +0.14 | +0.29 | +0.02 | +2.8 / −0.5 |

Paired, same stock (only stocks that reached the EMA): 21 EMA minus chase — special +0.37R outside (t 2.6) / +0.60R post-thrust
(t 2.5), strong-steady +0.50R (t 4.7) / +0.42R (t 2.8); 8 EMA minus chase ≈ 0 to −0.27R everywhere. How often the pullback comes
(special): 8 EMA touched cleanly 91% within 10 sessions; 21 EMA 60% clean, 10% broke through, 29% never came.

**Read.** The "special" acceleration is not the edge (same as R-2026-10-31-accelerating-groups): plain strong groups do as well. The edge is
the post-thrust window. Inside it, buy strong-group leaders either at the signal or at the 21 EMA; if a leader comes back to its 21
EMA, that is a much better price than having chased it. The 8 EMA is not a better entry than chasing. Outside thrust windows strong /
special groups' leaders did not beat the average stock — pullback or not.

**Caveats.** ~19 months, 6 thrust windows, bull-heavy, survivorship, no costs, today's sub-theme lists. Paired "21 EMA beat chase" is
conditional on the pullback happening (selection: stocks that dipped were by definition the weaker chases), so it says where to buy
IF it comes back, not that waiting is better than buying. The Oct 15, 2026 thrust was the weakest on record and unconfirmed.

**How it could be used.** A watch row on the Best Setups / EMA touch cards: strong-group (Strength ≥ 85) RS 85+ leaders inside a
post-thrust window, alert on the first 21-EMA touch. Information only until the forward log proves it.
