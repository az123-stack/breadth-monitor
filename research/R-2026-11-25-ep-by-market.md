---
id: R-2026-11-25-ep-by-market
title: Episodic pivots by market state, longs and shorts (incl. "short after a couple days")
date: 2026-11-25
status: doesnt
kind: setup
horizon: 5 sessions / 10 EMA trail
sample: Jan 2025 - Nov 2026, 9,070 trades; EP = gap >= 8% (or <= -8%) on 3x 50-day volume, $5+, $20M traded; state at the prior close (playbook rule)
result: Price-only EPs have no edge in any market state, long or short. Longs (stop under the EP-day low): next open -0.10 to -0.30R, buy over the EP-day high -0.13 to -0.25R, buy after a 2-day hold -0.01 to -0.40R; in weak breadth -0.18 / -0.25 / -0.01R. Quality filters ($10+, $20M/day, strong close, not extended) did not fix it (weak breadth -0.12 to -0.41R). Shorts of gap-downs: about zero everywhere (-0.12 to +0.15R; weak breadth -0.04 / -0.09 / +0.01R); "short after a couple of days on a failed bounce" +0.01R in weak breadth, -0.10R post-thrust; former leaders gapping down no better. The Today's playbook EP line (+0.05R in weak, Selective) uses a different exit; neither is a real edge.
halves: no variant positive in both halves with t >= 2
layers: []
integrated: no
source: chat Nov 25 2026 (Adam: "I thought episodic pivots were the best to trade in bad markets, whether longs or shorting after a couple days"); tools/ep_study/study.py
---
**Read.** The EP edge traders describe comes from the catalyst (earnings growth + raised guidance, a neglected stock re-rated), which bars can't
see: a mechanical gap-on-volume screen mixes beats with offerings, biotech binaries and buyouts. Next: tag EPs with the catalyst agent's
quality (strong / real / weak) going forward and test catalyst-confirmed EPs once ~50+ are logged. Survivorship (delisted gappers missing)
flatters longs and hurts shorts slightly.
