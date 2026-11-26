---
id: R-2026-11-26-rs-dots-breakouts
title: RS line new highs (blue dots): breakout filter, divergence warning, and 'dots stopped' exit
date: 2026-11-26
status: mixed           # works | doesnt | mixed | untested | process
kind: setup             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 21 sessions (also 5 / 63, and a 10 EMA trail up to 63)
sample: Jun 2025 - Nov 2026 (126-session RS needs history), liquid stocks $10+ $20M+/day, ETFs out; 15,636 breakouts (364 dates), 12,333 new 126-day highs, 35,593 holder samples
result: (A) RS-confirmed breakouts (RS dot within 5 sessions) vs unconfirmed +0.6 pts 21d excess (t 1.4, halves +0.9/+0.2), trade R +0.04 (t 0.6) - no edge; leading groups carry it (confirmed +2.6% t 3.7 vs unconfirmed +1.9%). (B) new 126-day price high with no RS dot in 20 sessions ("divergent") lagged confirmed highs by 1.1 pts 21d (t 2.4, halves +1.7/+0.4) but a simpler undeduped recompute gave t 1.5 with halves +1.4/-0.5; divergent highs had SMALLER drawdowns (-11.9% vs -14.9%, 10% vs 17% fell 25%+; ~equal in ADR units) - lower return, not a crash warning. (C) sessions since the last dot (0-5 vs 15-30) no difference (+0.3 pts, t 0.4), also for RS Rating 80+; "wide 21 EMA trail while dots print, 10 EMA after 15 dotless sessions" vs plain 10 EMA trail +0.005R (t -0.2).
halves: A +0.9/+0.2 pts; B +1.7/+0.4 (deduped) but +1.4/-0.5 undeduped; C mixed signs
layers: [rs_fire, rspull, setup_selector]
integrated: no          # yes | partly | no | rejected
source: chat Nov 26 2026 (Adam, @1ChartMaster SNDK chart: "notice when it stopped printing RS dots"); tools/rs_breakout_study/study.py (A.csv, B.csv, C.csv)
---
**Idea.** RS line (close / SPY) new highs = "blue dots". SNDK printed them all the way up Mar-Jun 2026, they stopped at the top, then -73%.
Three rules: (1) only take breakouts with a recent RS dot; (2) price new high without an RS dot = warning, no new entries; (3) no dot for
15-20 sessions while holding = stop adding / tighten the trail. Also: the 1-year RS Rating lags (SNDK still ~78 at -73%).

**How it was tested.** Daily bars, splits applied; dot = RS line at a new 63- or 126-session high. (A) breakout = close above the prior
20-session high, close > 50 EMA, 21 > 50 EMA, one per stock per 10 sessions; buy next open; excess vs the average liquid stock at 5/21/63
sessions; trade R with stop at the breakout-day low (0.3-2 ADR), exit first close under the 10 EMA (max 63). (B) new 126-session closing
high, dot within 5 sessions vs none in 20; 21/63 excess and worst drawdown in 63 sessions. (C) stocks above the 50 EMA with a dot in the
last 60 sessions, every 5 sessions, bucketed by sessions since the last dot; plus the exit comparison on (A) trades. Date = unit (per-date
means, date-paired diffs), halves split at the median date; states from breadth.csv (thrust / strong / mixed / weak).

**Result.** See the result line. By state (A, 126): thrust windows confirmed +2.2% 21d (t 4.7) vs unconfirmed +1.3%; strong ~0; mixed and
weak negative for both. "RS led price" (dot while price 3%+ under its high, then breakout) n 148-195, nothing. SNDK itself: on the daily
126-session RS its last close high (Jun 25, $291.9) printed a dot - no divergence at the top; the dots stopped because price stopped. A plain
10 EMA trail exited Jul 1 at $254; the "15 sessions without a dot" rule would have fired Jul 17 at $169.

**Caveats.** ~1.5 years, bull-heavy, survivorship (stored universe), no costs; overlapping 21/63-day windows; second half (2026) weak for
breakouts in general. Overlaps rs_fire (RS dots 1-3x then a 21 EMA pullback in leading groups, which does pass) and rspull.

**How it could be used.** Not as a standalone setup or exit. RS dots stay as an ingredient inside rs_fire (leading groups) in the setup
menu. Divergent new highs could be an info-only "laggard high" tag (watch: lower 21d return, not a crash flag). The 10 EMA trail already
beats the dot rule as an exit. The SNDK-style "dots stopped then collapse" needs a bear-market sample (longer history) to test the top case.
