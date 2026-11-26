---
id: R-2026-11-25-failed-pop-shorts
title: Failed-pop shorts in downtrends: worked only in the current pullback
date: 2026-11-25
status: doesnt        # works | doesnt | mixed | untested | process
kind: setup
horizon: 5 sessions
sample: Mar 2025 – Nov 2026, 1,960 trades (failed-pop, 5-day hold) on 330 entry dates; variants: 10-day hold, blind (no failure wait)
result: +0.18R (t 6.1) overall, but ALL of it from the Oct–Nov 2026 pullback (+0.99R, 365 trades; one week, Nov 9–15, gave 177 trades at +1.55R); excluding it −0.01R; earlier pullbacks +0.14 / +0.49 / −0.05R; weighting each entry day equally +0.01R (t 0.2); 10-day hold −0.08R; blind short of the pop +0.01R
halves: −0.05R / +0.41R
layers: []
integrated: no
source: chat (Adam: "run the studies"); tools/short_study/run.py
---
**Idea.** Short liquid stocks in a downtrend that pop 10%+ in 3 sessions and then fail (close below the pop day's low within 3 sessions).
Then find when shorts get a green light.

**How it was tested.** $5+, $20M+/day, close below a falling 50 SMA before the pop. Short the failure close; stop = the pop's highest high
(skip if risk > 2 ADR, floor 0.3 ADR); exit at the stop or the close after 5 / 10 sessions. One trade per ticker at a time. Split by playbook
state, weak breadth, SPY below its 21 EMA, the day-10 thrust tell, broken sub-theme (63-day median < 0), and the 4 SPY 5%+ pullbacks.
Split-adjusted bars.

**Result.** It looks good on paper only because of the last two months, and mostly one crash week. Outside the current pullback it is
flat (−0.01R) with every filter. SPY below its 21 EMA helped only inside the current pullback. Holding 10 days turns it negative, so whatever
works is fast. No market condition switched on a short edge in the three earlier pullbacks.

**Caveats.** Trades bunch on the same days, so the plain t-stat overstates the edge (equal weight per day: t 0.2). Borrow costs and
hard-to-borrow names are ignored, which flatters shorts. Survivorship: delisted names are missing.

**How it could be used.** Not as a setup. Keep the script; re-test after the next pullback. A short green light would need a short
setup with an edge first — next candidates: breakdowns of former leaders (RS was 90+), and shorts timed off a downside breadth thrust.
