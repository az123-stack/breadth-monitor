---
id: R-2026-10-28-theme-upkeep
title: Theme upkeep: reclassification worklist + weekly agent
date: 2026-10-28
status: process         # works | doesnt | mixed | untested | process
kind: data              # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: n/a
sample: Oct 27, 2026 close; 156 sub-themes, ~1,100 classified stocks, liquid universe ($5+, $10M+/day, 120 sessions)
result: first worklist 40 unclassified leaders, 30 poor fits, 4 stale tickers, 23 thin groups
halves: n/a (data hygiene, not a signal)
layers: []
integrated: yes
source: chat Oct 28, 2026 (Adam: "an agent checking whether tickers need reclassifying into our themes and sub-themes"); breadth/reclass.py
---
**Idea.** Every group signal (Strength, lifecycle, ignition, stair steps, Launch group points) is only as good as the sub-theme lists.
Stocks get missed (new leaders, IPOs), misfiled (ticker mix-ups) or go dead (acquired, renamed). Check it every week and fix it on purpose.

**How it was built.** Code measures, the agent reads, Adam decides. Each build computes a worklist (`reclass.build`): liquid stocks in no
sub-theme with RS 80+ or $100M+/day, with the 3 groups they trade most like (correlation of daily returns minus SPY, 120 sessions);
members whose correlation to their own group's other members is low while another group fits clearly better; theme-file tickers with no
bars in 5 sessions; sub-themes with fewer than 3 liquid members. A weekly agent (Sat 8:37 AM ET) researches the actual businesses and
publishes proposals (docs/agent/reclass.json, validated: worklist tickers only, exact sub-theme names or "NEW: Group / Name", a source per
move). Nothing changes until Adam says "apply reclass N"; decisions are logged (data/reclass_log.csv) and those tickers stay off the
worklist for 90 days.

**Result.** The first worklist found real errors on day one: ESS (Essex Property Trust, an apartment REIT) filed in Batteries & Storage,
almost certainly a ticker mix-up with ESS Tech; CME in Crypto Exchanges & Brokers (trades with Exchanges & Financial Data); ISRG in
Industrial & Surgical Robots (trades with Medical Devices); WBD, PSKY, ATKR and BZH with no recent bars.

**Caveats.** Correlation is a hint, not proof: a stock can decouple from its group for a month on its own news. That is why the agent must
check the business and Adam approves each move. Moving stocks changes group histories going forward only; past backtests used the lists as
they stand today (the usual hindsight caveat).

**How it could be used.** Cleaner groups for every group-level layer. Possible follow-up: re-run the lifecycle / ignition evidence after a
batch of fixes to see whether cleaner groups sharpen the edges.
