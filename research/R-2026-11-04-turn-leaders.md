---
id: R-2026-11-04-turn-leaders
title: Turning-point leaders: set up near highs at the low vs break out together after the thrust
date: 2026-11-04
status: mixed           # works | doesnt | mixed | untested | process
kind: setup             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 21 / 63 sessions
sample: 7 major thrusts Apr 2025 – Oct 2026 (2 deep: Apr 9 2025, Mar 31 2026), liquid $5+, $20M+/day; 4,360 fresh 52-wk-high breakouts (1,258 within 15 sessions after a thrust)
result: near-high / held-up names AT the thrust lagged at both deep lows (near 10% −11% vs avg stock over 63d; held up −14%); high-beta RS 80+ won (+19% / +27%). Fresh breakouts in the 15 sessions AFTER a thrust beat ordinary breakouts (+1.7% shallow / +4.1% deep vs −0.8%, 21d, t 3.5 / 2.9); with 2+ sub-theme peers breaking out too +4.3% / +6.9% (t 4.1 / 2.5); RS 80+ together after a deep thrust +14.8% (n 24)
halves: post-shallow +1.6 / +1.9; post-deep −8.0 (Apr 2025: early breakouts were defensives) / +6.6 (Mar 2026); ordinary +0.7 / −2.2
layers: [washout_thrust]
integrated: no          # yes | partly | no | rejected
source: chat Nov 4, 2026 (Adam: "at the April low the next leaders set up near highs and all broke out together, DELL, HPE … who's next?"); tools/turn_leaders/study.py + breakouts.py
---
**Idea.** At big lows the next leaders sit near their highs while the market falls, then break out together (DELL, HPE in April 2026).

**How it was tested.** Signal at the thrust-day close, buy next open. Part 1 (at the low): near 10/15% of the high, held up (off-high under
half of SPY's drawdown), RS line within 3% of its high, "setup" (near 15% + RS line within 5% + 10-session range ≤ 3 ADRs), setup with 3+ in
the same sub-theme, and the washout card's high-beta RS 80+ basket; vs the same rules on ordinary dates. Part 2 (after the low): fresh
close above the prior high (up to 252 sessions, none in the prior 20), within 1–15 sessions after a major thrust vs other days; "together"
= 2+ other members of its sub-theme broke out fresh in the last 5 sessions. Outcome = next open → 21 / 63 sessions minus the average liquid stock.

**Result.** At the low, the near-high idea was backwards at both deep turns (Apr 2025 near 10% −14.8% over 63d, Mar 2026 −7.2%); DELL and
HPE weren't near highs on Mar 31 (−12% / −15%, about SPY's drawdown) — they were cheap high-beta leaders that broke out 9–14 sessions later.
The "broke out together" part is real: post-thrust breakouts beat ordinary ones in every context tested, group clusters more so, and best
after deep thrusts with RS 80+. Mar 31 2026 cluster: semis equipment (AMAT, LRCX, KLAC, ONTO, UCTT, ICHR, COHU), ARM, VSH. Apr 2025 is the
exception: the first breakouts were defensives (banks, staples) and lost −8%; that thrust's real leaders broke out in June.

**Caveats.** 7 thrusts, 2 deep; overlapping windows; survivorship; today's sub-theme lists; Apr 2025 has only ~110 sessions of prior highs.

**How it could be used.** A "broke out together" list for the 15 sessions after any major thrust (sub-theme clusters of fresh 52-wk-high
breakouts, RS 80+), shown next to the washout card. Not built; test the defensive-vs-offensive mix of the cluster before trusting it.
