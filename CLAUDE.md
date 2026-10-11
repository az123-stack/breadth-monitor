# Breadth Monitor — project context

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

## Code map
- `breadth/config.py` settings and thresholds · `massive.py` API client
- `store.py` parquet bars in `data/bars/` (260 trading days, raw; splits applied in memory),
  themes/subthemes/names loaders, TradingView exchange map
- `update.py` entry point: `python -m breadth.update [--rebuild-only] [--backfill-days N] [--extend-history]`
- `metrics.py` breadth metrics, regime classifier, chart events
- `themes.py` sheet port: theme Score /8, rotation, setup score, long/short pulse, ranks, payload
- `strength.py` v2: RS Rating, RS-line ★/⚑ flags, tightness, Theme Strength
- `setups.py` momentum bursts (2LYNCH), anticipation, episodic pivots, regime trade stats
- `site.py` + `template.html` single self-contained page (tabs: Breadth, Themes, Browse, Setups, Stocks; TradingView export modal)
- `data/themes.csv` (theme,ticker,role) 79 themes · `data/subthemes.csv` (group,subtheme,ticker) 119 peer groups
- `tools/` build_themes, build_subthemes, evaluate (v1 vs v2) · `tests/test_pipeline.py` (run directly, 7 tests)

## Definitions
- Breadth universe: US common stocks ≥ $3 (ETFs/ADRs in themes excluded from breadth).
  4% up/down needs volume > prior day and ≥ 100k. T2108 = % above 40-day MA.
- RS Rating 1–99: 63/126/189/252-day returns weighted 40/20/20/20, percentile vs liquid stocks.
  ★ RS line vs SPY at 1-yr high; ⚑ same while price below its high.
- Theme Strength 0–100: percentile composite of relative perf vs SPY 5–90D (50%),
  % above EMA21/50 (25%), median RS Rating (25%); groups < 5 stocks shrunk toward 50.
- Anticipation: RS ≥ 85, ≤ 10% off high, ADR ≥ 4, 5-day range ≤ 1.5 ADR, volume dry-up ≤ 0.7.
- EPs: gap 8–60%, 3× volume, ≥ $5, ≥ $20M traded.
- TradingView export priority: bursts → anticipation → ⚑ → ★ → RS 99 → fast risers →
  top 2 themes → top 3 sub-themes (new names) → bottom 2 themes → EPs (off) → ETFs; de-duplicated.

## Findings so far (Feb–Oct 2026 history)
- Theme Strength ranks far more stable than Score /8 (rank corr 0.96 vs 0.79); neither predicts
  10-day theme returns, so weights were not tuned to the data.
- Setups pay only in strong breadth (bursts +0.16R, anticipation +0.18R; bursts −0.09R in weak);
  EPs without a catalyst check lose in every regime.
- Limits: survivorship bias in backfill, small strong-regime sample, no costs, no intraday H/L/volume.

## Working preferences
- Start every answer with a TL;DR, then detail.
- Ship working changes; verify with `--rebuild-only`, the tests, and a headless browser check before pushing.
- Don't run long blocking polling loops.
