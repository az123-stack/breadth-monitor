---
id: R-2026-10-27-theme-lifecycle
title: "Theme lifecycle: WATCH and BUY signals for blossoming themes"
date: 2026-10-27
status: works           # works | doesnt | mixed | untested | process
kind: group             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 20 sessions
sample: 127 sub-themes, Apr 2025 – Oct 2026 (after 120-session warm-up); BUY 515 signals on 208 dates, WATCH 426 on 213; 1,103 pullback trades in BUY groups
result: BUY groups +2.7% vs avg group next 20 sessions (t 3.5), +3.9% next 40 (t 3.4); same setup in weak breadth +1.4% but t −0.5; WATCH ≈ 0 (t −0.2) but 53% turn BUY within 30 sessions; pullbacks in BUY groups +0.74R vs +0.27R elsewhere (edge +0.31R, t 2.2)
halves: BUY +2.8% / +2.9% (20d); pullbacks in BUY groups +0.94R / +0.54R
layers: [lifecycle, group_ignition, money_flow_tiers, polished]
integrated: yes         # yes | partly | no | rejected
source: chat Oct 27, 2026 — breadth/lifecycle.py (evidence recomputed every build)
---
**Idea.** Adam: turn the "Anatomy of a Blossomed Theme" synthesis into signals: trigger a WATCH on a theme, activate a BUY, and
say which tickers to buy.

**How it was tested.** Daily stage per sub-theme (4+ members) from data up to that day only: forgotten (bottom fifth on 60-day
return vs SPY), first push (RS-rank +30 pts in 10 sessions from the bottom half, or 3 of 4 ignition checks), ignition (in the last
10 sessions), quiet build (top 40% on 60 days, within 15% of the 60-day high, inflow tier or rising relative trend 12 of 20
sessions), blossom (top 20%, within 3% of the 60-day high, ignition in 40 sessions or confirmed tier), fading (was top 20% in 40
sessions, now fading/outflow tier with < 50% above the 21 EMA). WATCH = first push or ignition WITH leaders. BUY = build or blossom
+ leaders + confirmed/steady money flow, breadth not weak (10-day ratio ≥ 1). Outcome: group vs the average group over the next 20 /
40 sessions, one signal per group per 20 sessions, t on per-date means, halves by date. Stock check: first touch of the daily 9/21
EMA ribbon (RS 70+, $10+, $20M+/day, 21 > rising 50 EMA), next open, stop 1 ADR, 20 sessions, by the stock's group state.
No-look-ahead test in tests/test_pipeline.py (stages for past days unchanged when later days are added).

**Result.**
- BUY +2.69% (20d, t 3.46, beat 54%, halves +2.8 / +2.9%); 40d +3.93% (t 3.35). First day of a BUY +2.77% (t 3.74).
  Breadth strong in 15 sessions +3.1% (t 3.5); mixed without that +1.5% (t 1.9, 40d ≈ 0) → half size.
- Same setup in WEAK breadth (ratio10 < 1): +1.4% mean but per-date ≈ 0 (t −0.5, halves +0.5 / −1.2%) → BUY waits ("ready").
- Build / blossom WITHOUT leaders or inflow: +1.1% (t 1.95) → the extra conditions roughly double the edge.
- Stages alone: blossom +3.0% (t 3.6), ignition +1.5% (t 1.8), build +0.8% (t 1.4), fade +0.7% (n.s.), forgotten −0.65% (t −2.7),
  first push −0.8% (t −2.7). Correction to the anatomy doc: the group edge is strongest AT the highs (blossom), not in the quiet
  middle; the "money stage" is about entries (pullbacks) inside build/blossom groups, not about waiting for a quiet group.
- WATCH: without leaders a first push lagged (−0.6%, t −2.5) and 30% turned BUY within 30 sessions; with leaders ≈ 0 (t −0.2) and
  53% turned BUY (ignition + leaders: +1.9%, 68%). WATCH = line up the names, not a buy.
- Pullback entries in BUY groups +0.74R (n 1,103, win 33%) vs WATCH groups +0.22R and other groups +0.27R; edge +0.31R (t 2.23,
  halves +0.94 / +0.54R) → passes.
- Oct 26 read: breadth weak (ratio10 0.87) → hold off; ready: Identity & Security, Cybersecurity Platforms, Data & Observability,
  Shale E&P, Defense IT & Services (all new), Enterprise SaaS, Integrated Oil, CROs, Consumer Brands, Design & Engineering Software.
  WATCH new: IT Services, Natural Gas Producers, Industrial Distribution, LNG & Midstream.

**Caveats.** ~2 years, mostly a bull market; today's group lists (survivorship, flatters all groups equally so the vs-average-group
measure cancels most of it); overlapping 20-day windows (~10 independent periods); no costs; stage thresholds set by reasoning from
the case studies, not tuned. Weak-breadth sample 142 days.

**How it could be used.** Built Oct 27 as information only (`lifecycle.py` → Theme lifecycle card at the top of Best Setups, Read-out
group-signal lines with the first tickers). Candidate for promotion: BUY groups as a context point for the swing picks (like the
ignition re-rank) or a filter on Best Setups pullbacks — needs Adam's approval (config.APPROVED_LAYERS). Watch the live record before
promoting; a push alert when a group turns BUY was offered as a scheduled task.

**Follow-up: lined-up buys (Oct 27, Adam: "stock buys when everything lines up and tickers are into their EMAs", top of Intraday).**
The live rule: a member of a BUY group (RS 70+, uptrend) dips into its 9/21 EMA ribbon; buy the break of that day's high within 3
sessions; stop at the dip low (max 1 ADR); hold 20 sessions. Daily-bar test: BUY groups +0.84R a trade (n 750, halves +0.98 / +0.69R,
29% win) vs other groups +0.13R and WATCH groups −0.15R (edge +0.49R, t 2.03, passes). 68% of dips triggered. Built as the "Lined-up
buys" card at the top of the Intraday tab (live from Google prices; info only). WATCH-group names are left out because their dips lost.

**Live record + alerts (Oct 27).** Every first dip of a BUY / ready-group leader is now frozen at the official close in
data/lineup_ledger.csv and settled with the backtest's exact rule, so the live record can be compared with +0.84R; ready (hold-off)
signals are logged too, to test the breadth gate forward. Phone alerts: GitHub checks every 5 minutes in the session
(breadth/lineup.py → docs/lineup_live.json) and a Claude scheduled task pushes new "in the EMAs" / "over yesterday's high" events.

**EMA location tags (Oct 27, Adam: OKTA read "in the EMAs" while ~0.9 ADR above the 9).** Each lined-up row now says where price is
against the live 9/21 EMAs: reclaimed the 21 / 9 (wicked under today, back over, within 0.5 ADR), on the 21 / 9 (within 0.3 ADR),
between them, under the 21, or "over the 9 · x ADR". Phone alerts for the dip now wait until price is on or reclaiming a line. Not
tested as an edge yet (follow-up: split the +0.84R trigger trades by where the dip day closed vs the 9/21).
