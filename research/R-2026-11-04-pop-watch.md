---
id: R-2026-11-04-pop-watch
title: Pop watch: buying the pullback after a sub-theme pops
date: 2026-11-04
status: doesnt          # works | doesnt | mixed | untested | process
kind: group             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 20 sessions (R trade)
sample: May 2025 – Oct 2026, 504 sub-theme pops; 861 first 9/21 dips 3–25 sessions after a pop vs 2,454 dips in groups with no pop in 25 sessions
result: dips after a pop +0.19R vs no pop +0.18R (date-matched edge +0.18R, t 1.27); group still beating SPY since the pop +0.21R vs lost it +0.16R (t 0.67)
halves: after pop +0.49 / −0.07R; no pop +0.37 / −0.01R
layers: []
integrated: partly      # yes | partly | no | rejected
source: chat Nov 4, 2026 (Adam: "sub-themes pop and then I forget them … homebuilders popped today, I'd love one on the pullback"); breadth/popwatch.py study()
---
**Idea.** A sub-theme that pops (relative strength) and then cools off is the moment to buy a leader on its pullback; the risk is forgetting it.

**How it was tested.** Pop = the live Runners rule on the official close (4+ liquid members, 75%+ up, average move ≥ 1.25 own ADRs, +3 pts vs SPY,
1.2× dollar volume), first per group in 10 sessions. Stocks = lifecycle "base" (RS 70+ by 63-day rank among theme stocks, $10+, $20M+, 21 EMA over a
rising 50). Entry = the Lined-up buys trigger rule on the first 9/21 ribbon dip (no dip in the prior 5): buy the break of the dip-day high within 3
sessions, stop the dip low ≤ 1 ADR, 20 sessions. Compared with the same dips by stocks whose group had no pop in 25 sessions, per date.

**Result.** The pop adds nothing measurable: post-pop dips are as good as any leader's dip (both ~+0.19R). Still beating SPY since the pop is a
hair better (+0.21R vs +0.16R), not significant. Both halves agree it isn't worse.

**Caveats.** ~1.5 years, overlapping trades, survivorship; the second half lost for every dip rule.

**How it could be used.** Built as a memory, not an edge: v3 Groups → Pop watch (25-session list, state, vs SPY since the pop, leaders tagged
live when they're into the 9/21 EMAs). Info only; nothing re-ranks picks.
