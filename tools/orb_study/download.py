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
    ap.add_argument("--outdir", default="orbdata")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--chunk", type=int, default=50)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    tks, start, end = tickers()
    if a.limit:
        tks = tks[: a.limit]
    os.makedirs(a.outdir, exist_ok=True)
    done = set()
    for f in sorted(os.listdir(a.outdir)):          # resume: tickers already in saved parts
        if f.endswith(".parquet"):
            done |= set(pd.read_parquet(os.path.join(a.outdir, f), columns=["ticker"]).ticker.unique())
    done_file = os.path.join(a.outdir, "done.txt")
    if os.path.exists(done_file):                    # tickers tried before that returned nothing
        done |= set(open(done_file).read().split())
    part = len([f for f in os.listdir(a.outdir) if f.endswith(".parquet")])
    cols = ["ticker", "date", "m", "o", "h", "l", "c", "v"]
    cli = MassiveClient()
    todo = [t for t in tks if t not in done]
    log.info("tickers %d, already have %d, to fetch %d, %s..%s", len(tks), len(done), len(todo), start, end)
    buf, tried, empty = [], [], []
    for i, t in enumerate(todo, 1):
        try:
            rows = fetch(cli, t, start, end)
        except Exception as e:  # keep going; a failed ticker is just missing (not marked done, retried next run)
            log.warning("%s failed: %s", t, e)
            rows = None
        if rows is not None:
            tried.append(t)
            if not rows:
                empty.append(t)
            buf.extend(rows)
        if i % a.chunk == 0 or i == len(todo):
            if buf:
                df = pd.DataFrame(buf, columns=cols)
                df["date"] = pd.to_datetime(df["date"])
                for k in "ohlc":
                    df[k] = df[k].astype("float32")
                df["m"] = df["m"].astype("int16")
                df.to_parquet(os.path.join(a.outdir, f"part_{part:03d}.parquet"), index=False)
                part += 1
            with open(done_file, "a") as fh:
                fh.write("\n".join(tried) + "\n")
            buf, tried = [], []
            log.info("%d/%d saved (part %d), empty so far %d", i, len(todo), part, len(empty))
    log.info("empty tickers: %s", " ".join(empty))


if __name__ == "__main__":
    main()
