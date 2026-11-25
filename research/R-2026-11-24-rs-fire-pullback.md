---
id: R-2026-11-24-rs-fire-pullback
title: RS fire (1-3 new RS-line highs) then pullback to the EMAs: buy the touch or the undercut-and-reclaim
date: 2026-11-24
status: mixed
kind: setup
horizon: 5 sessions / 10 EMA trail (max 30)
sample: Feb 2025 - Nov 2026, liquid stocks $10+ $20M+/day; RS fire = RS line (close/SPY) new 20/63/126/252-session high; 1-3 fires in the prior 20 sessions; first 21 EMA contact since the last fire
result: Leading groups (sub-theme top 30% on 60d) carry it. Pooled over periods, leading groups - touch 21 EMA after 1-3 fires +0.24R 5d (t 3.3, win 50%, n 452), trail +0.20R (t 2.8), halves +0.20/+0.20, vs the same touch with no recent fire +0.17R (halves -0.05/+0.37). Undercut 0.3 ADR + reclaim (close over 21 EMA and prior high, buy next open, stop = undercut low) after 1-3 fires +0.47R 5d (win 56%, n 85, t 1.7, halves +0.24/+0.68) vs after 4+ fires -0.07R and with no fire -0.08R. Outside leading groups every variant ~0. 9 EMA touches weaker than 21. Fire period barely matters (20-day fire slightly best: touch21 +0.25R t 3.0).
halves: touch21 1-3 lead same sign both halves; undercut 1-3 lead same sign but t < 2
layers: []
integrated: no
source: chat Nov 24 2026 (Adam: "when the x-timeframe RS fires one or a couple times and then pulls back to the EMAs, buy the touch or the undercut and rally"); tools/rs_fire_pullback/study.py (trades.csv)
---
**Read.** Adam's "once or a couple times" nuance is what separates the undercut trade (1-3 fires +0.47R vs 4+ fires -0.07R): a fresh RS leader
shaken out under the 21 EMA gets bought; a stock that has fired many times is extended and the undercut is distribution. Needs more samples
(n 85, t 1.7) before trusting; the 21 EMA touch version passes t >= 2 in leading groups but the edge over a plain leading-group dip is small (+0.07R).
Caveats: overlapping signals across periods (deduped in the pooled line), survivorship, no costs, touch fills assume the EMA price.
Candidate live card: "RS fresh fire -> 21 EMA" in leading groups (touch list + undercut-reclaim alerts).
