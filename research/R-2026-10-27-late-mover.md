---
id: R-2026-10-27-late-mover
title: Top late mover: does the strongest stock after the morning window keep going?
date: 2026-10-27
status: mixed           # works | doesnt | mixed | untested | process
kind: stock             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: rest of day / 1 / 5 sessions
sample: Oct 2024 – Oct 2026, ~470 days, ~700 liquid sub-theme stocks (15-min bars, orb-data branch, A–PBR)
result: #1 mover since 10:00 (by ADRs) ≈ 0R every horizon; beats the avg stock into the close +0.07R (t 3.0) but not after costs; best variant 12:00 · RS 80+ · leading group · highest RS → 5d +0.21R (+0.15R vs avg stock, t 1.3)
halves: best variant +0.15 / +0.15 vs avg stock (5d); biggest-mover pick 5d −0.06 / +0.01
layers: [late_mover]
integrated: partly      # yes | partly | no | rejected
source: chat Oct 27 2026; tools/late_mover/study.py (results.json)
---
**Idea.** Adam (logged Oct 13, asked to build Oct 27): a top stock pick once the morning window settles, the strongest late mover.

**How it was tested.** Anchor = 10:00 ET price; decision at 11:00 or 12:00 (bar closes). Candidates: $5+, $20M+/day (prior session),
up 1%+ since 10:00 and beating SPY. Filters: RS 80+, sub-theme top third on 13 weeks, volume since 10:00 ≥ 1.5× its own 20-session
norm for that window. Entry next bar's open, stop = the day's low so far (floored 0.3 ADR), 0.10% costs; exits: today's close, tomorrow's
close, 5 sessions (stop checked on bar / daily lows). #1 per day vs the average candidate and vs the average liquid stock, paired by date.

**Result.** The biggest late mover keeps outperforming other stocks into the close (+0.07–0.08R vs all, t 3.0–3.3, both halves) but its
own result is ≈ 0R after costs, it doesn't carry into the next day (≈ 0) and over 5 days it lags the other candidates (−0.06R). Ranking by
volume or group rank: no better. The one variant worth watching: at 12:00, RS 80+ in a leading group, pick the highest RS → 5 days
+0.21R (+0.15R vs the average stock, halves +0.15/+0.15, t 1.3). The whole RS 80+ leading-group late-mover basket: 5d +0.13R (t 1.6–1.7).

**Caveats.** Only ~700 of ~1,040 planned stocks downloaded (alphabetical A–PBR), today's sub-theme lists, survivorship, Google prices on
the page lag up to ~20 min (the study used exact bar prices), the intraday stop needs live monitoring.

**How it could be used.** Built as an "Unproven" watch line at the top of the Intraday tab's Second-half movers card (`lateLeader`, picks at
12:00 ET from the 10:00 snapshot). Next: finish the 15-minute download (orb_study.yml) and re-test; try it only on days the theme is in BUY
(lifecycle) or in strong breadth, and as an entry for names already on the Launch / Lined-up lists.
