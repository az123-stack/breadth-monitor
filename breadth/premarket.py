"""Pre-market tab: Yahoo pre-market quotes for every symbol in the live sheet, written to docs/premarket.json.

Google's GOOGLEFINANCE doesn't update before the open, so the Pre-market tab reads this file instead. The
`premarket.yml` workflow runs `python -m breadth.premarket` every 10 minutes from ~6 AM ET until 9:31 and commits
the file; the page fetches it from GitHub Pages.

Yahoo (free, no key): batched `v7/finance/spark` (20 symbols a call, intraday 5-minute bars incl. pre-market),
falling back to one `v8/finance/chart` call per symbol if spark refuses. For each symbol we keep the latest
pre-market price, the previous regular close, pre-market volume (sum of today's pre-market bars) and the time of the
last pre-market trade.

docs/premarket.json:
  {"asof": "2026-10-14T08:10", "date": "2026-10-14", "method": "spark", "n": 2950, "errors": 0,
   "rows": {"NVDA": [pre_price, prev_close, pre_volume, "08:09"], ...},
   "futures": {"ES=F": [price, prev_close, null, "08:09"], ...}}
"""
import argparse
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from . import config

log = logging.getLogger("breadth.premarket")
ET = ZoneInfo("America/New_York")
OUT = config.ROOT / "docs" / "premarket.json"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
SPARK = "https://query1.finance.yahoo.com/v7/finance/spark"
CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{s}"

# Futures and macro that trade overnight: key -> (Yahoo symbol, label)
FUTURES = {
    "ES=F": "S&P 500 futures", "NQ=F": "Nasdaq-100 futures", "RTY=F": "Russell 2000 futures", "YM=F": "Dow futures",
    "CL=F": "Crude oil", "NG=F": "Natural gas", "GC=F": "Gold", "SI=F": "Silver", "HG=F": "Copper",
    "ZN=F": "10y Treasury note", "^TNX": "10y yield", "DX-Y.NYB": "US dollar index", "BTC-USD": "Bitcoin", "ETH-USD": "Ether",
}
# Our sheet keys that Yahoo spells differently
YAHOO_SYMBOL = {"^SPX": "^GSPC", "^NDX": "^NDX", "^VIX": "^VIX", "^BTC": "BTC-USD"}


def yahoo_symbol(t):
    return YAHOO_SYMBOL.get(t, t.replace(".", "-"))


def tickers():
    """Every row of the live sheet (pulse symbols, sector ETFs, theme stocks, S&P 500, Nasdaq-100, Russell 2000)."""
    import csv
    p = config.DATA_DIR / "live_sheet.csv"
    with open(p) as f:
        return [r[0] for r in csv.reader(f) if r and r[0] and not r[0].startswith("_")]


def parse(res, today):
    """One chart result -> [pre_price, prev_close, pre_volume, "HH:MM"] for today's pre-market, or None."""
    meta = res.get("meta") or {}
    ts = res.get("timestamp") or []
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    closes, vols = q.get("close") or [], q.get("volume") or []
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    reg = ((meta.get("currentTradingPeriod") or {}).get("regular") or {}).get("start")
    last_p = last_t = None
    vol = 0
    for i, t in enumerate(ts):
        d = datetime.fromtimestamp(t, ET)
        if d.date().isoformat() != today or (reg and t >= reg):
            continue
        c = closes[i] if i < len(closes) else None
        if c is not None:
            last_p, last_t = c, d.strftime("%H:%M")
        v = vols[i] if i < len(vols) else None
        if v:
            vol += v
    if last_p is None:   # no pre-market trade yet today (futures/crypto: take the latest price)
        last_p = meta.get("regularMarketPrice")
        rt = meta.get("regularMarketTime")
        last_t = datetime.fromtimestamp(rt, ET).strftime("%H:%M") if rt else None
        if last_p is None or not rt or datetime.fromtimestamp(rt, ET).date().isoformat() != today:
            return [None, round(prev, 4) if prev else None, 0, None]
    return [round(last_p, 4), round(prev, 4) if prev else None, int(vol), last_t]


def fetch_spark(session, syms, today):
    out = {}
    for i in range(0, len(syms), 20):
        chunk = syms[i:i + 20]
        r = session.get(SPARK, params={"symbols": ",".join(chunk), "range": "1d", "interval": "5m", "includePrePost": "true"},
                        headers=UA, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"spark HTTP {r.status_code}: {r.text[:120]}")
        for item in (r.json().get("spark") or {}).get("result") or []:
            resp = (item.get("response") or [None])[0]
            if resp:
                out[item["symbol"]] = parse(resp, today)
        time.sleep(0.3)
    return out


def fetch_chart(session, syms, today, workers=6):
    errors = []

    def one(s):
        for attempt in range(3):
            try:
                r = session.get(CHART.format(s=s), params={"range": "1d", "interval": "5m", "includePrePost": "true"},
                                headers=UA, timeout=20)
                if r.status_code == 429:
                    time.sleep(5 * (attempt + 1)); continue
                if r.status_code != 200:
                    return s, None
                res = ((r.json().get("chart") or {}).get("result") or [None])[0]
                return s, parse(res, today) if res else None
            except Exception as e:  # network hiccup
                errors.append(str(e)[:80]); time.sleep(2)
        return s, None

    with ThreadPoolExecutor(workers) as ex:
        return {s: v for s, v in ex.map(one, syms) if v}


def run():
    now = datetime.now(ET)
    today = now.date().isoformat()
    keys = tickers()
    ysym = {t: yahoo_symbol(t) for t in keys}
    syms = sorted(set(ysym.values()) | set(FUTURES))
    session = requests.Session()
    method, err = "spark", None
    try:
        got = fetch_spark(session, syms, today)
        if len(got) < len(syms) * 0.5:
            raise RuntimeError(f"spark returned only {len(got)} of {len(syms)}")
    except Exception as e:
        err = str(e)[:200]
        log.warning("spark failed (%s); falling back to one chart call per symbol", err)
        method, got = "chart", fetch_chart(session, syms, today)
    rows = {t: got[y] for t, y in ysym.items() if got.get(y) and got[y][0] is not None}
    fut = {k: got[k] for k in FUTURES if got.get(k) and got[k][0] is not None}
    out = {"asof": now.strftime("%Y-%m-%dT%H:%M"), "date": today, "method": method, "spark_error": err,
           "n": len(rows), "asked": len(keys), "rows": rows, "futures": fut, "futures_labels": FUTURES}
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    log.info("pre-market: %d of %d symbols priced via %s, %d futures", len(rows), len(keys), method, len(fut))
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    argparse.ArgumentParser().parse_args()
    run()
