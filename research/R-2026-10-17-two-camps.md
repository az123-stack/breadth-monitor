---
id: R-2026-10-17-two-camps
title: Two camps: stick with leaders while their camp is winning
date: 2026-10-17
status: mixed
kind: market
horizon: 21 sessions
sample: ~276 dates Apr 2025–Sep 2026 (daily), RS ≥ 90 names per date (~150); 1 strong-split episode (Jul–Oct 2026)
result: RS ≥ 90 in the winning camp +2.6% vs all stocks, losing camp −1.7% (21d); when leaders sit mostly in the winning camp +2.7% vs −5.1% (+8.6 pts, 205 days); when mostly in the losing camp it flips (+1.3% vs +2.4%, 126 days); camp momentum alone ≈ coin flip (50–53%)
halves: winning − losing camp, RS ≥ 90 excess: 2025 +4.4 pts (+5.0% vs +0.6%), 2026 +3.9 pts (+0.3% vs −3.6%)
layers: [rotation_tier]
integrated: no
source: chat Oct 17, 2026 (scratch camps.py + camps_stock.py; follows the connector study conn_lib.py)
---
**Idea.** Adam: the market sometimes splits into two camps that move against each other. Does the split tell us
which leaders to trade? Three questions: (1) does the camp that won the last month keep winning, (2) does a very
strong split predict anything, (3) should RS leaders be picked from the winning camp?

**How it was tested.** Each session from Apr 2025 (data ≤ that day only): tradeable stocks ($5+, $20M+/day, ETFs out),
60-day daily returns, z-scored, PCA. PC1 = the market; PC2 = the split. Split strength = PC2 ÷ PC1 variance.
Camps = top / bottom 20% of PC2 loadings. "Winning camp" = the camp with the better last-20-session return, so no
labels like "AI" or "defensive" are needed (the sign of PC2 flips day to day). RS Rating = dashboard math
(`strength.rs_raw/breakpoints/rate`). Outcome: buy next open, close 21 sessions later, minus the average tradeable
stock; averaged per date first so each date counts once. A second, separate stock-level script re-derived the camps
and confirmed the headline.

**Result.**
- Split strength jumped in July 2026: 0.15–0.46 before, 0.8–0.98 since; Oct 16, 2026 = 0.92 (98th percentile).
  The camps' contents rotate (Dec 2025 AI/power vs consumer; Aug 2026 energy vs consumer/real estate; Oct 2026
  AI infra/semis/power/metals vs consumer/financials/software/biotech).
- Camp momentum alone: no edge (winning camp kept winning 50% of days in 2025, 53% in 2026).
- RS ≥ 90 by camp (excess 21d vs all stocks): winning +2.6%, middle −0.6%, losing −1.7%. Positive in 12 of 18
  months; lost 6–15 pts a month in Jan–Mar 2026 (rotation).
- Controlling for the stock's own 1-month return: holds for weak/mid own momentum (+2.5 / +4.0 vs −0.6 / −0.5);
  adds nothing for the strongest own-momentum names (+1.2 vs +1.0).
- Decisive condition = where the leaders sit:
  - leaders mostly in the WINNING camp (205 days): winning-camp RS 90 +2.7% vs losing −5.1%, ahead 57% of days.
  - leaders mostly in the LOSING camp (126 days): reverses, losing-camp leaders +2.4% vs winning +1.3%, ahead 36%.
    The leaders' camp bounced in ~3 of 5 episodes (Aug–Sep 2025, Dec 2025, Feb–May 2026) and kept falling in 2
    (Nov 2025, Jun–Jul 2026).
- Strong split (ratio > 0.6, Jul–Sep 2026, 53 days): all stocks −1.1%, RS 90 −2.0%, leader-camp worst dip −11% on
  average — but it is one episode, so it can't be judged.
- Oct 16, 2026 state: leaders mostly in the LOSING camp (39 of 49 camp-tagged RS ≥ 90 names). Over 20 sessions:
  AI infra −11%, semis −8%, quantum −26%, space −20%; consumer +4.5%, software +4.3%; SMH −10.5% in 5 days.
  Average correlation among RS ≥ 90 names 0.08 (lowest on record): leaders are not moving as one block.

**Caveats.** Overlapping 21-day windows → maybe 6–8 independent episodes for the "where leaders sit" split; only one
strong-split regime; survivorship (delisted names missing); no costs; mostly a bull market; today's group lists.
Overlaps with rotation_tier (leading groups) and own momentum — the camp adds a little on top, not a new engine.

**How it could be used.** Context tile, not a score: split strength, which camp is winning, and how many RS ≥ 90
names sit on each side. Reading: leaders in the winning camp → stick with them (the Qullamaggie "trade the leading
theme" rule, measured at the factor level); leaders in the losing camp → no edge either way, let breadth/thrust
and setups decide. Not built; Adam can ask for a Breadth-tab tile. Re-test when ~6 more months of data exist.
