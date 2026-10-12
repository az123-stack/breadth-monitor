"""Intraday tab: what the page needs to read the live Google Sheet during the session.

The live sheet ("Breadth Monitor – Live Prices") has one row per symbol:
  ticker | price | closeyest | open | volume | marketcap | volumeavg | index | symbol
'symbol' is what GOOGLEFINANCE is asked for (usually the ticker; index and crypto
rows use Google's own codes). marketcap and volumeavg are only filled for S&P 500 /
Nasdaq-100 members (index = 1) to keep the sheet light.

data/index_members.csv lists the members and sectors:
  S&P 500  - Wikipedia "List of S&P 500 companies", fetched 2026-10-12
  Nasdaq-100 - the user's index contribution tracker (Wikipedia list, Oct 2026, ICB sectors)
Weights are prior-close market caps from Google (not float-adjusted, like the tracker).
GOOG, FOX and NWS are left out of the weights: Google reports the whole company's
market cap on both share classes.

`python -m breadth.intraday --sheet-rows` prints the sheet's ticker/index/symbol rows.
"""
import argparse
import csv
import json

from . import config, store

# Market pulse rows: key -> (Google symbol, label)
PULSE = {
    "^SPX": ("INDEXSP:.INX", "S&P 500"), "^NDX": ("INDEXNASDAQ:NDX", "Nasdaq-100"),
    "SPY": ("SPY", "SPY"), "QQQ": ("QQQ", "QQQ"), "IWM": ("IWM", "Russell 2000 (IWM)"), "DIA": ("DIA", "Dow (DIA)"),
    "RSP": ("RSP", "S&P equal weight (RSP)"), "QQEW": ("QQEW", "Nasdaq-100 equal weight (QQEW)"),
    "^VIX": ("INDEXCBOE:VIX", "VIX"), "TLT": ("TLT", "20y Treasuries (TLT)"), "UUP": ("UUP", "US dollar (UUP)"),
    "GLD": ("GLD", "Gold (GLD)"), "USO": ("USO", "Oil (USO)"), "^BTC": ("CURRENCY:BTCUSD", "Bitcoin"),
}
SECTOR_ETFS = {"XLK": "Technology", "XLC": "Communication", "XLY": "Consumer Disc.", "XLF": "Financials",
               "XLV": "Health Care", "XLI": "Industrials", "XLE": "Energy", "XLB": "Materials", "XLP": "Staples",
               "XLU": "Utilities", "XLRE": "Real Estate", "SMH": "Semiconductors", "IGV": "Software", "XBI": "Biotech"}
DUP_CLASSES = {"GOOG", "FOX", "NWS"}   # same total market cap as GOOGL / FOXA / NWSA
# Share of a normal day's volume done by minutes since 9:30 (from the user's tracker)
VOLUME_PROFILE = [[0, 0.0], [30, 0.159], [60, 0.257], [90, 0.335], [120, 0.398], [150, 0.455], [180, 0.504],
                  [210, 0.549], [240, 0.596], [270, 0.639], [300, 0.686], [330, 0.734], [360, 0.788], [390, 1.0]]
# Day type thresholds (the tracker's starting guesses)
DAY_TYPE = {"flat": 0.0002, "narrow_top10": 0.75, "narrow_gap": 0.005, "broad_share": 0.7, "broad_top10": 0.6}
SYMBOL_OVERRIDE = {"P": "NYSE:P"}   # Google resolves the bare ticker to an old listing


def load_members():
    p = config.DATA_DIR / "index_members.csv"
    out = {"SPX": [], "NDX": []}
    if not p.exists():
        return out
    with open(p) as f:
        for r in csv.DictReader(f):
            out.setdefault(r["index"], []).append([r["ticker"], r["sector"]])
    return out


def payload():
    m = load_members()
    return {"members": m, "pulse": {k: v[1] for k, v in PULSE.items()}, "sector_etfs": SECTOR_ETFS,
            "dup_classes": sorted(DUP_CLASSES), "volume_profile": VOLUME_PROFILE, "day_type": DAY_TYPE}


def sheet_rows():
    """[ticker, index_flag, google_symbol] for every row the live sheet should carry."""
    m = load_members()
    idx = {t for rows in m.values() for t, _ in rows} - DUP_CLASSES
    tick = set(store.theme_tickers()) | {t for rows in m.values() for t, _ in rows} | set(SECTOR_ETFS)
    rows = []
    for k, (sym, _) in PULSE.items():
        rows.append([k, 0, sym])
        tick.discard(k)
    for t in sorted(tick):
        rows.append([t, 1 if t in idx else 0, SYMBOL_OVERRIDE.get(t, t)])
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet-rows", action="store_true")
    a = ap.parse_args()
    if a.sheet_rows:
        print(json.dumps(sheet_rows()))
