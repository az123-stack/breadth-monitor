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
