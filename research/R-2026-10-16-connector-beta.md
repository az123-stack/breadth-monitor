---
id: R-2026-10-16-connector-beta
title: After deep washouts, sensitivity (beta) paid — not plain RS
date: 2026-10-16
status: mixed
kind: market
horizon: 21 sessions
sample: ~200 cutoffs Apr 2025–Sep 2026; 4 washout thrusts by the study definition (dashboard: 7 thrusts, 2 deep)
result: deep thrusts (SPY ≥ 8% pullback, T2108 ≤ 25): RS ≥ 80 top-30 beta +26% / +33%; shallow +9% / −26%; RS top 30 lagged in thrust windows; no group leads (lead-lag ≈ 0)
halves: only 2 deep events
layers: [washout_thrust]
integrated: partly
source: chat Oct 16, 2026 — connector study (scratch conn_lib.py + scan.py); card built in commit 0f0aea5
---
**Idea.** Adam: some "connectors" (stocks, groups, hidden forces) influence many other stocks. If we know which
ones are in control and their shape (e.g. the April 2026 V-recovery), we should know which followers move most.

**How it was tested.** Tradeable stocks ($5+, $20M+/day, ETFs out), 60-day daily returns. Connector map: market
factor removed, PCA hidden factors, group "reach" (share of other stocks correlated with a group beyond the market).
Lead-lag: each group's ex-market return vs the rest of the market next day / next 5 days. Signals at each cutoff
(RS, leaders score, 60-day beta to SPY, PC2 "leader factor" loading, selloff depth, ADR, blends); buy next open,
21/63-day returns vs all stocks; ~200 cutoffs plus thrust windows (up4 ≥ 500 with ratio5 ≤ 1.2). Headline
(Apr 6, 2026 top 30 by beta) recomputed independently from raw bars: +37.6% vs all +7.8%.
Outside research consulted: inter-industry networks (central industries propagate shocks), customer momentum
(lead-lag decayed after 2004), Hong-Torous-Valkanov (industries leading the market — not tradeable after costs),
Daniel–Moskowitz momentum crashes (high-beta losers lead sharp rebounds), Kritzman absorption ratio.

**Result.**
- Hidden connector = one axis (AI hardware/power/semis vs defensives/software), ~8% of variance; nobody leads:
  next-day correlations ≈ 0 (best semis +0.06), every group bottomed within a day of SPY in 3 selloffs.
- April 2026 (Apr 6 cutoff): top 30 by beta ≈ +40% in 21d (60% in the top 10% of all stocks), RS + beta +40%,
  RS alone +21%, leaders score +16%, all stocks +8%, SPY +10%. PC2 "leader" loading added nothing.
- Across all dates: in thrust windows RS top 30 −2% vs all +5% (momentum-crash pattern); beta top 30 +10%.
  Outside thrusts beta ≈ market; in down months beta lagged by ~10 pts.
- Depth decides it (RS ≥ 80 + top-30 beta on the thrust day): Apr 2025 (SPY −19%, T2108 4) +26%; Mar 2026
  (−9%, 22) +33%; Nov 2025 (−5%, 28) +9%; Jun 2026 (−4.5%, 47) −26%. Dashboard's own 7 thrusts agree:
  deep +26% / +34%, shallow −4% to +9%.
- Live: Oct 15, 2026 thrust is SHALLOW (SPY −2.1% off high, T2108 low 26) → card says don't chase high beta;
  1 session in, list −6% vs all −1.6%. Its result lands ~Nov 13, 2026.

**Caveats.** Only 2 deep events; overlapping windows; single names in the list ranged to −79% / −90% in a month;
no costs; survivorship.

**Used.** Washout thrust card (experimental), `breadth/washout.py`, keeps a running scorecard of every thrust.
Small size per name, hard stops. Promote only after more deep washouts confirm it.
