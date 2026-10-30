---
id: R-2026-10-29-ema-test-odds
title: Time above the 9/21 EMAs and the odds when price comes back to them (long + short)
date: 2026-10-29
status: mixed         # works | doesnt | mixed | untested | process
kind: setup
horizon: 20 sessions; win = +2R before the stop
sample: Jan 29, 2025 – Sep 25, 2026; liquid stocks ($5+, $20M+/day); 38,558 long tests, 32,991 short tests
result: time above alone ≈ nothing (win 28.5% at 3–5 sessions vs 29.8% at 21–40); 17-feature logistic model AUC 0.50 out of sample; coupling works — post-thrust + leading group 34% win / +0.38R (halves +0.38/+0.38), + 15 sessions above 35% / +0.48R (+0.72/+0.42); outside thrust windows leading group −0.07R; shorts lose in every tier
halves: tier A +0.72R / +0.42R; tier B +0.38R / +0.38R; tier C +0.02R / −0.18R
layers: [emaprob]
integrated: yes
source: chat Oct 29, 2026 (Adam: "time spent above the 9 and/or 21 emas ... when the probability is high enough it results in an entry; same on the short side"); breadth/emaprob.py
---
**Idea.** A stock that has lived above its 9 / 21 EMA should hold it when it comes back; the longer it lived above, the better the odds.
Use the odds to decide when a test is an entry. Mirror for shorts (living below, rallying into the EMA).

**Test.** Test = 3+ closes on the right side, then the low within 0.25 ADR of the EMA (or through it); first per 5 sessions per EMA; a 9
test that reaches the 21 counts as a 21 test. Trade: buy the break of the test-day high within 3 sessions, stop the test-day low (max 1
ADR), win = +2R before the stop within 20 sessions (break-even 33%); also R after 20 sessions and Adam's exit (close under the 10 EMA).

**Result.** Every test: 29% win, −0.06R. Time above on its own: 3–5 sessions 28.5% / −0.10R, 21–40 sessions 29.8% / +0.04R (halves
disagree). Depth: holding 0.5–1 ADR above the EMA 31% vs closing 0.5+ ADR through 25%. A ridge logistic model on 17 measures (time above,
share of closes above, depth, run-up, prior tests, slope, RS, market, group rank, thrust window, interactions) trained on the first half
had NO skill on the second (AUC 0.50 long, 0.49 short), so no model probability is shown. Coupling held in both halves: leading group
(sub-theme top 30% on 60 days) inside a post-thrust window 34% / +0.38R (n 2,148), and with 15+ sessions above 35% / +0.48R (n 700,
Adam's exit +0.29R). Outside thrust windows leading groups were about break-even (−0.07R) and everything else lost (−0.10R). Shorts: every
tier lost (all −0.18R) in these two mostly rising years, weakest groups included.

**Read.** Time above the EMA matters only as a tiebreaker inside the real edge: leading group + post-thrust tape. It is not a signal on its own.

**Caveats.** Two years, mostly bull; 4–6 thrust windows carry tiers A/B (episodes overlap: many tests on the same days); survivorship;
the short side should be re-tested after a real downtrend.

**How it is used.** Card "EMA test odds" on the Setups tab (part 2): tier table re-run each build (A/B = entry tiers when win ≥ 30% and
both halves positive), live candidates in leading groups scored in the browser (`emaTier` = `emaprob.tier`), short side shown with a
"no edge found" label. Info only, never touches picks.
