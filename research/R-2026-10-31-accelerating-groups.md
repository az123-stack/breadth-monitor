---
id: R-2026-10-31-accelerating-groups
title: Accelerating vs SPY: groups whose relative line speeds up (15 > 60 > 180 pace)
date: 2026-10-31
status: mixed           # works | doesnt | mixed | untested | process
kind: group             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 20 / 40 / 60 sessions
sample: 140 sub-themes, Jul 2025 – Oct 2026, every 5th session (52–60 dates), 241 independent episodes
result: accelerating + 60D ≥ +10% vs SPY → +2.2% / +4.9% / +6.7% vs avg group at 20/40/60 sessions (t 2.7 / 4.3 / 5.1); but vs groups equally strong on 60D without the speed-up −0.8 pts (n.s.)
halves: 40d +5.5 / +4.3; accel-minus-strong 40d −3.6 / +2.1 (flips)
layers: [oracle_accel]
integrated: yes
source: tools/oracle_study/accel.py (chat Oct 31, Adam on the v3 Oracle tab)
---
**Idea.** Adam, Oct 31, looking at Oracle: Defense IT & Services and IT Services & Consulting were speeding up against SPY on the 60- and 15-session charts. He wants a filter that catches runners like Cloud Communications months before the big part of the run.

**How it was tested.** Sub-theme = equal-weight index of its members (members liquid the prior day, daily returns clipped as in oracle.py). rel = index ÷ SPY. Pace N = (rel now ÷ rel N sessions ago − 1) ÷ N. ACCELERATING = 15-session pace > 60-session pace > 180-session pace, 15-session rel > 0. Outcome = the group's next 20 / 40 / 60 sessions minus the average group's. Every 5th session from Jul 25 2025 (needs 180 sessions of history). Dates are the unit; halves split by date.

**Result.**
| Signal | 20d | 40d | 60d |
|---|---|---|---|
| accel (any 60D > 0) | +0.7% t1.3 | +1.5% t1.9 | +2.2% t2.8 |
| accel + 60D ≥ +10% vs SPY | +2.2% t2.7 | +4.9% t4.3 | +6.7% t5.1 |
| … early (180D vs SPY < +25%) | +2.0% | +5.1% t3.7 | +6.8% |
| … running (180D ≥ +25%) | +3.2% | +6.7% t3.9 | +8.5% |
| plain 60D top 20% (no accel) | +2.6% t3.9 | +5.7% t5.5 | +8.2% t7.1 |
| plain 15D top 20% | +1.3% | +2.2% | +3.7% |

Control: among groups ≥ +10% vs SPY over 60 sessions, accelerating minus not accelerating = −0.8 pts at 20/40/60d (t −0.5 to −0.9; halves flip). Same inside the 60D top 20%. Episodes (first fire per group after a 30-day gap, n 241): +4.1% mean vs avg group over 60 sessions, median −0.6%, 49% beat, worst −45% (Lithium Apr 29 2026); best Memory Aug 12 2025 +133%, Custom Silicon Apr 7 2026 +122%, Semicap +76%. Cloud Communications first fired Mar 6 2026 (rel line 0.62 → 1.36 by Oct). Oct 30: 13 groups on, incl. IT Services (early, since Oct 15), Defense IT (early, since Oct 22), Identity & Security (running, since May 19).

**Caveats.** The edge is plain 60-day relative strength (group momentum), which the dashboard already measures (rotation tiers, lifecycle). Acceleration doesn't add to it. Fat-tailed: the average comes from a few big runners; the median episode is flat. ~15 months testable, bull-heavy, survivorship in the member lists, no costs.

**How it could be used.** Built Oct 31 as an Oracle filter (info only): chips "▲ Accelerating vs SPY", "· early", "Strong 60D vs SPY", Vs SPY column with stage + start date, for stocks and sub-themes. A place to look for the next Cloud Communications, not a ranking input.
