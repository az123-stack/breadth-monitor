"""Record volume: stocks that traded their highest volume on record in the last 5 sessions.

"Record" is first checked against our own stored history (about 2 years, split-adjusted volume,
at least 250 sessions of history so new listings don't flood the list). The daily run then asks
Yahoo Finance for each candidate's full daily history (cached in data/hve_ever.json as the biggest
volume day per month) to tell a true highest-volume-EVER day from a 2-year record.

Evidence (recomputed every build; records need 250 sessions of history, so the test covers about the
last 12 months): an UP day on record volume has been followed by underperformance, not follow-through:
about -4% to -5% vs SPY over 10 sessions, ~37-40% winners; worse for RS 85+ leaders, and it held after
removing index-rebalance / expiry days (more than 25 records on one day, flagged on the page).
So the list is shown as a climax / exhaustion warning, with its evidence, not as a buy setup.
"""
import json
import logging
import time
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import requests

from . import config

log = logging.getLogger(__name__)
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{t}"
LOOKBACK = 5          # sessions shown
MIN_HIST = 250        # sessions of history needed before a day can count as a record
MIN_PRICE = 5.0
MIN_DOLLARS = 20e6
MASS_DAY = 25         # more records than this on one day = index rebalance / expiry, flagged
HOLD = 10
REFRESH_DAYS = 30
PAUSE = 0.6


def _path():
    return config.DATA_DIR / "hve_ever.json"


def load():
    p = _path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def record_mask(c, v):
    """Day's volume above every earlier day's volume in our history (with enough history)."""
    prior = v.shift(1).cummax()
    hist = v.notna().cumsum()
    return (v > prior) & (hist >= MIN_HIST), prior


def candidates(adjusted, universe, extra=()):
    """Tickers with a stored-history volume record in the last LOOKBACK sessions."""
    keep = set(universe) | set(extra)
    sub = adjusted[adjusted["ticker"].isin(keep)]
    c = sub.pivot_table(index="date", columns="ticker", values="c").sort_index()
    v = sub.pivot_table(index="date", columns="ticker", values="v").reindex_like(c)
    rec, _ = record_mask(c, v)
    liq = (c >= MIN_PRICE) & (c * v >= MIN_DOLLARS)
    m = (rec & liq).iloc[-LOOKBACK:]
    return sorted(m.columns[m.any()].tolist())


def parse_months(js):
    """Yahoo daily chart JSON -> {YYYY-MM: [max volume, YYYY-MM-DD]}."""
    res = (js.get("chart") or {}).get("result") or []
    if not res:
        return {}
    r = res[0]
    off = int((r.get("meta") or {}).get("gmtoffset") or 0)
    q = ((r.get("indicators") or {}).get("quote") or [{}])[0]
    out = {}
    for t, vol in zip(r.get("timestamp") or [], q.get("volume") or []):
        if not vol:
            continue
        d = datetime.fromtimestamp(t + off, timezone.utc).strftime("%Y-%m-%d")
        m = d[:7]
        if m not in out or vol > out[m][0]:
            out[m] = [int(vol), d]
    return out


def refresh_ever(tickers, session=None, cache=None):
    """Fetch full daily history for new/stale candidates. Never raises."""
    cache = load() if cache is None else cache
    session = session or requests.Session()
    today = date.today()
    got = fails = 0
    for t in tickers:
        rec = cache.get(t)
        if rec:
            try:
                if (today - date.fromisoformat(rec.get("asof", "2000-01-01"))).days <= REFRESH_DAYS:
                    continue
            except ValueError:
                pass
        try:
            r = session.get(URL.format(t=t.replace(".", "-")), params={"range": "max", "interval": "1d"},
                            headers={"User-Agent": "Mozilla/5.0 (breadth-monitor)"}, timeout=25)
            if r.status_code != 200:
                raise RuntimeError(r.status_code)
            months = parse_months(r.json())
            if months:
                cache[t] = {"months": months, "asof": today.isoformat(), "first": min(months)}
                got += 1
            fails = 0
        except Exception as e:
            fails += 1
            log.warning("hve: %s failed (%s)", t, e)
            if fails >= 8:
                log.warning("hve: source unreachable, stopping for this run")
                break
        time.sleep(PAUSE)
    if got:
        _path().write_text(json.dumps(cache, separators=(",", ":"), sort_keys=True))
    log.info("hve: %d histories fetched, %d cached", got, len(cache))
    return cache


def ever_check(cache, t, first_stored, rec_vol):
    """('ever' | 'not ever' | None, bigger-day date or first year of history)."""
    rec = cache.get(t)
    if not rec or not rec.get("months"):
        return None, None
    before = [(v, d) for m, (v, d) in rec["months"].items() if d < first_stored]
    if not before:
        return "ever", rec.get("first", "")[:4]          # listed inside our window: our history is all of it
    v, d = max(before)
    return ("ever", rec.get("first", "")[:4]) if rec_vol > v else ("not ever", d)


