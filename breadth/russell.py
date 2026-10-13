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


UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}
PRODUCT = "https://www.ishares.com/us/products/239710/ishares-russell-2000-etf"
JSON_URL = PRODUCT + "/1467271812596.ajax?tab=all&fileType=json"
SSGA_URL = ("https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/"
            "holdings-daily-us-en-twok.xlsx")   # SPDR Russell 2000 (TWOK): same index, fallback


def _num(v):
    if isinstance(v, dict):
        v = v.get("raw", v.get("display"))
    try:
        return float(str(v).replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return None


def parse_json(text):
    """iShares holdings JSON {"aaData": [[ticker, name, sector, asset class, mkt value, weight, ...], ...]}."""
    import json
    data = json.loads(text.lstrip("\ufeff"))
    out = []
    for row in data.get("aaData", []):
        if len(row) < 6 or str(row[3]).strip() != "Equity":
            continue
        t, w = str(row[0]).strip().upper(), _num(row[5])
        if not t or t == "-" or not w or w <= 0:
            continue
        exch = next((EXCHANGE[str(x).strip().lower()] for x in row if isinstance(x, str) and str(x).strip().lower() in EXCHANGE), "")
        out.append({"ticker": t.replace(" ", "."), "weight": w, "sector": str(row[2]).strip() or "Other", "exchange": exch})
    return out, None


def parse_ssga(content):
    """SSGA daily holdings xlsx: header row Name | Ticker | Identifier | SEDOL | Weight | Sector | ..."""
    import pandas as pd
    raw = pd.read_excel(io.BytesIO(content), header=None)
    hdr = next(i for i in range(min(len(raw), 15)) if "Ticker" in [str(x).strip() for x in raw.iloc[i]])
    df = raw.iloc[hdr + 1:].copy()
    df.columns = [str(x).strip() for x in raw.iloc[hdr]]
    asof = None
    for i in range(hdr):
        m = re.search(r"(\d{1,2}-[A-Za-z]{3}-\d{4})", " ".join(str(x) for x in raw.iloc[i]))
        if m:
            asof = m.group(1)
    out = []
    for _, r in df.iterrows():
        t, w = str(r.get("Ticker") or "").strip().upper(), _num(r.get("Weight"))
        if not t or t in ("-", "NAN", "CASH_USD") or not w or w <= 0:
            continue
        out.append({"ticker": t.replace(" ", "."), "weight": w, "sector": str(r.get("Sector") or "Other").strip(), "exchange": ""})
    return out, asof


def refresh(session=None):
    """Tries iShares CSV (with the product page's cookies), iShares JSON, then SSGA's TWOK file."""
    s = session or requests.Session()
    tries = []
    rows, asof = [], None
    try:
        s.get(PRODUCT, headers=UA, timeout=30)          # sets the site's cookies
    except Exception as e:
        tries.append({"src": "product page", "error": str(e)[:200]})
    for name, url, how in [("ishares csv", URL, "csv"), ("ishares json", JSON_URL, "json"), ("ssga twok", SSGA_URL, "xlsx")]:
        t, r = {"src": name}, None
        try:
            r = s.get(url, headers={**UA, "Referer": PRODUCT}, timeout=60)
            t = {"src": name, "http": r.status_code, "type": r.headers.get("content-type"), "bytes": len(r.content)}
            r.raise_for_status()
            rows, asof = parse(r.text) if how == "csv" else parse_json(r.text) if how == "json" else parse_ssga(r.content)
            t["rows"] = len(rows)
            tries.append(t)
            if len(rows) >= 1000:
                break
        except Exception as e:
            t["error"] = str(e)[:200]
            if r is not None and "xlsx" not in name:
                t["head"] = r.text[:160]
            tries.append(t)
            rows = []
    _status({"ok": len(rows) >= 1000, "rows": len(rows), "asof": asof, "tries": tries})
    if len(rows) < 1000:      # nothing usable: keep the cached file
        raise ValueError(f"Russell 2000 holdings unavailable: {tries}")
    with open(path(), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "weight", "sector", "exchange", "asof"])
        for x in rows:
            w.writerow([x["ticker"], x["weight"], x["sector"], x["exchange"], asof or ""])
    log.info("Russell 2000: %d holdings (as of %s)", len(rows), asof)
    return len(rows)


def _status(d):
    """Last fetch result (data/russell_status.json), so a failure can be read from the repo."""
    import json
    from datetime import datetime, timezone
    with open(config.DATA_DIR / "russell_status.json", "w") as f:
        json.dump({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **d}, f, indent=1)


def load():
    """[{ticker, weight, sector, exchange}], asof — empty if never fetched."""
    if not path().exists():
        return [], None
    with open(path()) as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["weight"] = float(r["weight"])
    return rows, (rows[0].get("asof") or None) if rows else None
