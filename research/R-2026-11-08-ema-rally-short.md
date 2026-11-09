---
id: R-2026-11-08-ema-rally-short
title: Short the rally into falling EMAs (downtrend mirror of the momentum burst)
date: 2026-11-08
status: doesnt          # works | doesnt | mixed | untested | process
kind: setup
horizon: 5 / 10 / 20 sessions, 9-EMA trail, 2R target
sample: 14,199 trades into the 21 EMA (444 dates) + 4,163 into the 50 EMA, Jan 2025 – Nov 2026; $5+, $20M+/day stocks
result: no edge overall (21 EMA −0.03R, 50 EMA +0.03R). "Falling market" (SPY under a falling 50-day) −0.12R; falling market outside thrust windows +0.39R (t 6.2) but ALL of it from one episode (Mar 2025 +1.33R; Apr 2025 −0.73, Mar 2026 −0.74, Jul 2026 −0.30). Inside thrust windows −0.28R (t −10). Fallen leaders (RS top 30%) −0.14 to −0.20R
halves: falling mkt & no thrust +0.95 / −0.69 (21 EMA), +0.79 / −0.70 (50 EMA)
layers: []
integrated: no
source: chat Nov 8, 2026 (Adam, about a trader's plan "mean reversion back into supply: shorts into declining 20/50/200-day MAs and gaps"; Adam: "like momentum bursts up from on top of EMAs, this would be down from below EMAs"); tools/supply_study/ema_short.py
---
**Idea.** In a falling market, short stocks whose bounce runs up into their declining 21 / 50 EMA and rolls over — the mirror of buying
momentum off rising EMAs.

**How it was tested.** Downtrend = close < EMA21 < EMA50, both falling vs 5 sessions ago, 10%+ under the 60-day high. Signal = the high
reaches the 21 (or 50) EMA within 0.25 ADR, close back under it and red. Short next open, stop 0.1 ADR above the signal high (risk floor 0.3
ADR), one signal per stock per 10 sessions. Exits: 5/10/20 sessions, cover on a close above the 9 EMA, or 2R target.

**Result.** Coin flip overall; it only paid in ONE real bear leg (Feb–Mar 2025, the decline that ran into April). In the dips that ended
(Apr 2025 low, Mar 2026, Jul 2026) it lost −0.3 to −0.7R. Inside a thrust window it is the worst trade we've measured (−0.28R, t −10).
Shorting fallen leaders into their EMAs lost (−0.14/−0.20R), same as the in-vogue short findings. Weak RS + falling market lost −0.43R.

**Caveats.** Only ~4 falling-market episodes in 2 years; survivorship flatters longs / hurts shorts slightly; no borrow costs.

**How it could be used.** Not as a standing setup. It is a bear-market tool: only when a decline keeps going (SPY under a falling 50-day
AND no thrust since), and even then one episode decided the whole sample. Nov 6, 2026: SPY 735 under a falling 50-day (766) BUT inside a
thrust window (Nov 4) → the worst bucket.
