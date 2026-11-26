---
id: R-2026-11-25-green-light-history
title: Green-light history: how long thrust windows last and what they paid
date: 2026-11-25
status: mixed        # works | doesnt | mixed | untested | process
kind: market             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 25 sessions
sample: Nov 2024 – Nov 24 2026, 533 sessions; 15 green periods (5 thrust-led, 10 ratio-only); 10 major thrust signals
result: thrust-led green periods lasted 29–76 sessions, SPY +13.5 / +8.1 / +4.4 / +0.5 / −6.9% (current, failing); ratio-only "strong" blips lasted 1–10 sessions and paid ~0; early tell: ratio10 ≥ 2 ten sessions after the signal in all 5 that worked, ≤ 1 in the 3 that failed (Oct 15 = 1.5, failed)
halves: 2025: 3 thrust periods, all up · 2026: 2 up (Nov–Mar flat for SPY, +4.7% IWM; Mar–May +13.5%), 1 failing
layers: []              # ids from data/layers.json this is evidence for (empty = new idea)
integrated: no          # yes | partly | no | rejected
source: chat (Adam: "when has the dashboard given the green light, how long did it last, what were the results"); tools/green_light_study/run.py
---
**Idea.** Know what a green light usually looks like: how long it lasts, what the index and the average stock do, and how to tell early
whether it is a real one.

**How it was tested.** Green = playbook state `thrust` (25 sessions after a major breadth thrust / follow-through, `metrics.thrust_window`)
or `strong` (ratio5 and ratio10 ≥ 1.5). Runs of green sessions, gaps of ≤ 3 non-green sessions merged. Returns from the first green close to
the last green close (SPY, QQQ, IWM, RSP, median $10+ stock), SPY max drawdown inside, SPY 20 sessions after. Early tell: SPY +5/+10/+25 and
ratio10 on day +10 for each major signal date. Uses only breadth.csv + bars; the state is known at each close (no look-ahead), but the
day-+10 tell was picked after looking at the 10 signals (in-sample).

**Result.**
| Period | Sessions | SPY | IWM | Median stock | SPY max DD |
|---|---|---|---|---|---|
| Apr 9 – May 20, 2025 | 29 | +8.1% | +10.2% | +8.8% | −6.3% |
| Aug 12 – Oct 9, 2025 | 42 | +4.4% | +8.1% | +0.9% | −1.5% |
| Nov 21, 2025 – Mar 13, 2026 | 76 | +0.5% | +4.7% | +1.7% | −4.8% |
| Mar 31 – May 12, 2026 | 30 | +13.5% | +13.9% | +4.1% | −0.9% |
| Oct 15 – Nov 24, 2026 (open) | 29 | −6.9% | −2.9% | −1.9% | −10.8% |

Ratio-only "strong" blips (10 of them): median 5 sessions, SPY −0.4% to +2.2%, no follow-through. Setup edge by state
(trade_bt, avg R per trade): Rotation Rookie +0.36R in thrust, Round Number +0.26R, VCP +0.23R, Leader Pullback +0.21R, ATH +0.10R;
Pullback +0.55R and ATH +0.25R in strong. SPY next-20 avg: thrust +1.85% (60% up), strong +0.35%, mixed +0.23%, weak +0.93%.
Day-10 tell: ratio10 at +10 sessions = 2.38 / 3.09 / 2.26 / 2.79 / 2.32 for the 5 that worked; 0.74 / 0.92 / 0.62 for the 3 that failed;
1.67 (Jan 5, 2026, flat) and 1.50 (Oct 15, 2026, failed) in between.

**Caveats.** Two years, 5 real green periods, 10 signals: anecdotes, not statistics. The day-10 tell is in-sample. Thrust windows
re-trigger (Nov 2025 ran 76 sessions on three signals), so period length depends on the merge rule.

**How it could be used.** A "how this thrust is going" line on the Post-thrust board: day N of 25, ratio10 vs the ≥ 2 / ≤ 1 tell, and the
past periods table. Re-test the tell on each new signal before letting it change size.
