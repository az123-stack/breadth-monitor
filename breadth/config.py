"""All tunable settings in one place.

Thresholds marked "starter" are reasonable defaults, not Stockbee's published
numbers. Calibrate them against your own history once you have a few months
of data (the dashboard shows percentiles to help with that).
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"

BARS_DIR = DATA_DIR / "bars"                 # one raw parquet file per trading day (rolling window)
BREADTH_FILE = DATA_DIR / "breadth.csv"      # full breadth history, one row per day
UNIVERSE_FILE = DATA_DIR / "universe.csv"    # common-stock ticker list
SPLITS_FILE = DATA_DIR / "splits.csv"        # split history used to adjust stored raw bars
REF_NAMES_FILE = DATA_DIR / "ref_names.csv"  # names/types for ETFs and ADRs
SUBTHEMES_FILE = DATA_DIR / "subthemes.csv"  # one peer-group sub-theme per stock
THEMES_FILE = DATA_DIR / "themes.csv"        # your theme lists (edit freely)
STATE_FILE = DATA_DIR / "state.json"         # bookkeeping (split checks, universe refresh)

# ---- Massive (formerly Polygon.io) API -------------------------------------
API_BASE = os.environ.get("MASSIVE_API_BASE", "https://api.massive.com")
API_KEY = os.environ.get("MASSIVE_API_KEY", "")
# Free Basic plan allows 5 calls/minute -> one call every 12.5s is safe.
# Set MASSIVE_MIN_INTERVAL=0 if you upgrade to a paid plan.
MIN_CALL_INTERVAL = float(os.environ.get("MASSIVE_MIN_INTERVAL", "12.5"))
UNIVERSE_REFRESH_DAYS = 7

BENCHMARK = "SPY"
# Published Google Sheet (CSV) with GOOGLEFINANCE prices for the live layer.
LIVE_CSV_URL = os.environ.get("LIVE_CSV_URL", "https://docs.google.com/spreadsheets/d/e/2PACX-1vTtdx4lANR9e4jocUDpnxs36dGZCVpxMC7NA9rU53hXunXlzPZ4j2sHmKWKGvXjaR2dqbtgoZCJVxpn/pub?output=csv")
REPO_URL = os.environ.get("REPO_URL", "https://github.com/az123-stack/breadth-monitor")
EXTRA_RETRY_DAYS = 7          # retry tickers that returned no data after this many days

# ---- Storage ---------------------------------------------------------------
# Longest lookback is 65 trading days (quarter); keep extra so recent history
# can be recomputed after split adjustments.
KEEP_TRADING_DAYS = 500    # ~2 years (the free plan reaches back ~2 years): 1-year highs, 200-day SMAs and a longer backtest

# ---- Universe filters ------------------------------------------------------
MIN_PRICE = 3.0              # close must be at least this
MIN_VOLUME = 100_000         # for 4% breakout/breakdown days
MIN_AVG_VOLUME = 100_000     # 20-day avg volume, for T2108 and 25%/quarter etc.
MEGA_CAP = 200e9             # Leaders "Mega caps" view: Google market cap from data/close_snapshot.csv

# ---- Metric definitions ----------------------------------------------------
PCT_MOVE = 0.04              # 4% breakout / breakdown
QUARTER_DAYS, QUARTER_PCT = 65, 0.25
MONTH_DAYS, MONTH_PCT, MONTH_BIG_PCT = 20, 0.25, 0.50
D34_DAYS, D34_PCT = 34, 0.13
MA_DAYS = 40                 # T2108 = % above 40-day MA
AVG_WINDOW = 40              # 40-day average of 4% breakouts

# ---- Regime rules (starter thresholds) ------------------------------------
T2108_OVERSOLD = 20
T2108_OVERBOUGHT = 80
STRONG_RATIO = 1.5           # 5- and 10-day ratios both above this = strong
THRUST_MULT = 2.0            # 4% up count >= 2x its 40-day average ...
THRUST_PCTILE = 0.90         # ... and in the top 10% of your history
EXTREME_LOW_PCTILE = 0.10    # 10-day ratio in bottom 10% = washed out
EXTREME_HIGH_PCTILE = 0.95   # 5-day ratio in top 5% = overextended
MIN_HISTORY_FOR_PCTILES = 60 # until then, percentile rules are skipped

# ---- Chart annotations (signal markers) ------------------------------------
EVENT_THRUST_MULT = 2.5      # up-4% count vs prior 40-day avg for a marked thrust
THRUST_LOW_T2108 = 30        # ...and within 10 days of T2108 at or below this
THRUST_LOW_RATIO = 0.8       # ...or of a 10-day ratio at or below this
T2108_EXTENDED = 75          # T2108 crossing above this is marked "Extended"

DASHBOARD_DAYS = 760         # max days on the charts (~3 years); they scroll

# Long-history levels (old highs) for Trade Setups, from Yahoo monthly data; tests switch this off.
LEVELS_ENABLED = True
