---
id: R-2026-10-29-rs-high-pullbacks
title: RS line highs, then buy the first dip into the 9/21 EMAs
date: 2026-10-29
status: mixed         # works | doesnt | mixed | untested | process
kind: setup
horizon: 20 sessions (and Adam's exit: first close under the 10 EMA)
sample: Nov 13, 2025 – Sep 25, 2026 (an RS high needs a year of history first); liquid uptrend stocks $5+, $20M+/day; 6,398 first dips
result: RS-high dips -0.03R/trade (n 1,764, 19% win, 80% stopped) vs strong stocks without a recent RS high -0.06R (n 284); same-day edge +0.26R (t 2.03, halves +0.45/+0.14) on a 20-session hold, but ~0 with Adam's 10-EMA exit (-0.01R) and +0.8 pts vs SPY (t 1.2)
halves: edge +0.45R / +0.14R (20-session hold); Adam's exit +0.21R / -0.15R
layers: [rspull]
integrated: yes
source: chat Oct 29, 2026 (Adam: a trader "finds tickers making new RS highs and waits for weakness on them for the entry", HNGE weekly chart); breadth/rspull.py
---
**Idea.** The RS line (stock ÷ SPY) at a 1-year high marks a stock big money keeps buying relative to the market. Don't chase it: wait
for the first dip into the daily 9/21 EMA ribbon, buy the break of the dip-day high (within 3 sessions), stop the dip-day low (max 1 ADR).

**Test.** Every FIRST dip (no ribbon touch in the prior 5 sessions) of a liquid uptrend stock (21 EMA over a rising 50 EMA), traded
exactly like the live card; R capped at 10 (a few tiny-risk trades print 30R+). Groups: RS high within 25 sessions of the dip vs stocks
in the top 20% on 63-day return WITHOUT an RS high in 25 sessions (the fair control: equally strong, just no new RS high) vs every dip.

**Result.** Dip-buying with a stop under the dip-day low lost slightly in this sample for everyone (all dips -0.08R, 80% stopped out
within 20 sessions). RS-high dips lost less (-0.03R vs -0.06R; same-day edge +0.26R, t 2.03, both halves positive) on a 20-session hold,
but with Adam's exit (first close under the 10 EMA) the edge vanished (-0.01R) and vs SPY it was +0.8 pts (t 1.2). By recency: RS high
0–5 sessions before the dip 0.00R (n 1,313), 6–10 -0.35R, 11–25 -0.04R, 26–60 +0.02R, none in 60 sessions -0.24R. RS that led price
(RS high while price 3%+ under its own high) +0.13R (n 270, halves +0.19/+0.03). Post-thrust windows: RS-high dips +0.16R, but strong
stocks without an RS high did better (+0.44R, n 129). SPY under its 50-day: -0.11R.

**Read.** Not a money-maker on its own here: an RS high makes a dip a little less bad, it doesn't make it a buy. Useful as a watchlist of
the strongest names to buy on weakness when the group / market agree (Theme lifecycle BUY, ★ leading group, post-thrust).

**Caveats.** One year, mostly bull tape; survivorship in the stored universe; daily RS highs (his chart uses weekly dots — a weekly
version, RS high on the weekly close then a dip to the 10-week EMA, needs more history to test); the touch-day-low stop is tight.

**How it is used.** Card "RS leaders pulling back" on the Setups tab (part 2, after Dip buys), info only, never touches picks; backtest
re-run every build (`rspull.study`), verdict Proven only if the edge passes (t ≥ 2, both halves, n ≥ 30) AND the group makes money on
its own AND with Adam's exit.
