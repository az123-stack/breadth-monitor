"""Russell 2000 members and weights, from iShares' published IWM holdings file.

Fetched in the daily run (free, one request) and cached in data/russell2000.csv:
  ticker,weight,sector,exchange,asof
weight = IWM's weight in % (float-adjusted index weights, as of the holdings date).
The Intraday tab uses it for "Who's moving the index" -> Russell 2000 (IWM).
If the fetch fails, the cached file is kept.
"""
import csv
import io
import logging
import re

import requests

from . import config

log = logging.getLogger(__name__)

URL = ("https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/1467271812596.ajax"
       "?fileType=csv&fileName=IWM_holdings&dataType=fund")
# iShares exchange name -> Google Finance prefix (bare tickers can resolve to the wrong listing)
EXCHANGE = {"nasdaq": "NASDAQ", "new york stock exchange inc.": "NYSE", "nyse arca": "NYSEARCA",
            "nyse mkt llc": "NYSEAMERICAN", "cboe bzx formerly known as bats": "BATS"}


def path():
    return config.DATA_DIR / "russell2000.csv"


def parse(text):
    """Holdings CSV -> (rows, asof). Keeps equity rows with a positive weight."""
    text = text.lstrip("﻿")
    lines = text.splitlines()
    asof = None
    for ln in lines[:12]:
        m = re.search(r"as of,\"?([A-Za-z]{3} \d{1,2}, \d{4})", ln)
        if m:
            asof = m.group(1)
    start = next((i for i, ln in enumerate(lines) if ln.startswith("Ticker,")), None)
    if start is None:
        raise ValueError("no holdings header")
    out = []
    for r in csv.DictReader(io.StringIO("\n".join(lines[start:]))):
        t = (r.get("Ticker") or "").strip().upper()
        if not t or t == "-" or (r.get("Asset Class") or "").strip() != "Equity":
            continue
        try:
            w = float((r.get("Weight (%)") or "").replace(",", ""))
        except ValueError:
            continue
        if w <= 0:
            continue
        out.append({"ticker": t.replace(" ", "."), "weight": w, "sector": (r.get("Sector") or "Other").strip(),
                    "exchange": EXCHANGE.get((r.get("Exchange") or "").strip().lower(), "")})
    return out, asof


def refresh(session=None):
    s = session or requests
    r = s.get(URL, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                          "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}, timeout=30)
    r.raise_for_status()
    rows, asof = parse(r.text)
    if len(rows) < 1000:      # a partial / error page: keep the cached file
        raise ValueError(f"only {len(rows)} holdings parsed")
    with open(path(), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "weight", "sector", "exchange", "asof"])
        for x in rows:
            w.writerow([x["ticker"], x["weight"], x["sector"], x["exchange"], asof or ""])
    log.info("Russell 2000: %d holdings (as of %s)", len(rows), asof)
    return len(rows)


def load():
    """[{ticker, weight, sector, exchange}], asof — empty if never fetched."""
    if not path().exists():
        return [], None
    with open(path()) as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["weight"] = float(r["weight"])
    return rows, (rows[0].get("asof") or None) if rows else None
