"""Long-history price levels (all-time high and major old peaks) for theme stocks.

The Massive free plan only reaches back about two years, so old highs (say a 2021
top) come from Yahoo Finance's free monthly chart data instead. Old peaks never
change, so each ticker is fetched once and cached in data/levels.json; tickers
are refreshed again only after REFRESH_DAYS. Recent highs come from our own
stored bars at build time, so a new high is picked up the same day.

Everything here is best effort: if Yahoo is unreachable the page falls back to
the 52-week high and marks the all-time high as unverified.
"""
import json
import logging
import time
from datetime import date, datetime, timezone

import requests

from . import config

log = logging.getLogger(__name__)
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{t}"
REFRESH_DAYS = 90
MAX_CALLS = 900          # per run; first run covers the whole theme list
PAUSE = 0.6              # seconds between calls
PIVOT = 3                # a peak is a monthly high above the 3 months either side


def _path():
    return config.DATA_DIR / "levels.json"


def load():
    p = _path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def save(levels):
    p = _path()
    p.write_text(json.dumps(levels, separators=(",", ":"), sort_keys=True))


def peaks_from_monthly(rows):
    """rows: list of (YYYY-MM, high) oldest first -> all-time high and pivot peaks."""
    rows = list({d: (d, h) for d, h in rows if h is not None and h > 0}.values())   # one bar per month
    if not rows:
        return None
    ath_d, ath = max(rows, key=lambda r: r[1])
    peaks = []
    for i, (d, h) in enumerate(rows):
        lo, hi = max(0, i - PIVOT), min(len(rows), i + PIVOT + 1)
        if all(h >= rows[k][1] for k in range(lo, hi) if k != i) and i >= 1:
            peaks.append([d, round(h, 2)])
    return {"ath": round(ath, 2), "ath_d": ath_d, "peaks": peaks[-12:], "first": rows[0][0]}


def parse_chart(js):
    res = (js.get("chart") or {}).get("result") or []
    if not res:
        return None
    r = res[0]
    ts = r.get("timestamp") or []
    q = ((r.get("indicators") or {}).get("quote") or [{}])[0]
    highs = q.get("high") or []
    rows = []
    for t, h in zip(ts, highs):
        d = datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m")
        rows.append((d, h))
    return peaks_from_monthly(rows)


def fetch_one(ticker, session):
    r = session.get(URL.format(t=ticker.replace(".", "-")), params={"range": "max", "interval": "1mo"},
                    headers={"User-Agent": "Mozilla/5.0 (breadth-monitor)"}, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code}")
    return parse_chart(r.json())


def refresh(tickers, levels=None, max_calls=MAX_CALLS, session=None):
    """Fetch levels for tickers that are missing or stale. Never raises."""
    levels = load() if levels is None else levels
    session = session or requests.Session()
    today = date.today()
    todo = []
    for t in sorted(set(tickers)):
        rec = levels.get(t)
        if rec is None:
            todo.append(t)
        else:
            try:
                age = (today - date.fromisoformat(rec.get("asof", "2000-01-01"))).days
            except ValueError:
                age = 9999
            if age > REFRESH_DAYS:
                todo.append(t)
    done = fails = 0
    for t in todo[:max_calls]:
        try:
            rec = fetch_one(t, session)
            if rec:
                rec["asof"] = today.isoformat()
                levels[t] = rec
            done += 1
            fails = 0
        except Exception as e:
            fails += 1
            log.warning("levels: %s failed (%s)", t, e)
            if fails >= 15:
                log.warning("levels: source unreachable, stopping for this run")
                break
        time.sleep(PAUSE)
    if done:
        save(levels)
    log.info("levels: %d fetched, %d still to do, %d cached", done, max(0, len(todo) - done), len(levels))
    return levels
