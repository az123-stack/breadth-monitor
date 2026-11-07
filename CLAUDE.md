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

## Code map (index — full detail in CODEMAP.md)
One line per module. Before changing a module, read its entry in **CODEMAP.md** (grep the file name). New modules: add the full note to CODEMAP.md and ONE line here. Keep this file under ~25 KB: it is loaded into every session.
- `breadth/config.py` settings and thresholds · `massive.py` API client
- `store.py` parquet bars in `data/bars/` (500 trading days ≈ the free plan's 2-year reach, raw; splits applied in memory),
- `update.py` entry point: `python -m breadth.update [--rebuild-only] [--backfill-days N] [--extend-history]`
- `metrics.py` breadth metrics, regime classifier, chart events. New highs/lows (Oct 12): `nh`, `nl`, `nhnl`, `nh10`, `nl10`
- `themes.py` sheet port: theme Score /8, rotation, setup score, long/short pulse, ranks, payload
- `strength.py` v2: RS Rating, RS-line ★/⚑ flags, tightness, Theme Strength
- `setups.py` momentum bursts (2LYNCH), anticipation, episodic pivots, regime trade stats
- `leaders.py` Leaders ranking → `DATA.themes.leaders`; Setups tab "Leaders" panel (Top 10 / One per group), recomputed live in the browser by …
- `tradesetups.py` Trade Setups tab: ATH Magnet, Round Number Magnet, Leader Pullback, Rotation Rookie, Qullamaggie Flag, Minervini VCP (top 5 …
- `review.py` "⚑ Review setups" flag (header button + card on Trade Setups) → `DATA.themes.setup_review`; checks regime change
- `playbook.py` "Today's playbook" card at the top of Trade Setups → `DATA.themes.playbook`: state = post-thrust (25 sessions
- Top 2 trades (`playbook.picks`, card at the top of Trade Setups): top 5 of each Focus setup (+ Selective if < 2
- Pick context re-rank (Oct 15; `playbook.context_fn` / `rerank`, called in update.py right after `rotation.build`, before the ledger
- Pick scoreboard (`ledger.py` → `data/pick_ledger.csv`, `DATA.themes.scoreboard`): logs picks each morning; next session
- Conviction tags (`tradesetups.TAGS`, row/pick `tags`): ⚑ RS ahead, ★ RS high, RS 99, RS riser, burst, coil, top-10 market,
- Whole-market leaders (`lists.strongest`, Setups tab Leaders → "Any theme"): all US stocks $10+, $20M+/day, RS ≥ 90,
- `levels.py` all-time highs and old monthly peaks from Yahoo (free; Massive free plan only reaches ~2 years), cached in
- `kq.py` KQ breakout screen → `DATA.kq` (Basing / Extended / Not this setup or failing a rule); "⬇ KQ list" button exports it to TradingView
- `washout.py` (Oct 16) Washout thrust card on the Breadth tab → `DATA.themes.washout`. Classifies each dashboard thrust
- `intraday.py` Intraday tab config → `DATA.intraday` (index members + sectors from `data/index_members.csv`, pulse symbols,
- `premarket.py` + `.github/workflows/premarket.yml` → `docs/premarket.json` → **Pre-market tab** (`renderPremarket`, Oct 14): Yahoo
- `macro.py` Macro drivers strip → `DATA.macro`: Yahoo daily closes (CL, BZ, RB, HO, NG, GC, SI, HG futures, ^TNX, DX-Y.NYB, ^VIX,
- `rotation.py` Rotation trade ideas → `DATA.themes.rotation` (top card on the Rotation tab, `rotationIdeasCard`): equal-weight
- `hve.py` Record volume card on Trade Setups (`hveCard`) → `DATA.themes.hve` (computed inside `strength.build_v2`): stocks
- Money flow card (top of Rotation, `moneyFlowCard`) → `rotation.flow`: Relative Rotation Graph per sub-theme (x = 100 × group/SPY ÷
- "Where's the money going · today" (`moneyTodayCard`, Oct 14; top of the Rotation tab only — removed from Intraday Oct 15 at Adam's request): …
- Rotation tab (browser-only rendering): ideas card · pair chart (`pairCard`: two groups' equal-weight index, ratio and
- Strength history uses `strength.group_inputs_many` (numpy, identical numbers to `group_inputs`, tested), which made
- Pick scorecard: `ledger.summary(..., history)` adds `card` (by setup, by playbook state on the pick date, by rank/month,
- Click-to-sort (Oct 14): every `.panel table` header sorts (generic delegated handler: `cellVal` parses numbers incl. %, ×, $, K/M/B,
- **Read-out tab** (Oct 14; default landing tab, `renderReadout`, `roPhase`): three `<details>` cards, the current one first and open
- **The story** (Oct 15; `breadth/story.py`, `story_guide.md`, top of the Read-out tab `storyCard`): scenario tracker A "money keeps
- `boxes.py` + `boxstudy.py` **Box trades** (Oct 16–17, 2026; Adam's charts: Loew's 1936 rectangle, HPE failed breakout, CRWV
- `sow.py` **Strength on Weakness** (Oct 21, 2026; Adam's weekly position setup, charts NRIX/APPN/AMPL/MTCH; card R-2026-10-21-strength-on-weakness,
- `leadership.py` **Market health** (Oct 22, 2026; Adam: "do leaders tell on the market?" + "count breakouts vs breakdowns"; card
- `thetrade.py` **The trade** (Oct 22, 2026; Adam: "how do we handle the trade in play?"; card R-2026-10-22-the-trade, layer `the_trade`, info)
- `stories.py` **Trade Stories tab** (Oct 22, 2026; Adam: "a tab where you put together news and earnings narratives into a cohesive
- `stairs.py` **Stair steps** (Oct 24, 2026; Adam: cyber broke out of its stair step Oct 22–23 and he couldn't see it across sessions;
- `dips.py` **Dip buys · 9 / 21 EMA** (Oct 24, 2026; Adam: "get in when price is wicking under the 9 or the 21 and coming back up", wants it live;
- `launch.py` **Launch list tab** (Oct 25, 2026; Adam's CDNA / DINO / NTRA charts: "what separates the ones that went"; card
- `polished.py` **Best Setups tab** (Oct 25, 2026; Adam: "a new tab for the polished setups"; card R-2026-10-25-polished-setups, layer
- `lifecycle.py` **Theme lifecycle · Watch → Buy** (Oct 27, 2026; Adam: "trigger a watch for a buy on a theme, activate a buy, and
- `rspull.py` **RS leaders pulling back** (Oct 29, 2026; Adam: a trader "finds tickers making new RS highs and waits for weakness"; card
- `emaprob.py` **EMA touch odds** (Oct 29, 2026; Adam: "% of time above the 9/21, then the 1st / 2nd touch"; same evening: "WEEKLY 9/21, time
- **RS period toggle** (Oct 29, Adam: "toggle the RS period rather than extra columns"): `strength.RS_SHORT` rs2w / rs4w / rs6w = 10 / 20 / 30-
- Performance + futures fix (Oct 30, 2026; Adam: "crack spreads are no longer in the intraday tab" + "a delay when I click"):
- `.github/workflows/rebuild.yml` (Oct 24): page-only rebuild (`--rebuild-only`, no Massive calls, queue `agent-rebuild`) so code changes
- `tools/orb_study/` ORB × sub-theme study (Oct 24, 2026; Adam): `download.py` 15-minute regular-session bars for ~1,040 liquid
- `earnings.py` **Earnings clusters** (Oct 27, 2026; Adam: "earnings results that together point to a theme, captured in the write-ups";
- **Headline picks = Launch picks + Lined-up buys** (Oct 27, Adam). Retired from the page: Top 2 swing picks (`picksCard`), Decision
- ★ in box grades (Oct 27, Adam approved): condition "★ Leading group (sub-theme top 30% on 60-day return)" in `boxstudy.conditions`
- Top late mover (Oct 27; `lateLeader` at the top of the Intraday Second-half movers card; card R-2026-10-27-late-mover; study
- 10-year yield tile (Oct 27, Adam): `intraday.PULSE` "^TNX" = Google `INDEXCBOE:TNX` (CBOE quotes ×10; the tile divides when > 20) → Intraday
- Scheduled-task models (Oct 27): "lined-up alerts (hourly)" and "10/11 snapshot kick" moved to Sonnet.
- Page tabs (Oct 27 cleanup): one `renderTab` table serves tab clicks and live refreshes (before, `rerenderPanel` lacked Best Setups and
- `reclass.py` **Theme upkeep · reclassification agent** (Oct 28, 2026; Adam: "an agent checking whether tickers need reclassifying into our
- **v2 page** — ON HOLD since Oct 29, 2026 (Adam: "you don't need to update that anymore, we will come back to it"). It still builds
- **v3 page** (Oct 30, 2026; Adam: "start over on the new dashboard ... go tab by tab and rebuild it; Themes first, as a sub under a
- **v3 Nov 4, 2026** (Adam): **Market parent** = Breadth / Pre-market / Intraday (v1 renderers). v3 lives in docs/v3/, so v3site rewrites the
- **Pop watch** (Nov 4, 2026; Adam: "sub-themes pop and then I forget them … that's exactly when I need to be grabbing them"; card
- **In Play** (Nov 5, 2026; Adam, after a Lance Breitstein transcript: "Let's have In Play under the stocks tab") → `breadth/inplay.py`
- `emerge.py` **Since the bottom** (Nov 7, 2026; Adam: "since 11/5, so it includes 11/6") v3 Groups → Since the bottom (`renderEmerge`); page picks the base close; info only. CODEMAP.md
- **AI Revenue setups** (Nov 5, 2026; Adam: "a separate tab for AI Revenue Setups where we look for all these stocks coming back into EMAs")
- **Trade warehouse · step 1** (Nov 4, 2026; Adam's VEEV weekly chart: "daily or weekly EMA pullback, and when?"; card
- **Rotation stage rewritten** (Oct 30, 2026; Adam: "energy/oil was showing Early but it's been climbing all year"): the sheet's rule
- `site.py` + `template.html` single self-contained page. **Layout since Oct 29, 2026** (Adam tried v2 and preferred v1's content: "organization
- `data/themes.csv` (theme,ticker,role) 81 themes · `data/subthemes.csv` (group,subtheme,ticker) 156 peer groups (Oct 15: every S&P 500 / …
- AI themes (Oct 29, 2026; Adam: "Box is what Wall Street wants: companies successfully monetizing AI"): themes.csv "AI & ROBOTICS - Enterprise
- `aimon.py` **AI Monetizers kept honest by the market** (Oct 29–30, 2026; Adam: "they're trying but it's not coming in yet" + "flag a new AI
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

## Findings so far
One line per study: `python -m breadth.research digest` (research/ cards). Early detailed notes: research/HISTORY.md.

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

## Strategy book (Nov 4, 2026)
Adam's own trading strategies live in the Claude Doc **"Strategy Book"** https://claude.ai/artifact/JwswLXGDoFnF2X26hwF8g7 (one page per
strategy: idea, where on the dashboard, buy checklist, entry/stop/size, evidence + research card, live trades, open questions; a strategy
log table with status Idea / Testing / Trusted / Retired). When Adam describes a new strategy, add a page there (docs tools) and file a
research card if it gets tested. Strategy 1 = Pop watch pullbacks (v3 Groups → Pop watch, Sort "Most pulled back").

## Working preferences
- Start every answer with a TL;DR, then detail.
- Ship working changes; verify with `--rebuild-only`, the tests, and a headless browser check before pushing.
- Don't run long blocking polling loops.
- **Usage budget (Adam, Nov 7, 2026: "make usage efficient without losing the data we need")**: at most 2 independent grader
  reviews per plan (ship after round 2; list open concerns on the card); no subagents unless a task needs them; read CODEMAP.md entries
  on demand instead of whole files; keep CLAUDE.md under ~25 KB. Agent models (Nov 7): Opus = Integrator, Librarian; Sonnet = review,
  reclass, catalyst, macro brief, data card, story am/pm; Haiku = lined-up alerts, 10/11 snapshot kick, midnight + morning kicks.
  "Daily Earnings Catalyst Tracker" email turned OFF (overlapped the morning story, macro brief and catalyst agent; re-enable in its settings).

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
- **Librarian · weekly Project brief** (Nov 7, 2026; Adam: a "sleep cycle" agent that consolidates what the project knows each week;
  card R-2026-11-07-librarian, process). Problem: the claude.ai Project's context doc ("Market Dashboard Context", what every Market
  Dashboard chat starts from) went stale while this repo stayed current. `breadth/librarian.py` (stdlib): `pack` = source bundle from
  the REPO ONLY, never chats (research/PINNED.md, data/layers.json, every card's one-line result, ROADMAP open items, the Integrator plan,
  DECISIONS.md, CLAUDE.md minus findings with a shortened code map, the approved brief); `check --file F` / agentfiles kind `brief`
  validate a draft: the 5 sections in order (Rules that never fade, How it runs, What's live, Findings, Open threads), every pinned rule
  word for word (pinned rules never decay; only Adam edits research/PINNED.md), ≤ 3,000 words, layers written `id (status)` must match the
  registry, every R- id must exist, every card dated on/after the approved brief's draft date must be named, no secret-looking strings,
  no "approved" header. Scheduled task "Market Monitor · Librarian (weekly Project brief)" Sat 11:07 AM ET (after the Integrator) drafts
  it and publishes `docs/agent/brief.json` (summary, brief, changes with sources) via `agentfiles publish --kind brief --push`, then
  notifies Adam with the change list. PROPOSES ONLY. When Adam says **"approve brief"**: pull, `python -m breadth.librarian diff` (show
  him the gist if he asks), `python -m breadth.librarian approve` (writes research/BRIEF.md with an `<!-- approved: … draft: … -->`
  header; refuses if the draft no longer passes), commit + push, then replace the Project doc "Market Dashboard Context" with BRIEF.md
  (Projects tool `project_write`, same path, without the header line). "reject brief" = do nothing; next Saturday drafts again.
  Test `test_librarian_brief`.
- Scheduled tasks: "Market Monitor · macro brief agent" 7:02 AM, "· catalyst agent" 7:12 AM (Mon–Fri), "· weekly layer
  review" Sat 9:07 AM (push notification).
