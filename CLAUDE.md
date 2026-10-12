# Market Monitor (repo: breadth-monitor) — project context

Morning market dashboard modeled on Stockbee's Market Monitor, extended with
theme rotation (ported from the user's "Trading Dashboard v12" Google Sheet),
RS Ratings, Theme Strength, setups and a TradingView export.

- Repo: https://github.com/az123-stack/breadth-monitor (branch `main`)
- Live page: https://az123-stack.github.io/breadth-monitor/ (GitHub Pages, `/docs`)
- Owner: Adam (trader, not a developer — explain GitHub steps plainly, step by step)

## How it runs (fully automated, free)
- GitHub Actions `.github/workflows/daily.yml`, cron `17 10 * * 2-6` (≈6:17 AM ET Tue–Sat,
  covers the prior trading day). Manual inputs: `backfill_days`, `extend_history`.
- Data: Massive (formerly Polygon.io) free plan, 5 calls/min (12.5 s spacing).
  Key lives only in the GitHub secret `MASSIVE_API_KEY` — never ask the user to paste it.
- Workflow commits data + rebuilt `docs/index.html`; push step retries with
  `git pull --rebase -X theirs`. When pushing manually, pull with rebase first
  (the bot commits daily) and rebuild generated files if they conflict.
- Intraday: page fetches a published Google Sheet CSV of GOOGLEFINANCE prices
  ("Breadth Monitor – Live Prices", id `1_R08vZphNLMB4MUJSl_bNPx5DjVVy29tMV8WFaOQkSs`,
  URL in `config.LIVE_CSV_URL`) and recomputes themes/stocks in the browser.
  Browser math mirrors Python exactly. Breadth tab stays end-of-day.
  Sheet layout (row 1 header): ticker | index | symbol | price | closeyest | open | volume | marketcap | volumeavg;
  rows 2-3 `_asof` (=NOW()) and `_spytime`. A4 = IMPORTDATA of the raw GitHub `data/live_sheet.csv` (written every build
  by `intraday.write_sheet_csv`: pulse symbols, sector ETFs, theme stocks, S&P 500 + Nasdaq-100), so ticker changes
  reach the sheet on their own. D:I formulas (rows 4-1400) ask GOOGLEFINANCE for column C (`symbol`);
  marketcap/volumeavg only where index = 1. If the list ever passes ~1,390 rows, extend the formulas.
  The page parser reads the header, so old 2-column sheets still work.

## Code map
- `breadth/config.py` settings and thresholds · `massive.py` API client
- `store.py` parquet bars in `data/bars/` (500 trading days ≈ the free plan's 2-year reach, raw; splits applied in memory),
  themes/subthemes/names loaders, TradingView exchange map
- `update.py` entry point: `python -m breadth.update [--rebuild-only] [--backfill-days N] [--extend-history]`
- `metrics.py` breadth metrics, regime classifier, chart events
- `themes.py` sheet port: theme Score /8, rotation, setup score, long/short pulse, ranks, payload
- `strength.py` v2: RS Rating, RS-line ★/⚑ flags, tightness, Theme Strength
- `setups.py` momentum bursts (2LYNCH), anticipation, episodic pivots, regime trade stats
- `leaders.py` Leaders ranking → `DATA.themes.leaders`; Setups tab "Leaders" panel (Top 10 / One per group), recomputed live in the browser by `leadersJS`
- `tradesetups.py` Trade Setups tab: ATH Magnet, Leader Pullback, Rotation Rookie, Qullamaggie Flag, Minervini VCP (top 5 each by Leaders score;
  Q-Flag by flag tightness, VCP by contraction;
  "setups hit" angles, magnet levels) → `DATA.themes.trade_setups`; backtest of every setup + confluence → `DATA.themes.trade_bt`
- `review.py` "⚑ Review setups" flag (header button + card on Trade Setups) → `DATA.themes.setup_review`; checks regime change
  (3+ sessions vs baseline), setup dry 3 sessions, slump ≤ −0.15R over last 30 sessions (n ≥ 10), 3+ new top-5 themes, 30+ days.
  Baseline `data/setups_review.json`; daily counts `data/setup_counts.csv`.
  **When Adam says "review my trade setups"**: read the reasons in `setup_review`, the backtest by regime (`trade_bt`),
  propose adds/drops/retunes, build them, then run `python -m breadth.review --mark-reviewed --note "..."` and rebuild.
- `playbook.py` "Today's playbook" card at the top of Trade Setups → `DATA.themes.playbook`: state = post-thrust (25 sessions
  after a major Breadth thrust / Follow-through, `metrics.thrust_window`) else breadth regime; ranks all 7 setup types
  (4 Trade Setups + bursts, anticipation, EPs) by backtested avg R in that state: Focus ≥ +0.15R, Selective ≥ 0, Avoid < 0,
  Unproven n < 15; shows the "if a thrust comes" ranking too. Setup cards follow the playbook order.
  The review flag also fires (⚡) the morning a major thrust prints, with the post-thrust playbook in the reason.
- Top 2 trades (`playbook.picks`, card at the top of Trade Setups): top 5 of each Focus setup (+ Selective if < 2
  actionable), keep ACTIONABLE ones (flag/VCP trigger within 1 ADR of close, `ACTIONABLE_ADR`; others buy next open),
  highest RS, ties on 60-day gain, one per sub-theme; the rest go to `pick_watch`. Replay (`trade_bt.pick_replay`) trades
  it the same way (next-session entry, trigger fills, 5-session hold, no stop) vs the average actionable candidate.
- Pick scoreboard (`ledger.py` → `data/pick_ledger.csv`, `DATA.themes.scoreboard`): logs picks each morning; next session
  entry (open, or trigger → may be "no fill"), stop 1 ADR / entry-day low (flag) / VCP stop, exit close 5 sessions later.
  Scores `ret` (with stop), `ret_nostop`, and `cand_ret` (avg candidate, next open, 5 sessions). Research export:
  `TS.backtest(..., signals=True)` returns per-signal features incl. `trig_adr`, `filled`, `fwd_next`.
- Conviction tags (`tradesetups.TAGS`, row/pick `tags`): ⚑ RS ahead, ★ RS high, RS 99, RS riser, burst, coil, top-10 market,
  top-2 theme, top-3 sub-theme, HTF; warnings EP/news, bottom-2 theme. `trade_bt.tag_stats` = each tag's 5-day result
  with vs without on past setup signals (actionable trading); t ≥ 2 → green outline "adds edge", t ≤ −2 → red. As of Oct 11 none ≥ 2.
- Whole-market leaders (`lists.strongest`, Setups tab Leaders → "Any theme"): all US stocks $10+, $20M+/day, RS ≥ 90,
  60% RS + 40% closeness to high, no theme weighting (catches lone runners like MRNA).
- `levels.py` all-time highs and old monthly peaks from Yahoo (free; Massive free plan only reaches ~2 years), cached in
  `data/levels.json`, fetched in the daily run for new/stale tickers (`config.LEVELS_ENABLED`; tests switch it off)
- `kq.py` KQ breakout screen → `DATA.kq` (Basing / Extended / Not this setup or failing a rule); "⬇ KQ list" button exports it to TradingView
- `intraday.py` Intraday tab config → `DATA.intraday` (index members + sectors from `data/index_members.csv`, pulse symbols,
  sector ETFs, the tracker's volume curve, day-type thresholds). The tab itself is browser-only (`renderIntraday`):
  market pulse (indexes, RSP−SPY, IWM−SPY, VIX, bonds, dollar, gold, oil, BTC, sector ETFs) · who's moving the index
  (SPX/NDX contribution = prior-close Google market cap weight × change, by stock and sector, day type Broad/Narrow/Mixed)
  · live 4% breadth on theme stocks with volume pacing · theme/sub-theme heat · in play (paced relative volume, gaps,
  gap-and-go vs fading) · your trades live (picks, setup rows, triggers/ATH, open scoreboard trades vs stops).
- `macro.py` Macro drivers strip → `DATA.macro`: Yahoo daily closes (CL, BZ, RB, HO, NG, GC, SI, HG futures, ^TNX, DX-Y.NYB, ^VIX,
  BTC-USD) fetched in the daily run (gated by `config.LEVELS_ENABLED`), cached in `data/macro.json`; derived 3-2-1 crack
  spread (2·RB·42 + HO·42 − 3·CL)/3 $/bbl; missing/stale (> 6 days behind our bars) series fall back to an ETF in our bars
  (USO, UNG, GLD, SLV, CPER, IBIT) or are dropped. Each tile lists the sub-themes it drives with their Strength.
  Compact strip on Breadth, full strip on the Rotation tab. Yahoo is blocked in Claude's sandbox: local rebuilds show ETF tiles.
- `rotation.py` Rotation trade ideas → `DATA.themes.rotation` (top card on the Rotation tab, `rotationIdeasCard`): equal-weight
  sub-theme index (4+ stocks) vs SPY. "Leading & accelerating" = line above a rising 20-day avg, within 3% of its 60-day high,
  top 20% of groups on 20-day relative move → ideas (max 6; a leading group with corr ≥ 0.8 to a chosen one joins it as "with");
  why-bullets (20-day vs SPY + rank, trend, Strength Δ20, % above 21 EMA, closest cousin, macro driver 1M); stocks $10+, ADR ≥ 3,
  above 21 EMA, RS ≥ 70, sorted by ADRs above the 21 EMA (near ≤ 1, fair ≤ 2.5, extended); buy above 5-day high, stop 1 ADR.
  Avoid = near 60-day relative low and falling; Turning = fresh cross (watch only). `bt` = next-10-session edge vs the average
  group by breadth regime, recomputed each build; banner = Act (current-regime t ≥ 2) or Watch.
  Findings (Feb 2025–Sep 2026): leading & accelerating +1.0% (t 3.1), strong breadth +2.2% (t 3.55, 62% win), mixed +0.3% (n.s.);
  fresh crosses no edge (−0.8% in strong, t −2.2); avoid list −0.4% (t −2.3), mixed −1.0% (t −3.4). Inside a leading group the
  member closest to its 60-day high lagged the group (t −2.0); nearest the 21 EMA slightly better (n.s.).
- Rotation tab (browser-only rendering): ideas card · pair chart (`pairCard`: two groups' equal-weight index, ratio and
  its 20-day avg; group rows carry `px`, 180 sessions, dates `themes.px_dates`; guided suggestions: `STARTER_PAIRS` (14 curated
  pairs, each with what a rising/falling ratio means; edit in template.html) and "Cousins pulling apart" (correlation of daily
  moves ≥ 0.7 over 120 sessions, 4+ stocks each, biggest 20-session ratio split, each group once); the chart header gives the
  verdict vs the 20-day average, the last crossing, and the pair's correlation in plain words) · theme timeline heatmap (`timelineCard`: rows carry `s_hist` = Strength for
  `themes.timeline_dates`, 90 sessions; ranks computed in the browser).
- Strength history uses `strength.group_inputs_many` (numpy, identical numbers to `group_inputs`, tested), which made
  the 90-day history cheaper than the old 30-day loop.
- Pick scorecard: `ledger.summary(..., history)` adds `card` (by setup, by playbook state on the pick date, by rank/month,
  results in R = ret ÷ risk to stop, risk floored at 0.3 ADR; `risk` column in the ledger) and `trade_bt.pick_replay.breakdown`
  (replayed #1 pick by setup / state / month + cumulative edge curve) fills the card until live picks close.
- `site.py` + `template.html` single self-contained page (tabs: Breadth, Intraday, Trade Setups, Themes, Rotation, Browse, Setups, Stocks; TradingView export modal)
- `data/themes.csv` (theme,ticker,role) 81 themes · `data/subthemes.csv` (group,subtheme,ticker) 127 peer groups (swept Oct 11: renames PSTG→P, BK→BNY, SATS→ECHO, ERJ→EMBJ; 21 dead tickers dropped; 154 strong names added)
- `tools/` build_themes, build_subthemes, evaluate (v1 vs v2) · `tests/test_pipeline.py` (run directly)

## Definitions
- Breadth universe: US common stocks ≥ $3 (ETFs/ADRs in themes excluded from breadth).
  4% up/down needs volume > prior day and ≥ 100k. T2108 = % above 40-day MA.
- RS Rating 1–99: 63/126/189/252-day returns weighted 40/20/20/20, percentile vs liquid stocks.
  ★ RS line vs SPY at 1-yr high today; ⚑ "RS line ahead of price": RS line 1-yr high within the last 5 sessions
  while price is still 3%+ below its 52-wk high (`strength.LEAD_DAYS`).
- Theme Strength 0–100: percentile composite of relative perf vs SPY 5–90D (50%),
  % above EMA21/50 (25%), median RS Rating (25%); groups < 5 stocks shrunk toward 50.
- Anticipation: RS ≥ 85, ≤ 10% off high, ADR ≥ 4, 5-day range ≤ 1.5 ADR, volume dry-up ≤ 0.7.
- EPs: gap 8–60%, 3× volume, ≥ $5, ≥ $20M traded.
- KQ screen: ADR ≥ 5, $20M+/day, top 5% on 1/3/6-month return, close > SMA50, SMA20 > SMA50, 30%+ leg in 60 days,
  ≤ 25% off high. Sections in order: event (10% gap on 3x vol or 8x vol day, 15 days) or flat MA (SMA20 rise < 0.9 ATR
  in 10 days) → reject; ≥ 1.5 ATR above SMA20 → extended; 10-day range > 3.5 ATR or 4+ SMA10 crosses → reject; else basing.
  Thresholds hand-calibrated on the Oct 9, 2026 candidates; screen proxies, not chart grades.
- Leaders score 0–100: 40% RS Rating + 25% strongest theme's Strength + 15% sub-theme Strength (none → 50)
  + 20% closeness to 52-wk high (at high 100, ≥ 25% off 0); stocks ≥ $10, no ETFs.
- Trade Setups (stocks ≥ $10; group = stronger of best theme / sub-theme Strength):
  ATH Magnet RS ≥ 90, group ≥ 80, ≤ 3% off 52-wk high, above 21 EMA, ADR ≥ 3, true ATH ≤ 2 ADRs away when known ·
  Leader Pullback RS ≥ 85, group ≥ 70, within 3% of 21 EMA, above 50 EMA, 4–20% off high, vol dry ≤ 0.9 ·
  Rotation Rookie theme up 10+ Strength ranks in 4 wks (≥ 55) or sub-theme up 15+ (≥ 60), RS ≥ 80 not falling,
  3–12% off high, 0–6% above 21 EMA · Qullamaggie Flag = KQ Basing, any theme, HTF tag at 90%+ leg; "on deck" = KQ Extended ·
  Minervini VCP = trend template (150/200 SMA live; 100/150 in backtest), RS ≥ 70, ≤ 15% off high, ranges 10d < 0.6×20d,
  20d < 0.8×40d, vol dry ≤ 0.9. (Coiled Leader was replaced by Qullamaggie Flag on Oct 11.)
  Backtest: new signals; ATH/Pullback/Rotation buy close, stop 1 ADR, exit 5 sessions. Q-Flag: buy above 5-day high
  within 5 days, stop entry-day low (skip if > 1 ADR), half out after 3 days, rest on close < 10 EMA (20 EMA variant
  reported). VCP: buy above 10-day high, stop 10-day low capped 8%, exit close < 50 SMA. R risk floored at 0.3 ADR.
- Header "⬇ Trade Setups" downloads today's top picks + every setup's top 5 (playbook order).
- TradingView export priority: top 10 any-theme stocks (lists.strongest) → bursts → anticipation → ⚑ → ★ → RS 99 → fast risers →
  top 2 themes → top 3 sub-themes (new names) → bottom 2 themes → EPs (off); de-duplicated (ETF section removed Oct 11).

## Findings so far (Feb–Oct 2026 history)
- Theme Strength ranks far more stable than Score /8 (rank corr 0.96 vs 0.79); neither predicts
  10-day theme returns, so weights were not tuned to the data.
- Setups pay only in strong breadth (bursts +0.16R, anticipation +0.18R; bursts −0.09R in weak);
  EPs without a catalyst check lose in every regime.
- Trade Setups (Mar–Oct 2026, mixed breadth): Rotation +0.29R, Pullback +0.22R, ATH Magnet +0.12R (tags the high 81%
  vs 76% for any near-high stock), Coiled +0.12R; RS 80+ baseline +0.10R. Confluence (2+ angles) ≈ same R as 1 angle.
- Limits: survivorship bias in backfill, small strong-regime sample, no costs, no intraday H/L/volume.

## Working preferences
- Start every answer with a TL;DR, then detail.
- Ship working changes; verify with `--rebuild-only`, the tests, and a headless browser check before pushing.
- Don't run long blocking polling loops.
