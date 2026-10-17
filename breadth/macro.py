"""Macro drivers strip: the commodities, rates and currencies behind the themes.

Daily closes come from Yahoo Finance's free chart data (futures and indexes),
fetched once per daily run and cached in data/macro.json, so --rebuild-only
works offline. If Yahoo is unreachable a series falls back to its ETF in our
own stored bars (USO for crude, GLD for gold, ...), marked as such on the page.

The 3-2-1 crack spread (refining margin, $/bbl) is derived from gasoline (RB),
heating oil / diesel (HO) and WTI crude (CL): (2*RB*42 + HO*42 - 3*CL) / 3.
"""
import json
import logging
import time
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

from . import config

log = logging.getLogger(__name__)
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{t}"
PAUSE = 0.6
SPARK = 90          # sessions shown in each sparkline
STALE_DAYS = 6      # cached series older than this vs our bars -> use the ETF fallback

# key, Yahoo symbol, label, unit ("$", "pct" = a yield in %, "pts" = index points),
# fallback ETF in our bars, sub-themes it drives (shown under the tile)
SERIES = [
    ("crude", "CL=F", "WTI crude", "$", "USO", ["Shale E&P", "Integrated & Large-cap Oil", "Oil Services & Drillers"]),
    ("brent", "BZ=F", "Brent crude", "$", None, ["Integrated & Large-cap Oil", "Tankers & Shipping"]),
    ("crack", None, "3-2-1 crack", "$", None, ["Refiners"]),
    ("gasoline", "RB=F", "Gasoline", "$", None, ["Refiners"]),
    ("diesel", "HO=F", "Diesel (heating oil)", "$", None, ["Refiners"]),
    ("natgas", "NG=F", "Natural gas", "$", "UNG", ["Natural Gas Producers", "LNG & Midstream"]),
    ("gold", "GC=F", "Gold", "$", "GLD", ["Gold Majors & Royalties", "Gold Mid-tiers"]),
    ("silver", "SI=F", "Silver", "$", "SLV", ["Silver Miners"]),
    ("copper", "HG=F", "Copper", "$", "CPER", ["Copper Miners", "Diversified Miners"]),
    ("tnx", "^TNX", "10-yr yield", "pct", None, ["Homebuilders", "Regional & Community Banks", "Regulated Utilities"]),
    ("dxy", "DX-Y.NYB", "US dollar", "pts", None, []),
    ("vix", "^VIX", "VIX", "pts", None, []),
    ("btc", "BTC-USD", "Bitcoin", "$", "IBIT", ["Bitcoin Miners", "Bitcoin Treasury Companies", "Crypto Exchanges & Brokers"]),
]


def _path():
    return config.DATA_DIR / "macro.json"


def load():
    p = _path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def parse_chart(js):
    """Yahoo chart JSON -> [[YYYY-MM-DD, close], ...] oldest first (exchange-local dates)."""
    res = (js.get("chart") or {}).get("result") or []
    if not res:
        return []
    r = res[0]
    off = int((r.get("meta") or {}).get("gmtoffset") or 0)
    ts = r.get("timestamp") or []
    q = ((r.get("indicators") or {}).get("quote") or [{}])[0]
    out = {}
    for t, c in zip(ts, q.get("close") or []):
        if c is None:
            continue
        d = datetime.fromtimestamp(t + off, timezone.utc).strftime("%Y-%m-%d")
        out[d] = round(float(c), 4)
    return [[d, out[d]] for d in sorted(out)]


def refresh(session=None):
    """Fetch a year of daily closes for every Yahoo series. Never raises."""
    cache = load()
    session = session or requests.Session()
    got = 0
    for key, sym, *_ in SERIES:
        if not sym:
            continue
        try:
            r = session.get(URL.format(t=sym), params={"range": config.MACRO_RANGE, "interval": "1d"},
                            headers={"User-Agent": "Mozilla/5.0 (breadth-monitor)"}, timeout=20)
            if r.status_code != 200:
                raise RuntimeError(r.status_code)
            rows = parse_chart(r.json())
            if rows:
                cache[key] = {"sym": sym, "rows": rows, "asof": date.today().isoformat()}
                got += 1
        except Exception as e:
            log.warning("macro: %s failed (%s)", sym, e)
        time.sleep(PAUSE)
    if got:
        _path().write_text(json.dumps(cache, separators=(",", ":"), sort_keys=True))
    log.info("macro: %d of %d series fetched", got, sum(1 for s in SERIES if s[1]))
    return cache


def _crack(cache):
    try:
        cl = dict(cache["crude"]["rows"]); rb = dict(cache["gasoline"]["rows"]); ho = dict(cache["diesel"]["rows"])
    except (KeyError, TypeError):
        return None
    ds = sorted(set(cl) & set(rb) & set(ho))
    rows = [[d, round((2 * rb[d] * 42 + ho[d] * 42 - 3 * cl[d]) / 3, 2)] for d in ds]
    return {"rows": rows} if rows else None


def _item(key, label, unit, drives, rows, src):
    s = pd.Series([v for _, v in rows], index=[d for d, _ in rows], dtype=float).dropna()
    if len(s) < 2:
        return None
    last = float(s.iloc[-1])

    def chg(n):
        if len(s) <= n:
            return None
        prev = float(s.iloc[-1 - n])
        if unit == "pct":                         # yields: change in percentage points
            return round(last - prev, 3)
        return round(last / prev - 1, 4) if prev else None

    sp = s.iloc[-SPARK:]
    hi, lo = float(s.iloc[-252:].max()), float(s.iloc[-252:].min())
    return {"key": key, "label": label, "unit": unit, "src": src, "date": s.index[-1],
            "last": round(last, 4), "d1": chg(1), "d5": chg(5), "d30": chg(21), "d90": chg(63),
            "pos": round((last - lo) / (hi - lo), 3) if hi > lo else None,      # where it sits in its 1-yr range
            "spark": [round(float(v), 4) for v in sp.values], "drives": drives}


def build(adjusted, cache=None):
    """List of strip tiles for the page."""
    cache = load() if cache is None else dict(cache)
    crack = _crack(cache)
    if crack:
        cache["crack"] = crack
    last_bar = pd.Timestamp(adjusted["date"].max()) if adjusted is not None and len(adjusted) else None
    closes = None
    out = []
    for key, sym, label, unit, etf, drives in SERIES:
        rec = cache.get(key)
        rows = rec.get("rows") if rec else None
        fresh = bool(rows) and (last_bar is None or
                                (last_bar - pd.Timestamp(rows[-1][0])).days <= STALE_DAYS)
        if fresh:
            it = _item(key, label, unit, drives, rows, "futures" if sym and "=F" in sym else "index" if sym else "derived")
        elif etf and adjusted is not None:
            if closes is None:
                etfs = {x[4] for x in SERIES if x[4]}
                sub = adjusted[adjusted["ticker"].isin(etfs)]
                closes = sub.pivot_table(index="date", columns="ticker", values="c")
            if etf not in closes.columns:
                continue
            s = closes[etf].dropna()
            rows = [[d.strftime("%Y-%m-%d"), float(v)] for d, v in s.items()]
            it = _item(key, label, "$", drives, rows, f"ETF {etf}")
        else:
            continue
        if it:
            out.append(it)
    return out


if __name__ == "__main__":      # python -m breadth.macro refresh  (used by .github/workflows/macro.yml)
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    if sys.argv[1:] == ["refresh"]:
        refresh()
