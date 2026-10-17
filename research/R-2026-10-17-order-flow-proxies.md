---
id: R-2026-10-17-order-flow-proxies
title: Free order-flow data: FINRA short-sale volume (DIX input)
date: 2026-10-17
status: untested
kind: data
horizon: 5–21 sessions
sample: available from Aug 2018
result: not tested yet; FINRA daily short volume is free, posted by 6 PM ET, reachable from GitHub Actions (blocked in Claude's sandbox)
halves: —
layers: []
integrated: no
source: vtilt study notes
---
**Idea.** Dark-pool short volume ratio (the raw input of SqueezeMetrics' DIX) as a market-level layer.

**How it could be used.** New daily fetch in the update workflow + backtest vs ratio10/dn_share/tilt; must add information beyond what we have.
