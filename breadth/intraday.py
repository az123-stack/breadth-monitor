"""Intraday tab: what the page needs to read the live Google Sheet during the session.

The live sheet ("Breadth Monitor – Live Prices") has one row per symbol:
  ticker | index | symbol | price | closeyest | open | volume | marketcap | volumeavg
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
Each build writes them to data/live_sheet.csv; the sheet's A4 cell is
=IMPORTDATA("<raw GitHub URL of data/live_sheet.csv>"), so it follows theme changes on its own.
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


def russell_members():
    """Russell 2000 rows [ticker, sector] + weights {ticker: %} from the cached IWM holdings."""
    from . import russell
    rows, asof = russell.load()
    return rows, asof


def payload():
    m = load_members()
    r2k, asof = russell_members()
    if r2k:
        m["R2K"] = [[r["ticker"], r["sector"]] for r in r2k]
    return {"members": m, "r2k_weights": {r["ticker"]: r["weight"] for r in r2k}, "r2k_asof": asof, "pulse": {k: v[1] for k, v in PULSE.items()}, "sector_etfs": SECTOR_ETFS,
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
    # Russell 2000 members not already listed: flag 2 = price, prior close and volume only (keeps the sheet light)
    have = {r[0] for r in rows}
    r2k, _ = russell_members()
    for r in sorted(r2k, key=lambda x: x["ticker"]):
        t = r["ticker"]
        if t in have:
            continue
        have.add(t)
        rows.append([t, 2, SYMBOL_OVERRIDE.get(t, f'{r["exchange"]}:{t}' if r["exchange"] else t)])
    return rows


def write_sheet_csv():
    with open(config.DATA_DIR / "live_sheet.csv", "w", newline="") as f:
        csv.writer(f).writerows(sheet_rows())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet-rows", action="store_true")
    a = ap.parse_args()
    if a.sheet_rows:
        print(json.dumps(sheet_rows()))


# ---------------------------------------------------------------------------
# Thrust watch: gauge a breadth thrust live, on the stocks the Google Sheet prices
# ---------------------------------------------------------------------------
THRUST_K = 2.5      # live up-4% count >= 2.5x its own 40-day average  -> "thrust pace"
CLOSE_K = 2.0       # >= 2.0x -> "getting close"


def thrust_watch(adjusted, history, universe):
    """Calibrates the live list (theme stocks + S&P 500 + Nasdaq-100 that are US common stocks) against the
    official whole-market 4% count. Price-only rule (close >= $3, up 4%+), since full-day volume isn't known
    until the close. Returns thresholds for today, the calibration record and the setup condition."""
    import numpy as np
    import pandas as pd
    from . import config as C, store
    m = load_members()
    live = sorted((set(store.theme_tickers()) | {t for rows in m.values() for t, _ in rows}) & set(universe))
    sub = adjusted[adjusted["ticker"].isin(live)]
    c = sub.pivot_table(index="date", columns="ticker", values="c").sort_index()
    chg = c / c.shift(1) - 1
    lup = ((chg >= 0.04) & (c >= 3)).sum(axis=1)
    ldn = ((chg <= -0.04) & (c >= 3)).sum(axis=1)
    h = history[history["complete"]] if "complete" in history.columns else history
    df = pd.DataFrame({"lup": lup, "ldn": ldn}).join(h[["up4", "up4_avg40", "t2108", "ratio10"]], how="inner")
    df["lavg"] = df["lup"].rolling(40).mean().shift(1)
    df["avg_prev"] = df["up4_avg40"].shift(1)
    cal = df.dropna()
    official = cal["up4"] >= C.EVENT_THRUST_MULT * cal["avg_prev"]
    flag = cal["lup"] >= THRUST_K * cal["lavg"]
    near = cal["lup"] >= CLOSE_K * cal["lavg"]
    scale = float((cal["up4"] / cal["lup"].replace(0, np.nan)).median()) if len(cal) else None
    lavg_now = float(df["lup"].iloc[-40:].mean())
    last = h.iloc[-1]
    t_min = float(h["t2108"].iloc[-10:].min())
    r_min = float(h["ratio10"].iloc[-10:].min())
    net = None
    if "nh10" in h.columns and pd.notna(last.get("nh10")) and pd.notna(last.get("nl10")):
        net = round(float(last["nh10"] - last["nl10"]), 1)
    past = [{"date": d.strftime("%Y-%m-%d"), "live": int(cal.at[d, "lup"]), "x": round(float(cal.at[d, "lup"] / cal.at[d, "lavg"]), 2),
             "official": int(cal.at[d, "up4"]), "caught": bool(flag[d])} for d in cal.index[official]][-10:]
    return {"tickers": live, "n": len(live), "avg40": round(lavg_now, 1),
            "pace": int(np.ceil(THRUST_K * lavg_now)), "close": int(np.ceil(CLOSE_K * lavg_now)), "k": THRUST_K, "k_close": CLOSE_K,
            "official_need": int(np.ceil(C.EVENT_THRUST_MULT * float(last["up4_avg40"]))), "scale": round(scale, 2) if scale else None,
            "corr": round(float(cal["up4"].corr(cal["lup"])), 3) if len(cal) > 10 else None,
            "caught": int((flag & official).sum()), "official_days": int(official.sum()),
            "near_caught": int((near & official).sum()), "false_alarms": int((flag & ~official).sum()),
            "setup": {"met": bool(t_min <= C.THRUST_LOW_T2108 or r_min <= C.THRUST_LOW_RATIO), "t2108_min": round(t_min, 1),
                      "ratio10_min": round(r_min, 2), "t_level": C.THRUST_LOW_T2108, "r_level": C.THRUST_LOW_RATIO},
            "net": net, "last": {"date": df.index[-1].strftime("%Y-%m-%d"), "live": int(df["lup"].iloc[-1]),
                                  "official": int(last["up4"])}, "past": past,
            "from": cal.index[0].strftime("%Y-%m-%d") if len(cal) else None}
