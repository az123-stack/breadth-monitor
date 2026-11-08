---
id: R-2026-11-08-heavy-lifters
title: Heavy lifters: the biggest stocks adding market value while AI megacaps fall
date: 2026-11-08
status: untested        # works | doesnt | mixed | untested | process
kind: stock             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 3 / 6-week windows (descriptive)
sample: S&P 500 + Nasdaq-100 with Google market caps, data to Nov 6, 2026
result: descriptive. 6 weeks: SPY −4.7%, gainers +4.15 index pts vs losers −9.17 (325 of 497 up); top adders LLY, BRK.B, WMT, MSFT, AMZN, V, MA, COST, HD, ACN; sectors Health Care +0.81, Staples +0.58, Financials +0.51, Discretionary +0.47; Tech −5.63. ★ EMA-pullback setups (top 50): LLY, WMT, MSFT, V, MA, AMGN, GILD, SPGI, ISRG, ABT …
halves: n/a
layers: []
integrated: yes         # v3 Stocks → Heavy lifters (info only)
source: chat Nov 8, 2026 (Adam); breadth/heavy.py + renderHeavy in breadth/v3_tabs.js
---
**Idea.** Adam: the hyperscalers / AI megacaps are falling, yet most stocks rise; which LARGE stocks carry the upside, and which of them are
pulling back into their EMAs — "these are the stocks I want to be concentrating on right now".

**How it was built.** Market-cap dollars added over the window = Google cap × (1 − 1/(1+return)); index points ≈ $ ÷ total S&P cap (not
float-adjusted). EMA spot and the ★ Setup rule are in CODEMAP.md (Heavy lifters). Nothing tested.

**Caveats.** Big caps move 1–2% a day: EMA pullbacks here are slow-money entries, not Kristjan breakouts. Related evidence: the 3-month
picks study found RS leaders inside leading & accelerating groups paid; the group (sub-theme top 20%) mattered in the Box and Supply
studies. Untested idea worth testing later: do the top-$ adders of the last 6 weeks keep beating SPY over the next 21 / 63 sessions, and do
their 9/21 EMA pullbacks beat buying them at random days?
