---
id: R-2026-10-27-earnings-clusters
title: Earnings clusters: a group's reports saying the same thing
date: 2026-10-27
status: mixed           # works | doesnt | mixed | untested | process
kind: group             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 20 sessions
sample: Jan 27 2025 – Sep 25 2026, 401 clusters (first per group per 20 sessions), 156 sub-themes
result: UP cluster → members that hadn't reported +1.9% vs avg group (t 1.93, 52% win); DOWN cluster → ~0 (t −0.02); group signed +0.5% (t 0.97)
halves: UP non-reporters +1.9% / +1.9%; DOWN +0.5% / −0.5%; group signed +0.2% / +0.8%
layers: [earnings_clusters]
integrated: partly      # yes | partly | no | rejected
source: chat Oct 27 2026; breadth/earnings.py (python -m breadth.earnings)
---
**Idea.** Adam (planned for the week of Nov 2, started Oct 27): when several companies in one group report in the same week and say
the same thing, that is a statement about the theme. Capture it in the write-ups, and check whether the group (and the members
that haven't reported yet) keeps going that way.

**How it was tested.** Bars only, so it can be replayed: an earnings-style day = gap ≥ max(3%, 1 ADR, ADR known the day before) on
2.5×+ the prior 50-day volume, $5+, $10M+/day; direction = the close vs prior close (mixed under 0.5 ADR). Cluster = a sub-theme
(3+ members) with 2+ reactions in the last 5 sessions and ≥ 2/3 the same way. First cluster per group per 20 sessions, known at that
day's close, measured from the NEXT close over 20 sessions vs the equal-weight average group; "quiet" = members with no reaction in
the window (the read-through trade). Signed by direction.

**Result.** UP clusters: the group +1.3% (t 1.5), its not-yet-reported members +1.9% (t 1.93, halves +1.9/+1.9). DOWN clusters: group
+0.3% (no follow-through), quiet members ~0 — bad news in a group did NOT keep spreading (priced in fast / snapback). Signed group
result +0.5% (t 0.97). Oct 26 live: Tower REITs UP (AMT, CCI, SBAC all reacted up, group +4.1%); Semicap Equipment DOWN (LRCX −12%,
ICHR −13%; the other 13 members −7.3%); Global & EM Banks DOWN (ITUB −20%, BSBR −13%).

**Caveats.** The bar rule catches non-earnings news too (deals, FDA, downgrades): the story writer confirms each with a search, and the
catalyst agent's earnings dates mark rows "confirmed" (carded names only). Clusters across groups overlap in time (earnings seasons),
so the t-stats overstate independence. ~2 years, bull-heavy, today's group lists. Not proven (t < 2).

**How it could be used.** Built Oct 27 as information only: `DATA.themes.earnings`, "Earnings clusters" card on the Trade Stories
tab, EARNINGS CLUSTERS block in the story fact sheet (am = official; pm adds today's reactions from the Google close snapshot), story
guide section **What earnings said:** (writer finds the common message with sources) and the stories guide adds confirmed clusters to
Trade Stories. Next test: UP cluster + group already in BUY (lifecycle) for the non-reporters; and a text layer — do clusters whose
reports AGREE (writer-confirmed) beat price-only clusters? Needs ~2 earnings seasons of the forward log.
