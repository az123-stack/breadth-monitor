---
id: R-2026-11-15-ipo-supply
title: IPO supply: do funds sell AI winners to pay for a mega IPO?
date: 2026-11-15
status: mixed           # works | doesnt | mixed | untested | process
kind: market            # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 5-20 sessions
sample: 6 IPOs Mar 2025 - Nov 2026 (SpaceX $75B the only priced mega deal; CoreWeave, Circle, Figma, Klarna ~$1-1.5B; Anthropic in progress)
result: Funding-selling NOT seen before SpaceX (AI hw +12.2% vs SPY filing->pricing, 77th pct; crowded winners +7.1%, 91st pct). Proxy dump WAS seen - space stand-ins +30% vs SPY Apr 1->May 20, then -16.5% 5d / -28.9% 20d after pricing. AI hw after SpaceX pricing +9.1% 5d, -13.2% 20d. Anthropic so far (Oct 26->Nov 13): AI hw -7.6% (16th pct), winners -8.2% (14th pct), megacaps -1.7%; NVDA -23% but AVGO +7%, AMZN +8.5%. Small IPOs: nothing.
halves: n/a (one mega event)
layers: [trade_stories]
integrated: partly      # yes | partly | no | rejected
source: chat Nov 15 2026 (Adam: "is this downturn just freeing up funds for the Anthropic IPO, and the way to do that is take down Nvidia?"); tools/ipo_study/study.py
---
**Idea.** Adam: the pullback may be funds raising cash for Anthropic's ~$90B offering (825M shares at $70-78 + $26B placement;
pricing Nov 18, trading Nov 19), done by selling the old leader Nvidia. Academic support: Braun & Larrain (RFS 2009, 254 IPOs in
emerging markets) found stocks most like a big IPO fall relative to others in the IPO month, stronger for bigger IPOs; they note a
single IPO rarely moves a large developed market.

**How it was tested.** Split-adjusted closes, equal-weight baskets minus SPY: AI hardware (the 7 short groups of the AI-spending
story), space (Launch & Space Systems + Satellite Connectivity & Imaging), megacaps (NVDA AVGO MSFT GOOGL META AMZN TSM ORCL),
crowded winners (top 50 $10+, $20M+/day stocks by 63-day return at window start). Pre window = public filing -> pricing close
(15 sessions for small IPOs); post = +5/+10/+20 from pricing close. Placebo = every same-length window (step 3) for a percentile.

**Result.** See `result`. Placebo 15-session medians: AI hw +5.7% (10th pct -12.1%), space +1.9%, megacaps +0.3%, winners -0.8%.
Anthropic's pre-window weakness is low but inside the normal range (not below the 10th percentile). Nvidia's drop is idiosyncratic
(AVGO and AMZN rose over the same window; Nvidia is a buyer in the placement).

**Caveats.** n = 1 priced mega IPO, overlapping macro news (midterms Nov 3-5, Nvidia leadership news, Nov 17 earnings), today's
theme lists, survivorship. SpaceX's own AI side (xAI) muddies "which group is most like it".

**How it could be used.** Built as Trade Story `ipo-supply-anthropic` (Trade Stories tab): context and a trade plan, no score
change. Forward test to settle on ~Dec 17 (20 sessions after Nov 18): AI hw and winners vs SPY at +5/+20 after pricing, and
"Anthropic proxy" names after Nov 19. If OpenAI files, repeat. Rerun: `python tools/ipo_study/study.py`.
