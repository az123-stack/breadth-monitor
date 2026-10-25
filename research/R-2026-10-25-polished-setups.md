---
id: R-2026-10-25-polished-setups
title: "Best Setups: EMA pullbacks and high tight flags inside leading groups"
date: 2026-10-25
status: mixed
kind: setup
horizon: 20 sessions
sample: Jan 2025 – Sep 2026; nuzzles 7,013 first touches (2,201 in leading groups); flags 2,071 (754 in leading groups)
result: nuzzle into the daily 9/21 EMAs by a leader that already went — leading groups +0.19R vs other groups +0.05R vs no sub-theme −0.13R, leading minus rest +0.19R t 2.57, halves +0.23 / +0.15 (works). High tight flag near the pivot — leading +0.12R vs other +0.02R vs none −0.13R, edge t 2.96, but leading halves +0.29 / −0.04 (fails the both-halves rule)
halves: nuzzle lead +0.23R / +0.15R; flag lead +0.29R / −0.04R
layers: [polished, launch]
integrated: yes
source: breadth/polished.py, tools/polished/study.py (Adam, Oct 25 2026: "a new tab for the polished setups: early names in the top groups, leaders that already went nuzzling the EMAs, and high tight flags about to break")
---
**Idea.** After the Launch list showed the group is the clue, Adam wanted one clean tab with three entry types, all inside the
leading groups: early base breakouts (the Launch list curl / early names), leaders that already went but are pulling into their
EMAs (late, so the entry matters), and high tight flags about to break.

**How it was tested.** Daily bars, split-adjusted. Leading group = sub-theme top third on 13-week return as of the PRIOR completed
week (no look-ahead). Nuzzle: 9+ weekly closes over the 50 WEMA with a weekly 9 > 21 > 50 stack, daily 21 > 50 EMA and 50 rising,
RS 70+, $20M+/day; low within 0.25 ADR of the daily 9/21 ribbon, close no more than 0.5 ADR under the 21 and within 1 ADR of the 9;
first touch in 5 sessions; next open, stop 1 ADR, 20 sessions. Flag: 30%+ leg (high vs the low of the 40 sessions before the
15-day window) into a high 3–15 sessions ago, flag depth (high → lowest low since the high) ≤ 25% and ≤ 3 ADR, last 5 sessions
≤ 2 ADR, close within 1 ADR of the high, above the 21 EMA, RS 70+; buy-stop at the high within 5 sessions, stop the flag low,
exit on a close under the 10 EMA after day 3 or 20 sessions. Groups: leading / other sub-theme / no sub-theme; per-date differences.

**Result.** Nuzzles: leading groups clearly better and positive in both halves (only ~26% of trades win: the 1-ADR stop is hit
often, winners pay). Stocks outside any sub-theme lose in both setups. Flags: leading groups better on average but the edge came
from the first half; flat since → unproven. Bug found and fixed while building: the first flag-low used the whole 15-day window,
reaching back into the leg (first-cut numbers: lead +0.11R n 310, other +0.12R).

**Caveats.** ~21 months, survivors only, no costs, today's sub-theme lists (mild hindsight on group membership), thresholds set by
judgement (not tuned). "Close to the EMAs" (no touch yet) is untested.

**How it could be used.** Built as the Best Setups tab (info only): Launch picks + live tracker on top, leading-groups table,
then 1 Early (Launch list A/B curl + early), 2 EMA pullbacks (tested), 3 high tight flags (unproven). Could feed the picks later
if the nuzzle layer holds in the forward log.
