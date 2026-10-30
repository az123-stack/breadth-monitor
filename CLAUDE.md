# Market Monitor (repo: breadth-monitor) — project context

Morning market dashboard modeled on Stockbee's Market Monitor, extended with
theme rotation (ported from the user's "Trading Dashboard v12" Google Sheet),
RS Ratings, Theme Strength, setups and a TradingView export.

- Repo: https://github.com/az123-stack/breadth-monitor (branch `main`)
- Live page: https://az123-stack.github.io/breadth-monitor/ (GitHub Pages, `/docs`)
- Owner: Adam (trader, not a developer — explain GitHub steps plainly, step by step)

## How it runs (fully automated, free)
- **When data arrives**: Massive's free plan returns 403 "not on plan" for a trading day until midnight ET, then serves it
  (measured Oct 13–14, 2026 via `data/massive_publish.csv`: 403 every 15 min 20:28–23:58, published 00:13). So no evening run can
  get the same day; the update runs just after midnight. GitHub Actions `.github/workflows/daily.yml` crons 04:17 + 05:17 UTC
  Tue–Sat (12:17 AM ET summer / winter; the other is a harmless rerun) and 10:17 UTC morning backup. GitHub's scheduler skipped every
  scheduled run Oct 10–13, then fired from Oct 14 (01:21Z, 06:00Z), so Claude scheduled tasks also dispatch it:
  "Market Monitor evening update kick" (despite the name, 12:25 AM ET Tue–Sat, input `wait_until=02:30`) and
  "Market Monitor daily update kick" (5:48 AM ET Tue–Sat backup; skips if the previous weekday is loaded). Dispatch via
  `gh api -X POST repos/az123-stack/breadth-monitor/actions/workflows/daily.yml/dispatches -f ref=main [-f 'inputs[wait_until]=HH:MM']`
  (gh GraphQL commands like `gh workflow run` are blocked in Claude sessions; use REST). `update.py --wait-until HH:MM` checks Massive
  every 15 min for the target day (today after 4 PM, else the last weekday) until it appears or HH:MM, logging each check to
  `data/massive_publish.csv`. Breadth tab shows a ⚠ banner when the last row is older than the previous weekday.
  Manual inputs: `backfill_days`, `extend_history`, `wait_until`.
- Data: Massive (formerly Polygon.io) free plan, 5 calls/min (12.5 s spacing).
  Key lives only in the GitHub secret `MASSIVE_API_KEY` — never ask the user to paste it.
- Workflow commits data + rebuilt `docs/index.html`; push step retries with
  `git pull --rebase -X theirs`. When pushing manually, pull with rebase first
  (the bot commits daily) and rebuild generated files if they conflict.
  Manual code pushes: plain `git pull --rebase` (no `-X theirs`) — other Claude sessions also commit code, and `-X theirs`
  silently drops their edits in shared files (Oct 16: it removed `MARKET_HOLIDAYS`; check `git diff <their commit> HEAD` shows only your additions).
- Intraday: page fetches a published Google Sheet CSV of GOOGLEFINANCE prices
  ("Breadth Monitor – Live Prices", id `1_R08vZphNLMB4MUJSl_bNPx5DjVVy29tMV8WFaOQkSs`,
  URL in `config.LIVE_CSV_URL`) and recomputes themes/stocks in the browser.
  Browser math mirrors Python exactly. Breadth tab stays end-of-day.
  Sheet layout (row 1 header): ticker | index | symbol | price | closeyest | open | volume | marketcap | volumeavg;
  rows 2-3 `_asof` (=NOW()) and `_spytime`. A4 = IMPORTDATA of the raw GitHub `data/live_sheet.csv` (written every build
  by `intraday.write_sheet_csv`: pulse symbols, sector ETFs, theme stocks, S&P 500 + Nasdaq-100, Russell 2000), so ticker changes
  reach the sheet on their own. D:I formulas (rows 4-3600) ask GOOGLEFINANCE for column C (`symbol`);
  marketcap/volumeavg only where index = 1, open skipped where index = 2 (Russell 2000 rows). Formulas run to row 3600; if the list passes ~3,590 rows, extend them.
  The page parser reads the header, so old 2-column sheets still work.
  Columns J:K `at10` / `at11` freeze each row at the first recalc after 10:00 / 11:00 ET on a weekday, using iterative calculation
  (File → Settings → Calculation, max 1 iteration — must stay ON) and self-referencing formulas. **Date-stamped since Oct 26, 2026**:
  rows hold "TICKER|price|volume|YYYY-MM-DD" and refreeze whenever the stored date isn't today (before 10:00 / weekends they keep the
  last value; the page ignores any date that isn't the sheet's session). The original Oct 13 version only reset when the sheet
  recalculated on a weekday BEFORE 10:00 ET, which it stopped doing, so the snapshot stayed stuck on Oct 13 until Oct 26 and the
  Second-half movers card was empty. A row whose ticker moved reads "TICKER|x|date" (ignored). J2/K2 hold the freeze time
  ("yyyy-mm-dd hh:mm" ET). The sheet's timezone is America/Los_Angeles, so formulas use NOW()+3/24 for ET — if the sheet timezone
  changes, fix those. J4:K4 formulas are copied down to row 3600 (Sheets API copyPaste PASTE_FORMULA).
  BACKUP (`breadth/anchors.py`, `.github/workflows/anchors.yml`): GitHub reads the published CSV at 10:00–10:45 / 11:00–11:45 ET and
  saves docs/anchors.json {date, at10/at11: {time, rows: {T: [price, volume]}}, health}; dispatched by the Claude scheduled task
  "Market Monitor · 10/11 snapshot kick" (10:02 + 11:02 ET Mon–Fri), crons as backup. Page (`fetchAnchors`, `resolveAnchors` in
  fetchLive): per slot, today's sheet freeze if it has one, else the backup, else nothing — stale anchors are removed from every row
  (`LIVE.anchorSrc`, `LIVE.anchorStale`), so the Read-out's `roLate` can't use old prices either. close.yml (4:25 PM) runs
  `python -m breadth.anchors check` and fails red when neither source had a snapshot. Tests `test_anchor_backup_snapshot`,
  `test_anchor_page_logic` (runs the page's parser in Node).

## Code map
- `breadth/config.py` settings and thresholds · `massive.py` API client
- `store.py` parquet bars in `data/bars/` (500 trading days ≈ the free plan's 2-year reach, raw; splits applied in memory),
  themes/subthemes/names loaders, TradingView exchange map
- `update.py` entry point: `python -m breadth.update [--rebuild-only] [--backfill-days N] [--extend-history]`
- `metrics.py` breadth metrics, regime classifier, chart events. New highs/lows (Oct 12): `nh`, `nl`, `nhnl`, `nh10`, `nl10`
  (liquid stocks with a year of history; high above every prior-year high), `near_hi` / `pct_near` / `pct_near10` (close within
  3% of the 52-week high), `spy_off_hi` (SPY bars passed as `bench`). Need 252 sessions of bars, so `merge` keeps stored values
  when a fresh one is blank. Events: "narrowing" (SPY within 1% of its high, pct_near10 ≤ 60% of its 60-day max, 3 days) and
  "highs_lead" (nh10 > nl10 for 3 days after nl10 led 15 of 20).
  Dollar flow (Oct 14): `dv_up` / `dv_dn` ($B of close × volume in rising / falling universe stocks $3+), `dv_net`, `dv_net5`, `dn_share`
  (% in falling), `dn_share10`, `dv_rel` (total $ vol ÷ prior 50-day avg); full ~2-year history from stored bars (median dn_share 47%);
  Breadth tab "Money in or out" tile row (≥ 60% leaving / ≤ 40% coming in), "Money in or out" chart (net $ bars + 10-day avg + dashed 20-day avg;
  legend buttons toggle each line, `MONEY_LINES`, remembered in localStorage "moneyLines"), table
  columns "$ in falling" and "Net $". Breadth tab: 4 tiles, two charts (highs/lows chart has an
  orange net line = nh10 − nl10 on the same mirrored scale), table columns.
  First look (Nov 2025–Sep 2026, ~210 days): high pct_near was followed by weaker SPY 20-day returns (corr −0.39, top quartile
  −0.4% vs bottom +3.3%); SPY-near-high divergence days −0.4% vs +1.2% (n 12). Context, not a timing signal.
  Volume tilt (Oct 17, `vtilt.py`, imbalance study): `vt_up` / `vt_dn` = median volume ÷ own 50-day avg of universe stocks ($3+, 100k avg
  vol, $5M+/day) that moved > 0.5σ (own 20-day vol) up / down; `vtilt10` = 100 × 10-day avg of log(vt_up ÷ vt_dn). `DATA.themes.vtilt`
  (date, v, pct, tier low ≤ 20th pct / high ≥ 80th, post = within `TILT_WINDOW` 25 sessions of a major thrust/follow-through, since,
  bt = SPY next open → 21 sessions by post/other × tier, recomputed each build, `post_dates`); Breadth tab tile row (`tiltTiles`,
  verdict Buyers pressing / Sellers gone (low, post-thrust) / Buyers tiring (low, no thrust) / Balanced) + chart (`chartTilt`).
  Study (Oct 2024–Oct 2026): up-volume % = dn_share (dropped); 90% days 4 in 2 yrs; "ease" (square-root impact) and dollar-weighted
  close-in-range: no edge. Tilt: low outside thrust windows SPY −4.2% next 21, up 14% (n 29); low post-thrust +2.4%, 73% (n 51);
  high +2.2–2.5% (68–88%); all days +1.3%, 68%. Extra info beyond ratio10/dn_share10/T2108 (residual IC ≈ 0.2–0.3). ~4 episodes per side.
  Thrust "unconfirmed" (Oct 17, EXPERIMENTAL, tile wording only; `vtilt.unconfirmed`, `TILT_UNCONFIRM_SHARE` 70): latest thrust's next 1–2
  sessions put ≥ 70% of $ volume in falling stocks → tilt verdict "Unclear: thrust not confirmed", context tile "Unconfirmed". Only 2 cases
  (Apr 9 2025 → 91% next day, still worked; Oct 15 2026 → 71%). Playbook / thrust_window unchanged.
  Who won the close (Oct 17): `clv_all` ($-weighted close location in the day's range, same stock filter as tilt), `absorb` (% of stocks
  down 1%+ closing in the top half), `fade` (% of stocks up 1%+ closing in the bottom half); Breadth tab `closeTiles` (verdict by clv_all
  percentile ≥ 80 buyers / ≤ 20 sellers / split). Test (Oct 2024–Oct 2026, SPY next open → 5/10/21): IC ≈ 0 for clv, absorb, fade, both
  halves; 5-day absorb +0.12 (2nd half −0.02); heavy days (dn_share ≥ 65) absorb ≥ 20% +2.1% SPY10 (n 12) vs < 8% +1.1% (n 38), all +0.5%.
  Descriptive only — labeled "no forward edge found". Oct 16, 2026: clv −0.41 (6th pct), absorb 1.8% (2nd pct); Oct 15 absorb 47% (98th).
  Hidden buying (FINRA, Oct 17, EXPERIMENTAL; `finra.py`, card R-2026-10-17-order-flow-proxies): free FINRA daily short sale volume
  (cdn.finra.org/equity/regsho/daily/CNMSshvolYYYYMMDD.txt, off-exchange trades, from Aug 2018, posted ~6 PM ET; Claude's sandbox can't
  reach it — `fetch` returns UNREACHABLE and the loop stops; GitHub Actions can) = raw input of SqueezeMetrics' DIX. Per ticker (liquid
  universe + SPY/QQQ/IWM) in `data/finra/YYYY-MM.parquet` (~19 MB / 2 yrs); `aggregate` → `data/finra_daily.csv` (sr_all, sr_spx, sr_ndx =
  $-weighted short share; srm_all median stock; offx_all off-exchange share of volume; sr_SPY/QQQ/IWM). Backfill: `.github/workflows/finra.yml`
  (input recent 0 = all missing days). update.py tops up the last 7 days (`LEVELS_ENABLED`) and `finra.build` → `DATA.themes.dix`
  (s5 = S&P 500 5-day share, norm = 120-day avg, dev = s5 − norm in pts, tier low/high = bottom/top 20% of dev, m5 median stock, bt = SPY
  next open → 21 by tier) → Breadth tab `dixTiles` (verdict, S&P share vs normal, typical stock + divergence note, what happened next).
  Test (486 days): detrended S&P 5-day IC +0.26 vs SPY 21d (halves +0.34/+0.19), residual vs ratio10/dn_share/T2108/vtilt +0.25; top
  fifth +3.1% (88% up) vs bottom +0.7%, all +1.4%; raw levels drift (2nd half +0.08); 60-day z weak; same-day link to SPY ≈ 0;
  offx and ETF shares noise. WATCH. Oct 16, 2026: S&P 44.2% vs normal 45.2% (35th pct), median stock 82nd pct.
- `themes.py` sheet port: theme Score /8, rotation, setup score, long/short pulse, ranks, payload
- `strength.py` v2: RS Rating, RS-line ★/⚑ flags, tightness, Theme Strength
- `setups.py` momentum bursts (2LYNCH), anticipation, episodic pivots, regime trade stats
- `leaders.py` Leaders ranking → `DATA.themes.leaders`; Setups tab "Leaders" panel (Top 10 / One per group), recomputed live in the browser by `leadersJS`
- `tradesetups.py` Trade Setups tab: ATH Magnet, Round Number Magnet, Leader Pullback, Rotation Rookie, Qullamaggie Flag, Minervini VCP (top 5 each by Leaders score;
  Q-Flag by flag tightness, VCP by contraction;
  "setups hit" angles, magnet levels) → `DATA.themes.trade_setups`; backtest of every setup + confluence → `DATA.themes.trade_bt`
- `review.py` "⚑ Review setups" flag (header button + card on Trade Setups) → `DATA.themes.setup_review`; checks regime change
  (3+ sessions vs baseline), setup dry 3 sessions, slump ≤ −0.15R over last 30 sessions (n ≥ 10), 3+ new top-5 themes, 30+ days.
  Baseline `data/setups_review.json`; daily counts `data/setup_counts.csv`.
  **When Adam says "review my trade setups"**: read the reasons in `setup_review`, the backtest by regime (`trade_bt`),
  propose adds/drops/retunes, build them, then run `python -m breadth.review --mark-reviewed --note "..."` and rebuild.
- `playbook.py` "Today's playbook" card at the top of Trade Setups → `DATA.themes.playbook`: state = post-thrust (25 sessions
  after a major Breadth thrust / Follow-through, `metrics.thrust_window`) else breadth regime; ranks all setup types
  (Trade Setups incl. Box Retest + bursts, anticipation, EPs) by backtested avg R in that state: Focus ≥ +0.15R, Selective ≥ 0, Avoid < 0,
  Unproven n < 15; shows the "if a thrust comes" ranking too. Setup cards follow the playbook order.
  The review flag also fires (⚡) the morning a major thrust prints, with the post-thrust playbook in the reason.
- Top 2 trades (`playbook.picks`, card at the top of Trade Setups): top 5 of each Focus setup (+ Selective if < 2
  actionable), keep ACTIONABLE ones (flag/VCP trigger within 1 ADR of close, `ACTIONABLE_ADR`; others buy next open),
  highest RS, ties on 60-day gain, one per sub-theme; the rest go to `pick_watch`. Replay (`trade_bt.pick_replay`) trades
  it the same way (next-session entry, trigger fills, 5-session hold, no stop) vs the average actionable candidate.
- Pick context re-rank (Oct 15; `playbook.context_fn` / `rerank`, called in update.py right after `rotation.build`, before the ledger
  records the picks): candidates are ranked by group context first, then RS / 60-day gain: +1 sub-theme ignited in the last 20 sessions
  with leaders (`ignition.recent` / rows); during an outflow episode (5-day avg `dn_share` ≥ 55%) +1 sold-hardest fifth and −1 held-up
  fifth over 5 sessions (`story.baskets`). Picks carry `ctx`, `ctx_notes` (appended to `why`); `playbook.context` = info + rule.
  Study (`tools/picks_context/`: capture.py wraps `TS.backtest(signals=True)` during a rebuild → signals.pkl; test.py, picks.py; 5,394
  signals Mar 2025–Oct 2026, actionable 5-session result): ignited 20d +1.90% vs +1.06% (t 2.4, halves +0.8/+0.9), + leaders +1.95% vs
  +1.10%; in outflow episodes sold-hardest group +6.5% vs +1.2% (n 47, t 2.6, both halves), held-up +0.6% vs +2.3% (t −2.6, both halves);
  money-flow tiers / flow > 0.25 / warming / group breadth: no consistent edge. Top-2 replay +1.96% a pick vs +1.66% RS-only (halves
  +2.07/+1.83 vs +2.06/+1.13; weak breadth +2.02% vs +0.52%). `trade_bt.pick_replay` still replays the old RS-only rule.
- Pick scoreboard (`ledger.py` → `data/pick_ledger.csv`, `DATA.themes.scoreboard`): logs picks each morning; next session
  entry (open, or trigger → may be "no fill"), stop 1 ADR / entry-day low (flag) / VCP stop, exit close 5 sessions later.
  Scores `ret` (with stop), `ret_nostop`, and `cand_ret` (avg candidate, next open, 5 sessions). Research export:
  `TS.backtest(..., signals=True)` returns per-signal features incl. `trig_adr`, `filled`, `fwd_next`.
- Conviction tags (`tradesetups.TAGS`, row/pick `tags`): ⚑ RS ahead, ★ RS high, RS 99, RS riser, burst, coil, top-10 market,
  top-2 theme, top-3 sub-theme, HTF; warnings EP/news, bottom-2 theme. `trade_bt.tag_stats` = each tag's 5-day result
  with vs without on past setup signals (actionable trading); t ≥ 2 → green outline "adds edge", t ≤ −2 → red. As of Oct 11 none ≥ 2.
- Whole-market leaders (`lists.strongest`, Setups tab Leaders → "Any theme"): all US stocks $10+, $20M+/day, RS ≥ 90,
  60% RS + 40% closeness to high, no theme weighting (catches lone runners like MRNA).
  "Mega caps" chip (Oct 15, `lists.mega`): every universe stock with Google market cap ≥ `config.MEGA_CAP` ($200B, from
  `data/close_snapshot.csv` via `strength.mega_caps`), same score, no RS floor, all shown (~60), Mkt cap column. ADRs (TSM) not in universe.
- `levels.py` all-time highs and old monthly peaks from Yahoo (free; Massive free plan only reaches ~2 years), cached in
  `data/levels.json`, fetched in the daily run for new/stale tickers (`config.LEVELS_ENABLED`; tests switch it off)
- `kq.py` KQ breakout screen → `DATA.kq` (Basing / Extended / Not this setup or failing a rule); "⬇ KQ list" button exports it to TradingView
- `washout.py` (Oct 16) Washout thrust card on the Breadth tab → `DATA.themes.washout`. Classifies each dashboard thrust
  (metrics.events kind "thrust") as deep (SPY ≥ 8% below its 60-day high within 15 sessions AND T2108 ≤ 25 within 10) or shallow;
  for ~21 sessions after a deep one it lists the 30 RS ≥ 80 stocks ($5+, $20M+/day) with the highest 60-day beta to SPY and tracks
  them from the next open. Settings `WASHOUT_*` in config.py. Evidence (connector study): deep Apr 9 2025 +26%, Mar 31 2026 +34%
  vs all stocks +9%/+8%; four shallow thrusts +3.5% avg vs +2.1%. No group/hub led rebounds (lead-lag ≈ 0); plain RS lagged in
  thrust windows. Only 2 deep events: experimental.
- `intraday.py` Intraday tab config → `DATA.intraday` (index members + sectors from `data/index_members.csv`, pulse symbols,
  sector ETFs, the tracker's volume curve, day-type thresholds). The tab itself is browser-only (`renderIntraday`):
  market pulse (indexes, RSP−SPY, IWM−SPY, VIX, bonds, dollar, gold, oil, BTC, sector ETFs) · who's moving the index
  (SPX/NDX contribution = prior-close Google market cap weight × change, by stock and sector, day type Broad/Narrow/Mixed)
  · live 4% breadth on theme stocks with volume pacing · theme/sub-theme heat · in play (paced relative volume, gaps,
  gap-and-go vs fading) · second-half movers (`lateMoversCard`: since 10:00 / 11:00 from the sheet's at10/at11 columns; chips for
  anchor, + Russell 2000, sort by move / move in ADRs / volume since vs normal (vol − anchor vol ÷ 50d avg × curve share); "catching
  a bid" = up 1%+ since and beating SPY, "losing it" = down 1%+ and lagging; pattern red→green / extending / new mover; sub-theme
  and theme averages since the anchor; $5+, $5M+ avg $ vol; warns when the freeze ran 15+ min late) · your trades live (picks, setup rows, triggers/ATH, open scoreboard trades vs stops).
  Russell 2000 option in "Who's moving the index" (Oct 13): iShares and Vanguard block scripted downloads from GitHub (tested),
  so Adam downloads the IWM "Detailed Holdings" CSV and Claude imports it: `python -m breadth.russell FILE` → `data/russell2000.csv`
  (ticker, mv = market value, sector, Google exchange prefix, asof). Each build `russell.weights(adjusted)` moves every weight by the
  price change since the file date (`intraday.set_bars`); payload `members.R2K`, `r2k_weights`, `r2k_asof`, `r2k_wdate`; card shows
  "IWM actual" vs reconstruction, no rel. volume. Re-upload caution on the card at 45 days (`russell.STALE_DAYS`, red at 75) — when
  Adam sends a new file, import it, rebuild, commit. Russell rebalances June + December. Sheet rows for R2K-only names carry index = 2
  and symbol `EXCH:TICKER` (price, closeyest, volume only), so the sheet is ~2,970 rows; formulas run to row 3600.
  Thrust watch (top of Intraday, `thrustWatchCard`) ← `intraday.thrust_watch` → `DATA.themes.thrust_watch`: live list = theme
  stocks + S&P 500 + Nasdaq-100 ∩ universe (~1,027); price-only up 4%+ ($3+) count vs its own 40-day avg: "thrust pace" ≥ 2.5×,
  "getting close" ≥ 2.0×; whole-market estimate = live × median ratio (~2.6); setup = washout in last 10 sessions (same rule as
  the thrust event); highs−lows backdrop. Calibration (Mar 2025–Oct 2026): corr 0.91 with the official count; 2.5× caught 10/13
  thrust-level days (2.0×: 11/13), 10 near-miss false alarms. Official signal still prints next morning.
- `premarket.py` + `.github/workflows/premarket.yml` → `docs/premarket.json` → **Pre-market tab** (`renderPremarket`, Oct 14): Yahoo
  `v7/finance/spark` (20 symbols/call, 150 calls ≈ 45 s) for every live-sheet symbol + futures/macro (ES, NQ, RTY, YM, CL, NG, GC, SI,
  HG, ZN, ^TNX, DXY, BTC, ETH); row = [pre price, prev close, volume (always 0: Yahoo reports no pre-market volume), last trade
  HH:MM, active 5-min pre-market bars]. Previous close: before the open Yahoo's `chartPreviousClose` is the close TWO sessions back (Oct 14 bug: every
  change included yesterday's move), so `parse` uses `regularMarketPrice` while `regularMarketTime` is before today's regular start;
  the page also cross-checks against Google (pre-open Google price = last close) and prefers it when they differ > 0.3%.
  User-Agent must be the plain "Mozilla/5.0 (breadth-monitor)" — a browser-looking UA gets 429
  on every call from GitHub runners. 4-min budget, `diag` in the JSON records HTTP statuses. Workflow loops every 10 min until 9:31
  ET, committing each snapshot (hourly crons 07:07–13:07 UTC Mon–Fri because GitHub fires them hours late — Oct 2026 they started after the open; waits until 4 AM ET, 5 h cap per run; the 5:48 AM Claude task dispatches it as backup). Page reads
  `premarket.json` from Pages every 2 min; `pmRows()` turns it into live-sheet-shaped rows (market cap = Google shares × pre price,
  ^SPX/^NDX = ES/NQ futures) and sets `ROWS_OVERRIDE` so the shared cards (`indexMoversCard`, `themeHeatCard`, `yourTradesCard`, also
  used by Intraday) read pre-market prices through `liveRow`. Cards: morning read (plain-English bullets), futures/macro/ETFs/sectors,
  what's moving the index, gap breadth on theme stocks, theme gaps, gappers (steady trading = 6+ active bars and a trade within 30
  min; $5+, $5M+ avg $ vol; gap in ADRs), possible EPs (8%+ gap, steady trading), your trades vs pre-market.
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
- `hve.py` Record volume card on Trade Setups (`hveCard`) → `DATA.themes.hve` (computed inside `strength.build_v2`): stocks
  (universe + theme tickers, $5+, $20M+ traded) whose volume beat every earlier day in our stored history (250+ sessions
  needed) in the last 5 sessions, one row per stock (latest record day, `also` = other record days), with day/date, × 50-day
  avg, × old record, move, close location, gap, record-day high/low, since, RS, $ traded; > 25 records on a day = index/expiry
  flag. "Ever" check: daily run fetches Yahoo full daily history for candidates (cached `data/hve_ever.json` as monthly max
  volume, refreshed after 30 days) → "Ever" / "2-yr" (bigger day before our window) / "2-yr*" (unchecked). Shown as a WARNING:
  up days on record volume lagged SPY (~−5% over 10 sessions, 37% beat SPY, t −2.5; −4% within 3; worse in strong/weak
  breadth; RS 85+ no better). One-off test: later re-break of the record-day high −1.2% vs SPY, pullbacks holding its low −0.7%.
  Table headers sort (`sortable`, state `UI.hve.sort`); card "⬇ TradingView" exports the rows shown in their current order;
  header "⬇ Trade Setups" adds "Record volume - up days (warning list)" and "- down days" sections; tickers are in `themes.tv`.
  Profile tags (`hve.profile`, `hve.short_status`, from the Oct 12 study): spike (gap ≥ 10%, day ≥ +20%, × avg > 20 or > 2.2× old
  record) → "Spike · short watch" with liquidity tag (thin < $5M / mid / liquid ≥ $25M avg $ vol) and status: wait (before day 3),
  watching (short below record-day low or a 3-day low), triggered (entry, stop = post-pop peak or 4-day high, % to stop, price
  since); pullback (liquid, ADR ≤ 10, 3–10% off 52-wk high) → "Pullback · watch"; other / down. Profile filter chips; Trade
  Setups download adds "short watch (turn triggered)" and "(spike, waiting)".
- Money flow card (top of Rotation, `moneyFlowCard`) → `rotation.flow`: Relative Rotation Graph per sub-theme (x = 100 × group/SPY ÷
  its 50-day avg, EMA5; y = 100 × x ÷ x 10 sessions ago; 15-session tails) + volume flow (10-session up-day minus down-day
  dollar volume ÷ total). Tiers: confirmed (leading & accelerating, or Leading quadrant 10/15 sessions + volume flow > 0.15),
  steady (Leading 10/15), new (entered Leading within 5 sessions), fading, bouncing (Improving), outflow (Lagging or x < 100 with
  flow < −0.15). Evidence per tier × regime recomputed each build. Findings: confirmed +0.8% vs avg group (t 2.9), strong +1.8%
  (t 3.4); steady mixed +1.0% (t 1.9); new ≈ 0; outflow −0.5% (t −2.5); bouncing −0.5% (t −2.4), strong −1.6%; weak breadth
  breaks the inflow tiers; volume flow alone ≈ 0. Lookup box maps a ticker (`stock_group`) or group name to its tier.
- "Where's the money going · today" (`moneyTodayCard`, Oct 14; top of the Rotation tab only — removed from Intraday Oct 15 at Adam's request): live from the
  Google Sheet, per sub-theme / theme (chips, 3+ stocks): avg change, vs SPY, up/n, paced relative $ volume, net $ flow = Σ dollar
  volume × sign(change) ($M/$B), flow × avg day (÷ group's 50-day avg $ volume), trend into today = `rotation.flow` tier at the last
  close, read (still being bought / fresh buying / leader being sold / still being sold). Bullets: leaving (top 4 net outflow), going
  into (top 4 net inflow), risk-on/off (avg XLU/XLP/XLV/XLRE vs XLK/SMH/XLY/XLC), IWM−SPY, RSP−SPY, groups up, leaders being sold.
  Whole-market block on top (`thrust_watch.dollar` from `intraday.dollar_flow`): share of the day's dollar volume in falling stocks on
  the ~1,027-stock live list, percentile vs ~2 years (sorted `hist`), last 10 sessions as mini bars, haven moves (TLT, UUP, GLD, VIX),
  and SPY next 5/10 sessions after similar days (bins: ≥ 80%, 70–80%, ≤ 20%, 20–30% falling). Calibration Oct 2024–Oct 2026: median
  47%; ≥ 70% days (n 35) SPY +1.3% next 5 sessions, up 83% (all days +0.3%, 58%); ≥ 80% (n 26) +0.7%, 65%. Not a buy signal.
  Oct 14, 2026: ≈ 73% in falling stocks (theme stocks alone 83.5%, ~95th percentile), TLT +0.7%, UUP +0.3%, GLD −1.5%, VIX +10.5%.
  Two-step layout (Oct 14): Step 1 verdict from the whole-market share in falling stocks (≥ 60% "money is leaving", ≤ 40% "coming in",
  else "mixed: rotating") with net $ today and 5 sessions (`dollar.last` third field = net $B); Step 2 always shows both tables, "Money coming in"
  then "Money going out" (Adam prefers both visible); on leaving days the inflow table is labeled as relative strength, not new money.
  Window chips (Oct 16): Today (live, above) / 3 / 5 / 15 / 30 / 90 days (`MT.win`, remembered in localStorage "moneyWin"; `moneyWindowBody`):
  official closes from `rotation.mhist` (`money_hist`: per sub-theme and theme with 3+ stocks, last 90 sessions of net $ flow $M, total $
  volume $M, equal-weight return bp; plus SPY bp; ETFs excluded) → change, vs SPY, stocks up over the window (stock d3/d5/d15/d30/d90), up
  days, $ volume vs 50-day avg × N, net $ flow, flow × avg day, tier, read; whole-market share/net from breadth rows dv_up/dv_dn.
  Oct 14 read: out of AI infra (Neoclouds −11.6% on 2.4× volume, custom silicon, AI servers, optical, hyperscalers, memory, quantum,
  BTC miners, SMR) into large-cap pharma, defense primes, biotech, managed care, oil majors, utilities; 16 of 102 groups up.
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
- Click-to-sort (Oct 14): every `.panel table` header sorts (generic delegated handler: `cellVal` parses numbers incl. %, ×, $, K/M/B,
  HH:MM, "Oct 13"-style dates, `data-v` overrides; first click = biggest / newest first, text A–Z). Choice kept in `AUTOSORT` keyed by
  section title + sub-heading + headers and re-applied by `reapplySorts` after every render/live refresh. Tables built with
  `sortable()` (data-driven sort) carry `data-own-sort` and are skipped. Tables with colspan rows aren't sorted.
- **Read-out tab** (Oct 14; default landing tab, `renderReadout`, `roPhase`): three `<details>` cards, the current one first and open
  (open/closed choice kept in `UIRO` until the phase changes). Phases (ET): pre 4:00–9:30 weekdays, live 9:30–16:00, post 16:00 →
  next weekday 4:00 (Adam: post-market read-out at the close from Google prices; official Massive data is used the next morning in
  pre-market). Pre = official close (`roMarket`: regime, breadth, money, thrust setup, playbook Focus/Avoid, recent signals, review
  flag) + Yahoo snapshot (`roOvernight`, via `pmRows`/`ROWS_OVERRIDE`) + plan (`roTrades("pre")`: picks vs trigger, setups through pivot,
  open scoreboard trades vs stop) + groups (`roGroups`: ignitions with grade, Day-1 follow-through, warming). Live/post (Google,
  `liveActive`) = `roLiveMarket` (indexes, day type, money share + top in/out sub-themes, thrust gauge, havens), trades, live groups
  (`liveIgnition`/`liveDay1`, near-misses), `roLate` (since 10/11), and post adds "For tomorrow". Without a newer Google session the
  post card shows the official recap of the last session. Every card ends with `roBoard`: top 8 sub-themes by Strength with rank move
  (live: vs last close via `LIVE_T`; official: vs 5 sessions ago from `s_hist`), hottest, top-10 ins/outs, climbers/slippers, best
  stocks (Leaders score, one per sub-theme), strongest anywhere (`lists.strongest`), new top-10 stocks (live) / RS jumpers (official).
  `dn_share` in breadth rows is in percent (`roDs` converts). Links (`data-go`) switch tabs.
  Oct 15: schedule strip on top (`roSchedule`, `RO_SCHED`: official data ~12:15–1 AM, pre-market quotes ~6–9:30, morning chapter
  ~8:00, live 9:30–4, post read-out 4:00, after-close chapter ~5:00; "Next:" line + last chapter). "What's driving the S&P 500" by
  sub-theme in every card (`roContrib`): columns last close (`intraday.prev_contrib` from data/close_snapshot.csv, used when its date =
  the official date) · pre-market (today's premarket.json via `pmRows`) · now / today's close (live), top 4 up / down in bp, plus a
  one-line "leadership changed / still" read. Pre-market + Intraday "who's moving the index" cards: Group by Sector / Sub-theme chips
  (`ID.grp`, `groupContrib`; stocks outside every sub-theme → "Other · <sector>"; `intraday.sub_of` from subthemes.csv covers the
  index names not in the theme stock list; 245 of 503 S&P names have a sub-theme).
- **The story** (Oct 15; `breadth/story.py`, `story_guide.md`, top of the Read-out tab `storyCard`): scenario tracker A "money keeps
  leaving" (latest share of $ volume in falling stocks ≥ 60%) / B "comes back" (≤ 40% after an outflow episode = 5-day avg ≥ 55% or 2+
  days ≥ 60% within 10 sessions) / W paused; Python `scenario()` and browser `storyState()` must stay identical (same for `baskets` /
  `storyBaskets`: bottom / top 20% of sub-themes by `vs_d5` = sold hardest / held up; 60-day-leader proxy = top 20% Strength 10 sessions
  ago). Signals chips, "where it's going today" (sold vs held basket live), playbooks per branch with the comeback-study evidence.
  Chapters in `docs/story.json` (page fetches from Pages every 10 min; `mdLite` renders **bold** / bullets), written by two Claude
  scheduled tasks: "Market Monitor story · morning" (7:52 AM ET Mon–Fri since Oct 16 so it lands by 8:00 ET / 5:00 PT, before 8:30 data releases; `--slot am`: official close + pre-market) and "· after the close"
  (4:50 PM ET Mon–Fri, `--slot pm`: `data/close_snapshot.csv` saved by `.github/workflows/close.yml` at 4:25 PM ET from the Google Sheet;
  the task dispatches that workflow if the snapshot is stale). Each run: clone, `python3 -m breadth.story facts --slot X` (stdlib only),
  write per `story_guide.md` (incl. "Why it's moving": WebSearch the catalyst for each group on the fact sheet's WHY research list, classify catalyst / rotation / sympathy / unexplained, inline source links rendered by `mdLite`; plus a "How markets work" teaching point tied to the day, a new pattern each chapter), `python3 -m breadth.story publish --slot X --title ... --branch ... --file ch.md --push` (commits only
  docs/story.json via `gh api` PUT). First chapter (Oct 14 pm, "The AI money is leaving") written by hand.
  Data days (Oct 16): the morning task checks the economic calendar; market-moving releases (CPI, PPI, PCE, payrolls, retail sales, GDP,
  ISM, JOLTS, FOMC, Fed Chair) open the chapter with a "**Data today:**" line and are saved on the chapter as `events` [{time, name, why}]
  (`publish --events-file`, workflow input `events_b64`). Read-out shows them in a banner on top (`dataBanner`). A third scheduled task
  "Market Monitor · data card" (8:44 AM ET Mon–Fri) writes slot `data` only when an 8:30 release came out: `facts --slot data` = today's
  events + futures/yields/dollar/ETF moves vs last close and vs the last pre-market snapshot before 8:30 (`_pm_before`, from the commit
  history of docs/premarket.json via gh REST). `dataCard` renders it above the story card; data cards are kept out of the chapter list.
  Chapter order within a day: am, data, pm (`SLOT_ORDER`).
  IN PLAY (Oct 22, Adam: "tell me where the extra edge is today"): `story.in_play(T, PM, catalysts)` (stdlib) → am fact sheet block "IN PLAY
  candidates": stocks gapping ≥ 4% and ≥ 1.5 ADR on steady pre-market trading (6+ active bars, $5+, $20M+/day when known) or Adam's names
  moving 2%+, scored by stacked reasons (gap, possible EP ≥ 8% liquid, RS 85+, its sub-theme gapping the same way ≥ 1%, on picks / pick
  watch / Trade Setups top 5 / SoW prime-breakout-pop-nuzzle, earnings date from catalysts.json for the card date, catalyst-agent strong/real
  read) minus warnings (red flags, record-volume up day, 30%+ below the 52-wk high); groups gapping ≥ 1% with ≥ 60% of members the same
  way (+ fresh ignition / Day 1, top-10 Strength); Adam's names in pre-market. `INPLAY` settings. story_guide.md "In play (morning
  chapter)": the writer searches premarket movers / earnings before the open / after-hours reports, picks 3–6 with catalyst + structure,
  each with source, edge and a one-clause plan, then a "Skip:" line; chapter lead-in **In play today:** right after Where we are.
  Comeback study (`tools/ignition_study/comeback.py`, Feb 2025–Oct 2026): heavy-selling day in an outflow streak (n 18) → SPY median +1.7%
  next 10 sessions, sold-hardest sub-themes +4.3% vs SPY (median +3.2%, 78%) vs held-up +0.5%; ex Mar–Apr 2025 +3.9%; any 70%+ day (n 24)
  sold +1.9% / held +1.0%. First calm comeback day (n 9) → SPY median −1.2% next 10, held-up +1.7%, middle +1.5%, sold −0.1%; 60-day
  leaders +3.1% over 20. Read: snapbacks start around the heavy-selling days; after a calm comeback day follow what held up.
- `boxes.py` + `boxstudy.py` **Box trades** (Oct 16–17, 2026; Adam's charts: Loew's 1936 rectangle, HPE failed breakout, CRWV
  breakdown retest) → `DATA.themes.boxes`, card `boxCard` on Trade Setups (4 trade tiles with today's verdict, tags per trade, research).
  LINES: tight box (`find_box`, 10–130 sessions ≤ 3/4/5/6 ADRs, min max(3%, 1 ADR), 2+ touches each side, flat; LONG side also needs a
  15%+ advance + volume dry-up, `strict`) and WIDE RANGE (`_range_breakouts`, `RG`: swing highs k=5 within 480 sessions clustered within
  max(1 ADR, 2%), line = cluster median, 3+ separate touches, span ≥ 40, level held — brief shakeouts ≤ 3 closes / 4% of span allowed,
  far side = 10th pct of lows, height ≤ 150%, fail line = 1.5 ADR back inside; tight boxes fail at the middle). Support lines run the same
  code on 1/price (`_space`). HPE: range line $63.44 (Adam drew $63.42), broke Oct 2, failed Oct 15–16. CRWV: support $68.51, broke Oct 14.
  TRADES (`boxstudy.TYPES`): retest_long / retest_short (break → back to the line → bounce / rejection, tags go/at/inside/coming via
  `boxes.retest_walk`), trap_short / trap_long (break → closes past the fail line before any bounce → trade toward the far side; tags
  failed (entry, stop 0.5 ADR back over the line, target far side) / far (close through the far side within 40 sessions, stop 5-day
  extreme) / falling (in between); dead if the line is reclaimed). Research: `collect` (every event, signal close → NEXT OPEN entry, skip
  gap-through-stop, 20-session exit or stop, R floored 0.3 ADR, x21/x63 vs SPY, `R5` = 5-session), `features` (market state thr05 /
  thr625 / none, regime, SPY 50/200, dn10, nh−nl; sub-theme + theme 20/60-day return rank, above 50-day, % above 21 EMA from
  `group_frames`; siblings = same group + trade within 10 sessions; RS, RS line near 1-yr high/low, 200-day, 50-day slope, signal volume,
  52-wk distance, beta quartile; box kind/length/break volume/extension/days to fail), `study` (per condition: stats + `edge_vs_rest`
  = R with minus without, Welch t, per half; `proven` = edge t ≥ 2, n ≥ 30, same sign both halves), pairs (exploratory, t ≥ 2.5, both
  halves), `episodes` (thr05 signals per independent thrust, follow-throughs merged within 14 days). Live rows (`live`) carry `conf`
  (proven helps/hurts present), `score`, grade A ≥ +2 / B +1 / C, `group_ok`. ~85 s per build.
  PLAYBOOK: `boxes.attach` (`BOX_SETUPS`) → setup "box" (Box Retest) = today's retest_long `go` names, and (Oct 17, Adam approved)
  setup "spring" (Box Spring) = trap_long `failed` names (closed back inside the box in the last 2 sessions), both only with group
  confluence (sub-theme above 50-day or top-20% sub-theme/theme, `GROUP_OK`), best `exp` first; rows carry `box_*` / `spring_*`
  (stop, lvl, target, grade, wks, ago, kind, exp). Ranked by `boxes.pb` / `boxes.pb_spring` (`boxstudy.playbook_states`, 5-session R by
  state; spring post-thrust +0.14R n 372, 20-session +0.53R). Spring plan: buy open, stop 0.5 ADR under the old bottom, target box top;
  ledger stop from `vcp_stop` column. Shorts / failed breakouts not in the playbook or picks.
  FINDINGS (Jan 2025–Oct 2026, next-open entry): retest_long all +0.04R; thr05 +0.45R (t 4.4, halves +0.41/+0.47, positive after 5 of 6
  thrusts; Feb 2026 −0.43); no thrust −0.05R; weak breadth −0.19R; group confluence proven: sub-theme top 20% 20d +0.24R (edge +0.22, t 2.4),
  60d +0.25R, above 50-day +0.16R (edge t 3.3), breadth 70%+ +0.16R, theme top 20% +0.25R; not in any sub-theme −0.04R (hurts); RS 80+
  alone no edge. Independent recompute (median-member groups, raw bars): thr05 +1.49% vs SPY 21d vs none −0.95%; top-20% group +1.87% vs
  −0.09%. retest_short all −0.12R (t −5.4); thr05 −0.43R (lost after 4 of 6 thrusts); weak-group shorts WORSE (sub-theme weak / low
  breadth / siblings breaking down: edge −0.1 to −0.36R) — sold-out groups snap back; helped: strong breadth (+0.12R), RS ≤ 30, stocks
  outside themes; lead pair 6–25 sessions after a thrust + RS ≤ 30 +0.28R. trap_short (HPE) −0.07R, no positive condition; far_short
  −0.04R. trap_long (spring) +0.07R; thr05 +0.46R (t 6.6, 5 of 6 thrusts), SPY under 50-day +0.24R, nh<nl +0.33R, money leaving +0.21R,
  theme top 20% +0.59R, ADR 4%+ +0.20R. far_long thr05 +0.33R, strong breadth +0.17R, group strength +0.3R, weak breadth −0.25R.
  Baseline any liquid stock 21d vs SPY −0.65% (shorts get that tailwind). Limits: survivorship (shorts look worse), bull-heavy 2 yrs.
  Oct 17 (2nd pass): range far side = most-touched swing-low zone inside the span (`_floor`; QQQ $702.7, Adam ~$703), tol floor 1%
  (was 2%: low-ADR ETFs like QQQ never "broke"). `INDEX` QQQ/SPY/IWM/SMH/DIA → `idx` rows + `idx_status` (strip on top of the card;
  QQQ Oct 16: failed breakout of range line $748.35, falling, far side $702.7). Target-exit variant `Rt` (retests: measured move; traps:
  far side; far breaks: measured move) and `touch20` (trap reached the far side within 20 sessions before reclaiming the line).
  SELECTION: `expected()` = avg R of past trades with the same type, market state and proven confluences (weakest dropped until n ≥ 30)
  → `exp`, `exp_win`, `exp_n`, `exp_used`, `exp_touch`; grade A ≥ +0.40R / B ≥ +0.15R / C; default view Grade A–B ("boxScope").
  IN VOGUE (6-month leaders, conditions group "In vogue"): shorting stocks in a 6-month top-20% theme / sub-theme (incl. "now fading" on
  20 days) much worse (retest_short edge −0.35 to −0.45R, trap_short −0.25 to −0.30R, both halves); helps longs (retest_long sub-theme
  +0.22R, spring theme +0.45R). Stock's own 6-month run: no reliable effect. Far-side reach after failure: tight 66%, range 39% (20d);
  target exit doesn't rescue trap_short (Rt −0.05R). Fib levels (0.382/0.5/0.618) inside the box held no better than neighbours (40% vs
  39%; middle 0.5 slightly better 44%). FOMC-day swing lows NOT more likely revisited/taken (68% vs 73% once within 1 ADR; per meeting
  44–100%); slightly more sweep-and-reverse (72% vs 67%). Any swing low is taken ~70% of the time once price is within 1 ADR.
- `sow.py` **Strength on Weakness** (Oct 21, 2026; Adam's weekly position setup, charts NRIX/APPN/AMPL/MTCH; card R-2026-10-21-strength-on-weakness,
  layer `sow`, status info) → `DATA.themes.sow`, card `sowCard` on Trade Setups (after Box trades; "Unproven" tag, never touches picks). Weekly bars from
  daily (`weekly`, week labelled by its last session; current week counts as it stands, volume paced to 5 sessions, `week_done` via `nyse.next_session`).
  Rules (`CFG`): $5+, $10M+/day, RS 70+; stack 9 > 21 > 50 WEMA, 21 rising 4 wks, 9 ≥ 99% of 4 wks ago; 50 WEMA ≥ 99% of 13 wks ago; base = 2+ closes
  crossing up the 50 WEMA and 10+ closes under it in 78 wks; black box = prior 10-wk range ≤ 3 weekly ATRs, a low within 3% of the 21 WEMA, no close
  5%+ under it; breakout = close > prior 10-wk high on 1.2× 20-wk avg volume; nuzzle = low ≤ 9 WEMA × 1.02 and close ≥ 21 WEMA × 0.98; pop = next week
  closes over the nuzzle week's high. States: breakout / pop (this or last week) > nuzzle (buy over this week's high, stop its low) > riding > extended
  (> 1.5 weekly ATRs over the 9); riding/nuzzle/extended need a 10-wk-high close in 26 wks. Rows carry weekly closes + EMAs (`wk`, `w9`, `w21`, `w50`)
  for the first 25 per state; card shows the top 25 (Show all), chips by state / scope, ⬇ TradingView; header ⬇ Trade Setups adds breakout/pop/nuzzle.
  Evidence (`backtest`, ~40 s per build): signals after 52 wks warm-up, complete weeks, next open → close 13/26 wks later vs avg liquid stock and vs
  avg RS 70+ stock (per signal week). Oct 21: pop 26w +14.8%, +6.6% vs avg stock (t 3.3) but +1.6% vs RS 70+ (t 1.0); breakout ≈ RS 70+;
  without the RS floor ≈ avg stock. Only ~1 year testable; needs longer history (Massive Starter) for a real test.
  ⭐ PRIME POSITIONED (Oct 21, Adam: "too late in the stage-2 break, show them in the box"; PEB/ABCL boxes): `prime` = liquid, RS line
  (price ÷ SPY, `spy` arg) above its 21-wk EMA and 13 wks ago (`rs_up`; no RS-rating floor), flat50, base, 3–30 consecutive closes over the 50 WEMA
  (`run`), 9 > 21 and 21 rising, close ≤ 50 WEMA × (1 + 2.5 weekly ATR); `vr` volume trend (10 vs prior 26 wks), `rsl_hi` RS line within 2% of its
  1-yr high. Rows carry `prime`, `prime_new` (entered in the last 4 wks), `run50`, `ext50`, `vr`, `rsl_hi`; prime rows with no later state get state
  "box" (In the box). Page: "⭐ Prime positioned" chip is the default (localStorage `sowState2`), sorted RS-line-high first then RS; ⭐ Prime / RS
  line high tags. Evidence `prime`, `prime_vol`, `prime_novol`, `prime_rshi` vs `vs_above` (any liquid stock over its 50 WEMA with rs_up):
  Oct 21 evening (Adam: BBY/CVLT/KDP/NWSA right; FROG late, PANW base too short, PENG crash not a nuzzle): prime also needs `slope26`
  (50 WEMA vs 26 wks ago) ≤ +20% (`prime_slope`) and 30+ closes under the 50 in 78 wks (`prime_below`); nuzzle needs `dd10` (10-wk high →
  week's low) ≤ min(2 weekly ATRs, 25%). Prime 172 → 110. Oct 22 (Adam): every SoW row also needs a 30-day avg volume ≥ 1M shares
  (`min_vol30`, `vol30` arg into `features`, applies to the backtest too); prime 103 → 73 (CVLT, APPN dropped). Evidence after: prime 26w +11.5%, −2.4% vs similar (t −1.5); pop vs RS 70+ +1.2/+1.9%.
- `leadership.py` **Market health** (Oct 22, 2026; Adam: "do leaders tell on the market?" + "count breakouts vs breakdowns"; card
  R-2026-10-22-leaders-and-breakouts, layer `market_health`, info) → `DATA.themes.leadership`, `healthCard` near the top of the Breadth tab
  (after the washout card). Leaders = top 10% RS of $5+/$10M+ stocks as of the previous session. `frames`: up10/dn10 (% of leader-days at a
  20-day high/low, 10 sessions), net, a21/a50, off (median off 63-day high), basket (leaders of 20 sessions ago now under the 50-day EMA),
  bo/bd (universe closes beyond the 20-day high/low out of a ≤ 6-ADR base on 1.3× 50-day volume), ratio10, work/wret/wn (breakouts 5–25
  sessions ago still above their level, return from next open). Verdicts: leaders breaking out (net ≥ 5) / cracking (≤ −5) / stalling;
  "not recovering" when basket ≥ 50%; breakouts working (≥ 55% holding and avg > 0) / failing (≤ 40%) / mixed. Lists (leaders as of 5
  sessions ago): crack / under50 / breakout / holding, top 20 shown. `evidence` (fifths vs next 20 sessions of the avg non-leader stock,
  IC + halves, `edges` for today's fifth) recomputed each build; ~40 s. Finding: no forward edge (|IC| ≤ 0.2, halves disagree) over 410 days.
  Pre-market tab (Oct 22): VIX tile first in "Futures, macro & ETFs" (from premarket.json rows `^VIX`: level, pts, %, calm < 15 / normal /
  elevated ≥ 20 / fear ≥ 30) and VIX in the morning-read futures line.
  3-2-1 CRACK (Oct 22, Adam): premarket.py FUTURES adds RB=F (gasoline) and HO=F (diesel); `crackCalc` in the page = (2·RB·42 + HO·42 −
  3·CL)/3 $/bbl (same as macro.py) → `crackTile` next to VIX on the Pre-market tab + `crackRead` line (morning read too). Intraday tab: new
  `.github/workflows/futures.yml` (hourly crons 13:11–19:11 UTC, loops every 10 min 9:25 AM–4:15 PM ET, concurrency `futures`) runs
  `python -m breadth.premarket --futures` (`run_futures`, `parse_live`: latest bar any session vs previous settle; FUT_LIVE CL, BZ, RB, HO, NG)
  → docs/futures.json → `oilCard` ("Oil & refining margins", after Market pulse; shown even without the Google sheet; fetched every 3 min).
  `crackRead` uses the Oct 22 study (same-day vs SPY, 2 yrs): oil ≥ +1.5% & crack ≥ +3% (31 days) refiners +3.1% (90% beat), shale +2.5%,
  airlines −1.0%; oil ≥ +1.5% & crack ≤ −2% (30 days) shale +1.5% (77%), refiners +0.4% (57%). Read thresholds: oil ≥ 1% with crack ≥ ±2%.
- `thetrade.py` **The trade** (Oct 22, 2026; Adam: "how do we handle the trade in play?"; card R-2026-10-22-the-trade, layer `the_trade`, info)
  → `DATA.themes.thetrade`, `tradeCard` on the Read-out tab (above the story card) + "THE TRADE" block on the story fact sheet (guide: one
  line in Where we are). Winners / losers = top / bottom fifth of sub-themes (4+ stocks, `rotation.group_frames`) on 20 sessions; name =
  sectors carrying most of each side's move; ratio (today's baskets) vs its 20-day avg → state on / cooling (2%+ off 5-day best) /
  fading (1–2 closes under) / over (3+); real or seesaw = 60-session correlation + winners minus SPY on the losers' best 15% of days
  (`ind` ≥ 0 holds up, < 0 gives back); plays = RS 80+ $10+ in winning groups (2 per group, setup lists first), "don't chase" > 2 ADRs
  over the 21 EMA; counter watch = RS 85+ in losing groups + comeback trigger (share in falling stocks ≤ 40%, live via `roMoney` when
  the sheet is newer). Live tile: winners vs losers basket today. Evidence (410 days): winners +0.9% vs avg group next 10 (t 1.5);
  holds up +1.1% (t 2.0, halves +1.3/+1.1); gives back → losers won 5 of 5 settled episodes (n small). Oct 21: Consumer + Biotech &
  Health over AI Infrastructure, on 13 sessions, corr 0.03, gives back since Oct 16. ~2 s per build.
  "Why this trade is happening" (Oct 22, Adam: "I want to understand the trade, it gives confidence"): every story chapter writes a
  **The trade, explained:** section (story_guide.md: What's happening / Why with sources / How it works / Real or seesaw / What
  confirms it or breaks it, with dated upcoming events); `tradeCard` shows the latest one at the top of the card (`mdLite`).
- `stories.py` **Trade Stories tab** (Oct 22, 2026; Adam: "a tab where you put together news and earnings narratives into a cohesive
  story and recommend how to trade the developing story"; card R-2026-10-22-trade-stories, layer `trade_stories`, info) → docs/stories.json
  (page fetches it from Pages every 15 min, `renderStories`, tab right after Read-out). Max 6 open storylines, updated (not rewritten) once a
  day by the "after the close" task (stories_guide.md): id, title, status building / peaking / fading / resolved, started, summary, changed,
  thesis {what, why, how, real, confirm}, timeline [{date, event, source, url, reaction}] (no url → dropped), groups {long, short} = exact
  sub-theme names, tickers {long, short, watch}, catalysts [{date, time, name, why}], trade (markdown), related, history (per day: status +
  groups, appended by `validate`). Code: `price_check` (favoured minus hurt groups, or vs SPY, from rotation.mhist; verdict agrees /
  wobbling / turning / disagrees) and `scorecard` (each history day, next 5 sessions) — mirrored in the page (`storyPrice`, `storyScore`).
  `python -m breadth.stories facts | guide | check --file F | publish --file F --push` (gzip+base64 → `.github/workflows/stories.yml`,
  `save --gz-b64`). Stdlib only. Seeded Oct 22 with 5 sourced stories (AI spending repriced, 10-year near 5%, Gulf oil, IT services
  re-rating, managed care).
- `stairs.py` **Stair steps** (Oct 24, 2026; Adam: cyber broke out of its stair step Oct 22–23 and he couldn't see it across sessions;
  card R-2026-10-24-stair-steps, layer `stairs`, info) → `DATA.themes.stairs`, `stairsCard` on the Rotation tab under Group ignition
  ("Unproven" tag, never touches picks). Stock states (`frames`): uptrend (21 EMA > 50, 50 rising 10 sessions); ◆ nuzzle (closed 2+ ADRs
  over the 21 within 20 sessions, then low into the 9/21 ribbon ≤ upper + 0.5 ADR, close ≥ 21 − 1.5 ADR and ≤ ribbon + 1 ADR; counts 5
  sessions); ↗ lift (nuzzled in the prior 5, close > 9 EMA and > prior high); ▲ step break (first close > prior 15-session high after a
  nuzzle in that window). Group (4+ liquid $5+/$10M+): setting up together = 50%+ nuzzled in 5 sessions; stepping up together = 40%+
  lifted/broke in 3 sessions after 40%+ nuzzled 3 sessions earlier. Rows: status + day count, ★ leader (top 30% on 60-day), 15-session
  strip (h_nuz / h_lift / h_st), members with d9/d21 (ADRs), e9/e21, step high, to_step; quiet non-leader groups keep only active
  members. Views Groups / Stocks (nuzzled first, top 30, ⬇ TradingView). `evidence` recomputed each build (~10 s). Finding: alone ≈ avg
  group; inside leading groups vs other leading groups 20d setting up +2.2% (t 1.9, halves +1.3/+3.5), stepping up +1.7% (t 2.0),
  pure step breaks −1.1%. Oct 23: Cybersecurity Platforms stepping up day 3; 8 stepping, 11 setting up.
  Themes tab tags (Oct 24, Adam): `stairTag` puts ★ (top 30% on 60-day) + "Setting up · day N" / "Stepping up · day N" next to every
  theme and sub-theme name; themes use `stairs.themes` (same rules on data/themes.csv members, ETFs out; TECH - Cybersecurity stepping Oct 23).
  "Stair steps" filter chips (`STAIR_FILTERS`, `stairPass`, `UI.themes.stair`): All / ★ + setting/stepping / setting or stepping / stepping /
  setting / ★ leading, with counts for the current view; kept when switching Themes ↔ Sub-themes.
  Box trades (Oct 24, Adam: "couple this with our box setups"): `stairs.stocks` = every liquid stock nuzzled / lifting / step break
  → [state, e9, e21]; `stairBits(r)` adds ★ group + "group setting/stepping up · dN" + the stock's own state under each box row's grade
  (trade sections and the tight-box pipeline); "Stair steps" chips (`BOX_STAIR`, `stairBoxPass`, localStorage "boxStair"): All / ★ group
  setting/stepping / ★ group + stock nuzzled/lifting / stock nuzzled/lifting / ★ leading group. Group = sub-theme, else theme. Not
  backtested as a box confluence yet (could add to `boxstudy.features`).
  ★ MY FAVORITES (Oct 24, Adam: "your favorite of these trades"; card R-2026-10-24-box-leaders, layer `box_favorites`, info; test scripts
  `tools/box_stairs/`): panel at the top of the Box trades card + "★ Favorites" chip. `isBoxFav`: retest_long go/at or trap_long failed,
  grade A–B, ★ leading group (`stairGroupOf`), `boxRR` (target − last) ÷ (last − stop) ≥ 1.5, "at" rows within 1.5 ADR of the line (ZS
  Oct 23 touched-and-ripped same day stays tagged "at" by `retest_walk`); `boxFavRank`: acting now, exp, own nuzzle/lift, RS; top 5.
  Evidence: retest bounce in ★ group +0.23R vs −0.02R (t 3.2, halves +0.27/+0.25; post-thrust +0.56R; +0.29R even without the sub-theme
  top-20% 60d badge, t 2.7); own nuzzle adds nothing inside ★ (+0.24 vs +0.22R); group setting/stepping nothing; springs ★ +0.22R (t 1.7);
  shorts in ★ groups worse (−0.28R t −3.5). ★ passes the proven rule but is NOT in box grades/playbook (needs Adam's approval).
  Strength on Weakness card (Oct 24, Adam): same `stairBits` tags in the State cell + "Stair steps" chips (BOX_STAIR without "fav",
  localStorage "sowStair"); `stairGroupOf` falls back to DATA.themes.stocks sub / first theme when a row has none. Stair states are DAILY
  (9/21-day EMAs), SoW states weekly; ★ / nuzzle not backtested on SoW signals. Rows carry `adr` (daily 20-day ADR %, Oct 24) → sortable "ADR %" column.
- `dips.py` **Dip buys · 9 / 21 EMA** (Oct 24, 2026; Adam: "get in when price is wicking under the 9 or the 21 and coming back up", wants it live;
  card R-2026-10-24-dip-buys, layer `dips`, info) → `DATA.themes.dips`, `dipCard` at the very top of Trade Setups (after the live bar) and on the
  Intraday tab (after "Your trades, live"). Names = Box longs (retest_long any tag, trap_long `failed`) + every SoW row. Daily 9/21 EMAs at the last
  close; flags under9/under21, wick9/wick21 (low under, close at/over), reclaim9/21 (closed under in the prior 3, over now), run9/run21, 10-day strip
  (0 above / 1 wick / 2 under 9 / 3 under 21). Live (`dipLive`, when `liveActive()`): today's EMA = e + α(price − e), α 2/10 and 2/22; low from sheet
  column **L "low"** (added Oct 24: `=IF(OR($C4="",$B4=2),"",IFERROR(GOOGLEFINANCE($C4,"low"),""))`, rows 4–3600), falls back to the open. Chips Show
  (wicked & back / under now / all; multi-select, both = either) · From (Box / SoW / ⭐ Prime) · Trend (9 over 21 default) · Stair steps (multi-select, `chipsMulti`: picked chips combine with OR, also on Box + SoW cards); localStorage dipF / dipSrc /
  dipTrend / dipStair. Sheet rows: `intraday.sheet_rows(extra=dips.tickers(...))` adds missing names (flag 0) and gives R2K-only dip names **flag 3**
  (open + low fetched; marketcap/volumeavg still only flag 1). Test (`tools/dip_study/test.py`, all liquid RS 70+ uptrend stocks): wick & back ≈
  any uptrend day (±0.1 pts vs SPY, t < 1, R +0.05 vs +0.03, halves flip) → entry-location tool, no edge alone.
  Weekly switch (Oct 24, Adam; chip "EMAs" Daily / Weekly, localStorage dipTf): rows carry `w` = same flags on `sow.weekly` bars with 9/21-WEEK EMAs
  (min_periods 1, as SoW), `low` = week's low so far, `p9/p21` = last week's EMAs, `atr` weekly range %, strip in weeks; payload `week`, `week_done`,
  `week_days`. Live weekly: week finished at the last close → base = that week's EMAs, low = today's; else base = p9/p21, low = min(week so far, today).
  Weekly version untested.
- `launch.py` **Launch list tab** (Oct 25, 2026; Adam's CDNA / DINO / NTRA charts: "what separates the ones that went"; card
  R-2026-10-25-what-made-them-go, layer `launch`, info, never touches picks; study scripts `tools/went_study/`) → `DATA.themes.launch`,
  tab "Launch list" after Trade Setups (`renderLaunch`). Names = fresh base breakouts (`frames`: liquid $5+/$10M+, 20+ of the prior 40
  weekly closes under the 50 WEMA, now 2–8 in a row over it, 9 > rising 21, close ≤ 50 × (1 + 3 weekly ATR)) + every SoW row. Points:
  group (sub-theme top third on 13-wk equal-weight return, 3+ stocks), RS 70+, RS line +15% in 13 wks, 6%+ gap-up day in 65 sessions.
  Grade A = group + 2–3 others, B = group + 0–1, C = no group point. `early` = run ≤ 8 (the tested window).
  STAGES (Oct 25 follow-up, Adam: "ACN / IT had already gone; the buy was the flag under the 50 WEMA"; `tools/went_study/early.py`):
  `curl` = base + 9 WEMA over a rising 21 + close within 1.5 weekly ATRs under to 0.5 over the 50 WEMA (the flag before the break)
  → evidence `evidence_curl` (failure = close 1.5 ATRs under the 50): group A 57% hit +50%, 13w vs SPY +11%; B 40% / +3%; C 18% / −5%
  (halves agree). IT curled Aug 21 at $196 (flag break), ACN Oct 2 at $199. RS / RS line / gap points mostly switch on after the move
  starts (ACN RS 8–14 in Aug): the group is the early clue. Row `stage` curl / early / later, `flag` (close above the prior 4-week high),
  `vs9` (ATRs over the 9 WEMA) + `loc` at9 ≤ 0.5 / near ≤ 1 / up ≤ 1.5 / far: Grade A breakouts within 1 ATR of the 9 hit +50% 53–54%
  vs 43% beyond 1.5. Page chips Stage (default curl, launchStage2) · Grade (default A+B, launchGrade2) · Where (launchLoc).
  **LAUNCH PICKS = the headline recommendations** (Oct 25, Adam approved; `config.APPROVED_LAYERS = ("launch",)`, registry status live):
  `launch.select(F, i, held)` each week: curl or fresh, group point on, $20M+/day, weekly ATR ≤ 15% (`PICK.max_atr`), rank grade A → curl →
  within 1 ATR of the 9 → group rank → RS, one per sub-theme, skip held names, top 3 (`PICK.n`). `launch.replay` runs the same rule on every
  past week with the tracker's exits → `pick_bt` (Oct 25: 148 picks, +9.7% vs SPY 13w, t 3.66, halves +11.4/+8.7%, median ≈ 0, worst −38%).
  Ledger `data/launch_ledger.csv` (`ledger_record` only when the week is complete and never rewrites a recorded week; `ledger_settle`:
  entry next session's open, exit close 65 sessions later or the first complete weekly close under 50 WEMA × `stop_mult` (curl: min(1.5
  weekly ATR, 15%) under; `floor` column), best high 130 sessions) → `tracker`. Built only with `ledger=True` (update.py). Page:
  `launchPicksCard` at the top of Trade Setups and the Launch list tab (picks with why/plan, replay banner, live tracker table); Read-out
  plan lists launch picks + open launch picks first. Old 5-day picks card relabeled "Swing picks (old rule, still logged)", unchanged.
  Test `test_launch_picks_ledger`. First week logged Oct 23, 2026: AI, DHR, IT. Evidence recomputed each build
  (fresh setups, first per stock per 26 wks, next open → best high 26 wks, 13-wk vs SPY, lost the 50 WEMA): A 57% hit +50% (n 76, halves
  55/58%), 13w vs SPY +5.6%; B 33%; C 18%, −5.1%. Volume (trend, up/down, biggest week) and volatility-adjusted RS line: no edge. Chips
  Grade (A / A+B / all, localStorage launchGrade) · Stage (early / later / all, launchStage); header ⬇ Trade Setups adds Grade A early/later.
- `polished.py` **Best Setups tab** (Oct 25, 2026; Adam: "a new tab for the polished setups"; card R-2026-10-25-polished-setups, layer
  `polished`, info) → `DATA.themes.polished` (groups, nuzzle, flags, evidence), tab "Best Setups" before Trade Setups (`renderBest`):
  Launch picks card + tracker on top, leading-groups table (sub-theme top third on 13 wks, counts per section), 1 Early (Launch list
  rows grade A/B, stage curl/early), 2 EMA pullbacks (leaders: weekly run > 8 over the 50 WEMA + weekly stack, daily 21 > 50 rising,
  RS 70+, $20M+; `touch` = low within 0.25 ADR of the daily 9/21 ribbon, close ≥ 21 − 0.5 ADR and ≤ 9 + 1 ADR; states nuzzle / touched
  (last 5 sessions) / close (within 1 ADR above, untested); chips Show, localStorage bestNz; top 30), 3 high tight flags (30%+ leg,
  high 3–15 sessions ago, flag low = lowest low SINCE the high via sliding windows, depth ≤ 25% and ≤ 3 ADR, 5-day range ≤ 2 ADR,
  close within 1 ADR of the high, above 21 EMA, RS 70+). Evidence (backtest uses the prior week's group rank): nuzzle lead +0.19R vs
  rest, t 2.57, halves +0.23/+0.15 (proven); flags lead +0.12R, edge t 2.96, halves +0.29/−0.04 (unproven). ~10 s per build.
- `lifecycle.py` **Theme lifecycle · Watch → Buy** (Oct 27, 2026; Adam: "trigger a watch for a buy on a theme, activate a buy, and
  recommend which tickers"; from the "Anatomy of a Blossomed Theme" doc; card R-2026-10-27-theme-lifecycle, layer `lifecycle`, info, never
  touches picks) → `DATA.themes.lifecycle`, `lifecycleCard` right under the Launch picks on the Best Setups tab + lines at the top of the
  Read-out group signals (`roGroups`). Reuses `rotation.group_frames` / `flow_frames` / `ignition_frames` on the sub-theme members (~3 s).
  Stages per day (`group_state`, priority blossom > fade > build > ignition > push > forgotten; `CFG`): forgotten rk60 ≤ 0.2 · push = RS-rank
  +30 pts in 10 from rk60 < 0.5 or 3/4 ignition checks · ignition in 10 sessions · build rk60 ≥ 0.6, within 15% of the 60-day high,
  inflow tier or trend 12/20 · blossom rk60 ≥ 0.8, within 3%, ignition in 40 or confirmed · fade = was rk60 ≥ 0.8 in 40, fading/outflow,
  breadth < 50% (rk60 = percentile of 60-day relative return). `ready` = build/blossom + leaders (`ignition_frames` lead) + confirmed/steady;
  `buy` = ready and ratio10 ≥ 1; size full when `act` (ratio10 ≥ 1.5 in 15 sessions) else half; weak → "hold off" (card banner).
  `watch` = push/ignition + leaders, not ready (`hot` = ignition). Picks (`picks`): members $10+, $20M+/day, RS 70+: pullback (low into the
  9/21 ribbon in the last 3 sessions, buy over the day's high, stop the low ≤ 1 ADR) > flag (polished flags pivot/stop) > curl (Launch
  A/B curl/early) > near (within 1 ADR above the ribbon); > 2 ADRs over the 21 EMA → `wait`; earnings date from docs/agent/catalysts.json.
  Rows only for staged/ready/watch groups; `alerts` = ready/watch that started within 3 sessions. Evidence each build: `evidence.d20/d40`
  per stage / buy / watch / buy_act / buy_noact / ready_weak / stage34_not_buy, `watch_to_buy`, `stock_evidence` (ribbon pullbacks by
  group state, 1-ADR stop, 20 sessions). Oct 27: BUY +2.7% vs avg group 20d (t 3.5, halves +2.8/+2.9), 40d +3.9%; weak breadth ≈ 0;
  WATCH ≈ 0, 53% turn BUY in 30 sessions; pullbacks in BUY groups +0.74R vs +0.27R (edge +0.31R, t 2.2); stage alone: blossom +3.0%
  (t 3.6), push −0.8%, forgotten −0.65%. Test `test_theme_lifecycle` (gating + no look-ahead).
  `lifecycle.all` (Oct 28, Adam: "a stage column like the stair-step table") = every modelled sub-theme →
  [stage name, n, days, last stage, sessions ago, signal buy/ready/watch/""]; no stage today → "Between stages" + the last stage held
  within 60 sessions. Page helper `lcStageOf(g)` → "Lifecycle stage" column (sortable, Blossom first) in both stair-step views.
  **Lined-up buys · live** (Oct 27, Adam: "stock buys when everything lines up and tickers are into their EMAs", top of Intraday):
  `lifecycle.live` = every liquid RS 70+ uptrend member (`P["base"]`) of a BUY / ready group (WATCH groups left out: their dips lost
  −0.15R) with c, hi, lo, e9, e21, adr, t3/t0 (ribbon touch in 3 sessions / last), earn. Browser `lineupState` (live EMAs as `dipLive`:
  α 0.2 / 2/22; low from sheet column L) → states over (in the zone and price > yesterday's high = the trigger) / zone (low into the
  9/21 ribbon today or t3, price ≥ 21 − 0.5 ADR, ≤ 9 + 1 ADR, trigger within 1.5 ADRs) / near (within 1 ADR above the ribbon); stop =
  dip low, max 1 ADR under the trigger. `lineupCard` = on the Best Setups tab right under the Theme lifecycle card (moved from the top of
  Intraday Oct 27 at Adam's request; still live from the Google sheet via `fetchLive` → `rerenderPanel`): banner hold-off (breadth weak)
  / N lined up and triggered (half size when mixed), checklist chips per row (Group BUY, Leaders, RS 70+ · uptrend, Into the 9/21, Over
  yesterday's high), top 25, ⬇ TradingView. Evidence `stock_evidence.trigger` (daily bars: touch, buy the break of the touch-day high within
  3 sessions, stop touch-day low ≤ 1 ADR, 20 sessions): BUY groups +0.84R (n 750, halves +0.98/+0.69R, 29% win) vs other +0.13R, WATCH
  −0.15R; edge +0.49R, t 2.03.
  TRACK RECORD + ALERTS (Oct 27, Adam: "phone notifications when a stock is ready" + "are these being tracked, I want live backtest data"):
  live ledger `data/lineup_ledger.csv` (`lifecycle.ledger_record / ledger_settle / tracker`, `build(..., ledger=True)` from update.py):
  each official close freezes the FIRST ribbon dips (`f0`, no touch in the prior 5) of BUY / ready-group leaders (kind buy / ready),
  a date is never rewritten (a "none" row marks dates with no signal); settle on daily bars = fill when a later session's high takes
  the dip-day high within 3 sessions (fill max(open, trigger)), stop max(dip low, fill − 1 ADR), exit 20th session close or stop; R, ret,
  xspy, status pending / open / done / stopped / nofill. `lifecycle.tracker` → card section "Track record" (`lineupRecord`: BUY vs ready
  vs backtest, last 40 rows, backtest trade list `stock_evidence.trigger.recent`). Seeded Oct 26 (VEEV, VRNS, ready).
  Alerts: `breadth/lineup.py` (`state` = Python twin of `lineupState`, parity tested in Node; `run` pure) via
  `.github/workflows/lineup.yml` (hourly crons :33 13–19 UTC, loops every 5 min 9:35 AM–4:05 PM ET) → docs/lineup_live.json {date, time,
  gate buy/half/hold, rows, events}; events = first time today a BUY-group name (gate not hold) reaches zone or over; optional instant
  ntfy.sh post when repo secret NTFY_TOPIC is set. Claude scheduled task "Market Monitor · lined-up alerts" (every 15 min in the session)
  reads `python -m breadth.lineup events --since 15` and pushes a phone notification for new events. Test `test_lineup_live_and_ledger`.
  **Biotech tab · drug value chain** (Oct 29, Adam: "biotech is the only thing moving; track it in detail so we can invest in the exact
  right places"; layer `valuechain`, info only, untested as a signal): `breadth/valuechain.py` `build(adjusted, theme_data)` →
  `DATA.themes.valuechain`, stages + tickers in data/valuechain.json (editable; a ticker may sit in 2 stages; `demand` = XBI/IBB
  gauges; `store.theme_tickers()` includes them so missing ones get bars). Per stage: equal-weight vs SPY r1/r5/r20/r60, above50, off
  (median off 1y high), rs (dashboard RS, else rated from `rs_bp`), rv5/rv20 ($ volume vs the 50 sessions before the last 20),
  net5/net20 (signed $ volume ÷ normal), up20, share / share_chg of the chain's $, `line` (61 sessions vs SPY), spots counts;
  composite rank = price rank + flow rank → read "Leading, money confirming" / "Leading on price, money lagging" / "Money moving in,
  price catching up" / "Being sold" / "Middle of the pack". Per stock: same + x10/x21 (ADRs over the EMA), v50, net20_usd, `spot`
  (pullback = uptrend and −0.5..+0.3 ADR from the 21 EMA; buy = ≤ 1.25 ADR; stretched 1.25–2; extended ≥ 2; basing; broken < 50
  EMA). Page `renderBiotech` (tab "Biotech", after Rotation): header + XBI/IBB tiles, sortable stage scorecard (click a row → its
  stocks), stock table with Stage / Spot chips and ⬇ TradingView; live "Today" columns when the sheet is a newer session than the
  build. Test `test_value_chain`.
  **Runners · groups running together** (Oct 29, Adam: "AI drug discovery all ran together — I'd have liked an alert to day trade it";
  card R-2026-10-29-group-runs, layer `runners`, info only): `breadth/runners.py` `scan(rows, subthemes, stocks, mins, profile)` per
  sub-theme from the live sheet (needs the sheet's volume column): liquid members ($3+, $10M+/day, 4+), RUNNING = 75%+ up AND avg move
  1.25+ ADRs (move ÷ own ADR) AND +3 pts vs SPY AND dollar volume 1.2x the paced normal (`vol_pace` = intraday volume_profile);
  strong = 1.5 ADRs on 1.5x; heating = 3 of 4 with breadth ok and ≥ 80% of the ADR bar (page only). Names to trade = members up 0.75+
  ADR and ≥ today's open, best RS. `alerts` = first RUNNING of the day per group (after 9:45), again each +1 ADR wider, max 3/day.
  Wired into `lineup.run(..., D=data.json)`: events with `type: "group"` in docs/lineup_live.json (+ `groups` = current running/heating),
  ntfy (Tags fire, click → #intraday), forward log data/runner_log.csv (committed by lineup.yml); the hourly task "lined-up alerts"
  formats group events. Page twin `runnersScan` / `runnersCard` (Intraday tab, right above "Who's moving the index"), parity tested in
  Node (`test_group_runners`). Daily evidence (tools/runner_study/hist.py): running → next day open→close +0.34% vs avg group (t 2.25),
  5d +0.90% (t 2.47); strong +0.62% / +1.47% (t 2.6), both halves. Re-test intraday continuation from the log after ~4 weeks.
  EMA LOCATION TAGS (Oct 27, Adam's OKTA chart: "In the EMAs" while 0.9 ADR above the 9): `loc` in `lineupState` / `lineup.state` (twins,
  parity tested) from live price vs live 9/21 EMAs in ADRs (`d9`, `d21`): reclaim21 / reclaim9 (low under the EMA today, price back over it
  and ≤ 0.5 ADR above) > on21 / on9 (within 0.3 ADR) > under21 / between (9–21) / above ("Over the 9 · x ADR"). `precise` = reclaim / on /
  between. Zone rows that aren't precise read "Bounced off the EMAs"; precise rows sort first; checklist chip "On / reclaiming the EMA
  now". Alerts: zone events fire only when precise (plus every "over"); ntfy title says where ("reclaimed the 9"). Untested as an edge.
- `rspull.py` **RS leaders pulling back** (Oct 29, 2026; Adam: a trader "finds tickers making new RS highs and waits for weakness"; card
  R-2026-10-29-rs-high-pullbacks, layer `rspull`, info) → `DATA.themes.rspull` (~50 s per build), `rsPullCard` on the Setups tab (part 2, after
  Dip buys) + drawer line + header ⬇ Trade Setups section. RS line = close ÷ SPY at a 252-session high; live rows = liquid uptrend ($5+, $20M+/day,
  21 EMA > rising 50 EMA) with an RS high within 30 sessions → state dip (9/21 ribbon touch in 3 sessions, lifecycle rule) / near / wait, same
  fields as lifecycle.live so the page reuses `lineupState`; `ahead` = RS high while price 3%+ under its 52-wk high. `study` re-run each
  build: first dips, buy the dip-day-high break within 3 sessions, stop dip-day low ≤ 1 ADR, 20 sessions (R capped 10) + Adam's exit (first
  close under the 10 EMA). Oct 29 (Nov 2025–Sep 2026): RS-high dips −0.03R (n 1,764) vs equally strong without an RS high −0.06R (edge
  +0.26R, t 2.03, halves +0.45/+0.14) but ≈ 0 with Adam's exit; RS-leads +0.13R (n 270). Verdict "proven" also needs own R > 0 and a positive
  Adam-exit edge → currently "helps" (Unproven badge). Test `test_rs_pullback`.
- `emaprob.py` **EMA test odds** (Oct 29, 2026; Adam: "time spent above the 9/21 EMAs ... when the probability is high enough it's an entry;
  same on the short side"; card R-2026-10-29-ema-test-odds, layer `emaprob`, info) → `DATA.themes.emaprob` {long, short: {evidence, rows, thr}}
  (~60 s per build), `emaOddsCard` on the Setups tab after RS leaders. Test = 3+ closes on the right side of the 9 or 21 EMA then low within
  0.25 ADR (or through); trade = break of the test-day high, stop test-day low ≤ 1 ADR, win = +2R first within 20 sessions. Tiers (`tier` =
  page `emaTier`): A post-thrust + leading group (sub-theme top 30% on 60 days) + 15+ sessions, B post-thrust + leading group, C leading +
  (15+ sessions or held 0.5+ ADR), D leading otherwise, E not leading; entry tier = win ≥ 30% + both halves positive (A, B on Oct 29). A
  17-feature logistic model had no skill (AUC 0.50) so no model probability is shown. Live rows = leading-group stocks within 1.5 ADR of the
  9/21 + tests in the last 3 sessions not yet triggered; the page scores live tests (live EMAs, sheet low). Shorts: every tier lost.
  Test `test_ema_test_odds`.
- **RS 2-week** (Oct 29, Adam: "a couple week one"): `strength` `rs2w` = 10-session return percentile 1–99 vs liquid stocks (`rs2w5` = change
  over 5 sessions), `rs2w_bp` breakpoints, refs key `c10` → `liveRating2w` live; Stocks tab columns "RS 2-wk" / "2-wk Δ", drawer. The RS Rating
  itself = 63/126/189/252-day returns weighted 40/20/20/20 (~1 year, mostly the last 3 months). Untested as a signal.
- `.github/workflows/rebuild.yml` (Oct 24): page-only rebuild (`--rebuild-only`, no Massive calls, queue `agent-rebuild`) so code changes
  reach the live page without waiting behind a data job in the `breadth-update` queue. Dispatch it after pushing page code:
  `gh api -X POST repos/az123-stack/breadth-monitor/actions/workflows/rebuild.yml/dispatches -f ref=main`.
- `tools/orb_study/` ORB × sub-theme study (Oct 24, 2026; Adam): `download.py` 15-minute regular-session bars for ~1,040 liquid
  sub-theme stocks + SPY/QQQ via `.github/workflows/orb_study.yml` → branch `orb-data` (parts of 50 tickers, resumable; GitHub
  artifacts are blocked from Claude's sandbox, git works). `study.py --bars <orb-data folder>`: rankings prior / or (+vol), SPY/QQQ
  15/30-min ORB trigger on 15-min closes, stock's own OR stop, exits close / 2R / 5d, baselines any / basket / anywhere, splits.
- `earnings.py` **Earnings clusters** (Oct 27, 2026; Adam: "earnings results that together point to a theme, captured in the write-ups";
  card R-2026-10-27-earnings-clusters, layer `earnings_clusters`, info) → `DATA.themes.earnings`, `earningsCard` on the Trade Stories tab
  (under the header) + EARNINGS CLUSTERS block in `story.earnings_lines` (am: official last 5 sessions; pm: plus today's reactions from
  data/close_snapshot.csv using stock rows' `adr` % and `v50`) → story_guide.md "What earnings said" (writer confirms each was earnings,
  finds the common message with sources) → stories_guide.md (confirmed clusters become Trade Stories timeline items). Reaction = gap ≥
  max(3%, 1 ADR) on 2.5× 50-day volume ($5+, $10M+), direction = close vs prior close (mixed < 0.5 ADR), `conf` when catalysts.json has
  that earnings date; cluster = 2+ in a sub-theme within 5 sessions, ≥ 2/3 the same way; `quiet` = members without a reaction; `next` =
  catalyst-agent earnings dates ahead. Evidence (~2 s): UP cluster → non-reporters +1.9% vs avg group 20d (t 1.93, halves +1.9/+1.9),
  DOWN → ~0. `python -m breadth.earnings` prints today + evidence. Test `test_earnings_clusters`.
- **Headline picks = Launch picks + Lined-up buys** (Oct 27, Adam). Retired from the page: Top 2 swing picks (`picksCard`), Decision
  Cards (`decisionCard`) and the pick scoreboard card; their Python (playbook.picks, ledger, decision.py log) still runs quietly. Every
  setup and trade list stays (Adam downloads them for weekend chart review); the header "⬇ Trade Setups" starts with Launch picks +
  lined-up buys (`launchPickSet`, `lineupNow`). Read-out plan, "Your trades" cards and story tags use them too. Catalyst agent worklist
  (`agentfiles.worklist`) = Launch picks → lined-up buys → theme-BUY tickers → old card names, max 45 (first 15 full research). Macro
  brief agent KEPT (Adam: important): `macroBriefCard` on the Read-out ("Macro & the week ahead": risk, rates / Fed / oil / geo, the
  coming events from today on, sources), fetched from docs/agent/macro_brief.json on Pages every 15 min. `config.APPROVED_LAYERS` = launch, box_favorites, lifecycle.
- ★ in box grades (Oct 27, Adam approved): condition "★ Leading group (sub-theme top 30% on 60-day return)" in `boxstudy.conditions`
  (feeds `expected()` grades when proven) and in `GROUP_OK` (Box Retest / Box Spring playbook confluence).
- Top late mover (Oct 27; `lateLeader` at the top of the Intraday Second-half movers card; card R-2026-10-27-late-mover; study
  `tools/late_mover/study.py` on the orb-data 15-min bars, results.json): at 12:00 ET, RS 80+, sub-theme top third on 13 wks
  (`polished.groups`), up 1%+ since 10:00 and beating SPY, $20M+/day → highest RS. 5d +0.21R (+0.15R vs avg stock, t 1.3);
  same/next day ≈ 0R; the biggest mover did worse. "Unproven" watch line.
- 10-year yield tile (Oct 27, Adam): `intraday.PULSE` "^TNX" = Google `INDEXCBOE:TNX` (CBOE quotes ×10; the tile divides when > 20) → Intraday
  Market pulse shows the yield in % and the day's change in bp (green when yields fall). Joins the live sheet on the next build.
- Scheduled-task models (Oct 27): "lined-up alerts (hourly)" and "10/11 snapshot kick" moved to Sonnet.
- Page tabs (Oct 27 cleanup): one `renderTab` table serves tab clicks and live refreshes (before, `rerenderPanel` lacked Best Setups and
  Launch list, so a live price refresh on those tabs drew the Breadth tab). Removed dead payload fields (stocks `rsraw`/`v1`, SoW
  `lo52`/`hi52`/`prime_wks`/`rs_up`, box live feature columns `g_r20`…`s_r126q`) and dead helpers (`fmtK`, `roPts`, `boxes._adr`,
  `lifecycle.build_safe`).
- `reclass.py` **Theme upkeep · reclassification agent** (Oct 28, 2026; Adam: "an agent checking whether tickers need reclassifying into our
  themes and sub-themes in case things change or tickers are missed"; proposals only, never moves anything by itself) → `DATA.themes.reclass`
  (built in update.py, ~2 s), card `reclassCard` at the bottom of the v1 Themes tab. Worklist (code measures): **unclassified** = liquid
  universe stocks ($5+, $10M+/day, 120 sessions) in no sub-theme with RS 80+ or $100M+/day, top 40 by RS, each with the 3 sub-themes it trades
  most like (correlation of daily returns minus SPY, 120 sessions, vs equal-weight group indexes); **poor_fit** = members whose correlation to
  their own group's OTHER members is < 0.25 while the best other group is ≥ 0.35 and 0.20 higher, or < 0.10 outright (ETF baskets like
  Commodity ETFs skipped), top 30 by gap; **stale** = theme-file tickers with no bars in 5 sessions; **thin** = sub-themes with < 3 liquid
  members. First run Oct 27: ESS (Essex, a REIT) filed in Batteries & Storage (ticker mix-up with ESS Tech), CME in Crypto Exchanges, ISRG in
  Industrial & Surgical Robots; stale WBD / PSKY / ATKR / BZH. Agent (kind `reclass` in agentfiles, WEEKLY): "Market Monitor · reclass agent"
  Sat 8:37 AM ET reads `python -m breadth.reclass worklist` (stdlib), researches each business, publishes docs/agent/reclass.json: moves
  {id, t, action add/move/remove/rename/keep, from, to (exact sub-theme name or "NEW: Group / Name"; new ticker for rename), theme_add,
  confidence, why, sources}; validation drops off-worklist tickers, unknown sub-theme names and source-less moves. **When Adam says "apply
  reclass N, M"**: `python -m breadth.reclass apply --ids N,M` (edits data/subthemes.csv / themes.csv, one sub-theme per stock, logs to
  data/reclass_log.csv), rebuild, commit, push; "reject reclass N" → `reclass reject --ids N`. Decided tickers stay off the worklist 90 days.
  `python -m breadth.reclass list` shows proposals + status. Test `test_theme_upkeep_reclass`.
- **v2 page** (Oct 28, 2026; Adam approved "Option B": a redesign beside v1, same data) → `v2site.py` + `v2_template.html` → docs/v2/index.html
  (served at /breadth-monitor/v2/), built at the end of every `site.build` from the same payload (`slim` keeps only what v2 shows, ~1.4 MB;
  each section built separately (`put`), a failing one shows "appears after the next data run"). 6 main tabs with sub-tabs, hash routes like
  #groups-themes, last sub-tab per tab remembered (localStorage v2sub). ALL pages built (Oct 28): Today (proven posture, your trades = Launch
  picks + lined-up buys, groups in BUY, key numbers) · Market: Breadth, Money flow, Macro, Pre-market & live · Groups: Themes (v1 Themes table
  rebuilt + lifecycle Stage + sector filter, click a row for its stocks), Lifecycle, Lighting up, Stair steps, Rotation, Timeline · Setups:
  All setups, Launch list, Box trades, Lined-up & dips, Strength on weakness, Record volume, Export lists (pick lists → one TradingView file)
  · Read: Latest (../story.json), Trade stories (../stories.json), Earnings, Archive · Lab: Experiments, Evidence (registry ladder), Research
  log (research/R-*.md). Evidence badge on every page. Shared `sortTable` with a sub-theme dropdown filter; "⬇ TradingView" = .txt download +
  copy. Light / dark / auto (localStorage v2theme); phones get a bottom tab bar.
  LIVE (Oct 28): payload `live` {url = config.LIVE_CSV_URL, pulse, etfs}; the page fetches the Google sheet (same parser as v1, no anchors)
  and ../premarket.json (every 2 min while relevant, `liveTick`). `liveMode()`: "live" / "closed" = sheet session newer than S.asof (open /
  after the close), "pre" = today's Yahoo snapshot before 9:30, else official close; header badge (`setMode`). `applyLive` pushes quotes into
  the data (originals kept): stock price/today, group Today column = avg of members with quotes (header reads Live / Pre-mkt), lined-up rows
  redone by `luState` (same math as lineup.state / v1 lineupState: live 9/21 EMAs, sheet column L low; adds "over the trigger"), picks.
  Live pages re-render in place (`LIVE_PAGES`, skipped while typing). Market → Pre-market & live (`pageLive`): futures/macro before the open or
  index pulse after, theme-stock breadth, strongest/weakest sub-themes, sector ETFs, movers ≥ 1 ADR (gap + steady flag pre-market).
  SEARCH (Oct 28): header box (#q, "/" focuses) → tickers / sub-themes / themes; any ticker link (a.tk) opens the drawer (`openTicker`: price
  live, RS, 5/30d, off high, vs 21 EMA, ADR, its groups with stage, setups & plan lines, lists it's on, TradingView chart link); a group jumps
  to the Themes table opened on it. Phone: drawer is a bottom sheet. Prototype history: branch `v2-prototype`. Test `test_v2_page_builds`.
  Local check: `python3 -c "import json; from breadth import v2site; v2site.build(json.load(open('docs/data.json')))"`, then
  `git checkout -- docs` before committing.
- `site.py` + `template.html` single self-contained page. **Layout since Oct 29, 2026** (Adam tried v2 and preferred v1's content: "organization
  was the biggest flaw, not the content"; every card kept): 10 tabs `TABS` = Read-out (default), Breadth, Pre-market, Intraday, Themes, Rotation,
  Biotech, Setups, Stocks, Trade Stories. Setups = `renderSetupsAll`: part 1 Best setups (`renderBest`), 2 Trade setups (`renderTrades`), 3 Launch
  list (`renderLaunch`), 4 Leaders & momentum (`renderSetups`), with `partDiv` headers; `ONCE` / `once()` stops the live bar and Launch picks card
  from repeating. Themes = `renderThemesTab`: View chips table (`renderThemes`) / browse (`renderBrowse`), localStorage themesMode. Old hashes
  (#best #trades #launch #browse) map through `TAB_ALIAS` / `tabOf`. Every tab: `decoratePanel` (called by `renderTab`) adds a sticky "On this
  page" jump bar (cards' titles via `cardTitle`: .head h2 / .kicker / summary, badges stripped) and a ▾ fold button on each card (state per
  tab+title in localStorage "folds"); tabs bar is sticky. Header: ticker search (#tq, "/" focuses → `openTicker` drawer: live price, RS, groups
  with Strength + lifecycle stage, every setup / list it's on with plan, positions, TradingView link) and a Theme: Auto/Light/Dark button.
  **My positions** (`posCard` at the top of Read-out and Intraday; `posState` rules: stop / near stop, under 10 or 20 EMA (live EMAs during the
  session, "decides at the close"), day 3–5 partial, break-even after a partial) read Adam's trades from the "Positions" tab of the live sheet
  (gid 810220388; `config.POSITIONS_CSV_URL` / `POSITIONS_EDIT_URL` → payload `pos_url` / `pos_edit`; columns ticker | bought | entry | shares |
  stop | sold | setup | notes + GOOGLEFINANCE price / closeyest / low / high). Nothing about positions is stored in the (public) repo.
  EOD references `breadth/positions.py` `refs` → `DATA.themes.posrefs` {date, dates (40), rows t: [close, e10, e20, adr %, high, low]}
  for every $3+/$2M+ ticker (test `test_position_refs`). TradingView export modal unchanged.
- `data/themes.csv` (theme,ticker,role) 81 themes · `data/subthemes.csv` (group,subtheme,ticker) 156 peer groups (Oct 15: every S&P 500 / Nasdaq-100 member now has one — 258 added, 29 new groups e.g. Mass Merchants & Grocers (WMT, COST), Beverages, Tobacco, Household & Personal Care, Packaged Foods, Home Improvement, Consumer Hardware (AAPL), Asset Managers, Exchanges & Financial Data, Insurance Brokers, Conglomerates (BRK.B), Drug Distributors, Railroads, Chemicals; UNH/ELV/CI/CVS into Managed Care; only dup classes GOOG/FOX/NWS left out. `themes.build` now lists sub-theme-only stocks too (themes = []), so stocks went 861 → 1,117); swept Oct 11: renames PSTG→P, BK→BNY, SATS→ECHO, ERJ→EMBJ; 21 dead tickers dropped; 154 strong names added
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
  Round Number Magnet (Oct 14) = RS ≥ 85, above 21 & 50 EMA, ADR ≥ 2.5, next big round number (`tradesetups.ROUND`: 10, 20, 25, 30, 40,
  50, 75, 100, 150, 200, 250, every 100 to 1,000, every 500 to 5,000, every 1,000 above; ≥ 0.2% above the close) within 1.5 ADRs;
  row fields `round_lvl/pct/adr`, `round_fresh` (level above the 52-wk high), `round_century` (multiple of 100, or 50); ranked fresh →
  century → Leaders score; plan = buy open, stop 1 ADR, target the level. Backtest = buy close, stop 1 ADR, 5 sessions, plus
  `trade_bt.round` (fresh / retest / century / smaller / base = same strong stocks NOT near a level, touch + close-above rates) ·
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
- Round Number Magnet first backtest (Oct 14, 2026, ~Mar–Oct 2026): all +0.12R (n 1,859) vs the same strong stocks not near a level
  +0.11R → the level alone adds little. Edge sits in fresh levels in good tape: after a thrust +0.30R all / +0.42R fresh vs base +0.20R;
  strong breadth fresh +0.36R vs base +0.22R; mixed fresh +0.07R vs base +0.17R; weak −0.01R (base −0.10R). Century marks ($50/$100/$200…)
  +0.01R vs smaller levels +0.18R (centuries act more like resistance). Level traded within 5 sessions 57% (closed above 42%); fresh 50% / 36%.
- Group ignition study (Oct 14, 2026; `tools/ignition_study/`; 101 sub-themes, Jan 2025–Oct 2026, event = first day in 20, outcome =
  group vs SPY). Refiners' run (Jun 18 low → +100% by Oct 13 vs SPY +4%) fired in order: crack spread +14% (20d) Jun 24 → group breadth
  0% → 89% above 21 EMA by Jun 29 → RRG leading Jun 30 → dollar flow +0.43, RS-rank +45 pts/10d and 40-day base breakout Jul 6
  (index +16% off the low) → rel 60-day high + confirmed tier Jul 8–9 (+23%). IGNITION = group index at 40-day high + 10-day dollar flow
  > +0.25 + 80%+ of members above 21 EMA + RS-rank (20d rel return pct) up 30+ pts in 10 sessions: all groups 20d +2.9% vs base +1.4%
  (median +1.3% vs +0.3%, t 1.9; 40d +5.0% vs +3.4%, win 57% vs 47%), both halves similar. In strong breadth (10-day ratio ≥ 1.5)
  +4.0% (edge +2.6 pts, t 2.4); otherwise no edge (−0.25). Market money net in vs out (dn_share10) made no difference. Macro driver up
  8%+ in 20d +5.5% (n 16) vs +3.6% (n 52) — small sample. Singles: dollar flow alone, RS jump alone, RRG leading alone ≈ base or worse;
  base breakout +2.5%, rel 60d high +2.7%. Refiners IGNITION dates: May 12 2025 (+27% 40d), Aug 29 2025 (+11.5%), Feb 11 2026 (+20%),
  May 4 2026 (−3%, false start), Jul 6 2026 (+37%), Sep 2 2026 (+9% 20d). Built Oct 14: `rotation.ignition_build` →
  `DATA.themes.rotation.ignition` → "Group ignition" card (Rotation tab, under the money card): gate Act (10-day ratio ≥ 1.5) / Watch only,
  evidence recomputed each build (all / strong / other vs base, next 20 sessions), 🔥 Ignition (fired in last 5 sessions, rel since),
  Warming up (3 of 4 checks, or group breadth thrust in 10 days + RRG leading), checks as of last close, breadth, flow, RS-rank Δ, 20d vs
  SPY, macro drivers (d30, up = +8% or yield up), Strength, top 4 stocks by RS with Trade Setups tags; recent ignitions (60 sessions).
  Live (Oct 14): `ignition.live[g]` (members, idx, hi39, rel20, rk10, f9/d9 signed/total $ vol of the last 9 sessions, brmin9, thrust9,
  rrg, ign20, ago) + `ignition.spy`; `liveIgnition()` in the browser finishes today's checks from Google prices + `refs` ema21 when
  `liveActive()` (sheet session newer than our bars). Verified Oct 13 (copy with that day's bars removed, Oct 13 bars as "live"): 14/15
  flagged groups identical status + checks, breadth/flow/RS-rank within ~0.02; the miss was RRG-only warming (RRG stays last close).
- "Day 1" group breakout study (Oct 14, 2026, `tools/ignition_study/day1.py`, prompted by large-cap pharma breaking out of 2-month
  bear flags on Oct 14 while scoring 0/4 on ignition: index 2.7% below its 40-day high, 10-day flow −0.01, breadth 67%, RS-rank +9).
  DAY 1 = group beats SPY by 2%+ on 1.3×+ normal $ volume, half its members close above their prior 10-day closing high, group 3–15%
  below its 60-day high the day before. Alone: no edge (20d +1.3% vs base +1.4%, n 264); strong breadth +2.7% (t 1.0), otherwise −0.4%.
  Follow-through decides it: Day 1 still above its close 3 sessions later → next 20 sessions +3.4% (n 132); faded → −0.7% (n 129).
  39% of Day-1 events (106/272) became an IGNITION within 15 sessions. Built Oct 14: `rotation.DAY1` rules, `ignition.day1` = {rows (Day 1 in last 6
  sessions: rel_d1, r1, rv, brk, d3 = rel 3 sessions later, since), bt (all/strong/other/held/faded), live (per group hi10 per stock,
  dv50, off, d1_20)} → "Day 1 · watch for follow-through" section of the Group ignition card (between Ignition and Warming up);
  browser `liveDay1` (with `ignLiveGroups`, shared with `liveIgnition`) adds today's Day 1s from Google prices (dollar volume paced by
  `volPace` while open), rolls follow-through forward, and lists "almost a Day 1" groups one rule short (Oct 14: Large-cap Pharma 1.16×).
- Cybersecurity case study + ignition iteration (Oct 14, 2026; `tools/ignition_study/cyber.py`, `cyber2.py`, `iterate*.py`; train/test
  halves split Dec 26, 2025). Cybersecurity Platforms and Identity & Security Tools both bottomed Apr 10, 2026 (rel −45% / −56% vs
  Jun 2025) and ran +131% / +166%. Sequence: group breadth thrust from a washout Apr 21/22 (+16–23% off the low; Identity already
  3 of 4 = warming) → flow > 0.25 Apr 24 → IGNITION May 7 for both (+29–30% off the low; next 40 sessions +28% / +55% vs SPY) →
  re-ignitions Jul 2–6, Aug 13, Sep 17, Oct 9 as they kept making highs. No Day 1 at the start (V-bottoms, > 15% below the 60-day high).
  The same-day gate said "watch" on May 7 (10-day ratio 1.40) although ratio hit 2.95 on Apr 17. Across all groups: leaders present
  (members' median 63-day RS pct ≥ 70 or 25%+ within 3% of a 52-wk high) +4.7% 20d / +8.1% 40d vs +2.0% / +3.0% without (base
  +1.9% / +3.9%), both halves; leaders + strong today +5.8%, leaders + strong only within 15 sessions +4.0% (40d +9.8%), no leaders +
  not strong −0.5%. Not useful: group breadth thrust alone (+1.4%, ≈ base), tight 40-day base (worse, +0.6%), coming from a 25%+
  drawdown (test half ≈ 0). Re-ignitions ≈ first ignitions at 40d. Identity's May 7 ignition had NO leaders (RS med 36) and still ran:
  grades are odds, not vetoes. Built: `IGN.gate_days` 15 (Act = ratio10 ≥ 1.5 any of the last 15 sessions, `ignition.peak15`),
  `ignition_frames` → `rsmed`, `near`, `lead`; rows/live/day1 rows carry `lead {ok, rsmed, near}`; bt adds lead / nolead /
  lead_strong / lead_other / c, day1 bt adds lead / nolead / held_lead / held_nolead; card shows Grade A (leaders + strong window) /
  B / C on ignitions, "★ has leaders" / "no leaders yet" on every row, Leaders column in recent ignitions.
- Record-volume "tells" study (Oct 12, 2026; 2,048 events Oct 2025–Sep 2026, no index/expiry days; 10-session return vs
  SPY, clipped ±50%; tells found on the first 60% by date, checked on the last 40%): all events −4.9% train / −7.7% test.
  Consistent AVOID tells (both halves): gap up 10%+ or up 20%+ (−15 to −18%), volume > 20× avg or > 2.2× old record,
  ADR > 10%, avg $ volume < $5M, down 20%+ over 60 days, 30%+ below the 52-wk high, breakout to a new 20-day high,
  2+ ADR above the 21 EMA. RS did NOT help: RS 95+ +0.7% train → −13% test; the decision tree's only positive leaf
  (RS > 95.5, liquid) +9.5% → −2.6% test. Cleaned set (avg $ vol ≥ $25M, ADR ≤ 10, × avg ≤ 20, gap < 10%, day < +20%,
  ≥ −30% off high, 60-day > −20%) ≈ flat vs SPY. Only candidate: cleaned + 3–10% below the 52-wk high: +1.9% (t 2.7,
  59% beat, n 130; train +2.1% t 2.7, test +1.35% t 1.0; fades by 20 sessions) vs −0.2% / 47% for ANY liquid stock 3–10%
  off its high. Promising, not proven; re-test as more data arrives.
  Retracement follow-up (same events, up days): buying a hold of the record day's 50% / 61.8% / low, or of the 38.2 / 50 / 61.8%
  retracement of the 20-session leg into the record day (touch within 20 sessions, close above), at the hold-day close or on a
  "pop back" (close above the hold day's high within 3 days), with or without a stop 0.5 ADR under the level: negative in both
  halves for all events (−1% to −9% vs SPY); cleaned set slightly positive in train (+0.3 to +2%), negative in test. No edge.
  By market type (first level touched per event, hold-day close): all events negative in every breadth regime and SPY trend
  (strong −6.1% t −4.4, mixed −6.8% t −6.6, weak −2.4% t −2.6; SPY uptrend −6.1% t −8.0, downtrend −3.0%); worst in strong/mixed
  and SPY uptrends. Cleaned set ≈ 0 in all; strong breadth + deeper leg retracements (38.2/61.8%) +2–3% but n 22–31, and strong
  train +1.8% → test −3.2% (n 13). Strong-breadth sample too small to trust.
  SHORT after the pop (up-day records, entries from day 3; cover on close > stop, close > 10 EMA, or 10 sessions; no borrow
  costs): A "turn" = close below record-day low (stop = post-pop peak); B = close below prior 3-day low while below record close
  (stop = 4-day high); C bear flag = ≥ 2 ADR drop then 3–7 day flag ≤ 1.5 ADR, close below flag low (stop = flag high).
  Spike profile (gap ≥ 10% or day ≥ +20% or × avg > 20 or > 2.2× old record) A: +8.1% train / +6.9% test (57% win), but the
  edge is in thin names (< $5M avg $ vol: +10% mean, worst −164%, 8% of trades lose > 30%, median stop 71% away → +0.04R);
  mid $5–25M A +8.8% / B +0.14R; liquid $25M+ ≈ 0 (A +0.3%, B −1.2% test, C −2%). Non-spike: no edge. Bear flag weakest.
- Limits: survivorship bias in backfill, small strong-regime sample, no costs, no intraday H/L/volume.

## To-do list
**ROADMAP.md** in the repo root is the running to-do list (priorities, review dates, done). Read it at the start of a work session
and keep it current.

## Play ideas Adam logged (not built yet — ask where they go before building)
- Oct 13, 2026 — "Theme breadth play" (95–100% of a theme's stocks up): DROPPED by Adam Oct 27.
- Oct 13, 2026 — "Top late mover": BUILT Oct 27 as a watch line (`lateLeader`, see below); tested, not proven.
- Oct 27, 2026 — to-do: a "my positions" card for Adam's own real trades that flags his exit rules live (sell part after 3–5
  days, trail the 10/20 EMA, stop alerts). Not started.
- Oct 27, 2026 — "R stacking" (Adam: "this trade is 0.8R, that one 0.5R, but layered together 1.3R — keep making this smarter"):
  first test bed `tools/rstack/box_stack.py` on Box trades (see Findings). Goal: a common trade warehouse across setups + a stacked
  expected R per live trade, with synergy pairs validated out of sample, refreshed weekly for the Integrator.

## Working preferences
- Start every answer with a TL;DR, then detail.
- Ship working changes; verify with `--rebuild-only`, the tests, and a headless browser check before pushing.
- Don't run long blocking polling loops.

## Decision Cards + agents (Oct 16–17, 2026) — read DECISIONS.md
- Principle: code measures, agents read, only proven layers move the score. Nothing here re-ranks the Top 2 picks.
- `macrofit.py` rate/oil/dollar sensitivity (market-neutral OLS, 120 sessions, |t| ≥ 2 only) + 5/20-day tailwind; `macro.json`
  now holds 2 years (`config.MACRO_RANGE`; `.github/workflows/macro.yml` refreshes it on demand).
- `decision.py` 7-layer cards (Market, Group, Setup, Macro fit, Calendar, Catalyst, Macro brief) for picks / watch / ~20
  candidates → `DATA.themes.decision`, Trade Setups tab `decisionCard`; every layer logged to `data/decision_log.csv`,
  settled next open → close 5 sessions later vs SPY.
- `layers.py` evidence → `data/layer_evidence.json` (`macro` backtest via in-memory signal capture, `log` forward test,
  `report`). Pass rule: t ≥ 2 over ≥ 20 dates and same sign in both halves.
- `agentfiles.py` worklist / schema / publish (validates, dispatches `agent.yml`) / save. Agents never write code or weights.
- Forward log has no look-ahead: `decision.record` freezes a date's rows at `nyse.entry_cutoff` (9:30 ET next session)
  and drops agent files written after it; `agentfiles publish` refuses after it. Holidays: `breadth/nyse.py` (by rule).
  Layers only color cards after a passed backtest AND `config.APPROVED_LAYERS`. `tools/check_info_only.py` = e2e proof.
- **Research ledger + registry + Integrator** (Oct 17): `research/R-*.md` finding cards (`breadth/research.py`: check / digest / new),
  `data/layers.json` registry (ladder idea→tested→info→proven→approved→live, retired), "Market Monitor · Integrator" Sat 10:07 AM ET
  → `docs/agent/plan.json` (kind `plan`). **Every research chat ends by filing a card** (`python -m breadth.research new ...`),
  updating `integrated` on cards and `status` in the registry when something is built. "build #N" = build Integrator plan item N.
- Scheduled tasks: "Market Monitor · macro brief agent" 7:02 AM, "· catalyst agent" 7:12 AM (Mon–Fri), "· weekly layer
  review" Sat 9:07 AM (push notification).
