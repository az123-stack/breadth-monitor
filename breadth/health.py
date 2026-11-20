"""Breadth data health check (Nov 20, 2026; Adam: "we're missing data in a bunch of our breadth graphs ... make sure this doesn't
happen again").

What was "missing" on Nov 20 was not lost data: the 52-week measures (new highs / lows, % near a high, SPY off its high) need a year
of price history before their first value, and the bar store only reaches back to Nov 2024 (Massive free plan ~2 years), so they
start Oct 15, 2025. Those warm-up stretches are now labelled on the charts. This check guards against REAL gaps:

  1. every NYSE session between the first and last row of data/breadth.csv is present (no skipped day);
  2. every bar file exists for every session in the bar store;
  3. no metric goes blank after it has started (an interior gap = a day computed with missing inputs);
  4. the latest row has every core metric.

  python -m breadth.health          print a report; exit 1 (red run in GitHub Actions, which emails Adam) if anything is wrong
Also exposed as `problems()` for the page (DATA.health → ⚠ banner on the Breadth tab) and tests.
"""
from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

import pandas as pd

from . import nyse

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "breadth.csv"
BARS = ROOT / "data" / "bars"
# metrics the latest row must always have (the rest may legitimately be blank, e.g. FINRA lags)
CORE = ["up4", "dn4", "ratio5", "ratio10", "t2108", "nh", "nl", "pct_near", "dv_net", "dn_share", "vtilt10"]
# columns allowed to have holes (external feeds that can skip a day)
OPTIONAL = {"finra", "dix", "dix_dev"}


def problems(csv: Path = CSV, bars: Path = BARS) -> list[str]:
    out: list[str] = []
    if not csv.exists():
        return [f"{csv.name} is missing"]
    b = pd.read_csv(csv, parse_dates=["date"]).sort_values("date")
    if b.empty:
        return [f"{csv.name} is empty"]
    have = set(b["date"].dt.date)
    first, last = b["date"].iloc[0].date(), b["date"].iloc[-1].date()
    miss = [d.date() for d in pd.bdate_range(first, last) if nyse.is_session(d.date()) and d.date() not in have]
    if miss:
        out.append(f"breadth.csv skips {len(miss)} session(s): {', '.join(map(str, miss[:8]))}")
    dup = b["date"][b["date"].duplicated()].dt.date.tolist()
    if dup:
        out.append(f"breadth.csv has duplicate dates: {', '.join(map(str, dup[:8]))}")
    files = glob.glob(str(bars / "*.parquet"))
    if files:
        bd = {pd.Timestamp(os.path.basename(f)[:10]).date() for f in files}
        bmiss = [d.date() for d in pd.bdate_range(min(bd), max(bd)) if nyse.is_session(d.date()) and d.date() not in bd]
        if bmiss:
            out.append(f"bar store is missing {len(bmiss)} session(s): {', '.join(map(str, bmiss[:8]))}")
    s = b.set_index("date")
    for c in s.columns:
        if c in OPTIONAL or not pd.api.types.is_numeric_dtype(s[c]):
            continue
        fv = s[c].first_valid_index()
        if fv is None:
            continue
        holes = s.loc[fv:, c]
        holes = holes[holes.isna()]
        if len(holes):
            out.append(f"{c} is blank on {len(holes)} day(s) after it started: {', '.join(str(d.date()) for d in holes.index[:6])}")
    lastrow = b.iloc[-1]
    blank = [c for c in CORE if c in b.columns and pd.isna(lastrow[c])]
    if blank:
        out.append(f"latest row ({last}) is missing {', '.join(blank)}")
    return out


def main() -> int:
    p = problems()
    if p:
        print("BREADTH DATA PROBLEMS:")
        for x in p:
            print(" -", x)
        return 1
    b = pd.read_csv(CSV, usecols=["date"])
    print(f"ok: breadth.csv {b['date'].iloc[0]} .. {b['date'].iloc[-1]}, no skipped sessions or gaps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
