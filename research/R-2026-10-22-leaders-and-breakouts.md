---
id: R-2026-10-22-leaders-and-breakouts
title: Market health: do leaders lead, and does breakout follow-through predict anything?
date: 2026-10-22
status: doesnt
kind: market
horizon: 20 sessions
sample: daily, Feb 2025 – Sep 2026 (410 days); first cut Nov 2025 – Sep 2026 (220 days)
result: no forward edge either way; every gauge's rank corr. with the next 20 sessions of the average non-leader stock within ±0.2, halves disagree
halves: e.g. breakouts-holding −0.03 / −0.42; leaders net breakouts −0.05 / −0.18; leaders under 50-day basket +0.10 / +0.12
layers: [market_health]
integrated: yes
source: breadth/leadership.py (Adam, Oct 22 2026: "if leaders stop breaking out, the rest of the market doesn't have a chance?")
---
**Idea.** Adam: leaders (top 10% RS) should tell on the rest of the market — when they stop breaking out, the rest has no
chance. And: count breakouts vs breakdowns across the universe (and whether breakouts follow through) to judge market health.

**How it was tested.** Leaders = top 10% of liquid stocks ($5+, $10M+/day) by RS Rating as of the previous session. Gauges:
share of leader-days at 20-day highs / lows (10 sessions), % above 21/50-day EMA, median off 3-month high, the leaders of 4
weeks ago now under the 50-day; universe base breakouts / breakdowns (beyond the 20-day high/low out of a ≤ 6-ADR base on
1.3× 50-day volume); "working" = breakouts from 5–25 sessions ago still above their level, return from the next open. Outcome:
next 20 sessions of the average non-leader stock (and SPY), by fifths, rank correlation, both halves. Also: do recent breakout
results predict the next breakouts' 10-session results (IC −0.09, halves −0.04 / −0.11: no), and do leaders' recent returns
predict their next ones (no).

**Result.** First cut (220 days): leaders weakest → rest +3.9% next 20 vs +0.6% when strongest; heavy leader breakdowns
+3.4%; breakouts failing +3.2% vs working −0.7%; leaders and the rest move the same week (corr 0.67), one week later 0.26,
reversing after 2–4 weeks. Full 410 days: all those effects shrink to noise (|IC| ≤ 0.2, halves disagree). So leaders do not
lead the rest in this sample, and weak readings were pullbacks that bounced. No bear market in the window: the classic
"leaders crack first at a top" is untested, not refuted.

**Caveats.** ~1.7 years, bull market with pullbacks (Apr 2025, Mar 2026); survivors only. Needs the 5-year history
(Massive Starter, incl. 2022) to test the top case.

**How it could be used.** Built as an info-only "Market health" card at the top of the Breadth tab: leaders verdict,
recovery check (4-week-ago leaders under the 50-day), breakouts vs breakdowns and "are they working", lists of cracking /
under-50 / breaking-out leaders, evidence recomputed every build. Re-test with longer history.
