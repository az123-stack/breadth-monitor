# Breadth Monitor

A self-updating market breadth dashboard modeled on Stockbee's Market Monitor.
Every weekday morning a GitHub Actions job pulls the previous day's bars for
all US common stocks from Massive (formerly Polygon.io, free plan), recomputes
the breadth metrics, labels the market regime, and republishes a dashboard on
GitHub Pages. Nothing runs on your computer.

## What it tracks

| Metric | Definition |
|---|---|
| Up / down 4% | Stocks closing ≥ 4% above (below) the prior close, on volume above the prior day and ≥ 100k |
| 5-day / 10-day ratio | Sum of 4% up days ÷ sum of 4% down days over the window |
| 40-day avg | 40-day average of the daily up-4% count |
| Up / down 25% quarter | Change over 65 trading days |
| Up / down 25% and 50% month | Change over 20 trading days |
| Up / down 13% in 34 days | Change over 34 trading days |
| T2108 | % of stocks above their 40-day moving average |

Universe: US common stocks (no ETFs, warrants, preferreds) closing ≥ $3. The
slower metrics and T2108 also require 20-day average volume ≥ 100k. All of
this is set in `breadth/config.py`.

The regime label (Washed out / Breadth thrust / Overextended / Strong uptrend /
Deteriorating / Choppy) uses starter thresholds. Once a few months of history
exist, adjust them in `config.py` — the dashboard shows where each reading sits
in your own history to help.

## Themes and Stocks tabs

Theme rotation scoring ported from the "Trading Dashboard v12" sheet, computed
daily from the same price data (no Apps Script, no GOOGLEFINANCE).

- **Edit the themes** in `data/themes.csv` (`theme,ticker,role`). `role` is
  `member` for stocks that count toward the theme, `etf` for its benchmark ETF.
  New tickers that aren't common stocks (ETFs, ADRs) are backfilled
  automatically on the next run; tickers with no data are listed under the
  Themes table.
- **Theme score (/8):** +1 each for positive average Today, 5D, 15D, 30D, RS and
  LT score; +1 if ≥50% of members are up today and over 5 days (ST breadth);
  +1 if ≥60% are up over 15 and 30 days (LT breadth). 7–8 strong, 4–6 watchlist.
- **RS:** % change over ~3 months (63 trading days), as in the sheet.
- **Rotation:** Late/Cooling (30D > 5%, today and 5D down), Mid (today up,
  5D > 3%, 15D and 30D > 5%), Early (today up, 30D > 5%), else Neutral.
- **Setup score (/10)** and **Market Pulse long/short (/10)** use the sheet's rules.
- Rank movement (themes and stocks) is computed from stored history, so it
  works without daily snapshots.

## Version-2 measures (RS Rating, Theme Strength, Setups)

- **RS Rating (1–99)**: weighted 3/6/9/12-month return (40/20/20/20) ranked
  against ~3,000 liquid US stocks; ★ RS line vs SPY at a 1-year high, ⚑ the same
  while price is below its high. The sheet's 3-month % is kept as "3M %".
- **Theme Strength (0–100)**: percentile composite across groups of median
  relative performance vs SPY over 5–90 days (50%), share of members above
  their 21/50-day EMAs (25%) and median RS Rating (25%); excludes today's move;
  groups under 5 stocks are shrunk toward 50. Themes rank by Strength by
  default; the sheet's Score /8 is one click away.
- **Tightness**: ADR %, 5-day range in ADRs, NR7/inside days, volume dry-up,
  distance from the 52-week high.
- **Setups tab**: Momentum bursts (Stockbee 4% breakouts with a 2LYNCH
  checklist), Anticipation (tight coils in leaders) and Episodic pivots, plus
  a table of how each list has traded by breadth regime (recomputed daily).
- `tools/evaluate.py` compares v2 and v1 on stored history (rank stability,
  forward-return IC, list results).

What the history showed (Feb–Oct 2026): Theme Strength ranks are far more
stable than Score /8 (day-to-day rank correlation 0.96 vs 0.79), but neither
predicted 10-day theme returns. Setups made money only in strong breadth
(bursts +0.16R, anticipation +0.18R per trade) and lost in weak breadth;
EPs without a catalyst check lost in every regime.

