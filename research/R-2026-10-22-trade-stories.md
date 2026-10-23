---
id: R-2026-10-22-trade-stories
title: "Trade Stories: do running news/earnings narratives, checked against price, point to the right groups?"
date: 2026-10-22
status: untested
kind: market
horizon: 5 sessions per daily call
sample: forward only, from Oct 22 2026 (5 seed stories)
result: not yet measured; every story-day is scored (favoured groups minus hurt groups or SPY, next 5 sessions)
halves: n/a
layers: [trade_stories]
integrated: yes
source: breadth/stories.py, stories_guide.md (Adam, Oct 22 2026: "a tab for Trade Stories ... recommend how to trade the developing story")
---
**Idea.** Pull the news, earnings and macro behind the market's moves into running storylines (max 6 open), each a case file
with a thesis (what / why / how / real or seesaw / confirm or break), a sourced timeline, the groups and stocks it trades
through, catalysts and a trading plan. Understanding the why is what lets a swing trader hold through noise.

**How it will be tested.** No backtest is possible (the narratives are written live). Each day a story is open, its call is
logged in `history` (status + favoured / hurt sub-themes) and settled 5 sessions later from rotation.mhist equal-weight returns:
favoured minus hurt (or minus SPY). Compare: all story-days vs random group pairs; building vs peaking vs fading; stories whose
price check agreed vs disagreed on the day. Pass rule as usual (t ≥ 2 over ≥ 20 dates, both halves) before it can affect picks.

**Caveats.** Writer hindsight in choosing groups; overlapping 5-session windows; a few stories dominate the sample.

**How it is used now.** Trade Stories tab (info only), written by the "after the close" task once a day.
Seed stories Oct 22: AI spending gets repriced (peaking), Hot inflation keeps the 10-year near 5% (peaking), Gulf attacks keep
oil above $100 (building), IT services from AI loser to AI implementer (building), Managed care repairs (building).
