"""Download 15-minute bars (regular session only) for every liquid sub-theme stock + SPY/QQQ.

One-off for the ORB x sub-theme study (Oct 24, 2026). Runs in GitHub Actions (needs MASSIVE_API_KEY):
    python -m tools.orb_study.download --out orb15.parquet
One call per ticker (15-min bars incl. extended hours for ~2 years is ~32k rows, under the 50k limit),
12.5 s apart on the free plan, so ~1,040 tickers take ~3.6 hours. Saves a checkpoint every 50 tickers
and resumes from an existing output file.
"""
import argparse
import logging
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from breadth import store
from breadth.massive import MassiveClient

ET = ZoneInfo("America/New_York")
log = logging.getLogger("orb_download")


def tickers(min_dv=5e6, min_px=5.0):
    st = pd.read_csv("data/subthemes.csv")
    b = store.apply_splits(store.load_bars(), store.load_splits())
    x = b[b.ticker.isin(set(st.ticker))].copy()
    x["dv"] = x.c * x.v
    g = x.groupby("ticker").agg(dv=("dv", "median"), c=("c", "median"))
    keep = sorted(g[(g.dv >= min_dv) & (g.c >= min_px)].index)
    return ["SPY", "QQQ"] + [t for t in keep if t not in ("SPY", "QQQ")], b.date.min().date(), b.date.max().date()


def fetch(cli, t, start, end):
    path = f"/v2/aggs/ticker/{t}/range/15/minute/{start.isoformat()}/{end.isoformat()}"
    rows = []
    for r in cli._paged(path, {"adjusted": "true", "sort": "asc", "limit": 50000}):
        if r.get("c") is None:
            continue
        ts = datetime.fromtimestamp(r["t"] / 1000, ET)
        mins = ts.hour * 60 + ts.minute
        if mins < 570 or mins >= 960:          # keep 9:30-15:45 bar starts (regular session)
            continue
        rows.append((t, ts.date(), mins - 570, r["o"], r["h"], r["l"], r["c"], r.get("v") or 0))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="orb15.parquet")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    tks, start, end = tickers()
    if a.limit:
        tks = tks[: a.limit]
    done, frames = set(), []
    if os.path.exists(a.out):
        old = pd.read_parquet(a.out)
        frames.append(old)
        done = set(old.ticker.unique())
    cols = ["ticker", "date", "m", "o", "h", "l", "c", "v"]
    cli = MassiveClient()
    todo = [t for t in tks if t not in done]
    log.info("tickers %d, already have %d, to fetch %d, %s..%s", len(tks), len(done), len(todo), start, end)
    buf, empty = [], []
    for i, t in enumerate(todo, 1):
        try:
            rows = fetch(cli, t, start, end)
        except Exception as e:  # keep going; a failed ticker is just missing
            log.warning("%s failed: %s", t, e)
            rows = []
        if not rows:
            empty.append(t)
        buf.extend(rows)
        if i % 50 == 0 or i == len(todo):
            frames.append(pd.DataFrame(buf, columns=cols))
            buf = []
            df = pd.concat(frames, ignore_index=True)
            df["date"] = pd.to_datetime(df["date"])
            df.to_parquet(a.out, index=False)
            frames = [df]
            log.info("%d/%d saved, rows %d, empty so far %d", i, len(todo), len(df), len(empty))
    log.info("empty tickers: %s", " ".join(empty))


if __name__ == "__main__":
    main()
