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
   "rows": {"NVDA": [pre_price, prev_close, pre_volume, "08:09", active_bars], ...},
Yahoo reports 0 volume for pre-market bars (checked Oct 14, 2026), so activity = number of 5-minute pre-market bars
with a trade ("active_bars") plus the last trade time.
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
UA = {"User-Agent": "Mozilla/5.0 (breadth-monitor)"}   # same as macro.py; Yahoo 429s browser-looking UAs without cookies
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
    # Before the open Yahoo's chartPreviousClose is the close TWO sessions back (checked Oct 14, 2026: MU 989.04 =
    # Oct 12 close, not Oct 13's 953.19). The last regular close is regularMarketPrice while regularMarketTime is
    # before today's regular start. Futures/crypto trade now, so their regularMarketTime is today: keep chartPreviousClose.
    rmp, rmt = meta.get("regularMarketPrice"), meta.get("regularMarketTime")
    if rmp and rmt and reg and rmt < reg and datetime.fromtimestamp(rmt, ET).date().isoformat() < today:
        prev = rmp
    last_p = last_t = None
    vol = bars = 0
    for i, t in enumerate(ts):
        d = datetime.fromtimestamp(t, ET)
        if d.date().isoformat() != today or (reg and t >= reg):
            continue
        c = closes[i] if i < len(closes) else None
        if c is not None:
            last_p, last_t = c, d.strftime("%H:%M")
            bars += 1
        v = vols[i] if i < len(vols) else None
        if v:
            vol += v
    if last_p is None:   # no pre-market trade yet today (futures/crypto: take the latest price)
        last_p = meta.get("regularMarketPrice")
        rt = meta.get("regularMarketTime")
        last_t = datetime.fromtimestamp(rt, ET).strftime("%H:%M") if rt else None
        if last_p is None or not rt or datetime.fromtimestamp(rt, ET).date().isoformat() != today:
            return [None, round(prev, 4) if prev else None, 0, None, 0]
    return [round(last_p, 4), round(prev, 4) if prev else None, int(vol), last_t, bars]


BUDGET_S = 240        # stop fetching after 4 minutes and write what we have (the loop runs every 10 min)


def fetch_spark(session, syms, today, deadline, diag):
    out = {}
    for i in range(0, len(syms), 20):
        if time.monotonic() > deadline:
            diag["spark_timeout"] = True
            break
        chunk = syms[i:i + 20]
        try:
            r = session.get(SPARK, params={"symbols": ",".join(chunk), "range": "1d", "interval": "5m", "includePrePost": "true"},
                            headers=UA, timeout=15)
        except requests.RequestException as e:
            diag.setdefault("spark_net", 0); diag["spark_net"] += 1
            continue
        diag.setdefault("spark_status", {}); diag["spark_status"][str(r.status_code)] = diag["spark_status"].get(str(r.status_code), 0) + 1
        if r.status_code != 200:
            if i == 0:   # refused on the first call: don't keep hammering
                raise RuntimeError(f"spark HTTP {r.status_code}: {r.text[:120]}")
            time.sleep(2)
            continue
        for item in (r.json().get("spark") or {}).get("result") or []:
            resp = (item.get("response") or [None])[0]
            if resp:
                out[item["symbol"]] = parse(resp, today)
        time.sleep(0.2)
    return out


def fetch_chart(session, syms, today, deadline, diag, workers=4):
    def one(s):
        if time.monotonic() > deadline:
            return s, None
        try:
            r = session.get(CHART.format(s=s), params={"range": "1d", "interval": "5m", "includePrePost": "true"},
                            headers=UA, timeout=10)
        except requests.RequestException:
            return s, None
        k = str(r.status_code)
        diag.setdefault("chart_status", {}); diag["chart_status"][k] = diag["chart_status"].get(k, 0) + 1
        if r.status_code != 200:
            if r.status_code == 429:
                time.sleep(2)
            return s, None
        res = ((r.json().get("chart") or {}).get("result") or [None])[0]
        return s, parse(res, today) if res else None

    with ThreadPoolExecutor(workers) as ex:
        return {s: v for s, v in ex.map(one, syms) if v}


def priority(keys):
    """Futures, pulse symbols, sector ETFs, theme stocks and S&P 500 / Nasdaq-100 first; Russell 2000-only names last."""
    import csv
    idx = {}
    with open(config.DATA_DIR / "live_sheet.csv") as f:
        for r in csv.reader(f):
            if r and len(r) > 1:
                idx[r[0]] = r[1]
    return sorted(keys, key=lambda t: 1 if idx.get(t) == "2" else 0)


def run():
    t0 = time.monotonic()
    now = datetime.now(ET)
    today = now.date().isoformat()
    keys = priority(tickers())
    ysym = {t: yahoo_symbol(t) for t in keys}
    syms = list(FUTURES) + [s for s in dict.fromkeys(ysym.values()) if s not in FUTURES]
    session = requests.Session()
    diag, method, err = {}, "spark", None
    deadline = t0 + BUDGET_S
    try:
        got = fetch_spark(session, syms, today, deadline, diag)
        if len(got) < 50:
            raise RuntimeError(f"spark returned only {len(got)} of {len(syms)}")
    except Exception as e:
        err = str(e)[:200]
        log.warning("spark failed (%s); falling back to one chart call per symbol", err)
        method, got = "chart", fetch_chart(session, syms, today, deadline, diag)
    rows = {t: got[y] for t, y in ysym.items() if got.get(y) and got[y][0] is not None}
    fut = {k: got[k] for k in FUTURES if got.get(k) and got[k][0] is not None}
    out = {"asof": now.strftime("%Y-%m-%dT%H:%M"), "date": today, "method": method, "spark_error": err,
           "n": len(rows), "asked": len(keys), "secs": round(time.monotonic() - t0), "diag": diag,
           "rows": rows, "futures": fut, "futures_labels": FUTURES}
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    log.info("pre-market: %d of %d symbols priced via %s, %d futures, %ds %s", len(rows), len(keys), method, len(fut), out["secs"], diag)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    argparse.ArgumentParser().parse_args()
    run()
