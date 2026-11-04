---
id: R-2026-11-04-rs-sheet-vs-dashboard
title: RS formula: Trading Dashboard v12 sheet (3-month % change) vs dashboard RS Rating
date: 2026-11-04
status: mixed           # works | doesnt | mixed | untested | process
kind: stock             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 20 / 60 sessions
sample: Nov 7, 2025 – Oct 2, 2026 (every 5 sessions, 252 sessions of history needed), liquid stocks $5+, $20M+/day, ~1,800 per date; top 10% ≈ 180 names
result: neither score picks winners reliably over this year. Top 10% vs the average liquid stock, next 20 sessions: dashboard RS +0.31% (t ~0.2), sheet −0.13%; next 60: RS +0.16%, sheet −0.79%. Top-10% lists share 58% of names; names only the dashboard RS picks beat names only the sheet picks (20d +1.01% vs −0.26%; 60d +0.97% vs −1.49%)
halves: RS +3.4 / −2.8 (20d), sheet +1.5 / −1.8; every momentum score flipped sign in the 2nd half (Apr–Oct 2026)
layers: []
integrated: no          # yes | partly | no | rejected
source: chat Nov 4, 2026 (Adam, Nov 2: "do you like our RS better than this one? It comes up with different stocks"); tools/rs_compare/study.py
---
**Idea.** Adam's "Trading Dashboard v12" sheet ranks stocks by
`googlefinance(price) / INDEX(googlefinance(price, TODAY()-90, TODAY()-63), 2, 2) - 1` = the % change since the first close on or
after 90 calendar days ago (≈ 62 sessions), one period, not ranked. The dashboard's RS Rating blends 63/126/189/252-session returns
40/20/20/20 and ranks 1–99 against liquid stocks. They list different stocks: which is better?

**How it was tested.** Our bars (splits applied), every 5 sessions with 252 sessions behind each date. Liquid = $5+, 50-day average
$20M+/day. Each date: top 10% and top 20% by each score, next 20 / 60 sessions return minus the equal-weight average liquid stock.
Also 21 / 42 / 63-session returns alone, a 50/50 blend of the two percentiles, and the split "on both / dashboard only / sheet only".
t-stats discounted for overlapping windows (effective n = dates × 5 ÷ horizon).

**Result.**
| Top 10% by | next 20 sessions | 1st / 2nd half | next 60 sessions | 1st / 2nd half |
|---|---|---|---|---|
| Dashboard RS Rating | +0.31% | +3.38 / −2.75 | +0.16% | +7.5 / −11.2 |
| Sheet (~62-session %) | −0.13% | +1.50 / −1.75 | −0.79% | +3.7 / −7.6 |
| 50/50 blend | +0.06% | +2.62 / −2.51 | −0.44% | +5.9 / −10.1 |
| On both lists | −0.08% | +2.87 / −3.02 | −0.23% | +7.2 / −11.6 |
| Dashboard RS only | +1.01% | +4.06 / −2.03 | +0.97% | +7.9 / −9.7 |
| Sheet only | −0.26% | −0.38 / −0.13 | −1.49% | −1.4 / −1.6 |
| 21 / 42-session return | −0.15 / −0.56% | | −0.62 / −1.52% | |

58% of the top-10% names are on both lists. The names the two disagree on are where they differ: the stocks the dashboard RS adds
(steady 6–12 month leaders) did better than the ones the sheet adds (fast 3-month movers that weren't strong before), in both
horizons and in both halves for the sheet-only side (always negative).

**Caveats.** One year (RS needs 252 sessions of history; the free plan has ~500), mostly overlapping windows, and this year's second
half punished every momentum ranking (the AI/semis unwind), so no version is "proven". Survivorship (delisted losers missing).

**How it could be used.** Keep the dashboard RS Rating as the main ranking. The sheet's number is just a 3-month return; it isn't
better, and the names only it finds did worse. If Adam wants to see it, it can sit as an extra "3M %" column, not a replacement.
Ranking alone isn't an edge in either form — the group filter, setups and market state carry the edge (Launch list, box trades).
