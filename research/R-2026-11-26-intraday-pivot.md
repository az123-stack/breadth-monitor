---
id: R-2026-11-26-intraday-pivot
title: 15-min / 30-min pivot entries (shakeout under a level, reclaim, buy the pivot break) vs daily entries
date: 2026-11-26
status: doesnt          # works | doesnt | mixed | untested | process
kind: setup
horizon: 5 sessions and 10 EMA trail (max 30)
sample: Mar 2025 - Oct 2026, 682 liquid sub-theme stocks A-PBR (orb-data 15-min bars), uptrend top-30% 63d stocks undercutting the prior-day low (12,788 setups) or the 21 EMA (7,128), 403 dates
result: Per setup at equal risk (misses = 0R), pivots = the plain daily touch: prior-day-low level P30 -0.01R vs touch (t -0.1), P15 +0.01R (t 0.1); 21 EMA level P30 -0.02R (t -1.1), P15 +0.01R (t 0.3); halves disagree. Pivots trigger on 56-65% (15-min) / 48-56% (30-min) of setups, stop ~0.4-0.5 ADR vs 1 ADR, R/trade higher (P15 +0.12 vs touch +0.08 trail) but ~70% stopped within 5 days vs 47%, trail win rate 22-25% vs 35%. Pivot entry with a 1 ADR stop (confirmation only) also no better (-0.03 to +0.01R/setup). Post-thrust windows best for every entry (touch +0.24R, P15 +0.32R/setup, paired +0.14R t 1.1); strong / mixed / weak breadth ~0 or negative for all.
halves: P15 vs touch (pdl) +0.02 / -0.01; P30 +0.02 / -0.03; e21 P15 +0.06 / -0.05
layers: [rs_fire, dips]
integrated: no
source: chat Nov 26 2026 (Adam, @1ChartMaster: "a shakeout into a 30-min pivot on tight risk right before a stock goes on an insane run"; asked for 15 and 30 min); tools/pivot30_study/study.py (trades.csv)
---
**Idea.** A good daily setup shakes out under an obvious level intraday, a 15/30-min bar closes back above it (the pivot), and you buy the
break of that bar's high with a stop at the day's low: same trade, much tighter risk, so the runners pay many R.

**How it was tested.** Daily context from the main bars at the prior close (no look-ahead): $10+, $20M+/day, close > 50 EMA, 21 > 50 EMA,
top 30% on 63-day return; flags leading group, RS fire 1-3, breadth state. Setup day = the day's low undercuts the prior-day low or the
prior day's 21 EMA. Entries on the same setups: D_touch (buy at the level, 1 ADR stop), D_close (buy the close if back above, stop day low),
P15/P30 (first bar closing back above the level = pivot, buy the break of its high later that day, stop = day low so far, floor 0.1 ADR),
H15/H30 (pivot entry with a 1 ADR stop). Exits 5 sessions or first close under the 10 EMA (max 30); same-day stop on later bars. One setup
per ticker per level per 5 sessions. Compared per setup (misses count 0R, so equal dollar risk per trade), date-paired, halves.
An independent pandas resample of 400 random P30 setups reproduced every trigger and entry price exactly.

**Result.** See the result line. The tighter stop is paid for by more stop-outs and missed setups; per setup it nets to the same as buying
the daily touch. When the pivot never triggered the daily touch lost (-0.3R) and when it did the touch made +0.3R, but that is same-day
hindsight: buying at the pivot gives up the move from the level to the pivot, so the "confirmation" entry (H) was no better.
Leading group + RS fire 1-3 (prior-day-low level): P15 +0.24R/trade, +0.16R/setup vs touch +0.12; D_close +0.30R/trade, n 2,390 - not
separately significant.

**Caveats.** Half the alphabet (download stopped at PBR), ~1.6 years, bull-heavy, no costs or slippage (tight stops suffer most from both),
survivorship; pivot definition is one mechanical reading (no volume / VWAP rule, first reclaim bar only).

**How it could be used.** Not as a separate setup or an edge. Fine as an execution preference (smaller stop, bigger size, more small
losses) on the daily setups that already work, mainly post-thrust; expect a ~25% win rate. If Adam wants it live, it needs Alpaca intraday
bars; a version with a volume or VWAP condition is the next test.
