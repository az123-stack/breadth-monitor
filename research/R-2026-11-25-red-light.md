---
id: R-2026-11-25-red-light
title: Red light for longs: which warning steps you aside early without costing return
date: 2026-11-25
status: mixed        # works | doesnt | mixed | untested | process
kind: market
horizon: 10 sessions
sample: Mar 3 2025 – Nov 17 2026, 432 sessions; 12 warnings; 4 SPY 5%+ pullbacks
result: ratio10 < 1 ("weak") as a step-aside rule = SPY 26.9% vs 25.1% buy & hold, max DD −8.6% vs −14.8%, out 33% of days, fired 0–6 sessions after all 4 peaks; credit (HYG/IEI) below its 20-day avg = 25.0%, max DD −6.0%, out 42%; VIX > 22 / VIX spikes / 10:1 down days / half the leaders below the 21 EMA come LATE (SPY next 10 +2.4% after VIX > 22): bottom signals, not red lights; thrust failing = SPY next 10 −1.38% (5 fires, in-sample)
halves: not split (only 4 pullbacks); each pullback reported on its own in the script output
layers: [red_light]
integrated: partly
source: chat (Adam: "run the studies"); tools/redlight_study/run.py
---
**Idea.** Find the warning that gets longs out early in a pullback without throwing away the good periods.

**How it was tested.** 12 daily on/off flags known at the close (breadth ratios, 10:1 down days, new lows vs highs, SPY vs its 21 EMA and
50 SMA, VIX, HYG/IEI credit, share of leaders below the 21 EMA, the day-10 thrust tell, a 2-of-3 combo). Scored on SPY next 10 sessions, a
momentum-long proxy (median next-5 return of the top 10% by 63-day return, $10+, $20M+/day, above the 21 EMA), "long SPY only when the flag
is off" (return and max drawdown), and the first fire after each of the 4 pullback peaks.

**Result.** Two rules cut the drawdown roughly in half without costing return: weak breadth (ratio10 < 1) and credit below its 20-day
average. Both fired within 0–6 sessions of every peak. The fear gauges (VIX, 10:1 down days, leaders breaking) fire near the lows and are
followed by gains, so they are the wrong tool for a red light. The leader proxy did NOT do worse when breadth was weak (+0.09% vs −0.01%),
so for momentum longs, weak breadth is a size-down rule, not a stop-trading rule.

**Caveats.** About 21 months and 4 pullbacks, with every rule chosen after looking at them. SPY stands in for "longs"; the per-setup R
by state already lives in trade_bt (the playbook).

**How it could be used.** A "Red light" line in What to trade: weak breadth + credit below the 20-day average = half size, no new index
longs. VIX > 22 shown as "fear high: watch for the bottom", not as a warning.
