---
id: R-2026-11-05-liquidity-magnets
title: Liquidity magnets: approaching an old level vs open sky (power gate failed → inconclusive)
date: 2026-11-05
status: untested        # works | doesnt | mixed | untested | process
kind: setup             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: tag within 20 sessions (H2a); Adam's management, cap 40 (H2b)
sample: Yahoo daily 2014–2026, 2,950 tickers (themes, S&P 500, Nasdaq-100, Russell 2000); confirmation set = episode starts 2015-03 → fills ending before 2025-09-05; 6,905 fills (C 5,661 + D 1,244); approaching (C) 611, open sky 2,278, far 516, stalled 1,168 (short 214 / touched 954)
result: NOT RUN — pre-registered power gates failed before any approaching outcome was opened. H2a: 249 of 611 approaching fills matched to open sky (B far: 60), MDE 18.6 pts vs gate 6, simulated pass rate 0%. H2b: counts OK but MDE 0.27R vs gate 0.15R, simulated pass 18%. Labels: H2a inconclusive, H2b inconclusive, stopped-short secondary 10%.
halves: n/a
layers: []
integrated: no          # yes | partly | no | rejected
source: chat Nov 5, 2026 (Adam: "price is magnetic to liquidity like overhead supply or ATHs" / "near overhead supply but hasn't hit it yet — prioritize?"); tools/warehouse/PLAN2.md v9.1 (graded 60 → 72 → 68 → 78 → 82 → 84 → 84 → 80 → 86% by fresh independent reviewers); daily.py + warehouse_daily.yml (branch warehouse-data); magnets.py, magnets_stats.py; data/warehouse/magnets/{validation.json, fills.parquet, power.txt}
---
**Idea.** A leader pulling back while an old peak / all-time high sits 1.5–6 ADRs above it gets pulled to that level (a magnet), so its
dip deserves priority over a dip of a leader already at all-time highs ("open sky").

**How it was tested.** Pre-registered (PLAN2.md v9.1), graded 86% before building. One source (Yahoo daily 2014+), point-in-time levels
frozen at the leg high, the step-1 leader filter, D and W dip entries, classes per fill (stalled / too close / approaching / far / open sky),
matched + model baselines, two-way clusters, simulated label power. Validation passed before outcomes: RS rank correlation with the
dashboard 0.992, breadth state agreement 97.5%, era strong-day shares 0.20 / 0.30 / 0.28 vs 0.28 on the overlap, era liquid sets
1,287–1,905 names, 57 tickers dropped for Yahoo-vs-Massive price mismatch, 2,019 bad bars screened, 536 split-screen ticker-years dropped.

**Result.** Inconclusive by the plan's own gates — the approaching / open-sky / far comparison is too thin once the matching cells
(month × breadth × D/W × listing-age tercile, d_lh ± 0.5–1 ADR) are applied, and outcomes cluster heavily by month (ρ 0.26) and ticker
(ρ 0.37) → design effect 2.5. 1,444 confirmation fills of the OLDEST listings were excluded because Yahoo's monthly history starts in 1985
while their first trade date is earlier ("starts late" rule) — the biggest single loss. No outcome of the approaching class was looked at.

**Caveats.** Survivor-only lists; liquidity floor = top 30% of the liquid set (stricter than $20M on the overlap: $20M = top 61%).

**How it could be used.** Nothing changes. A v10 would need: history back to ~2000 (Yahoo daily reaches it: more pullbacks, 2008/2011/
2015/2018/2020/2022 market groups), coarser matching (quarter × breadth × kind; listing age as a model covariate, not a cell), and a
completeness rule that accepts Yahoo's 1985 start as complete when the stock's pre-1985 high is below its post-1985 ATH (or just
treats pre-1985 peaks as unknowable and says so). Must be re-graded before any outcome is opened.
