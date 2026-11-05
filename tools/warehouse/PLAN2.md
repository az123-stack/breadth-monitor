# Trade scorecard · step 2 plan · v9.1 (Nov 5, 2026) — graded 86% by an independent reviewer (bar 85%); v9.1 = its 3 wording fixes — liquidity magnets: approaching a level vs stalled under it

Adam (Nov 5): "price is magnetic to certain liquidity like the overhead supply or ATHs" and "if a stock is near overhead supply but
hasn't hit it yet, that might be better to prioritize, right?" Step 1 (PLAN.md v3.1) measured supply only at the leg high. Nothing here
changes a pick or card.
v1 60% → v2 72% → v3. v2's reviewer: power can't reach the pass rules on ~10 months (an MDE near 0.4R), at most 4 market groups, the
"independent" set shares tickers and dates, 29% of episodes lose their levels to Yahoo/Massive mismatches. **v3 fixes the root cause:
a long, single-source daily history** (Yahoo daily bars from 2014 via GitHub Actions), so the confirmation sample is a different
DECADE, not the same weeks with weaker stocks. Plus the v2 reviewer's ten wording fixes.
v3 → 68%: v4 adds a swing-high age cap and an "untraded" rule, one breadth definition validated on the overlap, stop rules for failed
validations, a survivorship rule for H2a, a second (far-class) baseline + listing age, cluster-aware MDEs, a few-groups rule, C ends
before D's dates, a bad-bar screen, a time-stable liquidity floor and a dose-response check across distance.
v4 → 78%: v5 = the section "v5 rules" at the end, which OVERRIDES any earlier wording it touches (stalled levels, untraded clock,
clustering, exact-d tags, simulated label power, stopped-short class).
v5 → 82%: v6 = the section "v6 rules" at the end (clustered power simulation, placebo reported only, ticker recycling / split
screen, all levels frozen at S, touched over the whole leg, a deterministic match cap, listing age from monthly.json, survivorship
condition, small wording). v6 rules override everything above them.
v6 → 84%: v7 = the section "v7 rules" at the end (early-era drift check, stopped-short target, stalled edge case, recycling test
wording, empty-cell fallback, power vs baseline B, S&P condition for H2b).
v7 → 84%: v8 rules (leg-internal levels excluded, pre-2014 untraded clock, permutation pool, multiplicity, ticker shock, a
less-selected survivorship subset).
v8 → 80%: v9 rules (complete pre-2014 history or no class, one liquidity floor, RS liquid set = strength.py, per-ticker warm-up,
drawdown covariate). Order of precedence: v9 > v8 > v7 > v6 > v5 > body.

