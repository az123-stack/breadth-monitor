"""Thin client for the Massive (formerly Polygon.io) REST API.

Only three endpoints are used, all available on the free Basic plan:
  - grouped daily bars: every US stock's bar for one date in a single call
  - reference tickers:  the common-stock universe (excludes ETFs, warrants...)
  - splits:             to keep stored history split-adjusted
"""
import logging
import time

import requests

from . import config

log = logging.getLogger(__name__)


class MassiveError(RuntimeError):
    pass


class MassiveClient:
    def __init__(self, api_key=None, base=None, min_interval=None, session=None):
        self.api_key = api_key or config.API_KEY
        if not self.api_key:
            raise MassiveError(
                "MASSIVE_API_KEY is not set. Add it as a repository secret "
                "(Settings -> Secrets and variables -> Actions)."
            )
        self.base = (base or config.API_BASE).rstrip("/")
        self.min_interval = config.MIN_CALL_INTERVAL if min_interval is None else min_interval
        self.session = session or requests.Session()
        self._last_call = 0.0

    # -- low level -----------------------------------------------------------
    def _get(self, url, params=None, retries=4):
        params = dict(params or {})
        params["apiKey"] = self.api_key
        for attempt in range(retries + 1):
            wait = self.min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
            try:
                r = self.session.get(url, params=params, timeout=60)
            except requests.RequestException as e:
                if attempt == retries:
                    raise MassiveError(f"network error: {e}") from e
                time.sleep(10 * (attempt + 1))
                continue
            if r.status_code == 429:          # rate limited: back off a full minute
                log.warning("rate limited, sleeping 60s")
                time.sleep(60)
                continue
            if r.status_code >= 500 and attempt < retries:
                time.sleep(10 * (attempt + 1))
                continue
            if r.status_code in (401, 403):
                raise MassiveError(f"{r.status_code} from {url.split('?')[0]}: {r.text[:200]}")
            r.raise_for_status()
            return r.json()
        raise MassiveError(f"giving up on {url}")

    def _paged(self, path, params):
        data = self._get(self.base + path, params)
        yield from data.get("results") or []
        nxt = data.get("next_url")
        while nxt:
            data = self._get(nxt)  # next_url already carries the query, we add apiKey
            yield from data.get("results") or []
            nxt = data.get("next_url")

    # -- endpoints -----------------------------------------------------------
    def grouped_daily(self, day):
        """All US stock bars for `day` (a date). Unadjusted; we adjust ourselves.

        Returns a list of dicts with keys ticker,o,h,l,c,v. Empty list on
        weekends/holidays or if the day isn't published yet.
        """
        path = f"/v2/aggs/grouped/locale/us/market/stocks/{day.isoformat()}"
        data = self._get(self.base + path, {"adjusted": "false", "include_otc": "false"})
        out = []
        for r in data.get("results") or []:
            if r.get("c") is None or r.get("v") is None:
                continue
            out.append({"ticker": r["T"], "o": r.get("o"), "h": r.get("h"),
                        "l": r.get("l"), "c": r["c"], "v": r["v"]})
        return out

    def daily_bars(self, ticker, start, end):
        """Unadjusted daily bars for one ticker between two dates (inclusive)."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")
        path = f"/v2/aggs/ticker/{ticker}/range/1/day/{start.isoformat()}/{end.isoformat()}"
        data = self._get(self.base + path, {"adjusted": "false", "sort": "asc", "limit": 50000})
        out = []
        for r in data.get("results") or []:
            if r.get("c") is None:
                continue
            d = datetime.fromtimestamp(r["t"] / 1000, et).date()
            out.append({"date": d, "ticker": ticker, "o": r.get("o"), "h": r.get("h"),
                        "l": r.get("l"), "c": r["c"], "v": r.get("v") or 0})
        return out

    def common_stocks(self):
        """Active common stocks on US exchanges (type CS)."""
        rows = self._paged("/v3/reference/tickers",
                           {"market": "stocks", "type": "CS", "active": "true", "limit": 1000})
        return [{"ticker": r["ticker"], "name": r.get("name", ""),
                 "exchange": r.get("primary_exchange", "")} for r in rows]

    def tickers_of_type(self, kind):
        """Active tickers of one reference type (e.g. ETF, ADRC) with names."""
        rows = self._paged("/v3/reference/tickers",
                           {"market": "stocks", "type": kind, "active": "true", "limit": 1000})
        return [{"ticker": r["ticker"], "name": r.get("name", ""), "type": kind} for r in rows]

    def splits_since(self, start):
        """Splits with execution_date >= start."""
        rows = self._paged("/v3/reference/splits",
                           {"execution_date.gte": start.isoformat(), "limit": 1000})
        return [{"ticker": r["ticker"], "execution_date": r["execution_date"],
                 "split_from": float(r["split_from"]), "split_to": float(r["split_to"])}
                for r in rows if r.get("split_from") and r.get("split_to")]
