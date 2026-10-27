---
id: R-2026-10-27-bad-day-holders
title: Do groups that hold up on bad market days blossom next?
date: 2026-10-27
status: mixed           # works | doesnt | mixed | untested | process
kind: group             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 21 sessions
sample: 127 sub-themes (4+ liquid members), Jan 2025–Sep 2026 signal dates; 55 SPY −1% days / 89 heavy-breadth days; ~11–17 independent 21-day windows
result: single red-day strong sessions no edge (−0.4% 21d, t −1.8). 30-day version: raw "held up best on bad days" LOST (top fifth −1.1% vs avg group 21d, bottom fifth +2.0%; same sign both halves). Beta-adjusted ("better than its beta predicts") top fifth +1.9% 21d (t 1.5) / +3.6% 42d, high-beta groups +2.8% / +6.7%, both halves positive — but adds ~nothing beyond plain 30-day relative strength (residual IC +0.05, t 0.6)
halves: raw top fifth −0.5 / −1.6%; beta-adjusted top fifth +2.4 / +1.9% (21d), high-beta +6.0 / +2.7%
layers: [the_trade]     # ids from data/layers.json this is evidence for (empty = new idea)
integrated: no          # yes | partly | no | rejected
source: chat Oct 27, 2026 (scratch scripts badday.py / bd2-4.py; rebuild from this description)
---
**Idea.** Adam: one tell of a blossoming theme may be that on clearly bad market sessions its stocks hold or even go up.

**How it was tested.** Splits-adjusted bars, sub-themes from data/subthemes.csv with 4+ members that day ($5+, $5M+ 50-day $ volume).
Group = equal-weight daily return (clipped ±30%). Bad day = (a) SPY ≤ −1% close to close, or (b) breadth: dn4 ≥ 2 × up4 and dn4 ≥ 150.
On each date, trailing 30 sessions with 3+ bad days: (1) avg group excess vs SPY on the bad days, (2) % of bad days the group closed ≥ 0,
(3) beta-adjusted "surprise" = group return − beta × SPY on bad days, beta = 60-day beta measured BEFORE the 30-day window.
Outcome: buy next open → close 21 / 42 sessions later, equal-weight group, minus the average group that date. Top / bottom fifth of groups,
Spearman IC, IC beyond 30-day relative return (rank residual). t from non-overlapping samples (every 21 / 42 sessions, averaged over offsets).
Independent recompute (explicit loop, every 5th date): beta-adjusted top fifth +1.9% at 21d, positive on 72% of 32 dates — matches.

**Result.**
- Raw version is backwards: groups that fell least on bad days lagged (top fifth −1.1% 21d, −3.0% 42d), groups that fell most led
  (+2.0% / +4.4%). Holding up on a down day mostly measures low beta (utilities, staples), and high beta won over these two years.
- "% of bad days held ≥ 0": +1.1% 21d on SPY bad days (IC +0.09, t 1.7) but fully explained by 30-day relative strength; breadth version ≈ 0.
- Beta-adjusted version is the right reading and points the right way: top fifth +1.9% (21d, t 1.5), +3.6% (42d), bottom fifth −0.6%;
  breadth-defined bad days +0.9% / +2.4%. Among high-beta groups (beta ≥ 1.1) top fifth +2.8% / +6.7% (halves +6.0 / +2.7% at 21d).
  Both halves positive in every cut. But after controlling for plain 30-day relative strength the extra information is ≈ 0 (IC +0.05, t 0.6).
- Plain 30-day relative strength alone: top fifth +1.6% 21d (t 1.6) — about the same as the beta-adjusted bad-day measure.

**Caveats.** Only ~55 SPY −1% days in 2 years and ~11 independent 21-day windows; t < 2 everywhere (fails the promotion rule).
Bull-heavy history, survivorship, today's group lists, no costs. Group betas drift (the 2026 AI-vs-defensives rotation pushed many betas near 0).
Oct 23, 2026 read (3 SPY bad days in 30 sessions: Oct 14, 16, 22): beta-adjusted holders = Defense Primes (98th pct), IT Services (95th),
Enterprise SaaS (79th); CROs 43rd, Life Science Tools 54th; among beta ≥ 1 groups Building Products, HVAC, Asset Managers led.

**How it could be used.** Not as a stand-alone rule. Possible info column on the Rotation / ignition card: "held up on bad days, beyond its beta"
as a tiebreaker for groups that are already leading, labeled unproven. Never use the raw "fell least" version — it selects defensives.
Re-test once there are more bad days (or with 5 years of history via Massive Starter).

**Follow-up: single-session tells (Oct 27, Adam: "CROs had great breadth and growth on a few bad days").** Event = a sub-theme up 1%+
with 75%+ of its members up on a bad day; same group within 10 sessions = one event; next open → 21 / 42 sessions vs the average group.
SPY −1% days: −0.4% (292 events, 41 dates, beat 53%, t −1.8); heavy-breadth days −0.4% (567); any red day (SPY ≤ −0.4%) +0.2% (845);
excluding defensives (beta ≥ 0.8) −1.3% / −0.1% / −0.2%. Repeats (2 or 3 such days within 20 sessions) +0.1% / +0.6%. Control: the same
move on a normal up day +0.6%. → No edge: a single strong session on a red day is not a tell. CROs' own record: strong on Sep 15
(+4.7%, 3/4 up), Sep 24 (+3.0%, 4/4), Oct 12 (4/4), Oct 14 (SPY −1.1%, 517 stocks down 4%: CROs +1.2% 4/4, Large-cap Pharma 16/20 up)
but weak on Oct 16 (−1.6%, 0/4) and Oct 22 (−0.7%, 1/4); its breakout came on Oct 21 with the TMO / DHR / MEDP earnings, a catalyst.
Memory keeps the tells from groups that later ran and drops the misses.