## Data (new)
- `tools/warehouse/daily.py` + `.github/workflows/warehouse_daily.yml`: Yahoo v8 chart, interval 1d, period1 = 2014-01-01 → today
  (explicit period, not range=max, so bars stay daily), split-adjusted OHLC + volume, for every ticker in themes.csv / subthemes.csv,
  data/index_members.csv (S&P 500, Nasdaq-100) and data/russell2000.csv, plus SPY. Stored on branch `warehouse-data` as parquet parts
  (float32), resumable per ticker, budgeted like orb_study.yml, plain User-Agent "Mozilla/5.0 (breadth-monitor)", HTTP statuses logged.
  Survivors only (today's lists).
- **Bad-bar screen** (same for every class, before outcomes): a bar with high > 1.25 × max(open, close) whose next session's high is
  < 0.9 × that high has its high set to max(open, close); lows mirrored. Count reported.
- **One source for bars and levels:** levels inside the daily history are built from the same Yahoo daily bars (month highs = max of
  daily highs), so there is no cross-source mismatch. monthly.json is used only for peaks OLDER than the first daily bar (pre-2014 ATH /
  pivots); for those, the step-1 spot check (overlapping months within 2%) still applies and a failing ticker loses only its pre-2014
  levels (counted). Check before outcomes: Yahoo daily vs our Massive bars on the overlap (closes within 0.5% on ≥ 99% of days, else the
  ticker is dropped; counts reported).
- **RS:** the dashboard formula (63/126/189/252-day returns 40/20/20/20) as a percentile within this fetched set among liquid names ($3+,
  100k avg volume). Dates where the liquid set has < 500 names are dropped. Validation before outcomes: rank correlation with the
  dashboard RS on the overlap dates; **below 0.9 → stop, report, no H2 run.**
- **Breadth state** `strong` = ratio5 ≥ 1.5 AND ratio10 ≥ 1.5 (exactly build.py), recomputed on this set by the metrics.py rules (thrust
  windows likewise). Validated against `store.load_breadth()` on the overlap: if `strong` agrees on < 90% of days, the state used
  everywhere becomes SPY above / below its 50-day SMA (decided before outcomes, reported).
- **Liquidity floor:** the flat $20M/day becomes "20-day avg $ volume in the top 30% of the liquid set that day" (the share that $20M
  represents on the overlap is reported); $10+ stays.

## Samples
- **Discovery (D):** episodes whose final S falls in the step-1 window (2025-09-05 → 2026-06-26). Step 1 printed R by room / supply on
  these windows, and tag is tied to R, so D is treated as SEEN for both hypotheses: exploratory tables only.
- **Confirmation (C):** episodes with S from 2015-03-02 (after 252 sessions of warm-up for RS and the weekly EMAs) whose every fill + 40
  sessions ends before 2025-09-05 (fills that would run past it are dropped, counted), built with the identical step-1 code on the Yahoo
  set. C shares no episodes and no trade dates with D.
- Population (both): the step-1 leader filter exactly (RS ≥ 80, $10+, $20M+/day, daily 21 > 50 rising, weekly 9 > 21). RS 70–79 is an
  exploratory add-on, not in any test.
- Window end: fill + 40 sessions ≤ the last bar; censored trades counted and excluded.

## Unit, entries, timing
- Unchanged from step 1: pullback episodes; D (first daily 9/21 dip) and W (first weekly 9/21 dip) entries; trigger = break of the
  dip-day high within 3 sessions; fill = max(open, trigger); stop = dip-day low ≤ 1 ADR; risk floored 0.3 ADR; Adam's management (half at
  the 4th close, break-even, rest on the first close under the 10 EMA, cap 40, R capped 10). Secondary exit 20 sessions or stop.
- Each filled entry is scored (a "both" bar counts once, as D).
- Known before the fill f: ADR = `adr[f−1]`, breadth = `strong[f−1]`, RS = `RS[f−1]`; ext and levels as of S.

