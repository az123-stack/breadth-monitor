---
id: R-2026-10-17-order-flow-proxies
title: Free order-flow data: FINRA short-sale volume (DIX input)
date: 2026-10-17
status: mixed
kind: market
horizon: 21 sessions
sample: 486 days (Oct 2024–Oct 2026), ~22 independent 21-day windows
result: S&P 500 short share (5-day vs 120-day normal) IC +0.26 vs SPY 21d (halves +0.34 / +0.19), residual vs breadth tab +0.25; top fifth SPY +3.1% (88% up) vs bottom +0.7%, all +1.4%
halves: both positive
layers: [hidden_buying]
integrated: yes
source: breadth/finra.py, .github/workflows/finra.yml
---
**Data.** FINRA's free daily short sale volume files (cdn.finra.org/equity/regsho/daily/CNMSshvolYYYYMMDD.txt, off-exchange trades,
from Aug 2018, posted by ~6 PM ET). Stored per ticker for liquid universe stocks + SPY/QQQ/IWM in `data/finra/YYYY-MM.parquet` (~19 MB
for 2 years); daily measures in `data/finra_daily.csv`. Backfill via `finra.yml` (Actions; Claude's sandbox can't reach FINRA); the
daily update tops up the last 7 days inside `update.py` (gated by `LEVELS_ENABLED`).

**Test (SPY next open → 5/10/21/42 sessions, Spearman).** Same-day link to SPY's return ≈ 0 (it is not "who won today").
Raw levels: sr_spx5 IC +0.30 at 21d but halves +0.45 / +0.08 (drift). Detrended (5-day minus own 120-day mean) sr_spx5: +0.26, halves
+0.34 / +0.19, non-overlapping samples +0.12 / +0.25 / +0.40; residual after ratio10, dn_share, T2108, vtilt10 +0.25. 60-day z-scores
weaker (+0.09). Median-stock share (srm_all5) raw +0.29 (halves +0.49/+0.21) but detrended only +0.03–0.16. Off-exchange share of
volume: nothing. ETF short shares (SPY/QQQ/IWM): noise. Down days with short share z ≥ 1: SPY21 +2.6%, 82% up (n 17) vs normal +1.4%.

**Verdict.** WATCH → shown as experimental information. Only ~2 years; bull-heavy. Re-test when more history accrues; Massive Starter
won't help (FINRA goes back to 2018 for free — a longer backfill is possible by adding older bars).

**Oct 16, 2026.** S&P 500 5-day 44.2% vs normal 45.2% (35th pct, "normal"); median stock 54.5% (82nd pct) → typical stock bought more
than the big S&P names, consistent with the megacap/AI unwind.
