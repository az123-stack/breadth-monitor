---
id: R-2026-10-21-strength-on-weakness
title: Strength on Weakness: weekly stage-1 base, 9/21 WEMA re-anchor, breakout / nuzzle-pop
date: 2026-10-21
status: mixed
kind: setup
horizon: 13 and 26 weeks
sample: weekly signals Oct 24 2025 – Jul 24 2026 (13w) / Apr 24 2026 (26w); pops 1,850 (40 weeks), breakouts 206 (39 weeks)
result: pop 26w +14.8% avg, +6.6% vs avg stock (t 3.3) but only +1.6% vs other RS 70+ stocks (t 1.0); breakout ≈ RS 70+ stocks
halves: pop 26w vs RS 70+ +1.1% / +2.0%; pop 13w −0.3% / +5.1%; breakout 26w −7.5% / +6.4%
layers: [sow]
integrated: yes
source: breadth/sow.py (Adam's write-up + NRIX/APPN/AMPL/MTCH charts, Oct 21 2026)
---
**Idea.** Adam's position-trade setup on the weekly chart: a 6–24+ month stage-1 base around a flat/rising 50-week EMA with
2–3 "pumps" through it → first thrust → instead of selling off, the stock rests on the rising 9/21-week EMAs (the "black box")
→ breaks the box on volume with price > 9 > 21 > 50. His entry: buy when it nuzzles back into the 9/21 and take the next pop.

**How it was tested.** Weekly bars from our split-adjusted daily bars (≈104 weeks). Rules in `breadth/sow.py` (liquid $5+/$10M,
RS 70+, stack 9>21>50 with 21 rising, 50 WEMA ≥ 99% of 13 weeks ago, 2+ up-crosses of the 50 WEMA and 10+ weekly closes under
it in 78 weeks, black box = 10-week range ≤ 3 weekly ATRs with a low within 3% of the 21 WEMA, breakout = close over the prior
10-week high on 1.2× volume; nuzzle = low within 2% of the 9 WEMA, close ≥ 98% of the 21; pop = next week closes over the
nuzzle week's high). Signals only after 52 weeks of EMA warm-up, complete weeks only. Entry next session's open; exit the
weekly close 13 / 26 weeks later. Compared with the average liquid stock and the average RS 70+ stock bought the same day,
averaged per signal week. Exit on a weekly close under the 21 WEMA was tried in the prototype: worse than holding (win ~25%).

**Result.** Pops: 13w +5.5% avg (+3.2% vs avg stock, t 1.8; +2.4% vs RS 70+, t 1.6, halves −0.3/+5.1); 26w +14.8% (+6.6% vs
avg stock, t 3.3, halves +12.3/+1.3; +1.6% vs RS 70+, t 1.0, halves +1.1/+2.0). Breakouts: 13w +5.4% (+2.8% vs avg, t 0.9;
+2.2% vs RS 70+, t 0.7); 26w +10.1% (+4.1% vs avg; −0.6% vs RS 70+, halves −7.5/+6.4). Without the RS 70 floor the same
patterns were ≈ the average stock (pop 26w +2.7%, 2nd half −0.6%; breakout +1.3%). So the RS floor does most of the work;
the pattern adds a small, not significant amount on top. Live check Oct 20, 2026: NRIX nuzzling (trigger $26.34 = its
weekly high), APPN pop (last week), MTCH pop, AMPL riding the 9/21. 9 breakouts, 82 pops, 128 nuzzles, 63 riding, 11 extended.

**Caveats.** ~1 year of testable signals (50-week EMA needs a year of our 2-year history); 26-week holds from consecutive weeks
overlap, so the independent sample is roughly one market phase, mostly a bull market; survivors only; no costs. Multi-year
bases (Adam's 2021–2026 examples) can't be seen in 2 years of data — the base rule is a 78-week proxy.

**How it could be used.** Built Oct 21 as an information-only card on Trade Setups ("Strength on Weakness", unproven tag;
never touches the Top 2 picks). Re-test when more history exists (Massive Starter 5-year backfill would make this a real
test), and try: group strength / sub-theme leading as confluence, breadth regime at the pop, and a nuzzle depth filter.