## Levels at the fill
- Levels are the step-1 `supply_levels` rules (monthly pivots with 6 complete neighbours before the fill month, ATH, daily swing highs ±10
  complete before the leg low; current-leg highs never count) on the sources above, plus two v4 rules:
  - **age cap:** daily swing highs older than 504 sessions at S are dropped (step 1's effective reach); monthly pivots and the ATH have
    no age cap;
  - **untraded:** a level counts only if no close between its date and the leg low exceeded it × (1 + band) (a level taken out on an
    earlier leg is gone).
- `lh` = leg-high close; band = max(2%, ADR at S).
- Levels between the fill and lh × (1 + band) are CONSUMED and ignored.
- `lv_up` = nearest level strictly above max(fill, lh × (1 + band)); ∞ if none.
- `d_up` = (lv_up − fill) ÷ (fill × ADR); `d_lh` = (lh − fill) ÷ (fill × ADR).
- Round numbers: exploratory second list only.
- **Scope:** "approaching" here means a leader pulling back whose next old level sits above its leg high. Stocks basing under old supply
  without a leader pullback are not in this unit.

## Classes per fill (exhaustive, first that applies)
1. **stalled** = the episode's `hit_supply` exactly as coded in build.py (close at S within −band … +3% of a level), applying to all its fills.
2. **too close** = d_up < 1.5. This is rare by construction (pullback ≥ 1 ADR plus level ≥ band above lh); its count is reported.
3. **approaching** = 1.5 ≤ d_up ≤ 6.
4. **far** = 6 < d_up < ∞.
5. **open sky** = no level above.

Tickers with no usable level history (no daily history before the leg, or dropped by a check) are excluded from every class, never open
sky. Counts per set and class, and the class mix of excluded vs kept, appear in the power table.
Exploratory bucket: "within 1 ADR above lh, not hit" (the most literal "near, not hit yet"). If "too close" has < 30 fills it is
reported as a count only. Before outcomes: class mix by era and by listing age.

## H2a — the pull (confirmatory on C)
Does an approaching fill reach its level more often than a comparable open-sky fill reaches the same distance?

**Outcome and precomputation**
- `tag20` = max high over f … f + 20 ≥ lv_up; tag5 / tag10 reported.
- Tags are precomputed for every fill on a d grid (0.25 ADR steps, 0.5 → 8). An open-sky fill evaluated at distance d reaches
  fill × (1 + d × its own ADR).

**Matched estimate**
- **Two baselines, both must clear the bar:** (A) open-sky fills; (B) far fills (under an old level > 6 ADRs away), each scored at the
  approaching fill's d. (B) separates the level from "under its old high vs at its high".
- Each approaching fill is matched (per baseline) to fills with the same fill month, breadth state, entry kind and listing-age tercile
  (sessions since the ticker's first bar), and d_lh within ±0.5 ADR.
  If there are fewer than 3 matches, widen to ±1.0; if still fewer than 3, drop the fill (counted).
- Match weights are capped at 5 uses per open-sky fill; the effective number of distinct matches is reported.
- Baseline = the matches' mean tag at the approaching fill's d. Effect = mean(tag20 − baseline).

**Model estimate**
- Logistic regression on approaching and open-sky fills: tag20 ~ approaching + spline(d; knots at the 10th / 50th / 90th percentiles of
  d among approaching fills) + d_lh + RS + ADR + ext + kind + listing age + month fixed effects. SEs clustered by fill week. Fitted
  twice (approaching vs open sky; approaching vs far; far fills take an approaching d the same way).
- Each open-sky fill takes the d of a randomly drawn approaching fill from its own month × state × kind cell. The effect is averaged over
  50 draws (seed 7 first). Effect = average marginal effect of approaching (pts).
- The d_lh distributions of both classes are reported before matching.

**Placebo**
- Gap = tag(d) − tag(d + 1 ADR); placebo effect = approaching gap − matched gap.
- It rules out pure momentum, not resistance. The magnet claim rests on the matched and model effects.

**Inference**
- Cluster-robust t by fill week.
- Permutation (10,000 shuffles): class labels are shuffled as each episode's (D-class, W-class) pair within month × state × kind strata.
  A fill relabelled approaching takes the d of a randomly drawn real approaching fill in its stratum, and the matched effect is
  recomputed in full. One-sided p.
- Market-group jackknife: drop each SPY pullback group in turn.

**Eras, groups and power**
- Eras (fixed now): 2015-03 → 2018-12, 2019-01 → 2021-12, 2022-01 → 2025-08.
- Market group = SPY 3%+ pullback containing the fill date (step-1 rule, merged within 10 sessions) or "no pullback".
- Power gate: ≥ 300 approaching fills with ≥ 3 matches (each baseline) in C, ≥ 60 in each era, and MDE (80% power, one-sided 5%) ≤ 6
  pts, with the variance inflated by the cluster design effect = 1 + (m̄ − 1)·ρ, m̄ = mean approaching fills per fill week, ρ = within-week correlation of the outcome among
  OPEN-SKY fills only (not the tested class; computed before the approaching outcomes are opened), n = effective distinct fills after the
  5-use cap; else **inconclusive**.

**Labels (first that applies)**
- **inconclusive**: the power gate fails.
- **magnet real** requires all of:
  - matched effect ≥ +5 pts, t ≥ 2 and permutation p < 0.05 against BOTH baselines;
  - model effect ≥ +3 pts with t ≥ 2 in both fits;
  - placebo effect > 0;
  - the same sign in all 3 eras, and era 3 alone (2022–2025, least survivorship) ≥ half the full-sample matched effect (baseline A);
  - ≥ 2/3 of market groups with ≥ 20 approaching fills share the sign (fewer than 3 such groups → this rule counts as failed);
  - no jackknife drop flips the sign.
- **repels**: matched ≤ −5 and model ≤ −3 pts, both t ≤ −2.
- **no pull shown**: everything else.
- **Dose-response (confirmatory-secondary):** the matched effect (baseline A) in d buckets 1.5–3 / 3–4.5 / 4.5–6 ADRs with a
  cluster-robust trend test. A "magnet real" result is reported as a NEAR magnet only if the 1.5–3 bucket alone is ≥ +5 pts with t ≥ 2;
  otherwise as "far pull only" (it then says nothing about "near supply, not hit yet").

**Reported beside H2a** (tagged approaching fills)
- break and hold: a close above lv_up within 5 sessions of the first tag;
- rejection: a close ≥ 1 ADR under lv_up within 5 sessions, with no close above;
- stall: no close above within 10 sessions.
- Tag curves P(reach x ADRs) per class.

## H2b — priority (confirmatory on C)
**Contrasts** (mean R per filled trade, Adam's management)
- **H2b-1 (primary):** approaching − open sky, the real choice.
- Secondary (reported): approaching − all others, shown with class weights; approaching − stalled.

**Inference**
- Cluster t by fill week.
- Permutation at the episode-pair level within market group.
- Wild cluster bootstrap by fill week (Rademacher, 9,999 draws) → 95% interval.
- Market-group jackknife.

**Power gate**
- ≥ 300 approaching and ≥ 300 open-sky fills in C, ≥ 60 approaching per era.
- MDE ≤ +0.15R (80% power), R SD pooled across all classes, variance inflated by the same cluster design effect (ρ from open-sky R);
  else **inconclusive**.

**Pass (proven)** requires all of:
- effect ≥ +0.15R, t ≥ 2, permutation p < 0.05, bootstrap lower end > 0;
- approaching's own mean R > 0;
- the same sign in all 3 eras and in ≥ 2/3 of qualifying market groups (≥ 20 approaching fills; fewer than 3 qualifying groups → the
  rule counts as failed, so the best label is info / promising);
- no jackknife flip;
- the robustness checks keep the sign and ≥ half the size:
  - (i) D and W separately;
  - (ii) strong / not-strong breadth;
  - (iii) without the top 1% of trades by R;
  - (iv) without the 3 sub-themes with the most approaching fills (index-only stocks grouped by GICS sector);
  - (v) the 20-session exit;
  - (vi) excess return vs SPY;
  - (vii) the most recent era alone. Survivorship bias grows with age, and it flatters recovering names, so a result that lives only
    in 2015–2021 fails.

**Labels (first that applies)**
- inconclusive (gate);
- proven;
- info / promising = every pass rule holds except exactly one robustness check or the group-sign rule;
- doesn't work = effect ≤ 0, or the bootstrap upper end < +0.15R;
- not shown.

## What a result means (fixed now)
- Magnet real + H2b proven → the scorecard ranks approaching dips above open-sky dips and uses lv_up as the first target.
- Magnet real, H2b not → the level is a TARGET / exit tool (sell into it), not a reason to prioritize.
- No pull / repels → no magnet credit. Levels above count only as room in the reward-to-risk check.
- D (the step-1 window) is read only as "does the recent year look like the decade".

## Exploratory (labelled; no "proven" claims)
- Exit-at-the-level vs Adam's management vs half-at-level.
- d_up buckets × breadth × post-thrust.
- Level source and age.
- Stacked levels.
- Round numbers.
- Stalled vs open sky on C, to test whether step 1's −0.25R lead repeats.
- The RS 70–79 add-on.

## Outputs + checks
- daily.py + warehouse_daily.yml → branch warehouse-data.
- `build.py --source yahoo` → data/warehouse/fills.parquet (per fill: set, era, class, lv_up, d_up, d_lh, tag grid, R, R20, xs, week,
  group). Kept on the data branch if it is over 20 MB.
- `magnets.py` → validation table (Yahoo vs Massive, RS correlation), power table, then H2a, H2b, exploratory → results_magnets.txt.
- Independent check: a fresh reviewer recomputes 30 random fills from raw bars, plus both effects.
- Card R-2026-11-05-liquidity-magnets, Strategy Book note, ROADMAP.

## Known limits
- Survivors only over 11 years, which flatters recovering names; check (vii) guards against this.
- RS is ranked within the fetched set, not the full market.
- Theme lists are today's.
- Monthly peaks approximate supply (no volume-at-price).
- No costs.

## v5 rules (override earlier text where they touch it)
1. **One level set everywhere.** `stalled` = close at S within −band … +3% of a level from the v4 level set (Yahoo-daily sourced,
   504-session age cap, untraded). Step-1 `hit_supply` is reported beside it for comparison only.
2. **Untraded clock.** A level is untraded if no close from the bar after the level's bar (daily swing high), or from the first session
   after its month (monthly pivot / ATH, incl. pre-2014), through the leg low exceeds level × (1 + band at S). The 504-session age cap
   counts sessions of the Yahoo series.
3. **Clustering.** Every "cluster by fill week" in this plan becomes: two-way clusters by calendar month of the fill × ticker (month
   alone if the two-way estimator fails; reported). The design effect uses m̄ = approaching fills per month and ρ = within-month
   correlation among open-sky outcomes. Permutation strata stay month × state × kind, shuffled at the episode level. Wild bootstrap
   clusters by month.
4. **Exact distances.** Each fill stores mfe5 / mfe10 / mfe20 = (max high over bars f … f + k, fill bar INCLUDED, ÷ fill − 1) ÷ ADR;
   since the level is above the fill and fill ≥ open, any fill-bar high at the level was reached after the fill price was. tag_k(d) =
   mfe_k ≥ d, evaluated at the exact d
   (no grid). The placebo uses mfe20 ≥ d + 1.
5. **Label power, simulated before outcomes.** MDEs use the t ≥ 2 critical value actually required. Then the FULL label rule (every
   condition: both baselines, both fits, eras, era-3 half rule, group / year rule, jackknife, dose bucket) is simulated 500 times on the
   real cell structure: outcomes for every fill drawn from the open-sky tag rate of its own month × state × kind cell (H2b: open-sky R
   resampled by month), with a true +6 pts (H2b: +0.15R) added to approaching fills. If the full rule passes in < 50% of simulations,
   the label is capped at **inconclusive**. The simulated pass rate is printed in the power table.
6. **Group rule replaced.** "≥ 2/3 of market groups with ≥ 20 approaching fills" becomes "≥ 2/3 of calendar years 2015–2025 with ≥ 30
   approaching fills share the sign (fewer than 5 such years → the rule counts as failed)", for H2a and H2b. Market-group jackknife stays.
7. **Stopped short (Adam's literal case).** `stalled` splits into **touched** (the leg-high bar's high ≥ level × 0.995) and **stopped
   short** (never touched; leg high closed within the band under it). Stopped-short fills are a named confirmatory-secondary row:
   (a) H2a for them = "does the next leg reach the level the last leg stopped short of", tag at that level's exact d, against both
   baselines, matched and model, same inference; (b) H2b row = stopped short − open sky in R. Reported with the same label words, marked
   secondary (no Holm family with H2b-1; a pass reads "supported, secondary").
8. **Reported, not tested:** S&P 500 / Nasdaq-100 names vs Russell-2000-only / theme-only names (survivorship split); dropped-fill share
   by month; liquid-set size per year and RS-80 hit rate per era; a model-adjusted H2b contrast with the H2a covariates; the d_up
   distribution per class; Yahoo ticker renames / split mismatches logged apart from price mismatches.

## v6 rules (override everything above where they touch it)
1. **Clustered power simulation.** In v5 rule 5 each simulated outcome = the fill's cell rate on the logit scale + a month-level shock
   (normal, variance set so the simulated within-month ρ equals the open-sky ρ); H2b resamples WHOLE open-sky months (all their fills'
   R together), not single fills. The < 50% cap applies separately to H2a, H2b-1 and each stopped-short row; the 1.5–3 ADR dose bucket's
   own simulated pass rate is printed.
2. **Placebo = "wall test", reported only.** It is removed from the "magnet real" conditions (a resistance-only level also gives a
   positive gap; a magnet that breaks through can give ≤ 0).
3. **Ticker recycling / split screen.** A ticker-year is dropped (counted) if a close-to-close jump within 3% of a split ratio (×2, ×0.5,
   ×3, ×⅓, ×1.5, ×4, ×0.25) is not reversed within 5 sessions and is not in data/splits.csv-style Yahoo split events, or if the
   ticker's first Yahoo bar precedes a different company's history (first bar's month < the first month in monthly.json by > 1 month,
   or a > 70% gap in price level at a rename date known from the step-1 renames list). Renames are logged apart from price mismatches.
4. **Levels frozen at S.** All levels and classes are built once at S: monthly pivots need all 6 neighbours in months ≤ month(S) − 1;
   the ATH = max high of months ≤ month(S) − 1 and of daily bars before the leg-low bar; daily swing highs complete before the leg low.
   Fills only change d_up / d_lh (distances from the fill price), never the level list.
5. **Touched** (stalled split) = max high from the leg-low bar through S ≥ level × 0.995; otherwise stopped short.
6. **Match cap, deterministic.** Approaching fills are processed in a random order (seed 7); each takes its matches in order of |Δ d_lh|,
   ties broken by date then ticker; a candidate already used 5 times is skipped.
7. **Listing age** = sessions since the first month in monthly.json (Yahoo daily start if none); terciles cut over all C fills.
8. **Wording.** Era and calendar year are assigned by fill date; RS liquidity uses the 50-day average volume; 2025 counts as a year in
   the year rule only if it has ≥ 30 approaching fills (it ends at the C cut-off); "kind" = D or W.
9. **Survivorship condition.** "Magnet real" (H2a) also requires a matched effect (baseline A) ≥ +3 pts in the S&P 500 / Nasdaq-100
   member subset alone (today's index lists; these names were large and liquid long before, so less selected by later recovery).
10. **Reported beside H2b-1 with equal weight:** approaching − far, raw and model-adjusted (the H2a covariates); and the share of tagged
   approaching fills whose tag came AFTER Adam's exit (a reach after you're out is not tradeable). RS validation (≥ 0.9) is also run
   against an RS built from monthly.json closes on 2016–2019 (reported; < 0.8 is flagged in the card).

## v7 rules (highest precedence)
1. **Early-era drift.** Before outcomes, report per era the share of strong days and the liquid-set size. If any era's strong-day share
   is outside 0.5×–2× the overlap share, or any era's median liquid set is < 1,000 names, the breadth state everywhere (all eras, all
   matching, strata and robustness) becomes SPY above / below its 50-day SMA. Listing-age terciles are cut within each era; the share
   of fills whose listing age is censored at the Yahoo daily start (no monthly.json) is reported.
2. **Stopped-short target.** For stopped-short fills the target is the level the leg stopped short of (the nearest such level above lh;
   it is NOT consumed for this row): d_ss = (level − fill) ÷ (fill × ADR). Matching uses d_lh as for approaching fills; open-sky and far
   fills are scored at d_ss.
3. **Stalled edge case.** A close at S above level × (1 + band) but within +3% of it (possible when band < 3%) counts as stalled →
   touched, exactly as the build.py rule reads.
4. **Recycling test wording** (replaces the second half of v6 rule 3): drop the ticker (counted) if the daily series' first month and the
   monthly.json series' first month differ by > 1 month, or their month-end closes differ by > 2% on any overlapping month.
5. **Empty cells in the model draw.** An open-sky (or far) fill whose month × state × kind cell holds no approaching fill draws its d from
   month × kind, then from the month, then is dropped; counts reported.
6. **Power vs baseline B.** The label simulation (v5 rule 5 / v6 rule 1) draws baseline-B outcomes from far-fill cell rates and baseline-A
   outcomes from open-sky cell rates, with the +6 pts added to approaching fills only; the pass rate counts both baselines.
7. **H2b survivorship condition.** H2b-1 "proven" also requires approaching − open sky ≥ +0.10R in the S&P 500 / Nasdaq-100 subset.
8. **Excess vs SPY** (robustness vi) = the stock's price return over the hold minus SPY's price return from Yahoo daily closes (both
   price-only, no dividends), same entry and exit dates.
9. **Reported:** open-sky / far fills reused at the 5-use cap, per era.

## v8 rules (highest precedence)
1. **No level from inside the current leg** (replaces v6 rule 4's month cut). Monthly pivots and the monthly part of the ATH use only
   months ending before the leg-low month; the stretch from the start of the leg-low month to the bar before the leg low comes from daily
   bars (daily highs, for the ATH and for ±10 swing highs complete before the leg low). No bar from the leg low onward ever forms a level.
   Frozen at S as before.
2. **Untraded clock across the 2014 seam.** For a level older than the first daily bar: from the month after the level through the month
   before the first daily bar, use monthly.json month-end closes; from the first daily bar on, daily closes (v5 rule 2 otherwise).
3. **Permutation pool.** Labels are shuffled only among approaching + open-sky episodes (baseline A) or approaching + far episodes
   (baseline B) within each stratum; stalled and too-close fills stay out. Stopped-short rows: stopped-short + the baseline class.
4. **Multiplicity.** H2a and H2b-1 are separate questions, each at its own threshold, no correction between them. Stopped-short rows
   are secondary and carry no correction (a pass reads "supported, secondary"). v5 rule 7's "Holm family" phrase is void.
5. **Ticker shock in the power simulation.** The simulated outcome adds a ticker-level shock as well as the month shock (variances set
   to match the open-sky within-month and within-ticker correlations), matching the two-way clustering used in inference.
6. **Less-selected survivorship subset** (REPLACES the subset in v6 rule 9 and v7 rule 7): names that were already in the top 500 of the
   fetched set by 50-day avg $ volume on 2015-03-02. "Magnet real" needs a matched effect ≥ +3 pts there too, and H2b-1 "proven" needs
   ≥ +0.10R there too. The today's-S&P 500 / Nasdaq-100 subset becomes a report only (it holds later winners added after they ran). The v7 rule 4 recycling test is labelled a weak screen.
7. **Reported:** share of fills tagged on the fill day itself; count of stalled-touched fills from the v7 rule 3 edge case.

## v9 rules (highest precedence)
1. **Complete level history or no class.** monthly.py is extended to every ticker daily.py fetches (same workflow, before any outcome).
   A ticker's episodes can be classed (any class) only if its monthly.json series starts within 1 month of its first listed month on
   Yahoo AND it passed every spot check (v7 rule 4, step-1 2% check on overlapping months). Otherwise its episodes are classed only when
   lh is above its highest monthly.json high (then open sky is certain); else excluded from every class, counted per class and era.
2. **One liquidity floor.** Population liquidity = 20-day avg $ volume in the top 30% of that day's liquid set (v4) — this replaces
   $20M everywhere, in C, D (rebuilt on Yahoo bars) and every subset; $10+ stays.
3. **RS liquid set** = exactly build.py's `liquid_all`: close ≥ config.MIN_PRICE ($3) AND 20-day avg SHARE volume ≥ config.MIN_AVG_VOLUME
   (100k) AND in the stock universe (no ETFs; ADRs as store.load_universe treats them; for non-universe fetched tickers, the Yahoo
   quoteType must be EQUITY). This replaces v6 rule 8's "50-day" wording.
4. **Per-ticker warm-up.** A ticker's episodes need ≥ 252 sessions of its own Yahoo bars before S (RS and weekly EMA seed).
5. **Model covariate:** drawdown from the all-time high at S (from the frozen level set) is added to both H2a fits and the
   model-adjusted H2b contrast.
6. **Practical:** matching is precomputed once per stratum; if 10,000 permutations exceed 2 hours, 2,000 are run (reported).
7. **Known limits add:** the fetched set never contains delisted names, so the era-3 and 2015 top-500 guards are partial; Yahoo symbol
   reuse is screened only weakly (v7 rule 4).

## v9.1 (the 86% reviewer's three fixes; highest precedence)
1. **Complete monthly history** (defines v9 rule 1): first listed month = month of Yahoo `meta.firstTradeDate`. A ticker is complete only
   if monthly.json's first bar is within 1 month of it AND every monthly.json bar is 25–35 days after the previous one. Series that came
   back quarterly or weekly (the ones `build.norm_monthly` had to normalise) are incomplete. monthly.py asks for interval 1mo with
   period1 = 0 (not range=max) to get true monthly bars where Yahoo allows.
2. **Bad-bar screen scope:** it applies only to level-forming bars (before the leg low) and to the 252-session RS / EMA inputs. Outcome
   bars f … f + 40 use raw highs. Reported: tag20 also with the screen on outcome bars, and the number of tags that change.
3. **Timing test in code:** an automated test fails the build if changing any bar ≥ f (fill session) changes a fill's class, d_up,
   d_lh, lv_up or stratum; S, leg low, lh, the dip day, ext and ADR inputs must all come from bars ≤ f − 1.
