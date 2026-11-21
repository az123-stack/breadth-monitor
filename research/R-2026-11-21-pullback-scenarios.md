---
id: R-2026-11-21-pullback-scenarios
title: Pullback scenarios: what leads when big caps, small caps or both come back
date: 2026-11-21
status: mixed           # works | doesnt | mixed | untested | process
kind: market
horizon: 20 sessions
sample: 36 days with SPY down 4%+ over 20 sessions, Mar 2025 - Apr 2026 = only 2 independent episodes (Mar-Apr 2025, Mar 2026)
result: Next 20 sessions by scenario - both up, big caps lead (19 days): SPY +10.7, RSP +7.7, high beta +23.9, megacaps +19.2, semis +27.6, RS leaders (3-mo) +6.1, names that held up best +5.2, defensives +5.8. Broad leads (2 days): beta +23.5, all +10.8. More selling (15 days): beta -10.8, semis -13.5, defensives -8.8, held-up names -5.8, SPY -5.9. Rebounds were led by what fell most; "held up best" lagged every bounce. n = 2 episodes -> context, not a rule. Nov 20, 2026: SPY -11.5% off high, RSP -7.1, QQQ -19.9, IWM -15.9, SOXX -43.5; T2108 27.8 (washout rule needs <= 25 + a thrust).
halves: n/a (2 episodes)
layers: []
integrated: no
source: chat Nov 21 2026 (Adam: RSP/SPY and QQQE/QQQ rising but nothing going up; "run a scenario plan"); tools/scenario_study/study.py (arg = SPY 20d threshold, -0.04 used)
---
**Idea.** Adam saw equal-weight/cap-weight ratios rising with no themes rising. Checked: everything falling, caps faster (typical liquid stock -6.9% in 5d, 3/156 sub-themes up). Asked for a scenario plan.

**Method.** Signal = SPY 20-session return <= -4% (-5% gave 1 episode). Baskets fixed at the signal date: 3-month RS top 10% (bar history too short for the 12-month RS Rating before late 2025), top 10% 60-day beta, top 10% 20-day return into the signal ("held up"), Staples/Utilities/Health sub-theme groups, 8 megacaps, SOXX. Scenario labelled by what SPY and RSP did over the next 20 sessions (hindsight label, used only to ask "if X happens, what wins").

**Fits earlier work.** Connector study / Washout thrust card: after deep washouts (SPY -8%+, T2108 <= 25) RS >= 80 high-beta names led (+26% Apr 2025, +33% Mar 2026); shallow ones failed. Two-camps card: leaders in the losing camp tend to bounce hardest.

**Caveats.** 2 episodes, overlapping windows, survivorship, scenario labels use the future. Rerun when the current episode settles (~Dec 19).
