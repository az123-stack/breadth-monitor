"""Base watch (Nov 27, 2026; Adam: "give me a tab to watch these and move it to the top. Tier A and Tier B ... I want to track these").
Hand-picked multi-year box (Stage 1 -> 2) breakouts from tools/base_breakout/scan.py, ranked on our evidence (4-6 week RS inside a leading
sub-theme, quiet base, not defensive). List lives in data/base_watch.csv (ticker, tier, added, ref_px, box_top, note) — edit it to add/drop.
State per stock from daily closes vs the box top:
  below   > 3% under the top              · at_top  within 3% under
  breakout closed above the top, < 10% over, first close above <= 10 sessions ago
  retest  broke out earlier, now back within 3% of the top (add zone) · riding  above, < 10% over, older breakout
  extended > 10% over the top (don't chase) · failed  broke out in the last 30 sessions, now closed 8%+ under the top
Info only: never touches picks."""
from __future__ import annotations
import csv
from pathlib import Path
import numpy as np
import pandas as pd

CSV = Path(__file__).resolve().parent.parent / "data" / "base_watch.csv"
NEAR, EXT, FAIL = 0.03, 0.10, 0.08


def load(path=CSV):
    try:
        with open(path, newline="") as f:
            return [r for r in csv.DictReader(f) if r.get("ticker")]
    except FileNotFoundError:
        return []


def state_of(closes, top):
    """closes: list/array of daily closes (oldest first). Returns (state, sessions since first close above the top in this run or None)."""
    c = np.asarray(closes, float)
    if not len(c) or not top:
        return "below", None
    above = c > top
    pos = c[-1] / top - 1
    # most recent breakout = first close above the top after the last close under top*(1-NEAR)
    brk = None
    if above.any():
        under = np.where(c < top * (1 - NEAR))[0]
        start = under[-1] + 1 if len(under) else 0
        idx = np.where(above[start:])[0]
        if len(idx):
            brk = int(len(c) - 1 - (start + idx[0]))
    last_above = np.where(above)[0]
    ago_above = int(len(c) - 1 - last_above[-1]) if len(last_above) else None
    if pos <= -FAIL and ago_above is not None and ago_above <= 30:
        return "failed", None
    if pos > EXT:
        return "extended", brk
    if pos > 0:
        return ("breakout" if brk is not None and brk <= 10 else "riding"), brk
    if pos >= -NEAR:
        return ("retest" if ago_above is not None and ago_above <= 30 else "at_top"), brk
    return "below", None


def build(adjusted, theme_data, path=CSV):
    rows = load(path)
    if not rows:
        return None
    stocks = {s["t"]: s for s in theme_data.get("stocks", [])}
    subs = {s.get("theme"): s for s in theme_data.get("subthemes", [])}
    nsub = len(subs)
    df = adjusted[adjusted["ticker"].isin([r["ticker"] for r in rows])].sort_values("date")
    out, last = [], None
    for r in rows:
        t = r["ticker"]; top = float(r["box_top"])
        g = df[df["ticker"] == t]
        s = stocks.get(t, {})
        if g.empty:
            out.append({"t": t, "tier": r["tier"], "top": top, "note": r.get("note", ""), "state": "nodata"}); continue
        c = g["c"].to_numpy(float)
        last = max(last, g["date"].iloc[-1]) if last is not None else g["date"].iloc[-1]
        st, brk = state_of(c[-120:], top)
        e21 = pd.Series(c).ewm(span=21, adjust=False).mean().iloc[-1]
        ref = float(r.get("ref_px") or 0) or None
        sb = subs.get(s.get("sub"), {})
        out.append({"t": t, "tier": r["tier"], "name": s.get("name"), "price": round(float(c[-1]), 2), "top": top,
                    "vs_top": round(float(c[-1] / top - 1), 4), "brk_ago": brk, "state": st, "ema21": round(float(e21), 2),
                    "above21": bool(c[-1] > e21), "stop": round(top * (1 - FAIL), 2), "rs": s.get("rsr"), "rs4w": s.get("rs4w"),
                    "rs6w": s.get("rs6w"), "sub": s.get("sub"), "sub_rank": sb.get("rank"), "sub_n": nsub, "vdry": s.get("vdry"),
                    "adr": s.get("adr"), "added": r.get("added"), "ref_px": ref, "since": round(float(c[-1] / ref - 1), 4) if ref else None,
                    "note": r.get("note", "")})
    order = {"A": 0, "B": 1}
    out.sort(key=lambda x: (order.get(x["tier"], 9), -(x.get("rs") or 0)))
    return {"date": str(pd.Timestamp(last).date()) if last is not None else None, "rows": out,
            "rules": {"near": NEAR, "ext": EXT, "fail": FAIL}}
