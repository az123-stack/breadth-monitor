# Trade scorecard · step 1 plan · v3.1 (Nov 4, 2026) — graded 85% by the independent reviewer; v3.1 = its 9 wording fixes

Adam (VEEV weekly chart): "VEEV is working off overhead supply it just hit. Should we trade the pullback into the daily EMAs or the
weekly EMAs, and when to do either? Other variables should rate the setup and recommend this stock or another with a better outlook."
v2 = revised after an independent review (v1 scored 55%: per-signal instead of per-pullback, biased paired test, supply measured as
pullback depth, levels.json not point-in-time, H1 not a statistic, clustering too thin, no power check). v3 = second review (78%):
pin the leg high, require W to actually win in the cell, longer bootstrap blocks, 85-session buffer, power gate on informative episodes,
D/W ordering, policy (c) risk, pre-declared labels, current-leg-only supply exclusion, "no market pullback" bucket, weekly ATR defined.

## The question, as a decision
A leader has made a high and starts to pull back. Adam can (a) buy the first daily 9/21 dip, (b) skip it and wait for the weekly 9/21
dip, or (c) take the daily dip and, if stopped, re-enter at the weekly dip. **Which policy makes more R per pullback, and does the answer
flip when the leg just ran into old overhead supply after a big extension (the VEEV case)?** Nothing here changes a pick or card.

