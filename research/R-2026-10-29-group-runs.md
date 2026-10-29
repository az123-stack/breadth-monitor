---
id: R-2026-10-29-group-runs
title: Groups running together: follow-through of sub-themes that close up big together
date: 2026-10-29
status: works           # works | doesnt | mixed | untested | process
kind: group             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 1 / 5 / 10 sessions
sample: 48,126 sub-theme days, 115 sub-themes, 440 days (~Jan 2025–Oct 2026); running rule 560 signals on 226 days (~6/week); strong 238 on 144 days
result: Running (75%+ up, avg 1.25+ ADRs, +3 pts vs SPY, 1.2x volume) beat the avg group next day open→close +0.34% (t 2.25) and 5d +0.90% (t 2.47); strong (1.5+ ADRs on 1.5x) +0.62% (t 2.64) / +1.47% (t 2.58); win rate ~50% (a few big continuations)
halves: running next day +0.12 / +0.55%, 5d +1.13 / +0.68%; strong next day +0.46 / +0.78%, 5d +1.40 / +1.54%
layers: [runners]       # ids from data/layers.json this is evidence for (empty = new idea)
integrated: yes         # yes | partly | no | rejected
source: chat Oct 28–29 2026 (Adam: "AI drug discovery all ran together, I'd have liked an alert"); tools/runner_study/hist.py
---
**Idea.** When a whole sub-theme runs hard together intraday (AI Drug Discovery on Oct 28: DNA, SDGR, ABSI, RXRX, ABCL all up 6–18%),
Adam wants an alert so he can day-trade it. Question for the daily data: do such group runs keep going?

**How it was tested.** Daily bars ~2 years, split-adjusted; every sub-theme day with 4+ liquid members ($3+, $10M+/day 50-day).
Checks at the close: share of members up; average move in ADRs (each stock's move ÷ its own 20-day ADR, ADR known before the day);
average move minus SPY; dollar volume ÷ 50-day average. Forward: equal-weight group bought at the NEXT open, held 1 (open→close),
5 and 10 sessions, vs the average sub-theme on the same dates (date-paired, t over dates, both halves). Calibration: avg 1.0 ADR is
the top ~5% of group days, 1.25 the top ~2.5%, 1.5 the top ~1%. Oct 28 AI Drug Discovery read 5/5 up, +12%, 1.27 ADRs, 1.42x volume.

**Result.** (vs the average group, same dates)
| Rule | Signals / week | Next day open→close | 5 days | 10 days |
|---|---|---|---|---|
| 1.0 ADR, 1.2x vol | 9.6 | +0.12% (t 0.9) | +0.31% (t 1.0) | +1.03% (t 2.1) |
| **1.25 ADR, 1.2x vol (alert)** | 6.4 | **+0.34% (t 2.25)** | **+0.90% (t 2.47)** | +1.19% (t 2.19) |
| **1.5 ADR, 1.5x vol (strong)** | 2.7 | **+0.62% (t 2.64)** | **+1.47% (t 2.58)** | +1.46% (t 1.95) |
Bigger runs on bigger volume follow through more. Win rate stays ~50%: the edge comes from a minority of big continuations.

**Caveats.** Daily closes only: the live alert fires intraday at the same thresholds (volume paced by the intraday profile), so
intraday triggers are earlier and noisier than this test; same-day continuation after an intraday trigger is NOT tested. Every
alert is logged (data/runner_log.csv) for a forward test. Today's sub-theme lists (mild hindsight); ~2 bull-heavy years; no costs.

**How it could be used.** Built Oct 29 (information only, never re-ranks the picks): breadth/runners.py → 5-minute alert job
(breadth/lineup.py, ntfy + hourly summary task) and the Intraday tab "Runners" card above "Who's moving the index". Names to trade =
members up 0.75+ ADR and above today's open, best RS first. Next test once ~4 weeks of the log exist: from the alert time to the
close and next day, alert names vs the rest of the group.
