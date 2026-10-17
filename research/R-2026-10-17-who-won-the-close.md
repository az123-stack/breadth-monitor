---
id: R-2026-10-17-who-won-the-close
title: Who won the close (close location, absorption, fade)
date: 2026-10-17
status: doesnt
kind: market
horizon: 5–21 sessions
sample: ~470 days, Oct 2024–Oct 2026
result: descriptive only — IC ≈ 0 for close location, absorb, fade at 5/10/21 sessions, both halves
halves: no edge in either
layers: [who_won_close]
integrated: yes
source: breadth/metrics.py (clv_all, absorb, fade)
---
**Measures.** $-weighted close location in the day's range (−1 low, +1 high); % of stocks down 1%+ closing in the top half (absorb);
% of stocks up 1%+ closing in the bottom half (fade). Same stocks as volume tilt.

**Result.** No forward edge. 5-day absorb +0.12 (1st half +0.22, 2nd −0.02). Heavy days (dn_share ≥ 65): absorb ≥ 20% SPY10 +2.1% (n 12),
< 8% +1.1% (n 38), all +0.5%. A first quick cut ("close-at-lows days with T2108 < 42 led lower 4 of 5") did not survive the full list
of 20 such days (mixed, ≈ +1%).

**Oct 15–16, 2026.** Oct 15 absorb 47% (98th pct); Oct 16 clv −0.41 (6th pct), absorb 1.8% (2nd pct).