## Unit = the pullback episode (not the signal)
- **Leg high / episode start (day S):** an episode OPENS on a close at a 20-session closing high where the leader filter holds that day:
  $10+, 20-day avg $20M+/day, dashboard RS ≥ 80, daily 21 EMA > 50 EMA and 50 rising over 10 sessions, weekly 9 > weekly 21.
  While no entry has qualified yet, every new higher close MOVES the leg high (S = the day of the highest close so far); the filter is
  re-evaluated at each move but ONLY the check at the final S gates the episode. An entry bar counts only once some close on or before
  that bar (the entry bar's own close included; it is known at the signal close) is at least 1 ADR under the leg-high close. Episodes
  removed by this rule are counted; 0.5 ADR is run as an exploratory secondary (tight flags riding the 9 rarely pull back a full ADR). All episode variables are measured at the final S (the day of the leg high before the first dip).
  The filter is checked once (at the final S), identical for both entries, never at the dip.
- **Episode end:** the first of: a new close above the leg high AFTER the first qualifying dip bar (the pullback is over); a close more
  than 1 weekly ATR(10) under the weekly 21; 40 sessions after the final S. Entries not yet triggered die at the episode end; trades already
  filled run to their own exits. A new episode can open only after the previous one ends (no overlapping episodes per stock).
- **Weekly ATR(10):** mean of the last 10 weekly true ranges (completed weeks only, split-adjusted bars), as a % of the weekly close.
- **Sample window:** episode starts from 2025-09-05 (weekly EMAs seeded from Nov 2024 need ~40 weeks to shed the seed, (20/22)^40 ≈ 2%)
  to 85 sessions before the last bar (2026-11-03): 40-session episode + 3 to trigger + 40-session hold ≈ 83, so every exit under every
  policy completes; any trade still cut off is censored and counted. Real window ≈ 10 months of starts (2025-09-05 → ~2026-06-26,
  ≈ 205 sessions). The SPY 3%+ pullback groups in that window are listed in the power table before any outcome is computed. RS before ~Nov 2025 uses < 252 sessions (partial
  formula) — reported, and the main result is re-run on starts ≥ 2025-11-07 only.

## Entries inside an episode (pre-registered, not tuned)
- **D (daily dip):** first session after S (and after the 1-ADR pullback) BEFORE any W bar, with low ≤ max(daily 9, daily 21) + 0.25 ADR, close ≥ daily 21 − 0.5 ADR, close ≤ daily 9 + 1 ADR.
- **W (weekly dip):** first session after S with low ≤ max(weekly 9, weekly 21) + 0.25 ADR, close ≥ weekly 21 − 0.5 ADR, close ≤ weekly 9 + 1 ADR,
  using the weekly EMAs AS THEY STAND that day (`emaprob.weekly_ema`: completed weeks + today's close as the current week's close).
- A bar that qualifies as both is tagged "both" (counted; it is the same trade for policies a and b, adds 0 to the difference). If the
  first qualifying bar is a W bar (a fast drop straight to the weekly EMAs), the episode has NO D (P_D = 0R and P_W takes it); counts of
  D-first / both / W-first episodes are reported.
- **Trigger / fill / stop (identical):** trigger = a later session's high ≥ the dip-day high within 3 sessions; fill = max(open, trigger)
  (gap above = fill at the open). Initial stop = dip-day low, never more than 1 ADR under the fill; risk floored at 0.3 ADR. Daily-bar order
  rule: if the fill day's low ≤ stop, count it as stopped at the stop (conservative; share of such trades reported). A gap below the stop
  exits at that open. No trigger within 3 sessions = "no fill" (rate reported per entry).
- **Primary exit (Adam's management, pre-registered as THE metric):** sell half at the close of the 4th session after the fill; then the
  stop on the rest moves to break-even; the rest exits on the first close under the daily 10 EMA; cap 40 sessions. R capped at 10.
  Secondary (reported, not tested): fixed 20 sessions or stop; and Adam's management with the stop at the ENTRY day's low.
  No commissions / slippage (stated).

## Policies scored on EVERY episode
- **P_D** take the first D (0R if no D or no fill). **P_W** skip D, take the first W (0R if none). **P_DW** take D; if it hits its
  INITIAL stop before the half sale, take the next W in the same episode; if D never fills, or the episode is W-first, P_DW takes the
  first W (so P_DW ⊇ P_W's trades). Per policy: R per episode (main number), share of episodes
  traded, R per trade, win %; P_DW also as R per unit of risk taken (it can risk 2 units).
- Separately labelled conditional stat (not a test): "W's R in episodes where D was stopped".

## Variables, measured at the episode start S (what the trader sees at the leg high), no look-ahead
- **Overhead supply (point-in-time):** refetch Yahoo MONTHLY bars (full history, split-adjusted) for every candidate ticker once via a
  GitHub Actions job (the sandbox can't reach Yahoo; `levels.py` already has the fetcher) → `data/warehouse/monthly.json` (raw bars, not
  just peaks). For an episode starting in month M, use months ≤ M−1 only: old peaks = monthly highs above the 3 months on EACH side, all
  6 neighbours complete before M; ATH as of M−1. Plus swing highs from our daily bars (a high above the 10 sessions either side, both sides
  complete before S). Only highs from the CURRENT leg never count: anything after the leg's 60-session low before S. So a prior top of the
  same base (a double top 3–5 months back) does count. Each supply level is tagged with its source (monthly / daily) and age.
  `hit_supply` = the leg high is within max(2%, 1 ADR) BELOW a known supply level (above), or pierced one by ≤ 3% and closed back under it. `room` = % from the leg high to the next supply level above, from the SAME list as `hit_supply` (∞ if none). Spot check: Yahoo vs our bars + data/splits.csv on
  30 tickers incl. known spin-offs (CTVA): measure = each overlapping month's Yahoo monthly high vs the max of our daily highs that month;
  tickers where any overlapping month disagrees by > 2% are dropped from the supply variable and counted.
- **Extension (ONE variable for H1):** `ext` = (leg-high close − weekly 21 EMA at S) ÷ weekly ATR(10) at S. Two buckets: top third vs the
  rest, cut-off fixed on episodes starting in the first half of the window, applied to all.
- Logged for later steps (not tested now): `run` (% from 60-session low to leg high), weeks since the weekly 9/21 cross, RS, RS line at
  a 1-yr high, ADR, volume dry-up, sub-theme 60-day rank, breadth regime, post-thrust window, days to next earnings where known.

## Primary hypothesis H1 (the only confirmatory test)
Effect = (mean R per episode of P_W − P_D in the cell hit_supply = yes AND ext = top third) − (same difference in all other episodes).
H1 says the effect > 0 (waiting for the weekly dip is relatively better after a stretched run into old supply).
**Inference:** (1) clusters = calendar week of S; cluster-robust t on the effect. (2) A permutation test: shuffle cell membership among
episodes WITHIN each market group (10,000 shuffles) → one-sided p for the effect (p < 0.05 needed). (3) A moving-block bootstrap of 3
consecutive calendar months of S (2,000 draws) → 95% interval (coarse with ~10 months; reported, and its lower end must be > 0).
(4) The in-cell P_W − P_D must be > 0 in ≥ 2/3 of market groups. Market group of an episode = by its final leg-high date S: an SPY
pullback "contains" it if S falls between that drawdown's 20-day SPY high and its recovery to that high; each independent market pullback
(SPY 3%+ drawdown from a 20-day high, merged within 10 sessions) is one group, and all cell episodes outside any SPY pullback form ONE
extra "no market pullback" group.
**Pass (proven):** effect ≥ +0.15R, cluster t ≥ 2, permutation p < 0.05, bootstrap lower end > 0, AND inside the cell W actually wins:
in-cell mean(P_W − P_D) > 0 with cluster t ≥ 1.5, BOTH the effect and the in-cell P_W − P_D the same (positive) sign in each time half, same sign in both time halves, ≥ 2/3 of market episodes, AND
each robustness check keeps the same sign and ≥ half the size (zero failures allowed): (i) starts ≥ 2025-11-07, (ii) without post-thrust
windows, (iii) without the top 1% of trades by R, (iv) leaving out each of the 3 sub-themes with the most episodes, (v) excess return vs
SPY over the hold instead of R (same sign), (vi) within breadth regimes strong / not strong (same sign in both).
**Power gate (checked BEFORE R is computed):** count INFORMATIVE cell episodes = those where D or W at least triggered (fills only, no
outcomes), overall and in each time half, and the market groups they fall in. If the cell has < 40 informative episodes, < 15 in either
half, or < 4 market groups, H1 is reported **inconclusive** (not "doesn't work") and only the overall policy comparison is reported.
**Labels, pre-declared, exhaustive (first that applies):** **inconclusive** = gate not met · **proven** = every rule above ·
**info / promising** = passes effect, t, permutation, bootstrap, in-cell win and the halves, but fails exactly one robustness check or the
market-group rule · **doesn't work** = effect ≤ 0, or the bootstrap interval's UPPER end < +0.15R · **not shown** = everything else
(the gate is met but the result is neither clearly real nor clearly absent).
Re-run date: when 6 more months of bars exist (≈ May 2027) or after a longer-history purchase.

## Exploratory (labelled exploratory; no "proven" claims)
Overall P_D vs P_W vs P_DW; the same split by hit_supply alone and ext alone; `room` buckets; regime / post-thrust strata; the secondary
exits; D-vs-W market timing check = each W trade vs the average leader (filter at its own S) that did not dip that day, same hold.

## Outputs + checks
- `.github/workflows/monthly_levels.yml` + `tools/warehouse/monthly.py` → data/warehouse/monthly.json.
- `tools/warehouse/build.py` → data/warehouse/episodes.parquet (one row per episode: S, ticker, variables, every entry's fill / R /
  path flags under every exit, policy R) — the warehouse later steps extend with box, spring, HTF, SoW, EP entries.
- `tools/warehouse/study.py` → power table first, then H1, robustness, exploratory tables.
- Independent check: a fresh reviewer recomputes 30 random episodes from raw bars (entries, fills, stops, Adam-exit R) and H1 from the parquet.
- Card R-2026-11-04-daily-vs-weekly-dips + a Strategy Book page with the rule that results, if any.

## Known limits (written into the card)
~10 months of episode starts (Sep 2025 → late Jun 2026), so "inconclusive" is a likely, honest outcome, mostly a bull market, few independent market pullbacks; survivorship (delisted
/ renamed names missing); today's theme lists; monthly peaks approximate supply (no volume-at-price); no costs.
