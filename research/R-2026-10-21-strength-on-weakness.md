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

**Prime positioned (added Oct 21, Adam's follow-up with PEB / ABCL / CNK charts).** Adam wants the names while they're still
IN the box, before the stage-2 leg: after 2+ pumps through the 50 WEMA, now holding above it. Rule (`features` → `prime`):
liquid, RS line (price ÷ SPY) above its 21-week EMA and above 13 weeks ago (his box names had RS Ratings 26–67 in the box, so no
RS 70 floor), 50 WEMA flat/rising, base (2+ pumps, 10+ weeks under in 78), 3–30 consecutive weekly closes over the 50 WEMA,
9 > 21 with the 21 rising, close within 2.5 weekly ATRs of the 50. Matches PEB Dec 2025–May 2026, ABCL May–Aug 2026, MTCH
May–Oct 2026. Backtest (first prime week, next open; vs any liquid stock over its 50 WEMA with an improving RS line):
13w +3.0% (+0.1% vs avg stock; −0.1% vs similar, t −0.1), 26w +12.3% (+2.5% vs avg, t 1.7; −1.2% vs similar, t −0.85, halves
−4.2/+1.6). Volume rising (10-wk avg ≥ 1.1× the prior 26) did NOT help (26w −1.3% vs similar vs −0.2% without). RS line at a
1-yr high +3.2% vs similar (n 48–64, not significant). Verdict: the box stage is found reliably but has no tested edge over any
stock holding its 50 WEMA yet. Pops (same build, RS ranked among $10M+ stocks): 13w +2.7% vs RS 70+ (t 2.0, halves +0.6/+4.9),
26w +2.8% (t 2.0, halves +2.7/+2.9) — closest to passing, but overlapping windows over ~1 year; still info only.
Oct 20, 2026: 172 prime (87 new in 4 weeks), e.g. BBY, CVLT, KDP, NWSA (RS line at 1-yr high), ABSI, PENG, PANW, FROG.

**Prime tightened (Oct 21 evening, Adam: BBY/CVLT/KDP/NWSA good; FROG late, PANW base too short, PENG not a nuzzle).** Separators
measured Oct 20: 50 WEMA 26-week rise — good +5% to +12% (and his box examples PEB +1–4%, MTCH +1%, AMPL −4%, APPN −7%) vs
FROG +55%, PANW +56%, PENG +114%; weekly closes under the 50 in 78 weeks — good 33–58 vs FROG 10, PENG 17, PANW 26. New rules:
prime needs slope26 ≤ +20% and 30+ closes under the 50 in 78 weeks; nuzzle needs an orderly dip (10-week high → week's low ≤
min(2 weekly ATRs, 25%); PENG dropped 50%). Result: prime 172 → 110, BBY/CVLT/KDP/NWSA on top, FROG/PANW/PENG out, PEB/MTCH/
AMPL/APPN box weeks still flagged. Backtest after the change: prime 26w +11.5% (+1.2% vs avg stock, −2.4% vs similar, t −1.5);
13w +3.2% (+0.4% vs similar). Pop (stricter nuzzle) 13w +1.2% / 26w +1.9% vs RS 70+ (t 1.2) — weaker than before. Still info only.
