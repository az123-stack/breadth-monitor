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
MACRO_RANGE = "2y"     # Yahoo history for macro series; 2 years matches the stored bars (macro fit layer needs it)

# NYSE full-day closures (session counts on the Decision Cards, entry cutoffs), computed from the exchange's rules
# in breadth/nyse.py, so the list never runs out. One-off closures go in nyse.EXTRA.
from .nyse import holidays as _nyse_holidays  # noqa: E402
MARKET_HOLIDAYS = _nyse_holidays(2024, 2040)

# ---- Washout thrust (connector study, Oct 16 2026; see breadth/washout.py) --
# A breadth thrust that follows a deep washout: SPY at least WASHOUT_PULLBACK below its 60-day high
# within the 15 sessions up to the thrust, and T2108 at or below WASHOUT_T2108 within 10 sessions.
# After those (Apr 2025, Mar 2026) the most market-sensitive leaders ran +26% / +34% in a month;
# after the four shallow thrusts the same list averaged +3.5% (all stocks +2.1%). Only 2 deep events: experimental.
WASHOUT_PULLBACK = 0.08
WASHOUT_T2108 = 25
WASHOUT_WINDOW = 21          # sessions the flag stays on after the thrust (~1 month)
WASHOUT_MIN_RS = 80          # list: RS Rating at least this ...
WASHOUT_TOP = 30             # ... top N by 60-day beta to SPY ...
WASHOUT_MIN_DVOL = 20e6      # ... among stocks >= $5 with 50-day avg $ volume >= this

# Volume tilt (breadth tab; vtilt.py): stocks with 20-day avg dollar volume of at least TILT_MIN_DOLLARS whose
# move was more than TILT_MOVE_SIGMA of their own 20-day volatility count as "movers".
TILT_MIN_DOLLARS = 5_000_000
TILT_MOVE_SIGMA = 0.5
TILT_WINDOW = 25        # sessions after a major thrust that count as "post-thrust" (same as metrics.THRUST_WINDOW)
TILT_HORIZON = 21       # evidence: SPY from the next open to the close this many sessions later
TILT_UNCONFIRM_SHARE = 70   # experimental: thrust "unconfirmed" if a next-1-2-session day has this % of $ volume in falling stocks

# Unproven layers (macro_fit, ...) that Adam has approved to color the Decision Cards after passing their backtest.
# Passing a backtest alone never changes anything; see DECISIONS.md.
APPROVED_LAYERS = ("launch",)   # Oct 25, 2026: Adam approved the Launch list as the source of the headline picks (passed t >= 2, both halves)
