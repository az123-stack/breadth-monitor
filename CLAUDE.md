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
  Columns J:K `at10` / `at11` (Oct 13) freeze each row as "TICKER|price|volume" at the first recalc after 10:00 / 11:00 ET, using
  iterative calculation (File → Settings → Calculation, max 1 iteration — must stay ON) and self-referencing formulas; blank before
  that time on weekdays, held overnight/weekends; a row whose ticker moved reads "TICKER|x" (page ignores it). J2/K2 hold the freeze
  time ("yyyy-mm-dd hh:mm" ET). The sheet's timezone is America/Los_Angeles, so formulas use NOW()+3/24 for ET — if the sheet timezone
  changes, fix those. Self-reference starts at 0, hence the OR(J4="",J4=0) checks.

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
  after a major Breadth thrust / Follow-through, `metrics.thrust_window`) else breadth regime; ranks all 7 setup types
  (4 Trade Setups + bursts, anticipation, EPs) by backtested avg R in that state: Focus ≥ +0.15R, Selective ≥ 0, Avoid < 0,
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
  ET, committing each snapshot (crons 09:52 + 10:52 UTC Mon–Fri, plus the 5:48 AM Claude task dispatches it). Page reads
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
  Comeback study (`tools/ignition_study/comeback.py`, Feb 2025–Oct 2026): heavy-selling day in an outflow streak (n 18) → SPY median +1.7%
  next 10 sessions, sold-hardest sub-themes +4.3% vs SPY (median +3.2%, 78%) vs held-up +0.5%; ex Mar–Apr 2025 +3.9%; any 70%+ day (n 24)
  sold +1.9% / held +1.0%. First calm comeback day (n 9) → SPY median −1.2% next 10, held-up +1.7%, middle +1.5%, sold −0.1%; 60-day
  leaders +3.1% over 20. Read: snapbacks start around the heavy-selling days; after a calm comeback day follow what held up.
- `boxes.py` **Box breakout retest** (Oct 16, 2026; Adam's chart: Loew's 1936 rectangle from Edwards & Magee) → `DATA.themes.boxes`,
  card `boxCard` on Trade Setups (after the six setup cards). Box = longest 10–130-session range ≤ 3/4/5/6 ADRs (windows 2–4 wk,
  4–8 wk, 2–3 mo, 3–6 mo; max 25%), 2+ touches of top and bottom, flat (fit ≤ ½ height), after a 15%+ / 4+ ADR advance in the prior
  40 sessions, box volume ≤ 0.9× the advance. THE TRADE = breakout → pullback to the old top → bounce (`RT`, `retest_walk`): tags
  🔵 coming back (ran 1+ ADR past the top, now 1+ ADR off the high, within 3 ADRs), 🟡 at support / back inside (low within 0.5 ADR
  of the top, no bounce yet), 🟢 bounced (close > prior high and > top after the touch, last 2 sessions). Dead on a close under the box
  middle; 25 sessions to touch / bounce. Stop = retest low; target = top + height. Grade A = RS 80+ & 2–4 wk box, B = RS 80+.
  `rows` = plain box scan (pipeline: breakout today / recent / near top / in box); `rt` = retest tags; `rt_study` = research, `now`.
  Chips: box length + scope (remembered "boxWin"); ⬇ exports the three lists. Adds ~70 s to the build.
  Research (Jan 2025–Oct 2026, 4,083 breakouts → 2,942 touched → 2,353 bounces; buy bounce close, stop retest low, else 20 sessions):
  all +0.09R (35% win, t 2.3; halves +0.19 / 0.00). After a major thrust (25 sessions) +0.22R (t 3.3, both halves); thrust + RS 80+
  +0.50R (t 3.8, 42% win, halves +0.60/+0.47, n 271); + 2–4 wk box +0.68R (n 146). No thrust ≈ 0 (+0.01R; RS 80+ −0.08R, 2nd half −0.48);
  strong breadth without a thrust −0.09R; weak breadth −0.08R. Breakout volume, pullback volume, held-above vs dipped-inside: no
  consistent difference. Buying the breakout itself lagged SPY (−0.4% 10d vs −0.6% for any 20-day-high break). Banner = Act inside a
  thrust window, else Watch. Monthly R was negative Jul–Oct 2026 (no thrust). Not in the playbook / Top 2 picks yet.
- `site.py` + `template.html` single self-contained page (tabs: Read-out (default), Breadth, Pre-market, Intraday, Trade Setups, Themes, Rotation, Browse, Setups, Stocks; TradingView export modal)
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

## Play ideas Adam logged (not built yet — ask where they go before building)
- Oct 13, 2026 — "Theme breadth play": any theme at 95–100% breadth (share of its stocks up; Energy-Oil hit it Oct 13) should be
  flagged every day, and he wants to look at / play its top 2 stocks.
- Oct 13, 2026 — "Top late mover": the strongest mover after the morning window (window not yet defined in this repo's history;
  confirm with Adam — likely after the first 30–60 min).

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
- Scheduled tasks: "Market Monitor · macro brief agent" 7:02 AM, "· catalyst agent" 7:12 AM (Mon–Fri), "· weekly layer
  review" Sat 9:07 AM (push notification).
