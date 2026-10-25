---
id: R-2026-10-24-orb-subtheme
title: "ORB x sub-theme: buy the best stock in the top 2 sub-themes (short the worst in the bottom 2) when SPY/QQQ breaks its opening range"
date: 2026-10-24
status: doesnt
kind: setup
horizon: same day (close / 2R) and 5 sessions
sample: ~2 years of 15-minute bars (Massive free plan), 703 of ~1,040 liquid sub-theme stocks (alphabetical A to ~M; download stopped at Adam's request), ~450 trigger days per variant
result: picks ~0R (long) and -0.08 to -0.3R (short) in every variant; vs buying any liquid stock on the same breakout +0.02 to +0.09R, t mostly < 2 (2R-exit longs t 2.0-2.3 only); first and second halves disagree (long picks +0.10R / -0.06 to -0.09R)
halves: e.g. QQQ 15-min, OR ranking, long, 2R exit - pick +0.12R / -0.06R; edge vs any stock +0.15 / +0.03
layers: []
integrated: no
source: tools/orb_study/ (download.py, study.py; data on branch orb-data). Adam's idea, Oct 24 2026
---
**Idea.** Each morning rank sub-themes by change + breadth (prior close or the opening range, with or without relative volume);
when SPY or QQQ breaks its 15- or 30-minute opening range, buy the best stock in the top 2 sub-themes, or short the worst stock in
the bottom 2.

**How it was tested.** 15-minute regular-session bars, trigger on a 15-minute close beyond the index opening range, entry at that
close, stop at the stock's own opening-range extreme, exits at the close / 2R / 5 sessions; R floored at 0.3 ADR, 0.1% cost.
Baselines: the sub-theme basket, the best stock anywhere, and any liquid stock on the same signal.

**Result.** No usable edge. The picks themselves average about 0R; shorts lose. The early partial run (353 tickers, t ~3 vs any
stock) faded to t < 2 at 703 tickers, and the halves disagree. Adam stopped the download (not worth the usage).

**Caveats.** 703 of ~1,040 tickers (alphabetical, so not random); 2 bull-heavy years; survivors only.
