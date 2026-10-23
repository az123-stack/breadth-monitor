---
id: R-2026-10-22-the-trade
title: "The trade: does the market's main rotation persist, and does a seesaw reverse?"
date: 2026-10-22
status: mixed
kind: market
horizon: 10 sessions
sample: 410 days Feb 20 2025 – Oct 7 2026 (settled); 41 independent 10-session samples; 127 sub-themes (4+ stocks)
result: winning fifth +0.9% vs avg group next 10 (t 1.5); when winners hold up on the losers' best days +1.1% (t 2.0, halves +1.3/+1.1); when they give back, the losing side won 5 of 5 settled episodes (n small)
halves: all +1.0/+0.9; holds +1.3/+1.1; gives back losers +3.0/+1.2
layers: [the_trade]
integrated: yes
source: breadth/thetrade.py (Adam, Oct 22 2026: "how do we handle the trade in play?" after the AI-hardware → software/defensives day)
---
**Idea.** Name the market's main rotation every day, so the trade is explicit: the top fifth of sub-themes by 20-session move
(winners) vs the bottom fifth (losers). Then ask whether the winners attract real buying (they hold up on the days the losers
bounce) or whether it's a seesaw (money sloshing between the two, winners give back whenever the losers rally).

**How it was tested.** Equal-weight sub-theme indexes (rotation.group_frames, 4+ stocks). Every day from day 80: baskets
picked with data up to that day; over the prior 60 sessions, correlation of the two baskets' daily moves and the winners'
average move minus SPY on the losers' best 15% of days ("ind": ≥ 0 holds up, < 0 gives back). Outcome: each basket's next
10 sessions vs the average group. Independent samples every 10 sessions; split halves by date.

**Result.** Winners overall +0.9% (t 1.5, halves +1.0/+0.9); losers −0.1% (t −0.2). Holds up (367 days): winners +1.1%
(t 2.0, halves +1.3/+1.1), losers −0.4%. Gives back (43 days, 6 episodes: Feb–Mar 2025, Apr 2025, Jul–Aug 2026, Sep 1–3,
Sep 10–15 2026, Oct 16– 2026 open): winners −0.3%, losers +1.1% (n 5 independent); per episode the losing side beat the winning
side in all 5 settled ones (Apr 2025 +5.3% vs −5.2%). Baskets moving opposite (corr < 0.3, 23 days) is rare: winners −2.1%,
losers +3.1% (n 3). Normally the two baskets move together (corr median 0.68: both ends are high-beta groups).

**Caveats.** Two years, mostly a bull market; overlapping 20-day selection windows; survivorship in the theme lists (cancels
mostly, since everything is vs the average group); the "gives back" sample is tiny. The holds-up edge passes t ≥ 2 by a hair.

**How it could be used.** Built Oct 22 as an info-only card at the top of the Read-out tab (scoreboard, real-or-seesaw tile,
plays in the winning groups with a don't-chase flag at 2 ADRs over the 21 EMA, counter-trade watch with the comeback trigger,
evidence) and a THE TRADE block on the story fact sheet. Candidate layer later: in "gives back" states, prefer the snapback
side; in "holds up" states, add a confluence point to picks in the winning groups. Re-test both as history grows.
Oct 21 reading: Consumer + Biotech & Health over AI Infrastructure; correlation 0.03, winners −0.9% vs SPY on the losers'
best days → gives back (seesaw) since Oct 16.
