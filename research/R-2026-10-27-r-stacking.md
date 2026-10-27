---
id: R-2026-10-27-r-stacking
title: R stacking: do layers add up (or multiply) when combined on one trade?
date: 2026-10-27
status: mixed           # works | doesnt | mixed | untested | process
kind: process           # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 20 sessions (box trades)
sample: Box trades Jan 2025 – Oct 2026; retest bounce 1,664 / 2,117 trades, spring 1,369 / 1,612 (first / second half, split Dec 4 2025); ~42–48 yes/no conditions each
result: proven single layers stack about additively and hold (thrust window +0.37/+0.55R, ★ group +0.31/+0.28R); searched-for "synergy pairs" shrank from ~+0.5R to ~+0.05R out of sample; a 40-flag stacked model barely ranked new trades (IC 0.02, top fifth +0.14–0.24R vs bottom −0.10–+0.18R)
halves: see result (each number is first half / second half)
layers: [box_favorites]
integrated: no          # yes | partly | no | rejected
source: chat Oct 27 2026; tools/rstack/box_stack.py (results_box.json)
---
**Idea.** Adam: "this trade is 0.8R, that one 0.5R, but layered together they bring 1.3R — keep making this smarter." Can we give each
trade a stacked expected R built from every layer we've researched, including combinations that work better together than apart?

**How it was tested.** Box trades are the richest test bed (every past trade with ~40 market / group / stock conditions, same entry, stop
and exit). Everything is FOUND on the first half and CHECKED on the second: (1) single-layer lift (R with minus without); (2) synergy =
actual R when two conditions are both present minus base + lift A + lift B; (3) a shrunk additive model (ridge) on all flags, plus the
synergy pairs that held, scored on the second half (rank correlation and fifths).

**Result.**
- Single layers that hold in both halves are real and they stack roughly ADDITIVELY: thrust window (+0.37 / +0.55R), ★ leading group
  (+0.31 / +0.28R, which backs the Oct 27 approval), SPY above its 50-day (+0.26 / +0.20R); for springs the thrust window (+0.55 / +0.40R),
  theme top 20% (+0.40 / +0.66R), new lows beating new highs (+0.34 / +0.22R).
- "Synergy" pairs found by searching ~800 combinations mostly evaporated: first-half extra +0.44 to +0.69R → second half typically
  +0.0 to +0.1R (winner's curse). A few stayed positive but small. Combinations must be proposed first and then tested, not mined.
- Throwing all ~40 flags into one model barely ranked new trades (IC 0.02 retest, −0.01 spring). Fewer, proven layers beat more layers.

**Caveats.** One setup family, ~2 years, bull-heavy, today's group lists, trades overlap in time (t-stats generous).

**How it could be used.** The "stacked R" design that the data supports: (1) a TRADE WAREHOUSE with every setup's past trades on one
yardstick and the same layer columns (box, spring, lined-up dips, Best Setups nuzzles/flags, Launch picks); (2) expected R = setup base +
only PROVEN layer lifts, shrunk toward zero by sample size, with a combination counted only if it was proposed before testing and held in
both halves; (3) every live trade shows its stack ("+0.30 base, +0.28 ★ group, +0.45 thrust window = +1.03R expected"), logged and scored
forward like the other ledgers; (4) the Saturday Integrator re-runs it and proposes new combinations to test. Next step: build the warehouse.
