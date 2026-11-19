---
id: R-2026-11-18-ratio-watch
title: Ratio watch: RSP/SPY and MAGS/SOXX
date: 2026-11-18
status: mixed           # works | doesnt | mixed | untested | process
kind: market            # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 21 sessions
sample: Dec 2024 – Nov 2026, ~460 overlapping days (≈22 independent 21-day windows); RSP and MAGS rebuilt from member baskets
result: RSP/SPY 20-day change rank corr −0.26 vs SPY 21d (top 20% → SPY −1.2%, 41% up vs all +1.2%, 67%); MAGS/SOXX +0.23 (top 20% → SPY +3.1%, 87% up). Non-overlapping samples same sign (RSP −0.17/−0.19/−0.41, MAGS +0.40/+0.09/+0.18, n 22 each) but t < 2.
halves: RSP/SPY −0.27 / −0.19 · MAGS/SOXX +0.25 / +0.19
layers: [ratio_watch]
integrated: yes         # yes | partly | no | rejected
source: chat Nov 18, 2026 (Adam: "two things to watch, Mags / SOXX and RSP / SPY"); breadth/pairs.py
---
**Idea.** Adam asked for two ratios on the Breadth tab: equal-weight vs cap-weight S&P (is the market broad or carried by megacaps?)
and the Magnificent 7 vs semiconductors (where is the AI money sitting?).

**How it was tested.** `breadth/pairs.py`, recomputed every build. Ratio rebased to 100; signal = 20-day change; SPY bought next
open, held 5 / 21 sessions; tiers = bottom / top 20% of the 20-day change; also above / below the 50-day average. RSP = equal-weight
S&P 500 members (data/index_members.csv, today's list), MAGS = equal-weight AAPL MSFT NVDA AMZN GOOGL META TSLA, until the real ETFs'
history is stored (config.RATIO_ETFS, fetched like theme ETFs).

**Result.** Both point the opposite way from the usual reading. Fast broadening (RSP beating SPY) came before WEAKER SPY:
it showed up when megacaps were selling off and money hid in the average (defensive) stock. Mag 7 beating chips fast came before
STRONGER SPY (chips washed out, then rebounded). Above/below the 50-day: RSP above → SPY 21d +0.8% vs below +1.5%; MAGS above +2.4%
vs below +0.5%. 5-session horizon: no edge for either (rank corr ≈ 0). Nov 17 reading: RSP/SPY 20-day +5.1% (98th pct), MAGS/SOXX
+7.9% (86th pct) — both in the top tier.

**Caveats.** ~2 years, mostly a bull market, ≈22 independent windows → t < 2, doesn't pass the DECISIONS rule. Overlaps the
Two Camps (PC2) split and "The trade" (AI infra vs the rest); RSP/SPY overlaps dollar-flow and leadership-narrowing measures.
Baskets ≠ ETFs (RSP rebalances quarterly; MAGS weights differ). Today's S&P list = mild survivorship.

**How it could be used.** Information only: Breadth tab tiles + two charts. Re-test in ~3 months with the real ETF history and
more independent windows; if it holds, a Market-layer context flag (not a pick re-rank).