## TradingView watchlist export

The **⬇ TradingView list** button (top right) downloads a .txt watchlist
(`###Section,NASDAQ:XXXX,...`). In TradingView: watchlist menu → Upload list.
Sections, in priority order (a ticker appears only in the first section it
qualifies for): momentum bursts (2LYNCH 5+), anticipation coils, RS leads
price ⚑, RS line new high ★, RS Rating 99, fast risers (RS +15 in 5 days),
top 2 themes, top 3 sub-themes not already covered, bottom 2 themes (short
watch), episodic pivots (off by default), and market/theme ETFs. Each section
can be switched off before downloading. It uses live prices when they're loaded.

## Sub-themes and the Browse tab

`data/subthemes.csv` (`group,subtheme,ticker`) puts every stock in exactly one
peer group by what it sells (e.g. *Enterprise AI Infrastructure*: DELL, HPE,
NTNX, PSTG, NTAP), scored with the same rules as themes. The Themes tab has a
Themes / Sub-themes switch, the Browse tab lists every name bucket by bucket
(expand or collapse all, search), and the Stocks tab filters by either.
Returns are shown short-term (Today–30D) or long-term (30D–180D); long
horizons need about a year of stored bars (run the workflow once with
"extend history").

## Live prices during the day (free)

The Themes and Stocks tabs can update intraday from a Google Sheet that uses
GOOGLEFINANCE (one row per theme ticker), published to the web as CSV. The page
fetches it when opened, on **Refresh**, and every 3 minutes while open, then
recalculates every return, score, rank and the long/short pulse in the browser
using reference closes from the nightly run. Prices that differ from the last
close by more than 50% are ignored (wrong listing or bad print). Set the
published CSV link as `LIVE_CSV_URL` in `breadth/config.py`. The Breadth tab
stays end-of-day.

## One-time setup (about 10 minutes)

1. **Get a free Massive API key** at massive.com → Dashboard → API Keys.
2. **Create a GitHub repository** (private is fine) and push this folder to it.
3. **Add the key as a secret**: repo → Settings → Secrets and variables →
   Actions → New repository secret. Name: `MASSIVE_API_KEY`.
4. **Allow the workflow to commit**: Settings → Actions → General → Workflow
   permissions → "Read and write permissions".
5. **Load history**: Actions tab → "Breadth update" → Run workflow → set
   `backfill_days` to `730` (the free plan's two-year limit). On the free plan's
   5 calls/minute this takes about two hours. If it stops early, run it again;
   it picks up where it left off.
6. **Turn on the dashboard**: Settings → Pages → Deploy from a branch →
   `main`, folder `/docs`. Your dashboard URL appears there.

From then on the workflow runs Tuesday–Saturday at about 6:17 AM ET, covering
the prior trading day. GitHub emails you if a run fails.

Note: GitHub pauses scheduled workflows in repos with no activity for 60 days.
The daily data commits count as activity, so this shouldn't trigger while the
job is running normally.

## How it works

- `breadth/massive.py` – API client (grouped daily bars, common-stock list, splits), rate-limited for the free plan
- `breadth/store.py` – raw bars stored as one small parquet file per day in `data/bars/` (last 160 trading days); split adjustments are applied in memory each run, so files are never rewritten
- `breadth/metrics.py` – the metrics and the regime classifier
- `breadth/site.py` + `template.html` – builds `docs/index.html` with the data embedded
- `data/breadth.csv` – full breadth history (also downloadable from the dashboard)

Run locally:

```
pip install -r requirements.txt
export MASSIVE_API_KEY=...
python -m breadth.update --backfill-days 730   # first time
python -m breadth.update                       # daily
python -m breadth.update --rebuild-only        # recompute + rebuild page, no API calls
python tests/test_pipeline.py                  # offline tests
```

## Known limitations

- **Survivorship bias in the backfill**: the universe is today's active stocks,
  so names delisted during the backfill window are missing from older days.
  Live daily readings aren't affected.
- **Numbers won't match Stockbee's exactly** because the universe differs.
  Judge readings against this dashboard's own history.
- If the free plan ever stops serving split data, the run continues and logs a
  warning; a split would then show up as one false 4% move for that stock.
