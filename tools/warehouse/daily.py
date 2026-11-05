"""Step-2 data (PLAN2.md v9.1): Yahoo DAILY bars from 2014 + true MONTHLY bars (period1 = 0) + meta (firstTradeDate, instrumentType,
split events) for every theme / sub-theme / S&P 500 / Nasdaq-100 / Russell 2000 ticker plus SPY.
Runs in GitHub Actions (Claude's sandbox can't reach Yahoo): `python -m tools.warehouse.daily --outdir DIR [--limit N]`
→ DIR/daily/part_NNN.parquet (t, date, o, h, l, c, v; float32) and DIR/meta/part_NNN.json {t: {first, type, splits, monthly, status}}.
Parts of 100 tickers; a finished part is skipped, so a stopped run just resumes."""
import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from breadth import store  # noqa: E402

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{t}"
UA = {"User-Agent": "Mozilla/5.0 (breadth-monitor)"}
P1 = int(pd.Timestamp("2014-01-01", tz="UTC").timestamp())
PART = 100


def tickers():
    s = set(store.load_subthemes()["ticker"]) | set(store.load_themes()["ticker"])
    s |= set(pd.read_csv(ROOT / "data" / "index_members.csv")["ticker"])
    r2 = ROOT / "data" / "russell2000.csv"
    if r2.exists():
        s |= set(pd.read_csv(r2)["ticker"])
    s.add("SPY")
    return sorted(t for t in s if isinstance(t, str) and t)


def get(sess, t, params):
    for k in range(3):
        r = sess.get(URL.format(t=t.replace(".", "-")), params=params, headers=UA, timeout=25)
        if r.status_code == 429:
            time.sleep(20 * (k + 1))
            continue
        if r.status_code != 200:
            return None, r.status_code
        res = ((r.json().get("chart") or {}).get("result") or [None])[0]
        return res, 200
    return None, 429


def daily(sess, t):
    res, st = get(sess, t, {"period1": P1, "period2": int(time.time()), "interval": "1d", "events": "split"})
    if not res:
        return None, None, st
    ts = res.get("timestamp") or []
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    df = pd.DataFrame({"date": pd.to_datetime(ts, unit="s").normalize(), "o": q.get("open"), "h": q.get("high"), "l": q.get("low"),
                       "c": q.get("close"), "v": q.get("volume")}).dropna(subset=["c"])
    df.insert(0, "t", t)
    meta = res.get("meta") or {}
    sp = (res.get("events") or {}).get("splits") or {}
    info = {"first": meta.get("firstTradeDate"), "type": meta.get("instrumentType"),
            "splits": sorted([[pd.Timestamp(int(v["date"]), unit="s").strftime("%Y-%m-%d"), v.get("numerator"), v.get("denominator")]
                              for v in sp.values()])}
    return df, info, st


def monthly(sess, t):
    res, st = get(sess, t, {"period1": 0, "period2": int(time.time()), "interval": "1mo"})
    if not res:
        return None, st
    ts = res.get("timestamp") or []
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    out = []
    for i, t0 in enumerate(ts):
        h, l, c = (q.get(k, [None])[i] for k in ("high", "low", "close"))
        if h is None or c is None:
            continue
        out.append([pd.Timestamp(t0, unit="s").strftime("%Y-%m-%d"), round(h, 4), round(l, 4) if l is not None else None, round(c, 4)])
    return out, st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--budget", type=int, default=19000)
    a = ap.parse_args()
    out = Path(a.outdir)
    (out / "daily").mkdir(parents=True, exist_ok=True)
    (out / "meta").mkdir(parents=True, exist_ok=True)
    T = tickers()
    if a.limit:
        T = T[:a.limit]
    sess, t0 = requests.Session(), time.time()
    print(f"{len(T)} tickers in {(len(T) + PART - 1) // PART} parts", flush=True)
    for p in range(0, len(T), PART):
        name = f"part_{p // PART:03d}"
        mp = out / "meta" / f"{name}.json"
        if mp.exists() and set(T[p:p + PART]) <= set(json.loads(mp.read_text())):
            continue          # finished part (a --limit test run leaves a partial part that gets redone)
        if time.time() - t0 > a.budget:
            print("time budget reached; run again to resume"); break
        frames, meta, fails = [], {}, 0
        for t in T[p:p + PART]:
            try:
                df, info, st = daily(sess, t)
                time.sleep(0.35)
                m, st2 = monthly(sess, t)
                time.sleep(0.35)
            except Exception as e:  # network hiccup: record and move on
                df, info, st, m, st2 = None, None, str(e)[:60], None, None
            if df is not None and len(df):
                frames.append(df)
            meta[t] = {**(info or {}), "monthly": m, "status": [st, st2]}
            fails = fails + 1 if df is None else 0
            if fails >= 25:
                print("25 failures in a row; stopping (statuses in meta)"); break
        if fails >= 25:
            break
        if frames:
            D = pd.concat(frames)
            for k in ("o", "h", "l", "c"):
                D[k] = D[k].astype("float32")
            D["v"] = D["v"].fillna(0).astype("float64")
            D.to_parquet(out / "daily" / f"{name}.parquet", index=False)
        (out / "meta" / f"{name}.json").write_text(json.dumps(meta, separators=(",", ":")))
        ok = sum(1 for v in meta.values() if v["status"][0] == 200)
        print(f"{name}: {ok}/{len(meta)} ok · {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
