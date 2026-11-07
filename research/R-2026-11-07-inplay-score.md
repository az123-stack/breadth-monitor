---
id: R-2026-11-07-inplay-score
title: In Play ranking: which in-play stocks do best over the next 10 sessions
date: 2026-11-07
status: mixed           # works | doesnt | mixed | untested | process
kind: stock             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 10 sessions
sample: 46,296 in-play stock-days on 229 dates (Nov 24, 2025 – Oct 22, 2026); in-play = inplay.py rules, last 5 sessions, $5+, $10M+/day
result: Leading group (+2.9 pts vs other in-play stocks, t 9.0) and within 15% of the 52-wk high (+2.1, t 8.8) help; spike (−6.8), ADR > 10% (−12.2) and 30%+ off the high (−3.3) hurt. Score +2 → +1.2% vs SPY (56% up), −3 → −18.9% (22% up); +2 minus ≤ −1 = +4.2 pts (non-overlapping dates +5.5, t 4.7)
halves: leading group +3.15 / +2.70; near high +2.20 / +2.05; spike −3.75 / −9.79; ADR > 10% −7.13 / −17.18; 30%+ off −2.87 / −3.62; score gap +3.31 / +4.99. Direction, RS top 30%, event today, 2+ ADRs over the 21 EMA: halves disagree (not used)
layers: []              # ids from data/layers.json this is evidence for (empty = new idea)
integrated: yes         # yes | partly | no | rejected
source: chat Nov 7, 2026 (Adam: "score the in play so it's sorted with the best at the top"); tools/inplay_study/score.py
---
**Idea.** The In Play tab (Nov 5) listed every stock with something happening, newest first. Adam wants the best at the top.

**How it was tested.** Every date with a full year of history: stocks in play that day (same rules as breadth/inplay.py).
Entry next open, exit close 10 sessions later; compared with SPY on the same dates and with the average in-play stock that
day (date-paired, t over dates). Nine traits picked before looking, from earlier cards (group strength, RS, near highs,
direction, freshness, and the record-volume "avoid" tells). Kept only traits with the same sign in both halves.

**Result.** Score = +1 sub-theme top third on 63-day return, +1 within 15% of the 52-wk high, −1 spike in the window (gap
10%+, day +20%+ or 20x volume), −1 ADR over 10%, −1 30%+ below the high.
| Score | Share | vs SPY 10d | vs avg in-play | Up |
|---|---|---|---|---|
| +2 | 8% | +1.2% | +2.4 pts | 56% |
| +1 | 31% | +0.1% | +1.4 | 52% |
| 0 | 26% | −0.6% | +0.7 | 46% |
| −1 | 26% | −0.8% | +0.3 | 47% |
| −2 | 5% | −4.7% | −3.5 | 36% |
| −3 | 4% | −18.9% | −17.6 | 22% |
In-play stocks as a whole lagged SPY by 1.2% over 10 sessions: even the best score only just beats SPY. The score's real job is
keeping the junk (spikes, very volatile names, broken stocks) off the top.

**Caveats.** Traits were kept after seeing both halves (selection risk); 10-day windows overlap (t overstated ~3x; the
non-overlapping check still t 4.7); one year, bull-heavy; today's sub-theme lists (mild hindsight); no costs.

**How it could be used.** v3 Stocks → In Play sorts Best first by this score (Sort chip: Newest first restores the old order).
Information only: it orders the list, it does not move any pick. Next: the queued "same setup, in play vs not" test.
