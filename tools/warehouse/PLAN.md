# Trade scorecard · step 1 plan · v2 (Nov 4, 2026)

Adam (VEEV weekly chart): "VEEV is working off overhead supply it just hit. Should we trade the pullback into the daily EMAs or the
weekly EMAs, and when to do either? Other variables should rate the setup and recommend this stock or another with a better outlook."
v2 = revised after an independent review (v1 scored 55%: per-signal instead of per-pullback, biased paired test, supply measured as
pullback depth, levels.json not point-in-time, H1 not a statistic, clustering too thin, no power check).

## The question, as a decision
A leader has made a high and starts to pull back. Adam can (a) buy the first daily 9/21 dip, (b) skip it and wait for the weekly 9/21
dip, or (c) take the daily dip and, if stopped, re-enter at the weekly dip. **Which policy makes more R per pullback, and does the answer
flip when the leg just ran into old overhead supply after a big extension (the VEEV case)?** Nothing here changes a pick or card.

## Unit = the pullback episode (not the signal)
- **Leg high / episode start (day S):** a close at a 20-session closing high where the leader filter holds AT S:
  $10+, 20-day avg $20M+/day, dashboard RS ≥ 80 as of S, daily 21 EMA > 50 EMA and 50 rising over 10 sessions, weekly 9 > weekly 21.
  The filter is checked once, at S, identical for both entries (no re-check at the dip).
- **Episode end:** the first of: a new close above the leg high after any entry trigger; a close more than 1 weekly ATR(10) under the
  weekly 21; 40 sessions after S. A new episode can start only after the previous one ends (no overlapping episodes per stock).
- **Sample window:** episode starts from 2025-09-05 (weekly EMAs seeded from Nov 2024 need ~40 weeks to shed the seed, (20/22)^40 ≈ 2%)
  to 70 sessions before the last bar (2026-11-03), so every primary exit completes. RS before ~Nov 2025 uses < 252 sessions (partial
  formula) — reported, and the main result is re-run on starts ≥ 2025-11-07 only.

## Entries inside an episode (pre-registered, not tuned)
- **D (daily dip):** first session after S with low ≤ max(daily 9, daily 21) + 0.25 ADR, close ≥ daily 21 − 0.5 ADR, close ≤ daily 9 + 1 ADR.
- **W (weekly dip):** first session after S with low ≤ max(weekly 9, weekly 21) + 0.25 ADR, close ≥ weekly 21 − 0.5 ADR, close ≤ weekly 9 + 1 ADR,
  using the weekly EMAs AS THEY STAND that day (`emaprob.weekly_ema`: completed weeks + today's close as the current week's close).
- A bar that qualifies as both is tagged "both" (counted; it is the same trade for policies a and b).
- **Trigger / fill / stop (identical):** trigger = a later session's high ≥ the dip-day high within 3 sessions; fill = max(open, trigger)
  (gap above = fill at the open). Initial stop = dip-day low, never more than 1 ADR under the fill; risk floored at 0.3 ADR. Daily-bar order
  rule: if the fill day's low ≤ stop, count it as stopped at the stop (conservative; share of such trades reported). A gap below the stop
  exits at that open. No trigger within 3 sessions = "no fill" (rate reported per entry).
- **Primary exit (Adam's management, pre-registered as THE metric):** sell half at the close of the 4th session after the fill; then the
  stop on the rest moves to break-even; the rest exits on the first close under the daily 10 EMA; cap 40 sessions. R capped at 10.
  Secondary (reported, not tested): fixed 20 sessions or stop; and Adam's management with the stop at the ENTRY day's low.
  No commissions / slippage (stated).

## Policies scored on EVERY episode
- **P_D** take the first D (0R if no D or no fill). **P_W** skip D, take the first W (0R if none). **P_DW** take D; if it is stopped
  out, take the next W in the same episode. Per policy: R per episode (main number), share of episodes traded, R per trade, win %.
- Separately labelled conditional stat (not a test): "W's R in episodes where D was stopped".

## Variables, measured at the episode start S (what the trader sees at the leg high), no look-ahead
- **Overhead supply (point-in-time):** refetch Yahoo MONTHLY bars (full history, split-adjusted) for every candidate ticker once via a
  GitHub Actions job (the sandbox can't reach Yahoo; `levels.py` already has the fetcher) → `data/warehouse/monthly.json` (raw bars, not
  just peaks). For an episode starting in month M, use months ≤ M−1 only: old peaks = monthly highs above the 3 months on EACH side, all
  6 neighbours complete before M; ATH as of M−1. Highs from the last 6 months before S never count (that's the current leg).
  `hit_supply` = the leg high is within max(2%, 1 ADR) BELOW an old peak / ATH that is ≥ 6 months old, or pierced one by ≤ 3% and closed
  back under it. `room` = % from the leg high to the next old peak above (∞ if none). Spot check: Yahoo vs our bars + data/splits.csv on
  30 tickers incl. known spin-offs (CTVA); tickers that disagree > 2% are dropped and counted.
- **Extension (ONE variable for H1):** `ext` = (leg-high close − weekly 21 EMA at S) ÷ weekly ATR(10) at S. Two buckets: top third vs the
  rest, cut-off fixed on episodes starting in the first half of the window, applied to all.
- Logged for later steps (not tested now): `run` (% from 60-session low to leg high), weeks since the weekly 9/21 cross, RS, RS line at
  a 1-yr high, ADR, volume dry-up, sub-theme 60-day rank, breadth regime, post-thrust window, days to next earnings where known.

## Primary hypothesis H1 (the only confirmatory test)
Effect = (mean R per episode of P_W − P_D in the cell hit_supply = yes AND ext = top third) − (same difference in all other episodes).
H1 says the effect > 0 (waiting for the weekly dip is relatively better after a stretched run into old supply).
**Inference:** clusters = calendar week of S; cluster-robust t on the episode-level difference, plus a block bootstrap of 20-session
blocks (2,000 draws) for the 95% interval; and the sign of the in-cell P_W − P_D must hold in ≥ 2/3 of the independent market pullback
episodes (SPY 3%+ drawdowns from a 20-day high, merged within 10 sessions) that contain cell episodes.
**Pass (proven):** effect ≥ +0.15R, cluster t ≥ 2, bootstrap interval > 0, same sign in both time halves, ≥ 2/3 of market episodes, AND
each robustness check keeps the same sign and ≥ half the size (zero failures allowed): (i) starts ≥ 2025-11-07, (ii) without post-thrust
windows, (iii) without the top 1% of trades by R, (iv) leaving out each of the 3 sub-themes with the most episodes, (v) excess return vs
SPY over the hold instead of R (same sign), (vi) within breadth regimes strong / not strong (same sign in both).
**Power gate (checked BEFORE outcomes are computed):** count episodes per cell and market episodes. If the cell has < 40 episodes or < 4
market episodes, H1 is reported **inconclusive** (not "doesn't work"), and only the overall policy comparison is reported.

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
~14 months of usable episodes (Sep 2025 → Aug 2026), mostly a bull market, few independent market pullbacks; survivorship (delisted
/ renamed names missing); today's theme lists; monthly peaks approximate supply (no volume-at-price); no costs.