def evidence(c, v, h, l, spy, rating, regimes, liq):
    """Next-10-session result after an up day on record volume vs SPY, overall / RS 85+ / by regime."""
    rec, _ = record_mask(c, v)
    chg = c / c.shift(1) - 1
    loc = (c - l) / (h - l)
    up = rec & liq & (chg > 0) & (loc >= 0.5)
    cnt = (rec & liq).sum(axis=1)
    up = up & pd.DataFrame(np.repeat((cnt <= MASS_DAY).to_numpy()[:, None], c.shape[1], 1), index=c.index, columns=c.columns)
    base = liq & (v.notna().cumsum() >= MIN_HIST)
    fx = (c.shift(-HOLD) / c - 1).sub(spy.shift(-HOLD) / spy - 1, axis=0)
    f3 = (c.shift(-3) / c - 1).sub(spy.shift(-3) / spy - 1, axis=0)

    def st(m, F=fx):
        a = F.where(m).stack().dropna()
        if len(a) < 10:
            return {"n": int(len(a))}
        return {"n": int(len(a)), "ret": round(float(a.mean()), 4), "median": round(float(a.median()), 4),
                "win": round(float((a > 0).mean()), 3), "t": round(float(a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))), 2)}

    reg = pd.DataFrame(np.repeat(regimes.reindex(c.index).ffill().fillna("mixed").to_numpy(dtype=object)[:, None],
                                 c.shape[1], 1), index=c.index, columns=c.columns)
    out = {"hold": HOLD, "from": str(c.index[MIN_HIST].date()) if len(c) > MIN_HIST else None,
           "to": str(c.index[max(0, len(c) - HOLD - 1)].date()),
           "up": st(up), "up3": st(up, f3), "base": st(base), "up_rs85": st(up & (rating >= 85)) if rating is not None else None,
           "down": st(rec & liq & (chg < 0) & pd.DataFrame(np.repeat((cnt <= MASS_DAY).to_numpy()[:, None], c.shape[1], 1), index=c.index, columns=c.columns))}
    for k in ("strong", "mixed", "weak"):
        out["up_" + k] = st(up & (reg == k))
    return out


def screen(w, rating, universe, names, theme_of=None, cache=None, regimes=None):
    """Rows for the last LOOKBACK sessions + evidence. w = strength.wide_all frames (all tickers)."""
    theme_of = theme_of or {}
    cache = load() if cache is None else cache
    cols = [t for t in w["c"].columns if t in set(universe) or t in theme_of]
    c, v, h, l, o = (w[k][cols] for k in ("c", "v", "h", "l", "o"))
    rec, prior = record_mask(c, v)
    liq = (c >= MIN_PRICE) & (c * v >= MIN_DOLLARS)
    hit = rec & liq
    cnt = hit.sum(axis=1)
    v50 = v.shift(1).rolling(50, min_periods=30).mean()
    first_stored = c.index[0].strftime("%Y-%m-%d")
    N = len(c)
    last = N - 1
    rows = []
    for i in range(max(0, N - LOOKBACK), N):
        d = c.index[i]
        for t in hit.columns[hit.iloc[i].to_numpy()]:
            vol, pv = float(v.iat[i, cols.index(t)]), float(prior.iat[i, cols.index(t)])
            ci, pc = float(c[t].iat[i]), float(c[t].iat[i - 1])
            hi, lo, op = float(h[t].iat[i]), float(l[t].iat[i]), float(o[t].iat[i])
            ever, ref = ever_check(cache, t, first_stored, vol)
            r = rating.iloc[i].get(t) if rating is not None and d in rating.index else None
            rows.append({"t": t, "name": names.get(t, ""), "date": d.strftime("%Y-%m-%d"), "dow": d.strftime("%a"),
                         "ago": int(last - i), "vol": int(vol), "prev_rec": int(pv), "vs_prev": round(vol / pv, 2) if pv else None,
                         "x50": round(vol / float(v50[t].iat[i]), 1) if v50[t].iat[i] == v50[t].iat[i] and v50[t].iat[i] else None,
                         "chg": round(ci / pc - 1, 4) if pc else None, "gap": round(op / pc - 1, 4) if pc else None,
                         "loc": round((ci - lo) / (hi - lo), 2) if hi > lo else None, "hi": round(hi, 2), "lo": round(lo, 2),
                         "close": round(ci, 2), "price": round(float(c[t].iat[last]), 2),
                         "since": round(float(c[t].iat[last]) / ci - 1, 4), "above_lo": bool(float(c[t].iat[last]) >= lo),
                         "dollars": round(vol * ci / 1e6, 1), "rsr": None if r is None or r != r else int(r),
                         "ever": ever, "ever_ref": ref, "mass": bool(cnt.iat[i] > MASS_DAY), "day_count": int(cnt.iat[i]),
                         **theme_of.get(t, {})})
    latest = {}
    for r in sorted(rows, key=lambda r: r["ago"]):          # one row per stock: its latest record day
        if r["t"] in latest:
            latest[r["t"]].setdefault("also", []).append(f'{r["dow"]} {r["date"][5:]}')
        else:
            latest[r["t"]] = r
    rows = sorted(latest.values(), key=lambda r: (r["ago"], -(r["dollars"] or 0)))
    ev = None
    try:
        if "SPY" not in w["c"].columns:
            raise LookupError("no SPY")
        ev = evidence(c, v, h, l, w["c"]["SPY"], rating.reindex(index=c.index, columns=c.columns) if rating is not None else None,
                      regimes if regimes is not None else pd.Series(dtype=object), liq)
    except LookupError:
        ev = None
    except Exception as e:
        log.exception("hve evidence failed: %s", e)
    return {"rows": rows[:120], "count": len(rows), "evidence": ev,
            "days": [{"date": c.index[i].strftime("%Y-%m-%d"), "dow": c.index[i].strftime("%a"), "n": int(cnt.iat[i])}
                     for i in range(max(0, N - LOOKBACK), N)]}
